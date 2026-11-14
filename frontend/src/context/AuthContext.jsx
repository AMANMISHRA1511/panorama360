import { createContext, useContext, useState } from 'react';
import api from '../lib/api';
const Context = createContext(null);
export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('p360_token'));
  const [user, setUser] = useState(() => { try { return JSON.parse(localStorage.getItem('p360_user')); } catch { return null; } });
  const authenticate = async (mode, email, password) => {
    const { data } = await api.post(`/auth/${mode}`, { email, password });
    localStorage.setItem('p360_token', data.access_token);
    localStorage.setItem('p360_user', JSON.stringify(data.user));
    setToken(data.access_token); setUser(data.user);
  };
  const logout = () => {
    localStorage.removeItem('p360_token'); localStorage.removeItem('p360_user');
    setToken(null); setUser(null);
  };
  return <Context.Provider value={{ token, user, authenticate, logout }}>{children}</Context.Provider>;
}
export const useAuth = () => useContext(Context);
