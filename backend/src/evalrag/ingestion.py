"""Checksum-idempotent submission and atomic vector indexing."""

import hashlib
from pathlib import PurePath
from time import perf_counter

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from evalrag.chunking import chunk_pages
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


def ingest_document(db: Session, document_id: str, *, provider: EmbeddingProvider) -> Document:
    started = perf_counter()
    document = db.get(Document, document_id)
    if document is None:
        raise LookupError("Document not found")
    if document.status == "ready":
        return document
    kb = db.get(KnowledgeBase, document.knowledge_base_id)
    if provider.model != kb.embedding_model or provider.dimensions != kb.embedding_dimension:
        raise ProviderError("embedding_space_mismatch")
    chunks = chunk_pages(
        extract_pages(document.filename, document.content),
        size=kb.chunk_size,
        overlap=kb.chunk_overlap,
        strategy=kb.chunk_strategy,
    )
    vectors = []
    # Provider calls occur before the write lock. A lease-owning worker controls
    # retries; any concurrent replay rechecks completion under the final row lock.
    for offset in range(0, len(chunks), 32):
        batch = provider.embed([chunk.content for chunk in chunks[offset : offset + 32]])
        vectors.extend(batch.vectors)
    document = db.scalar(
        select(Document)
        .where(Document.id == document_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if document.status == "ready":
        return document
    for chunk, vector in zip(chunks, vectors, strict=True):
        db.add(
            Chunk(
                document_id=document.id,
                knowledge_base_id=kb.id,
                ordinal=chunk.ordinal,
                page=chunk.page,
                content=chunk.content,
                token_count=chunk.token_count,
                embedding=vector,
                embedding_dimension=kb.embedding_dimension,
                index_version=kb.index_version,
            )
        )
    document.status = "ready"
    document.chunk_count = len(chunks)
    document.ingestion_ms = int((perf_counter() - started) * 1000)
    document.indexed_at = utcnow()
    document.error_code = None
    db.flush()
    return document
