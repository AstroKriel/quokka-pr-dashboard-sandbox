import datetime

from pr_dashboard import compute_labels
from pr_dashboard import label_types
from pr_dashboard import pr_types

ROLES_WITH_TRIAGE_ACCESS = (
    pr_types.RoleInRepo.TRIAGE,
    pr_types.RoleInRepo.WRITE,
    pr_types.RoleInRepo.MAINTAIN,
    pr_types.RoleInRepo.ADMIN,
)
ROLES_WITH_WRITE_ACCESS = (
    pr_types.RoleInRepo.WRITE,
    pr_types.RoleInRepo.MAINTAIN,
    pr_types.RoleInRepo.ADMIN,
)
PRIORITY_CHOICES = "|".join(pr_types.Priority)
COMMAND_USAGES = {
    "/accept-review": "`/accept-review <YYYY-MM-DD>`, with the date you will review by",
    "/release-review": "`/release-review`",
    "/set-priority": f"`/set-priority <{PRIORITY_CHOICES}>`",
    "/set-milestone": "`/set-milestone <title|none>`",
    "/recompute-labels": "`/recompute-labels`",
}


def parse_command(
    comment_text: str,
) -> tuple[str, str] | None:
    lines = comment_text.strip().splitlines()
    if len(lines) == 0:
        return None
    first_line_words = lines[0].split(maxsplit=1)
    command_name = first_line_words[0]
    if command_name not in COMMAND_USAGES:
        return None
    if len(first_line_words) == 1:
        return command_name, ""
    else:
        return command_name, first_line_words[1].strip()


def _usage_reply(
    command_name: str,
) -> pr_types.UpdatePlan:
    return pr_types.UpdatePlan(reply=f"Use {COMMAND_USAGES[command_name]}.")


def _mention_list(
    user_names: tuple[str, ...],
) -> str:
    mentions = [f"@{_user_name}" for _user_name in user_names]
    if len(mentions) == 1:
        return mentions[0]
    else:
        return ", ".join(mentions[:-1]) + " and " + mentions[-1]


def _review_taken_reply(
    assignees: tuple[str, ...],
) -> str:
    if len(assignees) == 1:
        verb = "has"
    else:
        verb = "have"
    return (
        f"{_mention_list(assignees)} {verb} accepted this review. "
        "You're welcome to leave a review or comment, or ask them to hand it over."
    )


def _author_or_triage_only_reply(
    command_name: str,
) -> pr_types.UpdatePlan:
    return pr_types.UpdatePlan(
        reply=f"Only the PR author and people with triage access or higher can use `{command_name}`.",
    )


def _accept_review(
    pull_request: pr_types.PullRequest,
    comment: pr_types.Comment,
    argument: str,
    today: datetime.date,
) -> pr_types.UpdatePlan:
    try:
        review_date = datetime.date.fromisoformat(argument)
    except ValueError:
        review_date = None
    if comment.user.role_in_repo not in ROLES_WITH_WRITE_ACCESS:
        return pr_types.UpdatePlan(reply="Only people with write access can accept a review.")
    elif comment.user.user_name == pull_request.author:
        return pr_types.UpdatePlan(reply="You can't accept the review of your own PR.")
    elif review_date is None:
        return _usage_reply("/accept-review")
    elif review_date < today:
        return pr_types.UpdatePlan(
            reply=f"The review date has to be today or later. Use {COMMAND_USAGES['/accept-review']}.",
        )
    elif pull_request.assignees == (comment.user.user_name, ):
        return pr_types.UpdatePlan(react=True)
    elif len(pull_request.assignees) > 0:
        return pr_types.UpdatePlan(reply=_review_taken_reply(pull_request.assignees))
    else:
        return pr_types.UpdatePlan(
            assignees_to_add=(comment.user.user_name, ),
            react=True,
        )


def _release_review(
    pull_request: pr_types.PullRequest,
    comment: pr_types.Comment,
    argument: str,
) -> pr_types.UpdatePlan:
    if argument != "":
        return _usage_reply("/release-review")
    elif comment.user.user_name in pull_request.assignees:
        return pr_types.UpdatePlan(
            assignees_to_remove=(comment.user.user_name, ),
            react=True,
        )
    elif len(pull_request.assignees) > 0:
        return pr_types.UpdatePlan(
            reply=
            f"{_mention_list(pull_request.assignees)} accepted this review, so only they can release it.",
        )
    else:
        return pr_types.UpdatePlan(reply="Nobody has accepted this review yet.")


def _set_priority(
    pull_request: pr_types.PullRequest,
    argument: str,
) -> pr_types.UpdatePlan:
    try:
        priority = pr_types.Priority(argument.lower())
    except ValueError:
        return _usage_reply("/set-priority")
    wanted_label_name = f"{label_types.PRIORITY_PREFIX}{priority}"
    label_names_to_remove = tuple(
        _label_name for _label_name in pull_request.label_names
        if (_label_name.startswith(label_types.PRIORITY_PREFIX)) and (_label_name != wanted_label_name)
    )
    if wanted_label_name in pull_request.label_names:
        label_names_to_add = ()
    else:
        label_names_to_add = (wanted_label_name, )
    return pr_types.UpdatePlan(
        label_names_to_add=label_names_to_add,
        label_names_to_remove=label_names_to_remove,
        react=True,
    )


def _set_milestone(
    open_milestones: tuple[pr_types.Milestone, ...],
    argument: str,
) -> pr_types.UpdatePlan:
    matching_milestones = [
        _milestone for _milestone in open_milestones if _milestone.title.lower() == argument.lower()
    ]
    if argument == "":
        return _usage_reply("/set-milestone")
    elif argument.lower() == "none":
        return pr_types.UpdatePlan(
            milestone_change=pr_types.MilestoneChange(milestone_number=None),
            react=True,
        )
    elif len(matching_milestones) > 0:
        milestone_change = pr_types.MilestoneChange(milestone_number=matching_milestones[0].milestone_number)
        return pr_types.UpdatePlan(
            milestone_change=milestone_change,
            react=True,
        )
    elif len(open_milestones) == 0:
        return pr_types.UpdatePlan(
            reply=f'No open milestone is called "{argument}", and there are no open milestones.',
        )
    else:
        milestone_titles = ", ".join(f"`{_milestone.title}`" for _milestone in open_milestones)
        return pr_types.UpdatePlan(
            reply=f'No open milestone is called "{argument}". The open milestones are {milestone_titles}.',
        )


def recompute_labels(
    configured_labels: label_types.ConfiguredLabels,
    pull_request: pr_types.PullRequest,
    argument: str,
) -> pr_types.UpdatePlan:
    if argument != "":
        return _usage_reply("/recompute-labels")
    label_changes = compute_labels.compute_label_changes(
        configured_labels=configured_labels,
        current_label_names=pull_request.label_names,
        file_paths=pull_request.file_paths,
        num_lines_changed=pull_request.num_lines_changed,
    )
    return pr_types.UpdatePlan(
        label_names_to_add=label_changes.label_names_to_add,
        label_names_to_remove=label_changes.label_names_to_remove,
        react=True,
    )


def handle_comment(
    configured_labels: label_types.ConfiguredLabels,
    pull_request: pr_types.PullRequest,
    comment: pr_types.Comment,
    open_milestones: tuple[pr_types.Milestone, ...],
    today: datetime.date,
) -> pr_types.UpdatePlan | None:
    parsed_command = parse_command(comment.text)
    if parsed_command is None:
        return None
    command_name, argument = parsed_command
    commenter_is_author_or_triager = (
        (comment.user.user_name == pull_request.author)
        or (comment.user.role_in_repo in ROLES_WITH_TRIAGE_ACCESS)
    )
    if command_name == "/accept-review":
        return _accept_review(pull_request, comment, argument, today)
    elif command_name == "/release-review":
        return _release_review(pull_request, comment, argument)
    elif not commenter_is_author_or_triager:
        return _author_or_triage_only_reply(command_name)
    elif command_name == "/set-priority":
        return _set_priority(pull_request, argument)
    elif command_name == "/set-milestone":
        return _set_milestone(open_milestones, argument)
    else:
        return recompute_labels(configured_labels, pull_request, argument)
