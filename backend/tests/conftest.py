import os
import sys
import shutil
from pathlib import Path
import pytest

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Define isolated test database path
TEST_DB_PATH = str(BACKEND_DIR / "test_webstore.db")

# Force DATABASE_PATH environment variable BEFORE importing app/settings
os.environ["DATABASE_PATH"] = TEST_DB_PATH
os.environ["APP_ENV"] = "testing"

from app.core.config import settings
settings.DATABASE_PATH = TEST_DB_PATH

from app.models.schema import init_db
from seed_data import seed_database

def cleanup_test_files():
    for ext in ["", "-wal", "-shm"]:
        p = Path(TEST_DB_PATH + ext)
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass

@pytest.fixture(scope="session", autouse=True)
def isolate_test_database():
    """
    Session-level fixture:
    1. Ensures all tests run against test_webstore.db.
    2. Initializes schema and seeds clean demo data into test_webstore.db.
    3. Guarantees webstore.db is NEVER touched or modified by tests.
    4. Automatically cleans up test_webstore.db upon session completion.
    """
    # Safety assertions
    assert "test" in settings.DATABASE_PATH.lower(), f"Unsafe DATABASE_PATH: {settings.DATABASE_PATH}"
    assert not settings.DATABASE_PATH.endswith("webstore.db") or "test" in os.path.basename(settings.DATABASE_PATH).lower()

    # Clean old leftover test database
    cleanup_test_files()

    # Setup isolated test database with fresh schema & seed data
    init_db()
    seed_database()

    yield

    # Teardown: remove test database files
    cleanup_test_files()
