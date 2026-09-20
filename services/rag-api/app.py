"""Anubis RAG API (Kubernetes edition).

Ported from the .17 VM app.py. Behaviour preserved: /query and /ask keep the same
request/response contract and the same X-ANUBIS-TOKEN machine auth. Changes for
cloud-native operation:
  * embedding is fetched from the external embedder service (EMBED_URL/embed),
    not loaded in-process -> query and ingest share ONE model.
  * config is env-driven (ConfigMap/Secret).
  * added /auth/login (JWT roles), /ingest/upload + /ingest/jobs (UI-driven
    ingestion via K8s Jobs), and richer /health for dependency status.
"""
import os
import time
import shutil
import socket
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse

from models import (
    QueryRequest, QueryResponse, AskRequest, AskResponse, AskCitation,
    LoginRequest, LoginResponse,
)
import config
import auth

from qdrant_client import QdrantClient

app = FastAPI(title="anubis-rag-api")
qdrant = QdrantClient(url=config.QDRANT_URL)
START_TIME = time.time()


# =========================================================
# Embedding via the shared GPU service
# =========================================================
def embed_one(text: str) -> list:
    r = requests.post(f"{config.EMBED_URL}/embed", json={"texts": [text]}, timeout=30)
    r.raise_for_status()
    return r.json()["vectors"][0]


# =========================================================
# Retrieval (Qdrant query_points — same as .17)
# =========================================================
def run_retrieval(query: str, top_k: int = None):
    vector = embed_one(query)
    limit = top_k if top_k is not None else config.TOP_K
    response = qdrant.query_points(
        collection_name=config.COLLECTION_NAME,
        query=vector,
        limit=limit,
        with_payload=True,
    )
    results = []
    for p in response.points:
        results.append({
            "id": str(p.id),
            "chunk_id": p.payload.get("chunk_id"),
            "score": p.score,
            "text": p.payload.get("text"),
            "source_file": p.payload.get("source_file"),
        })
    return results


# =========================================================
# LLM call (external; OpenAI or llama.cpp format) — from .17
# =========================================================
_LLM_CONTEXT_LIMIT = None
CHARS_PER_TOKEN = 3.0


def _get_context_limit() -> int:
    global _LLM_CONTEXT_LIMIT
    if _LLM_CONTEXT_LIMIT is not None:
        return _LLM_CONTEXT_LIMIT
    base = config.LLM_COMPLETION_URL
    base = base.rsplit("/v1/", 1)[0] if "/v1/" in base else base.rsplit("/completion", 1)[0]
    try:
        r = requests.get(f"{base}/props", timeout=5)
        if r.status_code == 200:
            n_ctx = r.json().get("default_generation_settings", {}).get("n_ctx")
            if n_ctx and n_ctx > 0:
                _LLM_CONTEXT_LIMIT = n_ctx
                return n_ctx
    except Exception:
        pass
    _LLM_CONTEXT_LIMIT = 2048
    return _LLM_CONTEXT_LIMIT


def _truncate_prompt(prompt: str, max_response_tokens: int) -> str:
    ctx_limit = _get_context_limit()
    max_prompt_tokens = ctx_limit - max_response_tokens - 150
    max_prompt_chars = int(max_prompt_tokens * CHARS_PER_TOKEN)
    if len(prompt) > max_prompt_chars:
        q_marker = "\nQUESTION:\n"
        q_idx = prompt.rfind(q_marker)
        if q_idx > 0:
            question_part = prompt[q_idx:]
            remaining = max_prompt_chars - len(question_part) - 60
            if remaining > 200:
                return prompt[:remaining] + "\n[...context truncated...]\n" + question_part
        return prompt[:max_prompt_chars] + "\n[...truncated to fit context window...]\n"
    return prompt


def call_llm(prompt: str) -> str:
    prompt = _truncate_prompt(prompt, config.LLM_MAX_TOKENS)
    if config.LLM_API_FORMAT == "llamacpp":
        payload = {
            "prompt": prompt,
            "n_predict": config.LLM_MAX_TOKENS,
            "temperature": config.LLM_TEMPERATURE,
            "stop": ["###", "\n\nQUESTION:", "\n\nCONTEXT:"],
        }
        r = requests.post(config.LLM_COMPLETION_URL, json=payload, timeout=180)
        r.raise_for_status()
        return (r.json().get("content") or "").strip()
    payload = {
        "messages": [
            {"role": "system", "content": "You are a grounded assistant. Answer concisely using the provided context. Cite chunk IDs when applicable."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": config.LLM_MAX_TOKENS,
        "temperature": config.LLM_TEMPERATURE,
        "stop": ["###", "\n\nQUESTION:", "\n\nCONTEXT:"],
    }
    r = requests.post(config.LLM_COMPLETION_URL, json=payload, timeout=180)
    r.raise_for_status()
    data = r.json()
    choices = data.get("choices", [])
    if choices:
        return (choices[0].get("message", {}).get("content") or "").strip()
    return (data.get("content") or "").strip()


# =========================================================
# Auth routes
# =========================================================
@app.post("/auth/login", response_model=LoginResponse)
def login(req: LoginRequest):
    role = auth.verify_login(req.username, req.password)
    token, ttl = auth.issue_token(role)
    return LoginResponse(token=token, role=role, expires_in=ttl)


# =========================================================
# Retrieval / RAG routes (contract identical to .17)
# =========================================================
@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest, request: Request):
    auth.require_user(request)
    effective_top_k = req.top_k if req.top_k is not None else config.TOP_K
    results = run_retrieval(req.query, top_k=effective_top_k)
    return QueryResponse(
        query=req.query,
        top_k=effective_top_k,
        results=results,
        timestamp=datetime.utcnow().isoformat() + "Z",
    )


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest, request: Request):
    auth.require_user(request)
    effective_top_k = req.top_k if req.top_k is not None else config.TOP_K
    results = run_retrieval(req.query, top_k=effective_top_k)

    context_blocks, citations = [], []
    for r in results[:effective_top_k]:
        context_blocks.append(f"[{r['chunk_id']}]\n{r['text']}")
        citations.append(AskCitation(chunk_id=r["chunk_id"], score=r["score"],
                                     source_file=r.get("source_file")))
    context_text = "\n\n".join(context_blocks)
    prompt = (
        "### System:\n"
        "You are a grounded assistant.\n"
        "Use the CONTEXT below if it is relevant.\n"
        "If context is insufficient, answer using reasoning.\n"
        "Cite chunk IDs when applicable.\n"
        "###\n\n"
        f"CONTEXT:\n{context_text}\n\n"
        f"QUESTION:\n{req.query}\n\n"
        "ANSWER:\n"
    )
    try:
        answer_text = call_llm(prompt)
    except Exception as e:
        answer_text = f"LLM Error: {str(e)}"
    return AskResponse(query=req.query, answer=answer_text,
                       citations=citations, used_chunks=len(citations))


# =========================================================
# Ingestion routes (UI-driven -> K8s Jobs)
# =========================================================
@app.post("/ingest/upload")
async def ingest_upload(request: Request, file: UploadFile = File(...), label: str = Form(None)):
    auth.require_admin(request)
    import k8s_jobs
    ts = time.strftime("%Y%m%d-%H%M%S")
    subdir = f"{ts}-{os.getpid()}"
    dest_dir = os.path.join(config.UPLOADS_DIR, subdir)
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, os.path.basename(file.filename))
    with open(dest, "wb") as fh:
        shutil.copyfileobj(file.file, fh)
    job = k8s_jobs.launch_ingest_job(subdir, label or file.filename)
    return JSONResponse({"job": job, "uploaded": file.filename, "subdir": subdir})


@app.get("/ingest/jobs")
def ingest_jobs(request: Request):
    auth.require_admin(request)
    import k8s_jobs
    return {"jobs": k8s_jobs.list_jobs()}


# =========================================================
# Health / status (dependency-aware, for the admin dashboard)
# =========================================================
def _tcp_ok(url: str, default_port: int = 80) -> bool:
    try:
        p = urlparse(url)
        s = socket.create_connection((p.hostname, p.port or default_port), timeout=2)
        s.close()
        return True
    except Exception:
        return False


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat() + "Z"}


@app.get("/status")
def status():
    # embedder
    embed = {"reachable": False, "model": None, "dim": None}
    try:
        r = requests.get(f"{config.EMBED_URL}/health", timeout=3)
        if r.status_code == 200:
            j = r.json()
            embed = {"reachable": True, "model": j.get("model"), "dim": j.get("dim"),
                     "device": j.get("device")}
    except Exception:
        pass
    # qdrant
    qd = {"reachable": False, "points": None, "dim": None}
    try:
        info = qdrant.get_collection(config.COLLECTION_NAME)
        vs = info.config.params.vectors
        qd = {"reachable": True, "points": info.points_count,
              "dim": getattr(vs, "size", None), "status": str(info.status)}
    except Exception:
        pass
    return {
        "service": "anubis-rag",
        "uptime_seconds": int(time.time() - START_TIME),
        "collection": config.COLLECTION_NAME,
        "embedding_model": config.EMBEDDING_MODEL,
        "embedder": embed,
        "vector_db": "qdrant",
        "qdrant": qd,
        "retrieval": {"top_k": config.TOP_K, "context_top_k": config.CONTEXT_TOP_K,
                      "min_score": config.MIN_SCORE},
        "llm_endpoint": config.LLM_COMPLETION_URL,
        "llm_api_format": config.LLM_API_FORMAT,
        "llm_reachable": _tcp_ok(config.LLM_COMPLETION_URL),
    }


@app.get("/storage")
def storage():
    def disk(path):
        try:
            d = shutil.disk_usage(path)
            return {"path": path, "total_gb": round(d.total / 1e9, 2),
                    "used_gb": round(d.used / 1e9, 2), "free_gb": round(d.free / 1e9, 2)}
        except Exception:
            return {"path": path, "error": "unavailable"}
    return {"uploads": disk(config.UPLOADS_DIR)}
