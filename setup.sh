#!/bin/bash

# Colors for terminal output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Default to development mode
MODE="dev"

# Parse command line arguments
while getopts ":p" opt; do
  case $opt in
    p) MODE="prod" ;;
    \?) echo "Invalid option -$OPTARG" >&2 ;;
  esac
done

echo -e "${BLUE}Setting up The Digger in ${MODE} mode${NC}"

# Function to check Python version
check_python() {
  echo -e "${YELLOW}Checking Python version...${NC}"
  if command -v python3 &>/dev/null; then
    PYTHON="python3"
  elif command -v python &>/dev/null; then
    PYTHON="python"
  else
    echo -e "${RED}Python not found! Please install Python 3.8+ and try again.${NC}"
    exit 1
  fi

  # Check Python version
  PY_VERSION=$($PYTHON --version 2>&1 | awk '{print $2}')
  echo -e "${GREEN}Found Python version: ${PY_VERSION}${NC}"
  
  # Check major version
  PY_MAJOR=$(echo $PY_VERSION | cut -d. -f1)
  PY_MINOR=$(echo $PY_VERSION | cut -d. -f2)
  
  if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 8 ]); then
    echo -e "${RED}Python 3.8+ is required. You have ${PY_VERSION}.${NC}"
    echo -e "${YELLOW}Please upgrade Python and try again.${NC}"
    exit 1
  fi
}

# Function to set up virtual environment
setup_venv() {
  echo -e "${YELLOW}Setting up virtual environment...${NC}"
  # Check if venv exists
  if [ -d "venv" ]; then
    echo -e "${GREEN}Found existing virtual environment.${NC}"
  else
    echo -e "${YELLOW}Creating new virtual environment...${NC}"
    $PYTHON -m venv venv
    if [ $? -ne 0 ]; then
      echo -e "${RED}Failed to create virtual environment.${NC}"
      echo -e "${YELLOW}Try installing venv package with: sudo apt-get install python3-venv${NC}"
      exit 1
    fi
  fi
  
  # Activate virtual environment
  echo -e "${YELLOW}Activating virtual environment...${NC}"
  source venv/bin/activate
  
  # Upgrade pip
  echo -e "${YELLOW}Upgrading pip...${NC}"
  pip install --upgrade pip
}

# Function to install dependencies
install_deps() {
  echo -e "${YELLOW}Installing dependencies...${NC}"
  pip install -r requirements.txt
  if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to install dependencies.${NC}"
    exit 1
  fi
}

# Create appropriate .env file based on mode
create_env_file() {
  echo -e "${YELLOW}Creating .env file for ${MODE} mode...${NC}"
  if [ "$MODE" = "prod" ]; then
    cat > .env << EOL
# The Digger - Production Environment Variables
FLASK_DEBUG=0           # Debug mode disabled in production
FLASK_HOST=0.0.0.0      # Host to bind the server to
FLASK_PORT=8080         # Port to bind the server to

# Request configuration
REQUEST_TIMEOUT=20      # Timeout for HTTP requests in seconds
MAX_RETRIES=3           # Number of retry attempts for HTTP requests
RETRY_DELAY=2           # Seconds between retries
MAX_FETCH_LIMIT=300     # Maximum number of items to fetch
MAX_PAGINATION_PAGES=10 # Maximum number of pagination pages to fetch
RATE_LIMIT_RPM=30       # Rate limiting - requests per minute

# Cache configuration
CACHE_EXPIRY=86400      # Cache expiry time in seconds (24 hours)

# YouTube configuration
YOUTUBE_USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36
EOL
  else
    cat > .env << EOL
# The Digger - Development Environment Variables
FLASK_DEBUG=1           # Debug mode enabled for development
FLASK_HOST=127.0.0.1    # Localhost for development
FLASK_PORT=8080         # Port to bind the server to

# Request configuration
REQUEST_TIMEOUT=10      # Timeout for HTTP requests in seconds
MAX_RETRIES=3           # Number of retry attempts for HTTP requests
RETRY_DELAY=1           # Seconds between retries
MAX_FETCH_LIMIT=100     # Maximum number of items to fetch (reduced for development)
MAX_PAGINATION_PAGES=5  # Maximum number of pagination pages to fetch
RATE_LIMIT_RPM=45       # Rate limiting - requests per minute

# Cache configuration
CACHE_EXPIRY=3600       # Cache expiry time in seconds (1 hour for development)

# YouTube configuration
YOUTUBE_USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36
EOL
  fi
  echo -e "${GREEN}Environment file created${NC}"
}

# Make scripts executable
make_scripts_executable() {
  echo -e "${YELLOW}Making scripts executable...${NC}"
  chmod +x run-app.sh
  chmod +x worker.py
}

# Run all setup functions
check_python
setup_venv
install_deps
create_env_file
make_scripts_executable

echo -e "${GREEN}Setup complete!${NC}"
echo -e "${YELLOW}To run the application:${NC}"
echo -e "    ${BLUE}./run-app.sh${NC}"
if [ "$MODE" = "prod" ]; then
  echo -e "${YELLOW}For production worker:${NC}"
  echo -e "    ${BLUE}python worker.py${NC}"
fi
echo -e "${YELLOW}For more information, see README.md${NC}" 