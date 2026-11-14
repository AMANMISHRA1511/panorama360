import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import {
  Expand, Minimize, Pause, Play, RotateCcw,
  Smartphone, ZoomIn, ZoomOut,
} from 'lucide-react';
import { useUI } from '../context/UIContext';

const DEFAULT_VIEW = { yaw: 0, pitch: 0, fov: 78 };

function PanoramaSphere({ url, video, reportStatus, videoElementRef }) {
  const [texture, setTexture] = useState(null);

  useEffect(() => {
    let active = true;
    let loadedTexture = null;
    let videoElement = null;

    setTexture(null);
    reportStatus('loading');

    if (video) {
      videoElement = document.createElement('video');
      videoElement.crossOrigin = 'anonymous';
      videoElement.loop = true;
      videoElement.muted = true;
      videoElement.playsInline = true;
      videoElement.preload = 'auto';
      videoElementRef.current = videoElement;

      videoElement.onloadeddata = () => {
        if (!active) return;
        loadedTexture = new THREE.VideoTexture(videoElement);
        loadedTexture.colorSpace = THREE.SRGBColorSpace;
        setTexture(loadedTexture);
        reportStatus('ready');
        videoElement.play().catch(() => {
          if (active) reportStatus('paused');
        });
      };
      videoElement.onerror = () => {
        if (active) reportStatus('error: Cannot load the 360° video. Check the media URL and format.');
      };
      videoElement.src = url;
      videoElement.load();
    } else {
      const loader = new THREE.TextureLoader();
      loader.setCrossOrigin('anonymous');
      loader.load(
        url,
        (imageTexture) => {
          if (!active) {
            imageTexture.dispose();
            return;
          }
          loadedTexture = imageTexture;
          loadedTexture.colorSpace = THREE.SRGBColorSpace;
          setTexture(loadedTexture);
          reportStatus('ready');
        },
        undefined,
        () => {
          if (active) reportStatus('error: Cannot load the panorama image. Check the download URL, API authentication, or CORS settings.');
        },
      );
    }

    return () => {
      active = false;
      if (videoElement) {
        videoElement.pause();
        videoElement.onloadeddata = null;
        videoElement.onerror = null;
        videoElement.removeAttribute('src');
        videoElement.load();
        if (videoElementRef.current === videoElement) videoElementRef.current = null;
      }
      loadedTexture?.dispose();
    };
  }, [url, video, reportStatus]);

  if (!texture) return null;

  // Render the INSIDE of the sphere. Do not combine negative mesh scaling
  // with FrontSide: that combination can make the panorama invisible.
  return (
    <mesh>
      <sphereGeometry args={[100, 80, 48]} />
      <meshBasicMaterial
        map={texture}
        side={THREE.BackSide}
        toneMapped={false}
        depthWrite={false}
      />
    </mesh>
  );
}

function CameraMotion({ view, auto }) {
  const { camera } = useThree();
  const autoOffset = useRef(0);

  useFrame((_, delta) => {
    if (auto) autoOffset.current += Math.min(delta, 0.1) * 0.07;
    camera.rotation.order = 'YXZ';
    camera.rotation.set(view.pitch, view.yaw + autoOffset.current, 0);
    if (camera.fov !== view.fov) {
      camera.fov = view.fov;
      camera.updateProjectionMatrix();
    }
  });

  return null;
}

export default function Viewer360({ url, video = false }) {
  const root = useRef(null);
  const pointer = useRef(null);
  const videoElementRef = useRef(null);
  const [view, setView] = useState(DEFAULT_VIEW);
  const [auto, setAuto] = useState(false);
  const [full, setFull] = useState(false);
  const [gyro, setGyro] = useState(false);
  const [status, setStatus] = useState(url ? 'loading' : 'missing');
  const { toast } = useUI();

  useEffect(() => {
    setStatus(url ? 'loading' : 'missing');
  }, [url, video]);

  useEffect(() => {
    const onFullscreen = () => setFull(Boolean(document.fullscreenElement));
    document.addEventListener('fullscreenchange', onFullscreen);
    return () => document.removeEventListener('fullscreenchange', onFullscreen);
  }, []);

  useEffect(() => {
    if (!gyro) return;
    const onOrientation = (event) => {
      if (event.alpha === null || event.beta === null) return;
      setView((previous) => ({
        ...previous,
        yaw: THREE.MathUtils.degToRad(event.alpha),
        pitch: THREE.MathUtils.clamp(
          THREE.MathUtils.degToRad(event.beta - 90), -1.45, 1.45,
        ),
      }));
    };
    window.addEventListener('deviceorientation', onOrientation);
    return () => window.removeEventListener('deviceorientation', onOrientation);
  }, [gyro]);

  const activateGyro = async () => {
    if (gyro) {
      setGyro(false);
      return;
    }
    try {
      if (!('DeviceOrientationEvent' in window)) {
        throw new Error('Motion sensor is not available on this device.');
      }
      if (typeof DeviceOrientationEvent.requestPermission === 'function') {
        const permission = await DeviceOrientationEvent.requestPermission();
        if (permission !== 'granted') throw new Error('Motion sensor permission denied.');
      }
      setGyro(true);
      toast('Gyroscope enabled');
    } catch (error) {
      toast(error.message || 'Unable to start gyroscope', 'error');
    }
  };

  const zoom = (amount) => {
    setView((previous) => ({
      ...previous,
      fov: THREE.MathUtils.clamp(previous.fov + amount, 35, 110),
    }));
  };

  const reset = () => {
    setView({ ...DEFAULT_VIEW });
    setAuto(false);
    setGyro(false);
  };

  const onPointerMove = (event) => {
    if (!pointer.current || gyro) return;
    const dx = event.clientX - pointer.current.x;
    const dy = event.clientY - pointer.current.y;
    pointer.current = { x: event.clientX, y: event.clientY };
    setView((previous) => ({
      ...previous,
      yaw: previous.yaw - dx * 0.005,
      pitch: THREE.MathUtils.clamp(previous.pitch - dy * 0.005, -1.45, 1.45),
    }));
  };

  const message = status.startsWith('error:')
    ? status.slice('error:'.length).trim()
    : status === 'missing'
      ? 'No panorama image URL was provided.'
      : status === 'paused'
        ? 'Video autoplay is blocked. Click Play video to start.'
        : 'Loading 360° panorama…';

  return (
    <div className="viewer-shell" ref={root}>
      <div
        className="viewer-canvas"
        style={{ touchAction: 'none' }}
        onPointerDown={(event) => {
          pointer.current = { x: event.clientX, y: event.clientY };
          event.currentTarget.setPointerCapture(event.pointerId);
        }}
        onPointerMove={onPointerMove}
        onPointerUp={() => { pointer.current = null; }}
        onPointerCancel={() => { pointer.current = null; }}
        onWheel={(event) => zoom(event.deltaY > 0 ? 4 : -4)}
      >
        {url && (
          <Canvas
            camera={{ position: [0, 0, 0], fov: DEFAULT_VIEW.fov, near: 0.1, far: 150 }}
            gl={{ antialias: true }}
            fallback={<div className="viewer-fallback">WebGL is unavailable. Enable browser graphics acceleration.</div>}
          >
            <PanoramaSphere key={`${video}:${url}`} url={url} video={video} reportStatus={setStatus} videoElementRef={videoElementRef} />
            <CameraMotion view={view} auto={auto} />
          </Canvas>
        )}
        {status !== 'ready' && (
          <div
            role={status.startsWith('error:') ? 'alert' : 'status'}
            style={{
              position: 'absolute', inset: 0, display: 'grid', placeItems: 'center',
              padding: 32, textAlign: 'center', color: '#e2ecff',
              background: 'rgba(8, 18, 36, .55)', pointerEvents: status === 'paused' ? 'auto' : 'none',
              fontSize: 15, zIndex: 1,
            }}
          >
            <div>
              <p>{message}</p>
              {status === 'paused' && (
                <button
                  type="button"
                  onClick={async () => {
                    try {
                      await videoElementRef.current?.play();
                      setStatus('ready');
                    } catch {
                      toast('Video playback was blocked', 'error');
                    }
                  }}
                  style={{ marginTop: 12, background: '#3b82f6', color: '#fff', padding: '10px 18px', borderRadius: 8 }}
                >
                  Play video
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="viewer-info">
        <span className="live-pulse" /> 360° IMMERSIVE VIEW
        <span className="viewer-info-sub">Drag to explore · Scroll to zoom</span>
      </div>
      <div className="viewer-controls">
        <div className="control-group">
          <button title="Zoom in" onClick={() => zoom(-10)}><ZoomIn size={18} /></button>
          <button title="Zoom out" onClick={() => zoom(10)}><ZoomOut size={18} /></button>
          <button title="Reset view" onClick={reset}><RotateCcw size={17} /></button>
        </div>
        <div className="control-group">
          <button className={auto ? 'selected' : ''} title="Auto rotate" onClick={() => setAuto(!auto)}>
            {auto ? <Pause size={18} /> : <Play size={18} />}
          </button>
          <button className={gyro ? 'selected' : ''} title="Use mobile gyroscope" onClick={activateGyro}>
            <Smartphone size={18} />
          </button>
          <button
            title="Fullscreen"
            onClick={async () => {
              try {
                if (!document.fullscreenElement) await root.current.requestFullscreen();
                else await document.exitFullscreen();
              } catch {
                toast('Fullscreen not supported', 'error');
              }
            }}
          >
            {full ? <Minimize size={18} /> : <Expand size={18} />}
          </button>
        </div>
      </div>
    </div>
  );
}
