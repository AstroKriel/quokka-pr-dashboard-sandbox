import dataclasses
import datetime

from pr_dashboard import compute_labels
from pr_dashboard import label_types
from pr_dashboard import pr_types

_ROLES_WITH_TRIAGE_ACCESS = (
    pr_types.RoleInRepo.TRIAGE,
    pr_types.RoleInRepo.WRITE,
    pr_types.RoleInRepo.MAINTAIN,
    pr_types.RoleInRepo.ADMIN,
)
_ROLES_WITH_WRITE_ACCESS = (
    pr_types.RoleInRepo.WRITE,
    pr_types.RoleInRepo.MAINTAIN,
    pr_types.RoleInRepo.ADMIN,
)


@dataclasses.dataclass(frozen=True)
class CommandHelp:
    usage: str
    description: str
    allowed_users: str


COMMAND_HELPS = {
    "/accept-review":
    CommandHelp(
        usage="`/accept-review <YYYY-MM-DD>`",
        description="take on this PR's review, with the date you will review by",
        allowed_users="write access",
    ),
    "/release-review":
    CommandHelp(
        usage="`/release-review`",
        description="give the review back",
        allowed_users="the current reviewer",
    ),
    "/set-priority":
    CommandHelp(
        usage="`/set-priority <{priority_values}>`",
        description="set this PR's priority",
        allowed_users="the PR author, or triage access or higher",
    ),
    "/set-milestone":
    CommandHelp(
        usage="`/set-milestone <title|none>`",
        description="set or remove this PR's milestone",
        allowed_users="the PR author, or triage access or higher",
    ),
    "/recompute-labels":
    CommandHelp(
        usage="`/recompute-labels`",
        description="recalculate the scope and size labels",
        allowed_users="the PR author, or triage access or higher",
    ),
    "/help":
    CommandHelp(
        usage="`/help`",
        description="show this list",
        allowed_users="anyone",
    ),
}
COMMAND_NAMES = tuple(COMMAND_HELPS)


def parse_command(
    comment_text: str,
) -> tuple[str, str] | None:
    lines = comment_text.strip().splitlines()
    if len(lines) == 0:
        return None
    first_line_words = lines[0].split(maxsplit=1)
    command_name = first_line_words[0]
    if command_name not in COMMAND_NAMES:
        return None
    if len(first_line_words) == 1:
        return command_name, ""
    else:
        return command_name, first_line_words[1].strip()


def _format_usage(
    *,
    command_name: str,
    priority_labels: label_types.PriorityLabels,
) -> str:
    priority_values = "|".join(_priority_label.value for _priority_label in priority_labels.labels)
    return COMMAND_HELPS[command_name].usage.format(priority_values=priority_values)


def _usage_reply(
    command_name: str,
) -> pr_types.UpdatePlan:
    return pr_types.UpdatePlan(reply=f"Use {COMMAND_HELPS[command_name].usage}.")


def _help_reply(
    priority_labels: label_types.PriorityLabels,
) -> pr_types.UpdatePlan:
    help_lines = ["PR dashboard commands:"]
    for command_name, command_help in COMMAND_HELPS.items():
        usage = _format_usage(
            command_name=command_name,
            priority_labels=priority_labels,
        )
        help_line = f"- {usage}: {command_help.description} ({command_help.allowed_users})"
        help_lines.append(help_line)
    return pr_types.UpdatePlan(reply="\n".join(help_lines))


def _mention_list(
    user_names: tuple[str, ...],
) -> str:
    mentions = [f"@{_user_name}" for _user_name in user_names]
    if len(mentions) == 1:
        return mentions[0]
    else:
        return ", ".join(mentions[:-1]) + " and " + mentions[-1]


def _review_taken_reply(
    assignee_user_names: tuple[str, ...],
) -> str:
    if len(assignee_user_names) == 1:
        verb = "has"
    else:
        verb = "have"
    return (
        f"{_mention_list(assignee_user_names)} {verb} accepted this review. "
        "You're welcome to leave a review or comment, or ask them to hand it over."
    )


def _author_or_triage_only_reply(
    command_name: str,
) -> pr_types.UpdatePlan:
    return pr_types.UpdatePlan(
        reply=f"Only the PR author and people with triage access or higher can use `{command_name}`.",
    )


def _accept_review(
    *,
    pull_request: pr_types.PullRequest,
    comment: pr_types.Comment,
    argument: str,
    today: datetime.date,
) -> pr_types.UpdatePlan:
    try:
        review_date = datetime.date.fromisoformat(argument)
    except ValueError:
        review_date = None
    if comment.user.role_in_repo not in _ROLES_WITH_WRITE_ACCESS:
        return pr_types.UpdatePlan(reply="Only people with write access can accept a review.")
    elif comment.user.user_name == pull_request.author_user_name:
        return pr_types.UpdatePlan(reply="You can't accept the review of your own PR.")
    elif review_date is None:
        return _usage_reply("/accept-review")
    elif review_date < today:
        return pr_types.UpdatePlan(
            reply=f"The review date has to be today or later. Use {COMMAND_HELPS['/accept-review'].usage}.",
        )
    elif pull_request.assignee_user_names == (comment.user.user_name, ):
        return pr_types.UpdatePlan(react=True)
    elif len(pull_request.assignee_user_names) > 0:
        return pr_types.UpdatePlan(reply=_review_taken_reply(pull_request.assignee_user_names))
    else:
        return pr_types.UpdatePlan(
            assignee_user_names_to_add=(comment.user.user_name, ),
            react=True,
        )


def _release_review(
    *,
    pull_request: pr_types.PullRequest,
    comment: pr_types.Comment,
    argument: str,
) -> pr_types.UpdatePlan:
    if argument != "":
        return _usage_reply("/release-review")
    elif comment.user.user_name in pull_request.assignee_user_names:
        return pr_types.UpdatePlan(
            assignee_user_names_to_remove=(comment.user.user_name, ),
            react=True,
        )
    elif len(pull_request.assignee_user_names) > 0:
        return pr_types.UpdatePlan(
            reply=
            f"{_mention_list(pull_request.assignee_user_names)} accepted this review, so only they can release it.",
        )
    else:
        return pr_types.UpdatePlan(reply="Nobody has accepted this review yet.")


def _set_priority(
    *,
    priority_labels: label_types.PriorityLabels,
    pull_request: pr_types.PullRequest,
    argument: str,
) -> pr_types.UpdatePlan:
    priority_label = priority_labels.get_label(argument)
    if priority_label is None:
        usage = _format_usage(
            command_name="/set-priority",
            priority_labels=priority_labels,
        )
        return pr_types.UpdatePlan(reply=f"Use {usage}.")
    wanted_label_name = priority_label.label_name
    label_names_to_remove = tuple(
        _label_name for _label_name in pull_request.label_names
        if priority_labels.check_has_prefix(_label_name) and (_label_name != wanted_label_name)
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
    *,
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
    *,
    configured_labels: label_types.ConfiguredLabels,
    pull_request: pr_types.PullRequest,
    argument: str,
) -> pr_types.UpdatePlan:
    if argument != "":
        return _usage_reply("/recompute-labels")
    label_changes = compute_labels.compute_label_changes(
        configured_labels=configured_labels,
        current_label_names=pull_request.label_names,
        edited_file_paths=pull_request.edited_file_paths,
        num_lines_changed=pull_request.num_lines_changed,
    )
    return pr_types.UpdatePlan(
        label_names_to_add=label_changes.label_names_to_add,
        label_names_to_remove=label_changes.label_names_to_remove,
        react=True,
    )


def handle_comment(
    *,
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
        (comment.user.user_name == pull_request.author_user_name)
        or (comment.user.role_in_repo in _ROLES_WITH_TRIAGE_ACCESS)
    )
    if command_name == "/help":
        return _help_reply(configured_labels.priority_labels)
    elif command_name == "/accept-review":
        return _accept_review(
            pull_request=pull_request,
            comment=comment,
            argument=argument,
            today=today,
        )
    elif command_name == "/release-review":
        return _release_review(
            pull_request=pull_request,
            comment=comment,
            argument=argument,
        )
    elif not commenter_is_author_or_triager:
        return _author_or_triage_only_reply(command_name)
    elif command_name == "/set-priority":
        return _set_priority(
            priority_labels=configured_labels.priority_labels,
            pull_request=pull_request,
            argument=argument,
        )
    elif command_name == "/set-milestone":
        return _set_milestone(
            open_milestones=open_milestones,
            argument=argument,
        )
    else:
        return recompute_labels(
            configured_labels=configured_labels,
            pull_request=pull_request,
            argument=argument,
        )
