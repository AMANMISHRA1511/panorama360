import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowRight,
  Check,
  CircleAlert,
  Clock3,
  LoaderCircle,
  Waves,
} from 'lucide-react';
import api, { apiError, wsUrl } from '../lib/api';
import { BackLink } from '../components/Widgets';

const stages = ['Features', 'Matching', 'Warping', 'Blending', 'AI fill', 'Enhance'];
const stageThresholds = [8, 22, 40, 58, 76, 90];
const isFinished = (status) => status === 'done' || status === 'failed';

export default function Processing() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);
  const [connection, setConnection] = useState('Connecting');
  const [noProgress, setNoProgress] = useState(false);
  const lastStep = useRef({ key: '', changedAt: Date.now() });

  useEffect(() => {
    let active = true;
    let finished = false;
    let socket = null;
    let intervalId = null;

    setJob(null);
    setError(null);
    setConnection('Connecting');
    setNoProgress(false);
    lastStep.current = { key: '', changedAt: Date.now() };

    const noteUpdate = (data) => {
      const key = `${data.status ?? ''}|${data.progress ?? ''}|${data.stage ?? ''}`;
      const previous = lastStep.current;
      if (key !== previous.key) {
        lastStep.current = { key, changedAt: Date.now() };
        setNoProgress(false);
      } else if (!isFinished(data.status) && Date.now() - previous.changedAt > 60000) {
        setNoProgress(true);
      }
    };

    const stopUpdates = () => {
      finished = true;
      if (intervalId !== null) {
        clearInterval(intervalId);
        intervalId = null;
      }
      if (socket && socket.readyState < WebSocket.CLOSING) {
        socket.close();
      }
    };

    const poll = async () => {
      if (!active || finished) return;
      try {
        const { data } = await api.get(`/result/${id}`);
        if (!active) return;
        noteUpdate(data);
        setJob(data);
        setError(null);
        if (isFinished(data.status)) stopUpdates();
      } catch (err) {
        if (active && !finished) {
          setError(apiError(err));
          setConnection('Polling');
        }
      }
    };

    void poll();
    intervalId = setInterval(() => {
      void poll();
    }, 3000);

    try {
      socket = new WebSocket(wsUrl(id));
      socket.onopen = () => {
        if (active && !finished) setConnection('Live');
      };
      socket.onmessage = (event) => {
        if (!active || finished) return;
        try {
          const data = JSON.parse(event.data);
          if (!data || typeof data !== 'object') return;
          if (data.status != null && data.progress != null && data.stage != null) {
            noteUpdate(data);
          }
          setJob((previous) => ({ ...(previous || {}), ...data }));
          if (isFinished(data.status)) void poll();
        } catch {
          // Ignore malformed WebSocket messages; HTTP polling still runs.
        }
      };
      socket.onerror = () => {
        if (active && !finished) setConnection('Polling');
      };
      socket.onclose = () => {
        if (active && !finished) setConnection('Polling');
      };
    } catch {
      setConnection('Polling');
    }

    return () => {
      active = false;
      stopUpdates();
    };
  }, [id]);

  if (error && !job) {
    return (
      <div className="page site-container">
        <div className="center-state" role="alert">
          <CircleAlert size={28} />
          <h3>Unable to load your job</h3>
          <p>{error}</p>
          <Link to="/upload" className="btn btn-secondary">Back to upload</Link>
        </div>
      </div>
    );
  }

  const progress = Math.max(0, Math.min(100, Number(job?.progress) || 0));
  const failed = job?.status === 'failed';
  const complete = job?.status === 'done';
  const processing = !failed && !complete;
  const partial = complete && job?.stage?.startsWith('Partial panorama');

  return (
    <div className="page site-container process-page">
      <BackLink to="/upload">Back to creation</BackLink>
      <div className="process-card">
        <motion.div
          className="process-symbol"
          animate={
            failed ? { rotate: 0 } :
            complete ? { scale: [1, 1.15, 1] } :
            { rotate: 360 }
          }
          transition={
            failed ? { duration: 0 } :
            complete ? { duration: 0.7, repeat: 0 } :
            { duration: 8, repeat: Infinity, ease: 'linear' }
          }
        >
          {failed ? <CircleAlert size={37} /> : <Waves size={37} />}
        </motion.div>

        <div className="eyebrow">
          <span className="eyebrow-pip" />{' '}
          {partial ? 'PARTIAL PANORAMA' : complete ? 'YOUR PANORAMA IS READY' : failed ? 'PROCESSING FAILED' : 'MAKING SOMETHING SPECIAL'}
        </div>

        <h1>
          {partial ? 'A partial preview is ready.' : complete ? 'Your world, expanded.' : failed ? 'Could not complete this job.' : (
            <>Bringing every angle <span className="gradient-text">together.</span></>
          )}
        </h1>
        <p style={{ overflowWrap: 'anywhere' }}>
          {partial
            ? `${job.stage}. Missing camera directions are not real photographic data.`
            : complete
            ? 'Ready to step inside your immersive view.'
            : failed
              ? (job.error || 'The photos could not be stitched. Try consecutive, well-lit photos with substantial overlap.')
              : 'Our processing pipeline is transforming your media into an immersive experience.'}
        </p>

        <div className="progress-value" role={failed ? 'alert' : undefined}>
          {failed ? (
            <>
              <strong>Failed</strong>
              <span>Stopped at {progress}%</span>
            </>
          ) : (
            <>
              <strong>{progress}<span>%</span></strong>
              <span><Clock3 size={14} /> {complete ? 'Complete' : `${connection} updates`}</span>
            </>
          )}
        </div>

        <div
          className="big-progress"
          role="progressbar"
          aria-label="Job progress"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={progress}
        >
          {failed ? (
            <div style={{ width: `${progress}%`, background: '#ef4444' }} />
          ) : (
            <motion.div
              initial={false}
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.4 }}
            />
          )}
        </div>

        {processing && job?.stage && (
          <p role="status" style={{ marginTop: 12, overflowWrap: 'anywhere' }}>
            Current processing step: <strong>{job.stage}</strong>
          </p>
        )}
        {processing && noProgress && (
          <p role="alert" style={{ color: '#f59e0b', marginTop: 8 }}>
            No new progress for over 60 seconds. Check the Python worker terminal.
            Large photo sets may still be matching; do not start another job yet.
          </p>
        )}
        <div className="stage-list">
          {stages.map((stage, index) => {
            const passed = progress >= stageThresholds[index];
            return (
              <div key={stage} className={`stage-item ${passed ? 'stage-passed' : ''}`}>
                <span>{passed ? <Check size={14} /> : index + 1}</span>
                {stage}
              </div>
            );
          })}
        </div>

        {complete ? (
          <button
            type="button"
            className="btn btn-primary btn-xl full"
            onClick={() => navigate(`/view/${id}`)}
          >
            {partial ? 'View partial panorama' : 'Explore your 360° experience'} <ArrowRight size={19} />
          </button>
        ) : failed ? (
          <Link to="/upload" className="btn btn-primary btn-xl full">
            Try another upload <ArrowRight size={19} />
          </Link>
        ) : (
          <div className="process-note">
            <LoaderCircle size={17} className="spin" />
            {error
              ? `Connection issue: ${error}. Retrying automatically.`
              : 'Processing with the Redis worker. You can leave this page.'}
          </div>
        )}
      </div>
    </div>
  );
}
