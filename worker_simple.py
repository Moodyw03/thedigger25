from rq import SimpleWorker, Queue
from redis import Redis
import os
import logging
logging.basicConfig(level=logging.INFO)
redis_conn = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
queue = Queue(connection=redis_conn)
worker = SimpleWorker([queue], connection=redis_conn)
print("Worker starting...")
worker.work()
