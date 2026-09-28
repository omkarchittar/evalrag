"""Exact cosine retrieval over one immutable embedding-space identity."""

import math
from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from evalrag.models import Chunk, Document, KnowledgeBase


@dataclass(frozen=True)
class IndexSpec:
    knowledge_base_id: str
    workspace_id: str
    embedding_model: str
    embedding_dimension: int
    index_version: int

    @classmethod
    def from_kb(cls, kb: KnowledgeBase):
        return cls(
            kb.id, kb.workspace_id, kb.embedding_model, kb.embedding_dimension, kb.index_version
        )


@dataclass(frozen=True)
class Source:
    chunk_id: str
    document_id: str
    filename: str
    page: int
    ordinal: int
    content: str
    token_count: int
    score: float

    def as_dict(self):
        return asdict(self)


def retrieve(
    db: Session,
    index: IndexSpec,
    vector: list[float],
    *,
    top_k: int,
    minimum_score: float,
    document_ids: list[str] | None = None,
) -> list[Source]:
    if not 1 <= top_k <= 20 or not -1 <= minimum_score <= 1:
        raise ValueError("Invalid retrieval bounds")
    if (
        len(vector) != index.embedding_dimension
        or not any(vector)
        or any(type(v) not in {float, int} or not math.isfinite(v) for v in vector)
    ):
        raise ValueError("Search vector does not match the embedding space")
    distance = Chunk.embedding.cosine_distance(vector)
    query = (
        select(Chunk, Document.filename, distance.label("distance"))
        .join(Document, Document.id == Chunk.document_id)
        .where(
            Chunk.knowledge_base_id == index.knowledge_base_id,
            Chunk.embedding_dimension == index.embedding_dimension,
            Chunk.index_version == index.index_version,
            Document.status == "ready",
            distance <= 1 - minimum_score,
        )
    )
    if document_ids is not None:
        query = query.where(Document.id.in_(document_ids))
    rows = db.execute(query.order_by(distance, Chunk.id).limit(top_k)).all()
    return [
        Source(
            chunk.id,
            chunk.document_id,
            filename,
            chunk.page,
            chunk.ordinal,
            chunk.content,
            chunk.token_count,
            min(1.0, max(-1.0, 1 - float(d))),
        )
        for chunk, filename, d in rows
    ]
