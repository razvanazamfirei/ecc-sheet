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

# Install dependencies
echo "Installing dependencies..."
uv pip install -e .
echo "Dependencies installed"
echo ""

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from example..."
    cp .env.example .env
    echo ""
    echo "Please edit .env file with your configuration before running the app!"
    echo "Make sure to set the following variables:"
    echo "EMAIL_USERNAME: Your email address"
    echo "EMAIL_PASSWORD: Your email app password"
    echo "EMAIL_RECIPIENT: Recipient email address"
    echo "SECRET_KEY: A random secret key"
    echo ""
else
    echo ".env file already exists"
    echo ""
fi

echo "==================================="
echo "Setup Complete!"
echo "==================================="
echo ""
echo "Next steps:"
echo "1. Edit .env file with your configuration"
echo "2. Activate the virtual environment: source .venv/bin/activate"
echo "3. Run the application: uv run python run.py"
echo ""
echo "The app will be available at http://localhost:5000"
echo ""
