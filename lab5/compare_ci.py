import json
import sys

BASELINE_PATH = "lab5_deploy_regression/baseline.json"
CURRENT_PATH = "lab5_deploy_regression/regression_trace.json"

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ 找不到檔案: {path}")
        sys.exit(1)

def main():
    print("=" * 60)
    print("📊 執行 CI/CD 嚴格回歸分析 (Success Rate Check)")
    print("=" * 60)

    base_data = load_json(BASELINE_PATH)
    curr_data = load_json(CURRENT_PATH)

    # 直接從 regression.py 產出的 analysis 區塊讀取成功率
    base_rate = base_data.get("analysis", {}).get("success_rate", 0.0)
    curr_rate = curr_data.get("analysis", {}).get("success_rate", 0.0)
    
    # 另外計算個別案例的 success 總數作為雙重檢查
    base_success_count = sum(1 for r in base_data.get("results", []) if r.get("success") is True)
    curr_success_count = sum(1 for r in curr_data.get("results", []) if r.get("success") is True)
    
    total_cases = base_data.get("analysis", {}).get("total", 1)
    
    # 重新計算實際成功率 (避免 analysis 區塊沒更新)
    actual_curr_rate = curr_success_count / total_cases

    diff = actual_curr_rate - base_rate

    print(f"指標：系統總體成功率 (Success Rate)")
    print(f"基準線 (Baseline): {base_rate:.1%}")
    print(f"目前測試 (Current) : {actual_curr_rate:.1%}")
    
    if diff < 0:
        print(f"差異 (Diff)       : ❌ {diff:.1%} (下降！)")
        print("-" * 60)
        print("🚨 [CI/CD 阻斷] 偵測到模型能力下降，拒絕部署！")
        sys.exit(1) # 讓 CI 亮紅燈
    else:
        diff_str = f"+{diff:.1%}" if diff > 0 else "0.0%"
        print(f"差異 (Diff)       : ✅ {diff_str}")
        print("-" * 60)
        print("🚀 [CI/CD 放行] 效能穩定，允許部署。")
        sys.exit(0)

if __name__ == "__main__":
    main()