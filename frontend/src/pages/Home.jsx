import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowRight, ArrowUpRight, Aperture, Camera, Check, CirclePlay, Compass, ImagePlus, Layers3, MoveUpRight, ScanLine, Sparkles, WandSparkles, Zap } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
const features = [
  { icon: ImagePlus, title: 'One image. Endless perspective.', text: 'Convert wide-angle scenes to interactive spherical views with geometric precision.', color:'blue' },
  { icon: Layers3, title: 'Smart photo stitching', text: 'Match overlapping frames, align perspectives, and blend a wider world.', color:'violet' },
  { icon: WandSparkles, title: 'Enhance the details', text: 'Refine clarity and smoothly fill unmapped regions. Trained AI weights are optional.', color:'cyan' },
];
export default function Home() {
 const { token } = useAuth();
 return <><section className="hero site-container"><div className="hero-grid">
  <motion.div className="hero-left" initial={{opacity:0,y:25}} animate={{opacity:1,y:0}} transition={{duration:.6}}>
    <div className="hero-pill"><span className="pill-stars"><Sparkles size={14}/></span> YOUR WORLD, WITHOUT LIMITS <span className="pill-line"/></div>
    <h1>Go beyond<br/>the <span className="gradient-text">frame.</span></h1>
    <p>Turn your photos and videos into breathtaking 360° experiences. Create, explore, and share worlds worth getting lost in.</p>
    <div className="hero-cta"><Link className="btn btn-primary btn-large" to={token ? '/upload' : '/login'}>Start creating <ArrowUpRight size={18}/></Link><Link className="btn btn-glass btn-large" to="/capture"><Camera size={17}/> Live capture</Link></div>
    <div className="hero-caption"><div className="avatar-stack"><i>✦</i><i>◎</i><i>◈</i></div><div><strong>Built for immersive creators</strong><span>360° photos · video · panorama stitching</span></div></div>
  </motion.div>
  <motion.div className="hero-right" initial={{opacity:0,scale:.9}} animate={{opacity:1,scale:1}} transition={{duration:.8,delay:.15}}>
    <div className="planet-halo halo-one"/><div className="planet-halo halo-two"/><div className="planet-grid"/>
    <div className="planet-visual"><div className="planet-glow"/><div className="planet-sphere"><div className="sphere-land sphere-land-a"/><div className="sphere-land sphere-land-b"/><div className="sphere-highlight"/></div></div>
    <div className="floating-glass float-left"><span><ScanLine size={17}/></span><div><b>Seamless stitching</b><small>Frame by frame</small></div><Check size={15}/></div>
    <div className="floating-glass float-right"><span><Compass size={18}/></span><div><b>360° viewer</b><small>Look anywhere</small></div><ArrowUpRight size={16}/></div>
    <div className="hero-visual-label"><span className="orbit-dot"/> THE WORLD IS YOUR CANVAS <span>360°</span></div>
  </motion.div>
 </div><div className="hero-bottom"><span>CREATE BEYOND BOUNDARIES</span><div/><span>SCROLL TO DISCOVER ↓</span></div></section>
 <section className="feature-section"><div className="site-container"><div className="section-top"><div><div className="eyebrow"><span className="eyebrow-pip"/> ONE STUDIO. INFINITE POSSIBILITIES.</div><h2>Everything you need to<br/><span className="muted-heading">see the bigger picture.</span></h2></div><Link to="/upload" className="text-link">Explore the studio <ArrowUpRight size={17}/></Link></div>
 <div className="feature-grid">{features.map(({icon:Icon,title,text,color},i)=><motion.div key={title} className="feature-card" initial={{opacity:0,y:15}} whileInView={{opacity:1,y:0}} viewport={{once:true}} transition={{delay:i*.1}}><div className={`feature-icon feature-${color}`}><Icon size={23}/></div><span className="feature-index">0{i+1} / 03</span><h3>{title}</h3><p>{text}</p><ArrowRight size={19} className="feature-arrow"/></motion.div>)}</div>
 <div className="bottom-cta"><div><div className="eyebrow"><span className="eyebrow-pip"/> READY WHEN YOU ARE</div><h2>Have a moment worth <em>expanding?</em></h2><p>From your first photo to your next big adventure.</p></div><Link to="/upload" className="btn btn-primary btn-large">Create your first panorama <ArrowRight size={18}/></Link></div></div></section></>;
}
