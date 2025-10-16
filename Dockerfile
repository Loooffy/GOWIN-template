FROM python:3.11-slim

LABEL maintainer="your.email@example.com"
LABEL description="通用爬蟲服務模板 - Docker 容器"

# 設定工作目錄
WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安裝 uv (直接安裝到 /usr/local/bin)
RUN curl -LsSf https://astral.sh/uv/install.sh | env INSTALLER_NO_MODIFY_PATH=1 sh && \
    mv /root/.local/bin/uv /usr/local/bin/uv && \
    mv /root/.local/bin/uvx /usr/local/bin/uvx

# 複製依賴檔案
COPY requirements.txt pyproject.toml ./

# 使用 uv 安裝 Python 依賴
RUN uv pip install --system -r requirements.txt

# 複製原始碼
COPY src/ ./src/
COPY config.yaml ./

# 建立必要的目錄
RUN mkdir -p /app/logs /app/data

# 設定環境變數
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# 健康檢查（可選）
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# 執行爬蟲服務
CMD ["python", "src/main.py"]
