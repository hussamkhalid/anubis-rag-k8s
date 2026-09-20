"""Runtime config, fully env-driven for Kubernetes (ConfigMap + Secret).

Ported from the .17 VM config.py. The only behavioural change: embedding is no
longer loaded in-process — it is fetched from EMBED_URL (the shared GPU embedder
service) so query and ingest use the identical model.
"""
import os


def _int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _float(name, default):
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# ── Vector store ──
QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333")
COLLECTION_NAME = os.environ.get("COLLECTION_NAME", "anubis_rag_chunks")

# ── Embedding (external GPU service; see services/embedder) ──
EMBED_URL = os.environ.get("EMBED_URL", "http://embedder:8080")
# advertised for /status only — the real model lives in the embedder pod
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")

# ── Retrieval ──
TOP_K = _int("TOP_K", 4)
CONTEXT_TOP_K = _int("CONTEXT_TOP_K", 25)
MIN_SCORE = _float("MIN_SCORE", 0.55)

# ── Answer LLM (external — .14/.15 via an ExternalName Service) ──
LLM_COMPLETION_URL = os.environ.get(
    "LLM_COMPLETION_URL", "http://llm-external:8080/v1/chat/completions"
)
LLM_API_FORMAT = os.environ.get("LLM_API_FORMAT", "openai")  # "openai" | "llamacpp"
LLM_TEMPERATURE = _float("LLM_TEMPERATURE", 0.2)
LLM_MAX_TOKENS = _int("LLM_MAX_TOKENS", 256)

# ── Ingestion Job orchestration (K8s) ──
INGEST_IMAGE = os.environ.get("INGEST_IMAGE", "ghcr.io/hussamkhalid/anubis-rag-ingest:latest")
INGEST_NAMESPACE = os.environ.get("INGEST_NAMESPACE", "anubis-rag")
INGEST_UPLOADS_PVC = os.environ.get("INGEST_UPLOADS_PVC", "anubis-rag-uploads")
INGEST_GPU_NODE_SELECTOR = os.environ.get("INGEST_GPU_NODE_SELECTOR", "")  # "key=value" or empty
INGEST_SERVICE_ACCOUNT = os.environ.get("INGEST_SERVICE_ACCOUNT", "anubis-rag-ingest")
UPLOADS_DIR = os.environ.get("UPLOADS_DIR", "/uploads")

# ── Auth ──
# Machine-to-machine token (unchanged contract: header X-ANUBIS-TOKEN).
ANUBIS_API_TOKEN = os.environ.get("ANUBIS_API_TOKEN", "")
# UI login -> JWT with a role claim. Two roles: "user" (guided) and "admin".
JWT_SECRET = os.environ.get("JWT_SECRET", "")
JWT_TTL_HOURS = _int("JWT_TTL_HOURS", 12)
UI_USER_PASSWORD = os.environ.get("UI_USER_PASSWORD", "")
UI_ADMIN_PASSWORD = os.environ.get("UI_ADMIN_PASSWORD", "")
