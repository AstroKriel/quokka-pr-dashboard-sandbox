# Quokka PR Dashboard Sandbox

A private test bed for the Quokka PR dashboard tools before they go into `quokka-astro/quokka`. The tools live in `.github/pr_dashboard/` and `.github/workflows/pr-dashboard-*.yml`, at the same paths they will have in Quokka. The files under `src/`, `docs/` and `inputs/` are placeholders in Quokka's layout, to give test PRs something to change.

Offline tests:

```bash
python3 -m unittest discover --start-directory .github/pr_dashboard --pattern "test_*.py"
```
