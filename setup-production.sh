#!/bin/bash

# Colors for terminal output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}Setting up The Digger for production deployment${NC}"

# Install dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -r requirements.txt

# Create a production .env file
echo -e "${YELLOW}Creating production environment file...${NC}"
cat > .env << EOL
# The Digger - Production Environment Variables
FLASK_DEBUG=0           # Debug mode disabled in production
FLASK_HOST=0.0.0.0      # Host to bind the server to
FLASK_PORT=8080         # Port to bind the server to
BROWSER=0               # Disable browser auto-open in production

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

echo -e "${GREEN}Production environment file created${NC}"

# Make scripts executable
echo -e "${YELLOW}Making scripts executable...${NC}"
chmod +x digger.py run-app.sh

echo -e "${GREEN}Setup complete!${NC}"
echo -e "${YELLOW}To run the application in production mode:${NC}"
echo -e "    ${BLUE}./run-app.sh${NC}"
echo -e "${YELLOW}For more information, see the README.md file${NC}" 