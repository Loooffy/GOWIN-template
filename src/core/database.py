"""
資料庫存取層

實作 DatabaseRepository 抽象類別，支援 SQLite 和 PostgreSQL。
使用統一的介面進行資料存取，便於切換資料庫後端。
"""

import sqlite3
import json
import logging
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
from pathlib import Path

from src.core.abstract import DatabaseRepository

logger = logging.getLogger(__name__)


class SQLiteRepository(DatabaseRepository):
    """SQLite 資料庫實作

    適用於本地開發和小規模部署。
    自動建立資料庫檔案和必要的表格。
    """

    def __init__(self, config: Dict[str, Any]):
        """初始化 SQLite 資料庫連接

        Args:
            config: 資料庫配置，必須包含 'path' 欄位
        """
        self.db_path = config.get("path", "./data/crawler.db")
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        """建立資料庫連接並初始化表格"""
        try:
            # 確保資料庫目錄存在
            db_dir = Path(self.db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)

            # 建立連接
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row  # 使用字典式存取

            logger.info(f"成功連接到 SQLite 資料庫: {self.db_path}")

            # 建立表格
            self._create_tables()

        except Exception as e:
            logger.error(f"連接 SQLite 資料庫失敗: {e}")
            raise

    def _create_tables(self) -> None:
        """建立必要的資料庫表格"""
        cursor = self.conn.cursor()

        # 主要資料表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                processed INTEGER DEFAULT 0,
                filter_result TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 建立索引以加速查詢
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_processed
            ON items(processed)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_created_at
            ON items(created_at DESC)
        """)

        self.conn.commit()
        logger.debug("資料庫表格已建立或已存在")

    def save_items(self, items: List[Dict[str, Any]]) -> None:
        """批量儲存資料項目

        Args:
            items: 待儲存的資料項目列表

        Raises:
            Exception: 當儲存失敗時
        """
        if not items:
            logger.warning("沒有項目需要儲存")
            return

        cursor = self.conn.cursor()
        saved_count = 0
        updated_count = 0

        try:
            for item in items:
                # 準備資料
                item_id = item.get("id")
                title = item.get("title", "")
                content = item.get("content", "")
                metadata = json.dumps(item.get("metadata", {}), ensure_ascii=False)
                processed = 1 if item.get("processed") else 0
                filter_result = json.dumps(item.get("filter_result", {}), ensure_ascii=False) if item.get("filter_result") else None

                # 檢查是否已存在
                cursor.execute("SELECT id FROM items WHERE id = ?", (item_id,))
                exists = cursor.fetchone()

                if exists:
                    # 更新現有記錄
                    cursor.execute("""
                        UPDATE items
                        SET title = ?, content = ?, metadata = ?,
                            processed = ?, filter_result = ?
                        WHERE id = ?
                    """, (title, content, metadata, processed, filter_result, item_id))
                    updated_count += 1
                else:
                    # 插入新記錄
                    cursor.execute("""
                        INSERT INTO items (id, title, content, metadata, processed, filter_result)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (item_id, title, content, metadata, processed, filter_result))
                    saved_count += 1

            self.conn.commit()
            logger.info(f"成功儲存 {saved_count} 筆新記錄, 更新 {updated_count} 筆記錄")

        except Exception as e:
            self.conn.rollback()
            logger.error(f"儲存資料失敗: {e}")
            raise

    def get_processed_ids(self) -> Set[str]:
        """獲取已處理項目的 ID 集合

        Returns:
            已處理的項目 ID 集合
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id FROM items")
            ids = {row["id"] for row in cursor.fetchall()}
            logger.debug(f"從資料庫讀取 {len(ids)} 個已處理 ID")
            return ids

        except Exception as e:
            logger.error(f"獲取已處理 ID 失敗: {e}")
            return set()

    def get_item_by_id(self, item_id: str) -> Optional[Dict[str, Any]]:
        """根據 ID 獲取單個項目

        Args:
            item_id: 項目唯一識別碼

        Returns:
            項目資料字典，如果不存在則返回 None
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
            row = cursor.fetchone()

            if row:
                return {
                    "id": row["id"],
                    "title": row["title"],
                    "content": row["content"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    "processed": bool(row["processed"]),
                    "filter_result": json.loads(row["filter_result"]) if row["filter_result"] else None,
                    "created_at": row["created_at"],
                }
            return None

        except Exception as e:
            logger.error(f"獲取項目 {item_id} 失敗: {e}")
            return None

    def get_items_by_filter(
        self,
        processed: Optional[bool] = None,
        passed_filter: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """根據條件查詢項目

        Args:
            processed: 是否已處理（None 表示不篩選）
            passed_filter: 是否通過篩選（None 表示不篩選）
            limit: 返回記錄數上限
            offset: 偏移量

        Returns:
            符合條件的項目列表
        """
        try:
            cursor = self.conn.cursor()

            # 構建查詢條件
            conditions = []
            params = []

            if processed is not None:
                conditions.append("processed = ?")
                params.append(1 if processed else 0)

            if passed_filter is not None:
                # 需要解析 JSON 中的 passed 欄位
                conditions.append("json_extract(filter_result, '$.passed') = ?")
                params.append(1 if passed_filter else 0)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            query = f"""
                SELECT * FROM items
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()

            items = []
            for row in rows:
                items.append({
                    "id": row["id"],
                    "title": row["title"],
                    "content": row["content"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    "processed": bool(row["processed"]),
                    "filter_result": json.loads(row["filter_result"]) if row["filter_result"] else None,
                    "created_at": row["created_at"],
                })

            return items

        except Exception as e:
            logger.error(f"查詢項目失敗: {e}")
            return []

    def get_statistics(self) -> Dict[str, int]:
        """獲取資料庫統計資訊

        Returns:
            統計資訊字典
        """
        try:
            cursor = self.conn.cursor()

            stats = {}

            # 總項目數
            cursor.execute("SELECT COUNT(*) as count FROM items")
            stats["total"] = cursor.fetchone()["count"]

            # 已處理項目數
            cursor.execute("SELECT COUNT(*) as count FROM items WHERE processed = 1")
            stats["processed"] = cursor.fetchone()["count"]

            # 通過篩選的項目數
            cursor.execute("""
                SELECT COUNT(*) as count FROM items
                WHERE json_extract(filter_result, '$.passed') = 1
            """)
            stats["passed"] = cursor.fetchone()["count"]

            # 未通過篩選的項目數
            cursor.execute("""
                SELECT COUNT(*) as count FROM items
                WHERE processed = 1 AND json_extract(filter_result, '$.passed') = 0
            """)
            stats["failed"] = cursor.fetchone()["count"]

            return stats

        except Exception as e:
            logger.error(f"獲取統計資訊失敗: {e}")
            return {}

    def close(self) -> None:
        """關閉資料庫連接"""
        if self.conn:
            self.conn.close()
            logger.info("SQLite 資料庫連接已關閉")


# PostgreSQL 實作（佔位符，未來可擴展）
class PostgreSQLRepository(DatabaseRepository):
    """PostgreSQL 資料庫實作

    適用於生產環境和大規模部署。
    需要安裝 psycopg2 套件。
    """

    def __init__(self, config: Dict[str, Any]):
        """初始化 PostgreSQL 資料庫連接

        Args:
            config: 資料庫配置，必須包含 host, port, database, username, password
        """
        self.config = config
        self.conn = None
        logger.warning("PostgreSQL 實作尚未完成，建議使用 SQLite")

    def connect(self) -> None:
        """建立資料庫連接"""
        raise NotImplementedError("PostgreSQL 實作尚未完成")

    def save_items(self, items: List[Dict[str, Any]]) -> None:
        """批量儲存資料項目"""
        raise NotImplementedError("PostgreSQL 實作尚未完成")

    def get_processed_ids(self) -> Set[str]:
        """獲取已處理項目的 ID 集合"""
        raise NotImplementedError("PostgreSQL 實作尚未完成")

    def get_item_by_id(self, item_id: str) -> Optional[Dict[str, Any]]:
        """根據 ID 獲取單個項目"""
        raise NotImplementedError("PostgreSQL 實作尚未完成")

    def close(self) -> None:
        """關閉資料庫連接"""
        if self.conn:
            self.conn.close()


# 資料庫工廠函式
def create_database_repository(config: Dict[str, Any]) -> DatabaseRepository:
    """根據配置建立資料庫實例

    Args:
        config: 資料庫配置字典

    Returns:
        DatabaseRepository 實例

    Raises:
        ValueError: 當資料庫類型不支援時
    """
    db_type = config.get("type", "sqlite").lower()

    if db_type == "sqlite":
        return SQLiteRepository(config)
    elif db_type == "postgresql":
        return PostgreSQLRepository(config)
    else:
        raise ValueError(f"不支援的資料庫類型: {db_type}")
