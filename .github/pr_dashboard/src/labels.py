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
    paths: tuple[str, ...]
    min_num_lines: int | None


@dataclasses.dataclass(frozen=True)
class LabelConfig:
    label_definitions: tuple[LabelDefinition, ...]
    default_priority: str
    scope_fallback_label: str
    scope_fallback_paths: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class LabelChanges:
    labels_to_add: tuple[str, ...]
    labels_to_remove: tuple[str, ...]


def load_label_config(
    config_path: pathlib.Path,
) -> LabelConfig:
    with open(config_path, "rb") as config_file:
        config_data = tomllib.load(config_file)
    label_definitions = tuple(
        LabelDefinition(
            name=_label_data["name"],
            color=_label_data["color"],
            description=_label_data["description"],
            paths=tuple(
                _label_data.get(
                    "paths",
                    [],
                ),
            ),
            min_num_lines=_label_data.get("min_num_lines"),
        ) for _label_data in config_data["label"]
    )
    return LabelConfig(
        label_definitions=label_definitions,
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
            _label_definition.name
            for _label_definition in label_config.label_definitions
            if _label_definition.name.startswith(SCOPE_PREFIX)
            and _path_matches_any(file_path, _label_definition.paths)
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
    size_definitions = sorted(
        (
            _label_definition for _label_definition in label_config.label_definitions
            if _label_definition.name.startswith(SIZE_PREFIX)
        ),
        key=lambda _label_definition: _label_definition.min_num_lines,
    )
    size_label = size_definitions[0].name
    for size_definition in size_definitions:
        if num_lines_changed >= size_definition.min_num_lines:
            size_label = size_definition.name
    return size_label


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
