"""
Ollama LLM 客戶端

與本地 Ollama 服務整合，執行 LLM 推理任務。
參考 spam-blocker 的 OllamaClient 設計，支援結構化輸出。
"""

import logging
import requests
import json
from typing import Dict, Any, Optional

from src.models.base import ValidationResult

logger = logging.getLogger(__name__)


class OllamaClient:
    """Ollama API 客戶端

    用於呼叫本地 Ollama 服務進行 LLM 推理。
    支援結構化 JSON 輸出，適合用於資料驗證和篩選任務。
    """

    def __init__(
        self,
        api_url: str = "http://localhost:11434",
        model: str = "llama3",
        timeout: int = 30,
    ):
        """初始化 Ollama 客戶端

        Args:
            api_url: Ollama API URL
            model: 使用的模型名稱
            timeout: API 超時時間（秒）
        """
        self.api_url = api_url.rstrip("/")
        self.model = model
        self.timeout = timeout

        logger.info(f"Ollama 客戶端已初始化 - URL: {self.api_url}, 模型: {self.model}")

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        format_json: bool = False,
        format_schema: Optional[Dict[str, Any]] = None,
    ) -> str:
        """生成文字回應

        Args:
            prompt: 使用者提示詞
            system_prompt: 系統提示詞（可選）
            temperature: 溫度參數（0.0 = 確定性，1.0 = 隨機性）
            format_json: 是否要求 JSON 格式輸出（使用 "json" 字串）
            format_schema: JSON Schema 格式定義（優先於 format_json）

        Returns:
            LLM 生成的文字

        Raises:
            requests.exceptions.RequestException: 當 API 呼叫失敗時
        """
        url = f"{self.api_url}/api/generate"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
            }
        }

        # 添加系統提示詞
        if system_prompt:
            payload["system"] = system_prompt

        # 優先使用 JSON Schema（更精確的格式控制）
        if format_schema:
            payload["format"] = format_schema
        # 或使用簡單的 JSON 格式
        elif format_json:
            payload["format"] = "json"

        try:
            logger.debug(f"呼叫 Ollama API: {url}")
            response = requests.post(
                url,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()

            result = response.json()
            generated_text = result.get("response", "")

            logger.debug(f"Ollama 回應長度: {len(generated_text)} 字元")
            return generated_text

        except requests.exceptions.Timeout:
            logger.error(f"Ollama API 超時（超過 {self.timeout} 秒）")
            raise

        except requests.exceptions.ConnectionError as e:
            logger.error(f"無法連接到 Ollama API: {e}")
            raise

        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama API 呼叫失敗: {e}")
            raise

    def get_validation_result(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> ValidationResult:
        """獲取結構化驗證結果

        使用 JSON Schema 格式輸出，返回標準化的 ValidationResult。
        Ollama 會強制遵守提供的 schema，確保輸出格式正確。
        適合用於二元判斷任務（有效/無效、相關/不相關等）。

        Args:
            prompt: 使用者提示詞
            system_prompt: 系統提示詞（可選）

        Returns:
            ValidationResult 實例

        Raises:
            ValueError: 當無法解析 JSON 或格式不正確時
            requests.exceptions.RequestException: 當 API 呼叫失敗時
        """
        try:
            # 呼叫 API 並提供 ValidationResult 的 JSON Schema
            # Ollama 會自動強制輸出符合此 schema
            response_text = self.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.0,  # 使用低溫度以獲得一致性
                format_schema=ValidationResult.model_json_schema(),
            )

            # 解析 JSON 回應
            try:
                response_data = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error(f"無法解析 Ollama 回應為 JSON: {e}")
                logger.debug(f"原始回應: {response_text}")
                # 如果 schema 強制後仍失敗，嘗試從文字中提取
                return self._parse_text_response(response_text)

            # 使用 Pydantic 驗證並建立 ValidationResult
            # 這會確保所有必要欄位存在且類型正確
            validation_result = ValidationResult(**response_data)
            logger.debug(f"驗證結果: valid={validation_result.valid}, reason={validation_result.reason[:50]}...")

            return validation_result

        except Exception as e:
            logger.error(f"獲取驗證結果失敗: {e}")
            # 返回錯誤的驗證結果
            return ValidationResult(
                valid=False,
                reason=f"處理錯誤: {str(e)}"
            )

    def _parse_text_response(self, text: str) -> ValidationResult:
        """當 JSON 解析失敗時，嘗試從文字中提取判斷結果

        Args:
            text: LLM 回應文字

        Returns:
            ValidationResult 實例
        """
        text_lower = text.lower()

        # 簡單的啟發式判斷
        if "yes" in text_lower or "true" in text_lower or "valid" in text_lower:
            valid = True
        elif "no" in text_lower or "false" in text_lower or "invalid" in text_lower:
            valid = False
        else:
            # 無法判斷，預設為 False
            valid = False

        return ValidationResult(
            valid=valid,
            reason=text.strip()
        )

    def check_connection(self) -> bool:
        """檢查 Ollama 服務是否可用

        Returns:
            True 表示服務可用，False 表示不可用
        """
        try:
            url = f"{self.api_url}/api/tags"
            response = requests.get(url, timeout=5)
            response.raise_for_status()

            models = response.json().get("models", [])
            model_names = [m.get("name") for m in models]

            logger.info(f"Ollama 服務可用，可用模型: {', '.join(model_names)}")

            # 檢查指定的模型是否可用
            if self.model not in model_names:
                logger.warning(f"指定的模型 '{self.model}' 不在可用模型列表中")

            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama 服務不可用: {e}")
            return False


# 全域 Ollama 客戶端實例（單例模式）
_ollama_client: Optional[OllamaClient] = None


def get_ollama_client(
    api_url: Optional[str] = None,
    model: Optional[str] = None,
    timeout: Optional[int] = None,
) -> OllamaClient:
    """獲取全域 Ollama 客戶端實例

    使用單例模式，避免重複建立連接。

    Args:
        api_url: Ollama API URL（首次呼叫時必須提供）
        model: 使用的模型名稱（首次呼叫時必須提供）
        timeout: API 超時時間（秒）

    Returns:
        OllamaClient 實例
    """
    global _ollama_client

    if _ollama_client is None:
        if api_url is None or model is None:
            # 嘗試從配置中載入
            from src.config.config import get_ollama_config
            ollama_config = get_ollama_config()
            api_url = api_url or ollama_config.get("api_url", "http://localhost:11434")
            model = model or ollama_config.get("model", "llama3")
            timeout = timeout or ollama_config.get("timeout", 30)

        _ollama_client = OllamaClient(api_url=api_url, model=model, timeout=timeout)

    return _ollama_client
