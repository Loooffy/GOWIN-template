# 通用爬蟲服務模板設計文件

## 專案目標

設計並實作一個**通用、可配置的爬蟲服務模板**,參考 [GuangFuHero/spam-blocker](https://github.com/GuangFuHero/spam-blocker) 的架構哲學,實現高度可擴展性和抽象化設計,能夠輕鬆整合不同的資料源和後處理邏輯。

## 原始需求情境 (供理解使用)

構建一個 Arxiv 論文追蹤器:
1. 爬取指定時間範圍內的 Arxiv 論文並存入資料庫
2. 定期更新特定研究領域的論文
3. 使用本地 Ollama 服務對論文摘要進行 LLM 篩選,判斷是否符合特定主題

## 核心設計原則 (參考 spam-blocker)

### 1. 模組化分層架構
- **`src/lib/`**: 核心工具函式庫 (clients, handlers)
- **`src/workers/`**: 業務邏輯處理器 (fetchers, processors)
- **`src/message_queue/`**: 任務調度與追蹤 (可選)
- **`main.py`**: 程式進入點

### 2. 配置驅動設計
- 使用 `.env` 或 `config.yaml` 統一管理配置
- 支援多資料源獨立配置
- 環境變數與配置檔案分離

### 3. 依賴注入與抽象化
- 定義抽象基礎類別解耦具體實作
- 使用工廠模式動態載入實作類別
- 便於單元測試和模組替換

## 專案目錄結構

```
crawler-template/
├── src/
│   ├── lib/                    # 核心函式庫
│   │   ├── __init__.py
│   │   ├── abstract.py         # 抽象基礎類別定義
│   │   ├── database.py         # 資料庫 ORM 層
│   │   └── logger.py           # 日誌管理
│   │
│   ├── workers/                # 業務邏輯層
│   │   ├── __init__.py
│   │   ├── connectors/         # 資料源連接器
│   │   │   ├── __init__.py
│   │   │   └── arxiv.py        # Arxiv 連接器範例
│   │   │
│   │   ├── processors/         # 資料處理器
│   │   │   ├── __init__.py
│   │   │   └── ollama_filter.py # Ollama 篩選器範例
│   │   │
│   │   └── controller.py       # 核心控制器
│   │
│   ├── config/                 # 配置管理
│   │   ├── __init__.py
│   │   └── config.py           # 配置載入與驗證
│   │
│   └── main.py                 # 程式入口
│
├── config.yaml                 # 配置檔案
├── .env.example                # 環境變數範例
├── pyproject.toml              # Python 專案配置 (使用 uv)
├── requirements.txt            # 依賴套件 (備用)
└── README.md
```

## 核心抽象層設計

### `src/lib/abstract.py`

定義三個關鍵抽象基礎類別:

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List

class DataSourceConnector(ABC):
    """資料源連接器抽象類別"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化連接器
        
        Args:
            config: 該資料源的配置字典
        """
        self.config = config
        self.validate_config()
    
    @abstractmethod
    def validate_config(self) -> None:
        """驗證配置的有效性,不符合要求時拋出異常"""
        pass
    
    @abstractmethod
    def fetch_data(self) -> List[Dict[str, Any]]:
        """
        執行資料爬取
        
        Returns:
            統一格式的資料列表,每個 item 必須包含:
            - id: 唯一識別碼
            - title: 標題
            - content: 主要內容
            - metadata: 其他元資料 (dict)
        """
        pass


class DataProcessor(ABC):
    """資料處理器抽象類別 (用於 LLM 篩選、清洗等後處理)"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化處理器
        
        Args:
            config: 處理器配置字典
        """
        self.config = config
    
    @abstractmethod
    def process_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        處理單個資料項目
        
        Args:
            item: 待處理的資料項目
            
        Returns:
            處理後的資料項目,必須包含原始欄位外加:
            - processed: True/False (是否已處理)
            - filter_result: 篩選結果 (dict, 可含 passed, reason 等)
        """
        pass


class DatabaseRepository(ABC):
    """資料庫存取抽象類別"""
    
    @abstractmethod
    def connect(self) -> None:
        """建立資料庫連接"""
        pass
    
    @abstractmethod
    def save_items(self, items: List[Dict[str, Any]]) -> None:
        """批量儲存資料項目"""
        pass
    
    @abstractmethod
    def get_processed_ids(self) -> set:
        """獲取已處理項目的 ID 集合"""
        pass
    
    @abstractmethod
    def close(self) -> None:
        """關閉資料庫連接"""
        pass
```

## 配置檔案結構

### `config.yaml`

```yaml
# 資料庫配置
database:
  type: "sqlite"  # sqlite, postgresql, mysql
  path: "./data/crawler.db"  # SQLite 路徑
  # host: "localhost"  # PostgreSQL/MySQL
  # port: 5432
  # username: "user"
  # password: "pass"
  # database: "crawler_db"

# Ollama 配置 (若使用 LLM 處理)
ollama:
  api_url: "http://localhost:11434"
  model: "llama3"
  timeout: 30

# 日誌配置
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR
  file: "./logs/crawler.log"
  max_bytes: 5242880  # 5MB
  backup_count: 5

# 資料源配置列表
sources:
  - name: "arxiv_ai_papers"
    enabled: true
    connector_class: "ArxivConnector"
    processor_class: "OllamaFilterProcessor"
    schedule: "0 */6 * * *"  # Cron 表達式 (可選,用於排程)
    config:
      # Arxiv 專用配置
      query: "cat:cs.AI OR cat:cs.LG"
      max_results: 100
      sort_by: "submittedDate"
      sort_order: "descending"
      start_date: "2024-01-01"
    processor_config:
      # Ollama 篩選配置
      filter_prompt: |
        請判斷這篇論文是否與「大型語言模型的安全性」相關。
        只回答 YES 或 NO,並簡述理由。
      relevance_threshold: 0.7

  # - name: "rss_tech_news"
  #   enabled: false
  #   connector_class: "RSSConnector"
  #   processor_class: null  # 不需要後處理
  #   config:
  #     feed_url: "https://example.com/feed.xml"
  #     max_items: 50
```

### `.env.example`

```bash
# Ollama API (若不使用 config.yaml)
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3

# 資料庫 (若不使用 config.yaml)
DB_TYPE=sqlite
DB_PATH=./data/crawler.db

# 日誌等級
LOG_LEVEL=INFO
```

## 核心業務邏輯實作

### `src/workers/controller.py` - 核心控制器

```python
import importlib
import logging
from typing import List, Dict, Any, Optional
from src.lib.abstract import DataSourceConnector, DataProcessor, DatabaseRepository
from src.config.config import load_config

logger = logging.getLogger(__name__)


class CrawlerController:
    """爬蟲核心控制器 - 負責協調所有模組"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = load_config(config_path)
        self.db_repo: Optional[DatabaseRepository] = None
        
    def _load_class(self, module_path: str, class_name: str):
        """
        動態載入類別 (工廠模式)
        
        Args:
            module_path: 模組路徑,如 'src.workers.connectors.arxiv'
            class_name: 類別名稱,如 'ArxivConnector'
        """
        try:
            module = importlib.import_module(module_path)
            return getattr(module, class_name)
        except (ImportError, AttributeError) as e:
            logger.error(f"無法載入類別 {class_name} from {module_path}: {e}")
            raise
    
    def _init_database(self):
        """初始化資料庫連接"""
        db_class = self._load_class(
            "src.lib.database",
            f"{self.config['database']['type'].capitalize()}Repository"
        )
        self.db_repo = db_class(self.config['database'])
        self.db_repo.connect()
    
    def run_source(self, source_config: Dict[str, Any]):
        """
        執行單個資料源的爬取與處理
        
        Args:
            source_config: 資料源配置字典
        """
        source_name = source_config['name']
        logger.info(f"開始處理資料源: {source_name}")
        
        # 1. 動態載入連接器
        connector_class = self._load_class(
            f"src.workers.connectors.{source_config['connector_class'].lower().replace('connector', '')}",
            source_config['connector_class']
        )
        connector: DataSourceConnector = connector_class(source_config['config'])
        
        # 2. 爬取資料
        logger.info(f"正在爬取資料源: {source_name}")
        raw_data = connector.fetch_data()
        logger.info(f"成功爬取 {len(raw_data)} 筆資料")
        
        # 3. 過濾已處理的項目
        processed_ids = self.db_repo.get_processed_ids()
        new_items = [item for item in raw_data if item['id'] not in processed_ids]
        logger.info(f"新增項目: {len(new_items)} 筆")
        
        if not new_items:
            logger.info(f"資料源 {source_name} 無新增項目")
            return
        
        # 4. 執行後處理 (如果有配置)
        if source_config.get('processor_class'):
            processor_class = self._load_class(
                f"src.workers.processors.{source_config['processor_class'].lower().replace('processor', '')}",
                source_config['processor_class']
            )
            processor: DataProcessor = processor_class(source_config.get('processor_config', {}))
            
            logger.info(f"開始處理 {len(new_items)} 筆新項目")
            processed_items = []
            for item in new_items:
                try:
                    processed_item = processor.process_item(item)
                    processed_items.append(processed_item)
                except Exception as e:
                    logger.error(f"處理項目 {item.get('id')} 失敗: {e}")
                    # 標記為處理失敗但仍存入資料庫
                    item['processed'] = False
                    item['error'] = str(e)
                    processed_items.append(item)
            
            new_items = processed_items
        
        # 5. 儲存到資料庫
        logger.info(f"儲存 {len(new_items)} 筆資料到資料庫")
        self.db_repo.save_items(new_items)
        logger.info(f"資料源 {source_name} 處理完成")
    
    def run_all(self):
        """執行所有已啟用的資料源"""
        self._init_database()
        
        try:
            for source in self.config['sources']:
                if source.get('enabled', True):
                    try:
                        self.run_source(source)
                    except Exception as e:
                        logger.error(f"資料源 {source['name']} 處理失敗: {e}")
                        continue
        finally:
            if self.db_repo:
                self.db_repo.close()
```

## 具體實作範例

### `src/workers/connectors/arxiv.py` - Arxiv 連接器

```python
import arxiv
from datetime import datetime
from typing import List, Dict, Any
from src.lib.abstract import DataSourceConnector


class ArxivConnector(DataSourceConnector):
    """Arxiv API 連接器"""
    
    def validate_config(self) -> None:
        required = ['query', 'max_results']
        for key in required:
            if key not in self.config:
                raise ValueError(f"缺少必要配置: {key}")
    
    def fetch_data(self) -> List[Dict[str, Any]]:
        """爬取 Arxiv 論文"""
        client = arxiv.Client()
        
        search = arxiv.Search(
            query=self.config['query'],
            max_results=self.config['max_results'],
            sort_by=getattr(arxiv.SortCriterion, self.config.get('sort_by', 'SubmittedDate')),
            sort_order=getattr(arxiv.SortOrder, self.config.get('sort_order', 'Descending'))
        )
        
        results = []
        for paper in client.results(search):
            # 檢查日期過濾
            if 'start_date' in self.config:
                start_date = datetime.fromisoformat(self.config['start_date'])
                if paper.published.replace(tzinfo=None) < start_date:
                    continue
            
            results.append({
                'id': paper.entry_id,
                'title': paper.title,
                'content': paper.summary,
                'metadata': {
                    'authors': [author.name for author in paper.authors],
                    'categories': paper.categories,
                    'published': paper.published.isoformat(),
                    'pdf_url': paper.pdf_url,
                }
            })
        
        return results
```

### `src/workers/processors/ollama_filter.py` - Ollama 篩選處理器

```python
import requests
import logging
from typing import Dict, Any
from src.lib.abstract import DataProcessor

logger = logging.getLogger(__name__)


class OllamaFilterProcessor(DataProcessor):
    """使用 Ollama 進行論文相關性篩選"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # 從全域配置載入 Ollama 設定
        from src.config.config import get_config
        self.ollama_config = get_config()['ollama']
    
    def _call_ollama(self, prompt: str) -> str:
        """呼叫 Ollama API"""
        url = f"{self.ollama_config['api_url']}/api/generate"
        payload = {
            "model": self.ollama_config['model'],
            "prompt": prompt,
            "stream": False
        }
        
        response = requests.post(
            url,
            json=payload,
            timeout=self.ollama_config.get('timeout', 30)
        )
        response.raise_for_status()
        
        return response.json()['response']
    
    def process_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """使用 LLM 判斷論文相關性"""
        filter_prompt = self.config.get('filter_prompt', '')
        
        full_prompt = f"""{filter_prompt}

標題: {item['title']}
摘要: {item['content']}

請判斷並回答:"""
        
        try:
            llm_response = self._call_ollama(full_prompt)
            
            # 解析 LLM 回應
            is_relevant = 'yes' in llm_response.lower()
            
            item['processed'] = True
            item['filter_result'] = {
                'passed': is_relevant,
                'reason': llm_response.strip(),
                'model': self.ollama_config['model']
            }
            
            logger.info(f"論文 {item['id']} 篩選結果: {'通過' if is_relevant else '不通過'}")
            
        except Exception as e:
            logger.error(f"Ollama 處理失敗: {e}")
            item['processed'] = False
            item['filter_result'] = {
                'passed': False,
                'reason': f"處理錯誤: {str(e)}",
                'error': True
            }
        
        return item
```

## 程式入口

### `src/main.py`

```python
import logging
from src.workers.controller import CrawlerController
from src.lib.logger import setup_logging


def main():
    # 初始化日誌
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("=== 爬蟲服務啟動 ===")
    
    try:
        # 初始化控制器
        controller = CrawlerController(config_path="config.yaml")
        
        # 執行所有資料源
        controller.run_all()
        
        logger.info("=== 爬蟲服務完成 ===")
        
    except Exception as e:
        logger.error(f"服務執行失敗: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
```

## 擴展指南

### 新增資料源連接器

1. 在 `src/workers/connectors/` 建立新檔案,如 `rss.py`
2. 繼承 `DataSourceConnector` 並實作 `validate_config()` 和 `fetch_data()`
3. 在 `config.yaml` 新增資料源配置
4. 設定 `connector_class: "RSSConnector"`

### 新增資料處理器

1. 在 `src/workers/processors/` 建立新檔案,如 `sentiment.py`
2. 繼承 `DataProcessor` 並實作 `process_item()`
3. 在資料源配置中設定 `processor_class` 和 `processor_config`

## 開發與測試

### 安裝依賴

```bash
# 使用 uv (推薦)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync

# 或使用 pip
pip install -r requirements.txt
```

### 執行爬蟲

```bash
# 使用 uv
uv run python src/main.py

# 或直接執行
python src/main.py
```

### 單元測試

```bash
# 測試連接器
python -m pytest tests/test_connectors.py

# 測試處理器
python -m pytest tests/test_processors.py
```

## 部署建議

### Docker 部署

參考 spam-blocker 的 Docker 設定:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安裝 uv
RUN pip install uv

# 複製依賴檔案
COPY pyproject.toml .
COPY requirements.txt .

# 安裝依賴
RUN uv sync

# 複製程式碼
COPY src/ ./src/
COPY config.yaml .

# 執行
CMD ["uv", "run", "python", "src/main.py"]
```

### 定時排程

使用 cron 或 Kubernetes CronJob:

```bash
# crontab 範例: 每 6 小時執行一次
0 */6 * * * cd /path/to/crawler && uv run python src/main.py >> logs/cron.log 2>&1
```

## 注意事項

1. **錯誤處理**: 每個模組都應有完善的異常處理,避免單一失敗影響整體
2. **速率限制**: 注意外部 API 的速率限制,必要時加入延遲或重試邏輯
3. **資料去重**: 使用唯一 ID 確保不重複處理相同資料
4. **日誌管理**: 使用 RotatingFileHandler 避免日誌檔案過大
5. **配置驗證**: 啟動時驗證所有配置的有效性,提早發現錯誤

## 總結

此模板遵循 spam-blocker 的核心設計原則:
- ✅ 清晰的模組化分層
- ✅ 配置驅動的靈活性
- ✅ 抽象化設計的可擴展性
- ✅ 完整的錯誤處理與日誌
- ✅ 支援多資料源與多處理器

根據實際需求調整配置和實作,即可快速建立各種爬蟲服務。