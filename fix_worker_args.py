import os
tasks_path = '/a0/usr/workdir/bg-removal-service/bg-removal-service/app/workers/tasks.py'
with open(tasks_path, 'r') as f:
    code = f.read()

# Fix signature
if 'upscale: bool = False):' in code:
    code = code.replace('upscale: bool = False):', 'upscale: bool = False, upscale_mode: str = "none"):')
    print("Signature fixed.")

# Fix job_data assignment
if "'upscale': upscale," in code and "'upscale_mode': upscale_mode," not in code:
    code = code.replace("'upscale': upscale,", "'upscale': upscale, 'upscale_mode': upscale_mode,")
    print("job_data fixed.")

with open(tasks_path, 'w') as f:
    f.write(code)
