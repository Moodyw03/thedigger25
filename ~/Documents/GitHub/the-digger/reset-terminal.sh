#!/bin/bash

# Colors for terminal output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}Resetting terminal configuration for The Digger...${NC}"

# Remove any Terminal saved state that might be causing the prompt
echo -e "${YELLOW}Clearing Terminal saved state...${NC}"
rm -rf ~/Library/Saved\ Application\ State/com.apple.Terminal.savedState 2>/dev/null

# Remove the UI directory if it still exists
if [ -d ~/Documents/GitHub/the-digger-ui ]; then
    echo -e "${YELLOW}Removing the-digger-ui directory...${NC}"
    rm -rf ~/Documents/GitHub/the-digger-ui
else
    echo -e "${GREEN}the-digger-ui already removed.${NC}"
fi

# Clear Terminal preferences if needed (this is optional and will be commented out by default)
# echo -e "${YELLOW}Resetting Terminal preferences...${NC}"
# defaults delete com.apple.Terminal 2>/dev/null

# Create a simple shell alias to make running the app easier
echo -e "${YELLOW}Adding alias to .zshrc...${NC}"
if ! grep -q "alias digger=" ~/.zshrc; then
    echo "# The Digger alias" >> ~/.zshrc
    echo "alias digger='cd ~/Documents/GitHub/the-digger && ./run-app.sh'" >> ~/.zshrc
    echo -e "${GREEN}Added 'digger' alias to .zshrc${NC}"
else
    echo -e "${GREEN}Digger alias already exists in .zshrc${NC}"
fi

echo -e "${GREEN}Done!${NC}"
echo -e "${YELLOW}Please restart your terminal or run 'source ~/.zshrc' to apply changes.${NC}"
echo -e "${YELLOW}You can now simply type 'digger' to run the application.${NC}" 