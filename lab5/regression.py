"""
==============================================================================
LAB 5：回歸測試腳本
==============================================================================

📌 本檔案功能：
    對部署的 API 執行回歸測試，確保改動沒有破壞原有功能。

📖 回歸測試的價值：
    1. 自動化：每次改動都能快速驗證
    2. 量化：用數字說話（哪些案例失敗、指標變化）
    3. 持續監控：可以整合到 CI/CD 流程

🔧 執行方式：
    1. 確保 API 服務運行中：uvicorn lab5.app:app --port 9000
    2. 執行測試：python -m lab5.regression

📂 輸出：
    lab5_deploy_regression/regression_trace.json
"""

import json
import requests
from pathlib import Path
import time


# ==============================================================================
# 設定
# ==============================================================================

# API 端點
API_URL = "http://localhost:9000/chat"

# 測試案例檔案（Lab2 的測試集）
EVAL_CASES_PATH = "../lab2/eval_cases.json"

# 輸出目錄
OUTPUT_DIR = Path("lab5_deploy_regression")


def load_test_cases(path: str) -> list:
    """
    載入測試案例
    
    Args:
        path: JSON 檔案路徑（內容為案例陣列）
        
    Returns:
        測試案例列表
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_test_case(case: dict, timeout: int = 120) -> dict:
    """
    執行單一測試案例
    
    Args:
        case: 測試案例字典
            {"id": "c1", "messages": [...], "expect": {...}}
        timeout: 請求超時時間（秒）
        
    Returns:
        測試結果字典
        {
            "id": str,
            "success": bool,
            "trace": dict,
            "error": str | None
        }
    """
    
    try:
        # 呼叫 API
        # 注意：只送 user messages，system prompt 由 server 補
        resp = requests.post(
            API_URL,
            json={"messages": case["messages"]},
            timeout=timeout
        )
        
        # 檢查 HTTP 狀態
        resp.raise_for_status()
        
        # 解析回應
        data = resp.json()
        
        return {
            "id": case["id"],
            "success": True,
            "trace": data.get("trace"),
            "messages": data.get("messages"),
            "error": None,
        }
        
    except requests.exceptions.Timeout:
        return {
            "id": case["id"],
            "success": False,
            "trace": None,
            "error": "Timeout"
        }
        
    except requests.exceptions.RequestException as e:
        return {
            "id": case["id"],
            "success": False,
            "trace": None,
            "error": str(e)
        }
    
    except Exception as e:
        return {
            "id": case["id"],
            "success": False,
            "trace": None,
            "error": str(e)
        }


def analyze_results(results: list, cases: list) -> dict:
    """
    分析測試結果
    
    Args:
        results: run_test_case 的結果列表
        cases: 原始測試案例（含 expect）
        
    Returns:
        分析報告
    """
    
    # 建立 case_id → expect 的對照表
    expect_map = {c["id"]: c.get("expect", {}) for c in cases}
    
    total = len(results)
    success_count = sum(1 for r in results if r["success"])
    
    # 統計工具選擇正確率
    tool_correct = 0
    tool_total = 0
    
    for r in results:
        if not r["success"]:
            continue
        
        trace = r.get("trace", {})
        steps = trace.get("steps", [])
        
        # 找到 tool_call 步驟
        pred_tool = None
        for step in steps:
            if "tool_call" in step:
                pred_tool = step["tool_call"].get("name")
                break
        
        expect = expect_map.get(r["id"], {})
        if "tool" in expect:
            tool_total += 1
            if pred_tool == expect["tool"]:
                tool_correct += 1
    
    return {
        "total": total,
        "success_count": success_count,
        "success_rate": success_count / max(1, total),
        "tool_total": tool_total,
        "tool_correct": tool_correct,
        "tool_accuracy": tool_correct / max(1, tool_total),
    }


def main():
    """
    主函式：執行回歸測試
    
    流程：
    1. 檢查 API 是否可用
    2. 載入測試案例
    3. 對每個案例呼叫 API
    4. 收集結果
    5. 分析並輸出報告
    """
    
    print("=" * 60)
    print("LAB5: 回歸測試")
    print("=" * 60)
    
    # ==========================================================================
    # Step 1: 檢查 API 是否可用
    # ==========================================================================
    print("\n[Step 1] 檢查 API...")
    
    try:
        resp = requests.get("http://localhost:9000/health", timeout=5)
        resp.raise_for_status()
        health = resp.json()
        print(f"  API 狀態：{health.get('status')}")
    except Exception as e:
        print(f"  錯誤：無法連接到 API - {e}")
        print("  請確保服務運行中：uvicorn lab5.app:app --port 9000")
        return
    
    # ==========================================================================
    # Step 2: 載入測試案例
    # ==========================================================================
    print("\n[Step 2] 載入測試案例...")
    
    if not Path(EVAL_CASES_PATH).exists():
        print(f"  錯誤：找不到 {EVAL_CASES_PATH}")
        return
    
    cases = load_test_cases(EVAL_CASES_PATH)
    print(f"  載入 {len(cases)} 個測試案例")
    
    # ==========================================================================
    # Step 3: 執行測試
    # ==========================================================================
    print("\n[Step 3] 執行測試...")
    
    results = []
    
    for i, case in enumerate(cases, 1):
        print(f"  [{i}/{len(cases)}] {case['id']}...", end=" ")
        
        start = time.time()
        result = run_test_case(case)
        elapsed = time.time() - start
        
        if result["success"]:
            print(f"✓ ({elapsed:.1f}s)")
        else:
            print(f"✗ ({result['error']})")
        
        results.append(result)
    
    # ==========================================================================
    # Step 4: 分析結果
    # ==========================================================================
    print("\n[Step 4] 分析結果...")
    
    analysis = analyze_results(results, cases)
    
    print(f"\n  總案例數：{analysis['total']}")
    print(f"  成功率：{analysis['success_rate']:.1%}")
    print(f"  工具選擇準確率：{analysis['tool_accuracy']:.1%}")
    
    # ==========================================================================
    # Step 5: 輸出報告
    # ==========================================================================
    print("\n[Step 5] 輸出報告...")
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    output_path = OUTPUT_DIR / "regression_trace.json"
    
    report = {
        "timestamp": time.time(),
        "analysis": analysis,
        "results": results,
    }
    
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    
    print(f"  報告已輸出：{output_path}")
    
    # ==========================================================================
    # 顯示失敗案例
    # ==========================================================================
    failed = [r for r in results if not r["success"]]
    
    if failed:
        print(f"\n失敗案例 ({len(failed)} 個)：")
        for r in failed[:5]:
            print(f"  - {r['id']}: {r['error']}")
        if len(failed) > 5:
            print(f"  ... 還有 {len(failed) - 5} 個")
    
    print("\n" + "=" * 60)
    print("回歸測試完成！")
    print("=" * 60)


# ==============================================================================
# 程式進入點
# ==============================================================================
if __name__ == "__main__":
    main()
