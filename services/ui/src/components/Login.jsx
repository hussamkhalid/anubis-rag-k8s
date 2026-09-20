import React, { useState } from 'react'
import { api, auth } from '../api.js'

export default function Login({ onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setBusy(true); setErr('')
    try {
      const r = await api.login(username, password)
      auth.set(r.token, r.role)
      onLogin(r.role)
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="app">
      <form className="login card" onSubmit={submit}>
        <div className="brand"><h1>ANUBIS RAG</h1></div>
        <p className="muted">Sign in to ask questions or manage the knowledge base.</p>
        <label className="muted">Username</label>
        <input type="text" value={username} onChange={e => setUsername(e.target.value)}
          placeholder="user or admin" autoFocus />
        <label className="muted" style={{ marginTop: 10, display: 'block' }}>Password</label>
        <input type="password" value={password} onChange={e => setPassword(e.target.value)} />
        <button className="btn" style={{ marginTop: 14, width: '100%' }} disabled={busy}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
        {err && <div className="err">{err}</div>}
      </form>
    </div>
  )
}
