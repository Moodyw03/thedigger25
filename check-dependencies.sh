#!/bin/bash

# Colors for terminal output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}The Digger - Dependency Check${NC}"
echo -e "${YELLOW}Running dependency checker...${NC}"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
    echo -e "${GREEN}Activated virtual environment${NC}"
fi

# Make the Python script executable
chmod +x check_dependencies.py

# Run the dependency checker
./check_dependencies.py

# Check if dependencies.py executed successfully
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Dependency check complete${NC}"
else
    echo -e "${RED}Error running dependency checker${NC}"
    exit 1
fi

# Deactivate virtual environment if it was activated
if [ -n "$VIRTUAL_ENV" ]; then
    deactivate
    echo -e "${YELLOW}Deactivated virtual environment${NC}"
fi 