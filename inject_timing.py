import sys

file_path = "/a0/agent-zero-data/workdir/bg-removal-service/bg-removal-service/app/workers/tasks.py"
with open(file_path, "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "model = get_worker_segmenter(model_name)" in line:
        new_lines.append("        t_load0 = time.time()\n")
        new_lines.append(line)
        new_lines.append("        load_ms = (time.time() - t_load0) * 1000\n")
        new_lines.append("        logger.info(f\"[TIMING] Model load took {load_ms}ms\")\n")
    elif "result = model.process(" in line:
        new_lines.append("        logger.info(f\"[TIMING] Starting model.process...\")\n")
        new_lines.append(line)
    else:
        new_lines.append(line)

with open(file_path, "w") as f:
    f.writelines(new_lines)

print("Successfully injected timing logs into tasks.py")
