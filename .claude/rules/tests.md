# Test Rules

## Hard constraints
- **No network calls in `tests/unit/`** — use fixtures in `tests/fixtures/` and fakes in `tests/fakes/`
- **No cross-test imports** — tests import from `src/`, never from other test files
- **1:1 source mapping** — every `src/` module must have a corresponding test file (CI script enforces this)

## Structure
```
tests/
├── models/           # ORM model validation
├── services/         # Business logic (auth, admin, company, public, candidate)
├── api/              # Endpoint tests (SEO, rate limiting, request handling)
├── templates/        # Email template rendering
└── core/
    ├── services/     # Email, storage, file validation
    └── infrastructure/  # DB, config, security, transactions, rate limiting
```

## Execution
```bash
uv run pytest -n auto              # full suite, parallel (each worker = dedicated DB)
uv run pytest tests/services/auth/ # single directory
uv run pytest -k "test_lockout"    # filter by name
uv run pytest -x                   # stop on first failure
```

## Patterns
- Database tests use the `db_session` fixture — never open a session manually
- SQS/S3/email use fakes — see `tests/fakes/` for the fake implementations
- For async endpoints, use `AsyncClient` from `httpx` via the `client` fixture
- Factory helpers for model creation live in `tests/fixtures/factories.py`

## CI behaviour
Tests run with `uv sync --frozen --group test` + `pytest -n auto`. The `--frozen` flag means a stale `uv.lock` fails the build — always commit `uv.lock` after touching `pyproject.toml`.
