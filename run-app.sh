#!/bin/bash

# Colors for terminal output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Default configuration
PORT=8080
HOST="0.0.0.0"

# Parse command line arguments
while getopts ":p:d" opt; do
  case $opt in
    p) PORT="$OPTARG"
    ;;
    d) FLASK_DEBUG=1
    ;;
    \?) echo "Invalid option -$OPTARG" >&2
    ;;
  esac
done

# Set environment variables for the Flask app
export FLASK_PORT=$PORT
export FLASK_HOST=$HOST
# Set debug mode only for development environments (default to disabled)
export FLASK_DEBUG=${FLASK_DEBUG:-0}
export FLASK_APP=app.py # Tell Flask where the app is

echo -e "${BLUE}Starting The Digger application...${NC}"

# Kill any existing processes
echo -e "${YELLOW}Checking for existing processes...${NC}"
ps aux | grep '[p]ython.*app.py' | awk '{print $2}' | xargs -I{} echo "Killing process: {}"
ps aux | grep '[p]ython.*app.py' | awk '{print $2}' | xargs -I{} kill {} 2>/dev/null
sleep 1

# Activate virtual environment if it exists
if [ -d "venv" ]; then
  echo -e "${BLUE}Activating virtual environment...${NC}"
  source venv/bin/activate
else
  echo -e "${YELLOW}Virtual environment not found. Creating one...${NC}"
  python -m venv venv
  source venv/bin/activate
  echo -e "${GREEN}Virtual environment created and activated${NC}"
fi

# Install/update dependencies
echo -e "${BLUE}Installing/updating dependencies from requirements.txt...${NC}"
pip install -r requirements.txt

echo -e "${GREEN}Starting the server on port ${PORT}...${NC}"
echo -e "${YELLOW}Open your browser to: http://localhost:${PORT}${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"

# Debug mode notice
if [ "$FLASK_DEBUG" = "1" ]; then
    echo -e "${RED}WARNING: Debug mode is enabled. Do not use in production!${NC}"
fi

# Run the Flask app using the development server
flask run --host=$HOST --port=$PORT 