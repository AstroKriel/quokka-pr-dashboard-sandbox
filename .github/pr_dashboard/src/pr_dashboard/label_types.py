import dataclasses
import enum
import typing


class Priority(enum.StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclasses.dataclass(frozen=True)
class Label:
    PREFIX: typing.ClassVar[str]
    name: str
    color: str
    description: str

    def __post_init__(
        self,
    ) -> None:
        if not self.check_name_has_prefix(self.name):
            raise ValueError(f"label `name` must start with `{self.PREFIX}`; got `{self.name}`.")

    @classmethod
    def check_name_has_prefix(
        cls,
        label_name: str,
    ) -> bool:
        return label_name.startswith(cls.PREFIX)


@dataclasses.dataclass(frozen=True)
class ScopeLabel(Label):
    PREFIX: typing.ClassVar[str] = "scope/"
    paths: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class NotMappedLabel(Label):
    PREFIX: typing.ClassVar[str] = "scope/"


@dataclasses.dataclass(frozen=True)
class SizeLabel(Label):
    PREFIX: typing.ClassVar[str] = "size/"
    min_num_lines: int


@dataclasses.dataclass(frozen=True)
class PriorityLabel(Label):
    PREFIX: typing.ClassVar[str] = "priority/"
    is_default: bool

    @property
    def priority(
        self,
    ) -> Priority:
        return Priority(self.name.removeprefix(self.PREFIX))


@dataclasses.dataclass(frozen=True)
class ConfiguredLabels:
    scope_labels: tuple[ScopeLabel, ...]
    size_labels: tuple[SizeLabel, ...]
    priority_labels: tuple[PriorityLabel, ...]
    not_mapped_label: NotMappedLabel
    default_priority_label: PriorityLabel

    def all_labels(
        self,
    ) -> tuple[Label, ...]:
        return self.scope_labels + (self.not_mapped_label, ) + self.size_labels + self.priority_labels

    def get_priority_label(
        self,
        priority: Priority,
    ) -> PriorityLabel:
        matching_priority_labels = [
            _priority_label for _priority_label in self.priority_labels
            if _priority_label.priority == priority
        ]
        assert len(matching_priority_labels) == 1
        return matching_priority_labels[0]


@dataclasses.dataclass(frozen=True)
class LabelChanges:
    label_names_to_add: tuple[str, ...]
    label_names_to_remove: tuple[str, ...]
