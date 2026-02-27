import os

app_path = '/a0/usr/workdir/bg-removal-service/bg-removal-service/frontend/web-ui/src/App.tsx'
with open(app_path, 'r') as f:
    content = f.read()

old_cond = "if (item.status === 'idle' || item.status === 'failed' || item.status === 'error') {"
new_cond = "if (!['uploading', 'queued', 'processing'].includes(item.status)) {"

if old_cond in content:
    content = content.replace(old_cond, new_cond)
    with open(app_path, 'w') as f:
        f.write(content)
    print("Patched App.tsx successfully.")
else:
    print("Target string not found.")
