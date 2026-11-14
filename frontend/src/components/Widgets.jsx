import { motion } from 'framer-motion';
import { AlertCircle, ArrowLeft, ArrowRight, CheckCircle2, LoaderCircle } from 'lucide-react';
import { Link } from 'react-router-dom';
export function PageHead({ eyebrow, title, subtitle }) {
  return <motion.div className="page-heading" initial={{opacity:0,y:15}} animate={{opacity:1,y:0}} transition={{duration:.4}}>
    <div className="eyebrow"><span className="eyebrow-pip"/>{eyebrow}</div>
    <h1>{title}</h1><p>{subtitle}</p>
  </motion.div>;
}
export function Loading({ text = 'Loading your panorama...' }) { return <div className="center-state"><LoaderCircle className="spin" size={28}/><p>{text}</p></div>; }
export function ErrorState({ error, onRetry }) { return <div className="center-state"><AlertCircle size={28}/><h3>Something went wrong</h3><p>{error}</p>{onRetry && <button className="btn btn-secondary" onClick={onRetry}>Try again <ArrowRight size={16}/></button>}</div>; }
export function BackLink({ to = '/gallery', children = 'Back to gallery' }) { return <Link to={to} className="back-link"><ArrowLeft size={15}/>{children}</Link>; }
export function Tag({ children }) {return <span className="mini-tag"><CheckCircle2 size={13}/>{children}</span>}
export function Skeletons({ count = 6 }) {return <div className="gallery-grid">{Array.from({length:count},(_,i)=><div className="gallery-skeleton" key={i}><div/><span/><span/></div>)}</div>}
