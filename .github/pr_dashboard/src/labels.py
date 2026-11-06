import dataclasses
import fnmatch
import pathlib
import tomllib

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
    pass


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


def load_configured_labels(
    config_path: pathlib.Path,
) -> ConfiguredLabels:
    with open(config_path, "rb") as config_file:
        config_data = tomllib.load(config_file)
    scope_labels = tuple(
        ScopeLabel(
            name=_label_data["name"],
            color=_label_data["color"],
            description=_label_data["description"],
            paths=tuple(_label_data["paths"]),
        ) for _label_data in config_data["scope_label"]
    )
    size_labels = tuple(
        SizeLabel(
            name=_label_data["name"],
            color=_label_data["color"],
            description=_label_data["description"],
            min_num_lines=_label_data["min_num_lines"],
        ) for _label_data in config_data["size_label"]
    )
    priority_labels = tuple(
        PriorityLabel(
            name=_label_data["name"],
            color=_label_data["color"],
            description=_label_data["description"],
        ) for _label_data in config_data["priority_label"]
    )
    not_mapped_label = NotMappedLabel(
        name=config_data["not_mapped_label"]["name"],
        color=config_data["not_mapped_label"]["color"],
        description=config_data["not_mapped_label"]["description"],
    )
    default_priority_label_name = config_data["default_priority"]
    matching_priority_labels = [
        _priority_label for _priority_label in priority_labels
        if _priority_label.name == default_priority_label_name
    ]
    if len(matching_priority_labels) == 0:
        raise ValueError(
            f'default_priority "{default_priority_label_name}" is not a priority label in labels.toml'
        )
    return ConfiguredLabels(
        scope_labels=scope_labels,
        size_labels=size_labels,
        priority_labels=priority_labels,
        not_mapped_label=not_mapped_label,
        default_priority_label=matching_priority_labels[0],
    )


def _path_matches_any(
    file_path: str,
    patterns: tuple[str, ...],
) -> bool:
    return any(fnmatch.fnmatchcase(file_path, _pattern) for _pattern in patterns)


def compute_scope_label_names(
    configured_labels: ConfiguredLabels,
    file_paths: tuple[str, ...],
) -> set[str]:
    scope_label_names = set()
    for file_path in file_paths:
        matched_label_names = {
            _scope_label.name
            for _scope_label in configured_labels.scope_labels
            if _path_matches_any(file_path, _scope_label.paths)
        }
        if len(matched_label_names) == 0:
            scope_label_names.add(configured_labels.not_mapped_label.name)
        else:
            scope_label_names.update(matched_label_names)
    return scope_label_names


def compute_size_label_name(
    configured_labels: ConfiguredLabels,
    num_lines_changed: int,
) -> str:
    sorted_size_labels = sorted(
        configured_labels.size_labels,
        key=lambda _size_label: _size_label.min_num_lines,
    )
    size_label_name = sorted_size_labels[0].name
    for size_label in sorted_size_labels:
        if num_lines_changed >= size_label.min_num_lines:
            size_label_name = size_label.name
    return size_label_name


def compute_label_changes(
    configured_labels: ConfiguredLabels,
    current_label_names: tuple[str, ...],
    file_paths: tuple[str, ...],
    num_lines_changed: int,
) -> LabelChanges:
    wanted_label_names = compute_scope_label_names(configured_labels, file_paths)
    size_label_name = compute_size_label_name(configured_labels, num_lines_changed)
    wanted_label_names.add(size_label_name)
    priority_is_set = any(_label_name.startswith(PRIORITY_PREFIX) for _label_name in current_label_names)
    if not priority_is_set:
        wanted_label_names.add(configured_labels.default_priority_label.name)
    label_names_to_add = sorted(wanted_label_names - set(current_label_names))
    label_names_to_remove = sorted(
        _label_name for _label_name in current_label_names
        if (_label_name.startswith(SCOPE_PREFIX) or _label_name.startswith(SIZE_PREFIX)) and
        (_label_name not in wanted_label_names)
    )
    return LabelChanges(
        label_names_to_add=tuple(label_names_to_add),
        label_names_to_remove=tuple(label_names_to_remove),
    )
