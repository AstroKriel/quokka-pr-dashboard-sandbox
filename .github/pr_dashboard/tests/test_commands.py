import datetime
import pathlib
import unittest

import commands
import labels

LABEL_CONFIG = labels.load_label_config(pathlib.Path(__file__).parents[1] / "labels.toml")
TODAY = datetime.date(2026, 11, 5)
OPEN_MILESTONES = (
    commands.Milestone(milestone_number=6, title="Rewrite RHD module"),
    commands.Milestone(milestone_number=8, title="photochem"),
)


def make_pull_request(
    assignees: tuple[str, ...] = (),
    pr_labels: tuple[str, ...] = (),
    file_paths: tuple[str, ...] = ("src/hydro/hydro_system.cpp",),
    num_lines_changed: int = 12,
) -> commands.PullRequest:
    return commands.PullRequest(
        pr_number=1,
        author="pr-author",
        assignees=assignees,
        labels=pr_labels,
        num_lines_changed=num_lines_changed,
        file_paths=file_paths,
    )


def make_comment(
    text: str,
    user_name: str = "maintainer",
    repo_role: commands.RepoRole = commands.RepoRole.WRITE,
) -> commands.Comment:
    user = commands.User(user_name=user_name, repo_role=repo_role)
    return commands.Comment(comment_id=99, user=user, text=text)


def run_comment(pull_request: commands.PullRequest, comment: commands.Comment) -> commands.UpdatePlan | None:
    return commands.handle_comment(LABEL_CONFIG, pull_request, comment, OPEN_MILESTONES, TODAY)


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
        update_plan = run_comment(make_pull_request(), make_comment("/accept-review 2026-11-12"))
        self.assertEqual(update_plan, commands.UpdatePlan(assignees_to_add=("maintainer",), react=True))

    def test_today_is_allowed(self):
        update_plan = run_comment(make_pull_request(), make_comment("/accept-review 2026-11-05"))
        self.assertEqual(update_plan.assignees_to_add, ("maintainer",))

    def test_same_reviewer_moving_the_date(self):
        pull_request = make_pull_request(assignees=("maintainer",))
        update_plan = run_comment(pull_request, make_comment("/accept-review 2026-11-20"))
        self.assertEqual(update_plan, commands.UpdatePlan(react=True))

    def test_second_reviewer_is_refused(self):
        pull_request = make_pull_request(assignees=("first-reviewer",))
        update_plan = run_comment(pull_request, make_comment("/accept-review 2026-11-12"))
        expected_reply = (
            "@first-reviewer has accepted this review. "
            "You're welcome to leave a review or comment, or ask them to hand it over."
        )
        self.assertEqual(update_plan, commands.UpdatePlan(reply=expected_reply))

    def test_several_assignees_set_by_hand(self):
        pull_request = make_pull_request(assignees=("reviewer-a", "reviewer-b"))
        update_plan = run_comment(pull_request, make_comment("/accept-review 2026-11-12"))
        self.assertTrue(update_plan.reply.startswith("@reviewer-a and @reviewer-b have accepted this review."))

    def test_missing_date(self):
        update_plan = run_comment(make_pull_request(), make_comment("/accept-review"))
        self.assertEqual(update_plan.reply, f"Use {commands.COMMAND_USAGES['/accept-review']}.")

    def test_unreadable_date(self):
        update_plan = run_comment(make_pull_request(), make_comment("/accept-review next week"))
        self.assertEqual(update_plan.reply, f"Use {commands.COMMAND_USAGES['/accept-review']}.")

    def test_past_date(self):
        update_plan = run_comment(make_pull_request(), make_comment("/accept-review 2026-11-04"))
        self.assertTrue(update_plan.reply.startswith("The review date has to be today or later."))

    def test_without_write_access(self):
        comment = make_comment("/accept-review 2026-11-12", user_name="contributor", repo_role=commands.RepoRole.READ)
        update_plan = run_comment(make_pull_request(), comment)
        self.assertEqual(update_plan, commands.UpdatePlan(reply="Only people with write access can accept a review."))

    def test_triage_is_not_enough(self):
        comment = make_comment("/accept-review 2026-11-12", user_name="triager", repo_role=commands.RepoRole.TRIAGE)
        update_plan = run_comment(make_pull_request(), comment)
        self.assertEqual(update_plan, commands.UpdatePlan(reply="Only people with write access can accept a review."))

    def test_author_cannot_accept_own_pr(self):
        comment = make_comment("/accept-review 2026-11-12", user_name="pr-author")
        update_plan = run_comment(make_pull_request(), comment)
        self.assertEqual(update_plan, commands.UpdatePlan(reply="You can't accept the review of your own PR."))


class TestReleaseReview(unittest.TestCase):
    def test_reviewer_releases(self):
        pull_request = make_pull_request(assignees=("maintainer",))
        update_plan = run_comment(pull_request, make_comment("/release-review"))
        self.assertEqual(update_plan, commands.UpdatePlan(assignees_to_remove=("maintainer",), react=True))

    def test_someone_else_cannot_release(self):
        pull_request = make_pull_request(assignees=("first-reviewer",))
        update_plan = run_comment(pull_request, make_comment("/release-review"))
        expected_reply = "@first-reviewer accepted this review, so only they can release it."
        self.assertEqual(update_plan, commands.UpdatePlan(reply=expected_reply))

    def test_nobody_has_accepted(self):
        update_plan = run_comment(make_pull_request(), make_comment("/release-review"))
        self.assertEqual(update_plan, commands.UpdatePlan(reply="Nobody has accepted this review yet."))

    def test_unexpected_argument(self):
        pull_request = make_pull_request(assignees=("maintainer",))
        update_plan = run_comment(pull_request, make_comment("/release-review now"))
        self.assertEqual(update_plan, commands.UpdatePlan(reply="Use `/release-review`."))


class TestSetPriority(unittest.TestCase):
    def test_replaces_existing_priority(self):
        pull_request = make_pull_request(pr_labels=("priority/medium", "scope/hydro"))
        update_plan = run_comment(pull_request, make_comment("/set-priority High"))
        expected_update_plan = commands.UpdatePlan(
            labels_to_add=("priority/high",),
            labels_to_remove=("priority/medium",),
            react=True,
        )
        self.assertEqual(update_plan, expected_update_plan)

    def test_same_priority_changes_nothing(self):
        pull_request = make_pull_request(pr_labels=("priority/low",))
        update_plan = run_comment(pull_request, make_comment("/set-priority low"))
        self.assertEqual(update_plan, commands.UpdatePlan(react=True))

    def test_unknown_priority(self):
        update_plan = run_comment(make_pull_request(), make_comment("/set-priority urgent"))
        self.assertEqual(update_plan, commands.UpdatePlan(reply="Use `/set-priority <low|medium|high>`."))

    def test_author_with_read_access_can_set(self):
        comment = make_comment("/set-priority high", user_name="pr-author", repo_role=commands.RepoRole.READ)
        update_plan = run_comment(make_pull_request(), comment)
        self.assertEqual(update_plan.labels_to_add, ("priority/high",))

    def test_triager_can_set(self):
        comment = make_comment("/set-priority high", user_name="triager", repo_role=commands.RepoRole.TRIAGE)
        update_plan = run_comment(make_pull_request(), comment)
        self.assertEqual(update_plan.labels_to_add, ("priority/high",))

    def test_outsider_is_refused(self):
        comment = make_comment("/set-priority high", user_name="passer-by", repo_role=commands.RepoRole.READ)
        update_plan = run_comment(make_pull_request(), comment)
        expected_reply = "Only the PR author and people with triage access or higher can use `/set-priority`."
        self.assertEqual(update_plan, commands.UpdatePlan(reply=expected_reply))


class TestSetMilestone(unittest.TestCase):
    def test_matches_title_ignoring_case(self):
        update_plan = run_comment(make_pull_request(), make_comment("/set-milestone rewrite rhd module"))
        milestone_change = commands.MilestoneChange(milestone_number=6)
        self.assertEqual(update_plan, commands.UpdatePlan(milestone_change=milestone_change, react=True))

    def test_none_removes(self):
        update_plan = run_comment(make_pull_request(), make_comment("/set-milestone none"))
        milestone_change = commands.MilestoneChange(milestone_number=None)
        self.assertEqual(update_plan, commands.UpdatePlan(milestone_change=milestone_change, react=True))

    def test_no_match_lists_open_milestones(self):
        update_plan = run_comment(make_pull_request(), make_comment("/set-milestone RHD rewrite"))
        expected_reply = 'No open milestone is called "RHD rewrite". The open milestones are `Rewrite RHD module`, `photochem`.'
        self.assertEqual(update_plan, commands.UpdatePlan(reply=expected_reply))

    def test_no_open_milestones(self):
        comment = make_comment("/set-milestone photochem")
        update_plan = commands.handle_comment(LABEL_CONFIG, make_pull_request(), comment, (), TODAY)
        expected_reply = 'No open milestone is called "photochem", and there are no open milestones.'
        self.assertEqual(update_plan, commands.UpdatePlan(reply=expected_reply))

    def test_missing_title(self):
        update_plan = run_comment(make_pull_request(), make_comment("/set-milestone"))
        self.assertEqual(update_plan, commands.UpdatePlan(reply="Use `/set-milestone <title|none>`."))


class TestRecomputeLabels(unittest.TestCase):
    def test_recomputes_scope_and_size(self):
        pull_request = make_pull_request(pr_labels=("scope/IO", "priority/high"), num_lines_changed=250)
        update_plan = run_comment(pull_request, make_comment("/recompute-labels"))
        expected_update_plan = commands.UpdatePlan(
            labels_to_add=("scope/hydro", "size/L"),
            labels_to_remove=("scope/IO",),
            react=True,
        )
        self.assertEqual(update_plan, expected_update_plan)

    def test_unexpected_argument(self):
        update_plan = run_comment(make_pull_request(), make_comment("/recompute-labels all"))
        self.assertEqual(update_plan, commands.UpdatePlan(reply="Use `/recompute-labels`."))


if __name__ == "__main__":
    unittest.main()
