import pathlib
import tomllib

from pr_dashboard import label_types


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


def load_configured_labels(
    config_path: pathlib.Path,
) -> label_types.ConfiguredLabels:
    with open(config_path, "rb") as config_file:
        config_data = tomllib.load(config_file)
    scope_labels = tuple(
        label_types.ScopeLabel(
            name=_label_data["name"],
            color=_label_data["color"],
            description=_label_data["description"],
            paths=tuple(_label_data["paths"]),
        ) for _label_data in config_data["scope_label"]
    )
    size_labels = tuple(
        label_types.SizeLabel(
            name=_label_data["name"],
            color=_label_data["color"],
            description=_label_data["description"],
            min_num_lines=_label_data["min_num_lines"],
        ) for _label_data in config_data["size_label"]
    )
    priority_labels = tuple(
        label_types.PriorityLabel(
            name=_label_data["name"],
            color=_label_data["color"],
            description=_label_data["description"],
            is_default=_label_data.get("default", False),
        ) for _label_data in config_data["priority_label"]
    )
    not_mapped_label = label_types.NotMappedLabel(
        name=config_data["not_mapped_label"]["name"],
        color=config_data["not_mapped_label"]["color"],
        description=config_data["not_mapped_label"]["description"],
    )
    default_priority_label = _get_default_priority_label(priority_labels)
    return label_types.ConfiguredLabels(
        scope_labels=scope_labels,
        size_labels=size_labels,
        priority_labels=priority_labels,
        not_mapped_label=not_mapped_label,
        default_priority_label=default_priority_label,
    )
