import os
import logging
from redis import Redis, from_url as redis_from_url
from rq import Worker, Queue, Connection

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

# Define which queues to listen to
listen = ['default']

# Get Redis connection URL from environment variable (Railway provides this)
# Default to a local Redis instance if the environment variable is not set
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
log.info(f"Connecting to Redis at {redis_url}")

try:
    # Use from_url to handle connection string parsing
    redis_conn = redis_from_url(redis_url)
    # Test connection
    redis_conn.ping()
    log.info("Successfully connected to Redis.")
except Exception as e:
    log.error(f"Failed to connect to Redis: {e}")
    # Exit if connection fails, as the worker cannot function
    exit(1)


if __name__ == '__main__':
    try:
        with Connection(redis_conn):
            worker = Worker(list(map(Queue, listen)))
            log.info(f"Worker started, listening on queues: {', '.join(listen)}")
            worker.work(with_scheduler=False) # Run the worker loop
            log.info("Worker finished.")
    except Exception as e:
        log.error(f"An error occurred during worker execution: {e}") 