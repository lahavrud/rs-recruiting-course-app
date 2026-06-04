# PR Checklist

Run the full pre-PR validation suite for rs-recruitment.

## Steps

1. Run backend linters:
   ```bash
   uv run ruff check .
   uv run ruff format --check .
   ```
   If format check fails, run `uv run ruff format .` to fix, then re-check.

2. Run frontend type check, lint, and tests:
   ```bash
   cd frontend && npx tsc --noEmit && npm run lint && npm run test
   ```

3. Run backend tests:
   ```bash
   uv run pytest -n auto -q
   ```

4. If `CHANGELOG.md` exists, verify it has an entry under `## Unreleased` for behaviour-changing PRs.

5. Report a final summary:
   ```
   ✓/✗ backend lint
   ✓/✗ backend format
   ✓/✗ frontend types
   ✓/✗ frontend lint
   ✓/✗ frontend tests
   ✓/✗ backend tests (N passed, N failed)
   ✓/✗ changelog
   ```

Do not proceed with PR creation if any check fails.
