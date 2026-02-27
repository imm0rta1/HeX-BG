import os

os.chdir('/a0/usr/workdir/bg-removal-service/bg-removal-service/frontend/web-ui/src')
with open('App.tsx', 'r') as f:
    content = f.read()

if 'const [upscale' not in content:
    content = content.replace('const [autoCleanup, setAutoCleanup] = useState<boolean>(true);',
                              'const [autoCleanup, setAutoCleanup] = useState<boolean>(true);\n  const [upscale, setUpscale] = useState<boolean>(false);')
    content = content.replace("formData.append('auto_cleanup', autoCleanup.toString());",
                              "formData.append('auto_cleanup', autoCleanup.toString());\n    formData.append('upscale', upscale.toString());")

    ui_search = 'Automatically samples the background and surgically removes matching edge halos.\n                    </p>\n                  </div>'
    
    ui_replace = '''Automatically samples the background and surgically removes matching edge halos.
                    </p>
                  </div>

                  <div className="mb-5 p-3 bg-gray-700 rounded-lg border border-gray-600">
                    <label className="flex items-center cursor-pointer">
                      <div className="relative">
                        <input type="checkbox" className="sr-only" checked={upscale} onChange={(e) => setUpscale(e.target.checked)} />
                        <div className={`block w-10 h-6 rounded-full ${upscale ? \'bg-purple-500\' : \'bg-gray-500\'}`}></div>
                        <div className={`dot absolute left-1 top-1 bg-white w-4 h-4 rounded-full transition ${upscale ? \'transform translate-x-4\' : \'\'}`}></div>
                      </div>
                      <div className="ml-3 text-sm font-medium text-gray-200">
                        🔍 Enhance Resolution (2x AI Upscale)
                      </div>
                    </label>
                    <p className="text-xs text-gray-400 mt-2 ml-12">
                        Uses Deep Learning to hallucinate missing pixels and double the size of your cutout. (Adds ~5s processing time)
                    </p>
                  </div>'''
    
    content = content.replace(ui_search, ui_replace)
    
    with open('App.tsx', 'w') as f:
        f.write(content)
    print("UI updated successfully.")
else:
    print("UI already has the upscale toggle.")
