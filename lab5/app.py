"""
==============================================================================
LAB 5：FastAPI 服務 - Function Calling Agent HTTP API
==============================================================================

📌 本檔案功能：
    將 Function Calling Agent 封裝成 HTTP API，包含：
    1. RESTful 端點設計
    2. 防呆機制（驗證、重試）
    3. 觀測資訊（trace）
    4. 錯誤處理

📖 API 端點：
    POST /chat
    - 輸入：{"messages": [{"role": "user", "content": "..."}]}
    - 輸出：{"messages": [...], "trace": {...}}

🔧 啟動方式：
    方式 1：uvicorn lab5.app:app --host 0.0.0.0 --port 9000
    方式 2：python -m lab5.app（如果加入 __main__ 區塊）

📋 API 文件：
    啟動後訪問 http://localhost:9000/docs 查看 Swagger UI
"""

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import List, Dict, Any
import time
import requests # 用於檢查 vLLM 連線
from datetime import datetime, timezone # 用於產生時間戳記

# --- 新增 SlowAPI 限流套件 ---
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# --- 新增 結構化日誌套件 ---
import structlog
from uuid import uuid4

logger = structlog.get_logger()

# 共用模組
from common.call_llm import call_llm
from common.prompts import system_prompt, tool_result_message
from common.utils import extract_json_block, pretty
from common.validator import validate_tool_call
from common.tools import TOOL_REGISTRY


# ==============================================================================
# FastAPI 應用初始化
# ==============================================================================

app = FastAPI(
    title="Order CS Agent (vLLM + Tool JSON)",
    description="訂單客服 Agent API - 支援 Function Calling",
    version="1.0.0",
    docs_url="/docs",       # Swagger UI 路徑
    redoc_url="/redoc",     # ReDoc 路徑
)

# --- 設定限流器 (Rate Limiter) ---
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


def check_llm_connection() -> str:
    """
    檢查 vLLM 服務是否正常連線
    """
    try:
        # 參考 Lab 3 的環境準備建議，檢查 vLLM 的 models 資訊
        # 設定較短的 timeout (2秒)，避免健康檢查卡住
        resp = requests.get("http://127.0.0.1:8299/v1/models", timeout=2)
        if resp.status_code == 200:
            return "connected"
        return f"error: status_code {resp.status_code}"
    except Exception as e:
        return f"disconnected"

# ==============================================================================
# Request/Response 模型定義
# ==============================================================================

class ChatReq(BaseModel):
    """
    聊天請求格式
    
    Attributes:
        messages: 對話歷史列表
                  [{"role": "user", "content": "..."}]
                  
    Example:
        {
            "messages": [
                {"role": "user", "content": "幫我查訂單 A123456789 狀態"}
            ]
        }
    """
    messages: List[Dict[str, Any]]


class ChatResp(BaseModel):
    """
    聊天回應格式
    
    Attributes:
        messages: 更新後的對話歷史（包含 assistant 回覆）
        trace: 觀測資訊，用於除錯和監控
        
    Example:
        {
            "messages": [...],
            "trace": {
                "steps": [
                    {"model_out": "..."},
                    {"tool_call": {...}},
                    {"tool_result": {...}},
                    {"final": "..."}
                ]
            }
        }
    """
    messages: List[Dict[str, Any]]
    trace: Dict[str, Any]


# ==============================================================================
# API 端點
# ==============================================================================

@app.post("/chat", response_model=ChatResp)
@limiter.limit("15/minute")  # 限制每個 IP 每分鐘最多只能呼叫 15 次
def chat(request: Request, req: ChatReq):
    """
    聊天端點 - 處理使用者訊息並可能呼叫工具
    
    流程：
    ┌─────────────────────────────────────────────────────────────────┐
    │  1. 組合 system prompt + 使用者訊息                              │
    │  2. 呼叫 LLM 生成回應                                           │
    │  3. 檢查是否為 tool_call                                        │
    │     - 否 → 直接回傳                                             │
    │     - 是 → 驗證 → 重試（如果需要）→ 執行工具 → 生成最終回覆       │
    │  4. 回傳結果 + trace                                            │
    └─────────────────────────────────────────────────────────────────┘
    
    Args:
        req: 包含 messages 的請求物件
        
    Returns:
        ChatResp: 包含更新後的 messages 和 trace
    """
    
    # 記錄開始時間（用於計算延遲）
    start_time = time.time()

    # 產生請求 ID 與擷取使用者輸入
    req_id = str(uuid4())
    user_message = req.messages[-1]["content"] if req.messages else ""
    executed_tool = None  # 用來追蹤最後到底呼叫了哪個工具
    
    trace = {
        "steps": [],
        "latency_ms": 0
    }
    
    # ==========================================================================
    # Step 1: 組合對話歷史
    # ==========================================================================
    # 加入 system prompt（定義角色和可用工具）
    # req.messages 是使用者傳入的對話歷史
    messages = [{"role": "system", "content": system_prompt()}] + req.messages
    
    # 初始化 trace（觀測資訊）
    # trace 記錄每個步驟的結果，方便除錯和監控
    trace = {
        "steps": [],
        "start_time": start_time,
    }
    
    # ==========================================================================
    # Step 2: 呼叫 LLM
    # ==========================================================================
    out = call_llm(messages)
    trace["steps"].append({"model_out": out})
    
    # 嘗試提取 tool_call JSON
    tool_call = extract_json_block(out)
    
    # ==========================================================================
    # Step 3a: 沒有 tool_call → 直接回傳
    # ==========================================================================
    if not tool_call:
        messages.append({"role": "assistant", "content": out})
        trace["latency_ms"] = int((time.time() - start_time) * 1000)
        return {"messages": messages, "trace": trace}
    
    # ==========================================================================
    # Step 3b: 有 tool_call → 驗證
    # ==========================================================================
    ok, err = validate_tool_call(tool_call)
    
    if not ok:
        # ------------------------------------------------------------------
        # 驗證失敗 → 重試機制
        # ------------------------------------------------------------------
        # 這是重要的防呆機制！
        # LLM 可能輸出格式錯誤的 JSON，我們給它一次重試機會
        
        trace["steps"].append({"validation_error": err})
        
        # 告訴 LLM 它的輸出不合法
        messages.append({"role": "assistant", "content": out})
        messages.append({
            "role": "user", 
            "content": f"你的 tool_call 不合法：{err}。請只輸出合法 JSON。"
        })
        
        # 重試
        out2 = call_llm(messages)
        trace["steps"].append({"retry_out": out2})
        
        tool_call = extract_json_block(out2)
        
        if not tool_call:
            # 重試後仍無法解析 JSON → 放棄
            messages.append({"role": "assistant", "content": out2})
            trace["latency_ms"] = int((time.time() - start_time) * 1000)
            return {"messages": messages, "trace": trace}
        
        # 再次驗證
        ok, err = validate_tool_call(tool_call)
        if not ok:
            # 重試後仍不合法 → 放棄
            messages.append({"role": "assistant", "content": out2})
            trace["error"] = err
            trace["latency_ms"] = int((time.time() - start_time) * 1000)
            return {"messages": messages, "trace": trace}
    
    # ==========================================================================
    # Step 4: 執行工具
    # ==========================================================================
    name = tool_call["name"]
    args = tool_call["arguments"]

    executed_tool = name
    
    trace["steps"].append({"tool_call": tool_call})
    
    # 執行工具函式
    # 在生產環境中，這裡應該加入：
    # - 超時控制
    # - 錯誤處理
    # - 權限檢查
    try:
        result = TOOL_REGISTRY[name](**args)
        trace["steps"].append({"tool_result": result})
    except Exception as e:
        # 工具執行失敗
        trace["steps"].append({"tool_error": str(e)})
        result = {"ok": False, "error": str(e)}
    
    # ==========================================================================
    # Step 5: 餵回工具結果，生成最終回覆
    # ==========================================================================
    messages.append({"role": "assistant", "content": pretty(tool_call)})
    messages.append({"role": "user", "content": tool_result_message(name, result)})
    
    final = call_llm(messages)
    messages.append({"role": "assistant", "content": final})
    trace["steps"].append({"final": final})
    
    # ==========================================================================
    # 回傳結果
    # ==========================================================================
    trace["latency_ms"] = int((time.time() - start_time) * 1000)
    
    # --- 印出結構化日誌 ---
    logger.info(
        "chat_request_completed",
        request_id=req_id,
        user_input=user_message,
        tool_name=executed_tool,
        latency_ms=trace["latency_ms"]
    )

    return {"messages": messages, "trace": trace}


# ==============================================================================
# 健康檢查端點
# ==============================================================================

@app.get("/health")
def health():
    """
    健康檢查端點
    
    用於監控系統是否正常運作。
    
    Returns:
        {"status": "healthy", "timestamp": "..."}
    """
    return {
        "status": "healthy",
        "llm_status": check_llm_connection(),
        "timestamp": datetime.now(timezone.utc).isoformat() # 使用 ISO 格式的時間戳記
    }


@app.get("/")
def root():
    """
    根路徑 - 顯示 API 資訊
    """
    return {
        "name": "Order CS Agent",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


# ==============================================================================
# 程式進入點（可選）
# ==============================================================================

if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("LAB5: 啟動 FastAPI 服務")
    print("=" * 60)
    print("API 文件：http://localhost:9000/docs")
    print("健康檢查：http://localhost:9000/health")
    print("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=9000)
