import dataclasses
import enum


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
    edited_file_paths: tuple[str, ...]


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
