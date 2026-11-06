import datetime
import pathlib
import unittest

from pr_dashboard import interpret_commands
from pr_dashboard import load_labels
from pr_dashboard import pr_context

CONFIGURED_LABELS = load_labels.load_configured_labels(pathlib.Path(__file__).parents[1] / "labels.toml")
TODAY = datetime.date(2026, 11, 5)
OPEN_MILESTONES = (
    pr_context.Milestone(
        milestone_number=6,
        title="Rewrite RHD module",
    ),
    pr_context.Milestone(
        milestone_number=8,
        title="photochem",
    ),
)


def make_pull_request(
    *,
    assignee_user_names: tuple[str, ...] = (),
    label_names: tuple[str, ...] = (),
    edited_file_paths: tuple[str, ...] = ("src/hydro/hydro_system.cpp", ),
    num_lines_changed: int = 12,
) -> pr_context.PullRequest:
    return pr_context.PullRequest(
        pr_number=1,
        author_user_name="pr-author",
        assignee_user_names=assignee_user_names,
        label_names=label_names,
        num_lines_changed=num_lines_changed,
        edited_file_paths=edited_file_paths,
    )


DEFAULT_PULL_REQUEST = make_pull_request()


def run_command(
    *,
    text: str,
    pull_request: pr_context.PullRequest = DEFAULT_PULL_REQUEST,
    user_name: str = "maintainer",
    role_in_repo: pr_context.RoleInRepo = pr_context.RoleInRepo.WRITE,
    open_milestones: tuple[pr_context.Milestone, ...] = OPEN_MILESTONES,
) -> pr_context.UpdatePlan | None:
    user = pr_context.User(
        user_name=user_name,
        role_in_repo=role_in_repo,
    )
    comment = pr_context.Comment(
        comment_id=99,
        user=user,
        text=text,
    )
    return interpret_commands.make_comment_update_plan(
        configured_labels=CONFIGURED_LABELS,
        pull_request=pull_request,
        comment=comment,
        open_milestones=open_milestones,
        today=TODAY,
    )


class TestInterpretCommands_Parse(unittest.TestCase):

    def test_plain_comment_is_not_a_command(
        self,
    ):
        self.assertIsNone(interpret_commands.parse_command("Looks good, thanks!"))

    def test_misspelt_command_is_ignored(
        self,
    ):
        self.assertIsNone(interpret_commands.parse_command("/accept-reveiw 2026-11-12"))

    def test_command_mid_comment_is_ignored(
        self,
    ):
        self.assertIsNone(interpret_commands.parse_command("I will run /release-review later"))

    def test_command_with_argument_and_extra_lines(
        self,
    ):
        parsed_command = interpret_commands.parse_command(
            "/set-milestone Rewrite RHD module\nThis belongs to the rewrite.",
        )
        self.assertEqual(parsed_command, (interpret_commands.SET_MILESTONE, "Rewrite RHD module"))

    def test_empty_comment(
        self,
    ):
        self.assertIsNone(interpret_commands.parse_command("   "))


class TestInterpretCommands_AcceptReview(unittest.TestCase):

    def test_free_review_is_assigned(
        self,
    ):
        update_plan = run_command(text="/accept-review 2026-11-12")
        expected_update_plan = pr_context.UpdatePlan(
            assignee_user_names_to_add=("maintainer", ),
            react=True,
        )
        self.assertEqual(update_plan, expected_update_plan)

    def test_today_is_allowed(
        self,
    ):
        update_plan = run_command(text="/accept-review 2026-11-05")
        self.assertEqual(update_plan.assignee_user_names_to_add, ("maintainer", ))

    def test_same_reviewer_moving_the_date(
        self,
    ):
        pull_request = make_pull_request(assignee_user_names=("maintainer", ))
        update_plan = run_command(
            text="/accept-review 2026-11-20",
            pull_request=pull_request,
        )
        self.assertEqual(update_plan, pr_context.UpdatePlan(react=True))

    def test_second_reviewer_is_refused(
        self,
    ):
        pull_request = make_pull_request(assignee_user_names=("first-reviewer", ))
        update_plan = run_command(
            text="/accept-review 2026-11-12",
            pull_request=pull_request,
        )
        expected_reply = (
            "@first-reviewer has accepted this review. "
            "You're welcome to leave a review or comment, or ask them to hand it over."
        )
        self.assertEqual(update_plan, pr_context.UpdatePlan(reply=expected_reply))

    def test_several_assignees_set_by_hand(
        self,
    ):
        pull_request = make_pull_request(assignee_user_names=("reviewer-a", "reviewer-b"))
        update_plan = run_command(
            text="/accept-review 2026-11-12",
            pull_request=pull_request,
        )
        self.assertTrue(
            update_plan.reply.startswith("@reviewer-a and @reviewer-b have accepted this review."),
        )

    def test_missing_date(
        self,
    ):
        update_plan = run_command(text="/accept-review")
        self.assertEqual(update_plan.reply, f"Use {interpret_commands.ACCEPT_REVIEW.usage}.")

    def test_unreadable_date(
        self,
    ):
        update_plan = run_command(text="/accept-review next week")
        self.assertEqual(update_plan.reply, f"Use {interpret_commands.ACCEPT_REVIEW.usage}.")

    def test_past_date(
        self,
    ):
        update_plan = run_command(text="/accept-review 2026-11-04")
        self.assertTrue(update_plan.reply.startswith("The review date has to be today or later."))

    def test_without_write_access(
        self,
    ):
        update_plan = run_command(
            text="/accept-review 2026-11-12",
            user_name="contributor",
            role_in_repo=pr_context.RoleInRepo.READ,
        )
        expected_update_plan = pr_context.UpdatePlan(
            reply="Only maintainers (anyone with write access) can accept a review.",
        )
        self.assertEqual(update_plan, expected_update_plan)

    def test_triage_is_not_enough(
        self,
    ):
        update_plan = run_command(
            text="/accept-review 2026-11-12",
            user_name="triager",
            role_in_repo=pr_context.RoleInRepo.TRIAGE,
        )
        expected_update_plan = pr_context.UpdatePlan(
            reply="Only maintainers (anyone with write access) can accept a review.",
        )
        self.assertEqual(update_plan, expected_update_plan)

    def test_author_cannot_accept_own_pr(
        self,
    ):
        update_plan = run_command(
            text="/accept-review 2026-11-12",
            user_name="pr-author",
        )
        expected_update_plan = pr_context.UpdatePlan(reply="You can't accept the review of your own PR.")
        self.assertEqual(update_plan, expected_update_plan)


class TestInterpretCommands_ReleaseReview(unittest.TestCase):

    def test_reviewer_releases(
        self,
    ):
        pull_request = make_pull_request(assignee_user_names=("maintainer", ))
        update_plan = run_command(
            text="/release-review",
            pull_request=pull_request,
        )
        expected_update_plan = pr_context.UpdatePlan(
            assignee_user_names_to_remove=("maintainer", ),
            react=True,
        )
        self.assertEqual(update_plan, expected_update_plan)

    def test_someone_else_cannot_release(
        self,
    ):
        pull_request = make_pull_request(assignee_user_names=("first-reviewer", ))
        update_plan = run_command(
            text="/release-review",
            pull_request=pull_request,
        )
        expected_reply = "@first-reviewer accepted this review, so only they can release it."
        self.assertEqual(update_plan, pr_context.UpdatePlan(reply=expected_reply))

    def test_nobody_has_accepted(
        self,
    ):
        update_plan = run_command(text="/release-review")
        self.assertEqual(update_plan, pr_context.UpdatePlan(reply="Nobody has accepted this review yet."))

    def test_unexpected_argument(
        self,
    ):
        pull_request = make_pull_request(assignee_user_names=("maintainer", ))
        update_plan = run_command(
            text="/release-review now",
            pull_request=pull_request,
        )
        self.assertEqual(update_plan, pr_context.UpdatePlan(reply="Use `/release-review`."))


class TestInterpretCommands_SetPriority(unittest.TestCase):

    def test_replaces_existing_priority(
        self,
    ):
        pull_request = make_pull_request(label_names=("priority/medium", "scope/hydro"))
        update_plan = run_command(
            text="/set-priority High",
            pull_request=pull_request,
        )
        expected_update_plan = pr_context.UpdatePlan(
            label_names_to_add=("priority/high", ),
            label_names_to_remove=("priority/medium", ),
            react=True,
        )
        self.assertEqual(update_plan, expected_update_plan)

    def test_same_priority_changes_nothing(
        self,
    ):
        pull_request = make_pull_request(label_names=("priority/low", ))
        update_plan = run_command(
            text="/set-priority low",
            pull_request=pull_request,
        )
        self.assertEqual(update_plan, pr_context.UpdatePlan(react=True))

    def test_unknown_priority(
        self,
    ):
        update_plan = run_command(text="/set-priority urgent")
        self.assertEqual(update_plan, pr_context.UpdatePlan(reply="Use `/set-priority <low|medium|high>`."))

    def test_author_with_read_access_can_set(
        self,
    ):
        update_plan = run_command(
            text="/set-priority high",
            user_name="pr-author",
            role_in_repo=pr_context.RoleInRepo.READ,
        )
        self.assertEqual(update_plan.label_names_to_add, ("priority/high", ))

    def test_triager_can_set(
        self,
    ):
        update_plan = run_command(
            text="/set-priority high",
            user_name="triager",
            role_in_repo=pr_context.RoleInRepo.TRIAGE,
        )
        self.assertEqual(update_plan.label_names_to_add, ("priority/high", ))

    def test_outsider_is_refused(
        self,
    ):
        update_plan = run_command(
            text="/set-priority high",
            user_name="passer-by",
            role_in_repo=pr_context.RoleInRepo.READ,
        )
        expected_reply = "Only the PR author and maintainers can use `/set-priority`."
        self.assertEqual(update_plan, pr_context.UpdatePlan(reply=expected_reply))


class TestInterpretCommands_SetMilestone(unittest.TestCase):

    def test_matches_title_ignoring_case(
        self,
    ):
        update_plan = run_command(text="/set-milestone rewrite rhd module")
        expected_update_plan = pr_context.UpdatePlan(
            milestone_change=pr_context.MilestoneChange(milestone_number=6),
            react=True,
        )
        self.assertEqual(update_plan, expected_update_plan)

    def test_none_removes(
        self,
    ):
        update_plan = run_command(text="/set-milestone none")
        expected_update_plan = pr_context.UpdatePlan(
            milestone_change=pr_context.MilestoneChange(milestone_number=None),
            react=True,
        )
        self.assertEqual(update_plan, expected_update_plan)

    def test_no_match_lists_open_milestones(
        self,
    ):
        update_plan = run_command(text="/set-milestone RHD rewrite")
        expected_reply = (
            'No open milestone is called "RHD rewrite". '
            "The open milestones are `Rewrite RHD module`, `photochem`."
        )
        self.assertEqual(update_plan, pr_context.UpdatePlan(reply=expected_reply))

    def test_no_open_milestones(
        self,
    ):
        update_plan = run_command(
            text="/set-milestone photochem",
            open_milestones=(),
        )
        expected_reply = 'No open milestone is called "photochem", and there are no open milestones.'
        self.assertEqual(update_plan, pr_context.UpdatePlan(reply=expected_reply))

    def test_missing_title(
        self,
    ):
        update_plan = run_command(text="/set-milestone")
        self.assertEqual(update_plan, pr_context.UpdatePlan(reply="Use `/set-milestone <title|none>`."))


class TestInterpretCommands_RecomputeLabels(unittest.TestCase):

    def test_recomputes_scope_and_size(
        self,
    ):
        pull_request = make_pull_request(
            label_names=("scope/IO", "priority/high"),
            num_lines_changed=250,
        )
        update_plan = run_command(
            text="/recompute-labels",
            pull_request=pull_request,
        )
        expected_update_plan = pr_context.UpdatePlan(
            label_names_to_add=("scope/hydro", "size/L"),
            label_names_to_remove=("scope/IO", ),
            react=True,
        )
        self.assertEqual(update_plan, expected_update_plan)

    def test_unexpected_argument(
        self,
    ):
        update_plan = run_command(text="/recompute-labels all")
        self.assertEqual(update_plan, pr_context.UpdatePlan(reply="Use `/recompute-labels`."))


class TestInterpretCommands_Help(unittest.TestCase):

    def test_lists_every_command(
        self,
    ):
        update_plan = run_command(text="/help")
        for command in interpret_commands.COMMANDS:
            with self.subTest(command_name=command.name):
                self.assertIn(f"`{command.name}", update_plan.reply)

    def test_fills_in_the_priority_values(
        self,
    ):
        update_plan = run_command(text="/help")
        self.assertIn("`/set-priority <low|medium|high>`: set this PR's priority", update_plan.reply)
        self.assertNotIn("{priority_values}", update_plan.reply)

    def test_anyone_can_ask(
        self,
    ):
        update_plan = run_command(
            text="/help",
            user_name="passer-by",
            role_in_repo=pr_context.RoleInRepo.READ,
        )
        self.assertTrue(update_plan.reply.startswith("PR dashboard commands:"))

    def test_extra_words_are_ignored(
        self,
    ):
        update_plan = run_command(text="/help me please")
        self.assertTrue(update_plan.reply.startswith("PR dashboard commands:"))

    def test_changes_nothing(
        self,
    ):
        update_plan = run_command(text="/help")
        self.assertEqual(update_plan, pr_context.UpdatePlan(reply=update_plan.reply))


if __name__ == "__main__":
    unittest.main()
