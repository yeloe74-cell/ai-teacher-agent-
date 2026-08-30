cat << 'EOF' > setup.sh
#!/bin/bash
# setup.sh
# AI Teacher Bot - Initial Setup Script

set -e

echo "========================================"
echo "AI Teacher Bot - Setup"
echo "========================================"

# System Package Update
echo "Updating system..."
sudo apt update && sudo apt upgrade -y

# Python setup
echo "Installing Python and Essentials..."
sudo apt install -y python3 python3-pip python3-venv git

# Directory path check (Dynamic Path Detection)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Virtual environment creation
echo "Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate

# Install default dependencies
echo "Installing dependencies..."
pip install --upgrade pip
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    pip install requests python-dotenv APScheduler
fi

# Create system directories
echo "Creating required directories..."
mkdir -p logs data migrations scripts modules

# Create .env template if not exists
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cat > .env << 'ENVEOF'
# Cloudflare Workers AI
CF_ACCOUNT_ID=your_account_id
CF_API_TOKEN=your_api_token
CF_AI_MODEL=@cf/meta/llama-3-8b-instruct

# Cloudflare D1
CF_D1_DATABASE_ID=

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHANNEL_ID=@your_channel

# Owner
OWNER_USER_ID=your_user_id

# Schedule
MORNING_POST_TIME=08:00
EVENING_POST_TIME=20:00
TIMEZONE=Asia/Yangon

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/app.log

# Database
DB_BACKEND=sqlite
SQLITE_DB_PATH=data/app.db

# API Timeouts
AI_TIMEOUT=60
TELEGRAM_TIMEOUT=30

# Retry
MAX_RETRY_ATTEMPTS=3
RETRY_DELAY=2.0
RETRY_BACKOFF=2.0

# Content
MAX_TOKENS_MORNING=1000
MAX_TOKENS_EVENING=800
TEMPERATURE=0.7

# Safety
AUTO_SHARE_DEFAULT=0
MAX_DAILY_SHARES_PER_GROUP=2
EMERGENCY_STOP=0
MAINTENANCE_MODE=0
ENVEOF
fi

echo ""
echo "========================================"
echo "✅ Setup Complete"
echo "========================================"
echo ""
echo "Next Steps:"
echo "1. Edit .env file with your credentials: nano .env"
echo "2. Deploy the bot: bash deploy.sh"
echo "========================================"
EOF

chmod +x setup.sh
git add setup.sh
git commit -m "Add updated setup.sh script"
git push origin main

