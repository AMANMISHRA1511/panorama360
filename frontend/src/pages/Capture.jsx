import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Camera, Check, Compass, Download, Info, RefreshCw, RotateCw, VideoOff, X } from 'lucide-react';
import api, { apiError } from '../lib/api';
import { useUI } from '../context/UIContext';
import { PageHead } from '../components/Widgets';

// 3 overlapping camera rings plus four ceiling and four floor shots. These are capture targets,
// not a sensor-certified measurement of actual photographed coverage.
export const FULL_CAPTURE_STEPS = [
  ...[0, 45, 90, 135, 180, 225, 270, 315].map(yaw => ({ yaw, pitch: 0, name: 'Horizon' })),
  ...[0, 45, 90, 135, 180, 225, 270, 315].map(yaw => ({ yaw, pitch: 45, name: 'Upper ring' })),
  ...[0, 45, 90, 135, 180, 225, 270, 315].map(yaw => ({ yaw, pitch: -45, name: 'Lower ring' })),
  ...[0, 90, 180, 270].map(yaw => ({ yaw, pitch: 75, name: 'Ceiling' })),
  ...[0, 90, 180, 270].map(yaw => ({ yaw, pitch: -75, name: 'Floor' })),
];
const HORIZONTAL_CAPTURE_STEPS = FULL_CAPTURE_STEPS.slice(0, 8);
const modeChoices = [
  { id: 'full', label: 'Full sphere (32 shots)', note: 'Walls + upper ring + lower ring + 4 ceiling + 4 floor' },
  { id: 'horizontal', label: 'Horizontal preview (8 shots)', note: 'Partial panorama only; ceiling and floor not captured' },
];

function makeFile(blob, name) {
  return new File([blob], name, { type: 'image/jpeg', lastModified: Date.now() });
}

export default function Capture() {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const busyCaptureRef = useRef(false);
  const motionListenerRef = useRef(null);
  const previewsRef = useRef([]);
  const navigate = useNavigate();
  const { toast } = useUI();
  const [mode, setMode] = useState('full');
  const [captures, setCaptures] = useState([]);
  const [cameraError, setCameraError] = useState(null);
  const [ready, setReady] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [sensor, setSensor] = useState(null);
  const [motionError, setMotionError] = useState(null);
  const [aiEnabled, setAiEnabled] = useState(false);
  const steps = useMemo(() => mode === 'full' ? FULL_CAPTURE_STEPS : HORIZONTAL_CAPTURE_STEPS, [mode]);
  const next = steps[captures.length];
  const percent = Math.round(captures.length / steps.length * 100);

  useEffect(() => {
    let alive = true;
    const start = async () => {
      if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
        setCameraError('Live camera requires HTTPS or localhost. A phone cannot normally use camera access on a plain http://192.168.x.x address.');
        return;
      }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1080 } },
          audio: false,
        });
        if (!alive) { stream.getTracks().forEach(t => t.stop()); return; }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
          if (alive) setReady(true);
        }
      } catch (error) {
        if (alive) setCameraError(error?.message || 'Could not open camera. Check browser permission and device connection.');
      }
    };
    start();
    return () => {
      alive = false;
      streamRef.current?.getTracks().forEach(track => track.stop());
      streamRef.current = null;
      previewsRef.current.forEach(url => URL.revokeObjectURL(url));
      previewsRef.current = [];
      if (motionListenerRef.current) window.removeEventListener('deviceorientation', motionListenerRef.current);
    };
  }, []);

  const clear = () => {
    captures.forEach(c => URL.revokeObjectURL(c.url));
    previewsRef.current = previewsRef.current.filter(url => !captures.some(c => c.url === url));
    setCaptures([]);
  };
  const changeMode = newMode => {
    if (newMode === mode) return;
    clear();
    setMode(newMode);
  };
  const removeLast = () => setCaptures(old => {
    if (!old.length) return old;
    const removed = old[old.length - 1];
    URL.revokeObjectURL(removed.url);
    previewsRef.current = previewsRef.current.filter(url => url !== removed.url);
    return old.slice(0, -1);
  });

  const enableMotion = async () => {
    try {
      if (!('DeviceOrientationEvent' in window)) throw new Error('This device does not provide motion orientation. Manual capture still works.');
      if (typeof DeviceOrientationEvent.requestPermission === 'function') {
        const permission = await DeviceOrientationEvent.requestPermission();
        if (permission !== 'granted') throw new Error('Motion permission was declined. Manual capture still works.');
      }
      if (!motionListenerRef.current) {
        motionListenerRef.current = event => {
          if (event.alpha != null) setSensor({ heading: Math.round(event.alpha), tilt: event.beta == null ? null : Math.round(event.beta) });
        };
        window.addEventListener('deviceorientation', motionListenerRef.current, { passive: true });
      }
      setMotionError(null);
    } catch (error) { setMotionError(error.message); }
  };

  const capture = async () => {
    if (busyCaptureRef.current || !next) return;
    const video = videoRef.current;
    if (!ready || !video?.videoWidth || !video?.videoHeight) return toast('Camera stream is not ready.', 'error');
    busyCaptureRef.current = true;
    try {
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext('2d');
      if (!ctx) throw new Error('Cannot access camera canvas.');
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', .94));
      if (!blob) throw new Error('Camera could not encode JPEG image.');
      const file = makeFile(blob, `ring-${next.name.toLowerCase().replace(/\W+/g, '-')}-yaw-${next.yaw}-pitch-${next.pitch}.jpg`);
      const url = URL.createObjectURL(blob);
      previewsRef.current.push(url);
      setCaptures(old => old.length < steps.length ? [...old, { file, url, target: next }] : old);
    } catch (error) { toast(error.message || 'Capture failed.', 'error'); }
    finally { busyCaptureRef.current = false; }
  };

  const submit = async () => {
    if (captures.length !== steps.length) {
      toast(`Capture all ${steps.length} planned directions before stitching.`, 'error');
      return;
    }
    const data = new FormData();
    data.append('title', mode === 'full' ? 'Live full-sphere capture' : 'Live horizontal panorama');
    data.append('fov', '90');
    data.append('ai_enabled', String(aiEnabled));
    data.append('ai_strength', aiEnabled ? '0.12' : '0');
    data.append('ai_fill_small_gaps', 'false');
    captures.forEach(shot => data.append('files', shot.file));
    setUploading(true);
    try {
      const response = await api.post('/convert/multi', data, { timeout: 300000 });
      navigate(`/processing/${response.data.id}`);
    } catch (error) { toast(apiError(error), 'error'); }
    finally { setUploading(false); }
  };

  const downloadPhoto = shot => {
    const link = document.createElement('a');
    link.href = shot.url;
    link.download = shot.file.name;
    document.body.appendChild(link);
    link.click(); link.remove();
  };

  return <div className="page site-container">
    <PageHead eyebrow="GUIDED LIVE CAPTURE" title={<>Capture a <span className="gradient-text">360° scene.</span></>}
      subtitle="Rotate the camera from one fixed position. Capture every planned direction; the backend checks whether the photos really connect."/>
    <div className="capture-layout">
      <section className="capture-camera-card">
        <div className="capture-topline"><span><span className="live-pulse"/> LIVE CAMERA</span><span>{captures.length} / {steps.length} CAPTURED</span></div>
        <div style={{padding:'12px 16px',display:'flex',gap:8,flexWrap:'wrap'}}>
          {modeChoices.map(choice => <button key={choice.id} type="button" className={`btn ${mode === choice.id ? 'btn-primary' : 'btn-secondary'}`} onClick={() => changeMode(choice.id)}>{choice.label}</button>)}
        </div>
        <div className="camera-stage" style={{minHeight:280}}>
          {cameraError ? <div className="camera-error"><VideoOff size={40}/><h3>Camera unavailable</h3><p>{cameraError}</p></div> : <video ref={videoRef} autoPlay muted playsInline style={{width:'100%',height:'100%',objectFit:'contain',transform:'none'}}/>}
          {!cameraError && <><div className="camera-guides"><div className="guide-horizontal"/><div className="guide-vertical"/><div className="guide-ring"><span>+</span></div></div>
          <div className="camera-angle-label"><Compass size={15}/> {next ? `${next.name}: turn ${next.yaw}°, tilt ${next.pitch > 0 ? '+' : ''}${next.pitch}°` : 'ALL DIRECTIONS CAPTURED'}</div></>}
        </div>
        <div className="camera-actions" style={{padding:14,alignItems:'center'}}>
          <span style={{maxWidth:200}}>{next ? `Shot ${captures.length+1}: ${next.name} — yaw ${next.yaw}°, pitch ${next.pitch}°` : 'Capture plan complete'}</span>
          <button type="button" className="capture-button" disabled={!ready || !!cameraError || !next || uploading} onClick={capture} aria-label="Capture current direction"><div><Camera size={24}/></div></button>
          <button type="button" className="icon-button" title="Retake last photo" disabled={!captures.length || uploading} onClick={removeLast}><RotateCw size={18}/></button>
          <button type="button" className="icon-button" title="Start over" disabled={!captures.length || uploading} onClick={clear}><RefreshCw size={18}/></button>
        </div>
        <div style={{padding:'0 18px 18px',fontSize:13,opacity:.85}}>Keep the camera at the <strong>same position</strong> and rotate it, not your whole body around the room. Aim for roughly 50–70% overlap. Angles are instructions, not automatically verified positions.</div>
      </section>
      <aside className="capture-progress-card">
        <div className="eyebrow"><span className="eyebrow-pip"/> CAPTURE PROGRESS</div>
        <h2>{mode === 'full' ? 'Walls, ceiling and floor.' : 'Horizontal room preview.'}</h2>
        <div className="progress-circle" style={{'--progress':`${percent}%`}}><div><strong>{percent}%</strong><small>steps captured</small></div></div>
        <p>{mode === 'full' ? '3 rows of eight shots, four ceiling and four floor shots. All 32 steps are required for submission.' : 'Eight horizontal shots. This can create only a partial sphere.'}</p>
        <div className="shot-dots" style={{flexWrap:'wrap',gap:6}}>{steps.map((step, i) => <span key={`${step.name}-${step.yaw}`} title={`${step.name} yaw ${step.yaw}° pitch ${step.pitch}°`} className={i<captures.length?'shot-done':''}>{i<captures.length?<Check size={12}/>:i+1}</span>)}</div>
        <button type="button" className="btn btn-secondary full" onClick={enableMotion}>Enable optional motion readout</button>
        {sensor && <p style={{fontSize:12}}>Phone sensor: heading {sensor.heading}°, tilt {sensor.tilt == null ? 'unknown' : `${sensor.tilt}°`}. Values depend on device calibration.</p>}
        {motionError && <p role="status" style={{fontSize:12}}>{motionError}</p>}
        <label style={{display:'flex',alignItems:'center',gap:10,margin:'16px 0'}}><input type="checkbox" checked={aiEnabled} onChange={event=>setAiEnabled(event.target.checked)}/> Gentle AI enhancement (12%) — optional</label>
        <button type="button" className="btn btn-primary btn-large full" disabled={uploading || captures.length!==steps.length} onClick={submit}>{uploading?'Uploading...':'Stitch captured photos'} <ArrowRight size={17}/></button>
        <div className="capture-footnote"><Info size={16}/> 100% of steps does NOT guarantee full sphere coverage. Results are marked partial if matching or coverage is incomplete.</div>
      </aside>
    </div>
    {captures.length>0 && <section style={{padding:'24px 0'}}><h2>Captured frames ({captures.length})</h2>
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(145px,1fr))',gap:12,marginTop:12}}>
      {captures.map((shot,i)=><div key={shot.url} style={{padding:8,border:'1px solid #56647b',borderRadius:12}}><img src={shot.url} alt={`Capture ${i+1}`} style={{width:'100%',aspectRatio:'16/10',objectFit:'cover',borderRadius:8}}/><div style={{fontSize:12,marginTop:5}}>#{i+1}: {shot.target.name} · {shot.target.yaw}°</div><button type="button" onClick={()=>downloadPhoto(shot)} style={{display:'flex',alignItems:'center',gap:5,fontSize:12,marginTop:5}}><Download size={13}/> Save frame</button></div>)}
      </div></section>}
  </div>;
}
