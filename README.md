# Quokka PR Dashboard Sandbox

A private test bed for the Quokka PR dashboard tools before they go into `quokka-astro/quokka`. The tools live in `.github/pr_dashboard/` (code in `src/`, tests in `tests/`, the label set in `labels.toml`) and `.github/workflows/pr-dashboard-*.yml`, at the same paths they will have in Quokka. The files under `src/`, `docs/` and `inputs/` are placeholders in Quokka's layout, to give test PRs something to change.

Offline tests:

```bash
PYTHONPATH=.github/pr_dashboard/src python3 -m unittest discover --start-directory .github/pr_dashboard/tests --pattern "test_*.py"
```
