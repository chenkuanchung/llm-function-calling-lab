# 使用輕量級的 Python 3.11 映像檔作為基底
FROM python:3.11-slim

# 設定容器內的工作目錄
WORKDIR /app

# 將 requirements.txt 複製到容器內
COPY requirements.txt .

# 安裝所需套件 (加上 --no-cache-dir 可以讓映像檔更小)
RUN pip install --no-cache-dir -r requirements.txt

# 將當前目錄的所有程式碼複製到容器內的 /app 目錄下
COPY . .

# 設定容器啟動時執行的指令
CMD ["uvicorn", "lab5.app:app", "--host", "0.0.0.0", "--port", "9000"]