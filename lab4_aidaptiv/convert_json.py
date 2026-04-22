import json

# 讀取原始 JSON
with open("input.json", "r", encoding="utf-8") as f:
    data = json.load(f)

new_data = []
for item in data:
    new_item = {
        "id": item.get("id"),
        "question": "",
        "answer": "",
        "topic": item.get("topic"),
        "language": item.get("language")
    }
    # 提取 user 和 assistant 的內容
    messages = item.get("messages", [])
    for msg in messages:
        if msg.get("role") == "user":
            new_item["question"] = msg.get("content", "")
        elif msg.get("role") == "assistant":
            new_item["answer"] = msg.get("content", "")
    new_data.append(new_item)

# 輸出新的 JSON
with open("output.json", "w", encoding="utf-8") as f:
    json.dump(new_data, f, ensure_ascii=False, indent=4)