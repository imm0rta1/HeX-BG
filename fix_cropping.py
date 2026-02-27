import os
app = "/a0/usr/workdir/bg-removal-service/bg-removal-service/frontend/web-ui/src/App.tsx"
with open(app, "r") as f:
    c = f.read()

# Fix input preview to contain instead of cover
c = c.replace(
    'className="w-full h-32 object-cover opacity-80 mix-blend-screen"',
    'className="w-full h-40 object-contain opacity-80 mix-blend-screen"'
)

# Fix viewport wrapper to be strictly relative with absolute children
c = c.replace(
    '<div className="flex-1 min-h-0 p-2 md:p-4 flex items-center justify-center relative">',
    '<div className="flex-1 min-h-0 relative m-2 md:m-4">'
)

# Fix output container to absolutely fill the wrapper
c = c.replace(
    '<div className={`w-full h-full flex items-center justify-center relative ${bgClasses[bgMode]} border border-white/5 transition-colors duration-500 overflow-hidden`}>',
    '<div className={`absolute inset-0 flex items-center justify-center ${bgClasses[bgMode]} border border-white/5 transition-colors duration-500 overflow-hidden`}>'
)

# Fix output image to max out at 100% bounds
c = c.replace(
    'className="w-full h-full object-contain drop-shadow-2xl z-10 p-2 md:p-4 transition-transform duration-200"',
    'className="max-w-full max-h-full object-contain drop-shadow-2xl z-10 p-4 transition-transform duration-200"'
)

# Fix loading/idle container to absolutely fill the wrapper
c = c.replace(
    '<div className="w-full h-full text-center flex flex-col items-center justify-center border border-white/5 bg-white/[0.02]">',
    '<div className="absolute inset-0 text-center flex flex-col items-center justify-center border border-white/5 bg-white/[0.02]">'
)

with open(app, "w") as f:
    f.write(c)
