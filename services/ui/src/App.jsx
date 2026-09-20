import React, { useState } from 'react'
import { auth } from './api.js'
import Login from './components/Login.jsx'
import GuidedTab from './components/GuidedTab.jsx'
import AdminTab from './components/AdminTab.jsx'

export default function App() {
  const [role, setRole] = useState(auth.role())
  const [tab, setTab] = useState('ask')

  if (!role) return <Login onLogin={(r) => { setRole(r); setTab('ask') }} />

  const isAdmin = auth.isAdmin()
  return (
    <div className="app">
      <div className="brand">
        <h1>ANUBIS RAG</h1>
        <span className="tag">knowledge retrieval</span>
        <span className="grow" />
        <span className="muted">{role}</span>
        <button className="btn ghost" style={{ marginLeft: 10 }}
          onClick={() => { auth.clear(); setRole(null) }}>Sign out</button>
      </div>

      <div className="tabs">
        <button className={tab === 'ask' ? 'active' : ''} onClick={() => setTab('ask')}>Ask</button>
        {isAdmin && <button className={tab === 'admin' ? 'active' : ''} onClick={() => setTab('admin')}>Admin</button>}
      </div>

      {tab === 'ask' && <GuidedTab isAdmin={isAdmin} />}
      {tab === 'admin' && isAdmin && <AdminTab />}
    </div>
  )
}
