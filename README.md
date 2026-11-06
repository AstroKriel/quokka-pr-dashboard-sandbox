# Quokka PR Dashboard Sandbox

A private test bed for the Quokka PR dashboard tools before they go into `quokka-astro/quokka`. The tools live in `.github/pr_dashboard/` (the `pr_dashboard` package in `src/pr_dashboard/`, tests in `tests/`, the label set in `labels.toml`) and `.github/workflows/pr-dashboard-*.yml`, at the same paths they will have in Quokka. The files under `src/`, `docs/` and `inputs/` are placeholders in Quokka's layout, to give test PRs something to change.

Offline tests:

```bash
PYTHONPATH=.github/pr_dashboard/src python3 -m unittest discover --start-directory .github/pr_dashboard/tests --pattern "test_*.py"
```

A dry run against a real PR, which prints the planned label changes without writing anything:

```bash
PYTHONPATH=.github/pr_dashboard/src python3 -m pr_dashboard.run_dashboard label-pr --repo quokka-astro/quokka --pr <number> --dry-run
```
