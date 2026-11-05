import pathlib
import subprocess
import unittest

import labels

LABEL_CONFIG = labels.load_label_config(pathlib.Path(__file__).parents[1] / "labels.toml")


class TestScopeLabels(unittest.TestCase):

    def test_hydro_file(
        self,
    ):
        scope_labels = labels.compute_scope_labels(LABEL_CONFIG, ("src/hydro/HLLC.hpp", ))
        self.assertEqual(scope_labels, {"scope/hydro"})

    def test_mhd_file_inside_hydro_gets_both(
        self,
    ):
        scope_labels = labels.compute_scope_labels(LABEL_CONFIG, ("src/hydro/HLLD.hpp", ))
        self.assertEqual(scope_labels, {"scope/hydro", "scope/MHD"})

    def test_problem_directories(
        self,
    ):
        file_paths = (
            "src/problems/MHDBlast/test_mhd_blast.cpp",
            "src/problems/RadDust/test_rad_dust.cpp",
            "src/problems/ParticleSink/test_particle_sink.cpp",
        )
        scope_labels = labels.compute_scope_labels(LABEL_CONFIG, file_paths)
        self.assertEqual(scope_labels, {"scope/MHD", "scope/radiation", "scope/dust", "scope/particles"})

    def test_inputs_follow_their_problem(
        self,
    ):
        file_paths = ("inputs/MHDBlast.toml", "inputs/alfven_wave_linear_regression.toml")
        scope_labels = labels.compute_scope_labels(LABEL_CONFIG, file_paths)
        self.assertEqual(scope_labels, {"scope/MHD"})

    def test_unclaimed_problem_falls_back_to_tests(
        self,
    ):
        file_paths = ("src/problems/SN/testSN.cpp", "inputs/SN.toml", "extern/Toro/e1rpex.ini")
        scope_labels = labels.compute_scope_labels(LABEL_CONFIG, file_paths)
        self.assertEqual(scope_labels, {"scope/tests"})

    def test_claimed_problem_does_not_also_get_tests(
        self,
    ):
        scope_labels = labels.compute_scope_labels(LABEL_CONFIG, ("src/problems/RadTube/testRadTube.cpp", ))
        self.assertEqual(scope_labels, {"scope/radiation"})

    def test_build_files_and_libraries(
        self,
    ):
        file_paths = ("src/CMakeLists.txt", "src/problems/ProblemHelpers.cmake", "extern/amrex")
        scope_labels = labels.compute_scope_labels(LABEL_CONFIG, file_paths)
        self.assertEqual(scope_labels, {"scope/build"})

    def test_problem_registry_is_tests(
        self,
    ):
        scope_labels = labels.compute_scope_labels(LABEL_CONFIG, ("src/problems/CMakeLists.txt", ))
        self.assertEqual(scope_labels, {"scope/tests"})

    def test_scripts_are_tools(
        self,
    ):
        scope_labels = labels.compute_scope_labels(LABEL_CONFIG, ("scripts/python/prune_checkpoints.py", ))
        self.assertEqual(scope_labels, {"scope/tools"})

    def test_ci_and_documentation(
        self,
    ):
        file_paths = (".github/workflows/cmake.yml", "docs/index.md", "README.md")
        scope_labels = labels.compute_scope_labels(LABEL_CONFIG, file_paths)
        self.assertEqual(scope_labels, {"scope/CI", "scope/documentation"})

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
        unscoped_paths = [
            _file_path for _file_path in file_paths if len(
                labels.compute_scope_labels(
                    LABEL_CONFIG,
                    (_file_path, ),
                ),
            ) == 0
        ]
        self.assertEqual(unscoped_paths, [], "Add these paths to a scope in labels.toml")


class TestSizeLabel(unittest.TestCase):

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
                self.assertEqual(labels.compute_size_label(LABEL_CONFIG, num_lines_changed), expected_size)


class TestLabelChanges(unittest.TestCase):

    def test_new_pr_gets_scope_size_and_default_priority(
        self,
    ):
        label_changes = labels.compute_label_changes(LABEL_CONFIG, (), ("src/io/plotfile.cpp", ), 40)
        self.assertEqual(label_changes.labels_to_add, ("priority/medium", "scope/IO", "size/M"))
        self.assertEqual(label_changes.labels_to_remove, ())

    def test_stale_scope_and_size_are_replaced_and_others_kept(
        self,
    ):
        current_labels = ("scope/radiation", "size/XS", "priority/high", "code-audit")
        label_changes = labels.compute_label_changes(
            LABEL_CONFIG, current_labels, ("src/io/plotfile.cpp", ), 40
        )
        self.assertEqual(label_changes.labels_to_add, ("scope/IO", "size/M"))
        self.assertEqual(label_changes.labels_to_remove, ("scope/radiation", "size/XS"))

    def test_up_to_date_pr_needs_no_changes(
        self,
    ):
        current_labels = ("scope/IO", "size/M", "priority/low")
        label_changes = labels.compute_label_changes(
            LABEL_CONFIG, current_labels, ("src/io/plotfile.cpp", ), 40
        )
        self.assertEqual(label_changes.labels_to_add, ())
        self.assertEqual(label_changes.labels_to_remove, ())


if __name__ == "__main__":
    unittest.main()
