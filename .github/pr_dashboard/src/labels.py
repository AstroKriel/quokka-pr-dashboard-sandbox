import dataclasses
import fnmatch
import pathlib
import tomllib

SCOPE_PREFIX = "scope/"
SIZE_PREFIX = "size/"
PRIORITY_PREFIX = "priority/"


@dataclasses.dataclass(frozen=True)
class LabelDefinition:
    name: str
    color: str
    description: str


@dataclasses.dataclass(frozen=True)
class ScopeLabel(LabelDefinition):
    paths: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class SizeLabel(LabelDefinition):
    min_num_lines: int


@dataclasses.dataclass(frozen=True)
class LabelConfig:
    scope_labels: tuple[ScopeLabel, ...]
    size_labels: tuple[SizeLabel, ...]
    priority_labels: tuple[LabelDefinition, ...]
    default_priority: str
    scope_fallback_label: str
    scope_fallback_paths: tuple[str, ...]

    def all_label_definitions(
        self,
    ) -> tuple[LabelDefinition, ...]:
        return self.scope_labels + self.size_labels + self.priority_labels


@dataclasses.dataclass(frozen=True)
class LabelChanges:
    labels_to_add: tuple[str, ...]
    labels_to_remove: tuple[str, ...]


def load_label_config(
    config_path: pathlib.Path,
) -> LabelConfig:
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
        LabelDefinition(
            name=_label_data["name"],
            color=_label_data["color"],
            description=_label_data["description"],
        ) for _label_data in config_data["priority_label"]
    )
    return LabelConfig(
        scope_labels=scope_labels,
        size_labels=size_labels,
        priority_labels=priority_labels,
        default_priority=config_data["default_priority"],
        scope_fallback_label=config_data["scope_fallback"]["label"],
        scope_fallback_paths=tuple(config_data["scope_fallback"]["paths"]),
    )


def _path_matches_any(
    file_path: str,
    patterns: tuple[str, ...],
) -> bool:
    return any(fnmatch.fnmatchcase(file_path, _pattern) for _pattern in patterns)


def compute_scope_labels(
    label_config: LabelConfig,
    file_paths: tuple[str, ...],
) -> set[str]:
    scope_labels = set()
    for file_path in file_paths:
        matched_labels = {
            _scope_label.name
            for _scope_label in label_config.scope_labels
            if _path_matches_any(file_path, _scope_label.paths)
        }
        if (len(matched_labels) == 0) and _path_matches_any(file_path, label_config.scope_fallback_paths):
            scope_labels.add(label_config.scope_fallback_label)
        else:
            scope_labels.update(matched_labels)
    return scope_labels


def compute_size_label(
    label_config: LabelConfig,
    num_lines_changed: int,
) -> str:
    sorted_size_labels = sorted(
        label_config.size_labels,
        key=lambda _size_label: _size_label.min_num_lines,
    )
    size_label_name = sorted_size_labels[0].name
    for size_label in sorted_size_labels:
        if num_lines_changed >= size_label.min_num_lines:
            size_label_name = size_label.name
    return size_label_name


def compute_label_changes(
    label_config: LabelConfig,
    current_labels: tuple[str, ...],
    file_paths: tuple[str, ...],
    num_lines_changed: int,
) -> LabelChanges:
    wanted_labels = compute_scope_labels(label_config, file_paths)
    wanted_labels.add(
        compute_size_label(
            label_config,
            num_lines_changed,
        ),
    )
    priority_is_set = any(_label.startswith(PRIORITY_PREFIX) for _label in current_labels)
    if not priority_is_set:
        wanted_labels.add(label_config.default_priority)
    labels_to_add = sorted(wanted_labels - set(current_labels))
    labels_to_remove = sorted(
        _label for _label in current_labels if
        (_label.startswith(SCOPE_PREFIX) or _label.startswith(SIZE_PREFIX)) and (_label not in wanted_labels)
    )
    return LabelChanges(
        labels_to_add=tuple(labels_to_add),
        labels_to_remove=tuple(labels_to_remove),
    )
