import { useEffect, useState } from 'react';
import api, { apiError } from '../lib/api';
/** Authorization-safe blob loading for private assets. Public share assets use direct URLs. */
export function useAsset(path, isPublic = false) {
  const [state, setState] = useState({ url: null, loading: !!path, error: null });
  useEffect(() => {
    if (!path) { setState({ url: null, loading: false, error: null }); return; }
    if (isPublic) { setState({ url: path, loading: false, error: null }); return; }
    let alive = true, objectUrl = null;
    setState({ url: null, loading: true, error: null });
    api.get(path, { responseType: 'blob' }).then(({ data }) => {
      if (!alive) return;
      objectUrl = URL.createObjectURL(data);
      setState({ url: objectUrl, loading: false, error: null });
    }).catch(error => { if (alive) setState({ url: null, loading: false, error: apiError(error) }); });
    return () => { alive = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [path, isPublic]);
  return state;
}
