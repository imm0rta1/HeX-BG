import re

filepath = '/a0/agent-zero-data/workdir/bg-removal-service/bg-removal-service/frontend/web-ui/src/App.tsx'
with open(filepath, 'r') as f:
    content = f.read()

# State
content = content.replace(
    "const [zoom, setZoom] = useState<number>(1);",
    "const [zoom, setZoom] = useState<number>(1);\n  const [engineState, setEngineState] = useState<'idle' | 'warming' | 'ready'>('ready');"
)

# onModelChange
new_onmodelchange = """
  const pollPreloadStatus = (id: string) => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/v1/jobs/${id}`);
        if (!res.ok) throw new Error("Server error");
        const data = await res.json();
        if (data.status === 'done') {
          clearInterval(interval);
          setEngineState('ready');
        } else if (data.status === 'failed' || data.status === 'error') {
          clearInterval(interval);
          setEngineState('idle');
        }
      } catch (e) {
        clearInterval(interval);
        setEngineState('idle');
      }
    }, 1000);
  };

  const onModelChange = async (value: string) => {
    setModelName(value);
    setEngineState('warming');
    try {
      const formData = new FormData();
      formData.append('model_name', value);
      const res = await fetch('/api/v1/jobs/preload', { method: 'POST', body: formData });
      if (!res.ok) throw new Error("Failed to preload");
      const data = await res.json();
      pollPreloadStatus(data.job_id);
    } catch (e) {
      console.error(e);
      setEngineState('idle');
    }
  };
"""
content = re.sub(r'const onModelChange = \(value: string\) => \{.*?  \};', new_onmodelchange.strip(), content, flags=re.DOTALL)

# Header
old_params_header = """<div className="text-[10px] tracking-[0.2em] text-gray-500 uppercase border-b border-white/10 pb-2">
              Extraction Parameters
            </div>"""
new_params_header = """<div className="flex justify-between items-center pb-2 border-b border-white/10">
              <span className="text-[10px] tracking-[0.2em] text-gray-500 uppercase">
                Extraction Parameters
              </span>
              {engineState === 'warming' && (
                <span className="text-[9px] tracking-[0.2em] text-[#00F0FF] animate-pulse flex items-center gap-1">
                  <div className="w-1.5 h-1.5 rounded-full bg-[#00F0FF]"></div>
                  WARMING UP...
                </span>
              )}
              {engineState === 'ready' && (
                <span className="text-[9px] tracking-[0.2em] text-[#D4FF00] flex items-center gap-1">
                  <div className="w-1.5 h-1.5 rounded-full bg-[#D4FF00]"></div>
                  ENGINE READY
                </span>
              )}
            </div>"""
content = content.replace(old_params_header, new_params_header)

# Button
old_button_logic = """disabled={items.length === 0 || isProcessingAny}
              className={`w-full p-4 font-display font-bold text-[11px] tracking-[0.2em] uppercase transition-all flex items-center justify-center gap-2
                ${isProcessingAny ? 'cyber-button executing' :
                  (doneCount === items.length && items.length > 0) ? 'cyber-button' : 'cyber-button ready'}
                disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              {isProcessingAny
                ? <span>[ EXECUTING {items.filter(i => ['processing', 'queued', 'uploading'].includes(i.status)).length} ]</span>
                : (doneCount === items.length && items.length > 0 ? <span>[ RE-RUN BATCH ]</span> : <span>[ INITIATE BATCH ]</span>)}"""
new_button_logic = """disabled={items.length === 0 || isProcessingAny || engineState === 'warming'}
              className={`w-full p-4 font-display font-bold text-[11px] tracking-[0.2em] uppercase transition-all flex items-center justify-center gap-2
                ${isProcessingAny ? 'cyber-button executing' :
                  engineState === 'warming' ? 'bg-black/80 text-gray-500 border border-white/10 shadow-none hover:bg-black/80' :
                  (doneCount === items.length && items.length > 0) ? 'cyber-button' : 'cyber-button ready'}
                disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              {engineState === 'warming' 
                ? <span>[ WARMING UP AI... ]</span>
                : isProcessingAny
                ? <span>[ EXECUTING {items.filter(i => ['processing', 'queued', 'uploading'].includes(i.status)).length} ]</span>
                : (doneCount === items.length && items.length > 0 ? <span>[ RE-RUN BATCH ]</span> : <span>[ INITIATE BATCH ]</span>)}"""
content = content.replace(old_button_logic, new_button_logic)

with open(filepath, 'w') as f:
    f.write(content)
