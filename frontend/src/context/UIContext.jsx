import { createContext, useContext, useEffect, useState } from 'react';
const Context = createContext(null);
export function UIProvider({ children }) {
  const [theme, setTheme] = useState(() => localStorage.getItem('p360_theme') || 'dark');
  const [toasts, setToasts] = useState([]);
  useEffect(() => { document.documentElement.dataset.theme = theme; localStorage.setItem('p360_theme', theme); }, [theme]);
  function toast(message, kind = 'info') {
    const id = `${Date.now()}-${Math.random()}`;
    setToasts(old => [...old, { id, message, kind }]);
    setTimeout(() => setToasts(old => old.filter(x => x.id !== id)), 4200);
  }
  return <Context.Provider value={{ theme, setTheme, toast }}>
    {children}
    <div className="toast-stack" aria-live="polite">{toasts.map(t => <div className={`toast toast-${t.kind}`} key={t.id}>{t.message}</div>)}</div>
  </Context.Provider>;
}
export const useUI = () => useContext(Context);
