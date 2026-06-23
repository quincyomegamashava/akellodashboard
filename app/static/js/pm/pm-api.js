/** Project management API helpers (shared). */
window.PM_API_BASE = '/api';

window.pmApiGET = async function(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`GET ${path} failed (${res.status})`);
  return res.json();
};

window.pmApiPOST = async function(path, payload) {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || `POST ${path} failed (${res.status})`);
  }
  return res.json();
};

window.pmApiPATCH = async function(path, payload) {
  const res = await fetch(path, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || `PATCH ${path} failed (${res.status})`);
  }
  return res.json();
};

window.pmApiDELETE = async function(path, payload) {
  const opts = { method: 'DELETE' };
  if (payload) {
    opts.headers = { 'Content-Type': 'application/json' };
    opts.body = JSON.stringify(payload);
  }
  const res = await fetch(path, opts);
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || `DELETE ${path} failed (${res.status})`);
  }
  return res.json().catch(() => ({}));
};

window.pmDebounce = function(fn, ms) {
  let t;
  return function(...args) {
    clearTimeout(t);
    t = setTimeout(() => fn.apply(this, args), ms);
  };
};
