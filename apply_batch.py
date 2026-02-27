import os

# 1. Update routes_jobs.py to add ZIP batch download
routes_file = "/a0/usr/workdir/bg-removal-service/bg-removal-service/app/api/routes_jobs.py"
with open(routes_file, "r") as f:
    routes_code = f.read()

if "import zipfile" not in routes_code:
    routes_code = routes_code.replace("import uuid, time, shutil, logging, os", "import uuid, time, shutil, logging, os, zipfile, io\nfrom fastapi.responses import StreamingResponse")

zip_route = """
@router.get("/jobs/batch/zip")
def download_batch_zip(job_ids: str):
    ids = [i.strip() for i in job_ids.split(",") if i.strip()]
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for j_id in ids:
            job_dir = settings.STORAGE_DIR / j_id
            cutout_path = job_dir / "cutout.png"
            orig_name = f"cutout_{j_id[:8]}"
            for f in job_dir.glob("original_*"):
                orig_name = f.name.replace("original_", "").rsplit(".", 1)[0]
                break
            if cutout_path.exists():
                zip_file.write(cutout_path, arcname=f"{orig_name}_cutout.png")
    zip_buffer.seek(0)
    return StreamingResponse(zip_buffer, media_type="application/zip", headers={"Content-Disposition": "attachment; filename=batch_cutouts.zip"})
"""
if "/jobs/batch/zip" not in routes_code:
    routes_code += zip_route

with open(routes_file, "w") as f:
    f.write(routes_code)

# 2. Update App.tsx for Batch Support
app_code = r"""import React, { useState } from 'react';

interface JobResult {
  status: string;
  qc?: any;
  cutout_url?: string;
  mask_url?: string;
}

interface BatchItem {
  id: string;
  file: File;
  preview: string;
  jobId: string | null;
  status: 'idle' | 'uploading' | 'queued' | 'processing' | 'done' | 'failed' | 'error';
  result: JobResult | null;
}

function App() {
  const [items, setItems] = useState<BatchItem[]>([]);
  const [activeIndex, setActiveIndex] = useState<number>(0);
  
  const [modelName, setModelName] = useState<string>('isnet-general-use');
  const [erodeSize, setErodeSize] = useState<number>(0);
  const [blurSize, setBlurSize] = useState<number>(0);
  const [autoCleanup, setAutoCleanup] = useState<boolean>(true);
  const [upscale, setUpscale] = useState<boolean>(false);
  const [bgMode, setBgMode] = useState<string>('checkerboard');
  const [customBg, setCustomBg] = useState<string>('#FF00FF');
  const [zoom, setZoom] = useState<number>(1);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const newItems: BatchItem[] = Array.from(e.target.files).map((f) => ({
        id: Math.random().toString(36).substring(7),
        file: f,
        preview: URL.createObjectURL(f),
        jobId: null,
        status: 'idle',
        result: null
      }));
      setItems(newItems);
      setActiveIndex(0);
      setZoom(1);
    }
  };

  const updateItem = (index: number, updates: Partial<BatchItem>) => {
    setItems(prev => {
      const newItems = [...prev];
      newItems[index] = { ...newItems[index], ...updates };
      return newItems;
    });
  };

  const uploadAll = async () => {
    items.forEach((item, index) => {
      if (item.status === 'idle' || item.status === 'failed' || item.status === 'error') {
        uploadSingle(item, index);
      }
    });
  };

  const uploadSingle = async (item: BatchItem, index: number) => {
    updateItem(index, { status: 'uploading' });
    
    const formData = new FormData();
    formData.append('file', item.file);
    formData.append('model_name', modelName);
    formData.append('erode_size', erodeSize.toString());
    formData.append('blur_size', blurSize.toString());
    formData.append('auto_cleanup', autoCleanup.toString());
    formData.append('upscale', upscale.toString());

    try {
      const res = await fetch('/api/v1/jobs', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      updateItem(index, { jobId: data.job_id, status: 'queued' });
      pollStatus(data.job_id, index);
    } catch (err) {
      console.error(err);
      updateItem(index, { status: 'error' });
    }
  };

  const pollStatus = async (id: string, index: number) => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/v1/jobs/${id}`);
        const data = await res.json();
        
        if (data.status === 'done') {
          clearInterval(interval);
          updateItem(index, { status: 'done', result: data.result });
        } else if (data.status === 'failed') {
          clearInterval(interval);
          updateItem(index, { status: 'failed' });
        } else {
          updateItem(index, { status: data.status });
        }
      } catch (err) {
        clearInterval(interval);
        updateItem(index, { status: 'error' });
      }
    }, 1000);
  };

  const downloadAllZip = () => {
    const doneIds = items.filter(i => i.status === 'done' && i.jobId).map(i => i.jobId);
    if (doneIds.length === 0) return;
    window.location.href = `/api/v1/jobs/batch/zip?job_ids=${doneIds.join(',')}`;
  };

  const bgClasses: any = {
    checkerboard: "bg-[url('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAMUlEQVQ4T2NkYNgfQEhQGHAAksD///9OQXBwAmhmYABiwAEDo4D//w8wAAhE8QYQIAAA/3J/8b2mXbgAAAAASUVORK5CYII=')] bg-repeat",
    black: "bg-black",
    white: "bg-white",
    green: "bg-[#00FF00]",
    gray: "bg-gray-500"
  };

  const activeItem = items[activeIndex] || null;
  const isProcessingAny = items.some(i => ['uploading', 'queued', 'processing'].includes(i.status));
  const doneCount = items.filter(i => i.status === 'done').length;

  return (
    <div className="h-screen w-screen overflow-hidden text-gray-200 selection:bg-[#00F0FF] selection:text-black relative flex flex-col">
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Space+Mono:ital,wght@0,400;0,700;1,400;1,700&family=Syne:wght@400..800&display=swap');
        body {
          margin: 0;
          overflow: hidden;
          background-color: #030303;
          background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='0.05'/%3E%3C/svg%3E");
          font-family: 'Space Mono', monospace;
        }
        .font-display { font-family: 'Syne', sans-serif; }
        .glass-panel {
          background: rgba(10, 10, 10, 0.6);
          backdrop-filter: blur(20px);
          -webkit-backdrop-filter: blur(20px);
          border: 1px solid rgba(255, 255, 255, 0.05);
        }
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .stagger-1 { animation: fadeUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) 0.1s both; }
        .stagger-2 { animation: fadeUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) 0.2s both; }
        
        .cyber-button {
          position: relative;
          background: transparent;
          color: #00F0FF;
          border: 1px solid #00F0FF;
          overflow: hidden;
          transition: all 0.3s ease;
        }
        .cyber-button::before {
          content: '';
          position: absolute;
          top: 0; left: -100%; width: 100%; height: 100%;
          background: linear-gradient(90deg, transparent, rgba(0, 240, 255, 0.4), transparent);
          transition: all 0.5s ease;
        }
        .cyber-button:hover::before { left: 100%; }
        .cyber-button:hover {
          background: rgba(0, 240, 255, 0.1);
          box-shadow: 0 0 15px rgba(0, 240, 255, 0.3);
        }
        .cyber-button.ready {
          background: transparent;
          color: #D4FF00;
          border-color: #D4FF00;
        }
        .cyber-button.ready::before {
          background: linear-gradient(90deg, transparent, rgba(212, 255, 0, 0.4), transparent);
        }
        .cyber-button.ready:hover {
          background: rgba(212, 255, 0, 0.1);
          box-shadow: 0 0 15px rgba(212, 255, 0, 0.3);
        }
        .cyber-button.executing {
          border-color: #FF003C;
          color: #FF003C;
          background: rgba(255, 0, 60, 0.1);
          box-shadow: 0 0 20px rgba(255, 0, 60, 0.4);
          animation: pulse 1s infinite alternate;
        }
        @keyframes pulse {
          from { box-shadow: 0 0 10px rgba(255, 0, 60, 0.2); }
          to { box-shadow: 0 0 25px rgba(255, 0, 60, 0.6); }
        }
        
        input[type=range] {
          -webkit-appearance: none;
          background: transparent;
          width: 100%;
        }
        input[type=range]::-webkit-slider-thumb {
          -webkit-appearance: none;
          height: 16px; width: 8px;
          background: #00F0FF;
          cursor: pointer;
          border-radius: 0;
          margin-top: -7px;
        }
        input[type=range]::-webkit-slider-runnable-track {
          width: 100%; height: 2px;
          cursor: pointer;
          background: rgba(255, 255, 255, 0.2);
        }
        
        .custom-scrollbar::-webkit-scrollbar { width: 4px; height: 4px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(0, 240, 255, 0.3); border-radius: 4px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #00F0FF; }
      `}</style>

      <div className="fixed top-[-20%] left-[-10%] w-[50vw] h-[50vw] bg-[#00F0FF] rounded-full mix-blend-screen filter blur-[150px] opacity-[0.03] pointer-events-none z-0"></div>
      <div className="fixed bottom-[-20%] right-[-10%] w-[50vw] h-[50vw] bg-[#D4FF00] rounded-full mix-blend-screen filter blur-[150px] opacity-[0.03] pointer-events-none z-0"></div>

      <div className="w-full max-w-[1600px] mx-auto p-4 md:p-6 flex-1 flex flex-col min-h-0 z-10">
        
        <header className="shrink-0 mb-4 stagger-1 flex flex-col md:flex-row items-baseline justify-between border-b border-white/10 pb-4">
          <div>
            <h1 className="font-display text-3xl md:text-5xl font-bold tracking-tighter uppercase text-white">
              Surgical Extraction
            </h1>
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <span className="text-[10px] tracking-[0.2em] text-[#00F0FF] border border-[#00F0FF]/30 px-2 py-1 rounded-sm uppercase bg-[#00F0FF]/5">
                V4 Batch Mode
              </span>
              <span className="text-[9px] text-gray-500 tracking-widest uppercase">
                Hex OS / Agent Zero Integration
              </span>
            </div>
          </div>
          <div className="mt-4 md:mt-0 text-left md:text-right">
            <p className="text-[10px] text-gray-400 max-w-xs ml-auto leading-relaxed tracking-wider">
              High-fidelity neural matting.<br/> Zero edge destruction. Bulk Processing.
            </p>
          </div>
        </header>

        <div className="flex-1 flex flex-col lg:flex-row gap-6 min-h-0 overflow-hidden">
          
          {/* Controls Column */}
          <div className="lg:w-[400px] xl:w-[450px] shrink-0 flex flex-col gap-6 overflow-y-auto custom-scrollbar pr-2 pb-6 lg:pb-0">
            
            <div className="glass-panel p-5 relative overflow-hidden group shrink-0">
              <div className="absolute top-0 left-0 w-1 h-full bg-white/10 group-hover:bg-[#00F0FF] transition-colors"></div>
              <h2 className="font-display text-lg mb-4 tracking-wide text-white uppercase flex justify-between items-end border-b border-white/5 pb-2">
                <span>01. Input (Batch)</span>
                <span className="text-[9px] text-gray-600 tracking-widest">[ RAW_DATA ]</span>
              </h2>
              
              <label className="block w-full border border-dashed border-white/10 hover:border-[#00F0FF]/50 transition-all p-6 text-center cursor-pointer relative bg-white/5">
                <input type="file" multiple accept="image/*" onChange={handleFileChange} className="hidden" />
                <div className="text-[10px] tracking-widest text-gray-400 uppercase group-hover:text-[#00F0FF] transition-colors">
                  {items.length > 0 ? `[ ${items.length} IMAGES SELECTED ]` : "[ SELECT IMAGES ]"}
                </div>
              </label>

              {items.length > 0 && (
                <div className="mt-4 flex gap-2 overflow-x-auto custom-scrollbar pb-2 pt-1">
                  {items.map((item, idx) => (
                    <div 
                      key={item.id} 
                      onClick={() => setActiveIndex(idx)}
                      className={`relative w-16 h-16 shrink-0 cursor-pointer transition-all ${activeIndex === idx ? 'border-2 border-[#00F0FF] scale-105' : 'border border-white/10 opacity-60 hover:opacity-100'}`}
                    >
                      <img src={item.preview} className="w-full h-full object-cover" />
                      {item.status === 'done' && <div className="absolute top-1 right-1 w-2.5 h-2.5 bg-[#D4FF00] rounded-full border border-black shadow-lg"></div>}
                      {['processing', 'queued', 'uploading'].includes(item.status) && <div className="absolute top-1 right-1 w-2.5 h-2.5 bg-[#00F0FF] rounded-full border border-black animate-pulse shadow-lg"></div>}
                      {['failed', 'error'].includes(item.status) && <div className="absolute top-1 right-1 w-2.5 h-2.5 bg-[#FF003C] rounded-full border border-black shadow-lg"></div>}
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="glass-panel p-5 relative overflow-hidden shrink-0">
               <div className="absolute top-0 left-0 w-1 h-full bg-white/10 hover:bg-[#D4FF00] transition-colors"></div>
               <h2 className="font-display text-lg mb-6 tracking-wide text-white uppercase flex justify-between items-end border-b border-white/5 pb-2">
                <span>02. Parameters</span>
                <span className="text-[9px] text-gray-600 tracking-widest">[ SYS_CONF ]</span>
              </h2>

              <div className="space-y-8">
                <div className="group">
                  <label className="text-[9px] tracking-widest text-gray-500 block mb-2 uppercase group-hover:text-white transition-colors">Neural Core Model</label>
                  <div className="relative">
                    <select
                      value={modelName}
                      onChange={(e) => setModelName(e.target.value)}
                      className="w-full bg-black/50 border border-white/10 text-gray-300 p-2 text-[10px] tracking-wider focus:outline-none focus:border-[#D4FF00] transition-colors appearance-none cursor-pointer"
                    >
                      <option value="isnet-general-use">ISNet [ High Freq / Hair ]</option>
                      <option value="u2net">U2NET [ Standard ]</option>
                      <option value="isnet-anime">ISNet Anime [ Vector ]</option>
                      <option value="u2netp">U2NETp [ Fast ]</option>
                    </select>
                    <div className="absolute right-3 top-1/2 -translate-y-1/2 w-1.5 h-1.5 bg-[#D4FF00]/50 rotate-45 pointer-events-none"></div>
                  </div>
                </div>

                <div className="space-y-5">
                  <label className="flex items-start cursor-pointer group">
                    <div className="relative mt-1 mr-3">
                      <input type="checkbox" className="sr-only" checked={autoCleanup} onChange={(e) => setAutoCleanup(e.target.checked)} />
                      <div className={`w-4 h-4 border transition-colors flex items-center justify-center ${autoCleanup ? 'border-[#00F0FF] bg-[#00F0FF]/10' : 'border-white/20 group-hover:border-white/50'}`}>
                        {autoCleanup && <div className="w-1.5 h-1.5 bg-[#00F0FF]"></div>}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-white tracking-widest uppercase mb-1">Color Pull Decon</div>
                      <div className="text-[9px] text-gray-500 leading-relaxed tracking-wider">Extracts core colors to overwrite edge halo.</div>
                    </div>
                  </label>

                  <label className="flex items-start cursor-pointer group">
                    <div className="relative mt-1 mr-3">
                      <input type="checkbox" className="sr-only" checked={upscale} onChange={(e) => setUpscale(e.target.checked)} />
                      <div className={`w-4 h-4 border transition-colors flex items-center justify-center ${upscale ? 'border-[#D4FF00] bg-[#D4FF00]/10' : 'border-white/20 group-hover:border-white/50'}`}>
                        {upscale && <div className="w-1.5 h-1.5 bg-[#D4FF00]"></div>}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-white tracking-widest uppercase mb-1">2x Neural Upscale</div>
                      <div className="text-[9px] text-gray-500 leading-relaxed tracking-wider">Deep learning pass to hallucinate detail.</div>
                    </div>
                  </label>
                </div>

                <div className="space-y-5 pt-4 border-t border-white/5">
                  <div className="group pt-2">
                    <div className="flex justify-between text-[9px] tracking-widest text-gray-500 uppercase mb-3 group-hover:text-white transition-colors">
                      <span>Erosion Threshold</span>
                      <span className="text-[#00F0FF]">[{erodeSize}px]</span>
                    </div>
                    <input type="range" min="0" max="10" value={erodeSize} onChange={(e) => setErodeSize(parseInt(e.target.value))} />
                  </div>

                  <div className="group">
                    <div className="flex justify-between text-[9px] tracking-widest text-gray-500 uppercase mb-3 group-hover:text-white transition-colors">
                      <span>Edge Softness</span>
                      <span className="text-[#00F0FF]">[{blurSize}px]</span>
                    </div>
                    <input type="range" min="0" max="15" step="1" value={blurSize} onChange={(e) => setBlurSize(parseInt(e.target.value))} />
                  </div>
                </div>
              </div>
            </div>

            <div className="shrink-0 flex flex-col gap-3">
              <button
                onClick={uploadAll}
                disabled={items.length === 0 || isProcessingAny}
                className={`w-full p-4 font-display font-bold text-xs tracking-[0.2em] uppercase transition-all flex items-center justify-center gap-2
                  ${isProcessingAny ? 'cyber-button executing' : 
                    (doneCount === items.length && items.length > 0) ? 'cyber-button' : 'cyber-button ready'} 
                  disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                {isProcessingAny
                  ? <span>[ EXECUTING {items.filter(i => ['processing', 'queued', 'uploading'].includes(i.status)).length} FILES ]</span>
                  : (doneCount === items.length && items.length > 0 ? <span>[ RE-CALCULATE ALL ]</span> : <span>[ INITIATE BATCH ]</span>)}
              </button>

              {doneCount > 0 && (
                <button 
                  onClick={downloadAllZip}
                  className="w-full p-3 bg-white/5 hover:bg-[#D4FF00] hover:text-black border border-[#D4FF00]/40 transition-colors text-[10px] tracking-[0.2em] font-bold uppercase"
                >
                  + Download All ({doneCount}) as ZIP
                </button>
              )}
            </div>
          </div>

          {/* Visualization Column */}
          <div className="flex-1 flex flex-col min-h-0 stagger-2">
            <div className="glass-panel flex-1 flex flex-col min-h-0 relative">
              
              <div className="shrink-0 flex flex-wrap gap-4 justify-between items-center p-3 border-b border-white/5 bg-white/5">
                <div className="text-[9px] tracking-widest uppercase text-gray-400 flex items-center gap-2">
                  <div className="w-1.5 h-1.5 bg-[#00F0FF] animate-pulse"></div>
                  OUTPUT.VIEWPORT [ {activeItem ? `${activeIndex + 1} / ${items.length}` : 'IDLE'} ]
                </div>
                {activeItem && (
                  <div className="text-[9px] text-[#D4FF00] uppercase tracking-widest">
                    {activeItem.file.name}
                  </div>
                )}
              </div>

              <div className="flex-1 min-h-0 relative m-2 md:m-4">
                {activeItem ? (
                  <div 
                    className={`absolute inset-0 flex items-center justify-center ${bgMode !== 'custom' ? bgClasses[bgMode] : ''} border border-white/5 transition-colors duration-500 overflow-hidden`}
                    style={bgMode === 'custom' ? { backgroundColor: customBg } : {}}
                  >
                    {activeItem.status === 'done' && activeItem.result ? (
                      <>
                        <img 
                          src={activeItem.result.cutout_url} 
                          alt="Cutout" 
                          className="max-w-full max-h-full object-contain drop-shadow-2xl z-10 transition-transform duration-200"
                          style={{ transform: `scale(${zoom})`, transformOrigin: 'center center' }}
                        />
                        <a 
                          href={activeItem.result.cutout_url} 
                          download={activeItem.file.name.replace(/\.[^/.]+$/, "") + "_cutout.png"}
                          className="absolute top-4 right-4 z-30 bg-black/80 backdrop-blur border border-white/20 text-white text-[9px] tracking-[0.2em] uppercase px-4 py-3 hover:bg-[#00F0FF] hover:text-black hover:border-[#00F0FF] transition-all flex items-center gap-2 group shadow-xl"
                        >
                          <svg className="w-3 h-3 group-hover:-translate-y-0.5 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="square" strokeLinejoin="miter" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
                          Save Single
                        </a>
                      </>
                    ) : (
                      <div className="absolute inset-0 text-center flex flex-col items-center justify-center bg-black/50 backdrop-blur-sm z-20">
                        {['processing', 'queued', 'uploading'].includes(activeItem.status) ? (
                           <div className="relative w-20 h-20 flex items-center justify-center">
                             <div className="absolute inset-0 border border-[#FF003C]/20 rounded-full animate-ping"></div>
                             <div className="absolute inset-3 border border-l-transparent border-t-[#FF003C] border-r-transparent border-b-[#FF003C] rounded-full animate-spin"></div>
                             <div className="absolute inset-6 border border-l-[#00F0FF] border-t-transparent border-r-[#00F0FF] border-b-transparent rounded-full animate-spin" style={{animationDirection: 'reverse', animationDuration: '1.5s'}}></div>
                             <div className="text-[9px] font-bold text-white tracking-widest absolute uppercase">{activeItem.status}</div>
                           </div>
                        ) : activeItem.status === 'error' || activeItem.status === 'failed' ? (
                           <div className="text-[10px] tracking-[0.4em] font-display uppercase text-[#FF003C]">Extraction Failed</div>
                        ) : (
                           <img src={activeItem.preview} className="max-w-full max-h-full object-contain opacity-30 mix-blend-screen grayscale" />
                        )}
                      </div>
                    )}
                     
                     <div className="absolute inset-0 pointer-events-none border border-white/10 z-20"></div>

                     {/* Main Floating Controls: Bg Picker and Zoom */}
                     <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-40 flex flex-col sm:flex-row items-center gap-4 sm:gap-6 glass-panel px-6 py-4 rounded-xl sm:rounded-full border border-white/20 shadow-[0_10px_40px_rgba(0,0,0,0.8)] backdrop-blur-xl">
                       
                       <div className="flex items-center gap-4 sm:border-r border-white/20 sm:pr-6">
                         <span className="text-[10px] tracking-[0.2em] text-gray-400 uppercase font-bold">Bg_Color:</span>
                         <div className="flex items-center gap-3">
                           {['checkerboard', 'black', 'white', 'green', 'gray'].map(mode => (
                             <button 
                               key={mode} 
                               onClick={() => setBgMode(mode)}
                               className={`w-6 h-6 rounded-full border-2 transition-all hover:scale-125 ${bgMode === mode ? 'border-[#00F0FF] scale-110 shadow-[0_0_15px_rgba(0,240,255,0.6)]' : 'border-white/20'} ${bgClasses[mode]}`}
                               title={mode}
                             />
                           ))}
                           <div className="w-px h-4 bg-white/20 mx-1"></div>
                           {/* Custom BG Color Wheel Toggle */}
                           <label 
                             className={`relative w-6 h-6 rounded-full border-2 transition-all hover:scale-125 cursor-pointer flex items-center justify-center ${bgMode === 'custom' ? 'border-[#00F0FF] scale-110 shadow-[0_0_15px_rgba(0,240,255,0.6)]' : 'border-white/20'}`} 
                             style={{ backgroundColor: customBg }} 
                             title="Custom BG"
                           >
                             <input type="color" value={customBg} onChange={(e) => { setCustomBg(e.target.value); setBgMode('custom'); }} className="opacity-0 absolute inset-0 w-full h-full cursor-pointer" />
                           </label>
                         </div>
                       </div>
                       
                       <div className="flex items-center gap-3">
                         <span className="text-[10px] tracking-[0.2em] text-gray-400 uppercase font-bold">Zoom:</span>
                         <button onClick={() => setZoom(z => Math.max(0.5, z - 0.25))} className="w-6 h-6 flex items-center justify-center bg-white/5 hover:bg-[#00F0FF]/20 text-[#00F0FF] border border-[#00F0FF]/30 rounded transition-colors font-bold">-</button>
                         <span className="text-xs text-white w-10 text-center font-mono font-bold">{Math.round(zoom * 100)}%</span>
                         <button onClick={() => setZoom(z => Math.min(5, z + 0.25))} className="w-6 h-6 flex items-center justify-center bg-white/5 hover:bg-[#00F0FF]/20 text-[#00F0FF] border border-[#00F0FF]/30 rounded transition-colors font-bold">+</button>
                         <button onClick={() => setZoom(1)} className="text-[9px] text-gray-500 hover:text-white ml-2 tracking-[0.2em] uppercase transition-colors">Reset</button>
                       </div>

                     </div>
                  </div>
                ) : (
                  <div className="absolute inset-0 text-center flex flex-col items-center justify-center border border-white/5 bg-white/[0.02]">
                     <div className="w-px h-16 bg-gradient-to-b from-transparent to-[#00F0FF]/30 mb-4"></div>
                     <div className="text-[10px] tracking-[0.4em] font-display uppercase text-gray-500">Awaiting Signal</div>
                     <div className="text-[9px] tracking-widest text-gray-700 mt-2 uppercase">System Idle</div>
                  </div>
                )}
              </div>
              
              <div className="shrink-0 h-1 w-full bg-gradient-to-r from-transparent via-[#00F0FF]/20 to-transparent"></div>
            </div>
          </div>

        </div>
      </div>
    </div>
  )
}

export default App
"""
with open('/a0/usr/workdir/bg-removal-service/bg-removal-service/frontend/web-ui/src/App.tsx', 'w') as f:
    f.write(app_code)

print("Batch feature written. Rebuilding and restarting...")
