# 通用爬蟲服務模板 GOWIN (Get Only What I Need))

一個高度可配置、模組化的爬蟲服務模板，參考 [spam-blocker](https://github.com/GuangFuHero/spam-blocker) 的架構設計，實現了抽象化、可擴展的資料爬取與處理框架。

## ✨ 特性

- **🔧 高度模組化** - 清晰的分層架構（lib / workers / message_queue）
- **📝 配置驅動** - 使用 YAML 配置檔案，無需修改程式碼即可調整行為
- **🔌 可擴展設計** - 基於抽象基礎類別，輕鬆添加新的資料源和處理器
- **🗄️ 多資料庫支援** - SQLite（開發）/ PostgreSQL（生產）
- **🤖 LLM 整合** - 內建 Ollama 支援，用於智能內容篩選和分析
- **🔄 Redis 狀態追蹤** - 可選的高效去重機制，支援增量更新
- **📊 完整日誌** - RotatingFileHandler，避免日誌檔案過大
- **🐳 Docker 支援** - 完整的容器化部署方案

## 📁 專案結構

```
crawler-template/
├── src/
│   ├── lib/                          # 核心函式庫層
│   │   ├── abstract.py               # 抽象基礎類別定義
│   │   ├── database.py               # 資料庫 ORM 層
│   │   ├── logger.py                 # 日誌管理
│   │   └── ollama_client.py          # Ollama LLM 客戶端
│   │
│   ├── workers/                      # 業務邏輯層
│   │   ├── connectors/               # 資料源連接器
│   │   │   └── arxiv.py              # Arxiv 連接器範例
│   │   │
│   │   ├── processors/               # 資料處理器
│   │   │   └── ollama_filter.py      # Ollama 篩選器範例
│   │   │
│   │   └── controller.py             # 核心控制器
│   │
│   ├── message_queue/                # 狀態追蹤與佇列
│   │   └── tracker.py                # Redis 狀態追蹤器
│   │
│   ├── config/                       # 配置管理
│   │   └── config.py                 # 配置載入與驗證
│   │
│   ├── models/                       # Pydantic 資料模型
│   │   ├── base.py                   # 基礎模型
│   │   └── arxiv.py                  # Arxiv 特定模型
│   │
│   └── main.py                       # 程式入口點
│
├── config.yaml                       # 配置檔案
├── .env.example                      # 環境變數範例
├── pyproject.toml                    # Python 專案配置
├── requirements.txt                  # 依賴清單
├── Dockerfile                        # Docker 容器定義
├── docker-compose.yml                # Docker 服務編排
└── README.md                         # 本檔案
```

## 🚀 快速開始

### 前置需求

- Python 3.9+
- Ollama（必須，用於 LLM 篩選）
- Redis（可選，用於狀態追蹤去重）

### 1. 安裝依賴

#### 使用 pip

```bash
pip install -r requirements.txt
```

#### 使用 uv（推薦，更快）

```bash
# 安裝 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安裝依賴
uv sync
```

### 2. 配置環境

複製環境變數範例檔案：

```bash
cp .env.example .env
```

編輯 `.env` 並填入實際值（可選，也可直接使用 `config.yaml`）。

### 3. 啟動 Ollama

LLM 篩選是核心功能，必須安裝：

```bash
# 安裝 Ollama
curl https://ollama.ai/install.sh | sh

# 下載模型
ollama pull llama3

# Ollama 會自動在 http://localhost:11434 運行
```

### 4. （可選）啟動 Redis

如果需要使用 Redis 進行狀態追蹤去重：

```bash
# 使用 Docker
docker run -d -p 6379:6379 redis:7-alpine

# 或使用系統套件管理器安裝
# Ubuntu/Debian
sudo apt install redis-server
sudo systemctl start redis
```

### 5. 執行爬蟲

```bash
# 使用預設配置
python src/main.py

# 使用自訂配置檔案
python src/main.py -c custom_config.yaml

# 設定日誌等級
python src/main.py --log-level DEBUG

# 不使用 Redis（僅使用資料庫去重）
python src/main.py --no-redis
```

## 🐳 Docker 部署

### 使用 Docker Compose（推薦）

```bash
# 構建並啟動所有服務
docker-compose up --build

# 背景執行
docker-compose up -d

# 查看日誌
docker-compose logs -f crawler

# 停止服務
docker-compose down
```

### 單獨使用 Docker

```bash
# 構建映像
docker build -t crawler-template .

# 執行容器
docker run --rm \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  --network host \
  crawler-template
```

## ⚙️ 配置說明

### config.yaml 結構

```yaml
# 資料庫配置
database:
  type: "sqlite"  # sqlite, postgresql
  path: "./data/crawler.db"

# Redis 配置
redis:
  url: "redis://localhost:6379/0"

# Ollama 配置
ollama:
  api_url: "http://localhost:11434"
  model: "llama3"
  timeout: 30

# 日誌配置
logging:
  level: "INFO"
  file: "./logs/crawler.log"
  max_bytes: 5242880  # 5MB
  backup_count: 5

# 資料源配置
sources:
  - name: "arxiv_ai_papers"
    enabled: true
    connector_class: "ArxivConnector"
    processor_class: "OllamaFilterProcessor"
    config:
      query: "cat:cs.AI OR cat:cs.LG"
      max_results: 100
    processor_config:
      filter_prompt: |
        請判斷這篇論文是否與「大型語言模型的安全性」相關。
        只回答 YES 或 NO，並簡述理由。
```

## 🔌 擴展指南

### 新增資料源連接器

1. 在 `src/workers/connectors/` 建立新檔案，例如 `rss.py`
2. 繼承 `DataSourceConnector` 並實作必要方法：

```python
from src.lib.abstract import DataSourceConnector
from typing import List, Dict, Any

class RSSConnector(DataSourceConnector):
    def validate_config(self) -> None:
        # 驗證配置
        if "feed_url" not in self.config:
            raise ValueError("缺少 feed_url")

    def fetch_data(self) -> List[Dict[str, Any]]:
        # 實作爬取邏輯
        # 必須返回統一格式：{id, title, content, metadata}
        pass
```

3. 在 `config.yaml` 中配置：

```yaml
sources:
  - name: "tech_news_rss"
    enabled: true
    connector_class: "RSSConnector"
    config:
      feed_url: "https://example.com/feed.xml"
```

### 新增資料處理器

1. 在 `src/workers/processors/` 建立新檔案，例如 `sentiment.py`
2. 繼承 `DataProcessor` 並實作 `process_item` 方法：

```python
from src.lib.abstract import DataProcessor
from typing import Dict, Any

class SentimentProcessor(DataProcessor):
    def process_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        # 實作處理邏輯
        sentiment = self._analyze_sentiment(item["content"])

        item["processed"] = True
        item["filter_result"] = {
            "passed": sentiment == "positive",
            "reason": f"情感分析結果: {sentiment}"
        }
        return item

    def _analyze_sentiment(self, text: str) -> str:
        # 情感分析實作
        pass
```

3. 在資料源配置中指定：

```yaml
sources:
  - name: "news_with_sentiment"
    processor_class: "SentimentProcessor"
```

## 📊 資料庫查詢

爬取的資料儲存在 SQLite 資料庫中，可以使用標準 SQL 查詢：

```bash
# 使用 sqlite3 命令列工具
sqlite3 data/crawler.db

# 查詢所有項目
SELECT * FROM items;

# 查詢通過篩選的項目
SELECT * FROM items WHERE json_extract(filter_result, '$.passed') = 1;

# 統計資訊
SELECT
  COUNT(*) as total,
  SUM(processed) as processed,
  SUM(CASE WHEN json_extract(filter_result, '$.passed') = 1 THEN 1 ELSE 0 END) as passed
FROM items;
```

## 🧪 測試

```bash
# 執行所有測試
pytest

# 執行測試並顯示覆蓋率
pytest --cov=src --cov-report=html

# 執行特定測試檔案
pytest tests/test_connectors.py
```

## 📝 日誌管理

日誌檔案位於 `logs/crawler.log`，使用 RotatingFileHandler 自動輪轉：

- 單個檔案最大 5MB
- 保留 5 個歷史檔案
- 支援 UTF-8 編碼（中文友善）

## 🔧 開發工具

```bash
# 程式碼格式化
black src/

# Linting
ruff check src/

# 型別檢查
mypy src/
```

## 🏗️ 架構設計原則

本專案遵循以下設計原則（參考 spam-blocker）：

1. **模組化分層** - lib（工具）/ workers（業務）/ message_queue（基礎設施）
2. **依賴注入** - 構造函式注入，便於測試和替換實作
3. **抽象化設計** - ABC 定義介面，具體類別實作
4. **配置驅動** - YAML + 環境變數，靈活調整行為
5. **錯誤處理** - 完善的異常處理和日誌記錄
6. **型別安全** - 使用 Pydantic 模型驗證資料
7. **結構化 LLM 輸出** - 使用 JSON Schema 強制 Ollama 輸出格式

## 🤝 貢獻

歡迎提交 Issue 和 Pull Request！

## 📄 授權

MIT License

## 🙏 致謝

本專案參考了 [GuangFuHero/spam-blocker](https://github.com/GuangFuHero/spam-blocker) 的優秀架構設計。

## 📮 聯絡方式

如有問題或建議，請開啟 Issue 或聯絡維護者。

---

**注意事項**

1. **Ollama 必須** - LLM 篩選是核心功能，請確保 Ollama 服務正常運行
2. **速率限制** - 注意外部 API（如 Arxiv）的速率限制，避免過度請求
3. **LLM 效能** - LLM 推理較耗時，建議根據需求調整 `max_results`
4. **資料隱私** - 爬取的資料請遵守相關法規和網站條款
5. **Redis 可選** - Redis 可提升去重效率，但非必需（可用 `--no-redis` 選項運行）

## 📚 參考資源

- [Arxiv API 文檔](https://info.arxiv.org/help/api/index.html)
- [Ollama 文檔](https://ollama.ai/docs)
- [Pydantic 文檔](https://docs.pydantic.dev/)
- [Redis 文檔](https://redis.io/docs/)
