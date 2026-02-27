import os

app_dir = 'app'
for root, dirs, files in os.walk(app_dir):
    for file in files:
        if file.endswith('.py'):
            file_path = os.path.join(root, file)
            with open(file_path, 'r') as f:
                content = f.read()
            
            if 'RealESRGANer(' in content:
                print(f"Found RealESRGANer in {file_path}")
                if 'tile=' not in content:
                    content = content.replace('RealESRGANer(', 'RealESRGANer(tile=512, tile_pad=10, ')
                    with open(file_path, 'w') as f:
                        f.write(content)
                    print("Patched successfully! Memory tiling enabled.")
                else:
                    print("Already patched.")
