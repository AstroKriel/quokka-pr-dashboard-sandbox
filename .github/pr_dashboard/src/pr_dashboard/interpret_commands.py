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
class Command:
    name: str
    argument_hint: str
    description: str
    allowed_users: str

    @property
    def usage(
        self,
    ) -> str:
        if self.argument_hint == "":
            return f"`{self.name}`"
        else:
            return f"`{self.name} {self.argument_hint}`"


ACCEPT_REVIEW = Command(
    name="/accept-review",
    argument_hint="<YYYY-MM-DD>",
    description="take on this PR's review, with the date you will review by",
    allowed_users="maintainers (anyone with write access)",
)
RELEASE_REVIEW = Command(
    name="/release-review",
    argument_hint="",
    description="give the review back",
    allowed_users="the current reviewer",
)
SET_PRIORITY = Command(
    name="/set-priority",
    argument_hint="<{priority_values}>",
    description="set this PR's priority",
    allowed_users="the PR author, or maintainers",
)
SET_MILESTONE = Command(
    name="/set-milestone",
    argument_hint="<title|none>",
    description="set or remove this PR's milestone",
    allowed_users="the PR author, or maintainers",
)
RECOMPUTE_LABELS = Command(
    name="/recompute-labels",
    argument_hint="",
    description="recalculate the scope and size labels",
    allowed_users="the PR author, or maintainers",
)
HELP = Command(
    name="/help",
    argument_hint="",
    description="show this list",
    allowed_users="anyone",
)
COMMANDS = (
    ACCEPT_REVIEW,
    RELEASE_REVIEW,
    SET_PRIORITY,
    SET_MILESTONE,
    RECOMPUTE_LABELS,
    HELP,
)


def parse_command(
    comment_text: str,
) -> tuple[Command, str] | None:
    lines = comment_text.strip().splitlines()
    if len(lines) == 0:
        return None
    first_line_words = lines[0].split(maxsplit=1)
    matching_commands = [_command for _command in COMMANDS if _command.name == first_line_words[0]]
    if len(matching_commands) == 0:
        return None
    command = matching_commands[0]
    if len(first_line_words) == 1:
        return command, ""
    else:
        return command, first_line_words[1].strip()


def _format_usage(
    *,
    command: Command,
    priority_labels: label_types.PriorityLabels,
) -> str:
    priority_values = "|".join(_priority_label.value for _priority_label in priority_labels.labels)
    return command.usage.format(priority_values=priority_values)


def _usage_reply(
    command: Command,
) -> pr_types.UpdatePlan:
    return pr_types.UpdatePlan(reply=f"Use {command.usage}.")


def _help_reply(
    priority_labels: label_types.PriorityLabels,
) -> pr_types.UpdatePlan:
    help_lines = ["PR dashboard commands:"]
    for command in COMMANDS:
        usage = _format_usage(
            command=command,
            priority_labels=priority_labels,
        )
        help_line = f"- {usage}: {command.description}. For {command.allowed_users}."
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
    command: Command,
) -> pr_types.UpdatePlan:
    return pr_types.UpdatePlan(
        reply=f"Only the PR author and maintainers can use `{command.name}`.",
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
        return pr_types.UpdatePlan(reply="Only maintainers (anyone with write access) can accept a review.")
    elif comment.user.user_name == pull_request.author_user_name:
        return pr_types.UpdatePlan(reply="You can't accept the review of your own PR.")
    elif review_date is None:
        return _usage_reply(ACCEPT_REVIEW)
    elif review_date < today:
        return pr_types.UpdatePlan(
            reply=f"The review date has to be today or later. Use {ACCEPT_REVIEW.usage}.",
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
        return _usage_reply(RELEASE_REVIEW)
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
            command=SET_PRIORITY,
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
        return _usage_reply(SET_MILESTONE)
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
        return _usage_reply(RECOMPUTE_LABELS)
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


def make_comment_update_plan(
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
    command, argument = parsed_command
    commenter_is_author_or_triager = (
        (comment.user.user_name == pull_request.author_user_name)
        or (comment.user.role_in_repo in _ROLES_WITH_TRIAGE_ACCESS)
    )
    if command == HELP:
        return _help_reply(configured_labels.priority_labels)
    elif command == ACCEPT_REVIEW:
        return _accept_review(
            pull_request=pull_request,
            comment=comment,
            argument=argument,
            today=today,
        )
    elif command == RELEASE_REVIEW:
        return _release_review(
            pull_request=pull_request,
            comment=comment,
            argument=argument,
        )
    elif not commenter_is_author_or_triager:
        return _author_or_triage_only_reply(command)
    elif command == SET_PRIORITY:
        return _set_priority(
            priority_labels=configured_labels.priority_labels,
            pull_request=pull_request,
            argument=argument,
        )
    elif command == SET_MILESTONE:
        return _set_milestone(
            open_milestones=open_milestones,
            argument=argument,
        )
    elif command == RECOMPUTE_LABELS:
        return recompute_labels(
            configured_labels=configured_labels,
            pull_request=pull_request,
            argument=argument,
        )
    else:
        command_names = ", ".join(f"`{_command.name}`" for _command in COMMANDS)
        raise ValueError(f"`command` must be one of {{{command_names}}}; got `{command.name}`.")
