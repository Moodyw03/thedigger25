import sys
import os
import logging

# Configure logging for Vercel
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory to path so we can import app.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Log the Python path for debugging
logger.info(f"Python path: {sys.path}")
logger.info(f"Current directory: {os.getcwd()}")

# Import Flask app from app.py
try:
    from app import app
    logger.info("Successfully imported app from app.py")
except Exception as e:
    logger.error(f"Error importing app: {str(e)}")
    raise

# Set debug to False for production
app.debug = False

# Configure for production
if os.environ.get("FLASK_ENV") == "production":
    # Production settings
    app.config['PROPAGATE_EXCEPTIONS'] = True
    # Disable JSON pretty printing to save bandwidth
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False
    # Disable auto-reloading
    app.config['USE_RELOADER'] = False

# Log that the app is ready
logger.info("Vercel serverless function is initialized and ready")

# This is for Vercel serverless deployments
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080))) 