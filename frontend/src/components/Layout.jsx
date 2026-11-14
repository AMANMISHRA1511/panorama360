import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { Aperture, ArrowUpRight, Camera, ChevronDown, Compass, FolderOpen, LogOut, Menu, Moon, Plus, Sun, X } from 'lucide-react';
import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useUI } from '../context/UIContext';
export function Logo() {
  return <Link to="/" className="logo"><span className="logo-symbol"><Aperture size={21} strokeWidth={2.5}/></span><span>panorama<span className="logo-highlight">studio</span><span className="logo-dot">.</span></span></Link>;
}
const links = [['/upload', 'Create', Plus], ['/capture', 'Live capture', Camera], ['/gallery', 'My gallery', FolderOpen]];
export default function Layout() {
  const { token, user, logout } = useAuth();
  const { theme, setTheme } = useUI();
  const [mobile, setMobile] = useState(false);
  const navigate = useNavigate();
  return <div className="site-shell"><div className="ambient-top"/>
    <header className="topbar"><div className="site-container nav-content"><Logo/>
      <nav className={`nav-links ${mobile ? 'nav-open' : ''}`}>
        {links.map(([path, text, Icon]) => <NavLink key={path} onClick={() => setMobile(false)} to={path} className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}><Icon size={16}/>{text}</NavLink>)}
      </nav>
      <div className="nav-actions"><button className="icon-button" title="Toggle light/dark theme" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} aria-label="Toggle theme">{theme === 'dark' ? <Sun size={18}/> : <Moon size={18}/>}</button>
        {token ? <div className="account-group"><span className="account-avatar">{user?.email?.slice(0,1).toUpperCase() || 'U'}</span><button title="Log out" onClick={() => {logout();navigate('/');}} className="icon-button"><LogOut size={17}/></button></div>
          : <Link to="/login" className="btn btn-primary btn-small">Get started <ArrowUpRight size={15}/></Link>}
        <button aria-label="Toggle menu" className="icon-button mobile-menu" onClick={() => setMobile(!mobile)}>{mobile ? <X/> : <Menu/>}</button>
      </div></div></header>
    <main><Outlet/></main>
    <footer className="footer site-container"><span><Aperture size={15}/> Panorama Studio <span className="footer-faded">© 2026</span></span><span>Made for a wider world <Compass size={15}/></span></footer>
  </div>;
}
