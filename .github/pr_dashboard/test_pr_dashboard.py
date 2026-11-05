import datetime
import pathlib
import unittest

import commands
import labels

LABEL_CONFIG = labels.load_label_config(pathlib.Path(__file__).parent / "labels.toml")
TODAY = datetime.date(2026, 11, 5)
OPEN_MILESTONES = (
    commands.Milestone(number=6, title="Rewrite RHD module"),
    commands.Milestone(number=8, title="photochem"),
)


def make_pull_request(
    assignees: tuple[str, ...] = (),
    pr_labels: tuple[str, ...] = (),
    file_paths: tuple[str, ...] = ("src/hydro/hydro_system.cpp",),
    lines_changed: int = 12,
) -> commands.PullRequest:
    return commands.PullRequest(
        number=1,
        author="pr-author",
        assignees=assignees,
        labels=pr_labels,
        lines_changed=lines_changed,
        file_paths=file_paths,
    )


def make_comment(body: str, author: str = "maintainer", author_has_write_access: bool = True) -> commands.Comment:
    return commands.Comment(comment_id=99, author=author, author_has_write_access=author_has_write_access, body=body)


def run_comment(pull_request: commands.PullRequest, comment: commands.Comment) -> commands.Outcome | None:
    return commands.handle_comment(LABEL_CONFIG, pull_request, comment, OPEN_MILESTONES, TODAY)


class TestScopeLabels(unittest.TestCase):
    def test_hydro_file(self):
        scope_labels = labels.compute_scope_labels(LABEL_CONFIG, ("src/hydro/HLLC.hpp",))
        self.assertEqual(scope_labels, {"scope/hydro"})

    def test_mhd_file_inside_hydro_gets_both(self):
        scope_labels = labels.compute_scope_labels(LABEL_CONFIG, ("src/hydro/HLLD.hpp",))
        self.assertEqual(scope_labels, {"scope/hydro", "scope/MHD"})

    def test_problem_directories(self):
        file_paths = (
            "src/problems/MHDBlast/test_mhd_blast.cpp",
            "src/problems/RadDust/test_rad_dust.cpp",
            "src/problems/ParticleSink/test_particle_sink.cpp",
        )
        scope_labels = labels.compute_scope_labels(LABEL_CONFIG, file_paths)
        self.assertEqual(scope_labels, {"scope/MHD", "scope/radiation", "scope/dust", "scope/particles"})

    def test_unmatched_source_file_falls_back_to_core(self):
        scope_labels = labels.compute_scope_labels(LABEL_CONFIG, ("src/problems/SN/test_sn.cpp",))
        self.assertEqual(scope_labels, {"scope/core"})

    def test_file_outside_source_with_no_match_gets_no_scope(self):
        scope_labels = labels.compute_scope_labels(LABEL_CONFIG, ("scripts/plot_slice.py",))
        self.assertEqual(scope_labels, set())

    def test_ci_and_documentation(self):
        file_paths = (".github/workflows/cmake.yml", "docs/index.md", "README.md")
        scope_labels = labels.compute_scope_labels(LABEL_CONFIG, file_paths)
        self.assertEqual(scope_labels, {"scope/CI", "scope/documentation"})


class TestSizeLabel(unittest.TestCase):
    def test_boundaries(self):
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
        for lines_changed, expected_size in expected_sizes.items():
            with self.subTest(lines_changed=lines_changed):
                self.assertEqual(labels.compute_size_label(LABEL_CONFIG, lines_changed), expected_size)


class TestLabelChanges(unittest.TestCase):
    def test_new_pr_gets_scope_size_and_default_priority(self):
        label_changes = labels.compute_label_changes(LABEL_CONFIG, (), ("src/io/plotfile.cpp",), 40)
        self.assertEqual(label_changes.labels_to_add, ("priority/medium", "scope/IO", "size/M"))
        self.assertEqual(label_changes.labels_to_remove, ())

    def test_stale_scope_and_size_are_replaced_and_others_kept(self):
        current_labels = ("scope/radiation", "size/XS", "priority/high", "code-audit")
        label_changes = labels.compute_label_changes(LABEL_CONFIG, current_labels, ("src/io/plotfile.cpp",), 40)
        self.assertEqual(label_changes.labels_to_add, ("scope/IO", "size/M"))
        self.assertEqual(label_changes.labels_to_remove, ("scope/radiation", "size/XS"))

    def test_up_to_date_pr_needs_no_changes(self):
        current_labels = ("scope/IO", "size/M", "priority/low")
        label_changes = labels.compute_label_changes(LABEL_CONFIG, current_labels, ("src/io/plotfile.cpp",), 40)
        self.assertEqual(label_changes.labels_to_add, ())
        self.assertEqual(label_changes.labels_to_remove, ())


class TestParseCommand(unittest.TestCase):
    def test_plain_comment_is_not_a_command(self):
        self.assertIsNone(commands.parse_command("Looks good, thanks!"))

    def test_misspelt_command_is_ignored(self):
        self.assertIsNone(commands.parse_command("/accept-reveiw 2026-11-12"))

    def test_command_mid_comment_is_ignored(self):
        self.assertIsNone(commands.parse_command("I will run /release-review later"))

    def test_command_with_argument_and_extra_lines(self):
        parsed_command = commands.parse_command("/set-milestone Rewrite RHD module\nThis belongs to the rewrite.")
        self.assertEqual(parsed_command, ("/set-milestone", "Rewrite RHD module"))

    def test_empty_comment(self):
        self.assertIsNone(commands.parse_command("   "))


class TestAcceptReview(unittest.TestCase):
    def test_free_review_is_assigned(self):
        outcome = run_comment(make_pull_request(), make_comment("/accept-review 2026-11-12"))
        self.assertEqual(outcome, commands.Outcome(assignees_to_add=("maintainer",), react=True))

    def test_today_is_allowed(self):
        outcome = run_comment(make_pull_request(), make_comment("/accept-review 2026-11-05"))
        self.assertEqual(outcome.assignees_to_add, ("maintainer",))

    def test_same_reviewer_moving_the_date(self):
        outcome = run_comment(make_pull_request(assignees=("maintainer",)), make_comment("/accept-review 2026-11-20"))
        self.assertEqual(outcome, commands.Outcome(react=True))

    def test_second_reviewer_is_refused(self):
        outcome = run_comment(make_pull_request(assignees=("first-reviewer",)), make_comment("/accept-review 2026-11-12"))
        expected_reply = (
            "@first-reviewer has accepted this review. "
            "You're welcome to leave a review or comment, or ask them to hand it over."
        )
        self.assertEqual(outcome, commands.Outcome(reply=expected_reply))

    def test_several_assignees_set_by_hand(self):
        pull_request = make_pull_request(assignees=("reviewer-a", "reviewer-b"))
        outcome = run_comment(pull_request, make_comment("/accept-review 2026-11-12"))
        self.assertTrue(outcome.reply.startswith("@reviewer-a and @reviewer-b have accepted this review."))

    def test_missing_date(self):
        outcome = run_comment(make_pull_request(), make_comment("/accept-review"))
        self.assertEqual(outcome.reply, f"Use {commands.COMMAND_USAGES['/accept-review']}.")

    def test_unreadable_date(self):
        outcome = run_comment(make_pull_request(), make_comment("/accept-review next week"))
        self.assertEqual(outcome.reply, f"Use {commands.COMMAND_USAGES['/accept-review']}.")

    def test_past_date(self):
        outcome = run_comment(make_pull_request(), make_comment("/accept-review 2026-11-04"))
        self.assertTrue(outcome.reply.startswith("The review date has to be today or later."))

    def test_without_write_access(self):
        comment = make_comment("/accept-review 2026-11-12", author="contributor", author_has_write_access=False)
        outcome = run_comment(make_pull_request(), comment)
        self.assertEqual(outcome, commands.Outcome(reply="Only people with write access can accept a review."))

    def test_author_cannot_accept_own_pr(self):
        comment = make_comment("/accept-review 2026-11-12", author="pr-author")
        outcome = run_comment(make_pull_request(), comment)
        self.assertEqual(outcome, commands.Outcome(reply="You can't accept the review of your own PR."))


class TestReleaseReview(unittest.TestCase):
    def test_reviewer_releases(self):
        outcome = run_comment(make_pull_request(assignees=("maintainer",)), make_comment("/release-review"))
        self.assertEqual(outcome, commands.Outcome(assignees_to_remove=("maintainer",), react=True))

    def test_someone_else_cannot_release(self):
        outcome = run_comment(make_pull_request(assignees=("first-reviewer",)), make_comment("/release-review"))
        expected_reply = "@first-reviewer accepted this review, so only they can release it."
        self.assertEqual(outcome, commands.Outcome(reply=expected_reply))

    def test_nobody_has_accepted(self):
        outcome = run_comment(make_pull_request(), make_comment("/release-review"))
        self.assertEqual(outcome, commands.Outcome(reply="Nobody has accepted this review yet."))

    def test_unexpected_argument(self):
        outcome = run_comment(make_pull_request(assignees=("maintainer",)), make_comment("/release-review now"))
        self.assertEqual(outcome, commands.Outcome(reply="Use `/release-review`."))


class TestSetPriority(unittest.TestCase):
    def test_replaces_existing_priority(self):
        pull_request = make_pull_request(pr_labels=("priority/medium", "scope/hydro"))
        outcome = run_comment(pull_request, make_comment("/set-priority High"))
        expected_outcome = commands.Outcome(
            labels_to_add=("priority/high",),
            labels_to_remove=("priority/medium",),
            react=True,
        )
        self.assertEqual(outcome, expected_outcome)

    def test_same_priority_changes_nothing(self):
        pull_request = make_pull_request(pr_labels=("priority/low",))
        outcome = run_comment(pull_request, make_comment("/set-priority low"))
        self.assertEqual(outcome, commands.Outcome(react=True))

    def test_unknown_priority(self):
        outcome = run_comment(make_pull_request(), make_comment("/set-priority urgent"))
        self.assertEqual(outcome, commands.Outcome(reply="Use `/set-priority <low|medium|high>`."))

    def test_author_without_write_access_can_set(self):
        comment = make_comment("/set-priority high", author="pr-author", author_has_write_access=False)
        outcome = run_comment(make_pull_request(), comment)
        self.assertEqual(outcome.labels_to_add, ("priority/high",))

    def test_outsider_is_refused(self):
        comment = make_comment("/set-priority high", author="passer-by", author_has_write_access=False)
        outcome = run_comment(make_pull_request(), comment)
        expected_reply = "Only the PR author and people with write access can use `/set-priority`."
        self.assertEqual(outcome, commands.Outcome(reply=expected_reply))


class TestSetMilestone(unittest.TestCase):
    def test_matches_title_ignoring_case(self):
        outcome = run_comment(make_pull_request(), make_comment("/set-milestone rewrite rhd module"))
        self.assertEqual(outcome, commands.Outcome(milestone_number=6, react=True))

    def test_none_clears(self):
        outcome = run_comment(make_pull_request(), make_comment("/set-milestone none"))
        self.assertEqual(outcome, commands.Outcome(clear_milestone=True, react=True))

    def test_no_match_lists_open_milestones(self):
        outcome = run_comment(make_pull_request(), make_comment("/set-milestone RHD rewrite"))
        expected_reply = 'No open milestone is called "RHD rewrite". The open milestones are `Rewrite RHD module`, `photochem`.'
        self.assertEqual(outcome, commands.Outcome(reply=expected_reply))

    def test_no_open_milestones(self):
        outcome = commands.handle_comment(
            LABEL_CONFIG, make_pull_request(), make_comment("/set-milestone photochem"), (), TODAY
        )
        expected_reply = 'No open milestone is called "photochem", and there are no open milestones.'
        self.assertEqual(outcome, commands.Outcome(reply=expected_reply))

    def test_missing_title(self):
        outcome = run_comment(make_pull_request(), make_comment("/set-milestone"))
        self.assertEqual(outcome, commands.Outcome(reply="Use `/set-milestone <title|none>`."))


class TestRecomputeLabels(unittest.TestCase):
    def test_recomputes_scope_and_size(self):
        pull_request = make_pull_request(pr_labels=("scope/IO", "priority/high"), lines_changed=250)
        outcome = run_comment(pull_request, make_comment("/recompute-labels"))
        expected_outcome = commands.Outcome(
            labels_to_add=("scope/hydro", "size/L"),
            labels_to_remove=("scope/IO",),
            react=True,
        )
        self.assertEqual(outcome, expected_outcome)

    def test_unexpected_argument(self):
        outcome = run_comment(make_pull_request(), make_comment("/recompute-labels all"))
        self.assertEqual(outcome, commands.Outcome(reply="Use `/recompute-labels`."))


if __name__ == "__main__":
    unittest.main()
