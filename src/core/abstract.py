"""
抽象基礎類別定義

定義三個核心抽象類別：
1. DataSourceConnector - 資料源連接器
2. DataProcessor - 資料處理器
3. DatabaseRepository - 資料庫存取層
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Set, Optional


class DataSourceConnector(ABC):
    """資料源連接器抽象類別

    所有資料源連接器必須繼承此類別並實作相關方法。
    統一輸出格式確保後續處理的一致性。
    """

    def __init__(self, config: Dict[str, Any]):
        """初始化連接器

        Args:
            config: 該資料源的配置字典
        """
        self.config = config
        self.validate_config()

    @abstractmethod
    def validate_config(self) -> None:
        """驗證配置的有效性

        檢查必要的配置項目是否存在，不符合要求時拋出 ValueError。

        Raises:
            ValueError: 當配置缺少必要項目或格式不正確時
        """
        pass

    @abstractmethod
    def fetch_data(self) -> List[Dict[str, Any]]:
        """執行資料爬取

        Returns:
            統一格式的資料列表，每個 item 必須包含：
            - id (str): 唯一識別碼
            - title (str): 標題
            - content (str): 主要內容
            - metadata (dict): 其他元資料

        Example:
            [
                {
                    'id': 'arxiv-2024-00001',
                    'title': 'Paper Title',
                    'content': 'Abstract content...',
                    'metadata': {
                        'authors': ['Author 1', 'Author 2'],
                        'published': '2024-01-01T00:00:00',
                        'url': 'https://...'
                    }
                }
            ]
        """
        pass


class DataProcessor(ABC):
    """資料處理器抽象類別

    用於對爬取的資料進行後處理，如 LLM 篩選、情感分析、內容清洗等。
    """

    def __init__(self, config: Dict[str, Any]):
        """初始化處理器

        Args:
            config: 處理器配置字典
        """
        self.config = config

    @abstractmethod
    def process_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """處理單個資料項目

        Args:
            item: 待處理的資料項目（來自 DataSourceConnector）

        Returns:
            處理後的資料項目，必須包含原始欄位外加：
            - processed (bool): 是否已成功處理
            - filter_result (dict): 處理結果，包含：
                - passed (bool): 是否通過篩選
                - reason (str): 篩選理由或處理說明
                - model (str, optional): 使用的模型名稱
                - error (bool, optional): 是否發生錯誤

        Example:
            {
                'id': 'arxiv-2024-00001',
                'title': 'Paper Title',
                'content': 'Abstract content...',
                'metadata': {...},
                'processed': True,
                'filter_result': {
                    'passed': True,
                    'reason': 'Relevant to AI safety',
                    'model': 'llama3'
                }
            }
        """
        pass


class DatabaseRepository(ABC):
    """資料庫存取抽象類別

    提供統一的資料庫操作介面，支援不同的資料庫後端（SQLite, PostgreSQL 等）。
    """

    @abstractmethod
    def connect(self) -> None:
        """建立資料庫連接

        如果資料庫不存在，應自動建立資料庫和必要的表格。

        Raises:
            Exception: 當連接失敗時
        """
        pass

    @abstractmethod
    def save_items(self, items: List[Dict[str, Any]]) -> None:
        """批量儲存資料項目

        Args:
            items: 待儲存的資料項目列表

        Raises:
            Exception: 當儲存失敗時
        """
        pass

    @abstractmethod
    def get_processed_ids(self) -> Set[str]:
        """獲取已處理項目的 ID 集合

        用於去重，避免重複處理相同的資料。

        Returns:
            已處理的項目 ID 集合
        """
        pass

    @abstractmethod
    def get_item_by_id(self, item_id: str) -> Optional[Dict[str, Any]]:
        """根據 ID 獲取單個項目

        Args:
            item_id: 項目唯一識別碼

        Returns:
            項目資料字典，如果不存在則返回 None
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """關閉資料庫連接

        確保所有變更已提交，資源已釋放。
        """
        pass
