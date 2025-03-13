import sys
import os

# Add parent directory to path so we can import app.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import Flask app from app.py
from app import app

# Set debug to False for production
app.debug = False

# This is for Vercel serverless deployments
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080))) 