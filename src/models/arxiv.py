"""
Arxiv 資料模型

定義 Arxiv 論文的特定資料結構。
"""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl


class ArxivAuthor(BaseModel):
    """Arxiv 作者模型"""

    name: str = Field(..., description="作者姓名")
    affiliation: Optional[str] = Field(default=None, description="所屬機構")


class ArxivPaper(BaseModel):
    """Arxiv 論文模型

    擴展基礎 DataItem，添加 Arxiv 特定欄位。
    """

    entry_id: str = Field(..., description="Arxiv 論文 ID")
    title: str = Field(..., description="論文標題")
    summary: str = Field(..., description="論文摘要")
    authors: List[str] = Field(default_factory=list, description="作者列表")
    categories: List[str] = Field(default_factory=list, description="論文分類")
    published: datetime = Field(..., description="發表日期")
    updated: Optional[datetime] = Field(default=None, description="更新日期")
    pdf_url: str = Field(..., description="PDF 下載連結")
    primary_category: Optional[str] = Field(default=None, description="主要分類")
    comment: Optional[str] = Field(default=None, description="論文備註")
    journal_ref: Optional[str] = Field(default=None, description="期刊參考")
    doi: Optional[str] = Field(default=None, description="DOI")

    def to_data_item(self) -> dict:
        """轉換為標準 DataItem 格式

        Returns:
            符合 DataItem 格式的字典
        """
        return {
            "id": self.entry_id,
            "title": self.title,
            "content": self.summary,
            "metadata": {
                "authors": self.authors,
                "categories": self.categories,
                "published": self.published.isoformat(),
                "updated": self.updated.isoformat() if self.updated else None,
                "pdf_url": self.pdf_url,
                "primary_category": self.primary_category,
                "comment": self.comment,
                "journal_ref": self.journal_ref,
                "doi": self.doi,
            }
        }

    class Config:
        json_schema_extra = {
            "example": {
                "entry_id": "http://arxiv.org/abs/2024.00001v1",
                "title": "Advances in Large Language Model Safety",
                "summary": "This paper presents new approaches to improving the safety...",
                "authors": ["Alice Smith", "Bob Johnson"],
                "categories": ["cs.AI", "cs.LG", "cs.CL"],
                "published": "2024-01-15T10:30:00",
                "updated": "2024-01-20T15:45:00",
                "pdf_url": "http://arxiv.org/pdf/2024.00001v1",
                "primary_category": "cs.AI",
                "comment": "10 pages, 3 figures",
                "journal_ref": None,
                "doi": None
            }
        }


class ArxivSearchConfig(BaseModel):
    """Arxiv 搜尋配置模型

    用於驗證 Arxiv 連接器的配置。
    """

    query: str = Field(..., description="搜尋查詢字串", min_length=1)
    max_results: int = Field(default=100, description="最大結果數", gt=0, le=1000)
    sort_by: str = Field(default="submittedDate", description="排序依據")
    sort_order: str = Field(default="descending", description="排序順序")
    start_date: Optional[str] = Field(default=None, description="開始日期 (ISO 格式)")
    end_date: Optional[str] = Field(default=None, description="結束日期 (ISO 格式)")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "cat:cs.AI OR cat:cs.LG",
                "max_results": 100,
                "sort_by": "submittedDate",
                "sort_order": "descending",
                "start_date": "2024-01-01",
                "end_date": "2024-12-31"
            }
        }
