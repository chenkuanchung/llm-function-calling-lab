"""
==============================================================================
LAB 2：Function Calling 評估
==============================================================================

📌 本檔案功能：
    1. 讀取 eval_cases.json 測試案例
    2. 對每個案例呼叫 LLM 進行推論
    3. 計算評估指標（格式合法率、工具選擇準確率、參數相符率）
    4. 輸出評估報告

📖 執行方式：
    python -m lab2.eval

📊 輸出：
    - 終端機顯示評估結果摘要
    - lab2_evaluation/eval_report.json（詳細報告）

🔍 學習重點：
    本檔案有三處 TODO，請依序完成：
    - TODO 1：實作工具選擇正確性判斷
    - TODO 2：實作參數完全相符判斷
    - TODO 3：用 try/except 處理 JSON 提取與解析失敗
"""

import json
from pathlib import Path

from jsonschema import validate as jsonschema_validate
from jsonschema.exceptions import ValidationError

from common.call_llm import call_llm
from common.prompts import system_prompt
from common.tool_schema import TOOLS
from common.utils import extract_json_block


# ==============================================================================
# 工具索引：name → tool_definition
# 用於驗證 LLM 輸出的工具名稱是否合法
# ==============================================================================
TOOL_INDEX = {t["name"]: t for t in TOOLS}


# ==============================================================================
# Step 1: 驗證 tool_call 格式
# ==============================================================================

def validate_tool_call(tool_call: dict) -> tuple[bool, str | None]:
    """
    驗證 LLM 輸出的 tool_call 是否合法
    
    依序執行以下檢查：
      1. tool_call 是否為 dict
      2. type 是否為 "tool_call"
      3. name 是否是已知工具
      4. arguments 是否為 dict
      5. arguments 是否符合該工具的 JSON Schema

    Returns:
        (True, None)          → 驗證通過
        (False, "錯誤說明")   → 驗證失敗
    """
    if not isinstance(tool_call, dict):
        return False, "tool_call_not_object"

    if tool_call.get("type") != "tool_call":
        return False, "type_must_be_tool_call"

    name = tool_call.get("name")
    if name not in TOOL_INDEX:
        return False, f"unknown_tool:{name}"

    args = tool_call.get("arguments")
    if not isinstance(args, dict):
        return False, "arguments_must_be_object"

    schema = TOOL_INDEX[name]["parameters"]
    try:
        jsonschema_validate(instance=args, schema=schema)
    except ValidationError as e:
        return False, f"schema_error:{e.message}"

    return True, None


# ==============================================================================
# Step 2: 評估指標函式
# ==============================================================================

def tool_selection_correct(pred_tool: str | None, expect: dict) -> bool:
    """
    判斷工具選擇是否正確

    判斷邏輯：
      - expect 有 "tool" → 比對 pred_tool 是否等於 expect["tool"]
      - expect 沒有 "tool" → pred_tool 應該是 None（不呼叫任何工具）

    Args:
        pred_tool: LLM 預測的工具名稱（或 None）
        expect:    測試案例的 expect 欄位

    Returns:
        True 表示選擇正確

    範例：
        tool_selection_correct("get_order_status", {"tool": "get_order_status"}) → True
        tool_selection_correct(None, {"should_ask_clarification": True})         → True
        tool_selection_correct("track_shipment", {"tool": "get_order_status"})   → False
    """
    # -------------------------------------------------------------------------
    # TODO 1：實作工具選擇正確性判斷
    #
    # 提示：
    #   if "tool" in expect:
    #       ...（比對工具名稱）
    #   ...（沒有 "tool" 時，pred_tool 應為 None）
    # -------------------------------------------------------------------------
    raise NotImplementedError("TODO 1：請實作 tool_selection_correct")


def args_exact_match(pred_args: dict | None, expect: dict) -> bool:
    """
    判斷預測的參數是否與期望完全相符

    判斷邏輯：
      - expect 有 "arguments" → 直接比對 pred_args == expect["arguments"]
      - expect 沒有 "arguments" → pred_args 應該是 None

    Args:
        pred_args: LLM 預測的參數字典（或 None）
        expect:    測試案例的 expect 欄位

    Returns:
        True 表示參數完全相符

    範例：
        args_exact_match({"order_id": "A123456789"}, {"arguments": {"order_id": "A123456789"}}) → True
        args_exact_match({"order_id": "A999999999"}, {"arguments": {"order_id": "A123456789"}}) → False
    """
    # -------------------------------------------------------------------------
    # TODO 2：實作參數完全相符判斷
    #
    # 提示：
    #   if "arguments" not in expect:
    #       ...（沒有預期參數，pred_args 應為 None）
    #   ...（有預期參數，直接比對）
    # -------------------------------------------------------------------------
    raise NotImplementedError("TODO 2：請實作 args_exact_match")


# ==============================================================================
# Step 3: 對單一案例執行 LLM 推論
# ==============================================================================

def run_one(case: dict) -> dict:
    """
    對單一測試案例執行 LLM 推論，回傳預測結果

    流程：
      1. 組合 messages（system prompt + 測試案例的 messages）
      2. 呼叫 LLM
      3. 提取 JSON（tool_call）
      4. 驗證格式

    Returns:
        {
            "raw":       str,        # LLM 原始輸出（供除錯用）
            "tool":      str | None, # 預測的工具名稱
            "arguments": dict | None,# 預測的參數
            "valid":     bool,       # tool_call 格式是否合法
            "error":     str | None  # 驗證錯誤訊息
        }
    """
    messages = [{"role": "system", "content": system_prompt()}] + case["messages"]
    out = call_llm(messages)

    pred = {
        "raw": out,
        "tool": None,
        "arguments": None,
        "valid": False,
        "error": None,
    }

    # -------------------------------------------------------------------------
    # TODO 3：從 LLM 輸出中提取 JSON，並處理解析失敗的情況
    #
    # LLM 有可能輸出格式破損的 JSON（例如少了括號、多了說明文字），
    # 這時 extract_json_block 會回傳 None，應視為「無法解析」。
    #
    # 請用 try/except 包住提取與驗證邏輯：
    #
    #   try:
    #       tool_call = extract_json_block(out)
    #       if tool_call is None:
    #           return pred   # LLM 沒有輸出 JSON（追問或直接回答，屬正常情況）
    #       ok, err = validate_tool_call(tool_call)
    #       pred["tool"]      = tool_call.get("name")
    #       pred["arguments"] = tool_call.get("arguments")
    #       pred["valid"]     = ok
    #       pred["error"]     = err
    #   except Exception as e:
    #       pred["error"] = f"json_parse_error:{e}"
    # -------------------------------------------------------------------------
    raise NotImplementedError("TODO 3：請加入 try/except 處理 JSON 提取與解析失敗")

    return pred


# ==============================================================================
# Step 4: 主流程
# ==============================================================================

def main():
    print("=" * 60)
    print("LAB2: Function Calling 評估")
    print("=" * 60)

    # --------------------------------------------------------------------------
    # 載入測試案例
    # eval_cases.json 的格式：標準 JSON 陣列，每個元素是一個案例
    # --------------------------------------------------------------------------
    cases_path = Path(__file__).parent / "eval_cases.json"
    if not cases_path.exists():
        print(f"錯誤：找不到 {cases_path}")
        return

    with open(cases_path, encoding="utf-8") as f:
        cases = json.load(f)

    print(f"載入 {len(cases)} 個測試案例\n開始評估...")

    # --------------------------------------------------------------------------
    # 對每個案例執行推論並計算指標
    # --------------------------------------------------------------------------
    rows = []
    for c in cases:
        pred = run_one(c)
        expect = c["expect"]

        row = {
            "id": c["id"],
            "valid": pred["valid"],
            "pred_tool": pred["tool"],
            "pred_args": pred["arguments"],
            "expect": expect,
            "tool_ok": tool_selection_correct(pred["tool"], expect),
            "args_ok": (
                args_exact_match(pred["arguments"], expect)
                if "arguments" in expect
                else None
            ),
        }
        rows.append(row)

    # --------------------------------------------------------------------------
    # 計算彙總統計
    # --------------------------------------------------------------------------
    n = len(rows)

    valid_rate = sum(1 for r in rows if r["valid"]) / n
    tool_acc = sum(1 for r in rows if r["tool_ok"]) / n
    args_cases = [r for r in rows if r["args_ok"] is not None]
    args_exact = (
        sum(1 for r in args_cases if r["args_ok"]) / len(args_cases)
        if args_cases else 0.0
    )

    summary = {
        "n": n,
        "valid_rate": round(valid_rate, 4),
        "tool_acc": round(tool_acc, 4),
        "args_exact": round(args_exact, 4),
    }

    # --------------------------------------------------------------------------
    # 輸出報告
    # --------------------------------------------------------------------------
    out_dir = Path("lab2_evaluation")
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "eval_report.json"

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rows": rows}, f, ensure_ascii=False, indent=2)

    # --------------------------------------------------------------------------
    # 顯示結果
    # --------------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("評估結果")
    print("=" * 60)
    print(f"總案例數：{n}")
    print(f"格式合法率     (valid_rate)：{valid_rate:.1%}")
    print(f"工具選擇準確率   (tool_acc)：{tool_acc:.1%}")
    print(f"參數完全相符率 (args_exact)：{args_exact:.1%}")
    print("=" * 60)
    print(f"詳細報告：{report_path}")

    # 顯示失敗案例（最多顯示 5 個）
    failed = [r for r in rows if not r["tool_ok"] or r["args_ok"] is False]
    if failed:
        print(f"\n失敗案例（{len(failed)} 個）：")
        for r in failed[:5]:
            print(f"  [{r['id']}] tool_ok={r['tool_ok']}, args_ok={r['args_ok']}")
            print(f"    預測：tool={r['pred_tool']}, args={r['pred_args']}")
            print(f"    期望：{r['expect']}")
        if len(failed) > 5:
            print(f"  ... 還有 {len(failed) - 5} 個")


if __name__ == "__main__":
    main()
