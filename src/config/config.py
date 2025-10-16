"""
配置管理模組

負責載入和驗證 YAML 配置檔案以及環境變數。
提供統一的配置存取介面。
"""

import os
import yaml
from typing import Any, Dict, Optional
from pathlib import Path


# 全域配置快取
_config_cache: Optional[Dict[str, Any]] = None


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """載入配置檔案

    從 YAML 檔案載入配置，並使用環境變數覆蓋特定設定。
    配置會被快取，避免重複讀取檔案。

    Args:
        config_path: YAML 配置檔案路徑

    Returns:
        配置字典

    Raises:
        FileNotFoundError: 當配置檔案不存在時
        yaml.YAMLError: 當 YAML 格式錯誤時
        ValueError: 當配置驗證失敗時

    Example:
        >>> config = load_config("config.yaml")
        >>> print(config['database']['type'])
        'sqlite'
    """
    global _config_cache

    # 如果已快取且路徑相同，直接返回
    if _config_cache is not None:
        return _config_cache

    # 檢查檔案是否存在
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置檔案不存在: {config_path}")

    # 載入 YAML 檔案
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if config is None:
        raise ValueError(f"配置檔案為空: {config_path}")

    # 使用環境變數覆蓋配置
    config = _override_with_env(config)

    # 驗證配置結構
    _validate_config(config)

    # 快取配置
    _config_cache = config

    return config


def _override_with_env(config: Dict[str, Any]) -> Dict[str, Any]:
    """使用環境變數覆蓋配置

    支援的環境變數：
    - DATABASE_TYPE: 資料庫類型
    - DATABASE_PATH: SQLite 資料庫路徑
    - REDIS_URL: Redis 連接 URL
    - OLLAMA_URL: Ollama API URL
    - OLLAMA_MODEL: Ollama 模型名稱
    - LOG_LEVEL: 日誌等級

    Args:
        config: 原始配置字典

    Returns:
        覆蓋後的配置字典
    """
    # 資料庫配置
    if os.getenv("DATABASE_TYPE"):
        config.setdefault("database", {})["type"] = os.getenv("DATABASE_TYPE")
    if os.getenv("DATABASE_PATH"):
        config.setdefault("database", {})["path"] = os.getenv("DATABASE_PATH")
    if os.getenv("DATABASE_HOST"):
        config.setdefault("database", {})["host"] = os.getenv("DATABASE_HOST")
    if os.getenv("DATABASE_PORT"):
        config.setdefault("database", {})["port"] = int(os.getenv("DATABASE_PORT"))
    if os.getenv("DATABASE_NAME"):
        config.setdefault("database", {})["database"] = os.getenv("DATABASE_NAME")
    if os.getenv("DATABASE_USER"):
        config.setdefault("database", {})["username"] = os.getenv("DATABASE_USER")
    if os.getenv("DATABASE_PASSWORD"):
        config.setdefault("database", {})["password"] = os.getenv("DATABASE_PASSWORD")

    # Redis 配置
    if os.getenv("REDIS_URL"):
        config.setdefault("redis", {})["url"] = os.getenv("REDIS_URL")

    # Ollama 配置
    if os.getenv("OLLAMA_URL"):
        config.setdefault("ollama", {})["api_url"] = os.getenv("OLLAMA_URL")
    if os.getenv("OLLAMA_MODEL"):
        config.setdefault("ollama", {})["model"] = os.getenv("OLLAMA_MODEL")
    if os.getenv("OLLAMA_TIMEOUT"):
        config.setdefault("ollama", {})["timeout"] = int(os.getenv("OLLAMA_TIMEOUT"))

    # 日誌配置
    if os.getenv("LOG_LEVEL"):
        config.setdefault("logging", {})["level"] = os.getenv("LOG_LEVEL")
    if os.getenv("LOG_FILE"):
        config.setdefault("logging", {})["file"] = os.getenv("LOG_FILE")

    return config


def _validate_config(config: Dict[str, Any]) -> None:
    """驗證配置的有效性

    Args:
        config: 待驗證的配置字典

    Raises:
        ValueError: 當配置缺少必要項目或格式不正確時
    """
    # 驗證資料庫配置
    if "database" not in config:
        raise ValueError("配置缺少 'database' 區塊")

    db_config = config["database"]
    if "type" not in db_config:
        raise ValueError("資料庫配置缺少 'type' 欄位")

    db_type = db_config["type"].lower()
    if db_type not in ["sqlite", "postgresql", "mysql"]:
        raise ValueError(f"不支援的資料庫類型: {db_type}")

    # SQLite 需要 path
    if db_type == "sqlite" and "path" not in db_config:
        raise ValueError("SQLite 資料庫配置缺少 'path' 欄位")

    # PostgreSQL/MySQL 需要連接資訊
    if db_type in ["postgresql", "mysql"]:
        required_fields = ["host", "port", "database", "username", "password"]
        missing = [f for f in required_fields if f not in db_config]
        if missing:
            raise ValueError(f"{db_type.upper()} 資料庫配置缺少必要欄位: {', '.join(missing)}")

    # 驗證 Ollama 配置（必須）
    if "ollama" not in config:
        raise ValueError("配置缺少 'ollama' 區塊（LLM 篩選是必要功能）")
    
    ollama_config = config["ollama"]
    if "api_url" not in ollama_config:
        raise ValueError("Ollama 配置缺少 'api_url' 欄位")
    if "model" not in ollama_config:
        raise ValueError("Ollama 配置缺少 'model' 欄位")

    # 驗證日誌配置
    if "logging" in config:
        log_config = config["logging"]
        if "level" in log_config:
            valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            if log_config["level"].upper() not in valid_levels:
                raise ValueError(f"無效的日誌等級: {log_config['level']}")

    # 驗證資料源配置
    if "sources" not in config or not config["sources"]:
        raise ValueError("配置缺少 'sources' 區塊或資料源列表為空")

    for idx, source in enumerate(config["sources"]):
        if "name" not in source:
            raise ValueError(f"資料源 #{idx} 缺少 'name' 欄位")
        if "connector_class" not in source:
            raise ValueError(f"資料源 '{source.get('name')}' 缺少 'connector_class' 欄位")
        if "config" not in source:
            raise ValueError(f"資料源 '{source.get('name')}' 缺少 'config' 欄位")


def get_config() -> Dict[str, Any]:
    """獲取當前快取的配置

    Returns:
        配置字典

    Raises:
        RuntimeError: 當配置尚未載入時
    """
    if _config_cache is None:
        raise RuntimeError("配置尚未載入，請先呼叫 load_config()")
    return _config_cache


def reload_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """重新載入配置檔案

    清除快取並重新載入配置。

    Args:
        config_path: YAML 配置檔案路徑

    Returns:
        新的配置字典
    """
    global _config_cache
    _config_cache = None
    return load_config(config_path)


def get_database_config() -> Dict[str, Any]:
    """獲取資料庫配置

    Returns:
        資料庫配置字典
    """
    return get_config().get("database", {})


def get_redis_config() -> Dict[str, Any]:
    """獲取 Redis 配置

    Returns:
        Redis 配置字典
    """
    return get_config().get("redis", {})


def get_ollama_config() -> Dict[str, Any]:
    """獲取 Ollama 配置

    Returns:
        Ollama 配置字典
    """
    return get_config().get("ollama", {})


def get_logging_config() -> Dict[str, Any]:
    """獲取日誌配置

    Returns:
        日誌配置字典
    """
    return get_config().get("logging", {})


def get_sources_config() -> list:
    """獲取資料源配置列表

    Returns:
        資料源配置列表
    """
    return get_config().get("sources", [])
