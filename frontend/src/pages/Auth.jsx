import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowRight, Eye, EyeOff, KeyRound, LockKeyhole, Mail, Sparkles } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useUI } from '../context/UIContext';
import { apiError } from '../lib/api';
export default function Auth() {
 const [signup, setSignup] = useState(false), [email, setEmail] = useState(''), [password, setPassword] = useState(''), [show, setShow] = useState(false), [busy, setBusy] = useState(false);
 const { authenticate } = useAuth(), { toast } = useUI(), nav = useNavigate(), loc = useLocation();
 const onSubmit = async e => {e.preventDefault();setBusy(true);try{await authenticate(signup?'signup':'login',email,password);toast(signup?'Account created!':'Welcome back!','success');nav(loc.state?.from || '/gallery',{replace:true});}catch(err){toast(apiError(err),'error');}finally{setBusy(false);}};
 return <div className="auth-page site-container"><motion.div className="auth-panel" initial={{opacity:0,y:20}} animate={{opacity:1,y:0}}>
   <div className="auth-illustration"><div className="auth-halo"><div className="auth-orb"><Sparkles size={49}/></div></div><div className="eyebrow">YOUR CREATIVE JOURNEY</div><h2>See more.<br/>Create <span className="gradient-text">more.</span></h2><p>Every unforgettable view starts with a single frame.</p></div>
   <div className="auth-form-side"><div className="eyebrow"><span className="eyebrow-pip"/> WELCOME TO PANORAMA STUDIO</div><h1>{signup?'Create your account':'Welcome back'}</h1><p className="form-intro">{signup?'Your next adventure starts here.':'Log in to keep exploring your world.'}</p>
   <form onSubmit={onSubmit} className="stack-form"><label>Email address<div className="input-wrap"><Mail size={18}/><input type="email" required value={email} onChange={e=>setEmail(e.target.value)} autoComplete="email" placeholder="you@example.com"/></div></label>
   <label>Password<div className="input-wrap"><LockKeyhole size={18}/><input type={show?'text':'password'} required minLength={8} maxLength={72} value={password} onChange={e=>setPassword(e.target.value)} autoComplete={signup?'new-password':'current-password'} placeholder="Minimum 8 characters"/><button type="button" onClick={()=>setShow(!show)} aria-label="Show or hide password">{show?<EyeOff size={17}/>:<Eye size={17}/>}</button></div></label>
   <button type="submit" className="btn btn-primary btn-large full" disabled={busy}>{busy?'Please wait...':(signup?'Create account':'Sign in')}<ArrowRight size={18}/></button></form>
   <p className="auth-switch">{signup?'Already have an account?':'New to Panorama Studio?'} <button onClick={()=>setSignup(!signup)}>{signup?'Sign in':'Create an account'}</button></p>
   <p className="auth-note"><KeyRound size={14}/> Your projects stay private unless you share their link.</p></div>
  </motion.div></div>;
}
