import os

# 1. Patch routes_jobs.py
routes_file = "/a0/usr/workdir/bg-removal-service/bg-removal-service/app/api/routes_jobs.py"
with open(routes_file, "r") as f:
    text = f.read()
text = text.replace(
    "upscale: bool = Form(False)\n):",
    "upscale: bool = Form(False),\n    target_color: str = Form(\"\"),\n    target_tolerance: int = Form(15)\n):"
)
text = text.replace(
    "upscale, job_id=job_id",
    "upscale, target_color, target_tolerance, job_id=job_id"
)
with open(routes_file, "w") as f:
    f.write(text)

# 2. Patch tasks.py
tasks_file = "/a0/usr/workdir/bg-removal-service/bg-removal-service/app/workers/tasks.py"
with open(tasks_file, "r") as f:
    text = f.read()
text = text.replace(
    "upscale: bool = False):",
    "upscale: bool = False, target_color: str = \"\", target_tolerance: int = 15):"
)
text = text.replace(
    "auto_cleanup=auto_cleanup)",
    "auto_cleanup=auto_cleanup, target_color=target_color, target_tolerance=target_tolerance)"
)
with open(tasks_file, "w") as f:
    f.write(text)

# 3. Patch segment_primary.py
seg_file = "/a0/usr/workdir/bg-removal-service/bg-removal-service/app/pipeline/segment_primary.py"
with open(seg_file, "r") as f:
    text = f.read()
text = text.replace(
    "auto_cleanup: bool = True) -> dict:",
    "auto_cleanup: bool = True, target_color: str = \"\", target_tolerance: int = 15) -> dict:"
)
text = text.replace(
    "result_np = final_edge_cleanup(result_np)",
    "result_np = final_edge_cleanup(result_np, target_color, target_tolerance)"
)
with open(seg_file, "w") as f:
    f.write(text)

# 4. Patch final_edge_cleanup.py
cleanup_file = "/a0/usr/workdir/bg-removal-service/bg-removal-service/app/pipeline/final_edge_cleanup.py"
with open(cleanup_file, "r") as f:
    text = f.read()
text = text.replace(
    "def final_edge_cleanup(rgba: np.ndarray):",
    "def final_edge_cleanup(rgba: np.ndarray, target_color: str = \"\", target_tolerance: int = 15):"
)

inject_code = """    # 1.5) Targeted Color Eraser
    if target_color and target_color.startswith('#'):
        try:
            hex_c = target_color.lstrip('#')
            tr, tg, tb = tuple(int(hex_c[i:i+2], 16) for i in (0, 2, 4))
            diff = np.abs(rgb.astype(np.int32) - np.array([tr, tg, tb], dtype=np.int32))
            dist = np.linalg.norm(diff, axis=2)
            a[(dist <= target_tolerance) & (fg_core == 0)] = 0
        except Exception as e:
            pass
            
    # 2) remove tiny components outside allowed (pre)"""

text = text.replace("    # 2) remove tiny components outside allowed (pre)", inject_code)
with open(cleanup_file, "w") as f:
    f.write(text)

print("Backend patches applied successfully!")
