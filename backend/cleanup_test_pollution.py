"""
cleanup_test_pollution.py — Safe cleanup of test-generated pollution records from webstore.db
"""
import sys
import os
import sqlite3
import argparse
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent
DB_PATH = BACKEND_DIR / "webstore.db"

def run_cleanup(dry_run: bool = True):
    print(f"=== CLEANUP TEST POLLUTION ({'DRY-RUN' if dry_run else 'EXECUTE'}) ===")
    print(f"Database: {DB_PATH}")

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # 1. Inspect test customers
    c.execute("""
        SELECT id, customer_code, name, email
        FROM customers
        WHERE customer_code LIKE 'KH-TEST-%'
    """)
    test_customers = c.fetchall()
    print(f"\n[1] Test Customers to delete ({len(test_customers)}):")
    for cust in test_customers:
        # Check FK
        c.execute("SELECT COUNT(*) FROM orders WHERE customer_id = ?", (cust["id"],))
        ref_orders = c.fetchone()[0]
        assert ref_orders == 0, f"Cannot delete customer {cust['id']} referenced by {ref_orders} orders!"
        print(f"  - ID={cust['id']} | Code={cust['customer_code']} | Name={cust['name']} | Email={cust['email']}")

    # 2. Inspect test categories
    c.execute("""
        SELECT id, code, name
        FROM categories
        WHERE code LIKE 'CAT-RETRO-%' OR code LIKE 'CAT-FORBIDDEN-%'
    """)
    test_categories = c.fetchall()
    print(f"\n[2] Test Categories to delete ({len(test_categories)}):")
    for cat in test_categories:
        # Check FK
        c.execute("SELECT COUNT(*) FROM products WHERE category_id = ?", (cat["id"],))
        ref_prods = c.fetchone()[0]
        assert ref_prods == 0, f"Cannot delete category {cat['id']} referenced by {ref_prods} products!"
        print(f"  - ID={cat['id']} | Code={cat['code']} | Name={cat['name']}")

    # 3. Inspect test users
    c.execute("""
        SELECT id, username, role, full_name
        FROM users
        WHERE (
            username LIKE 'cashier_%'
            OR username LIKE 'admin_sub_%'
            OR username LIKE 'staff_created_%'
            OR username LIKE 'fake_%'
            OR username LIKE 'legacy_mgr_%'
            OR username LIKE 'new_mgr_%'
        )
        AND id NOT IN (1, 2, 3, 4, 38, 39)
    """)
    test_users = c.fetchall()
    print(f"\n[3] Test Users to delete ({len(test_users)}):")
    safe_test_user_ids = []
    for u in test_users:
        c.execute("SELECT COUNT(*) FROM orders WHERE user_id = ? OR approved_by = ? OR processed_by = ? OR rejected_by = ?", (u["id"], u["id"], u["id"], u["id"]))
        ref_orders = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM purchase_receipts WHERE user_id = ?", (u["id"],))
        ref_pr = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM ai_audit_logs WHERE user_id = ?", (u["id"],))
        ref_ai = c.fetchone()[0]
        if ref_orders == 0 and ref_pr == 0 and ref_ai == 0:
            safe_test_user_ids.append(u["id"])
            print(f"  - ID={u['id']:2d} | Username={u['username']:20s} | Role={u['role']} (Safe to delete)")
        else:
            print(f"  - SKIP ID={u['id']} | Username={u['username']} | Referenced by {ref_orders} orders, {ref_pr} receipts, {ref_ai} ai_logs")

    if dry_run:
        print("\n[DRY-RUN] No changes were made to webstore.db. Re-run with --execute to commit deletions.")
        conn.close()
        return

    # EXECUTE DELETIONS IN TRANSACTION
    conn.execute("BEGIN TRANSACTION")
    try:
        # Delete test customers
        if test_customers:
            cust_ids = [cust["id"] for cust in test_customers]
            placeholders = ",".join("?" for _ in cust_ids)
            c.execute(f"DELETE FROM customers WHERE id IN ({placeholders})", cust_ids)
            print(f"\n[EXECUTE] Deleted {len(cust_ids)} test customers.")

        # Delete test categories
        if test_categories:
            cat_ids = [cat["id"] for cat in test_categories]
            placeholders = ",".join("?" for _ in cat_ids)
            c.execute(f"DELETE FROM categories WHERE id IN ({placeholders})", cat_ids)
            print(f"[EXECUTE] Deleted {len(cat_ids)} test categories.")

        # Delete safe test users
        if safe_test_user_ids:
            placeholders = ",".join("?" for _ in safe_test_user_ids)
            c.execute(f"DELETE FROM users WHERE id IN ({placeholders})", safe_test_user_ids)
            print(f"[EXECUTE] Deleted {len(safe_test_user_ids)} test users.")

        # Check foreign keys
        c.execute("PRAGMA foreign_key_check;")
        fk_errors = c.fetchall()
        if fk_errors:
            raise RuntimeError(f"Foreign key violations detected after cleanup: {fk_errors}")

        conn.commit()
        print("\n[EXECUTE] PRAGMA foreign_key_check: 0 errors. Cleanup successfully COMMITTED!")
    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] Cleanup failed and was ROLLED BACK: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cleanup test pollution from webstore.db")
    parser.add_argument("--execute", action="store_true", help="Actually execute the cleanup")
    args = parser.parse_args()

    run_cleanup(dry_run=not args.execute)
