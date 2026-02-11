#!/bin/bash
# Setup script for ECC Sheet application

set -e

echo "==================================="
echo "ECC Sheet Application Setup"
echo "==================================="
echo ""

# Check if UV is installed
if ! command -v uv &> /dev/null; then
    echo "UV is not installed. Installing UV..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo ""
    echo "UV installed successfully!"
    echo "Please restart your terminal and run this script again."
    exit 0
fi

echo "UV is installed"
echo ""

# Check if Bun is installed
if ! command -v bun &> /dev/null; then
    echo "Bun is not installed. Installing Bun..."
    curl -fsSL https://bun.sh/install | bash
    echo ""
    echo "Bun installed successfully!"
    echo "Please restart your terminal and run this script again."
    exit 0
fi

echo "Bun is installed"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
uv venv
echo "Virtual environment created"
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate
echo "Virtual environment activated"
echo ""

# Install Python dependencies
echo "Installing Python dependencies..."
uv sync
echo "Python dependencies installed"
echo ""

# Install frontend dependencies
echo "Installing frontend dependencies..."
bun install
echo "Frontend dependencies installed"
echo ""

# Build frontend assets
echo "Building frontend assets..."
bun run build
echo "Frontend assets built"
echo ""

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from example..."
    if [ -f .env.example ]; then
        cp .env.example .env
    else
        cat > .env << 'EOF'
# Required
SECRET_KEY=change-this-to-a-random-secret-key
DATABASE_URL=sqlite:///ecc_sheet.db
USER_NAME=Admin

# Admin access (comma-separated list)
ADMIN_USERS=Admin

# Email Configuration (for reports)
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_USERNAME=user@example.com
EMAIL_PASSWORD=your-app-password
EMAIL_RECIPIENT=recipient@example.com

# Optional
TIMEZONE=America/New_York
PORT=5000
EOF
    fi
    echo ""
    echo "Please edit .env file with your configuration before running the app!"
    echo "Make sure to set the following variables:"
    echo "  - SECRET_KEY: A random secret key"
    echo "  - EMAIL_HOST, EMAIL_USERNAME, EMAIL_PASSWORD: SMTP settings"
    echo "  - EMAIL_RECIPIENT: Default recipient for reports"
    echo "  - ADMIN_USERS: Comma-separated list of admin usernames"
    echo ""
else
    echo ".env file already exists"
    echo ""
fi

# Apply database migrations
echo "Applying database migrations..."
uv run flask --app backend.app db upgrade
echo "Database migrations applied"
echo ""

echo "==================================="
echo "Setup Complete!"
echo "==================================="
echo ""
echo "Next steps:"
echo "1. Edit .env file with your configuration"
echo "2. Activate the virtual environment: source .venv/bin/activate"
echo "3. Run the application: uv run python -m backend.app"
echo ""
echo "The app will be available at http://localhost:5000"
echo ""
