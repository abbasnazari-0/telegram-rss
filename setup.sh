#!/bin/bash

echo "🚀 Telegram RSS Generator Installer"

# درخواست مقادیر
read -p "Enter Telegram API_ID: " API_ID
read -p "Enter Telegram API_HASH: " API_HASH
read -p "Enter Telegram PHONE: " PHONE

# ساخت config.json
cat <<EOF > config.json
{
  "API_ID": "$API_ID",
  "API_HASH": "$API_HASH",
  "PHONE": "$PHONE"
}
EOF

echo "✅ config.json created."

# نصب docker در صورت نبود
if ! command -v docker &> /dev/null
then
    echo "🐳 Docker not found. Installing..."
    apt update && apt install -y docker.io docker-compose
fi

echo "🐳 Running docker-compose..."
docker-compose up --build -d

echo ""
echo "🎉 Installation finished!"
echo "API is running at: http://YOUR_SERVER_IP:8000"
