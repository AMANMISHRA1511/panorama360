import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowRight, Camera, CircleAlert, CloudUpload, Film, Grid2X2, Image as ImageIcon, Plus, Search, Trash2 } from 'lucide-react';
import api, { apiError } from '../lib/api';
import { useUI } from '../context/UIContext';
import { PageHead, Skeletons } from '../components/Widgets';
import { useAsset } from '../hooks/useAsset';
export default function Gallery() {
 const [jobs,setJobs]=useState([]),[loading,setLoading]=useState(true),[error,setError]=useState(null),[search,setSearch]=useState('');
 const {toast}=useUI();
 const refresh=useCallback(async()=>{try{const {data}=await api.get('/gallery');setJobs(data);setError(null);}catch(e){setError(apiError(e));}finally{setLoading(false);}},[]);
 useEffect(()=>{refresh();},[refresh]);
 const remove=async(id)=>{if(!window.confirm('Delete this project and its uploaded media?'))return;try{await api.delete(`/gallery/${id}`);setJobs(old=>old.filter(j=>j.id!==id));toast('Project deleted','success');}catch(e){toast(apiError(e),'error');}};
 const visible=jobs.filter(j=>j.title.toLowerCase().includes(search.trim().toLowerCase()));
 return <div className="page site-container"><div className="gallery-header"><PageHead eyebrow="YOUR CREATIVE SPACE" title={<>Your <span className="gradient-text">gallery.</span></>} subtitle="Every moment you've expanded, all in one place."/><Link to="/upload" className="btn btn-primary btn-large"><Plus size={18}/> New creation</Link></div>
 <div className="gallery-toolbar"><span><Grid2X2 size={18}/> All projects <b>{jobs.length}</b></span><label className="gallery-search"><Search size={17}/><input placeholder="Search your gallery..." value={search} onChange={e=>setSearch(e.target.value)}/></label></div>
 {error&&<div className="error-banner"><CircleAlert size={17}/>{error}<button onClick={refresh}>Retry</button></div>}
 {loading?<Skeletons/>:visible.length===0?<div className="empty-gallery"><div><ImageIcon size={35}/></div><h2>{search?'No matching projects':'Your next masterpiece starts here'}</h2><p>{search?'Try a different search term.':'Upload photos or capture a scene to create your first immersive panorama.'}</p><Link to="/upload" className="btn btn-primary btn-large"><CloudUpload size={18}/> Create a panorama</Link></div>:
 <div className="gallery-grid">{visible.map((job,i)=><motion.article key={job.id} className="gallery-card" initial={{opacity:0,y:12}} animate={{opacity:1,y:0}} transition={{delay:Math.min(i*.05,.5)}}>
 <Link to={job.status==='done'?`/view/${job.id}`:`/processing/${job.id}`} className="gallery-cover"><GalleryThumb job={job}/><span className="gallery-type">{job.mime==='video/mp4'?<Film size={15}/>:<ImageIcon size={15}/>} {job.mode}</span></Link>
 <div className="gallery-card-bottom"><div><Link to={job.status==='done'?`/view/${job.id}`:`/processing/${job.id}`}><h3>{job.title}</h3></Link><span>{new Date(job.created_at).toLocaleDateString()} <span className="meta-dot">·</span> <span className={`status-text status-${job.status}`}>{job.status}</span></span></div><button className="icon-button" title="Delete project" onClick={()=>remove(job.id)}><Trash2 size={17}/></button></div>
 </motion.article>)}</div>}</div>;
}
function GalleryThumb({job}) {
 const {url}=useAsset(job.mime?.startsWith('image/')?job.asset_url:null);
 if(job.status!=='done')return <div className="thumb-placeholder"><Camera size={40}/><span>{job.progress}%</span></div>;
 if(job.mime==='video/mp4')return <div className="thumb-placeholder video-thumb"><Film size={40}/><span>360° video</span></div>;
 return url?<img src={url} alt={job.title} loading="lazy"/>:<div className="thumb-placeholder"><ImageIcon size={35}/></div>;
}
