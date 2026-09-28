"""Checksum-idempotent submission and atomic vector indexing."""

import hashlib
from dataclasses import dataclass
from pathlib import PurePath
from time import perf_counter

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from evalrag.chunking import TextChunk, chunk_pages
from evalrag.db import new_id, utcnow
from evalrag.documents import MEDIA_TYPES, extract_pages
from evalrag.models import Chunk, Document, Job, KnowledgeBase
from evalrag.providers import EmbeddingProvider, ProviderError


def submit_document(
    db: Session, knowledge_base_id: str, filename: str, data: bytes, *, max_bytes: int = 10_000_000
) -> Document:
    filename = PurePath(filename.replace("\\", "/")).name
    if not filename or len(filename) > 255:
        raise ValueError("Filename must contain 1–255 characters")
    extract_pages(filename, data, max_bytes=max_bytes)
    checksum = hashlib.sha256(data).hexdigest()
    # ON CONFLICT handles concurrent identical uploads without aborting the caller's transaction.
    document_id = db.scalar(
        insert(Document)
        .values(
            id=new_id(),
            knowledge_base_id=knowledge_base_id,
            filename=filename,
            checksum=checksum,
            media_type=MEDIA_TYPES[PurePath(filename).suffix.lower()],
            size_bytes=len(data),
            content=data,
            status="queued",
            chunk_count=0,
            created_at=utcnow(),
        )
        .on_conflict_do_nothing(index_elements=["knowledge_base_id", "checksum"])
        .returning(Document.id)
    )
    if document_id:
        db.add(
            Job(
                kind="ingest_document",
                resource_id=document_id,
                idempotency_key=f"ingest:{document_id}",
                payload={},
            )
        )
        db.flush()
        return db.get(Document, document_id)
    return db.scalar(
        select(Document).where(
            Document.knowledge_base_id == knowledge_base_id, Document.checksum == checksum
        )
    )


@dataclass(frozen=True)
class IndexInput:
    document_id: str
    knowledge_base_id: str
    checksum: str
    filename: str
    content: bytes
    embedding_model: str
    embedding_dimension: int
    index_version: int
    chunk_size: int
    chunk_overlap: int
    chunk_strategy: str


@dataclass(frozen=True)
class PreparedIndex:
    source: IndexInput
    chunks: list[TextChunk]
    vectors: list[list[float]]
    input_tokens: int
    duration_ms: int


def index_input(db: Session, document_id: str) -> IndexInput:
    document = db.get(Document, document_id)
    if document is None:
        raise LookupError("Document not found")
    kb = db.get(KnowledgeBase, document.knowledge_base_id)
    return IndexInput(
        document.id,
        kb.id,
        document.checksum,
        document.filename,
        document.content,
        kb.embedding_model,
        kb.embedding_dimension,
        kb.index_version,
        kb.chunk_size,
        kb.chunk_overlap,
        kb.chunk_strategy,
    )


def build_index(source: IndexInput, provider: EmbeddingProvider) -> PreparedIndex:
    """Provider IO operates on a detached snapshot, with no open DB transaction."""
    started = perf_counter()
    if (
        provider.model != source.embedding_model
        or provider.dimensions != source.embedding_dimension
    ):
        raise ProviderError("embedding_space_mismatch")
    chunks = chunk_pages(
        # The bytes have already passed admission limits. Preserve that accepted
        # size across later worker configuration changes, up to the global ceiling.
        extract_pages(
            source.filename, source.content, max_bytes=min(len(source.content), 50_000_000)
        ),
        size=source.chunk_size,
        overlap=source.chunk_overlap,
        strategy=source.chunk_strategy,
    )
    vectors = []
    tokens = 0
    for offset in range(0, len(chunks), 32):
        batch = provider.embed([chunk.content for chunk in chunks[offset : offset + 32]])
        if batch.model != source.embedding_model or batch.dimensions != source.embedding_dimension:
            raise ProviderError("embedding_space_mismatch")
        vectors.extend(batch.vectors)
        tokens += batch.input_tokens
    return PreparedIndex(source, chunks, vectors, tokens, int((perf_counter() - started) * 1000))


def commit_index(db: Session, prepared: PreparedIndex) -> Document:
    source = prepared.source
    document = db.scalar(
        select(Document)
        .where(Document.id == source.document_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if document is None:
        raise LookupError("Document not found")
    if document.status == "ready":
        return document
    current = index_input(db, document.id)
    if current != source:
        raise ProviderError("index_inputs_changed")
    for chunk, vector in zip(prepared.chunks, prepared.vectors, strict=True):
        db.add(
            Chunk(
                document_id=document.id,
                knowledge_base_id=source.knowledge_base_id,
                ordinal=chunk.ordinal,
                page=chunk.page,
                content=chunk.content,
                token_count=chunk.token_count,
                embedding=vector,
                embedding_dimension=source.embedding_dimension,
                index_version=source.index_version,
            )
        )
    document.status = "ready"
    document.chunk_count = len(prepared.chunks)
    document.embedding_tokens = prepared.input_tokens
    document.ingestion_ms = prepared.duration_ms
    document.indexed_at = utcnow()
    document.error_code = None
    db.flush()
    return document


def ingest_document(db: Session, document_id: str, *, provider: EmbeddingProvider) -> Document:
    """Synchronous service for controlled callers; production workers separate phases."""
    row = db.get(Document, document_id)
    if row is not None and row.status == "ready":
        return row
    return commit_index(db, build_index(index_input(db, document_id), provider))
