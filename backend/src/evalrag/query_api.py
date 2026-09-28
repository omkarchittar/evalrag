"""Authenticated query commands and persisted trace inspection."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import Field
from sqlalchemy import func, select

from evalrag.api import knowledge_base
from evalrag.auth import Actor, Db, Input
from evalrag.generation import OpenAIGenerationProvider
from evalrag.models import QueryTrace
from evalrag.providers import OpenAIEmbeddingProvider
from evalrag.rag import QueryAccessError, QueryConfig, ask

router = APIRouter(prefix="/api", tags=["queries"])


class QueryInput(Input):
    question: str = Field(min_length=1, max_length=4000)
    config: QueryConfig | None = None


class QueryProviders:
    def __init__(self, settings):
        self.settings = settings
        self.standard_openai = settings.openai_base_url.rstrip("/") == "https://api.openai.com/v1"

    def key(self):
        value = self.settings.openai_api_key
        return value.get_secret_value() if value else ""

    def embedding(self, index):
        return OpenAIEmbeddingProvider(
            self.key(),
            model=index.embedding_model,
            dimensions=index.embedding_dimension,
            base_url=self.settings.openai_base_url,
            timeout=self.settings.provider_timeout_seconds,
        )

    def generation(self, model):
        return OpenAIGenerationProvider(
            self.key(),
            model=model,
            base_url=self.settings.openai_base_url,
            timeout=self.settings.provider_timeout_seconds,
        )


def get_query_database(request: Request):
    return request.app.state.database


def get_query_providers(request: Request):
    return QueryProviders(request.app.state.settings)


def trace_view(trace):
    fields = [
        "id",
        "knowledge_base_id",
        "user_id",
        "request_id",
        "question",
        "answer",
        "config",
        "retrieved",
        "citations",
        "tool_calls",
        "abstained",
        "latency_ms",
        "input_tokens",
        "output_tokens",
        "cost_usd",
        "error_code",
        "created_at",
    ]
    return {
        **{key: getattr(trace, key) for key in fields},
        "outcome": "error" if trace.error_code else "abstained" if trace.abstained else "answered",
    }


def allowed_models(settings):
    return list(dict.fromkeys([settings.generation_model, *settings.additional_generation_models]))


@router.get("/query-options")
def query_options(request: Request, actor: Actor):
    return {
        "models": allowed_models(request.app.state.settings),
        "prompt_versions": ["grounded-v1", "concise-v1"],
        "max_top_k": 20,
        "max_tool_calls": 3,
    }


@router.post("/knowledge-bases/{kb_id}/queries", status_code=201)
def create_query(
    kb_id: str,
    body: QueryInput,
    request: Request,
    db: Db,
    actor: Actor,
    database: Annotated[object, Depends(get_query_database)],
    providers: Annotated[QueryProviders, Depends(get_query_providers)],
):
    knowledge_base(db, kb_id, actor)
    settings = request.app.state.settings
    values = body.config.model_dump(exclude_unset=True) if body.config else {}
    values.setdefault("model", settings.generation_model)
    config = QueryConfig(**values)
    if config.model not in allowed_models(settings):
        raise HTTPException(422, "Generation model is not configured for this deployment")
    actor_id = actor.id
    # Finish the read-only authentication transaction before any network IO.
    db.commit()
    try:
        trace = ask(
            database,
            kb_id,
            actor_id=actor_id,
            question=body.question,
            config=config,
            request_id=request.state.request_id,
            embedding_factory=providers.embedding,
            generation_factory=providers.generation,
            standard_openai=providers.standard_openai,
        )
    except QueryAccessError as exc:
        raise HTTPException(404, "Knowledge base not found") from exc
    return trace_view(trace)


@router.get("/knowledge-bases/{kb_id}/queries")
def list_queries(
    kb_id: str,
    db: Db,
    actor: Actor,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    knowledge_base(db, kb_id, actor)
    rows = db.scalars(
        select(QueryTrace)
        .where(QueryTrace.knowledge_base_id == kb_id)
        .order_by(QueryTrace.created_at.desc(), QueryTrace.id)
        .offset(offset)
        .limit(limit)
    )
    return {
        "items": [trace_view(row) for row in rows],
        "total": db.scalar(
            select(func.count())
            .select_from(QueryTrace)
            .where(QueryTrace.knowledge_base_id == kb_id)
        ),
        "limit": limit,
        "offset": offset,
    }


@router.get("/query-traces/{trace_id}")
def get_trace(trace_id: str, db: Db, actor: Actor):
    trace = db.get(QueryTrace, trace_id)
    if trace is None:
        raise HTTPException(404, "Query trace not found")
    knowledge_base(db, trace.knowledge_base_id, actor)
    return trace_view(trace)
