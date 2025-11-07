#!/bin/bash

# Chrome Remote Debugging Launcher for TruMedia Scraping
# This script launches Chrome with remote debugging enabled

# Configuration
DEBUG_PORT=9222
USER_DATA_DIR="$HOME/.chrome-debug-profile"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== TruMedia Chrome Debug Launcher ===${NC}\n"

# Check if Chrome is already running on the debug port
if lsof -Pi :$DEBUG_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}Chrome is already running on port $DEBUG_PORT${NC}"
    echo "You can now run the Python scraper script."
    exit 0
fi

# Detect Chrome location based on OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    CHROME_PATH=$(which google-chrome || which chromium-browser || which chromium)
else
    # Windows (Git Bash/WSL)
    CHROME_PATH="/c/Program Files/Google/Chrome/Application/chrome.exe"
fi

# Check if Chrome exists
if [ ! -f "$CHROME_PATH" ] && [ ! -x "$CHROME_PATH" ]; then
    echo -e "${RED}Error: Chrome not found at $CHROME_PATH${NC}"
    echo "Please set CHROME_PATH manually in this script."
    exit 1
fi

echo "Chrome found at: $CHROME_PATH"
echo "Debug port: $DEBUG_PORT"
echo "User data directory: $USER_DATA_DIR"
echo ""

# Create user data directory if it doesn't exist
mkdir -p "$USER_DATA_DIR"

# Launch Chrome with remote debugging
echo -e "${GREEN}Launching Chrome with remote debugging...${NC}"

"$CHROME_PATH" \
    --remote-debugging-port=$DEBUG_PORT \
    --user-data-dir="$USER_DATA_DIR" \
    --no-first-run \
    --no-default-browser-check \
    &

# Wait for Chrome to start
echo "Waiting for Chrome to start..."
sleep 3

# Check if Chrome is running
if lsof -Pi :$DEBUG_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Chrome is running with remote debugging on port $DEBUG_PORT${NC}"
    echo ""
    echo -e "${YELLOW}IMPORTANT:${NC}"
    echo "1. Log in to TruMedia in this Chrome window"
    echo "2. Once logged in, keep this Chrome window open"
    echo "3. Run your Python scraper script"
    echo ""
    echo "To close Chrome and stop debugging, use:"
    echo "  killall 'Google Chrome' (macOS/Linux)"
    echo "  taskkill /IM chrome.exe /F (Windows)"
else
    echo -e "${RED}✗ Failed to start Chrome with remote debugging${NC}"
    exit 1
fi
