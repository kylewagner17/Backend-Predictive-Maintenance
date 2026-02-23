# Testing and test-driven development (TDD)

## Run tests

```bash
# Install dependencies (includes pytest, pytest-cov)
pip install -r requirements.txt

# Run all tests
pytest -v

# Run with coverage
pytest --cov=app --cov-report=term-missing -v

# Run specific file or test
pytest test_api.py -v
pytest test_crud.py::test_create_device -v
```

## Layout

- **`conftest.py`** – Pytest fixtures:
  - `db`: fresh SQLite in-memory session per test (tables created/dropped).
  - `client`: FastAPI `TestClient` with `get_db` overridden to use the test DB so API tests don’t touch PostgreSQL.
- **`test_api.py`** – API endpoint tests (health, devices, sensors, analysis, notifications).
- **`test_crud.py`** – CRUD layer tests (devices, readings, tag map, predictions).
- **`test_analysis.py`** – Analysis logic tests (threshold recommendations, run for all devices).

When `TESTING=1` is set (done in `conftest.py` before importing the app), the PLC poll thread is not started.

## TDD workflow

1. **Red**: Write a failing test for the behavior you want (new endpoint, new CRUD function, or new analysis rule).
2. **Green**: Implement the minimum code to make the test pass.
3. **Refactor**: Clean up while keeping tests green.

When adding a feature:

- Prefer adding a test in the right file (`test_api.py` for routes, `test_crud.py` for DB access, `test_analysis.py` for prediction logic).
- Use the `client` fixture for HTTP tests and the `db` fixture when you need to seed data or assert on DB state directly.
- Keep tests isolated: each test gets a fresh DB (for tests that use the `db` fixture).

## Adding new tests

- **New API route**: Add a test in `test_api.py` that calls the route via `client` and asserts status and JSON.
- **New CRUD function**: Add a test in `test_crud.py` that calls the function with `db` and asserts on return value or query results.
- **New analysis rule**: Add a test in `test_analysis.py` that creates readings via `db`, runs `run_predictions_for_device` or `run_predictions_all_devices`, and asserts on `maintenance_predictions`.
