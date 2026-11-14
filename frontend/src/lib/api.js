import axios from 'axios';
export const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const api = axios.create({ baseURL: API_BASE, timeout: 60000 });
api.interceptors.request.use(config => {
  const token = localStorage.getItem('p360_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
export function apiError(err) {
  if (err?.response?.data?.detail) {
    const detail = err.response.data.detail;
    if (Array.isArray(detail)) return detail.map(x => x.msg).join(', ');
    return String(detail);
  }
  if (err?.code === 'ERR_NETWORK') return 'Cannot reach the API. Start FastAPI on port 8000.';
  return err?.message || 'Something went wrong. Please retry.';
}
export function wsUrl(jobId) {
  const root = API_BASE.replace(/^http/i, 'ws');
  return `${root}/ws/progress/${encodeURIComponent(jobId)}?token=${encodeURIComponent(localStorage.getItem('p360_token') || '')}`;
}
export default api;
