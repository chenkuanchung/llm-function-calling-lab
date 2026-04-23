# 🤖 Order CS AI Agent: End-to-End Function Calling & MLOps 實作

這是一個基於 **Qwen2.5-3B** 模型開發的訂單客服 AI 助理系統。本專案不僅實現了高度精準的 **Function Calling (Tool Use)**，更涵蓋了從數據合成、LoRA 微調、到生產級 API 封裝與 CI/CD 評估的完整生命週期。

## 🌟 專案核心亮點

本專案將原本脆弱的 LLM 輸出轉化為強韌的企業級服務，核心技術包括：
- **兩階段數據合成**：利用大模型自動化生成具備多樣性與長尾分佈的 SFT 訓練資料。
- **LoRA 格式微調**：針對 JSON Schema 遵循能力進行特定任務微調，大幅提升工具呼叫成功率。
- **生產級 API 封裝**：整合 FastAPI、Rate Limiting、結構化日誌 (Structured Logging) 與自動重試機制。
- **自動化回歸評估**：建立 CI/CD 守門員機制，透過量化指標（Success Rate, Tool Accuracy）防止模型效能退化。

---

## 🛠️ 技術棧 (Tech Stack)

- **核心模型**：Qwen2.5-3B (Base Model)
- **推理引擎**：vLLM (OpenAI-compatible API)
- **微調技術**：LoRA (PEFT), Hugging Face Trainer
- **後端架構**：FastAPI, Pydantic v2, SlowAPI (限流), Structlog (結構化日誌)
- **環境部署**：Docker (Containerization)
- **品管系統**：JSON Schema Validation, CI/CD Regression Testing

---

## 📂 專案架構與開發階段

專案分為五個核心實驗室 (Labs)，逐步構建完整的 AI 代理服務：

### [Lab 1] 基礎工具定義 (Function Calling Foundation)
- 定義 11 種客服專用工具（如 `get_order_status`, `apply_coupon`, `cancel_order` 等）。
- 撰寫精準的 JSON Schema 與 System Prompt，建立基本的 Tool-Use 邏輯。

### [Lab 2] 自動化評估系統 (Evaluation System)
- 捨棄手動測試，建立自動化評估腳本。
- 定義量化指標，對基礎模型進行基準線 (Baseline) 測試。

### [Lab 3] 數據合成工程 (Synthetic Data Engineering)
- 實作兩階段生成策略：首先生成情境描述，再由模型轉化為對話樣本。
- 透過負面案例 (Negative Samples) 強化模型的邊界判斷能力。

### [Lab 4] LoRA 模型微調 (LoRA Fine-tuning)
- 執行 LoRA 微調，讓模型學會嚴格遵循 JSON 輸出規則。
- 在維持推理速度的前提下，顯著提升模型在特定垂直領域的精準度。

### [Lab 5] 生產級部署與防護 (Production Deployment & Guardrails)
- **FastAPI 封裝**：提供標準 HTTP API 介面。
- **隱形重試 (Auto-Retry)**：內部消化 LLM 格式錯誤，自動反饋重試，顯著提升系統穩定性。
- **安全防護**：實作 Rate Limiting 與健康檢查端點（Health Check）。
- **CI/CD 守門員**：實作比較腳本，確保每一次更動不會導致系統指標下降。

---

## 🎓 致謝與來源 (Credits)

本專案之原始教學素材與課程架構源自 **群聯電子 (Phison) 陳界安老師 (Alkalid)**。
- **課程來源**：[2026_ai_rookie_course7](https://github.com/Alkalid/2026_ai_rookie_course7)
- **特別感謝**：感謝陳界安老師在 AI 新秀計畫中提供的深度技術指導與專業教材。

---
