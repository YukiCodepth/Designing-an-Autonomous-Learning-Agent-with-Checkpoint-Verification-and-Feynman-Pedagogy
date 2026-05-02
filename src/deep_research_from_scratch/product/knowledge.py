"""Knowledge-base helpers for ingestion, embeddings, and retrieval."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from deep_research_from_scratch.product.config import settings
from deep_research_from_scratch.product.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentKind,
    KnowledgeDocumentStatus,
)


EMBEDDING_DIMENSION = 768


def ensure_product_dirs() -> None:
    """Create local directories used by uploads and exported artifacts."""
    Path(settings.artifacts_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.uploads_dir).mkdir(parents=True, exist_ok=True)


def chunk_text(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    """Split long text into overlapping chunks."""
    normalized = " ".join(text.split())
    if not normalized:
        return []

    chunks: list[str] = []
    start = 0
    text_length = len(normalized)
    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunks.append(normalized[start:end].strip())
        if end >= text_length:
            break
        start = max(end - overlap, start + 1)
    return [chunk for chunk in chunks if chunk]


def _deterministic_embedding(text: str) -> list[float]:
    """Fallback embedding that keeps local development usable without remote calls."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values: list[float] = []
    seed = digest
    while len(values) < EMBEDDING_DIMENSION:
        seed = hashlib.sha256(seed + digest).digest()
        values.extend(((byte / 255.0) * 2.0) - 1.0 for byte in seed)
    return values[:EMBEDDING_DIMENSION]


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed text with Google by default, with a deterministic fallback for local dev."""
    filtered = [text.strip() for text in texts if text.strip()]
    if not filtered:
        return []

    try:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        embeddings = GoogleGenerativeAIEmbeddings(model=settings.embedding_model)
        return embeddings.embed_documents(filtered)
    except Exception:
        return [_deterministic_embedding(text) for text in filtered]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Return cosine similarity for two embedding vectors."""
    numerator = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def guess_document_kind(filename: str) -> KnowledgeDocumentKind:
    """Infer a knowledge-document kind from a filename or URI."""
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return KnowledgeDocumentKind.pdf
    if suffix in {".md", ".markdown"}:
        return KnowledgeDocumentKind.markdown
    return KnowledgeDocumentKind.text


def extract_text_from_file(path: str, kind: KnowledgeDocumentKind) -> str:
    """Extract plain text from uploaded files."""
    file_path = Path(path)
    if kind == KnowledgeDocumentKind.pdf:
        reader = PdfReader(str(file_path))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages).strip()
    return file_path.read_text(encoding="utf-8")


def fetch_url_text(url: str) -> str:
    """Fetch and simplify a URL into readable text."""
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        },
    )
    with urlopen(request, timeout=20) as response:  # noqa: S310
        html = response.read().decode("utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n")
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def upsert_document_chunks(
    db: Session,
    document: KnowledgeDocument,
    *,
    content_text: str,
    metadata_json: dict[str, Any] | None = None,
) -> int:
    """Replace document chunks after generating embeddings."""
    db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == document.id).delete()
    chunks = chunk_text(
        content_text,
        chunk_size=settings.knowledge_chunk_size,
        overlap=settings.knowledge_chunk_overlap,
    )
    embeddings = embed_texts(chunks)
    for index, chunk in enumerate(chunks):
        db.add(
            KnowledgeChunk(
                document_id=document.id,
                workspace_id=document.workspace_id,
                project_id=document.project_id,
                chunk_index=index,
                content=chunk,
                metadata_json={**(metadata_json or {}), "document_title": document.title},
                embedding=embeddings[index] if index < len(embeddings) else _deterministic_embedding(chunk),
            )
        )
    document.content_text = content_text
    document.status = KnowledgeDocumentStatus.ready
    return len(chunks)


def search_project_knowledge(
    db: Session,
    *,
    project_id: str,
    query: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Search a project's knowledge chunks with embedding similarity."""
    query_embedding = embed_texts([query])[0]
    chunks = db.scalars(
        select(KnowledgeChunk).where(KnowledgeChunk.project_id == project_id)
    ).all()

    scored_hits: list[dict[str, Any]] = []
    for chunk in chunks:
        if chunk.embedding is None:
            continue
        document = db.get(KnowledgeDocument, chunk.document_id)
        if not document:
            continue
        score = cosine_similarity(list(chunk.embedding), query_embedding)
        scored_hits.append(
            {
                "document_id": document.id,
                "document_title": document.title,
                "chunk_id": chunk.id,
                "content": chunk.content,
                "score": round(score, 4),
                "metadata_json": {
                    **chunk.metadata_json,
                    "kind": document.kind.value,
                    "source_uri": document.source_uri,
                },
                "source_id": f"knowledge-{document.id}-{chunk.chunk_index}",
                "url": document.source_uri or f"workspace://knowledge/{document.id}",
                "title": document.title,
                "excerpt": chunk.content[:320],
                "summary": chunk.content[:480],
                "published_at": None,
                "confidence": round(score, 4),
                "retrieved_at": "workspace-knowledge",
            }
        )

    scored_hits.sort(key=lambda item: item["score"], reverse=True)
    return scored_hits[:limit]
