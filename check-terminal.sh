#!/bin/bash

# Colors for terminal output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}Checking for possible sources of the digger prompt...${NC}"

# Get the current directory
current_dir=$(pwd)
echo -e "${YELLOW}Current directory: ${current_dir}${NC}"

# Check Terminal Profile
echo -e "${YELLOW}Checking Terminal profiles:${NC}"
plutil -p ~/Library/Preferences/com.apple.Terminal.plist 2>/dev/null | grep -E "command|digger" || echo "No Terminal launch commands found"

# Check for any applications in startup items
echo -e "${YELLOW}Checking launch agents:${NC}"
ls -la ~/Library/LaunchAgents/ | grep -i digger || echo "No Digger launch agents found"

# Check for any startup script in the shell
echo -e "${YELLOW}Checking shell startup files:${NC}"
for file in ~/.bash_profile ~/.bashrc ~/.zshrc ~/.profile; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}Checking $file:${NC}"
        grep -i digger "$file" || echo "No digger references found in $file"
    fi
done

# Check if the current shell session has any relevant environment variables
echo -e "${YELLOW}Checking environment variables:${NC}"
env | grep -i digger || echo "No digger environment variables found"

echo -e "${GREEN}Done!${NC}"
echo -e "${YELLOW}The UI directory has been removed.${NC}"
echo -e "${YELLOW}You now have a 'digger' alias to run the application easily.${NC}"
echo -e "${YELLOW}If you're still seeing a prompt when opening Terminal, it might be in Terminal preferences.${NC}"
echo -e "${YELLOW}Open Terminal -> Preferences -> Profiles -> Shell and ensure 'Run command' is empty.${NC}" 