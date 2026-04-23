import json

# 1. 載入上一次的滿分紀錄（基準線）
# 假設你已經把剛剛 100% 的檔案改名存成 baseline.json
try:
    with open("lab5_deploy_regression/baseline.json") as f:
        baseline = json.load(f)
except FileNotFoundError:
    print("找不到 baseline.json，請先將一份成績複製並改名為 baseline.json")
    exit()

# 2. 載入你剛剛改完程式碼後，最新跑出來的結果
with open("lab5_deploy_regression/regression_trace.json") as f:
    current = json.load(f)

# 3. 比較整體成功率
base_acc = baseline["analysis"]["success_rate"]
curr_acc = current["analysis"]["success_rate"]
diff = curr_acc - base_acc

print(f"上次成功率：{base_acc:.1%}")
print(f"本次成功率：{curr_acc:.1%}")

if diff > 0:
    print(f"✅ 系統進步了！上升 {diff:.1%}")
elif diff < 0:
    print(f"❌ 警告：系統退化了！下降 {abs(diff):.1%}")
else:
    print("➖ 系統保持穩定無變化。")

# 4. 找出具體是哪一題壞掉？
print("\n🔍 案例差異分析：")
for base_res, curr_res in zip(baseline["results"], current["results"]):
    if base_res["success"] and not curr_res["success"]:
        print(f"  ⚠️ 案例 {curr_res['id']} 原本會過，現在壞掉了！")
        print(f"     錯誤原因: {curr_res['error']}")