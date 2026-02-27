from redis import Redis
from rq import Queue
from rq.registry import FailedJobRegistry

redis = Redis()
registry = FailedJobRegistry(queue=Queue('high', connection=redis))
job_ids = registry.get_job_ids()

if job_ids:
    job = Queue('high', connection=redis).fetch_job(job_ids[-1])
    if job:
        print(f"Job ID: {job.id}")
        print(f"Error:\n{job.exc_info}")
else:
    print("No failed jobs found in the 'high' queue.")
