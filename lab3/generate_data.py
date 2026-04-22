"""
==============================================================================
LAB 3：自動生成 SFT 訓練資料（LLM 兩階段生成版）
==============================================================================

📌 本檔案功能：
    用 vLLM（Qwen2.5-3B-Instruct）兩階段生成 Function Calling 訓練資料：
        Step 1：給 LLM 一個 tool 的 schema → 產出符合 schema 的 tool_call
        Step 2：把 tool_call 餵給 LLM → 產出對應的自然 user query
    最後組成 {system, user, assistant tool_call} 三輪訊息。

📖 為什麼用 LLM 生成？
    - 比寫死模板多元很多（同一個 tool 每次的問法都不一樣）
    - 不用為每個 tool 手寫模板與 slot 產生器
    - args 仍會用 jsonschema 嚴格驗證，失敗會重試

🔧 前置需求：
    需要先啟動 vLLM 服務（lab2 用的同一個）：
        http://127.0.0.1:8299/v1/chat/completions

🔧 執行方式：
    python -m lab3.generate_data --num 200
"""

import argparse
import json
import random
import time
from collections import Counter
from pathlib import Path

import requests
from jsonschema import validate as jsonschema_validate
from jsonschema.exceptions import ValidationError

from common.tool_schema import TOOLS


# ==============================================================================
# vLLM 呼叫（本檔案專用：可調 temperature，與 common/call_llm.py 隔離）
# ==============================================================================

VLLM_URL = "http://127.0.0.1:8299/v1/chat/completions"
MODEL_NAME = "Qwen2.5-3B-Instruct"


def llm(messages: list[dict], temperature: float = 0.9, top_p: float = 0.95) -> str:
    """
    呼叫 vLLM，回傳 assistant 文字。

    生成資料用的 temperature/top_p 比 common/call_llm.py 高，
    才能在多輪生成時拿到夠多樣化的內容。
    """
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": temperature,
        "top_p": top_p,
        "stream": False,
        "max_tokens": 512,
    }
    resp = requests.post(VLLM_URL, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


# ==============================================================================
# JSON 提取（容忍 ```json ... ``` 包裝、額外文字）
# ==============================================================================

def _extract_first_json(text: str) -> dict | None:
    """從 LLM 輸出抽出第一個 {...} 區塊並解析。失敗回傳 None。"""
    if not text:
        return None
    # 先剝掉 ```json ... ``` 區塊
    fence_start = text.find("```")
    if fence_start != -1:
        fence_end = text.find("```", fence_start + 3)
        if fence_end != -1:
            inner = text[fence_start + 3:fence_end]
            inner = inner.lstrip("json").lstrip("JSON").lstrip()
            try:
                return json.loads(inner)
            except json.JSONDecodeError:
                pass

    # 括號匹配抓第一個 {...}
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


# ==============================================================================
# Step 1 Prompt：根據 tool schema 生 args
# ==============================================================================

ARGS_GEN_SYSTEM = """你是訓練資料生成器。
任務：根據給定的工具 JSON Schema，生成一組「合理且符合 schema」的範例參數值。

規則：
1. 必填欄位（required）一定要有
2. 選填欄位可以有也可以沒有，請隨機決定（增加資料多樣性）
3. 所有值都要符合 type、pattern、enum 等限制
4. 值要寫實（例如訂單號 A123456789、電話 0912345678、收件人是合理中文姓名、地址是合理台灣地址）
5. 每次生成都要不一樣（不要永遠用相同的範例值）

只回傳一個 JSON 物件（args 的內容），格式：
{"order_id": "A123456789", "reason": "商品瑕疵"}

不要包 ```json``` 也不要其他說明文字。"""


def _build_args_prompt(tool_def: dict) -> list[dict]:
    """組 Step 1 的 messages：system + user(描述工具 schema)。"""
    schema = tool_def["parameters"]
    required = schema.get("required", [])
    optional = [k for k in schema.get("properties", {}) if k not in required]
    user_text = (
        f"工具名稱：{tool_def['name']}\n"
        f"工具用途：{tool_def['description']}\n"
        f"必填欄位：{required}\n"
        f"選填欄位：{optional}\n\n"
        f"參數 JSON Schema：\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        f"請生成一組合理的範例參數，回傳純 JSON 物件。"
    )
    return [
        {"role": "system", "content": ARGS_GEN_SYSTEM},
        {"role": "user", "content": user_text},
    ]


# ==============================================================================
# Step 2 Prompt：根據 tool_call 反推 user query
# ==============================================================================

QUERY_GEN_SYSTEM = """你是訓練資料生成器。
任務：根據一個工具呼叫（tool_call），反推出一句自然的「使用者口語問句」，
讓客服系統看到這句話之後，就會產生那個 tool_call。

規則：
1. 用繁體中文，符合台灣使用者的口語習慣
2. 句子要包含 tool_call.arguments 裡的所有值（例如訂單號、原因等）
3. 風格要多樣：可以是禮貌的、口語的、簡短的、急躁的、含糊的、清晰的……
4. 不要在句子裡出現「tool」「json」「呼叫」等技術詞彙
5. 只回傳那一句話，不要任何前綴、引號、說明、JSON

範例：
tool_call: {"name":"get_order_status","arguments":{"order_id":"A123456789"}}
→ 幫我查訂單 A123456789 狀態

tool_call: {"name":"create_refund_request","arguments":{"order_id":"B987654321","reason":"商品瑕疵"}}
→ 我要退款，訂單 B987654321，東西壞掉了，原因是商品瑕疵"""


def _build_query_prompt(tool_call_obj: dict) -> list[dict]:
    user_text = (
        "tool_call:\n"
        + json.dumps(tool_call_obj, ensure_ascii=False)
        + "\n→ "
    )
    return [
        {"role": "system", "content": QUERY_GEN_SYSTEM},
        {"role": "user", "content": user_text},
    ]


# ==============================================================================
# 兩階段生成
# ==============================================================================

def _validate_args(args: dict, tool_def: dict) -> tuple[bool, str | None]:
    if not isinstance(args, dict):
        return False, "args_not_dict"
    try:
        jsonschema_validate(instance=args, schema=tool_def["parameters"])
    except ValidationError as e:
        return False, e.message
    return True, None


def generate_args(tool_def: dict, max_retries: int = 3) -> dict | None:
    """Step 1：用 LLM 生成符合 schema 的 args，最多重試 max_retries 次。"""
    messages = _build_args_prompt(tool_def)
    for attempt in range(max_retries):
        try:
            raw = llm(messages, temperature=0.9, top_p=0.95)
            obj = _extract_first_json(raw)
            if obj is None:
                continue
            ok, _ = _validate_args(obj, tool_def)
            if ok:
                return obj
        except requests.RequestException:
            time.sleep(1)
    return None


def generate_user_query(tool_call_obj: dict) -> str | None:
    """Step 2：給定 tool_call，用 LLM 反推自然 user query。"""
    messages = _build_query_prompt(tool_call_obj)
    try:
        text = llm(messages, temperature=1.0, top_p=0.95).strip()
        text = text.strip("「」\"' \n\t")
        return text or None
    except requests.RequestException:
        return None


# ==============================================================================
# 輔助：tool_call 字串、system prompt
# ==============================================================================

def tool_call(name: str, arguments: dict) -> str:
    """生成 assistant 應輸出的 tool_call JSON 字串。"""
    return json.dumps(
        {"type": "tool_call", "name": name, "arguments": arguments},
        ensure_ascii=False,
    )


def get_system_prompt() -> str:
    """訓練資料的 system prompt（含工具清單）。"""
    return "你是訂單客服助理。可用工具：" + json.dumps(TOOLS, ensure_ascii=False)


# ==============================================================================
# 組單筆訓練範例（兩階段 + 失敗重試）
# ==============================================================================

def make_example(tool_def: dict) -> dict | None:
    """
    給定一個 tool，跑兩階段生成；任何一階段失敗回傳 None。

    Returns:
        {"messages": [system, user, assistant tool_call]} 或 None
    """
    args = generate_args(tool_def)
    if args is None:
        return None

    tool_call_obj = {"type": "tool_call", "name": tool_def["name"], "arguments": args}
    user_text = generate_user_query(tool_call_obj)
    if not user_text:
        return None

    return {
        "messages": [
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": tool_call(tool_def["name"], args)},
        ]
    }


# ==============================================================================
# 主程式
# ==============================================================================

def main(num_examples: int = 200, seed: int = 7):
    random.seed(seed)

    out_dir = Path("lab3/out")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"目標 {num_examples} 筆，使用 vLLM 兩階段生成（{MODEL_NAME}）...")
    print(f"endpoint: {VLLM_URL}\n")

    data: list[dict] = []
    failures = 0
    attempts = 0
    target = num_examples

    while len(data) < target:
        attempts += 1
        tool_def = random.choice(TOOLS)
        ex = make_example(tool_def)
        if ex is None:
            failures += 1
            print(f"  [{attempts:4d}] {tool_def['name']:24s} ✗ (失敗，重抽)")
            continue
        data.append(ex)
        user_preview = ex["messages"][1]["content"][:40].replace("\n", " ")
        print(f"  [{attempts:4d}] {tool_def['name']:24s} ✓  {user_preview}")

    print(f"\n生成完成：{len(data)} 筆（嘗試 {attempts} 次，失敗 {failures} 次）")

    random.shuffle(data)
    split = int(len(data) * 0.8)
    train, valid = data[:split], data[split:]
    print(f"  Train: {len(train)} 筆")
    print(f"  Valid: {len(valid)} 筆")

    train_path = out_dir / "train.json"
    with open(train_path, "w", encoding="utf-8") as f:
        json.dump(train, f, ensure_ascii=False, indent=2)

    valid_path = out_dir / "valid.json"
    with open(valid_path, "w", encoding="utf-8") as f:
        json.dump(valid, f, ensure_ascii=False, indent=2)

    print(f"\n輸出：")
    print(f"  {train_path}")
    print(f"  {valid_path}")

    dist = Counter(
        json.loads(ex["messages"][-1]["content"])["name"] for ex in data
    )
    print("\nTool 分布：")
    for tool in TOOLS:
        print(f"  {tool['name']:28s} {dist.get(tool['name'], 0):4d}")

    print("\n第一筆範例：")
    print(json.dumps(data[0], ensure_ascii=False, indent=2))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="用 LLM 自動生成 SFT 訓練資料")
    parser.add_argument("--num", type=int, default=200, help="要生成的範例總數（預設 200）")
    parser.add_argument("--seed", type=int, default=7, help="隨機種子（預設 7）")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    main(num_examples=args.num, seed=args.seed)
