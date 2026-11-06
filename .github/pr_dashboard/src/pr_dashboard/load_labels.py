import pathlib
import tomllib

from pr_dashboard import label_types


def _load_scope_labels(
    scope_data: dict,
) -> label_types.ScopeLabels:
    prefix = scope_data["prefix"]
    labels = tuple(
        label_types.ScopeLabel(
            prefix=prefix,
            value=_label_data["value"],
            color=_label_data["color"],
            description=_label_data["description"],
            path_patterns=tuple(_label_data["path_patterns"]),
        ) for _label_data in scope_data["label"]
    )
    not_mapped_label = label_types.NotMappedLabel(
        prefix=prefix,
        value=scope_data["not_mapped_label"]["value"],
        color=scope_data["not_mapped_label"]["color"],
        description=scope_data["not_mapped_label"]["description"],
    )
    return label_types.ScopeLabels(
        prefix=prefix,
        labels=labels,
        not_mapped_label=not_mapped_label,
    )


def _load_size_labels(
    size_data: dict,
) -> label_types.SizeLabels:
    prefix = size_data["prefix"]
    labels = tuple(
        label_types.SizeLabel(
            prefix=prefix,
            value=_label_data["value"],
            color=_label_data["color"],
            description=_label_data["description"],
            min_num_lines=_label_data["min_num_lines"],
        ) for _label_data in size_data["label"]
    )
    return label_types.SizeLabels(
        prefix=prefix,
        labels=labels,
    )


def _get_default_priority_label(
    priority_labels: tuple[label_types.PriorityLabel, ...],
) -> label_types.PriorityLabel:
    default_priority_labels = [
        _priority_label for _priority_label in priority_labels if _priority_label.is_default
    ]
    if len(default_priority_labels) != 1:
        raise ValueError(
            f"exactly one priority label must have `default = true`; got {len(default_priority_labels)}.",
        )
    return default_priority_labels[0]


def _load_priority_labels(
    priority_data: dict,
) -> label_types.PriorityLabels:
    prefix = priority_data["prefix"]
    labels = tuple(
        label_types.PriorityLabel(
            prefix=prefix,
            value=_label_data["value"],
            color=_label_data["color"],
            description=_label_data["description"],
            is_default=_label_data.get("default", False),
        ) for _label_data in priority_data["label"]
    )
    default_label = _get_default_priority_label(labels)
    return label_types.PriorityLabels(
        prefix=prefix,
        labels=labels,
        default_label=default_label,
    )


def load_configured_labels(
    config_path: pathlib.Path,
) -> label_types.ConfiguredLabels:
    with open(config_path, "rb") as config_file:
        config_data = tomllib.load(config_file)
    scope_labels = _load_scope_labels(config_data["scope"])
    size_labels = _load_size_labels(config_data["size"])
    priority_labels = _load_priority_labels(config_data["priority"])
    return label_types.ConfiguredLabels(
        scope_labels=scope_labels,
        size_labels=size_labels,
        priority_labels=priority_labels,
    )
