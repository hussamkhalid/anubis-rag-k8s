// Thin API client. All calls are same-origin /api/* (nginx proxies to the RAG
// API in-cluster). The JWT from login is attached as a Bearer token.

const TOKEN_KEY = 'anubis_rag_token'
const ROLE_KEY = 'anubis_rag_role'

export const auth = {
  token: () => localStorage.getItem(TOKEN_KEY),
  role: () => localStorage.getItem(ROLE_KEY),
  set: (token, role) => { localStorage.setItem(TOKEN_KEY, token); localStorage.setItem(ROLE_KEY, role) },
  clear: () => { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(ROLE_KEY) },
  isAdmin: () => localStorage.getItem(ROLE_KEY) === 'admin',
}

function headers(extra = {}) {
  const h = { ...extra }
  const t = auth.token()
  if (t) h['Authorization'] = `Bearer ${t}`
  return h
}

async function jr(res) {
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try { const j = await res.json(); msg = j.detail || j.error || msg } catch { /* noop */ }
    throw new Error(msg)
  }
  return res.json()
}

export const api = {
  login: (username, password) =>
    fetch('/api/auth/login', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    }).then(jr),

  ask: (query, top_k) =>
    fetch('/api/ask', {
      method: 'POST', headers: headers({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ query, top_k }),
    }).then(jr),

  query: (query, top_k) =>
    fetch('/api/query', {
      method: 'POST', headers: headers({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ query, top_k }),
    }).then(jr),

  status: () => fetch('/api/status', { headers: headers() }).then(jr),

  jobs: () => fetch('/api/ingest/jobs', { headers: headers() }).then(jr),

  upload: (file, label) => {
    const fd = new FormData()
    fd.append('file', file)
    if (label) fd.append('label', label)
    return fetch('/api/ingest/upload', { method: 'POST', headers: headers(), body: fd }).then(jr)
  },
}
