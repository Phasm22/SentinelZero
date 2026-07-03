# SentinelZero Test Suite

## Structure

```
tests/
├── conftest.py              # Shared fixtures (if present)
├── unit/                    # Fast, isolated tests
│   ├── test_database.py
│   ├── test_scanner_helpers.py
│   ├── test_sensor_telemetry.py
│   ├── test_host_context.py
│   ├── test_insights_and_diff.py
│   ├── test_hunter_reports.py
│   └── …
└── integration/             # Flask test client, API flows
    ├── test_api_endpoints.py
    ├── test_comprehensive_api.py
    ├── test_aux_routes.py
    └── test_scan_flow_socket.py
```

There is no `tests/e2e/` Python directory. Frontend tests use **Vitest** in `frontend/react-sentinelzero/`. Playwright is a dev dependency but no `.spec.js` suites are checked in; Playwright output dirs are gitignored.

## Running tests

From repo root via `frontend/package.json`:

```bash
cd frontend
npm run test:backend       # all backend tests + coverage
npm run test:unit          # unit only
npm run test:integration   # integration only
npm run test:frontend      # Vitest (React)
npm run test               # backend + frontend
npm run test:coverage      # backend with HTML coverage report
```

Directly in backend:

```bash
cd backend
uv run pytest tests/ -v
uv run pytest tests/unit/test_sensor_telemetry.py -v
```

Frontend only:

```bash
cd frontend/react-sentinelzero
npm run test:run
npm run test:coverage
```

## Coverage

Configured in `backend/pyproject.toml`:

- Source: `src/` (+ `app.py` when run via npm scripts)
- Minimum: **38%** (`--cov-fail-under=38`)
- HTML report: `backend/htmlcov/`

Coverage data (`.coverage`) is gitignored.

## Writing tests

**Unit tests** — mock external I/O, use in-memory SQLite:

```python
app = create_app({
    'TESTING': True,
    'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
    'ENABLE_BACKGROUND_SERVICES': False,
})
```

**Integration tests** — use Flask test client against the same in-memory config.

Place new files under `tests/unit/` or `tests/integration/` following the `test_*.py` naming convention.

## Lint and format

```bash
cd frontend
npm run lint          # flake8 on backend
npm run format        # black on backend
npm run lint:frontend
npm run pre-commit    # lint + backend tests
```

## Troubleshooting

```bash
# Verbose single file
uv run pytest tests/unit/test_host_context.py -v -s

# Drop into debugger on failure
uv run pytest tests/unit/test_scanner_helpers.py --pdb
```
