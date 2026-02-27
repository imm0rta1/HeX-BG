import os

app_file = "/a0/usr/workdir/bg-removal-service/bg-removal-service/frontend/web-ui/src/App.tsx"

with open(app_file, "r") as f:
    content = f.read()

# Fix 1: Make the main viewport container strictly bound to the screen height on desktop
content = content.replace(
    'min-h-[600px]',
    'min-h-[50vh] lg:h-[85vh]'
)

# Fix 2: Force the image to stay 100% within the bounds of its parent container
content = content.replace(
    'className="max-w-full max-h-[700px] object-contain drop-shadow-2xl z-10"',
    'className="max-w-full max-h-full p-4 object-contain drop-shadow-2xl z-10"'
)

with open(app_file, "w") as f:
    f.write(content)

print("App.tsx patched successfully!")
