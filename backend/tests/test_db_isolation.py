"""
test_db_isolation.py — Regression tests verifying database isolation between test and production/demo.
"""
import os
import sqlite3
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.core.config import settings
from app.models.schema import init_db
from seed_data import seed_database
from app.main import app

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROD_DB_PATH = BACKEND_DIR / "webstore.db"
TEST_DB_PATH = BACKEND_DIR / "test_webstore.db"

@pytest.fixture
def client():
    return TestClient(app)

def test_database_path_is_isolated():
    """Verify test runner environment is pointing to test_webstore.db, not webstore.db."""
    assert "test_webstore.db" in settings.DATABASE_PATH, f"Unsafe DB path in settings: {settings.DATABASE_PATH}"
    assert os.environ.get("DATABASE_PATH") == settings.DATABASE_PATH
    assert Path(settings.DATABASE_PATH).resolve() != PROD_DB_PATH.resolve()

def test_seed_database_is_idempotent():
    """Verify seed_database() can be executed repeatedly with zero record duplication."""
    conn = sqlite3.connect(settings.DATABASE_PATH)
    c = conn.cursor()
    
    # Get baseline counts in test database
    tables = ["users", "categories", "products", "customers", "orders", "purchase_receipts"]
    c.execute("SELECT COUNT(*) FROM users")
    users_before = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM categories")
    cats_before = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM products")
    prods_before = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM customers")
    custs_before = c.fetchone()[0]
    conn.close()

    # Run seed_database multiple times
    seed_database()
    seed_database()

    conn = sqlite3.connect(settings.DATABASE_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    assert c.fetchone()[0] == users_before
    c.execute("SELECT COUNT(*) FROM categories")
    assert c.fetchone()[0] == cats_before
    c.execute("SELECT COUNT(*) FROM products")
    assert c.fetchone()[0] == prods_before
    c.execute("SELECT COUNT(*) FROM customers")
    assert c.fetchone()[0] == custs_before
    conn.close()

def test_init_db_is_idempotent():
    """Verify init_db() can run multiple times safely without corrupting schema or data."""
    init_db()
    init_db()
    conn = sqlite3.connect(settings.DATABASE_PATH)
    c = conn.cursor()
    c.execute("PRAGMA foreign_key_check;")
    assert len(c.fetchall()) == 0
    conn.close()

def test_test_operations_do_not_pollute_production_db():
    """Verify writing test data only modifies test_webstore.db and leaves webstore.db untouched."""
    # 1. Snapshot production database counts
    prod_conn = sqlite3.connect(str(PROD_DB_PATH))
    prod_c = prod_conn.cursor()
    prod_c.execute("SELECT COUNT(*) FROM categories")
    prod_cats_before = prod_c.fetchone()[0]
    prod_c.execute("SELECT COUNT(*) FROM customers")
    prod_custs_before = prod_c.fetchone()[0]
    prod_conn.close()

    # 2. Insert test record using test connection
    from app.core.database import get_db_transaction
    with get_db_transaction() as test_conn:
        test_conn.execute(
            "INSERT INTO categories (code, name, description) VALUES (?, ?, ?)",
            ("CAT-ISOLATION-VERIFY", "Test Isolation Category", "Temp category")
        )
        test_conn.execute(
            "INSERT INTO customers (customer_code, name, phone, email) VALUES (?, ?, ?, ?)",
            ("KH-ISO-VERIFY", "Test Isolation Customer", "0999999999", "iso@test.vn")
        )

    # 3. Verify inserted into test_webstore.db
    test_conn = sqlite3.connect(settings.DATABASE_PATH)
    test_c = test_conn.cursor()
    test_c.execute("SELECT COUNT(*) FROM categories WHERE code = 'CAT-ISOLATION-VERIFY'")
    assert test_c.fetchone()[0] == 1
    test_c.execute("SELECT COUNT(*) FROM customers WHERE customer_code = 'KH-ISO-VERIFY'")
    assert test_c.fetchone()[0] == 1
    test_conn.close()

    # 4. Assert production database (webstore.db) counts are 100% unchanged
    prod_conn = sqlite3.connect(str(PROD_DB_PATH))
    prod_c = prod_conn.cursor()
    prod_c.execute("SELECT COUNT(*) FROM categories")
    assert prod_c.fetchone()[0] == prod_cats_before, "Pollution detected in webstore.db categories!"
    prod_c.execute("SELECT COUNT(*) FROM customers")
    assert prod_c.fetchone()[0] == prod_custs_before, "Pollution detected in webstore.db customers!"
    prod_c.execute("SELECT COUNT(*) FROM categories WHERE code = 'CAT-ISOLATION-VERIFY'")
    assert prod_c.fetchone()[0] == 0
    prod_c.execute("SELECT COUNT(*) FROM customers WHERE customer_code = 'KH-ISO-VERIFY'")
    assert prod_c.fetchone()[0] == 0
    prod_conn.close()
