import sys

file_path = "/a0/agent-zero-data/workdir/bg-removal-service/bg-removal-service/app/workers/tasks.py"
with open(file_path, "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "model = get_worker_segmenter(model_name)" in line:
        new_lines.append("        print(f\"[TIMING_DEBUG] START: Calling get_worker_segmenter({model_name})...\")\n")
        new_lines.append("        t_load0 = time.time()\n")
        new_lines.append(line)
        new_lines.append("        load_ms = (time.time() - t_load0) * 1000\n")
        new_lines.append("        print(f\"[TIMING_DEBUG] FINISH: Model load took {load_ms}ms\")\n")
    elif "result = model.process(" in line:
        new_lines.append("        print(f\"[TIMING_DEBUG] START: Starting model.process...\")\n")
        new_lines.append(line)
        new_lines.append("        print(f\"[TIMING_DEBUG] FINISH: model.process completed.\")\n")
    elif "logger.info(f\"[TIMING]" in line:
        pass # Remove old logger lines
    else:
        new_lines.append(line)

with open(file_path, "w") as f:
    f.writelines(new_lines)

print("Successfully re-injected timing logs with print() into tasks.py")
