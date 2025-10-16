"""
日誌管理模組

提供統一的日誌配置，支援檔案輪轉和多種輸出格式。
參考 spam-blocker 的日誌設計，使用 RotatingFileHandler 避免日誌檔案過大。
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    max_bytes: int = 5 * 1024 * 1024,  # 5MB
    backup_count: int = 5,
    console_output: bool = True,
) -> None:
    """設定全域日誌配置

    Args:
        log_level: 日誌等級 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 日誌檔案路徑，如果為 None 則不寫入檔案
        max_bytes: 單個日誌檔案的最大大小（位元組）
        backup_count: 保留的歷史日誌檔案數量
        console_output: 是否同時輸出到控制台

    Example:
        >>> setup_logging(log_level="DEBUG", log_file="logs/app.log")
        >>> logger = logging.getLogger(__name__)
        >>> logger.info("Application started")
    """
    # 將字串等級轉換為 logging 常數
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # 定義日誌格式
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # 建立 handlers 列表
    handlers = []

    # 如果指定了日誌檔案，加入檔案 handler
    if log_file:
        # 確保日誌目錄存在
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        # 建立輪轉檔案 handler
        file_handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(
            logging.Formatter(log_format, datefmt=date_format)
        )
        handlers.append(file_handler)

    # 如果啟用控制台輸出，加入 console handler
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(
            logging.Formatter(log_format, datefmt=date_format)
        )
        handlers.append(console_handler)

    # 配置根 logger
    logging.basicConfig(
        level=numeric_level,
        format=log_format,
        datefmt=date_format,
        handlers=handlers,
        force=True,  # 覆蓋現有配置
    )

    # 記錄配置資訊
    logger = logging.getLogger(__name__)
    logger.info(f"日誌系統已初始化 - 等級: {log_level}")
    if log_file:
        logger.info(f"日誌檔案: {log_file} (最大 {max_bytes / 1024 / 1024:.1f}MB, 保留 {backup_count} 個備份)")


def get_logger(name: str) -> logging.Logger:
    """獲取指定名稱的 logger

    建議使用 __name__ 作為 logger 名稱，以便追蹤日誌來源。

    Args:
        name: Logger 名稱，通常使用 __name__

    Returns:
        配置好的 Logger 實例

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing started")
    """
    return logging.getLogger(name)


def set_log_level(logger_name: str, level: str) -> None:
    """動態調整特定 logger 的日誌等級

    Args:
        logger_name: Logger 名稱
        level: 新的日誌等級 (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Example:
        >>> set_log_level("src.workers.connectors", "DEBUG")
    """
    logger = logging.getLogger(logger_name)
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)
    logger.info(f"Logger '{logger_name}' 等級已調整為 {level}")


# 為第三方套件設定較高的日誌等級，避免過多輸出
def suppress_noisy_loggers() -> None:
    """抑制常見第三方套件的冗餘日誌

    將常見的第三方套件（如 urllib3, requests）的日誌等級設為 WARNING，
    避免在 DEBUG 模式下產生過多輸出。
    """
    noisy_loggers = [
        "urllib3",
        "requests",
        "httpx",
        "httpcore",
        "arxiv",
    ]

    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
