"""
爬蟲核心控制器

協調所有模組，執行完整的爬取、處理、儲存流程。
參考 spam-blocker 的工廠模式和依賴注入設計。
"""

import logging
import importlib
from typing import Dict, Any, Optional
from datetime import datetime
import time

from src.core.abstract import DataSourceConnector, DataProcessor, DatabaseRepository
from src.core.database import create_database_repository
from src.core.ollama_client import get_ollama_client
from src.message_queue.tracker import ProcessedRecordTracker
from src.models.base import ProcessingStats

logger = logging.getLogger(__name__)


class CrawlerController:
    """爬蟲核心控制器

    負責：
    1. 驗證 Ollama 服務可用性（必須）
    2. 動態載入連接器和處理器類別
    3. 協調資料爬取、處理、儲存流程
    4. 管理資料庫連接和可選的 Redis 追蹤
    5. 追蹤處理統計資訊
    """

    def __init__(self, config: Dict[str, Any]):
        """初始化控制器

        Args:
            config: 完整的配置字典
        """
        self.config = config
        self.db_repo: Optional[DatabaseRepository] = None
        self.redis_tracker: Optional[ProcessedRecordTracker] = None

    def _init_database(self) -> None:
        """初始化資料庫連接"""
        if self.db_repo is not None:
            return

        logger.info("初始化資料庫連接...")
        db_config = self.config.get("database", {})
        self.db_repo = create_database_repository(db_config)
        self.db_repo.connect()

    def _check_ollama_availability(self) -> None:
        """檢查 Ollama 服務是否可用（必要檢查）
        
        Raises:
            RuntimeError: 當 Ollama 服務不可用時
        """
        logger.info("檢查 Ollama 服務連接...")
        ollama_client = get_ollama_client()
        
        if not ollama_client.check_connection():
            raise RuntimeError(
                "Ollama 服務不可用！LLM 篩選是必要功能，請確保：\n"
                "1. Ollama 已安裝並運行 (curl https://ollama.ai/install.sh | sh)\n"
                "2. 模型已下載 (ollama pull llama3)\n"
                f"3. API URL 正確配置: {ollama_client.api_url}"
            )
        
        logger.info("✓ Ollama 服務連接正常")

    def _init_redis_tracker(self, namespace: str) -> ProcessedRecordTracker:
        """初始化 Redis 追蹤器（可選功能）
        
        如果 Redis 不可用，追蹤器會自動降級使用資料庫去重

        Args:
            namespace: 資料源命名空間

        Returns:
            ProcessedRecordTracker 實例
        """
        redis_config = self.config.get("redis", {})
        redis_url = redis_config.get("url", "redis://localhost:6379/0")

        return ProcessedRecordTracker(redis_url=redis_url, namespace=namespace)

    def _load_connector_class(self, class_name: str) -> type:
        """動態載入連接器類別

        Args:
            class_name: 類別名稱 (例如: ArxivConnector)

        Returns:
            連接器類別

        Raises:
            ImportError: 當無法載入類別時
        """
        # 將類別名稱轉換為模組路徑
        # ArxivConnector -> src.workers.connectors.arxiv
        module_name = class_name.replace("Connector", "").lower()
        module_path = f"src.workers.connectors.{module_name}"

        try:
            module = importlib.import_module(module_path)
            connector_class = getattr(module, class_name)
            logger.debug(f"成功載入連接器: {class_name}")
            return connector_class

        except (ImportError, AttributeError) as e:
            logger.error(f"無法載入連接器 {class_name}: {e}")
            raise ImportError(f"連接器 {class_name} 不存在或無法載入")

    def _load_processor_class(self, class_name: str) -> type:
        """動態載入處理器類別

        Args:
            class_name: 類別名稱 (例如: OllamaFilterProcessor)

        Returns:
            處理器類別

        Raises:
            ImportError: 當無法載入類別時
        """
        # 將類別名稱轉換為模組路徑
        # OllamaFilterProcessor -> src.workers.processors.ollama_filter
        module_name = class_name.replace("Processor", "").lower()
        # 處理駝峰命名 (OllamaFilter -> ollama_filter)
        import re
        module_name = re.sub(r'(?<!^)(?=[A-Z])', '_', module_name).lower()
        module_path = f"src.workers.processors.{module_name}"

        try:
            module = importlib.import_module(module_path)
            processor_class = getattr(module, class_name)
            logger.debug(f"成功載入處理器: {class_name}")
            return processor_class

        except (ImportError, AttributeError) as e:
            logger.error(f"無法載入處理器 {class_name}: {e}")
            raise ImportError(f"處理器 {class_name} 不存在或無法載入")

    def run_source(self, source_config: Dict[str, Any]) -> ProcessingStats:
        """執行單個資料源的完整流程

        流程：
        1. 初始化 Redis 追蹤器（可選）
        2. 載入並初始化連接器
        3. 爬取資料
        4. 使用 Redis/資料庫過濾已處理項目
        5. 如果配置了處理器，執行 LLM 篩選（必須）
        6. 儲存到資料庫
        7. 更新 Redis 追蹤狀態（如可用）

        Args:
            source_config: 資料源配置字典

        Returns:
            ProcessingStats 處理統計資訊
        """
        source_name = source_config.get("name", "unknown")
        logger.info(f"=" * 60)
        logger.info(f"開始處理資料源: {source_name}")
        logger.info(f"=" * 60)

        stats = ProcessingStats()
        start_time = time.time()

        try:
            # 1. 初始化 Redis 追蹤器
            tracker = self._init_redis_tracker(namespace=source_name)

            # 2. 載入並初始化連接器
            connector_class = self._load_connector_class(source_config["connector_class"])
            connector: DataSourceConnector = connector_class(source_config["config"])

            # 3. 爬取資料
            logger.info(f"正在爬取資料...")
            raw_data = connector.fetch_data()
            stats.total_fetched = len(raw_data)
            logger.info(f"成功爬取 {stats.total_fetched} 筆資料")

            if stats.total_fetched == 0:
                logger.warning(f"資料源 {source_name} 未爬取到任何資料")
                return stats

            # 4. 過濾已處理的項目
            logger.info("正在過濾已處理項目...")
            processed_ids = self._get_processed_ids(tracker)
            new_items = [item for item in raw_data if item["id"] not in processed_ids]
            logger.info(f"新增項目: {len(new_items)} 筆 (已處理: {len(processed_ids)} 筆)")

            if not new_items:
                logger.info(f"資料源 {source_name} 無新增項目")
                return stats

            # 5. 執行後處理（如果配置了處理器）
            if source_config.get("processor_class"):
                logger.info(f"正在執行後處理...")
                new_items = self._process_items(
                    source_config["processor_class"],
                    source_config.get("processor_config", {}),
                    new_items,
                    stats,
                )

            # 6. 儲存到資料庫
            logger.info(f"正在儲存 {len(new_items)} 筆資料到資料庫...")
            self.db_repo.save_items(new_items)

            # 7. 更新 Redis 追蹤狀態
            logger.info("更新 Redis 追蹤狀態...")
            for item in new_items:
                tracker.mark_as_processed(item["id"])

            # 更新最後處理的 ID
            if new_items:
                tracker.set_last_processed_id(new_items[-1]["id"])

            # 計算處理時間
            stats.processing_time = time.time() - start_time

            logger.info(f"資料源 {source_name} 處理完成")
            logger.info(f"統計: {stats.get_summary()}")
            logger.info(f"處理時間: {stats.processing_time:.2f} 秒")

            return stats

        except Exception as e:
            logger.error(f"資料源 {source_name} 處理失敗: {e}", exc_info=True)
            stats.processing_time = time.time() - start_time
            raise

    def _get_processed_ids(self, tracker: ProcessedRecordTracker) -> set:
        """獲取已處理的 ID 集合

        優先從 Redis 獲取，如果 Redis 不可用則從資料庫獲取。

        Args:
            tracker: Redis 追蹤器

        Returns:
            已處理 ID 的集合
        """
        # 嘗試從 Redis 獲取
        redis_ids = tracker.get_processed_ids()
        if redis_ids:
            logger.debug(f"從 Redis 讀取 {len(redis_ids)} 個已處理 ID")
            return redis_ids

        # Redis 不可用，從資料庫獲取
        logger.warning("Redis 不可用，從資料庫獲取已處理 ID")
        db_ids = self.db_repo.get_processed_ids()
        logger.debug(f"從資料庫讀取 {len(db_ids)} 個已處理 ID")
        return db_ids

    def _process_items(
        self,
        processor_class_name: str,
        processor_config: Dict[str, Any],
        items: list,
        stats: ProcessingStats,
    ) -> list:
        """執行項目後處理

        Args:
            processor_class_name: 處理器類別名稱
            processor_config: 處理器配置
            items: 待處理項目列表
            stats: 統計資訊物件

        Returns:
            處理後的項目列表
        """
        processor_class = self._load_processor_class(processor_class_name)
        processor: DataProcessor = processor_class(processor_config)

        processed_items = []
        for idx, item in enumerate(items, 1):
            logger.debug(f"處理項目 {idx}/{len(items)}: {item.get('id')}")

            try:
                processed_item = processor.process_item(item)
                processed_items.append(processed_item)

                # 更新統計
                filter_result = processed_item.get("filter_result", {})
                passed = filter_result.get("passed", False)
                error = filter_result.get("error", False)
                stats.add_result(passed=passed, error=error)

            except Exception as e:
                logger.error(f"處理項目 {item.get('id')} 失敗: {e}")
                # 標記為處理失敗但仍保留
                item["processed"] = False
                item["filter_result"] = {
                    "passed": False,
                    "reason": f"處理異常: {str(e)}",
                    "error": True,
                }
                processed_items.append(item)
                stats.add_result(passed=False, error=True)

        return processed_items

    def run_all(self) -> Dict[str, ProcessingStats]:
        """執行所有已啟用的資料源

        Returns:
            各資料源的處理統計資訊字典
        """
        logger.info("=" * 60)
        logger.info("爬蟲服務啟動")
        logger.info("=" * 60)

        # 檢查 Ollama 服務（必須）
        self._check_ollama_availability()

        # 初始化資料庫
        self._init_database()

        all_stats = {}

        try:
            sources = self.config.get("sources", [])
            enabled_sources = [s for s in sources if s.get("enabled", True)]

            logger.info(f"共有 {len(enabled_sources)} 個已啟用的資料源")

            for source in enabled_sources:
                source_name = source.get("name", "unknown")
                try:
                    stats = self.run_source(source)
                    all_stats[source_name] = stats

                except Exception as e:
                    logger.error(f"資料源 {source_name} 執行失敗: {e}")
                    all_stats[source_name] = ProcessingStats()
                    continue

            # 輸出總體統計
            self._print_summary(all_stats)

            return all_stats

        finally:
            # 清理資源
            if self.db_repo:
                self.db_repo.close()

            logger.info("=" * 60)
            logger.info("爬蟲服務結束")
            logger.info("=" * 60)

    def _print_summary(self, all_stats: Dict[str, ProcessingStats]) -> None:
        """輸出總體統計摘要

        Args:
            all_stats: 各資料源的統計資訊
        """
        logger.info("")
        logger.info("=" * 60)
        logger.info("處理統計摘要")
        logger.info("=" * 60)

        for source_name, stats in all_stats.items():
            logger.info(f"\n資料源: {source_name}")
            logger.info(f"  {stats.get_summary()}")
            if stats.processing_time:
                logger.info(f"  處理時間: {stats.processing_time:.2f} 秒")

        # 總計
        total_fetched = sum(s.total_fetched for s in all_stats.values())
        total_processed = sum(s.total_processed for s in all_stats.values())
        total_passed = sum(s.passed_filter for s in all_stats.values())
        total_failed = sum(s.failed_filter for s in all_stats.values())
        total_errors = sum(s.errors for s in all_stats.values())

        logger.info(f"\n總計:")
        logger.info(f"  總抓取: {total_fetched}, 總處理: {total_processed}")
        logger.info(f"  通過: {total_passed}, 未通過: {total_failed}, 錯誤: {total_errors}")
        logger.info("=" * 60)
