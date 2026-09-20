import React, { useState } from 'react'
import { api } from '../api.js'

// The end-user "learning" surface: ask a question, get a grounded answer with
// the exact source chunks it used. Admins additionally see an upload box.
export default function GuidedTab({ isAdmin }) {
  const [q, setQ] = useState('')
  const [ans, setAns] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  async function ask() {
    if (!q.trim()) return
    setBusy(true); setErr(''); setAns(null)
    try {
      setAns(await api.ask(q.trim()))
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="card">
        <h2>Ask a question</h2>
        <textarea value={q} onChange={e => setQ(e.target.value)}
          placeholder="e.g. What does the partner service offering include?"
          onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) ask() }} />
        <div className="row" style={{ marginTop: 10 }}>
          <button className="btn" onClick={ask} disabled={busy}>{busy ? 'Thinking…' : 'Ask'}</button>
          <span className="muted">⌘/Ctrl + Enter</span>
        </div>
        {err && <div className="err">{err}</div>}
      </div>

      {ans && (
        <div className="card">
          <h2>Answer</h2>
          <div className="answer">{ans.answer}</div>
          {ans.citations?.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div className="muted" style={{ marginBottom: 6 }}>
                Grounded in {ans.used_chunks} source{ans.used_chunks !== 1 ? 's' : ''}:
              </div>
              {ans.citations.map((c, i) => (
                <span className="cite" key={i}
                  title={c.source_file || ''}>{c.chunk_id} · {c.score?.toFixed(3)}</span>
              ))}
            </div>
          )}
        </div>
      )}

      {isAdmin && <UploadBox />}
    </>
  )
}

function UploadBox() {
  const [over, setOver] = useState(false)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')

  async function send(file) {
    setErr(''); setMsg(`Uploading ${file.name}…`)
    try {
      const r = await api.upload(file, file.name)
      setMsg(`Ingestion started: job ${r.job}. Track it in the Admin tab.`)
    } catch (e) {
      setErr(e.message); setMsg('')
    }
  }

  return (
    <div className="card">
      <h2>Add a document</h2>
      <div className={`drop ${over ? 'over' : ''}`}
        onDragOver={e => { e.preventDefault(); setOver(true) }}
        onDragLeave={() => setOver(false)}
        onDrop={e => { e.preventDefault(); setOver(false); if (e.dataTransfer.files[0]) send(e.dataTransfer.files[0]) }}>
        Drop a PDF / DOCX / XLSX / TXT here, or
        <label style={{ color: 'var(--accent)', cursor: 'pointer' }}>
          &nbsp;browse
          <input type="file" style={{ display: 'none' }} accept=".pdf,.docx,.xlsx,.txt"
            onChange={e => e.target.files[0] && send(e.target.files[0])} />
        </label>
      </div>
      {msg && <div className="muted" style={{ marginTop: 10 }}>{msg}</div>}
      {err && <div className="err">{err}</div>}
    </div>
  )
}
