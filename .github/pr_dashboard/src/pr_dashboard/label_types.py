import dataclasses


@dataclasses.dataclass(frozen=True)
class Label:
    prefix: str
    value: str
    color: str
    description: str

    @property
    def label_name(
        self,
    ) -> str:
        return self.prefix + self.value


@dataclasses.dataclass(frozen=True)
class ScopeLabel(Label):
    path_patterns: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class NotMappedLabel(Label):
    pass


@dataclasses.dataclass(frozen=True)
class SizeLabel(Label):
    min_num_lines: int


@dataclasses.dataclass(frozen=True)
class PriorityLabel(Label):
    is_default: bool


@dataclasses.dataclass(frozen=True)
class LabelCategory:
    prefix: str

    def check_owns(
        self,
        label_name: str,
    ) -> bool:
        return label_name.startswith(self.prefix)


@dataclasses.dataclass(frozen=True)
class ScopeLabels(LabelCategory):
    labels: tuple[ScopeLabel, ...]
    not_mapped_label: NotMappedLabel


@dataclasses.dataclass(frozen=True)
class SizeLabels(LabelCategory):
    labels: tuple[SizeLabel, ...]


@dataclasses.dataclass(frozen=True)
class PriorityLabels(LabelCategory):
    labels: tuple[PriorityLabel, ...]
    default_label: PriorityLabel

    def get_label(
        self,
        value: str,
    ) -> PriorityLabel | None:
        matching_labels = [_label for _label in self.labels if _label.value.lower() == value.lower()]
        if len(matching_labels) == 0:
            return None
        else:
            return matching_labels[0]


@dataclasses.dataclass(frozen=True)
class ConfiguredLabels:
    scope_labels: ScopeLabels
    size_labels: SizeLabels
    priority_labels: PriorityLabels

    def all_labels(
        self,
    ) -> tuple[Label, ...]:
        return (
            self.scope_labels.labels + (self.scope_labels.not_mapped_label, ) + self.size_labels.labels +
            self.priority_labels.labels
        )


@dataclasses.dataclass(frozen=True)
class LabelChanges:
    label_names_to_add: tuple[str, ...]
    label_names_to_remove: tuple[str, ...]
