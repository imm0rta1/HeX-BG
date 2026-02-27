import re

# 1. Patch routes_jobs.py
routes_path = 'app/api/routes_jobs.py'
with open(routes_path, 'r') as f:
    routes_code = f.read()

if "upscale_mode: str = Form" not in routes_code:
    routes_code = routes_code.replace(
        "upscale: bool = Form(False)",
        "upscale: bool = Form(False),\n    upscale_mode: str = Form('none')"
    )
    routes_code = re.sub(
        r"q\.enqueue\((process_image_task.*?)upscale,",
        r"q.enqueue(\1upscale, upscale_mode,",
        routes_code
    )
    with open(routes_path, 'w') as f:
        f.write(routes_code)
    print("routes_jobs.py patched.")

# 2. Patch tasks.py
tasks_path = 'app/workers/tasks.py'
with open(tasks_path, 'r') as f:
    tasks_code = f.read()

if "upscale_mode: str = 'none'" not in tasks_code:
    tasks_code = re.sub(
        r"def process_image_task\((.*?)upscale: bool\):",
        r"def process_image_task(\1upscale: bool, upscale_mode: str = 'none'):",
        tasks_code
    )
    
    # Make sure we add it to job_data so the upscale block can read it
    if "'upscale': upscale," in tasks_code and "'upscale_mode': upscale_mode" not in tasks_code:
        tasks_code = tasks_code.replace(
            "'upscale': upscale,",
            "'upscale': upscale,\n        'upscale_mode': upscale_mode,"
        )
        
    with open(tasks_path, 'w') as f:
        f.write(tasks_code)
    print("tasks.py patched.")
