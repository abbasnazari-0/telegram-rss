#!/bin/bash

echo "=========================================================="
echo "🚀 Telegram RSS Generator - Full Auto Installer"
echo "=========================================================="

# ---------------------------
# 1) نصب Docker و Compose
# ---------------------------
if ! command -v docker &> /dev/null
then
    echo "🐳 Installing Docker..."
    apt update && apt install -y docker.io
fi

if ! command -v docker-compose &> /dev/null
then
    echo "📦 Installing docker-compose..."
    apt install -y docker-compose
fi

# ---------------------------
# 2) گرفتن اطلاعات کاربر
# ---------------------------
echo ""
echo "🔧 Enter your Telegram API details:"
read -p "API_ID: " API_ID
read -p "API_HASH: " API_HASH
read -p "PHONE (example: +9715xxxx): " PHONE

# ---------------------------
# 3) ساخت فایل config.json
# ---------------------------
cat <<EOF > config.json
{
  "API_ID": "$API_ID",
  "API_HASH": "$API_HASH",
  "PHONE": "$PHONE"
}
EOF

echo "✅ config.json created."

# ---------------------------
# 4) دانلود docker-compose.yml
# ---------------------------
echo "📥 Downloading docker-compose.yml..."

cat <<EOF > docker-compose.yml
version: "3.9"

services:
  telegram_rss:
    build: .
    container_name: telegram_rss
    restart: always
    ports:
      - "8000:8000"
    volumes:
      - ./media:/app/media
      - ./config.json:/app/config.json
      - ./session_name.session:/app/session_name.session
EOF

echo "✅ docker-compose.yml ready."

# ---------------------------
# 5) دانلود Dockerfile
# ---------------------------
cat <<EOF > Dockerfile
FROM python:3.10-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "app.py"]
EOF

echo "🛠 Dockerfile created."


# ---------------------------
# 6) دانلود requirements.txt
# ---------------------------
cat <<EOF > requirements.txt
fastapi
uvicorn[standard]
telethon
python-dotenv
EOF

echo "📦 requirements.txt downloaded."


# ---------------------------
# 7) دانلود فایل‌های برنامه (app.py و config manager)
# ---------------------------
echo "📥 Downloading main app files…"

curl -O https://raw.githubusercontent.com/abbasnazari-0/telegram-rss/main/app.py
curl -O https://raw.githubusercontent.com/abbasnazari-0/telegram-rss/main/config_manager.py

echo "✅ Python application downloaded."


# ---------------------------
# 8) اجرای docker-compose
# ---------------------------
echo ""
echo "🐳 Building & starting Docker container..."
docker-compose up --build -d

sleep 5

# ---------------------------
# 9) ورود به کانتینر برای Login Telethon
# ---------------------------
echo ""
echo "📲 Logging into Telegram account (Telethon)…"
echo "👉 Please enter the OTP code when asked."

docker exec -it telegram_rss python app.py

echo ""
echo "🔒 Login completed. Saving session…"

# ---------------------------
# 10) ری‌استارت نهایی
# ---------------------------
docker-compose restart

echo ""
echo "=========================================================="
echo "🎉 Installation Completed!"
echo "📡 Your API is now running at:"
echo ""
echo "👉 http://YOUR_SERVER_IP:8000"
echo "=========================================================="
