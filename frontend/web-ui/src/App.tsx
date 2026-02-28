import React, { useState } from 'react';

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
  const [upscaleMode, setUpscaleMode] = useState<string>('none');
  const [bgMode, setBgMode] = useState<string>('checkerboard');
  const [customBg, setCustomBg] = useState<string>('#FF00FF');
  const [zoom, setZoom] = useState<number>(1);
  const [engineState, setEngineState] = useState<'idle' | 'warming' | 'ready'>('ready');
  const isBiRefNet = modelName.toLowerCase().includes("birefnet");

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
      // Append or replace? Let's replace for a clean batch start
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
      if (!['uploading', 'queued', 'processing'].includes(item.status)) {
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
    formData.append('upscale_mode', upscaleMode);

    try {
      const res = await fetch('/api/v1/jobs', {
        method: 'POST',
        body: formData
      });
      if (!res.ok) throw new Error(await res.text() || "Server error");
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
        if (!res.ok) throw new Error(await res.text() || "Server error");
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
          color: #D4FF00;
          border-color: #D4FF00;
        }
        .cyber-button.ready::before {
          background: linear-gradient(90deg, transparent, rgba(212, 255, 0, 0.4), transparent);
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
        .custom-scrollbar::-webkit-scrollbar { width: 6px; height: 6px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: rgba(0,0,0,0.2); }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(0, 240, 255, 0.3); border-radius: 4px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #00F0FF; }
      `}</style>

      <div className="fixed top-[-20%] left-[-10%] w-[50vw] h-[50vw] bg-[#00F0FF] rounded-full mix-blend-screen filter blur-[150px] opacity-[0.03] pointer-events-none z-0"></div>

      {/* HEADER */}
      <header className="shrink-0 p-4 border-b border-white/10 flex flex-col md:flex-row items-baseline justify-between bg-black/40 z-10">
        <div>
          <h1 className="font-display text-2xl md:text-3xl font-bold tracking-tighter uppercase text-white">
            Surgical Extraction
          </h1>
          <div className="mt-1 flex items-center gap-3">
            <span className="text-[10px] tracking-[0.2em] text-[#00F0FF] border border-[#00F0FF]/30 px-2 py-0.5 rounded-sm uppercase bg-[#00F0FF]/5">
              V4 Batch Workspace
            </span>
          </div>
        </div>
      </header>

      {/* MAIN WORKSPACE */}
      <div className="flex-1 flex flex-row min-h-0 relative z-10">
        
        {/* LEFT SIDEBAR (No Scrolling Needed) */}
        <div className="w-[320px] shrink-0 flex flex-col gap-6 p-5 border-r border-white/10 bg-black/60">
          
          {/* ADD IMAGES BUTTON */}
          <label className="w-full p-6 text-center cursor-pointer border-2 border-dashed border-[#00F0FF]/40 hover:border-[#00F0FF] hover:bg-[#00F0FF]/5 transition-all group flex flex-col items-center justify-center gap-2">
            <input type="file" multiple accept="image/*" onChange={handleFileChange} className="hidden" />
            <svg className="w-6 h-6 text-[#00F0FF] group-hover:scale-110 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="square" strokeLinejoin="miter" strokeWidth="2" d="M12 4v16m8-8H4"></path></svg>
            <span className="text-[11px] tracking-[0.2em] font-bold uppercase text-white group-hover:text-[#00F0FF]">
              Add Images
            </span>
          </label>

          {/* PARAMETERS */}
          <div className="flex flex-col gap-5">
            <div className="flex justify-between items-center pb-2 border-b border-white/10">
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
            </div>

            <div className="space-y-4">
              <div className="relative">
                <select
                  value={modelName}
                  onChange={(e) => onModelChange(e.target.value)}
                  className="w-full bg-black/50 border border-white/10 text-gray-300 p-2.5 text-[10px] tracking-wider focus:outline-none focus:border-[#D4FF00] transition-colors appearance-none cursor-pointer"
                >
                  <option value="isnet-general-use">ISNet [ High Freq / Hair ]</option>
                  <option value="birefnet-general">BiRefNet [ SOTA Quality (Slow) ]</option>
                  <option value="u2net">U2NET [ Standard ]</option>
                  <option value="isnet-anime">ISNet Anime [ Vector ]</option>
                  <option value="u2netp">U2NETp [ Fast ]</option>
                </select>
                <div className="absolute right-3 top-1/2 -translate-y-1/2 w-1.5 h-1.5 bg-[#D4FF00]/50 rotate-45 pointer-events-none"></div>
              </div>

              <label className="flex items-center cursor-pointer group">
                <div className="relative mr-3">
                  <input type="checkbox" className="sr-only" checked={autoCleanup} onChange={(e) => setAutoCleanup(e.target.checked)} />
                  <div className={`w-4 h-4 border transition-colors flex items-center justify-center ${autoCleanup ? 'border-[#00F0FF] bg-[#00F0FF]/10' : 'border-white/20'}`}>
                    {autoCleanup && <div className="w-1.5 h-1.5 bg-[#00F0FF]"></div>}
                  </div>
                </div>
                <span className="text-[10px] text-white tracking-widest uppercase">Color Pull Decon</span>
              </label>

              <div className="relative pt-1">
                <label className="text-[9px] tracking-widest text-gray-500 block mb-2 uppercase">Neural Upscale Mode</label>
                
                <div className="relative">
                  <select
                    value={upscaleMode}
                    onChange={(e) => setUpscaleMode(e.target.value)}
                    
                    className="w-full bg-black/50 border border-white/10 text-gray-300 p-2 text-[10px] tracking-wider focus:outline-none focus:border-[#D4FF00] transition-colors appearance-none cursor-pointer"
                  >
                    <option value="none">None [ Native Res ]</option>
                    <option value="2x">2x Neural [ HQ ]</option>
                    <option value="4x_topaz">4x Topaz / 4096px [ Ultra ]</option>
                  </select>
                  <div className="absolute right-3 top-1/2 -translate-y-1/2 w-1.5 h-1.5 bg-[#D4FF00]/50 rotate-45 pointer-events-none"></div>
                </div>
              </div>
            </div>

            <div className="space-y-4 pt-3 border-t border-white/10">
              <div className="group">
                <div className="flex justify-between text-[9px] tracking-widest text-gray-400 uppercase mb-2">
                  <span>Erosion Shave</span>
                  <span className="text-[#00F0FF]">[{erodeSize}px]</span>
                </div>
                <input type="range" min="0" max="10" value={erodeSize} onChange={(e) => setErodeSize(parseInt(e.target.value))} />
              </div>

              <div className="group">
                <div className="flex justify-between text-[9px] tracking-widest text-gray-400 uppercase mb-2">
                  <span>Edge Blur</span>
                  <span className="text-[#00F0FF]">[{blurSize}px]</span>
                </div>
                <input type="range" min="0" max="15" step="1" value={blurSize} onChange={(e) => setBlurSize(parseInt(e.target.value))} />
              </div>
            </div>
          </div>

          {/* ACTION BUTTONS (Pinned to bottom of sidebar naturally) */}
          <div className="mt-auto flex flex-col gap-3 pt-6 border-t border-white/10">
            <button
              onClick={uploadAll}
              disabled={items.length === 0 || isProcessingAny || engineState === 'warming'}
              className={`w-full p-4 font-display font-bold text-[11px] tracking-[0.2em] uppercase transition-all flex items-center justify-center gap-2
                ${isProcessingAny ? 'cyber-button executing' :
                  engineState === 'warming' ? 'bg-black/80 text-[#00F0FF]/50 border border-[#00F0FF]/20 shadow-none hover:bg-black/80' :
                  (doneCount === items.length && items.length > 0) ? 'cyber-button' : 'cyber-button ready'}
                disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              {engineState === 'warming'
                ? <span>[ WARMING UP AI... ]</span>
                : isProcessingAny
                ? <span>[ EXECUTING {items.filter(i => ['processing', 'queued', 'uploading'].includes(i.status)).length} ]</span>
                : (doneCount === items.length && items.length > 0 ? <span>[ RE-RUN BATCH ]</span> : <span>[ INITIATE BATCH ]</span>)}
            </button>

            {doneCount > 0 && (
              <button 
                onClick={downloadAllZip}
                className="w-full p-3 bg-[#D4FF00]/10 hover:bg-[#D4FF00] hover:text-black border border-[#D4FF00]/40 transition-colors text-[10px] tracking-[0.2em] font-bold uppercase"
              >
                + Download ZIP ({doneCount})
              </button>
            )}
          </div>

        </div>

        {/* RIGHT SIDE (Viewport + Bottom Queue) */}
        <div className="flex-1 flex flex-col min-h-0 relative">
          
          {/* VIEWPORT */}
          <div className="flex-1 relative min-h-0">
            {activeItem ? (
              <div 
                className={`absolute inset-0 flex items-center justify-center ${bgMode !== 'custom' ? bgClasses[bgMode] : ''} transition-colors duration-500 overflow-hidden`}
                style={bgMode === 'custom' ? { backgroundColor: customBg } : {}}
              >
                {activeItem.status === 'done' && activeItem.result ? (
                  <img 
                    src={activeItem.result.cutout_url} 
                    alt="Cutout" 
                    className="max-w-full max-h-full object-contain drop-shadow-2xl z-10 transition-transform duration-200"
                    style={{ transform: `scale(${zoom})`, transformOrigin: 'center center' }}
                  />
                ) : (
                  <div className="absolute inset-0 text-center flex flex-col items-center justify-center bg-black/50 backdrop-blur-sm z-20">
                    {['processing', 'queued', 'uploading'].includes(activeItem.status) ? (
                       <div className="relative w-24 h-24 flex items-center justify-center">
                         <div className="absolute inset-0 border border-[#FF003C]/20 rounded-full animate-ping"></div>
                         <div className="absolute inset-3 border border-l-transparent border-t-[#FF003C] border-r-transparent border-b-[#FF003C] rounded-full animate-spin"></div>
                         <div className="absolute inset-6 border border-l-[#00F0FF] border-t-transparent border-r-[#00F0FF] border-b-transparent rounded-full animate-spin" style={{animationDirection: 'reverse', animationDuration: '1.5s'}}></div>
                         <div className="text-[9px] font-bold text-white tracking-widest absolute uppercase">{activeItem.status}</div>
                       </div>
                    ) : activeItem.status === 'error' || activeItem.status === 'failed' ? (
                       <div className="text-[12px] tracking-[0.4em] font-display uppercase text-[#FF003C]">Extraction Failed</div>
                    ) : (
                       <img src={activeItem.preview} className="max-w-full max-h-full object-contain opacity-40 mix-blend-screen grayscale" />
                    )}
                  </div>
                )}
                 
                 <div className="absolute inset-0 pointer-events-none border border-white/5 z-20"></div>

                 {/* Viewport Floating Controls */}
                 <div className="absolute top-4 right-4 z-40 flex flex-col items-end gap-3">
                    {activeItem.status === 'done' && activeItem.result && (
                      <a 
                        href={activeItem.result.cutout_url} 
                        download={activeItem.file.name.replace(/\.[^/.]+$/, "") + "_cutout.png"}
                        className="bg-black/80 backdrop-blur border border-white/20 text-white text-[9px] tracking-[0.2em] uppercase px-4 py-3 hover:bg-[#00F0FF] hover:text-black hover:border-[#00F0FF] transition-all flex items-center gap-2 group shadow-xl"
                      >
                        <svg className="w-3 h-3 group-hover:-translate-y-0.5 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="square" strokeLinejoin="miter" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
                        Save Image
                      </a>
                    )}
                 </div>

                 <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-40 flex items-center gap-6 glass-panel px-6 py-3 rounded-full border border-white/20 shadow-[0_10px_40px_rgba(0,0,0,0.8)]">
                   <div className="flex items-center gap-3 border-r border-white/20 pr-6">
                     {['checkerboard', 'black', 'white', 'green', 'gray'].map(mode => (
                       <button 
                         key={mode} 
                         onClick={() => setBgMode(mode)}
                         className={`w-5 h-5 rounded-full border-2 transition-all hover:scale-125 ${bgMode === mode ? 'border-[#00F0FF] scale-110 shadow-[0_0_10px_rgba(0,240,255,0.6)]' : 'border-white/20'} ${bgClasses[mode]}`}
                       />
                     ))}
                     <div className="w-px h-4 bg-white/20 mx-1"></div>
                     <label className={`relative w-5 h-5 rounded-full border-2 transition-all hover:scale-125 cursor-pointer ${bgMode === 'custom' ? 'border-[#00F0FF] scale-110 shadow-[0_0_10px_rgba(0,240,255,0.6)]' : 'border-white/20'}`} style={{ backgroundColor: customBg }}>
                       <input type="color" value={customBg} onChange={(e) => { setCustomBg(e.target.value); setBgMode('custom'); }} className="opacity-0 absolute inset-0 w-full h-full cursor-pointer" />
                     </label>
                   </div>
                   
                   <div className="flex items-center gap-3">
                     <button onClick={() => setZoom(z => Math.max(0.5, z - 0.25))} className="text-[#00F0FF] hover:text-white font-bold">-</button>
                     <span className="text-[10px] text-white w-8 text-center font-mono">{Math.round(zoom * 100)}%</span>
                     <button onClick={() => setZoom(z => Math.min(5, z + 0.25))} className="text-[#00F0FF] hover:text-white font-bold">+</button>
                     <button onClick={() => setZoom(1)} className="text-[9px] text-gray-500 hover:text-white ml-2 tracking-[0.2em] uppercase">Reset</button>
                   </div>
                 </div>

              </div>
            ) : (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-white/[0.02]">
                 <div className="text-[10px] tracking-[0.4em] uppercase text-gray-500">Viewport Idle</div>
                 <div className="text-[9px] tracking-widest text-gray-700 mt-2 uppercase">Add images to begin</div>
              </div>
            )}
          </div>

          {/* BOTTOM FILMSTRIP (THE QUEUE) */}
          <div className="h-[170px] shrink-0 border-t border-white/10 bg-black/80 flex flex-col z-20">
            <div className="flex justify-between items-center px-4 py-2 border-b border-white/5 bg-white/[0.02]">
              <span className="text-[10px] tracking-[0.3em] font-bold text-white uppercase flex items-center gap-2">
                 <div className="w-1.5 h-1.5 bg-[#D4FF00]"></div>
                 Batch Queue
              </span>
              <span className="text-[9px] tracking-widest text-gray-400 uppercase">
                {doneCount} / {items.length} Completed
              </span>
            </div>
            
            <div className="flex-1 flex gap-4 overflow-x-auto custom-scrollbar p-4 items-center">
              {items.length === 0 ? (
                <div className="text-gray-600 text-[10px] tracking-[0.2em] uppercase mx-auto border border-dashed border-gray-600/50 px-6 py-3 rounded-sm">
                  Queue is empty. Use [+ Add Images] to populate.
                </div>
              ) : (
                items.map((item, idx) => (
                  <div 
                    key={item.id} 
                    onClick={() => setActiveIndex(idx)}
                    className={`group relative w-[100px] h-[100px] shrink-0 cursor-pointer overflow-hidden transition-all 
                      ${activeIndex === idx ? 'border-2 border-[#00F0FF] shadow-[0_0_20px_rgba(0,240,255,0.3)] scale-105 z-10' : 'border border-white/20 opacity-60 hover:opacity-100 hover:border-white/50'}`}
                  >
                    <img src={item.preview} className="w-full h-full object-cover" />
                    
                    {/* Status Overlays */}
                    <div className="absolute inset-x-0 bottom-0 bg-black/90 backdrop-blur text-[8px] text-center p-1.5 tracking-widest uppercase truncate border-t border-white/10">
                      <span className={
                        item.status === 'done' ? 'text-[#D4FF00]' : 
                        item.status === 'failed' || item.status === 'error' ? 'text-[#FF003C]' :
                        ['uploading','queued','processing'].includes(item.status) ? 'text-[#00F0FF]' : 'text-gray-400'
                      }>
                        {item.status}
                      </span>
                    </div>
                    
                    {item.status === 'done' && <div className="absolute top-1 right-1 w-2 h-2 bg-[#D4FF00] rounded-full shadow-[0_0_5px_#D4FF00]"></div>}
                    {['queued','uploading','processing'].includes(item.status) && <div className="absolute top-1 right-1 w-2 h-2 bg-[#00F0FF] rounded-full shadow-[0_0_5px_#00F0FF] animate-pulse"></div>}
                    {['failed','error'].includes(item.status) && <div className="absolute top-1 right-1 w-2 h-2 bg-[#FF003C] rounded-full shadow-[0_0_5px_#FF003C]"></div>}
                  </div>
                ))
              )}
            </div>
          </div>

        </div>

      </div>
    </div>
  )
}

export default App
