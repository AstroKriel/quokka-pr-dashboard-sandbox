# PR Dashboard Tools

These tools keep the labels on Quokka PRs in step with what each PR changes, and let people act on a PR by writing commands in its comments. How to use the commands and what the labels mean is described in the contributor documentation. This README is for anyone reviewing or changing the code.

## Layout

| Path | Holds |
|---|---|
| `labels.toml` | The labels the tools manage, and the rules for giving them to PRs |
| `src/pr_dashboard/` | The code; see [its README](src/pr_dashboard/README.md) for what each module holds |
| `tests/` | Offline tests; they never contact GitHub |
| `../workflows/pr-dashboard-*.yml` | The four GitHub Actions workflows that run the code |

## How a Run Works

Every run follows the same steps:

1. A GitHub event starts one of the workflows.
2. The workflow runs one action of `run_dashboard.py`, with every input given explicitly on the command line.
3. The code reads what it needs from GitHub and decides what should change, as an `UpdatePlan`: labels to add or remove, assignees, a milestone, a reply, a reaction.
4. `apply_update_plan` writes that plan to GitHub.

Deciding and writing are kept apart, so every decision can be tested offline and inspected with `--dry-run`, and every run prints its plan to the Actions log.

| Workflow | Runs when | Action |
|---|---|---|
| `pr-dashboard-labels.yml` | A PR is opened, reopened or marked ready for review | `label-pr`: sets the scope and size labels, and the default priority |
| `pr-dashboard-commands.yml` | A comment containing `/` is posted on a PR | `run-command`: runs a command, or explains why it was not run |
| `pr-dashboard-repo-labels.yml` | `labels.toml` changes on `development`, or someone starts it from the Actions tab | `update-repo-labels`: creates and updates the labels on GitHub |
| `pr-dashboard-tests.yml` | A PR changes these tools or their workflows | Runs the offline tests |

## Changing the Labels

Edit `labels.toml`. Each category sets a prefix, and each label holds only its value; the label name on GitHub is the prefix plus the value, for example `scope/` and `hydro`.

- Scope labels list `path_patterns`. A PR gets every scope with a pattern matching one of its changed files, and `*` also matches `/`.
- Size labels list `min_num_lines`. A PR gets the largest one its line count reaches.
- One priority label is marked `default = true`, and is given to a PR with no priority.
- A changed file that matches no scope gives the PR the not-mapped label, so a missing pattern shows up on the PR.

After the change merges into `development`, the label workflow creates any new labels and updates colours and descriptions. A PR that is already open keeps its old labels until it is labelled again, for example with `/recompute-labels`.

## Running the Tests

From the repository root:

```bash
PYTHONPATH=.github/pr_dashboard/src python3 -m unittest discover --start-directory .github/pr_dashboard/tests --pattern "test_*.py"
```

One test checks that every file in the repository matches a scope, so adding a folder without a pattern for it fails the tests here first.

## Debugging a PR

The actions can be run from a local checkout with a `gh` login. `--dry-run` prints the plan without writing anything:

```bash
PYTHONPATH=.github/pr_dashboard/src python3 -m pr_dashboard.run_dashboard label-pr --repo quokka-astro/quokka --pr <number> --dry-run
PYTHONPATH=.github/pr_dashboard/src python3 -m pr_dashboard.run_dashboard update-repo-labels --repo quokka-astro/quokka --dry-run
```

## Design Decisions

Decisions I made along the way, and why.

### Labels

- **The tools manage only the label categories configured in `labels.toml`,** rather than every label on a PR. Any other label, such as one added by hand for another reason, is never touched. Within the scope and size categories the tools decide the labels, so one edited by hand is replaced the next time the PR is labelled. A priority is only set when a PR has none.
- **A file with no matching scope is flagged,** rather than given a fallback scope. A fallback would hide a missing pattern; the flag shows it, so the labels can be trusted to describe the whole change.

### Commands

- **Commands only run when they are at the start of a comment,** rather than anywhere in it. People mention commands in passing, quote them and paste examples. A command anywhere else is not run, and the comment gets a reply saying how to run it.
- **Every command gets visible feedback,** rather than succeeding or failing silently. A thumbs-up reaction means it ran; a reply means it was read but not run, and the reply says why. Misspelt commands are ignored, since other tools on Quokka also use commands that start with `/`.
- **One reviewer holds a review at a time,** rather than everyone who is asked to review. `/accept-review` makes the commenter the assignee of the PR, and refuses while someone else holds the review, so it is always clear who is responsible. Anyone can still comment and review.
- **Reviewers give their review deadline as a local date,** rather than working it out in UTC. Quokka is maintained from around the world and GitHub works in UTC, so a local today can be yesterday in UTC; a date up to one day in the past is therefore accepted.

### Running the Code

- **The labels workflow uses `pull_request_target`,** rather than `pull_request`. Only `pull_request_target` can label PRs from forks. It is safe here because the workflow checks out only these tools from the base branch, and never runs code from the PR.
