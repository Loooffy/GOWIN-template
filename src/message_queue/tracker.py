"""
Redis 狀態追蹤器

使用 Redis 追蹤已處理的記錄 ID，實現高效的去重功能。
參考 spam-blocker 的 ProcessedRecordTracker 設計。
"""

import logging
from typing import Set, Optional
import redis

logger = logging.getLogger(__name__)


class ProcessedRecordTracker:
    """已處理記錄追蹤器

    使用 Redis SET 資料結構儲存已處理的記錄 ID，
    提供 O(1) 的查詢效能。
    """

    def __init__(self, redis_url: str, namespace: str = "crawler"):
        """初始化追蹤器

        Args:
            redis_url: Redis 連接 URL (例如: redis://localhost:6379/0)
            namespace: 命名空間，用於區分不同的資料源
        """
        self.redis_url = redis_url
        self.namespace = namespace

        # Redis key 定義
        self.processed_set_key = f"{namespace}:processed_ids"
        self.last_id_key = f"{namespace}:last_processed_id"

        # Redis 連接
        self.redis_client: Optional[redis.Redis] = None

        # 嘗試連接
        self._connect()

    def _connect(self) -> None:
        """建立 Redis 連接"""
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,  # 自動解碼為字串
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            # 測試連接
            self.redis_client.ping()
            logger.info(f"成功連接到 Redis: {self.redis_url}")

        except redis.ConnectionError as e:
            logger.error(f"連接 Redis 失敗: {e}")
            logger.warning("將在不使用 Redis 追蹤的情況下繼續執行")
            self.redis_client = None

        except Exception as e:
            logger.error(f"Redis 初始化失敗: {e}")
            self.redis_client = None

    def is_processed(self, record_id: str) -> bool:
        """檢查記錄是否已處理

        Args:
            record_id: 記錄唯一識別碼

        Returns:
            True 表示已處理，False 表示未處理
        """
        if not self.redis_client:
            return False

        try:
            return self.redis_client.sismember(self.processed_set_key, record_id)

        except Exception as e:
            logger.error(f"檢查記錄狀態失敗 ({record_id}): {e}")
            return False

    def mark_as_processed(self, record_id: str) -> bool:
        """標記記錄為已處理

        Args:
            record_id: 記錄唯一識別碼

        Returns:
            True 表示標記成功，False 表示失敗
        """
        if not self.redis_client:
            return False

        try:
            self.redis_client.sadd(self.processed_set_key, record_id)
            logger.debug(f"已標記為已處理: {record_id}")
            return True

        except Exception as e:
            logger.error(f"標記記錄失敗 ({record_id}): {e}")
            return False

    def get_processed_ids(self) -> Set[str]:
        """獲取所有已處理的記錄 ID

        Returns:
            已處理記錄 ID 的集合
        """
        if not self.redis_client:
            return set()

        try:
            ids = self.redis_client.smembers(self.processed_set_key)
            logger.debug(f"從 Redis 讀取 {len(ids)} 個已處理 ID")
            return ids

        except Exception as e:
            logger.error(f"獲取已處理 ID 失敗: {e}")
            return set()

    def get_processed_count(self) -> int:
        """獲取已處理記錄的數量

        Returns:
            已處理記錄數
        """
        if not self.redis_client:
            return 0

        try:
            return self.redis_client.scard(self.processed_set_key)

        except Exception as e:
            logger.error(f"獲取已處理數量失敗: {e}")
            return 0

    def set_last_processed_id(self, record_id: str) -> bool:
        """設定最後處理的記錄 ID

        用於追蹤處理進度，支援增量更新。

        Args:
            record_id: 記錄唯一識別碼

        Returns:
            True 表示設定成功，False 表示失敗
        """
        if not self.redis_client:
            return False

        try:
            self.redis_client.set(self.last_id_key, record_id)
            logger.debug(f"已設定最後處理 ID: {record_id}")
            return True

        except Exception as e:
            logger.error(f"設定最後處理 ID 失敗: {e}")
            return False

    def get_last_processed_id(self) -> Optional[str]:
        """獲取最後處理的記錄 ID

        Returns:
            最後處理的記錄 ID，如果不存在則返回 None
        """
        if not self.redis_client:
            return None

        try:
            return self.redis_client.get(self.last_id_key)

        except Exception as e:
            logger.error(f"獲取最後處理 ID 失敗: {e}")
            return None

    def clear_all(self) -> bool:
        """清除所有追蹤記錄

        警告：此操作會刪除所有已處理記錄的追蹤資料！

        Returns:
            True 表示清除成功，False 表示失敗
        """
        if not self.redis_client:
            return False

        try:
            self.redis_client.delete(self.processed_set_key)
            self.redis_client.delete(self.last_id_key)
            logger.warning(f"已清除命名空間 '{self.namespace}' 的所有追蹤資料")
            return True

        except Exception as e:
            logger.error(f"清除追蹤資料失敗: {e}")
            return False

    def close(self) -> None:
        """關閉 Redis 連接"""
        if self.redis_client:
            self.redis_client.close()
            logger.info("Redis 連接已關閉")
