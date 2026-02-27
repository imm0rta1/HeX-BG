import os
app = "/a0/usr/workdir/bg-removal-service/bg-removal-service/frontend/web-ui/src/App.tsx"
with open(app, "r") as f:
    c = f.read()

c = c.replace('min-h-[50vh] lg:h-[85vh]', 'min-h-[50vh]')
c = c.replace(
    'className="max-w-full max-h-full p-4 object-contain drop-shadow-2xl z-10"',
    'className="w-full h-[50vh] md:h-[60vh] object-contain drop-shadow-2xl z-10 p-4"'
)

with open(app, "w") as f:
    f.write(c)
