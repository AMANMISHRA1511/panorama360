import { useEffect, useState } from 'react';
import { useUI } from '../context/UIContext';
import { Link, useParams } from 'react-router-dom';
import { ArrowRight, Aperture, Download, Share2 } from 'lucide-react';
import axios from 'axios';
import { API_BASE, apiError } from '../lib/api';
import Viewer360 from '../components/Viewer360';
import { ErrorState, Loading } from '../components/Widgets';
export default function Share() {
 const {token}=useParams(),[job,setJob]=useState(null),[error,setError]=useState(null);
 const {toast}=useUI();
 useEffect(()=>{let alive=true;axios.get(`${API_BASE}/share/${token}`).then(({data})=>{if(alive)setJob(data)}).catch(e=>{if(alive)setError(apiError(e))});return()=>{alive=false;};},[token]);
 if(error)return <div className="page site-container"><ErrorState error={error}/><Link to="/" className="btn btn-secondary">Visit Panorama Studio</Link></div>;
 if(!job)return <div className="page site-container"><Loading text="Opening the shared world..."/></div>;
 const url=`${API_BASE}${job.asset_url}`,isVideo=job.mime==='video/mp4';
 const download=async()=>{
   try {
     const response=await axios.get(url,{responseType:'blob'});
     const object=URL.createObjectURL(response.data);
     const anchor=document.createElement('a');anchor.href=object;
     anchor.download=`${(job.title||'panorama').replace(/[^\w-]+/g,'-')}.${isVideo?'mp4':'jpg'}`;
     document.body.appendChild(anchor);anchor.click();anchor.remove();
     setTimeout(()=>URL.revokeObjectURL(object),2000);
     toast('Download started','success');
   } catch(e) {toast(apiError(e),'error');}
 };
 return <div className="page site-container view-page"><div className="view-header"><div><div className="eyebrow"><span className="eyebrow-pip"/> SHARED WITH YOU</div><h1>{job.title}</h1><p>Explore this moment from every angle.</p></div><span className="view-badge"><Aperture size={16}/> SHARED 360° VIEW</span></div>
 <Viewer360 url={url} video={isVideo}/><div className="view-tools"><span>Drag to look around · Scroll to zoom · Use fullscreen for immersion</span><button className="btn btn-primary" onClick={download}><Download size={16}/> Get media</button></div>
 <div className="share-panel"><div className="share-icon"><Aperture size={22}/></div><div className="share-description"><h3>Make your own immersive view</h3><p>Turn your own photos and videos into a 360° experience.</p></div><Link to="/upload" className="btn btn-primary">Try Panorama Studio <ArrowRight size={17}/></Link></div></div>;
}
