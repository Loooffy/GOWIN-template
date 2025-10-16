"""
Ollama 篩選處理器

使用 Ollama LLM 進行論文相關性篩選。
"""

import logging
from typing import Dict, Any

from src.core.abstract import DataProcessor
from src.core.ollama_client import get_ollama_client
from src.models.base import FilterResult

logger = logging.getLogger(__name__)


class OllamaFilterProcessor(DataProcessor):
    """Ollama LLM 篩選處理器

    使用本地 LLM 判斷內容是否符合特定主題或標準。
    """

    def __init__(self, config: Dict[str, Any]):
        """初始化處理器

        Args:
            config: 處理器配置，應包含 filter_prompt
        """
        super().__init__(config)

        # 獲取 Ollama 客戶端
        self.ollama_client = get_ollama_client()

        # 驗證配置
        if "filter_prompt" not in config:
            logger.warning("處理器配置缺少 'filter_prompt'，將使用預設提示詞")

        self.filter_prompt = config.get(
            "filter_prompt",
            "請判斷這篇內容是否相關。只回答 YES 或 NO，並簡述理由。"
        )

        logger.info("Ollama 篩選處理器已初始化")

    def process_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """使用 LLM 判斷項目相關性

        Args:
            item: 待處理的資料項目

        Returns:
            處理後的資料項目，包含 filter_result
        """
        item_id = item.get("id", "unknown")
        title = item.get("title", "")
        content = item.get("content", "")

        logger.debug(f"開始處理項目: {item_id}")

        try:
            # 構建完整提示詞
            full_prompt = f"""{self.filter_prompt}

標題: {title}
內容: {content[:1000]}...
"""  # 限制內容長度以避免超過 token 限制

            # 呼叫 Ollama 進行判斷
            validation_result = self.ollama_client.get_validation_result(full_prompt)

            # 構建 filter_result
            filter_result = FilterResult(
                passed=validation_result.valid,
                reason=validation_result.reason,
                model=self.ollama_client.model,
                error=False,
            )

            # 更新項目
            item["processed"] = True
            item["filter_result"] = filter_result.model_dump()

            status = "通過" if filter_result.passed else "未通過"
            logger.info(f"項目 {item_id} 篩選{status}: {filter_result.reason[:50]}...")

            return item

        except Exception as e:
            logger.error(f"處理項目 {item_id} 時發生錯誤: {e}", exc_info=True)

            # 標記為處理失敗
            item["processed"] = False
            item["filter_result"] = FilterResult(
                passed=False,
                reason=f"處理錯誤: {str(e)}",
                model=self.ollama_client.model,
                error=True,
            ).model_dump()

            return item
