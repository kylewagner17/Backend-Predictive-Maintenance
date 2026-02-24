"""
Pytest fixtures: test DB (SQLite) and API client.
Set TESTING=1 so the app does not start the PLC poll thread.
Use one file-based SQLite DB so the app and tests share the same database.
"""
import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Disable PLC loop before app is imported
os.environ["TESTING"] = "1"

# Single file-based test DB so create_all() and request handlers use the same DB.
# (In-memory SQLite can end up as two DBs due to import order; file ensures one shared DB.)
_test_db_path = os.path.join(tempfile.gettempdir(), "capstone_test.db")
if os.path.exists(_test_db_path):
    try:
        os.remove(_test_db_path)
    except OSError:
        pass
SQLALCHEMY_DATABASE_URL = f"sqlite:///{_test_db_path}"
test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

import app.database  # noqa: E402
import app.models as models  # noqa: E402, F401 - register models with Base
# Replace app's engine and session so the whole app uses the test DB.
app.database.engine = test_engine
app.database.SessionLocal = TestingSessionLocal

from app.main import app  # noqa: E402
# create_app() already ran and called create_all(bind=engine), so test DB now has tables.


@pytest.fixture(scope="function")
def db():
    """Fresh DB session per test; ensure tables exist, then drop after test for clean slate next time."""
    # Ensure tables exist (create_app() already ran create_all on test_engine; recreate if dropped)
    models.Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        models.Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db):
    """API test client using the same in-memory SQLite DB (no override needed)."""
    with TestClient(app) as c:
        yield c
