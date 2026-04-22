"""
==============================================================================
Common 模組：LLM 客戶端 (llm_client.py)
==============================================================================

📌 本檔案功能：
    提供與 vLLM 服務溝通的客戶端類別。

📖 架構說明：
    本專案使用 vLLM 作為 LLM 推論後端，透過 OpenAI 相容的 API 進行溝通：
    
    ┌─────────────┐    HTTP/JSON     ┌─────────────┐
    │  Python     │ ───────────────▶ │   vLLM      │
    │  Client     │ ◀─────────────── │   Server    │
    └─────────────┘                  └─────────────┘
    
    vLLM 提供 /v1/chat/completions 端點，與 OpenAI API 相容。

🔧 使用方式：
    from common.llm_client import VllmChatClient
    
    client = VllmChatClient()
    response = client.chat([
        {"role": "user", "content": "你好"}
    ])
    print(response)

📋 環境變數：
    - VLLM_BASE_URL：vLLM 服務網址（預設 http://localhost:8299/v1）
    - VLLM_MODEL：模型名稱（預設 Qwen/Qwen2.5-3B-Instruct）
"""

import os
import requests
from typing import List, Dict, Any, Optional


# ==============================================================================
# 環境變數設定
# ==============================================================================

# vLLM 服務的基礎 URL
# 預設 8299 是 docker-compose.yaml 中設定的外部端口
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8299/v1")
"""
vLLM 服務的基礎 URL。

可透過環境變數設定：
    export VLLM_BASE_URL=http://your-server:8000/v1
    
Docker Compose 設定中，vLLM 內部運行在 8000 埠，
對外映射到 8299 埠。
"""

# 使用的模型名稱
VLLM_MODEL = os.getenv("VLLM_MODEL", "Qwen/Qwen2.5-3B-Instruct")
"""
vLLM 服務中載入的模型名稱。

需要與 docker-compose.yaml 中的 --model 參數一致。
"""


class VllmChatClient:
    """
    vLLM Chat API 客戶端
    
    用於與 vLLM 服務進行聊天對話。
    支援 OpenAI 相容的 chat completions API。
    
    Attributes:
        base_url: vLLM 服務的基礎 URL
        model: 使用的模型名稱
        timeout: 請求超時時間（秒）
    
    Example:
        # 基本使用
        >>> client = VllmChatClient()
        >>> response = client.chat([{"role": "user", "content": "你好"}])
        >>> print(response)
        "你好！有什麼我可以幫助你的嗎？"
        
        # 自訂設定
        >>> client = VllmChatClient(
        ...     base_url="http://custom-server:8000/v1",
        ...     model="Llama-3-8B-Instruct",
        ...     timeout=60
        ... )
    """
    
    def __init__(
        self, 
        base_url: str = VLLM_BASE_URL, 
        model: str = VLLM_MODEL, 
        timeout: int = 120
    ):
        """
        初始化 VllmChatClient
        
        Args:
            base_url: vLLM 服務的基礎 URL（預設從環境變數讀取）
            model: 模型名稱（預設從環境變數讀取）
            timeout: HTTP 請求超時時間，單位為秒（預設 120 秒）
        """
        # 移除尾端斜線，避免重複
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def chat(
        self, 
        messages: List[Dict[str, Any]], 
        temperature: float = 0.2, 
        max_tokens: int = 512
    ) -> str:
        """
        發送聊天請求
        
        將對話歷史送給 vLLM，取得模型的回應。
        
        Args:
            messages: 對話歷史列表，格式遵循 OpenAI API 標準
                [
                    {"role": "system", "content": "你是助理"},
                    {"role": "user", "content": "你好"},
                    {"role": "assistant", "content": "你好！"},
                    {"role": "user", "content": "今天天氣如何？"}
                ]
            
            temperature: 生成的隨機程度（0.0 ~ 2.0）
                - 0.0：完全確定性（每次輸出相同）
                - 0.2：低隨機性（推薦用於 Function Calling）
                - 0.7-1.0：較高隨機性（適合創意寫作）
            
            max_tokens: 最多生成的 token 數量
                - 設太小可能截斷輸出
                - 設太大會增加延遲
        
        Returns:
            模型生成的回應文字（str）
        
        Raises:
            requests.exceptions.HTTPError: HTTP 請求失敗
            requests.exceptions.Timeout: 請求超時
        
        Example:
            >>> messages = [
            ...     {"role": "system", "content": "你是客服助理"},
            ...     {"role": "user", "content": "幫我查訂單 A123456789"}
            ... ]
            >>> response = client.chat(messages, temperature=0.0)
            >>> print(response)
        
        API 格式說明：
            Request:
            POST /v1/chat/completions
            {
                "model": "Qwen/Qwen2.5-3B-Instruct",
                "messages": [...],
                "temperature": 0.2,
                "max_tokens": 512
            }
            
            Response:
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "..."
                        }
                    }
                ]
            }
        """
        
        # 組合 API URL
        url = f"{self.base_url}/chat/completions"
        
        # 組合請求 payload
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        # 發送 POST 請求
        r = requests.post(url, json=payload, timeout=self.timeout)
        
        # 檢查 HTTP 狀態碼
        # 如果不是 2xx，會拋出 HTTPError
        r.raise_for_status()
        
        # 解析回應
        data = r.json()
        
        # 提取 assistant 的回覆內容
        return data["choices"][0]["message"]["content"]
