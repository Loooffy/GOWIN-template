"""
Arxiv 連接器

實作 Arxiv API 資料源連接器，用於爬取學術論文。
"""

import logging
from typing import List, Dict, Any
from datetime import datetime
import arxiv

from src.core.abstract import DataSourceConnector
from src.models.arxiv import ArxivPaper

logger = logging.getLogger(__name__)


class ArxivConnector(DataSourceConnector):
    """Arxiv API 連接器

    使用官方 arxiv Python 套件爬取論文資料。
    """

    def validate_config(self) -> None:
        """驗證配置的有效性

        必要欄位：
        - query: 搜尋查詢字串
        - max_results: 最大結果數
        """
        required_fields = ["query", "max_results"]
        for field in required_fields:
            if field not in self.config:
                raise ValueError(f"Arxiv 連接器配置缺少必要欄位: {field}")

        # 驗證 max_results 範圍
        max_results = self.config["max_results"]
        if not isinstance(max_results, int) or max_results <= 0 or max_results > 1000:
            raise ValueError(f"max_results 必須在 1-1000 之間，當前值: {max_results}")

        logger.info(f"Arxiv 連接器配置驗證通過 - 查詢: {self.config['query']}")

    def fetch_data(self) -> List[Dict[str, Any]]:
        """執行 Arxiv 論文爬取

        Returns:
            統一格式的論文資料列表
        """
        logger.info(f"開始爬取 Arxiv 論文 - 查詢: {self.config['query']}")

        try:
            # 建立 Arxiv 客戶端
            client = arxiv.Client()

            # 構建搜尋參數
            sort_by = self._get_sort_criterion()
            sort_order = self._get_sort_order()

            search = arxiv.Search(
                query=self.config["query"],
                max_results=self.config["max_results"],
                sort_by=sort_by,
                sort_order=sort_order,
            )

            # 執行搜尋
            results = []
            for paper in client.results(search):
                # 日期過濾
                if not self._check_date_filter(paper):
                    continue

                # 轉換為統一格式
                paper_data = self._convert_paper(paper)
                results.append(paper_data)

            logger.info(f"成功爬取 {len(results)} 篇 Arxiv 論文")
            return results

        except Exception as e:
            logger.error(f"爬取 Arxiv 論文失敗: {e}", exc_info=True)
            raise

    def _get_sort_criterion(self) -> arxiv.SortCriterion:
        """獲取排序依據

        Returns:
            arxiv.SortCriterion 枚舉值
        """
        sort_by = self.config.get("sort_by", "submittedDate")

        sort_map = {
            "relevance": arxiv.SortCriterion.Relevance,
            "lastUpdatedDate": arxiv.SortCriterion.LastUpdatedDate,
            "submittedDate": arxiv.SortCriterion.SubmittedDate,
        }

        return sort_map.get(sort_by, arxiv.SortCriterion.SubmittedDate)

    def _get_sort_order(self) -> arxiv.SortOrder:
        """獲取排序順序

        Returns:
            arxiv.SortOrder 枚舉值
        """
        sort_order = self.config.get("sort_order", "descending")

        if sort_order.lower() == "ascending":
            return arxiv.SortOrder.Ascending
        else:
            return arxiv.SortOrder.Descending

    def _check_date_filter(self, paper: arxiv.Result) -> bool:
        """檢查論文是否符合日期過濾條件

        Args:
            paper: Arxiv 論文結果

        Returns:
            True 表示符合條件，False 表示不符合
        """
        # 移除時區資訊以便比較
        paper_date = paper.published.replace(tzinfo=None)

        # 檢查開始日期
        if "start_date" in self.config:
            start_date = datetime.fromisoformat(self.config["start_date"])
            if paper_date < start_date:
                logger.debug(f"論文 {paper.entry_id} 早於開始日期，跳過")
                return False

        # 檢查結束日期
        if "end_date" in self.config:
            end_date = datetime.fromisoformat(self.config["end_date"])
            if paper_date > end_date:
                logger.debug(f"論文 {paper.entry_id} 晚於結束日期，跳過")
                return False

        return True

    def _convert_paper(self, paper: arxiv.Result) -> Dict[str, Any]:
        """將 Arxiv 論文轉換為統一格式

        Args:
            paper: Arxiv 論文結果

        Returns:
            統一格式的資料字典
        """
        return {
            "id": paper.entry_id,
            "title": paper.title,
            "content": paper.summary,
            "metadata": {
                "authors": [author.name for author in paper.authors],
                "categories": paper.categories,
                "primary_category": paper.primary_category,
                "published": paper.published.isoformat(),
                "updated": paper.updated.isoformat() if paper.updated else None,
                "pdf_url": paper.pdf_url,
                "comment": paper.comment,
                "journal_ref": paper.journal_ref,
                "doi": paper.doi,
            }
        }
