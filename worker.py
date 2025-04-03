#!/usr/bin/env python
import os
import logging
import redis
from rq import Worker, Queue, Connection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Get Redis connection URL from environment
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
logger.info(f"Connecting to Redis at: {redis_url}")

# Configure Redis connection with extended timeouts
redis_conn = redis.from_url(
    redis_url,
    socket_timeout=90,
    socket_connect_timeout=30,
    socket_keepalive=True,
    health_check_interval=30
)

# Set queue name, default is 'default'
queue_name = os.getenv('QUEUE_NAME', 'default')

if __name__ == '__main__':
    # Use the Connection context to manage the Redis connection
    with Connection(redis_conn):
        # Create a queue with an extended timeout
        q = Queue(queue_name, default_timeout=1800)  # 30 minutes
        
        # Create a worker listening on the specified queues
        w = Worker([q])
        
        logger.info(f"Worker started, listening on queue: {queue_name}")
        w.work()
