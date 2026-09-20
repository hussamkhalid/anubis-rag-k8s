"""Anubis RAG - Embedder service.

Wraps a SentenceTransformer model on GPU behind a small HTTP API. The RAG API
(query time) and the ingestion Job (index time) both call this ONE service, so
the query vector and the stored vectors are always produced by the same model.
That removes the ingest-vs-query dimension/model drift that a per-process
embedder invites.
"""
import os

from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List

MODEL_NAME = os.environ.get("EMBED_MODEL", "BAAI/bge-base-en-v1.5")
NORMALIZE = os.environ.get("EMBED_NORMALIZE", "true").lower() == "true"
BATCH_SIZE = int(os.environ.get("EMBED_BATCH", "64"))

app = FastAPI(title="anubis-embedder")

# Loaded once at startup. torch picks CUDA when the pod lands on a GPU node.
import torch
from sentence_transformers import SentenceTransformer

_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
_model = SentenceTransformer(MODEL_NAME, device=_DEVICE)
_DIM = _model.get_sentence_embedding_dimension()


class EmbedRequest(BaseModel):
    texts: List[str] = Field(..., min_length=1)
    # index-time ingest normalizes; keep the default aligned with query time
    normalize: bool = NORMALIZE
    batch_size: int = Field(BATCH_SIZE, ge=1, le=512)


class EmbedResponse(BaseModel):
    model: str
    dim: int
    count: int
    vectors: List[List[float]]


@app.get("/health")
def health():
    return {
        "ok": True,
        "model": MODEL_NAME,
        "dim": _DIM,
        "device": _DEVICE,
        "cuda": torch.cuda.is_available(),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    }


@app.post("/embed", response_model=EmbedResponse)
def embed(req: EmbedRequest):
    vectors = _model.encode(
        req.texts,
        batch_size=req.batch_size,
        normalize_embeddings=req.normalize,
        show_progress_bar=False,
    )
    return EmbedResponse(
        model=MODEL_NAME,
        dim=_DIM,
        count=len(req.texts),
        vectors=vectors.tolist() if hasattr(vectors, "tolist") else [v.tolist() for v in vectors],
    )
