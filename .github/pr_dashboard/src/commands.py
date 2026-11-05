import dataclasses
import datetime

import labels

PRIORITY_LEVELS = ("low", "medium", "high")
COMMAND_USAGES = {
    "/accept-review": "`/accept-review <YYYY-MM-DD>`, with the date you will review by",
    "/release-review": "`/release-review`",
    "/set-priority": "`/set-priority <low|medium|high>`",
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
    labels: tuple[str, ...]
    num_lines_changed: int
    file_paths: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class Comment:
    comment_id: int
    user_name: str
    has_write_access: bool
    text: str


@dataclasses.dataclass(frozen=True)
class MilestoneChange:
    milestone_number: int | None


@dataclasses.dataclass(frozen=True)
class UpdatePlan:
    labels_to_add: tuple[str, ...] = ()
    labels_to_remove: tuple[str, ...] = ()
    assignees_to_add: tuple[str, ...] = ()
    assignees_to_remove: tuple[str, ...] = ()
    milestone_change: MilestoneChange | None = None
    reply: str | None = None
    react: bool = False


def parse_command(comment_text: str) -> tuple[str, str] | None:
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


def _usage_reply(command_name: str) -> UpdatePlan:
    return UpdatePlan(reply=f"Use {COMMAND_USAGES[command_name]}.")


def _mention_list(user_names: tuple[str, ...]) -> str:
    mentions = [f"@{_user_name}" for _user_name in user_names]
    if len(mentions) == 1:
        return mentions[0]
    else:
        return ", ".join(mentions[:-1]) + " and " + mentions[-1]


def _review_taken_reply(assignees: tuple[str, ...]) -> str:
    if len(assignees) == 1:
        verb = "has"
    else:
        verb = "have"
    return (
        f"{_mention_list(assignees)} {verb} accepted this review. "
        "You're welcome to leave a review or comment, or ask them to hand it over."
    )


def _author_or_write_only_reply(command_name: str) -> UpdatePlan:
    return UpdatePlan(reply=f"Only the PR author and people with write access can use `{command_name}`.")


def accept_review(pull_request: PullRequest, comment: Comment, argument: str, today: datetime.date) -> UpdatePlan:
    try:
        review_date = datetime.date.fromisoformat(argument)
    except ValueError:
        review_date = None
    if not comment.has_write_access:
        return UpdatePlan(reply="Only people with write access can accept a review.")
    elif comment.user_name == pull_request.author:
        return UpdatePlan(reply="You can't accept the review of your own PR.")
    elif review_date is None:
        return _usage_reply("/accept-review")
    elif review_date < today:
        return UpdatePlan(reply=f"The review date has to be today or later. Use {COMMAND_USAGES['/accept-review']}.")
    elif pull_request.assignees == (comment.user_name,):
        return UpdatePlan(react=True)
    elif len(pull_request.assignees) > 0:
        return UpdatePlan(reply=_review_taken_reply(pull_request.assignees))
    else:
        return UpdatePlan(assignees_to_add=(comment.user_name,), react=True)


def release_review(pull_request: PullRequest, comment: Comment, argument: str) -> UpdatePlan:
    if argument != "":
        return _usage_reply("/release-review")
    elif comment.user_name in pull_request.assignees:
        return UpdatePlan(assignees_to_remove=(comment.user_name,), react=True)
    elif len(pull_request.assignees) > 0:
        return UpdatePlan(reply=f"{_mention_list(pull_request.assignees)} accepted this review, so only they can release it.")
    else:
        return UpdatePlan(reply="Nobody has accepted this review yet.")


def set_priority(pull_request: PullRequest, argument: str) -> UpdatePlan:
    wanted_label = labels.PRIORITY_PREFIX + argument.lower()
    if argument.lower() not in PRIORITY_LEVELS:
        return _usage_reply("/set-priority")
    labels_to_remove = tuple(
        _label
        for _label in pull_request.labels
        if (_label.startswith(labels.PRIORITY_PREFIX)) and (_label != wanted_label)
    )
    if wanted_label in pull_request.labels:
        labels_to_add = ()
    else:
        labels_to_add = (wanted_label,)
    return UpdatePlan(labels_to_add=labels_to_add, labels_to_remove=labels_to_remove, react=True)


def set_milestone(open_milestones: tuple[Milestone, ...], argument: str) -> UpdatePlan:
    matching_milestones = [
        _milestone for _milestone in open_milestones if _milestone.title.lower() == argument.lower()
    ]
    if argument == "":
        return _usage_reply("/set-milestone")
    elif argument.lower() == "none":
        return UpdatePlan(milestone_change=MilestoneChange(milestone_number=None), react=True)
    elif len(matching_milestones) > 0:
        milestone_change = MilestoneChange(milestone_number=matching_milestones[0].milestone_number)
        return UpdatePlan(milestone_change=milestone_change, react=True)
    elif len(open_milestones) == 0:
        return UpdatePlan(reply=f'No open milestone is called "{argument}", and there are no open milestones.')
    else:
        milestone_titles = ", ".join(f"`{_milestone.title}`" for _milestone in open_milestones)
        return UpdatePlan(reply=f'No open milestone is called "{argument}". The open milestones are {milestone_titles}.')


def recompute_labels(label_config: labels.LabelConfig, pull_request: PullRequest, argument: str) -> UpdatePlan:
    if argument != "":
        return _usage_reply("/recompute-labels")
    label_changes = labels.compute_label_changes(
        label_config=label_config,
        current_labels=pull_request.labels,
        file_paths=pull_request.file_paths,
        num_lines_changed=pull_request.num_lines_changed,
    )
    return UpdatePlan(
        labels_to_add=label_changes.labels_to_add,
        labels_to_remove=label_changes.labels_to_remove,
        react=True,
    )


def handle_comment(
    label_config: labels.LabelConfig,
    pull_request: PullRequest,
    comment: Comment,
    open_milestones: tuple[Milestone, ...],
    today: datetime.date,
) -> UpdatePlan | None:
    parsed_command = parse_command(comment.text)
    if parsed_command is None:
        return None
    command_name, argument = parsed_command
    commenter_is_author_or_writer = (comment.user_name == pull_request.author) or comment.has_write_access
    if command_name == "/accept-review":
        return accept_review(pull_request, comment, argument, today)
    elif command_name == "/release-review":
        return release_review(pull_request, comment, argument)
    elif not commenter_is_author_or_writer:
        return _author_or_write_only_reply(command_name)
    elif command_name == "/set-priority":
        return set_priority(pull_request, argument)
    elif command_name == "/set-milestone":
        return set_milestone(open_milestones, argument)
    else:
        return recompute_labels(label_config, pull_request, argument)
