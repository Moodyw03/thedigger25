from rq import SimpleWorker, Queue
from redis import Redis
import os
import logging
import sys
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get Redis connection URL with better validation
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
logger.info(f"Connecting to Redis at: {redis_url}")

# Validate URL format
if not redis_url or not (redis_url.startswith('redis://') or redis_url.startswith('rediss://')):
    logger.error(f"Invalid Redis URL: '{redis_url}'. URL must start with redis:// or rediss://")
    logger.error("Please check the REDIS_URL environment variable in your Railway service settings")
    sys.exit(1)  # Exit with error code

# Create Redis connection with longer timeouts and retry logic
max_retries = 5
retry_delay = 2  # seconds

for attempt in range(max_retries):
    try:
        logger.info(f"Connection attempt {attempt+1} to Redis at {redis_url.split('@')[-1]}")
        
        # Create Redis connection with longer timeouts
        redis_conn = Redis.from_url(
            redis_url,
            socket_timeout=90,          # Increase from default 5 seconds
            socket_connect_timeout=30,  # Increase connection timeout
            socket_keepalive=True,      # Keep connections alive
            health_check_interval=30    # Check health periodically
        )
        
        # Test connection
        redis_conn.ping()
        logger.info("Successfully connected to Redis")
        break
        
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {str(e)}")
        if attempt < max_retries - 1:
            logger.info(f"Retrying in {retry_delay} seconds... (Attempt {attempt+1}/{max_retries})")
            time.sleep(retry_delay)
            retry_delay *= 2  # Exponential backoff
        else:
            logger.error(f"Maximum retry attempts ({max_retries}) reached. Exiting.")
            sys.exit(1)  # Exit with error code

# Create queue with a longer default timeout for all jobs
queue = Queue(connection=redis_conn, default_timeout=3600)  # 60 minutes max (increased from 30)

# Create a worker
worker = SimpleWorker([queue], connection=redis_conn)
logger.info("Worker starting with 1 hour job timeout...")
worker.work()

