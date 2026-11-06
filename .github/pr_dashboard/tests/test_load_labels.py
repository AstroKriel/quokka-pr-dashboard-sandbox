import pathlib
import tempfile
import unittest

from pr_dashboard import label_types
from pr_dashboard import load_labels

CONFIGURED_LABELS = load_labels.load_configured_labels(pathlib.Path(__file__).parents[1] / "labels.toml")
SCOPE_LABEL_TEXT = (
    '[[scope_label]]\nname = "scope/hydro"\ncolor = "4ADD08"\ndescription = "Hydro"\npaths = ["src/hydro/*"]\n'
)


def make_priority_label_text(
    *,
    label_name: str,
    is_default: bool = False,
) -> str:
    if is_default:
        default_line = "default = true\n"
    else:
        default_line = ""
    return f'[[priority_label]]\nname = "{label_name}"\ncolor = "FBCA04"\ndescription = "Priority"\n{default_line}'


LOW_PRIORITY_LABEL_TEXT = make_priority_label_text(label_name="priority/low")
MEDIUM_PRIORITY_LABEL_TEXT = make_priority_label_text(label_name="priority/medium")
DEFAULT_PRIORITY_LABEL_TEXT = make_priority_label_text(
    label_name="priority/medium",
    is_default=True,
)
HIGH_PRIORITY_LABEL_TEXT = make_priority_label_text(label_name="priority/high")
VALID_PRIORITY_LABELS_TEXT = LOW_PRIORITY_LABEL_TEXT + DEFAULT_PRIORITY_LABEL_TEXT + HIGH_PRIORITY_LABEL_TEXT


def make_config_text(
    *,
    scope_label_text: str = SCOPE_LABEL_TEXT,
    priority_label_text: str = VALID_PRIORITY_LABELS_TEXT,
) -> str:
    return (
        '[not_mapped_label]\nname = "scope/not_mapped"\ncolor = "B60205"\ndescription = "Not mapped"\n'
        f"{scope_label_text}"
        '[[size_label]]\nname = "size/XS"\ncolor = "00FF00"\ndescription = "Small"\nmin_num_lines = 0\n'
        f"{priority_label_text}"
    )


def load_config_text(
    config_text: str,
) -> label_types.ConfiguredLabels:
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = pathlib.Path(temp_dir) / "labels.toml"
        config_path.write_text(config_text)
        return load_labels.load_configured_labels(config_path)


class TestLoadLabels_Kinds(unittest.TestCase):

    def test_kinds_are_split(
        self,
    ):
        self.assertEqual(len(CONFIGURED_LABELS.scope_labels), 15)
        self.assertEqual(len(CONFIGURED_LABELS.size_labels), 5)
        self.assertEqual(len(CONFIGURED_LABELS.priority_labels), 3)
        self.assertEqual(len(CONFIGURED_LABELS.all_labels()), 24)
        for priority_label in CONFIGURED_LABELS.priority_labels:
            self.assertIsInstance(priority_label, label_types.PriorityLabel)
        self.assertIsInstance(CONFIGURED_LABELS.not_mapped_label, label_types.NotMappedLabel)

    def test_default_priority_is_a_priority_label(
        self,
    ):
        self.assertIsInstance(CONFIGURED_LABELS.default_priority_label, label_types.PriorityLabel)
        self.assertEqual(CONFIGURED_LABELS.default_priority_label.name, "priority/medium")
        self.assertTrue(CONFIGURED_LABELS.default_priority_label.is_default)

    def test_each_priority_has_its_label(
        self,
    ):
        for priority in label_types.Priority:
            with self.subTest(priority=priority):
                priority_label = CONFIGURED_LABELS.get_priority_label(priority)
                self.assertEqual(priority_label.name, f"priority/{priority}")

    def test_minimal_config_loads(
        self,
    ):
        configured_labels = load_config_text(make_config_text())
        self.assertEqual(configured_labels.default_priority_label.name, "priority/medium")
        self.assertFalse(configured_labels.priority_labels[0].is_default)


class TestLoadLabels_Errors(unittest.TestCase):

    def test_scope_label_without_paths_fails(
        self,
    ):
        config_text = make_config_text(
            scope_label_text=
            '[[scope_label]]\nname = "scope/hydro"\ncolor = "4ADD08"\ndescription = "Hydro"\n',
        )
        with self.assertRaises(KeyError):
            load_config_text(config_text)

    def test_label_with_the_wrong_prefix_fails(
        self,
    ):
        config_text = make_config_text(
            scope_label_text=SCOPE_LABEL_TEXT.replace(
                'name = "scope/hydro"',
                'name = "size/hydro"',
            ),
        )
        with self.assertRaisesRegex(ValueError, "must start with `scope/`"):
            load_config_text(config_text)

    def test_priority_label_that_is_not_a_level_fails(
        self,
    ):
        urgent_label_text = make_priority_label_text(label_name="priority/urgent")
        config_text = make_config_text(priority_label_text=VALID_PRIORITY_LABELS_TEXT + urgent_label_text)
        with self.assertRaisesRegex(ValueError, "`priority/urgent` must end in one of"):
            load_config_text(config_text)

    def test_missing_priority_level_fails(
        self,
    ):
        config_text = make_config_text(
            priority_label_text=LOW_PRIORITY_LABEL_TEXT + DEFAULT_PRIORITY_LABEL_TEXT
        )
        with self.assertRaisesRegex(ValueError, "must cover each of"):
            load_config_text(config_text)

    def test_no_default_priority_fails(
        self,
    ):
        config_text = make_config_text(
            priority_label_text=LOW_PRIORITY_LABEL_TEXT + MEDIUM_PRIORITY_LABEL_TEXT +
            HIGH_PRIORITY_LABEL_TEXT,
        )
        with self.assertRaisesRegex(ValueError, "got 0"):
            load_config_text(config_text)

    def test_two_default_priorities_fail(
        self,
    ):
        default_high_label_text = make_priority_label_text(
            label_name="priority/high",
            is_default=True,
        )
        config_text = make_config_text(
            priority_label_text=LOW_PRIORITY_LABEL_TEXT + DEFAULT_PRIORITY_LABEL_TEXT +
            default_high_label_text,
        )
        with self.assertRaisesRegex(ValueError, "got 2"):
            load_config_text(config_text)


if __name__ == "__main__":
    unittest.main()
