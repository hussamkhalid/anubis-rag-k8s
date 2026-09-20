"""Pydantic schemas. Query/Ask carried over verbatim from the .17 contract so
existing API clients keep working; ingest + auth schemas added for the UI."""
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: Optional[int] = Field(None, ge=1, le=50)
    model_config = ConfigDict(extra="forbid")


class QueryResult(BaseModel):
    id: str
    chunk_id: Optional[str] = None
    score: float
    text: Optional[str] = None
    source_file: Optional[str] = None
    model_config = ConfigDict(extra="ignore")


class QueryResponse(BaseModel):
    query: str
    top_k: int
    results: List[QueryResult]
    timestamp: str


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: Optional[int] = Field(None, ge=1, le=50)
    model_config = ConfigDict(extra="forbid")


class AskCitation(BaseModel):
    chunk_id: Optional[str] = None
    score: float
    source_file: Optional[str] = None


class AskResponse(BaseModel):
    query: str
    answer: str
    citations: List[AskCitation]
    used_chunks: int


# ── Auth ──
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=256)
    model_config = ConfigDict(extra="forbid")


class LoginResponse(BaseModel):
    token: str
    role: str
    expires_in: int


# ── Ingestion ──
class IngestJobInfo(BaseModel):
    name: str
    status: str          # Pending | Running | Succeeded | Failed | Unknown
    created: Optional[str] = None
    source: Optional[str] = None
