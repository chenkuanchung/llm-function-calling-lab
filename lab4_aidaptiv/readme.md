# Lab4（aiDAPTIV2 路線）：Docker 內微調流程

## 目的

在**已裝好 aiDAPTIV2 / Phison** 容器環境的前提下，把 `lab4_aidaptiv` 裡的**環境、實驗、資料集設定檔**複製進容器指定位置，用官方 **`phisonai2`** 跑一輪微調。這條路跟主線 `lab4/lab4.py`（本機 TRL + SFTTrainer）**不一樣**，課程要求擇一或兩個都做。

## 學習目標

- 熟悉 **Docker Compose** 啟動服務、進入容器、在容器內執行訓練指令的完整順序。
- 能對照 `env_config.yaml`、`exp_config.yaml`、`QA_dataset_config.yaml` 理解「環境／實驗／資料」分層設定。
- 當指令失敗時，會用 `docker compose ps`、`logs` 排查服務是否起來、路徑是否正確。

## 前置準備（請逐項確認）

1. **Docker Desktop**（或等效）已安裝且**引擎正在執行**（Windows 須開啟 Docker Desktop）。
2. 終端機先 `cd` 到這個資料夾：  
   `.../2026_ai_rookie_course4/lab4_aidaptiv`
3. 已依助教說明取得 **aiDAPTIV2 映像檔／授權**；若映像需額外登入或拉取，請先完成。
4. 資料檔：`train.json`、`input.json` 等需符合 `QA_dataset_config.yaml` 內路徑與格式；若你更動檔名或欄位，請**同步修改 yaml**，否則容器內訓練會讀不到資料。

## 標準執行順序（必須遵守）

**順序一定是：先 `docker compose up`，再進容器執行訓練指令。**

### 1) 啟動容器（背景）

在 `lab4_aidaptiv` 執行：

```bash
docker compose up -d
```

- `-d`：背景執行。若想先看啟動 log，可改用不加 `-d` 的 `docker compose up`，再以 Ctrl+C 結束後改 `-d`。
- 確認服務狀態：

```bash
docker compose ps
```

應看到服務為 `running`（或 healthy，視 compose 定義而定）。若 `Exit` 或重啟循環，請看下一節「常見問題」。

### 2) 進入容器

依目前 `docker-compose.yaml`，服務名稱為 `aidaptiv_fine_tune`：

```bash
docker compose exec aidaptiv_fine_tune bash
```

若你改過服務名稱，請以 `docker compose ps` 的 **NAME** 或 **SERVICE** 欄為準。

### 3) 在容器內複製設定並執行訓練

進入容器後執行（路徑以映像內實際目錄為準，若與下列不同請依助教文件調整）：

```bash
cp /workspace/env_config.yaml /home/root/aiDAPTIV2/commands/env_config/
cp /workspace/exp_config.yaml /home/root/aiDAPTIV2/commands/exp_config/
cp /workspace/QA_dataset_config.yaml /home/root/aiDAPTIV2/commands/dataset_config/text-generation/

cd /home/root/aiDAPTIV2/commands/
phisonai2 --env_config ./env_config/env_config.yaml --exp_config ./exp_config/exp_config.yaml
```

說明：

- 第一個 `cp` 是把**掛進容器的** `/workspace/`（通常就是你電腦上的 `lab4_aidaptiv`）裡的 yaml 複製到 aiDAPTIV2 要讀的位置。
- `phisonai2` 會依兩個 yaml 合併決定裝置、訓練參數與資料；**錯誤的相對路徑**是常見失敗原因。

### 4) 檢查產物

- 訓練 log、checkpoint 輸出目錄請依 `exp_config.yaml` 與助教說明查看（可能在容器內某 `output` 或掛載資料夾）。
- 若需把權重拷回本機，請用 `docker cp` 或已掛載的 volume 路徑取出。

## 常見問題

| 現象 | 可能原因與處理 |
|------|----------------|
| `Cannot connect to the Docker daemon` | Docker 未啟動；請開啟 Docker Desktop 或系統 docker 服務。 |
| `service ... is not running` | 未執行 `docker compose up -d`，或 compose 啟動失敗；執行 `docker compose ps`、`docker compose logs`（可加服務名）查看錯誤。 |
| `docker compose exec` 失敗 | 服務名稱打錯或容器已退出；以 `docker compose ps` 確認。 |
| `phisonai2` 找不到資料或格式錯誤 | 檢查 `QA_dataset_config.yaml` 內檔案路徑是否在容器內存在；`train.json` 欄位是否符合工具要求。 |
| `cp: cannot stat '/workspace/...'` | volume 沒掛到你預期的專案資料夾；檢查 `docker-compose.yaml` 的 `volumes` 與本機路徑。 |

## 與主線 Lab4 的關係

- **`lab4/lab4.py`**：以 Hugging Face **TRL + PEFT** 在本機（或同一 GPU 環境）直接跑 `SFTTrainer`。
- **`lab4_aidaptiv`**：以廠商／計畫提供的 **aiDAPTIV2** 管線在容器內跑；兩者**設定檔格式不同**，但課程目標同是「完成一次可重現的微調流程」。

## 完成定義

- 容器可穩定處於 running，且 `phisonai2` 能跑完或達到課堂指定 step，並能在指定目錄找到輸出；書面記錄使用的 yaml 版本與任何路徑修改。
