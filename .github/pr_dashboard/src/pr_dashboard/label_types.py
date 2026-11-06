import dataclasses

SCOPE_PREFIX = "scope/"
SIZE_PREFIX = "size/"
PRIORITY_PREFIX = "priority/"


@dataclasses.dataclass(frozen=True)
class Label:
    name: str
    color: str
    description: str


@dataclasses.dataclass(frozen=True)
class ScopeLabel(Label):
    paths: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class SizeLabel(Label):
    min_num_lines: int


@dataclasses.dataclass(frozen=True)
class PriorityLabel(Label):
    is_default: bool


@dataclasses.dataclass(frozen=True)
class NotMappedLabel(Label):
    pass


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


@dataclasses.dataclass(frozen=True)
class LabelChanges:
    label_names_to_add: tuple[str, ...]
    label_names_to_remove: tuple[str, ...]
