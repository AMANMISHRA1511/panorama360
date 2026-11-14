import { useCallback, useRef, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Aperture, ArrowRight, Camera, Check, CloudUpload, Film, Image as ImageIcon, Images, Info, Plus, Sparkles, Trash2, WandSparkles, X } from 'lucide-react';
import api, { apiError } from '../lib/api';
import { useUI } from '../context/UIContext';
import { PageHead } from '../components/Widgets';
const modes = [
 {id:'single', title:'Single → 360°', desc:'Project a photo onto a sphere', icon:ImageIcon},
 {id:'multi', title:'Stitch photos', desc:'Combine overlapping angles', icon:Images},
 {id:'video', title:'360° video', desc:'Convert a video to 2:1 output', icon:Film},
 {id:'enhance', title:'Enhance only', desc:'Refine a 2:1 panorama', icon:Sparkles},
 {id:'fill', title:'Repair small gaps', desc:'No invented 360° surroundings', icon:WandSparkles}
];
export default function Upload() {
 const [aiEnabled,setAiEnabled]=useState(false), [aiStrength,setAiStrength]=useState(12), [fillSmallGaps,setFillSmallGaps]=useState(false);
 const [mode,setMode]=useState('single'), [files,setFiles]=useState([]), [drag,setDrag]=useState(false),[fov,setFov]=useState(90),[title,setTitle]=useState(''),[busy,setBusy]=useState(false);
 const fileInput=useRef(null), nav=useNavigate(), {toast}=useUI();
 const accept = mode === 'video' ? 'video/mp4,video/webm,video/quicktime,video/x-msvideo,.mp4,.mov,.webm,.avi' : 'image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp';
 const selectMode = id => {setMode(id);setFiles([]);if(fileInput.current) fileInput.current.value='';};
 const addFiles = useCallback((newFiles) => {
  const incoming=Array.from(newFiles || []);
  const video = mode==='video';
  const allowed=video?['mp4','mov','webm','avi']:['jpg','jpeg','png','webp'];
  const valid=incoming.filter(f => allowed.includes(f.name.split('.').pop()?.toLowerCase()));
  if (valid.length!==incoming.length) toast(`Please select supported ${video?'video':'image'} formats.`, 'error');
  setFiles(old => {
   const limit=(mode==='multi'||mode==='fill')?32:1;
   const next=limit===1?valid.slice(0,1):[...old,...valid].slice(0,limit);
   return next;
  });
 },[mode,toast]);
 const submit=async()=>{
  if (!files.length || (mode==='multi'&&files.length<2)){toast(mode==='multi'?'Select 2 or more overlapping photos.':'Select a file first.','error');return;}
  const form=new FormData();form.append('title', title.trim() || (mode==='video'?'360 video':'My panorama'));form.append('fov',String(fov));
  if (mode!=='video') {form.append('ai_enabled', String(aiEnabled)); form.append('ai_strength', String(aiStrength/100)); form.append('ai_fill_small_gaps', String(aiEnabled&&fillSmallGaps));}
  for (const file of files) form.append(mode==='multi'||mode==='fill'?'files':'file',file);
  const endpoint={single:'/convert/single',multi:'/convert/multi',video:'/convert/video',enhance:'/enhance',fill:'/generate/missing-angles'}[mode];
  setBusy(true);
  try{const {data}=await api.post(endpoint,form,{timeout:180000});nav(`/processing/${data.id}`);}catch(err){toast(apiError(err),'error');}finally{setBusy(false);}
 };
 return <div className="page site-container"><PageHead eyebrow="CREATE SOMETHING IMMERSIVE" title={<>Your world, <span className="gradient-text">reimagined.</span></>} subtitle="Start with your favorite photos or videos. We'll help you make something extraordinary."/>
 <div className="workspace-grid"><section className="workspace-main">
 <div className="section-line"><span className="step-index">01</span><div><h2>Choose your experience</h2><p>Pick the perfect way to bring your view to life</p></div></div>
 <div className="mode-grid">{modes.map(({id,title:label,desc,icon:Icon})=><button key={id} onClick={()=>selectMode(id)} className={`mode-card ${mode===id?'mode-active':''}`}><span className="mode-icon"><Icon size={22}/></span><span className="mode-title">{label}</span><small>{desc}</small>{mode===id&&<Check className="mode-check" size={15}/>}</button>)}</div>
 <div className="section-line section-line-spaced"><span className="step-index">02</span><div><h2>Add your {mode==='video'?'video':'photos'}</h2><p>{mode==='multi'?'Use photos with 25–50% overlap, taken from the same spot.':'Drag files here or browse your device'}</p></div></div>
 <input ref={fileInput} type="file" className="sr-only" accept={accept} multiple={mode==='multi'||mode==='fill'} onChange={e=>{addFiles(e.target.files);e.target.value='';}}/>
 <div role="button" tabIndex={0} onKeyDown={e=>{if(e.key==='Enter')fileInput.current?.click();}} className={`drop-zone ${drag?'drag-active':''}`} onDragOver={e=>{e.preventDefault();setDrag(true)}} onDragLeave={()=>setDrag(false)} onDrop={e=>{e.preventDefault();setDrag(false);addFiles(e.dataTransfer.files)}} onClick={()=>fileInput.current?.click()}>
  <div className="upload-symbol"><CloudUpload size={31}/></div><h3>Drop your {mode==='video'?'video':'images'} here</h3><p>or <span>browse files</span> from your computer</p><small>{mode==='video'?'MP4, MOV, WEBM · Max 350 MB · First 240 output frames':'JPG, PNG, WEBP · Max 100 MB per photo'}</small>
 </div>
 {files.length>0&&<div className="selected-files"><div className="selected-header"><b>{files.length} file{files.length>1?'s':''} selected</b><button onClick={()=>setFiles([])}>Clear all <X size={14}/></button></div><div className="file-list">{files.map((f,i)=><FilePreview key={`${f.name}-${i}`} file={f} onRemove={()=>setFiles(old=>old.filter((_,index)=>index!==i))}/>)}</div></div>}
 <div className="section-line section-line-spaced"><span className="step-index">03</span><div><h2>Finishing touches</h2><p>Just a few details before the magic begins</p></div></div>
 <div className="settings-panel"><label>Project name <input value={title} maxLength={200} placeholder="e.g. Sunset at the summit" onChange={e=>setTitle(e.target.value)}/></label>
 {mode!=='enhance'&&<div className="fov-setting"><div><label>Camera field of view</label><b>{fov}°</b></div><input type="range" min={50} max={140} value={fov} onChange={e=>setFov(Number(e.target.value))}/><div className="range-labels"><span>Telephoto</span><span>Wide angle</span></div></div>}
 {mode!=='video'&&<div className="ai-options" style={{marginTop:20, padding:16, border:'1px solid rgba(120,145,190,.35)', borderRadius:12}}>
   <label style={{display:'flex', gap:12, alignItems:'center', cursor:'pointer'}}>
     <input type="checkbox" checked={aiEnabled} onChange={e=>setAiEnabled(e.target.checked)}/>
     <strong>Use AI enhancement (optional)</strong>
   </label>
   <p style={{margin:'8px 0 12px', fontSize:13, opacity:.8}}>Off by default: preserves photographed pixels. AI never creates a full 360° view from missing angles.</p>
   {aiEnabled&&<>
     <div className="fov-setting"><div><label>AI intensity — gentle blend</label><b>{aiStrength}%</b></div>
       <input type="range" min="0" max="25" step="1" value={aiStrength} onChange={e=>setAiStrength(Number(e.target.value))}/>
       <div className="range-labels"><span>Original</span><span>Maximum 25%</span></div>
     </div>
     <label style={{display:'flex', gap:10, alignItems:'center', marginTop:12, cursor:'pointer'}}>
       <input type="checkbox" checked={fillSmallGaps} onChange={e=>setFillSmallGaps(e.target.checked)}/>
       <span>Repair only tiny enclosed gaps (not missing room directions)</span>
     </label>
     <small style={{display:'block', opacity:.75, marginTop:8}}>If trained weights are unavailable, a mild classical image filter is used instead of trained AI.</small>
   </>}
 </div>}</div>
 <button className="btn btn-primary btn-xl full submit-create" disabled={busy||!files.length} onClick={submit}>{busy?'Uploading files...':'Create my panorama'} <ArrowRight size={19}/></button>
 </section><aside className="workspace-side"><div className="sidebar-tip"><div className="tip-icon"><Sparkles size={19}/></div><h3>Capture the extraordinary</h3><p>Good input makes the biggest difference. Here are a few pro tips for amazing results.</p>
 <div className="tip-divider"/>{['For stitching, overlap photos by at least 25%.','Rotate the camera from one fixed position.','Use a full 2:1 panorama for a complete 360° scene.','AI is optional and never invents directions you did not capture.'].map((tip,i)=><div className="tip-row" key={i}><Check size={15}/><span>{tip}</span></div>)}</div>
 <div className="sidebar-capture"><div className="capture-chip"><Camera size={19}/></div><h3>Prefer to capture live?</h3><p>Use your device camera and follow our step-by-step rotation guide.</p><Link className="text-link" to="/capture">Open live capture <ArrowRight size={17}/></Link></div>
 <div className="small-disclaimer"><Info size={16}/> A single ordinary photo cannot reveal what was behind the camera.</div></aside></div></div>;
}
function FilePreview({file,onRemove}) {
 const [url,setUrl]=useState(null);
 useCallback(()=>{},[]);
 // Local preview URL is owned by this component and revoked at unmount.
 const ref=useCallback(node=>{if(node&&file.type.startsWith('image/')) {const blob=URL.createObjectURL(file); node.src=blob; node.onload=()=>URL.revokeObjectURL(blob);}},[file]);
 return <div className="file-preview"><div className="file-thumb">{file.type.startsWith('image/')?<img ref={ref} alt={file.name}/>:<Film size={22}/>}</div><div><b title={file.name}>{file.name}</b><small>{(file.size/1024/1024).toFixed(2)} MB</small></div><button title="Remove" onClick={onRemove}><Trash2 size={16}/></button></div>;
}
