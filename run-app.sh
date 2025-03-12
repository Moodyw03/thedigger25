#!/bin/bash

# Colors for terminal output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting The Digger application...${NC}"

# Kill any existing Digger processes
echo -e "${YELLOW}Checking for existing processes...${NC}"
ps aux | grep '[p]ython.*digger.py' | awk '{print $2}' | xargs -I{} echo "Killing process: {}"
ps aux | grep '[p]ython.*digger.py' | awk '{print $2}' | xargs -I{} kill {} 2>/dev/null
sleep 1

# Activate virtual environment
source venv/bin/activate

# Make digger.py executable
chmod +x digger.py

# Use port 8080 to avoid conflicts with macOS AirPlay
PORT=8080

echo -e "${GREEN}Starting the server on port ${PORT}...${NC}"
echo -e "${YELLOW}Open your browser to: http://localhost:${PORT}${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"

# Run the Digger application directly
./digger.py 