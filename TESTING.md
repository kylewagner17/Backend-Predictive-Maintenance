# Testing

Here’s how the test suite is wired up and how we usually work when changing behavior.

## Running pytest

From the project root (with dependencies installed):

```bash
pip install -r requirements.txt

pytest -v
pytest --cov=app --cov-report=term-missing -v

pytest test_api.py -v
pytest test_crud.py::test_create_device -v
```

On Windows, `python -m pytest ...` works the same way if `pytest` isn’t on your PATH.

## What `conftest.py` is doing

Before the FastAPI app imports, we:

- Set `TESTING=0` and `SCHEDULER_ENABLED=0` in the environment so the PLC background thread and APScheduler don’t start during test runs.
- Point SQLAlchemy at a **single file-backed SQLite database** under the system temp directory (`capstone_test.db`). That sounds picky, but it matters: an in-memory SQLite DB can accidentally become *two* different databases depending on import order, which breaks API tests. One file keeps the app and pytest on the same data.
- Monkey-patch `app.database.engine` and `SessionLocal` to that test engine, then import `app.main`. So when `TestClient` hits an endpoint, it uses the same DB as fixtures.

The `db` fixture opens a session, yields it, then closes and runs `metadata.drop_all` so the next test starts clean. Dynamic per-device tables (`device_{id}_readings`, etc.) live on the same metadata, so they get torn down with everything else.

The `client` fixture is just a `TestClient` around the shared app — no custom `get_db` override because the session factory already points at the test database.

## Which files contain what

| File | Rough purpose |
|------|----------------|
| `test_api.py` | HTTP routes: health, devices, sensors, analysis, notifications |
| `test_crud.py` | Database helpers: devices, readings, tag maps, predictions |
| `test_analysis.py` | Prediction pipeline: windows, ordering, stored snapshots |
| `test_industrial_poc.py` | PLC status codes, retention, scheduler gating, email gating, rule edge cases |

## TDD in practice

If you’re adding something new, the boring workflow still works well:

1. Write a test that describes the behavior you want and watch it fail.
2. Implement the smallest change that turns it green.
3. Refactor if needed; keep pytest happy.

Put the test next to the layer you’re touching: HTTP in `test_api.py`, pure DB in `test_crud.py`, scoring logic in `test_analysis.py` or `test_industrial_poc.py` depending on whether it’s core rules vs. industrial/PLC glue.

A few practical notes:

- Predictions and readings in tests go through the same CRUD paths the app uses, which means they land in **per-device tables**, not old global `sensor_readings` / `maintenance_predictions` names.
- When you assert on predictions after `run_predictions_for_device`, you’re checking objects returned from `get_predictions_for_device` — including optional `readings_snapshot` JSON when analysis stored a window.
- Keep tests independent: prefer the `db` fixture over relying on data left behind by another test.

That’s enough to get oriented; run `pytest -v` before you push and you’re in good shape.
