"""
cleanup_duplicates.py — Script dọn dẹp sản phẩm trùng tên trong StoreFlow AI

Mục tiêu:
  1. Tìm tất cả nhóm sản phẩm có cùng `name` (case-insensitive).
  2. Với mỗi nhóm trùng, giữ lại 01 bản ghi "chính" theo ưu tiên:
       a. status = 'active' trước
       b. stock_quantity cao nhất
       c. id nhỏ nhất (tạo sớm nhất)
  3. Chuyển toàn bộ FK references (order_items, purchase_items, inventory_logs)
     từ bản ghi bị xóa → bản ghi chính.
  4. Hard Delete các bản ghi trùng.
  5. Xóa vector tương ứng khỏi ChromaDB.
  6. Re-sync bản ghi chính vào ChromaDB.

Cách chạy (từ thư mục backend/):
    python cleanup_duplicates.py [--dry-run]

    --dry-run  : Chỉ in báo cáo, KHÔNG thực sự xóa hay cập nhật.
"""

import sys
import os
import sqlite3
import argparse
from collections import defaultdict

# ---------------------------------------------------------------------------
# Setup path để import được app.* modules
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

DB_PATH = os.path.join(SCRIPT_DIR, "webstore.db")

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=OFF")  # Tự xử lý FK thủ công
    return conn


def find_duplicate_groups(conn: sqlite3.Connection) -> dict:
    """
    Trả về dict: { lower_name -> [list of product rows] }
    Chỉ trả về các nhóm có ít nhất 2 bản ghi.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, sku, name, status, stock_quantity, created_at
        FROM products
        ORDER BY LOWER(name), status DESC, stock_quantity DESC, id ASC
    """)
    rows = cursor.fetchall()

    groups = defaultdict(list)
    for row in rows:
        key = row["name"].strip().lower()
        groups[key].append(dict(row))

    return {k: v for k, v in groups.items() if len(v) > 1}


def pick_primary(group: list) -> dict:
    """
    Chọn bản ghi chính theo thứ tự ưu tiên:
      1. status = 'active' trước inactive
      2. stock_quantity cao nhất
      3. id nhỏ nhất (tạo sớm nhất)
    """
    return sorted(
        group,
        key=lambda p: (
            0 if p["status"] == "active" else 1,
            -p["stock_quantity"],
            p["id"],
        )
    )[0]


def reassign_fk(conn: sqlite3.Connection, old_id: int, new_id: int, dry_run: bool):
    """Cập nhật FK trong order_items, purchase_items, inventory_logs."""
    tables = [
        ("order_items",    "product_id"),
        ("purchase_items", "product_id"),
        ("inventory_logs", "product_id"),
    ]
    cursor = conn.cursor()
    for table, col in tables:
        cursor.execute(f"SELECT COUNT(*) as cnt FROM {table} WHERE {col} = ?", (old_id,))
        cnt = cursor.fetchone()["cnt"]
        if cnt > 0:
            if dry_run:
                print(f"    [DRY-RUN] WOULD UPDATE {cnt} row(s) in `{table}`: {col} {old_id} -> {new_id}")
            else:
                cursor.execute(
                    f"UPDATE {table} SET {col} = ? WHERE {col} = ?",
                    (new_id, old_id)
                )
                print(f"    [FK] Updated {cnt} row(s) in `{table}`: {col} {old_id} -> {new_id}")


def hard_delete_product(conn: sqlite3.Connection, product_id: int, dry_run: bool):
    """Xóa cứng sản phẩm khỏi SQLite."""
    cursor = conn.cursor()
    if dry_run:
        print(f"    [DRY-RUN] WOULD DELETE products.id={product_id}")
    else:
        cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
        print(f"    [DELETED] products.id={product_id}")


def chroma_delete(product_ids: list, dry_run: bool):
    """Xóa vector khỏi ChromaDB cho các product_ids đã hard-delete."""
    if not product_ids:
        return
    try:
        from app.services.rag_service import rag_service
        for pid in product_ids:
            if dry_run:
                print(f"    [DRY-RUN] WOULD delete ChromaDB vector for product_id={pid}")
            else:
                rag_service.delete_single_product(pid)
                print(f"    [ChromaDB] Deleted vector for product_id={pid}")
    except Exception as e:
        print(f"    [ChromaDB WARNING] Could not delete: {e}")


def chroma_resync(primary_ids: list, dry_run: bool):
    """Re-upsert bản ghi chính vào ChromaDB sau khi dọn."""
    if not primary_ids:
        return
    if dry_run:
        print(f"    [DRY-RUN] WOULD re-sync {len(primary_ids)} primary product(s) into ChromaDB")
        return
    try:
        from app.services.rag_service import rag_service
        for pid in primary_ids:
            ok = rag_service.upsert_single_product(pid)
            print(f"    [ChromaDB] Re-synced product_id={pid}: {'OK' if ok else 'SKIPPED'}")
    except Exception as e:
        print(f"    [ChromaDB WARNING] Could not re-sync: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Dọn dẹp sản phẩm trùng tên trong StoreFlow AI"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Chỉ in báo cáo, không thay đổi dữ liệu"
    )
    args = parser.parse_args()
    dry_run: bool = args.dry_run

    print("=" * 62)
    print("  StoreFlow AI — Cleanup Duplicate Products")
    print(f"  Database : {DB_PATH}")
    print(f"  Mode     : {'DRY-RUN (no changes)' if dry_run else 'LIVE (changes will be committed)'}")
    print("=" * 62)

    if not os.path.exists(DB_PATH):
        print(f"\n[ERROR] Database not found at: {DB_PATH}")
        sys.exit(1)

    conn = get_connection(DB_PATH)
    try:
        groups = find_duplicate_groups(conn)

        if not groups:
            print("\n[OK] Khong tim thay san pham trung ten. Database da sach!")
            return

        print(f"\n[FOUND] {len(groups)} nhom san pham trung ten:\n")

        deleted_ids: list = []
        primary_ids: list = []
        total_deleted = 0

        for name_key, group in groups.items():
            primary = pick_primary(group)
            duplicates = [p for p in group if p["id"] != primary["id"]]

            original_name = group[0]["name"]
            print(f"  [NHOM] \"{original_name}\" — {len(group)} ban ghi")
            print(f"    GIU LAI : id={primary['id']} | SKU={primary['sku']} "
                  f"| status={primary['status']} | stock={primary['stock_quantity']}")

            for dup in duplicates:
                print(f"    XOA     : id={dup['id']} | SKU={dup['sku']} "
                      f"| status={dup['status']} | stock={dup['stock_quantity']}")

                # Bước 1: Chuyển FK
                reassign_fk(conn, dup["id"], primary["id"], dry_run)

                # Bước 2: Hard delete SQLite
                hard_delete_product(conn, dup["id"], dry_run)

                deleted_ids.append(dup["id"])
                total_deleted += 1

            primary_ids.append(primary["id"])
            print()

        # Bước 3: Đồng bộ ChromaDB
        print("--- ChromaDB Sync ---")
        chroma_delete(deleted_ids, dry_run)
        chroma_resync(primary_ids, dry_run)

        # Bước 4: Commit
        if not dry_run:
            conn.commit()
            print("\n[OK] Da commit thay doi vao database.")

        print("\n" + "=" * 62)
        print("  Tong ket:")
        print(f"    - Nhom trung lap  : {len(groups)}")
        print(f"    - Ban ghi da xoa  : {total_deleted}")
        print(f"    - Ban ghi giu lai : {len(primary_ids)}")
        if dry_run:
            print("\n  [!] Day la DRY-RUN. Chay lai KHONG co --dry-run de ap dung.")
        print("=" * 62)

    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()

