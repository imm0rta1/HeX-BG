from redis import Redis
from rq import Queue
from rq.registry import FailedJobRegistry
from rq.job import Job

try:
    redis_conn = Redis(host='localhost', port=6379, db=0)
    q = Queue('default', connection=redis_conn)
    registry = FailedJobRegistry(queue=q)
    job_ids = registry.get_job_ids()
    if job_ids:
        latest_job_id = job_ids[-1]
        job = Job.fetch(latest_job_id, connection=redis_conn)
        print(f"Job {latest_job_id} Failed with Error:")
        print(job.exc_info)
    else:
        print("No failed jobs found in registry.")
except Exception as e:
    print("Error fetching from Redis:", e)
