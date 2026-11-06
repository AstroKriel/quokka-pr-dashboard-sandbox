import pathlib
import subprocess
import unittest

from pr_dashboard import compute_labels
from pr_dashboard import load_labels

CONFIGURED_LABELS = load_labels.load_configured_labels(pathlib.Path(__file__).parents[1] / "labels.toml")


class TestComputeLabels_Scope(unittest.TestCase):

    def test_hydro_file(
        self,
    ):
        scope_label_names = compute_labels._compute_scope_label_names(
            CONFIGURED_LABELS,
            ("src/hydro/HLLC.hpp", ),
        )
        self.assertEqual(scope_label_names, {"scope/hydro"})

    def test_mhd_file_inside_hydro_gets_both(
        self,
    ):
        scope_label_names = compute_labels._compute_scope_label_names(
            CONFIGURED_LABELS,
            ("src/hydro/HLLD.hpp", ),
        )
        self.assertEqual(scope_label_names, {"scope/hydro", "scope/MHD"})

    def test_problem_directories(
        self,
    ):
        file_paths = (
            "src/problems/MHDBlast/test_mhd_blast.cpp",
            "src/problems/RadDust/test_rad_dust.cpp",
            "src/problems/ParticleSink/test_particle_sink.cpp",
        )
        scope_label_names = compute_labels._compute_scope_label_names(CONFIGURED_LABELS, file_paths)
        expected_label_names = {
            "scope/MHD",
            "scope/radiation",
            "scope/dust",
            "scope/particles",
            "scope/tests",
        }
        self.assertEqual(scope_label_names, expected_label_names)

    def test_inputs_follow_their_problem(
        self,
    ):
        file_paths = ("inputs/MHDBlast.toml", "inputs/alfven_wave_linear_regression.toml")
        scope_label_names = compute_labels._compute_scope_label_names(CONFIGURED_LABELS, file_paths)
        self.assertEqual(scope_label_names, {"scope/MHD", "scope/tests"})

    def test_problem_with_no_physics_area_is_tests(
        self,
    ):
        file_paths = ("src/problems/SN/testSN.cpp", "inputs/SN.toml", "extern/Toro/e1rpex.ini")
        scope_label_names = compute_labels._compute_scope_label_names(CONFIGURED_LABELS, file_paths)
        self.assertEqual(scope_label_names, {"scope/tests"})

    def test_unknown_file_is_not_mapped(
        self,
    ):
        file_paths = ("src/newmodule/thing.hpp", "src/hydro/HLLC.hpp")
        scope_label_names = compute_labels._compute_scope_label_names(CONFIGURED_LABELS, file_paths)
        self.assertEqual(scope_label_names, {"scope/not_mapped", "scope/hydro"})

    def test_build_files_and_libraries(
        self,
    ):
        file_paths = ("src/CMakeLists.txt", "src/problems/ProblemHelpers.cmake", "extern/amrex")
        scope_label_names = compute_labels._compute_scope_label_names(CONFIGURED_LABELS, file_paths)
        self.assertEqual(scope_label_names, {"scope/build", "scope/tests"})

    def test_problem_registry_is_tests(
        self,
    ):
        scope_label_names = compute_labels._compute_scope_label_names(
            CONFIGURED_LABELS,
            ("src/problems/CMakeLists.txt", ),
        )
        self.assertEqual(scope_label_names, {"scope/tests"})

    def test_scripts_are_tools(
        self,
    ):
        scope_label_names = compute_labels._compute_scope_label_names(
            CONFIGURED_LABELS,
            ("scripts/python/prune_checkpoints.py", ),
        )
        self.assertEqual(scope_label_names, {"scope/tools"})

    def test_ci_and_documentation(
        self,
    ):
        file_paths = (".github/workflows/cmake.yml", "docs/index.md", "README.md")
        scope_label_names = compute_labels._compute_scope_label_names(CONFIGURED_LABELS, file_paths)
        self.assertEqual(scope_label_names, {"scope/CI", "scope/documentation"})

    def test_every_repository_file_has_a_scope(
        self,
    ):
        repo_root = pathlib.Path(__file__).parents[3]
        completed_process = subprocess.run(
            ["git", "ls-files"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        file_paths = completed_process.stdout.splitlines()
        not_mapped_label_name = CONFIGURED_LABELS.not_mapped_label.name
        not_mapped_paths = [
            _file_path for _file_path in file_paths if not_mapped_label_name in
            compute_labels._compute_scope_label_names(CONFIGURED_LABELS, (_file_path, ))
        ]
        self.assertEqual(not_mapped_paths, [], "Add these paths to a scope in labels.toml")


class TestComputeLabels_Size(unittest.TestCase):

    def test_boundaries(
        self,
    ):
        expected_sizes = {
            0: "size/XS",
            9: "size/XS",
            10: "size/S",
            29: "size/S",
            30: "size/M",
            99: "size/M",
            100: "size/L",
            499: "size/L",
            500: "size/XL",
            50000: "size/XL",
        }
        for num_lines_changed, expected_size in expected_sizes.items():
            with self.subTest(num_lines_changed=num_lines_changed):
                self.assertEqual(
                    compute_labels._compute_size_label_name(CONFIGURED_LABELS, num_lines_changed),
                    expected_size,
                )


class TestComputeLabels_Changes(unittest.TestCase):

    def test_new_pr_gets_scope_size_and_default_priority(
        self,
    ):
        label_changes = compute_labels.compute_label_changes(
            CONFIGURED_LABELS,
            (),
            ("src/io/plotfile.cpp", ),
            40,
        )
        self.assertEqual(label_changes.label_names_to_add, ("priority/medium", "scope/IO", "size/M"))
        self.assertEqual(label_changes.label_names_to_remove, ())

    def test_stale_scope_and_size_are_replaced_and_others_kept(
        self,
    ):
        current_label_names = ("scope/radiation", "size/XS", "priority/high", "code-audit")
        label_changes = compute_labels.compute_label_changes(
            CONFIGURED_LABELS,
            current_label_names,
            ("src/io/plotfile.cpp", ),
            40,
        )
        self.assertEqual(label_changes.label_names_to_add, ("scope/IO", "size/M"))
        self.assertEqual(label_changes.label_names_to_remove, ("scope/radiation", "size/XS"))

    def test_up_to_date_pr_needs_no_changes(
        self,
    ):
        current_label_names = ("scope/IO", "size/M", "priority/low")
        label_changes = compute_labels.compute_label_changes(
            CONFIGURED_LABELS,
            current_label_names,
            ("src/io/plotfile.cpp", ),
            40,
        )
        self.assertEqual(label_changes.label_names_to_add, ())
        self.assertEqual(label_changes.label_names_to_remove, ())


if __name__ == "__main__":
    unittest.main()
