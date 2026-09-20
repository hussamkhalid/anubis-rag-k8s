# Anubis RAG on Kubernetes

End-to-end Retrieval-Augmented Generation pipeline packaged for a k3s cluster,
with a role-gated management UI. Ported from the single-VM Anubis RAG service
(`.17`) into reproducible container images and a Helm chart.

## Architecture

```
                         ┌───────────────────────────── k3s cluster ─────────────────────────────┐
   browser ── Ingress ──▶│  rag-ui (nginx+React)  ──/api──▶  rag-api (FastAPI)                     │
   (Traefik)             │                                     │        │                          │
                         │                                     │        ├─▶ embedder (GPU, bge-base)│
                         │                                     │        ├─▶ qdrant (StatefulSet+PVC)│
                         │                                     │        └─▶ ingest Job (per upload) │
                         │                                     ▼                                    │
                         └─────────────────────────────── llm-external ─┼────────────────────────┘
                                                                         ▼
                                                        answer-LLM on 192.168.70.14/.15 (llama.cpp)
```

- **rag-ui** — React SPA. `Ask` tab for everyone (question → grounded answer + cited
  sources). `Admin` tab (role-gated) for pipeline health, retrieval settings, and ingestion.
- **rag-api** — FastAPI. Same `/query` and `/ask` contract as the VM version
  (`X-ANUBIS-TOKEN` machine auth preserved). Adds JWT login (`user`/`admin`), `/ingest/upload`
  (spawns a K8s Job), `/ingest/jobs`, and a dependency-aware `/status`.
- **embedder** — one GPU-backed `bge-base-en-v1.5` service. Both query and ingest call it, so
  index-time and query-time vectors always come from the identical model (768-dim).
- **qdrant** — vector DB, `v1.16.3` (matches the existing on-disk format), PVC-backed.
- **ingest** — a K8s Job per upload: parse (PDF/DOCX/XLSX/TXT) → chunk (1400/200) →
  embed → upsert, with SHA-256 file dedup and UUIDv5 idempotent ids.
- **llm-external** — a selectorless Service→Endpoints pointing at the external llama.cpp host.

## Repo layout

```
services/
  rag-api/    FastAPI app (query/ask/ingest/auth/status) — CPU
  embedder/   bge-base HTTP embedder — GPU
  ingest/     ingestion Job image — CPU (embeds via the service)
  ui/         React + Vite SPA, served by nginx
deploy/helm/anubis-rag/   Helm chart (see deploy/README.md)
.github/workflows/        build + push images to GHCR
```

## Quick start

Prereqs and full install/verify steps: **[deploy/README.md](deploy/README.md)**.

```bash
# 1. build + push the four images (or let CI do it) — see deploy/README.md
# 2. set real secrets in a values override, then:
helm upgrade --install anubis-rag deploy/helm/anubis-rag \
  -n anubis-rag --create-namespace \
  -f my-values.yaml
```

## Provenance

Derived from the live Anubis RAG pipeline on VM `.17`: the FastAPI app, the
`bge-base-en-v1.5` embedder, the parallel ingestion engine (chunk policy 1400/200,
UUIDv5 dedup), and the `anubis_rag_chunks` Qdrant collection (768-dim, Cosine). The one
behavioural change is that embedding moved out of the API process into a shared GPU service,
which removes the ingest-vs-query model-drift risk.
