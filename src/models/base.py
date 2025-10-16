"""
基礎資料模型

使用 Pydantic 定義基礎資料模型，確保資料類型安全和驗證。
"""

from typing import Any, Dict, Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class DataItem(BaseModel):
    """統一的資料項目模型

    所有 DataSourceConnector 返回的資料都應符合此格式。
    """

    id: str = Field(..., description="唯一識別碼")
    title: str = Field(..., description="標題")
    content: str = Field(..., description="主要內容")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="額外元資料")

    # 處理相關欄位（由 DataProcessor 添加）
    processed: Optional[bool] = Field(default=None, description="是否已處理")
    filter_result: Optional[Dict[str, Any]] = Field(default=None, description="篩選結果")

    # 時間戳記（由資料庫層添加）
    created_at: Optional[datetime] = Field(default=None, description="建立時間")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "arxiv-2024-00001",
                "title": "Sample Research Paper",
                "content": "This paper discusses...",
                "metadata": {
                    "authors": ["Author One", "Author Two"],
                    "published": "2024-01-01T00:00:00",
                    "url": "https://arxiv.org/abs/2024.00001"
                },
                "processed": True,
                "filter_result": {
                    "passed": True,
                    "reason": "Relevant to AI safety",
                    "model": "llama3"
                }
            }
        }


class FilterResult(BaseModel):
    """篩選結果模型

    DataProcessor 應返回此格式的 filter_result。
    """

    passed: bool = Field(..., description="是否通過篩選")
    reason: str = Field(..., description="篩選理由或說明")
    model: Optional[str] = Field(default=None, description="使用的模型名稱")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="信心分數")
    error: Optional[bool] = Field(default=False, description="處理時是否發生錯誤")

    class Config:
        json_schema_extra = {
            "example": {
                "passed": True,
                "reason": "Paper is relevant to large language model safety",
                "model": "llama3",
                "confidence": 0.85,
                "error": False
            }
        }


class ValidationResult(BaseModel):
    """LLM 驗證結果模型

    用於 Ollama 或其他 LLM 的結構化輸出。
    參考 spam-blocker 的 ValidationResult 設計。
    """

    valid: bool = Field(..., description="驗證結果")
    reason: str = Field(..., description="驗證理由")

    @field_validator('reason')
    @classmethod
    def reason_not_empty(cls, v: str) -> str:
        """確保理由不為空"""
        if not v or not v.strip():
            raise ValueError("驗證理由不能為空")
        return v.strip()

    class Config:
        json_schema_extra = {
            "example": {
                "valid": True,
                "reason": "This research paper is directly related to AI safety concerns."
            }
        }


class ProcessingStats(BaseModel):
    """處理統計模型

    用於追蹤處理進度和統計資訊。
    """

    total_fetched: int = Field(default=0, description="總共抓取的項目數")
    total_processed: int = Field(default=0, description="總共處理的項目數")
    passed_filter: int = Field(default=0, description="通過篩選的項目數")
    failed_filter: int = Field(default=0, description="未通過篩選的項目數")
    errors: int = Field(default=0, description="處理錯誤數")
    processing_time: Optional[float] = Field(default=None, description="處理時間（秒）")

    def add_result(self, passed: bool, error: bool = False) -> None:
        """添加處理結果

        Args:
            passed: 是否通過篩選
            error: 是否發生錯誤
        """
        self.total_processed += 1
        if error:
            self.errors += 1
        elif passed:
            self.passed_filter += 1
        else:
            self.failed_filter += 1

    def get_summary(self) -> str:
        """獲取統計摘要

        Returns:
            統計摘要字串
        """
        return (
            f"總抓取: {self.total_fetched}, "
            f"總處理: {self.total_processed}, "
            f"通過: {self.passed_filter}, "
            f"未通過: {self.failed_filter}, "
            f"錯誤: {self.errors}"
        )

    class Config:
        json_schema_extra = {
            "example": {
                "total_fetched": 100,
                "total_processed": 95,
                "passed_filter": 30,
                "failed_filter": 63,
                "errors": 2,
                "processing_time": 125.5
            }
        }
