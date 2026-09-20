import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

// Ops surface: live pipeline health (embedder / Qdrant / external LLM),
// retrieval settings, and ingestion job history.
export default function AdminTab() {
  const [st, setSt] = useState(null)
  const [jobs, setJobs] = useState([])
  const [err, setErr] = useState('')

  async function refresh() {
    setErr('')
    try {
      const [s, j] = await Promise.all([api.status(), api.jobs().catch(() => ({ jobs: [] }))])
      setSt(s); setJobs(j.jobs || [])
    } catch (e) { setErr(e.message) }
  }

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 5000)
    return () => clearInterval(t)
  }, [])

  const dot = (ok) => <span className={`dot ${ok ? 'good' : 'bad'}`} />

  return (
    <>
      <div className="card">
        <h2>Pipeline health</h2>
        {!st ? <div className="muted">Loading…</div> : (
          <div className="kv">
            <div className="k">Embedder</div>
            <div>{dot(st.embedder?.reachable)}{st.embedder?.reachable
              ? `${st.embedder.model} · dim ${st.embedder.dim} · ${st.embedder.device}` : 'unreachable'}</div>
            <div className="k">Vector DB (Qdrant)</div>
            <div>{dot(st.qdrant?.reachable)}{st.qdrant?.reachable
              ? `${st.collection} · ${st.qdrant.points} vectors · dim ${st.qdrant.dim} · ${st.qdrant.status}` : 'unreachable'}</div>
            <div className="k">Answer LLM (external)</div>
            <div>{dot(st.llm_reachable)}{st.llm_reachable ? st.llm_endpoint : `${st.llm_endpoint} — unreachable`}</div>
            <div className="k">Dimension match</div>
            <div>{dot(st.embedder?.dim && st.qdrant?.dim && st.embedder.dim === st.qdrant.dim)}
              {st.embedder?.dim === st.qdrant?.dim ? `consistent (${st.qdrant?.dim})` : 'MISMATCH — re-ingest needed'}</div>
          </div>
        )}
        {err && <div className="err">{err}</div>}
      </div>

      {st && (
        <div className="card">
          <h2>Retrieval settings</h2>
          <div className="kv">
            <div className="k">top_k (default)</div><div>{st.retrieval?.top_k}</div>
            <div className="k">context_top_k</div><div>{st.retrieval?.context_top_k}</div>
            <div className="k">min_score</div><div>{st.retrieval?.min_score}</div>
            <div className="k">LLM format</div><div>{st.llm_api_format}</div>
          </div>
          <p className="muted" style={{ marginTop: 10 }}>
            These come from the RAG API ConfigMap. Change them in the Helm values
            (<code>ragApi.env</code>) and <code>helm upgrade</code> to apply.
          </p>
        </div>
      )}

      <div className="card">
        <h2>Ingestion jobs</h2>
        {jobs.length === 0 ? <div className="muted">No jobs yet. Upload a document from the Ask tab.</div> : (
          <table className="jobs">
            <thead><tr><th>Job</th><th>Status</th><th>Created</th></tr></thead>
            <tbody>
              {jobs.map(j => (
                <tr key={j.name}>
                  <td>{j.name}</td>
                  <td>{statusDot(j.status)}{j.status}</td>
                  <td className="muted">{j.created ? new Date(j.created).toLocaleString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  )
}

function statusDot(status) {
  const cls = status === 'Succeeded' ? 'good' : status === 'Failed' ? 'bad' : 'warn'
  return <span className={`dot ${cls}`} />
}
