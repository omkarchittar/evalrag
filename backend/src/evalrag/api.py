"""Workspace-scoped product APIs; every object lookup enforces membership."""

from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import EmailStr, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from evalrag.auth import Actor, Db, Input
from evalrag.documents import DocumentError
from evalrag.ingestion import submit_document
from evalrag.metrics import aggregate_operations
from evalrag.models import (
    Chunk,
    Document,
    EvaluationRun,
    KnowledgeBase,
    Membership,
    QueryTrace,
    User,
    Workspace,
)

router = APIRouter(prefix="/api", tags=["knowledge"])


class WorkspaceInput(Input):
    name: str = Field(min_length=1, max_length=200)


class MembershipInput(Input):
    email: EmailStr
    role: Literal["owner", "editor", "viewer"]


class KnowledgeBaseInput(WorkspaceInput):
    description: str = Field(default="", max_length=2000)
    embedding_model: Literal["text-embedding-3-small", "text-embedding-3-large"] = (
        "text-embedding-3-small"
    )
    embedding_dimension: int = Field(default=1536, ge=1, le=3072)
    chunk_strategy: Literal["fixed", "recursive"] = "recursive"
    chunk_size: int = Field(default=400, ge=8, le=8192)
    chunk_overlap: int = Field(default=60, ge=0)

    @model_validator(mode="after")
    def valid_index(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("Overlap must be smaller than chunk size")
        if self.embedding_model == "text-embedding-3-small" and self.embedding_dimension > 1536:
            raise ValueError("Embedding dimension exceeds model capacity")
        return self


def membership(
    db: Session, workspace_id: str, actor: User, *, write=False, owner=False
) -> Membership:
    row = db.get(Membership, (workspace_id, actor.id), populate_existing=True)
    if row is None:
        raise HTTPException(404, "Workspace not found")
    if (write and row.role == "viewer") or (owner and row.role != "owner"):
        raise HTTPException(403, "Workspace permission required")
    return row


def knowledge_base(db: Session, kb_id: str, actor: User, *, write=False) -> KnowledgeBase:
    row = db.get(KnowledgeBase, kb_id)
    if row is None:
        raise HTTPException(404, "Knowledge base not found")
    membership(db, row.workspace_id, actor, write=write)
    return row


def kb_view(row: KnowledgeBase) -> dict:
    return {
        field: getattr(row, field)
        for field in [
            "id",
            "workspace_id",
            "name",
            "description",
            "embedding_provider",
            "embedding_model",
            "embedding_dimension",
            "index_version",
            "chunk_strategy",
            "chunk_size",
            "chunk_overlap",
            "created_at",
        ]
    }


def document_view(row: Document) -> dict:
    return {
        field: getattr(row, field)
        for field in [
            "id",
            "knowledge_base_id",
            "filename",
            "checksum",
            "media_type",
            "size_bytes",
            "status",
            "error_code",
            "ingestion_ms",
            "embedding_tokens",
            "chunk_count",
            "created_at",
            "indexed_at",
        ]
    }


@router.get("/workspaces")
def list_workspaces(db: Db, actor: Actor):
    rows = db.execute(
        select(Workspace, Membership.role)
        .join(Membership)
        .where(Membership.user_id == actor.id)
        .order_by(Workspace.created_at)
        .limit(200)
    ).all()
    return [
        {
            "id": workspace.id,
            "name": workspace.name,
            "role": role,
            "created_at": workspace.created_at,
        }
        for workspace, role in rows
    ]


@router.post("/workspaces", status_code=201)
def create_workspace(body: WorkspaceInput, db: Db, actor: Actor):
    row = Workspace(name=body.name)
    db.add(row)
    db.flush()
    db.add(Membership(workspace_id=row.id, user_id=actor.id, role="owner"))
    db.flush()
    return {"id": row.id, "name": row.name, "role": "owner", "created_at": row.created_at}


@router.get("/workspaces/{workspace_id}/members")
def list_members(workspace_id: str, db: Db, actor: Actor):
    membership(db, workspace_id, actor)
    rows = db.execute(
        select(User, Membership.role)
        .join(Membership)
        .where(Membership.workspace_id == workspace_id)
    ).all()
    return [
        {"id": user.id, "name": user.name, "email": user.email, "role": role} for user, role in rows
    ]


@router.put("/workspaces/{workspace_id}/members")
def set_member(workspace_id: str, body: MembershipInput, db: Db, actor: Actor):
    db.scalar(select(Workspace).where(Workspace.id == workspace_id).with_for_update())
    membership(db, workspace_id, actor, owner=True)
    user = db.scalar(
        select(User).where(User.email == str(body.email).casefold(), User.active.is_(True))
    )
    if user is None:
        raise HTTPException(404, "Active user not found")
    if user.id == actor.id and body.role != "owner":
        owners = db.scalar(
            select(func.count())
            .select_from(Membership)
            .where(Membership.workspace_id == workspace_id, Membership.role == "owner")
        )
        if owners <= 1:
            raise HTTPException(409, "At least one workspace owner is required")
    db.execute(
        insert(Membership)
        .values(workspace_id=workspace_id, user_id=user.id, role=body.role)
        .on_conflict_do_update(index_elements=["workspace_id", "user_id"], set_={"role": body.role})
    )
    return {"user_id": user.id, "role": body.role}


@router.get("/workspaces/{workspace_id}/knowledge-bases")
def list_knowledge_bases(workspace_id: str, db: Db, actor: Actor):
    membership(db, workspace_id, actor)
    return [
        kb_view(row)
        for row in db.scalars(
            select(KnowledgeBase)
            .where(KnowledgeBase.workspace_id == workspace_id)
            .order_by(KnowledgeBase.created_at.desc())
            .limit(200)
        )
    ]


@router.post("/workspaces/{workspace_id}/knowledge-bases", status_code=201)
def create_knowledge_base(workspace_id: str, body: KnowledgeBaseInput, db: Db, actor: Actor):
    membership(db, workspace_id, actor, write=True)
    row = KnowledgeBase(workspace_id=workspace_id, **body.model_dump())
    db.add(row)
    db.flush()
    return kb_view(row)


@router.get("/knowledge-bases/{kb_id}")
def get_knowledge_base(kb_id: str, db: Db, actor: Actor):
    return kb_view(knowledge_base(db, kb_id, actor))


@router.get("/knowledge-bases/{kb_id}/documents")
def list_documents(
    kb_id: str,
    db: Db,
    actor: Actor,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    knowledge_base(db, kb_id, actor)
    rows = db.scalars(
        select(Document)
        .where(Document.knowledge_base_id == kb_id)
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    total = db.scalar(
        select(func.count()).select_from(Document).where(Document.knowledge_base_id == kb_id)
    )
    return {
        "items": [document_view(row) for row in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.post("/knowledge-bases/{kb_id}/documents", status_code=201)
def upload_document(
    kb_id: str, request: Request, db: Db, actor: Actor, file: Annotated[UploadFile, File()]
):
    knowledge_base(db, kb_id, actor, write=True)
    maximum = request.app.state.settings.upload_limit_bytes
    data = file.file.read(maximum + 1)
    try:
        return document_view(
            submit_document(db, kb_id, file.filename or "", data, max_bytes=maximum)
        )
    except (DocumentError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        file.file.close()


@router.get("/documents/{document_id}/download")
def download_document(document_id: str, db: Db, actor: Actor):
    row = db.get(Document, document_id)
    if row is None:
        raise HTTPException(404, "Document not found")
    knowledge_base(db, row.knowledge_base_id, actor)
    return Response(
        row.content,
        media_type=row.media_type,
        headers={
            "Content-Disposition": "attachment; filename*=UTF-8''" + quote(row.filename, safe="")
        },
    )


@router.get("/documents/{document_id}/chunks")
def list_chunks(
    document_id: str,
    db: Db,
    actor: Actor,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    row = db.get(Document, document_id)
    if row is None:
        raise HTTPException(404, "Document not found")
    knowledge_base(db, row.knowledge_base_id, actor)
    chunks = db.scalars(
        select(Chunk)
        .where(Chunk.document_id == document_id)
        .order_by(Chunk.ordinal)
        .offset(offset)
        .limit(limit)
    )
    return {
        "items": [
            {
                "id": c.id,
                "page": c.page,
                "ordinal": c.ordinal,
                "content": c.content,
                "token_count": c.token_count,
            }
            for c in chunks
        ],
        "total": row.chunk_count,
        "offset": offset,
        "limit": limit,
    }


@router.get("/workspaces/{workspace_id}/overview")
def overview(workspace_id: str, db: Db, actor: Actor):
    membership(db, workspace_id, actor)
    kb_ids = select(KnowledgeBase.id).where(KnowledgeBase.workspace_id == workspace_id)
    counts = dict(
        db.execute(
            select(Document.status, func.count())
            .where(Document.knowledge_base_id.in_(kb_ids))
            .group_by(Document.status)
        ).all()
    )
    traces = db.scalars(
        select(QueryTrace)
        .where(QueryTrace.knowledge_base_id.in_(kb_ids))
        .order_by(QueryTrace.created_at.desc())
        .limit(200)
    ).all()
    rows = [
        {
            "latency_ms": t.latency_ms,
            "input_tokens": t.input_tokens,
            "output_tokens": t.output_tokens,
            "cost_usd": t.cost_usd,
            "error": bool(t.error_code),
        }
        for t in traces
    ]
    runs = db.scalars(
        select(EvaluationRun)
        .where(EvaluationRun.workspace_id == workspace_id)
        .order_by(EvaluationRun.created_at.desc())
        .limit(10)
    )
    return {
        "documents": counts,
        "knowledge_base_count": db.scalar(
            select(func.count())
            .select_from(KnowledgeBase)
            .where(KnowledgeBase.workspace_id == workspace_id)
        ),
        "operations": aggregate_operations(rows),
        "operations_sample_limit": 200,
        "recent_runs": [
            {
                "id": r.id,
                "name": r.name,
                "status": r.status,
                "metrics": r.metrics,
                "created_at": r.created_at,
            }
            for r in runs
        ],
    }
