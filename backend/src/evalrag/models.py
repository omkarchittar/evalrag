"""Relational invariants are enforced in PostgreSQL as well as domain services."""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from evalrag.db import Base, new_id, utcnow


class Identity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Identity, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(320), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(20), default="member")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (CheckConstraint("role IN ('member','admin')", name="valid_role"),)


class AuthSession(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Job(Identity, Base):
    __tablename__ = "jobs"
    kind: Mapped[str] = mapped_column(String(40))
    resource_id: Mapped[str] = mapped_column(String(36), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[str | None] = mapped_column(String(36))
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("status IN ('queued','running','completed','failed')", name="valid_status"),
        CheckConstraint("attempts >= 0 AND max_attempts > 0", name="valid_attempts"),
        Index("ix_jobs_claim", "status", "available_at"),
    )


class Workspace(Identity, Base):
    __tablename__ = "workspaces"
    name: Mapped[str] = mapped_column(String(200))


class Membership(Base):
    __tablename__ = "memberships"
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(20), default="editor")
    __table_args__ = (CheckConstraint("role IN ('owner','editor','viewer')", name="valid_role"),)


class KnowledgeBase(Identity, Base):
    __tablename__ = "knowledge_bases"
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    embedding_provider: Mapped[str] = mapped_column(String(40), default="openai")
    embedding_model: Mapped[str] = mapped_column(String(100))
    embedding_dimension: Mapped[int] = mapped_column(Integer, default=1536)
    index_version: Mapped[int] = mapped_column(Integer, default=1)
    chunk_strategy: Mapped[str] = mapped_column(String(20), default="recursive")
    chunk_size: Mapped[int] = mapped_column(Integer, default=400)
    chunk_overlap: Mapped[int] = mapped_column(Integer, default=60)
    __table_args__ = (
        UniqueConstraint("id", "workspace_id"),
        UniqueConstraint(
            "id", "embedding_dimension", "index_version", name="uq_knowledge_bases_index_identity"
        ),
        CheckConstraint("chunk_strategy IN ('fixed','recursive')", name="valid_chunk_strategy"),
        CheckConstraint(
            "chunk_size BETWEEN 8 AND 8192 AND chunk_overlap >= 0 AND chunk_overlap < chunk_size",
            name="valid_chunk_bounds",
        ),
        CheckConstraint(
            "embedding_dimension BETWEEN 1 AND 16000 AND index_version > 0", name="valid_index"
        ),
    )


class Document(Identity, Base):
    __tablename__ = "documents"
    knowledge_base_id: Mapped[str] = mapped_column(ForeignKey("knowledge_bases.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    checksum: Mapped[str] = mapped_column(String(64))
    media_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    content: Mapped[bytes] = mapped_column(LargeBinary)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    error_code: Mapped[str | None] = mapped_column(String(80))
    embedding_tokens: Mapped[int] = mapped_column(Integer, default=0)
    ingestion_ms: Mapped[int | None] = mapped_column(Integer)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("knowledge_base_id", "checksum"),
        UniqueConstraint("id", "knowledge_base_id"),
        CheckConstraint("status IN ('queued','processing','ready','failed')", name="valid_status"),
        CheckConstraint("size_bytes > 0 AND chunk_count >= 0", name="valid_size"),
    )


class Chunk(Identity, Base):
    __tablename__ = "chunks"
    document_id: Mapped[str] = mapped_column(String(36))
    knowledge_base_id: Mapped[str] = mapped_column(String(36), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    page: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[list[float]] = mapped_column(Vector())
    embedding_dimension: Mapped[int] = mapped_column(Integer)
    index_version: Mapped[int] = mapped_column(Integer)
    __table_args__ = (
        UniqueConstraint("document_id", "ordinal"),
        ForeignKeyConstraint(
            ["document_id", "knowledge_base_id"], ["documents.id", "documents.knowledge_base_id"]
        ),
        ForeignKeyConstraint(
            ["knowledge_base_id", "embedding_dimension", "index_version"],
            [
                "knowledge_bases.id",
                "knowledge_bases.embedding_dimension",
                "knowledge_bases.index_version",
            ],
        ),
        CheckConstraint(
            "vector_dims(embedding) = embedding_dimension", name="embedding_dimension_matches"
        ),
        CheckConstraint("ordinal >= 0 AND page > 0 AND token_count > 0", name="valid_chunk"),
    )


class QueryTrace(Identity, Base):
    __tablename__ = "query_traces"
    knowledge_base_id: Mapped[str] = mapped_column(ForeignKey("knowledge_bases.id"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    request_id: Mapped[str] = mapped_column(String(100), index=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict] = mapped_column(JSONB)
    retrieved: Mapped[list] = mapped_column(JSONB, default=list)
    citations: Mapped[list] = mapped_column(JSONB, default=list)
    tool_calls: Mapped[list] = mapped_column(JSONB, default=list)
    abstained: Mapped[bool] = mapped_column(Boolean, default=False)
    latency_ms: Mapped[int] = mapped_column(Integer)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float | None] = mapped_column(Float)
    error_code: Mapped[str | None] = mapped_column(String(80))


class EvaluationDataset(Identity, Base):
    __tablename__ = "evaluation_datasets"
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (UniqueConstraint("id", "workspace_id"),)


class EvaluationCase(Identity, Base):
    __tablename__ = "evaluation_cases"
    dataset_id: Mapped[str] = mapped_column(ForeignKey("evaluation_datasets.id"), index=True)
    question: Mapped[str] = mapped_column(Text)
    expected_answer: Mapped[str | None] = mapped_column(Text)
    expected_abstention: Mapped[bool | None] = mapped_column(Boolean)
    expected_sources: Mapped[list] = mapped_column(JSONB, default=list)
    expected_tool: Mapped[str | None] = mapped_column(String(60))
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    notes: Mapped[str] = mapped_column(Text, default="")


class EvaluationRun(Identity, Base):
    __tablename__ = "evaluation_runs"
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    dataset_id: Mapped[str] = mapped_column(String(36), index=True)
    knowledge_base_id: Mapped[str] = mapped_column(String(36), index=True)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    config: Mapped[dict] = mapped_column(JSONB)
    dataset_snapshot: Mapped[list] = mapped_column(JSONB)
    corpus_snapshot: Mapped[list] = mapped_column(JSONB)
    dataset_hash: Mapped[str] = mapped_column(String(64))
    corpus_hash: Mapped[str] = mapped_column(String(64))
    metrics: Mapped[dict | None] = mapped_column(JSONB)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    __table_args__ = (
        ForeignKeyConstraint(
            ["dataset_id", "workspace_id"],
            ["evaluation_datasets.id", "evaluation_datasets.workspace_id"],
        ),
        ForeignKeyConstraint(
            ["knowledge_base_id", "workspace_id"],
            ["knowledge_bases.id", "knowledge_bases.workspace_id"],
        ),
        CheckConstraint("status IN ('queued','running','completed','failed')", name="valid_status"),
    )


class EvaluationResult(Identity, Base):
    __tablename__ = "evaluation_results"
    run_id: Mapped[str] = mapped_column(ForeignKey("evaluation_runs.id"), index=True)
    case_id: Mapped[str] = mapped_column(String(36))  # snapshot identity, survives dataset edits
    trace_id: Mapped[str] = mapped_column(ForeignKey("query_traces.id"))
    metrics: Mapped[dict] = mapped_column(JSONB)
    __table_args__ = (UniqueConstraint("run_id", "case_id"),)


class LoginThrottle(Base):
    __tablename__ = "login_throttles"
    subject_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    __table_args__ = (CheckConstraint("attempts > 0", name="positive_attempts"),)
