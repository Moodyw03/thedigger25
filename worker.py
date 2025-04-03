from rq import SimpleWorker, Queue
from redis import Redis
import os
import logging

logging.basicConfig(level=logging.INFO)

# Increase timeout settings for Redis
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
print(f"Connecting to Redis at: {redis_url}")

# Create Redis connection with longer timeouts
redis_conn = Redis.from_url(
    redis_url,
    socket_timeout=90,         # Increase from default 5 seconds
    socket_connect_timeout=30,  # Increase connection timeout
    socket_keepalive=True,      # Keep connections alive
    health_check_interval=30    # Check health periodically
)

queue = Queue(connection=redis_conn)
worker = SimpleWorker(
    [queue], 
    connection=redis_conn,
    job_timeout=1800  # 30 minutes max for a job
)
print("Worker starting...")
worker.work()
