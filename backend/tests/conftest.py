import os
import sys
import shutil
from pathlib import Path
import pytest

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Define isolated test database and ChromaDB paths
TEST_DB_PATH = str(BACKEND_DIR / "test_webstore.db")
TEST_CHROMA_PATH = str(BACKEND_DIR / "scratch" / "test_chroma_data")

# Force DATABASE_PATH and CHROMA_PERSIST_DIRECTORY environment variables BEFORE importing app/settings
os.environ["DATABASE_PATH"] = TEST_DB_PATH
os.environ["CHROMA_PERSIST_DIRECTORY"] = TEST_CHROMA_PATH
os.environ["APP_ENV"] = "testing"

from app.core.config import settings
settings.DATABASE_PATH = TEST_DB_PATH
settings.CHROMA_PERSIST_DIRECTORY = TEST_CHROMA_PATH

import chromadb
from app.models.schema import init_db
from seed_data import seed_database
from app.services.rag_service import rag_service

def cleanup_test_files():
    for ext in ["", "-wal", "-shm"]:
        p = Path(TEST_DB_PATH + ext)
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass
    if os.path.exists(TEST_CHROMA_PATH):
        try:
            shutil.rmtree(TEST_CHROMA_PATH, ignore_errors=True)
        except Exception:
            pass

@pytest.fixture(scope="session", autouse=True)
def isolate_test_database():
    """
    Session-level fixture:
    1. Ensures all tests run against test_webstore.db and isolated test_chroma_data.
    2. Initializes schema and seeds clean demo data into test_webstore.db.
    3. Guarantees webstore.db and production chroma_data are NEVER touched or modified by tests.
    4. Automatically cleans up test files upon session completion.
    """
    # Safety assertions
    assert "test" in settings.DATABASE_PATH.lower(), f"Unsafe DATABASE_PATH: {settings.DATABASE_PATH}"
    assert not settings.DATABASE_PATH.endswith("webstore.db") or "test" in os.path.basename(settings.DATABASE_PATH).lower()

    # Clean old leftover test database & test chroma
    cleanup_test_files()

    # Setup isolated test database with fresh schema & seed data
    init_db()
    seed_database()

    # Isolate ChromaDB collection for the test session
    rag_service.persist_dir = Path(TEST_CHROMA_PATH)
    rag_service.persist_dir.mkdir(parents=True, exist_ok=True)
    rag_service.client = chromadb.PersistentClient(path=TEST_CHROMA_PATH)
    rag_service.collection = rag_service.client.get_or_create_collection(
        name="storeflow_products",
        metadata={"hnsw:space": "cosine"}
    )
    rag_service.sync_all_products()

    yield

    # Teardown: remove test database and test chroma files
    cleanup_test_files()
