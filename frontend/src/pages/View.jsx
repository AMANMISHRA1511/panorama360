import { useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowRight, Check, ChevronDown, Copy, Download, ExternalLink, Film, Image as ImageIcon, Link2, Share2, SlidersHorizontal } from 'lucide-react';
import api, { apiError } from '../lib/api';
import { API_BASE } from '../lib/api';
import { useAsset } from '../hooks/useAsset';
import { useUI } from '../context/UIContext';
import Viewer360 from '../components/Viewer360';
import { BackLink, ErrorState, Loading } from '../components/Widgets';
export async function downloadImageAsPNG(src, name) {
 const image = new window.Image(); image.crossOrigin = 'anonymous'; image.src = src;
 await image.decode();const canvas=document.createElement('canvas');canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;
 canvas.getContext('2d').drawImage(image,0,0);
 const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
 if(!blob) throw new Error('PNG conversion failed');
 const blobUrl=URL.createObjectURL(blob), anchor=document.createElement('a');anchor.href=blobUrl;anchor.download=name;anchor.click();setTimeout(()=>URL.revokeObjectURL(blobUrl),2000);
}
function downloadBlob(url, filename) {const anchor=document.createElement('a');anchor.href=url;anchor.download=filename;document.body.appendChild(anchor);anchor.click();anchor.remove();}
export default function View() {
 const {id}=useParams(),{toast}=useUI(),[job,setJob]=useState(null),[error,setError]=useState(null),[compare,setCompare]=useState(false),[split,setSplit]=useState(50);
 useEffect(()=>{let active=true;api.get(`/result/${id}`).then(({data})=>{if(active)setJob(data)}).catch(e=>{if(active)setError(apiError(e))});return()=>{active=false;};},[id]);
 const {url,loading,error:assetError}=useAsset(job?.asset_url);
 const {url:original}=useAsset(compare?job?.original_url:null);
 if(error)return <div className="page site-container"><ErrorState error={error}/></div>;
 if(!job)return <div className="page site-container"><Loading/></div>;
 if(job.status!=='done')return <div className="page site-container"><ErrorState error="This project has not finished processing."/><Link to={`/processing/${id}`} className="btn btn-primary">View processing progress</Link></div>;
 const isVideo=job.mime==='video/mp4';
 const partial=job.stage?.startsWith('Partial panorama');
 const save=async(type)=>{if(!url)return;try{const basename=(job.title||'panorama').replace(/[^\w-]+/g,'-');if(type==='png'){await downloadImageAsPNG(url,`${basename}.png`);}else{downloadBlob(url,`${basename}.${isVideo?'mp4':'jpg'}`);}toast('Download started','success');}catch(e){toast(e.message,'error');}};
 const copy=async()=>{try{await navigator.clipboard.writeText(job.share_url);toast('Public share link copied!','success');}catch{toast('Could not copy link. Use the share URL below.','error');}};
 const share=async()=>{if(navigator.share){try{await navigator.share({title:job.title,url:job.share_url});}catch{}}else copy();};
 return <div className="page site-container view-page"><BackLink/><div className="view-header"><div><div className="eyebrow"><span className="eyebrow-pip"/> YOUR IMMERSIVE EXPERIENCE</div><h1>{job.title}</h1><p>{partial?'This is a partial spherical preview, not a complete 360° capture. Unphotographed directions are shown as a neutral background.':'Look around. The whole world is yours to explore.'}</p></div><span className="view-badge"><Check size={15}/> {partial?'PARTIAL PREVIEW':'READY TO EXPLORE'}</span></div>
 {!partial&&!isVideo&&<div className="capture-footnote" style={{marginBottom:12}}>Download 360° JPG to keep the Photo Sphere XMP metadata. PNG is a flat equirectangular export without Photo Sphere metadata.</div>}
 {partial&&<div className="error-banner" role="status">{job.stage}. The missing views cannot be reconstructed from the uploaded photos. For a complete 360° photo, capture overlapping views all around, plus ceiling and floor.</div>}
 {assetError&&<div className="error-banner">{assetError}</div>}
 <Viewer360 url={url} video={isVideo}/>
 <div className="view-tools"><div className="view-tools-left"><span className="view-filetype">{isVideo?<Film size={16}/>:<ImageIcon size={16}/>} {isVideo?'H.264 MP4':'Equirectangular JPG'}</span><span>{partial?'Partial sphere (not a full 360° photo)':'360° Equirectangular Photo Sphere'}</span></div><div className="view-tools-right">
 {!isVideo&&<button className="btn btn-secondary" onClick={()=>setCompare(!compare)}><SlidersHorizontal size={17}/> {compare?'Hide comparison':'Before / After'}</button>}
 <button className="btn btn-secondary" disabled={!url} onClick={()=>save(isVideo?'mp4':'jpg')}><Download size={17}/> {isVideo?'Download MP4':partial?'Download partial JPG':'Download 360° JPG'}</button>
 {!isVideo&&<button className="btn btn-secondary" disabled={!url} onClick={()=>save('png')}><Download size={17}/> Download PNG</button>}
 <button className="btn btn-primary" onClick={share}><Share2 size={17}/> Share</button></div></div>
 {compare&&!isVideo&&<div className="compare-panel"><h3>Before & after</h3><p>Slide to compare the original flat file with the final 360° projection.</p><div className="compare-stage">{url&&<img src={url} alt="Enhanced panorama"/>}{original&&<div className="compare-original" style={{width:`${split}%`}}><img src={original} style={{width:`${10000/split}%`}} alt="Original flat input"/></div>}<div className="compare-divider" style={{left:`${split}%`}}/></div><input type="range" aria-label="Before/after split" min={1} max={99} value={split} onChange={e=>setSplit(Number(e.target.value))}/><div className="compare-captions"><span>Original file (left)</span><span>Processed panorama (right)</span></div></div>}
 <div className="share-panel"><div className="share-icon"><Link2 size={21}/></div><div className="share-description"><h3>Take everyone along</h3><p>Share this panorama with anyone. No account needed to view it.</p><code>{job.share_url}</code></div><div className="share-actions"><button className="btn btn-secondary" onClick={copy}><Copy size={17}/> Copy link</button><Link className="btn btn-secondary" to={`/s/${job.share_url.split('/s/')[1]}`} target="_blank"><ExternalLink size={17}/> Open public view</Link></div></div>
 </div>;
}
