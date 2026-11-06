import dataclasses
import datetime
import enum

import labels


class Priority(enum.StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RoleInRepo(enum.StrEnum):
    READ = "read"
    TRIAGE = "triage"
    WRITE = "write"
    MAINTAIN = "maintain"
    ADMIN = "admin"


ROLES_WITH_TRIAGE_ACCESS = (
    RoleInRepo.TRIAGE,
    RoleInRepo.WRITE,
    RoleInRepo.MAINTAIN,
    RoleInRepo.ADMIN,
)
ROLES_WITH_WRITE_ACCESS = (
    RoleInRepo.WRITE,
    RoleInRepo.MAINTAIN,
    RoleInRepo.ADMIN,
)
PRIORITY_CHOICES = "|".join(Priority)
COMMAND_USAGES = {
    "/accept-review": "`/accept-review <YYYY-MM-DD>`, with the date you will review by",
    "/release-review": "`/release-review`",
    "/set-priority": f"`/set-priority <{PRIORITY_CHOICES}>`",
    "/set-milestone": "`/set-milestone <title|none>`",
    "/recompute-labels": "`/recompute-labels`",
}


@dataclasses.dataclass(frozen=True)
class Milestone:
    milestone_number: int
    title: str


@dataclasses.dataclass(frozen=True)
class PullRequest:
    pr_number: int
    author: str
    assignees: tuple[str, ...]
    label_names: tuple[str, ...]
    num_lines_changed: int
    file_paths: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class User:
    user_name: str
    role_in_repo: RoleInRepo


@dataclasses.dataclass(frozen=True)
class Comment:
    comment_id: int
    user: User
    text: str


@dataclasses.dataclass(frozen=True)
class MilestoneChange:
    milestone_number: int | None


@dataclasses.dataclass(frozen=True)
class UpdatePlan:
    label_names_to_add: tuple[str, ...] = ()
    label_names_to_remove: tuple[str, ...] = ()
    assignees_to_add: tuple[str, ...] = ()
    assignees_to_remove: tuple[str, ...] = ()
    milestone_change: MilestoneChange | None = None
    reply: str | None = None
    react: bool = False


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
) -> UpdatePlan:
    return UpdatePlan(reply=f"Use {COMMAND_USAGES[command_name]}.")


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
) -> UpdatePlan:
    return UpdatePlan(
        reply=f"Only the PR author and people with triage access or higher can use `{command_name}`.",
    )


def accept_review(
    pull_request: PullRequest,
    comment: Comment,
    argument: str,
    today: datetime.date,
) -> UpdatePlan:
    try:
        review_date = datetime.date.fromisoformat(argument)
    except ValueError:
        review_date = None
    if comment.user.role_in_repo not in ROLES_WITH_WRITE_ACCESS:
        return UpdatePlan(reply="Only people with write access can accept a review.")
    elif comment.user.user_name == pull_request.author:
        return UpdatePlan(reply="You can't accept the review of your own PR.")
    elif review_date is None:
        return _usage_reply("/accept-review")
    elif review_date < today:
        return UpdatePlan(
            reply=f"The review date has to be today or later. Use {COMMAND_USAGES['/accept-review']}.",
        )
    elif pull_request.assignees == (comment.user.user_name, ):
        return UpdatePlan(react=True)
    elif len(pull_request.assignees) > 0:
        return UpdatePlan(reply=_review_taken_reply(pull_request.assignees))
    else:
        return UpdatePlan(
            assignees_to_add=(comment.user.user_name, ),
            react=True,
        )


def release_review(
    pull_request: PullRequest,
    comment: Comment,
    argument: str,
) -> UpdatePlan:
    if argument != "":
        return _usage_reply("/release-review")
    elif comment.user.user_name in pull_request.assignees:
        return UpdatePlan(
            assignees_to_remove=(comment.user.user_name, ),
            react=True,
        )
    elif len(pull_request.assignees) > 0:
        return UpdatePlan(
            reply=
            f"{_mention_list(pull_request.assignees)} accepted this review, so only they can release it.",
        )
    else:
        return UpdatePlan(reply="Nobody has accepted this review yet.")


def set_priority(
    pull_request: PullRequest,
    argument: str,
) -> UpdatePlan:
    try:
        priority = Priority(argument.lower())
    except ValueError:
        return _usage_reply("/set-priority")
    wanted_label_name = f"{labels.PRIORITY_PREFIX}{priority}"
    label_names_to_remove = tuple(
        _label_name for _label_name in pull_request.label_names
        if (_label_name.startswith(labels.PRIORITY_PREFIX)) and (_label_name != wanted_label_name)
    )
    if wanted_label_name in pull_request.label_names:
        label_names_to_add = ()
    else:
        label_names_to_add = (wanted_label_name, )
    return UpdatePlan(
        label_names_to_add=label_names_to_add,
        label_names_to_remove=label_names_to_remove,
        react=True,
    )


def set_milestone(
    open_milestones: tuple[Milestone, ...],
    argument: str,
) -> UpdatePlan:
    matching_milestones = [
        _milestone for _milestone in open_milestones if _milestone.title.lower() == argument.lower()
    ]
    if argument == "":
        return _usage_reply("/set-milestone")
    elif argument.lower() == "none":
        return UpdatePlan(
            milestone_change=MilestoneChange(milestone_number=None),
            react=True,
        )
    elif len(matching_milestones) > 0:
        milestone_change = MilestoneChange(milestone_number=matching_milestones[0].milestone_number)
        return UpdatePlan(
            milestone_change=milestone_change,
            react=True,
        )
    elif len(open_milestones) == 0:
        return UpdatePlan(
            reply=f'No open milestone is called "{argument}", and there are no open milestones.',
        )
    else:
        milestone_titles = ", ".join(f"`{_milestone.title}`" for _milestone in open_milestones)
        return UpdatePlan(
            reply=f'No open milestone is called "{argument}". The open milestones are {milestone_titles}.',
        )


def recompute_labels(
    configured_labels: labels.ConfiguredLabels,
    pull_request: PullRequest,
    argument: str,
) -> UpdatePlan:
    if argument != "":
        return _usage_reply("/recompute-labels")
    label_changes = labels.compute_label_changes(
        configured_labels=configured_labels,
        current_label_names=pull_request.label_names,
        file_paths=pull_request.file_paths,
        num_lines_changed=pull_request.num_lines_changed,
    )
    return UpdatePlan(
        label_names_to_add=label_changes.label_names_to_add,
        label_names_to_remove=label_changes.label_names_to_remove,
        react=True,
    )


def handle_comment(
    configured_labels: labels.ConfiguredLabels,
    pull_request: PullRequest,
    comment: Comment,
    open_milestones: tuple[Milestone, ...],
    today: datetime.date,
) -> UpdatePlan | None:
    parsed_command = parse_command(comment.text)
    if parsed_command is None:
        return None
    command_name, argument = parsed_command
    commenter_is_author_or_triager = (
        (comment.user.user_name == pull_request.author)
        or (comment.user.role_in_repo in ROLES_WITH_TRIAGE_ACCESS)
    )
    if command_name == "/accept-review":
        return accept_review(pull_request, comment, argument, today)
    elif command_name == "/release-review":
        return release_review(pull_request, comment, argument)
    elif not commenter_is_author_or_triager:
        return _author_or_triage_only_reply(command_name)
    elif command_name == "/set-priority":
        return set_priority(pull_request, argument)
    elif command_name == "/set-milestone":
        return set_milestone(open_milestones, argument)
    else:
        return recompute_labels(configured_labels, pull_request, argument)
