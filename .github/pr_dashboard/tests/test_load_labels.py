import pathlib
import tempfile
import unittest

from pr_dashboard import label_types
from pr_dashboard import load_labels

CONFIGURED_LABELS = load_labels.load_configured_labels(pathlib.Path(__file__).parents[1] / "labels.toml")
SCOPE_LABEL_TEXT = (
    '[[scope_label]]\nname = "scope/hydro"\ncolor = "4ADD08"\ndescription = "Hydro"\npaths = ["src/hydro/*"]\n'
)
LOW_PRIORITY_LABEL_TEXT = '[[priority_label]]\nname = "priority/low"\ncolor = "0E8A16"\ndescription = "Low"\n'
DEFAULT_PRIORITY_LABEL_TEXT = (
    '[[priority_label]]\nname = "priority/medium"\ncolor = "FBCA04"\ndescription = "Normal"\ndefault = true\n'
)


def make_config_text(
    *,
    scope_label_text: str,
    priority_label_text: str,
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

    def test_minimal_config_loads(
        self,
    ):
        config_text = make_config_text(
            scope_label_text=SCOPE_LABEL_TEXT,
            priority_label_text=LOW_PRIORITY_LABEL_TEXT + DEFAULT_PRIORITY_LABEL_TEXT,
        )
        configured_labels = load_config_text(config_text)
        self.assertEqual(configured_labels.default_priority_label.name, "priority/medium")
        self.assertFalse(configured_labels.priority_labels[0].is_default)


class TestLoadLabels_Errors(unittest.TestCase):

    def test_scope_label_without_paths_fails(
        self,
    ):
        config_text = make_config_text(
            scope_label_text=
            '[[scope_label]]\nname = "scope/hydro"\ncolor = "4ADD08"\ndescription = "Hydro"\n',
            priority_label_text=DEFAULT_PRIORITY_LABEL_TEXT,
        )
        with self.assertRaises(KeyError):
            load_config_text(config_text)

    def test_no_default_priority_fails(
        self,
    ):
        config_text = make_config_text(
            scope_label_text=SCOPE_LABEL_TEXT,
            priority_label_text=LOW_PRIORITY_LABEL_TEXT,
        )
        with self.assertRaisesRegex(ValueError, "got 0"):
            load_config_text(config_text)

    def test_two_default_priorities_fail(
        self,
    ):
        second_default_text = DEFAULT_PRIORITY_LABEL_TEXT.replace("priority/medium", "priority/high")
        config_text = make_config_text(
            scope_label_text=SCOPE_LABEL_TEXT,
            priority_label_text=DEFAULT_PRIORITY_LABEL_TEXT + second_default_text,
        )
        with self.assertRaisesRegex(ValueError, "got 2"):
            load_config_text(config_text)


if __name__ == "__main__":
    unittest.main()
