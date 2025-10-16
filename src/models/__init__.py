"""
Data Models Package

Export all Pydantic data models for the crawler system.
"""

from src.models.base import (
    DataItem,
    FilterResult,
    ValidationResult,
    ProcessingStats,
)
from src.models.arxiv import (
    ArxivAuthor,
    ArxivPaper,
    ArxivSearchConfig,
)

__all__ = [
    # Base models
    "DataItem",
    "FilterResult",
    "ValidationResult",
    "ProcessingStats",
    # Arxiv models
    "ArxivAuthor",
    "ArxivPaper",
    "ArxivSearchConfig",
]
