import sqlite3
import csv
import json
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from src.config import DB_PATH
from src.parser import clean_phone

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS businesses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT,
    category TEXT,
    status TEXT,
    is_active INTEGER DEFAULT 1,
    is_checked INTEGER DEFAULT 0,
    address TEXT,
    website TEXT,
    rating REAL,
    reviews_count INTEGER,
    google_maps_url TEXT UNIQUE,
    search_query TEXT,
    latitude REAL,
    longitude REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_businesses_phone ON businesses(phone);
CREATE INDEX IF NOT EXISTS idx_businesses_category ON businesses(category);
CREATE INDEX IF NOT EXISTS idx_businesses_is_active ON businesses(is_active);
CREATE INDEX IF NOT EXISTS idx_businesses_is_checked ON businesses(is_checked);
CREATE INDEX IF NOT EXISTS idx_businesses_name ON businesses(name);
CREATE INDEX IF NOT EXISTS idx_businesses_url ON businesses(google_maps_url);
"""

class Database:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        # Ensure parent directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(CREATE_TABLE_SQL)
            # Run migration for existing databases missing is_checked column
            cursor.execute("PRAGMA table_info(businesses)")
            columns = [row["name"] for row in cursor.fetchall()]
            if "is_checked" not in columns:
                cursor.execute("ALTER TABLE businesses ADD COLUMN is_checked INTEGER DEFAULT 0")
                conn.commit()
            
            cursor.executescript(CREATE_INDEXES_SQL)
            conn.commit()

        # Tự động chuẩn hoá các SĐT cũ (+84 -> 0) và loại bỏ SĐT tổng đài 1900/1800, số bàn 028 nếu có
        self.clean_existing_phones()

    def clean_existing_phones(self) -> Dict[str, int]:
        """
        Quét và chuẩn hoá toàn bộ số điện thoại trong DB:
        - Chuyển đầu số +84 thành đầu số 0 (ví dụ +84901234567 -> 0901234567)
        - Xoá các số tổng đài (1900, 1800,...)
        - Xoá các số điện thoại bàn 028, +8428, 8428
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, phone FROM businesses WHERE phone IS NOT NULL AND phone != ''")
            rows = cursor.fetchall()
            
            updated_count = 0
            removed_invalid_count = 0
            
            for row in rows:
                old_phone = row["phone"]
                new_phone = clean_phone(old_phone)
                if new_phone != old_phone:
                    cursor.execute(
                        "UPDATE businesses SET phone = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (new_phone, row["id"])
                    )
                    updated_count += 1
                    if not new_phone:
                        removed_invalid_count += 1
            
            conn.commit()
            return {
                "total_checked": len(rows),
                "updated": updated_count,
                "removed_invalid": removed_invalid_count,
                "removed_028": removed_invalid_count
            }

    def update_checked_status(self, business_id: int, is_checked: int = 1) -> bool:
        """
        Updates the is_checked status for a specific business ID.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE businesses SET is_checked = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (is_checked, business_id)
            )
            return cursor.rowcount > 0

    def upsert_business(self, item: Dict[str, Any]) -> str:
        """
        Inserts or updates a business in the database.
        Returns: 'inserted', 'updated', or 'skipped'
        """
        if not item.get("name"):
            return "skipped"

        url = item.get("google_maps_url") or ""
        # Đảm bảo số điện thoại được chuẩn hoá và loại bỏ 028 / +8428
        phone = clean_phone(item.get("phone"))

        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if record exists by google_maps_url or by (name, phone)
            existing = None
            if url:
                cursor.execute("SELECT id FROM businesses WHERE google_maps_url = ?", (url,))
                existing = cursor.fetchone()

            if not existing and phone and item.get("name"):
                cursor.execute(
                    "SELECT id FROM businesses WHERE name = ? AND phone = ?",
                    (item["name"], phone)
                )
                existing = cursor.fetchone()

            if existing:
                business_id = existing["id"]
                cursor.execute("""
                    UPDATE businesses SET
                        name = COALESCE(?, name),
                        phone = ?,
                        category = COALESCE(?, category),
                        status = COALESCE(?, status),
                        is_active = COALESCE(?, is_active),
                        is_checked = COALESCE(?, is_checked),
                        address = COALESCE(?, address),
                        website = COALESCE(?, website),
                        rating = COALESCE(?, rating),
                        reviews_count = COALESCE(?, reviews_count),
                        search_query = COALESCE(?, search_query),
                        latitude = COALESCE(?, latitude),
                        longitude = COALESCE(?, longitude),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    item.get("name"),
                    phone,
                    item.get("category"),
                    item.get("status"),
                    item.get("is_active", 1),
                    item.get("is_checked"),
                    item.get("address"),
                    item.get("website"),
                    item.get("rating"),
                    item.get("reviews_count"),
                    item.get("search_query"),
                    item.get("latitude"),
                    item.get("longitude"),
                    business_id
                ))
                return "updated"
            else:
                cursor.execute("""
                    INSERT INTO businesses (
                        name, phone, category, status, is_active, is_checked,
                        address, website, rating, reviews_count,
                        google_maps_url, search_query, latitude, longitude
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item.get("name"),
                    phone,
                    item.get("category"),
                    item.get("status"),
                    item.get("is_active", 1),
                    item.get("is_checked", 0),
                    item.get("address"),
                    item.get("website"),
                    item.get("rating"),
                    item.get("reviews_count"),
                    url,
                    item.get("search_query"),
                    item.get("latitude"),
                    item.get("longitude")
                ))
                return "inserted"

    def get_stats(self) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) as total FROM businesses")
            total = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(*) as active FROM businesses WHERE is_active = 1")
            active = cursor.fetchone()["active"]

            cursor.execute("SELECT COUNT(*) as checked FROM businesses WHERE is_checked = 1")
            checked = cursor.fetchone()["checked"]

            cursor.execute("SELECT COUNT(*) as unchecked FROM businesses WHERE is_checked = 0 OR is_checked IS NULL")
            unchecked = cursor.fetchone()["unchecked"]

            cursor.execute("SELECT COUNT(*) as with_phone FROM businesses WHERE phone IS NOT NULL AND phone != ''")
            with_phone = cursor.fetchone()["with_phone"]

            cursor.execute("SELECT COUNT(DISTINCT category) as categories FROM businesses WHERE category IS NOT NULL")
            categories_count = cursor.fetchone()["categories"]

            cursor.execute("""
                SELECT category, COUNT(*) as count 
                FROM businesses 
                WHERE category IS NOT NULL AND category != '' 
                GROUP BY category 
                ORDER BY count DESC 
                LIMIT 10
            """)
            top_categories = [dict(row) for row in cursor.fetchall()]

            cursor.execute("""
                SELECT search_query, COUNT(*) as count 
                FROM businesses 
                WHERE search_query IS NOT NULL 
                GROUP BY search_query 
                ORDER BY count DESC 
                LIMIT 10
            """)
            top_queries = [dict(row) for row in cursor.fetchall()]

            return {
                "total_businesses": total,
                "active_businesses": active,
                "checked_businesses": checked,
                "unchecked_businesses": unchecked,
                "with_phone": with_phone,
                "distinct_categories": categories_count,
                "top_categories": top_categories,
                "top_queries": top_queries
            }

    def export_to_csv(self, file_path: str, only_active: bool = True) -> int:
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM businesses"
            if only_active:
                query += " WHERE is_active = 1"
            query += " ORDER BY id DESC"
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            if not rows:
                return 0

            fieldnames = [column[0] for column in cursor.description]
            with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in rows:
                    writer.writerow(dict(row))

            return len(rows)

    def export_to_json(self, file_path: str, only_active: bool = True) -> int:
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM businesses"
            if only_active:
                query += " WHERE is_active = 1"
            query += " ORDER BY id DESC"

            cursor.execute(query)
            rows = [dict(row) for row in cursor.fetchall()]

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, indent=2)

            return len(rows)

    def list_businesses(
        self,
        limit: int = 20,
        only_active: bool = True,
        is_checked: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT id, name, phone, category, status, is_active, is_checked, address, rating FROM businesses WHERE 1=1"
            params: List[Any] = []
            if only_active:
                query += " AND is_active = 1"
            if is_checked is not None:
                query += " AND is_checked = ?"
                params.append(is_checked)
            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, tuple(params))
            return [dict(row) for row in cursor.fetchall()]

