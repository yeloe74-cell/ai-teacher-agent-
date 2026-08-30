#!/bin/bash
# ============================================================
# AI Teacher Agent - Universal Deployment Script
# Works on: VPS (Ubuntu/Debian) & Cloud PaaS (JustRunMyApp/Docker)
# ============================================================

set -e

# Project Root Directory ကို အလိုအလျောက် ရယူခြင်း
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}🚀 AI Teacher Agent - Universal Deploy${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}📁 Directory: $PROJECT_DIR${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Check if running as root
check_root() {
    if [ "$(id -u)" -eq 0 ]; then
        IS_ROOT=true
    else
        IS_ROOT=false
    fi
}

# Check Python version
check_python() {
    print_info "Checking Python..."
    
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
        print_success "Python $PYTHON_VERSION found"
        
        # Check if Python 3.8+
        PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f1)
        PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f2)
        
        if [ "$PYTHON_MAJOR" -lt 3 ] || [ "$PYTHON_MAJOR" -eq 3 -a "$PYTHON_MINOR" -lt 8 ]; then
            print_error "Python 3.8+ is required"
            exit 1
        fi
    else
        print_error "Python 3 not found"
        exit 1
    fi
}

# Check disk space
check_disk_space() {
    print_info "Checking disk space..."
    
    AVAILABLE=$(df -m "$PROJECT_DIR" | tail -1 | awk '{print $4}')
    
    if [ "$AVAILABLE" -lt 200 ]; then
        print_warning "Low disk space: ${AVAILABLE}MB available"
        print_warning "Bot may fail if disk is full"
    else
        print_success "Disk space OK: ${AVAILABLE}MB available"
    fi
}

# Check internet connectivity
check_internet() {
    print_info "Checking internet connectivity..."
    
    if ping -c 1 -W 3 telegram.org >/dev/null 2>&1; then
        print_success "Internet connected"
    else
        print_warning "Cannot reach telegram.org — check network"
    fi
}

# Create required directories
create_directories() {
    print_info "Creating required directories..."
    
    mkdir -p logs
    mkdir -p data
    mkdir -p migrations
    mkdir -p scripts
    mkdir -p modules
    
    print_success "Directories created"
}

# Setup virtual environment
setup_venv() {
    print_info "Setting up virtual environment..."
    
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        print_success "Virtual environment created"
    else
        print_success "Virtual environment already exists"
    fi
    
    print_info "Activating virtual environment..."
    source venv/bin/activate
}

# Install dependencies
install_dependencies() {
    print_info "Installing dependencies..."
    
    pip install --upgrade pip --quiet 2>/dev/null || print_warning "pip upgrade failed"
    
    if [ -f "requirements.txt" ]; then
        # Count requirements
        REQ_COUNT=$(grep -c "^[a-zA-Z]" requirements.txt 2>/dev/null || echo "0")
        print_info "Found $REQ_COUNT dependencies in requirements.txt"
        
        if pip install -r requirements.txt --quiet 2>/dev/null; then
            print_success "Dependencies installed"
        else
            print_error "Dependency installation failed"
            print_warning "Trying individual installs..."
            
            while IFS= read -r line; do
                if [ -n "$line" ] && [[ ! "$line" =~ ^# ]]; then
                    print_info "Installing: $line"
                    pip install "$line" --quiet 2>/dev/null || print_warning "Failed: $line"
                fi
            done < requirements.txt
        fi
    else
        print_warning "requirements.txt not found — installing defaults..."
        pip install requests python-dotenv APScheduler --quiet 2>/dev/null
    fi
}

# Check .env file
check_env_file() {
    print_info "Checking .env file..."
    
    if [ -f ".env" ]; then
        # Check required variables
        REQUIRED_VARS=("CF_ACCOUNT_ID" "CF_API_TOKEN" "TELEGRAM_BOT_TOKEN" "TELEGRAM_CHANNEL_ID" "OWNER_USER_ID")
        MISSING_VARS=()
        
        for VAR in "${REQUIRED_VARS[@]}"; do
            if ! grep -q "^$VAR=" .env 2>/dev/null; then
                MISSING_VARS+=("$VAR")
            fi
        done
        
        if [ ${#MISSING_VARS[@]} -eq 0 ]; then
            print_success ".env file found with all required variables"
        else
            print_warning ".env file is missing: ${MISSING_VARS[*]}"
            print_warning "Bot may not start correctly"
        fi
    else
        print_warning ".env file not found"
        print_info "Creating .env from example..."
        
        if [ -f ".env.example" ]; then
            cp .env.example .env
            print_success "Created .env from .env.example"
            print_warning "Edit .env file with your credentials!"
        else
            print_warning "No .env.example found — create .env manually"
        fi
    fi
}

# Run migrations
run_migrations() {
    print_info "Running database migrations..."
    
    if [ -f "scripts/run_migrations.py" ]; then
        if python scripts/run_migrations.py; then
            print_success "Migrations completed"
        else
            print_warning "Migration had warnings — continuing"
        fi
    else
        print_warning "Migration script not found"
    fi
}

# Setup systemd service
setup_systemd() {
    print_info "Configuring systemd service..."
    
    SERVICE_NAME="ai-teacher-bot"
    SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
    
    cat << EOF > "$SERVICE_FILE"
[Unit]
Description=AI Teacher Bot Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
EnvironmentFile=$PROJECT_DIR/.env

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME" 2>/dev/null
    systemctl restart "$SERVICE_NAME" 2>/dev/null
    
    print_success "systemd service configured"
}

# Test bot configuration
test_bot() {
    print_info "Testing bot configuration..."
    
    # Quick import test
    if python -c "from config import get_config; config = get_config(); print('Config OK')" 2>/dev/null; then
        print_success "Config module loads correctly"
    else
        print_error "Config module failed to load"
        return 1
    fi
    
    # Check database connection
    if python -c "from database import SQLiteDatabase; db = SQLiteDatabase(); db.close(); print('Database OK')" 2>/dev/null; then
        print_success "Database works"
    else
        print_warning "Database check failed"
    fi
    
    return 0
}

# Show post-deployment info
show_info() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${GREEN}✅ Deployment Complete!${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    echo -e "${BLUE}Useful Commands:${NC}"
    echo "  Status  : systemctl status ai-teacher-bot"
    echo "  Restart : systemctl restart ai-teacher-bot"
    echo "  Stop    : systemctl stop ai-teacher-bot"
    echo "  Logs    : journalctl -u ai-teacher-bot -f"
    echo ""
    echo -e "${BLUE}========================================${NC}"
}

# Direct run (non-systemd)
run_direct() {
    print_info "Starting bot directly..."
    echo ""
    exec python main.py
}

# Main execution
main() {
    print_header
    echo ""
    
    # Pre-flight checks
    check_root
    check_python
    check_disk_space
    check_internet
    echo ""
    
    # Setup
    create_directories
    setup_venv
    install_dependencies
    check_env_file
    run_migrations
    echo ""
    
    # Test
    test_bot || print_warning "Bot test had issues — continuing"
    echo ""
    
    # Deploy
    if [ "$IS_ROOT" = true ] && command -v systemctl >/dev/null 2>&1 && [ -d "/etc/systemd/system" ]; then
        setup_systemd
        echo ""
        show_info
    else
        print_info "Non-root or no systemd — running directly"
        run_direct
    fi
}

# Run main
main "$@"
