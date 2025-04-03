from rq import SimpleWorker, Queue
from redis import Redis
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get Redis connection URL
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
logger.info(f"Connecting to Redis at: {redis_url}")

# Create Redis connection with longer timeouts
redis_conn = Redis.from_url(
    redis_url,
    socket_timeout=90,          # Increase from default 5 seconds
    socket_connect_timeout=30,  # Increase connection timeout
    socket_keepalive=True,      # Keep connections alive
    health_check_interval=30    # Check health periodically
)

# Create queue with a default timeout for all jobs
queue = Queue(connection=redis_conn, default_timeout=1800)  # 30 minutes max

# Create a worker
worker = SimpleWorker([queue], connection=redis_conn)
logger.info("Worker starting...")
worker.work()

