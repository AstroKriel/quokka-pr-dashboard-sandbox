import fnmatch

from pr_dashboard import label_types


def _path_matches_any(
    *,
    file_path: str,
    patterns: tuple[str, ...],
) -> bool:
    return any(fnmatch.fnmatchcase(file_path, _pattern) for _pattern in patterns)


def _compute_scope_label_names(
    *,
    configured_labels: label_types.ConfiguredLabels,
    edited_file_paths: tuple[str, ...],
) -> set[str]:
    scope_label_names = set()
    for file_path in edited_file_paths:
        matched_label_names = {
            _scope_label.label_name
            for _scope_label in configured_labels.scope_labels.labels
            if _path_matches_any(
                file_path=file_path,
                patterns=_scope_label.path_patterns,
            )
        }
        if len(matched_label_names) == 0:
            scope_label_names.add(configured_labels.scope_labels.not_mapped_label.label_name)
        else:
            scope_label_names.update(matched_label_names)
    return scope_label_names


def _compute_size_label_name(
    *,
    configured_labels: label_types.ConfiguredLabels,
    num_lines_changed: int,
) -> str:
    sorted_size_labels = sorted(
        configured_labels.size_labels.labels,
        key=lambda _size_label: _size_label.min_num_lines,
    )
    size_label_name = sorted_size_labels[0].label_name
    for size_label in sorted_size_labels:
        if num_lines_changed >= size_label.min_num_lines:
            size_label_name = size_label.label_name
    return size_label_name


def compute_label_changes(
    *,
    configured_labels: label_types.ConfiguredLabels,
    current_label_names: tuple[str, ...],
    edited_file_paths: tuple[str, ...],
    num_lines_changed: int,
) -> label_types.LabelChanges:
    wanted_label_names = _compute_scope_label_names(
        configured_labels=configured_labels,
        edited_file_paths=edited_file_paths,
    )
    size_label_name = _compute_size_label_name(
        configured_labels=configured_labels,
        num_lines_changed=num_lines_changed,
    )
    wanted_label_names.add(size_label_name)
    priority_is_set = any(
        configured_labels.priority_labels.check_owns(_label_name) for _label_name in current_label_names
    )
    if not priority_is_set:
        wanted_label_names.add(configured_labels.priority_labels.default_label.label_name)
    label_names_to_add = sorted(wanted_label_names - set(current_label_names))
    label_names_to_remove = sorted(
        _label_name for _label_name in current_label_names if (
            configured_labels.scope_labels.check_owns(_label_name)
            or configured_labels.size_labels.check_owns(_label_name)
        ) and (_label_name not in wanted_label_names)
    )
    return label_types.LabelChanges(
        label_names_to_add=tuple(label_names_to_add),
        label_names_to_remove=tuple(label_names_to_remove),
    )
