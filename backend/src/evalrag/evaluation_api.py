"""Versioned datasets, immutable run creation and comparable experiment reads."""

import hashlib
from typing import Annotated, Literal

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import Field, model_validator
from sqlalchemy import delete, func, select, text

from evalrag.api import knowledge_base, membership
from evalrag.auth import Actor, Db, Input
from evalrag.evaluation import CASE_FIELDS, build_run, compare_runs, digest
from evalrag.models import (
    EvaluationCase,
    EvaluationDataset,
    EvaluationResult,
    EvaluationRun,
    Job,
    QueryTrace,
)
from evalrag.query_api import allowed_models
from evalrag.rag import QueryConfig
from evalrag.runtime import QueryProviders

router = APIRouter(prefix="/api", tags=["evaluations"])
IdempotencyKey = Annotated[
    str, Header(alias="Idempotency-Key", min_length=8, max_length=100, pattern=r"^[A-Za-z0-9:_-]+$")
]
Checksum = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Tag = Annotated[str, Field(min_length=1, max_length=40)]


class DatasetName(Input):
    name: str = Field(min_length=1, max_length=200)


class DatasetRename(DatasetName):
    version: int = Field(ge=1)


class CaseInput(Input):
    question: str = Field(min_length=1, max_length=4000)
    expected_answer: str | None = Field(default=None, min_length=1, max_length=8000)
    expected_abstention: bool | None = None
    expected_sources: list[Checksum] = Field(default_factory=list, max_length=50)
    expected_tool: Literal["document_search", "calculator", "metadata_lookup"] | None = None
    tags: list[Tag] = Field(default_factory=list, max_length=20)
    notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def consistent(self):
        if self.expected_abstention is True and self.expected_answer is not None:
            raise ValueError("An expected abstention cannot also require an answer")
        self.expected_sources = list(dict.fromkeys(self.expected_sources))
        return self


class CasesReplace(Input):
    version: int = Field(ge=1)
    cases: list[CaseInput] = Field(max_length=200)


class RunInput(Input):
    dataset_id: str = Field(min_length=1, max_length=36)
    knowledge_base_id: str = Field(min_length=1, max_length=36)
    name: str = Field(min_length=1, max_length=200)
    query: QueryConfig | None = None
    evaluate_semantics: bool = True
    evaluator_model: str | None = Field(default=None, min_length=1, max_length=100)


def get_dataset(db, identifier, actor, *, write=False, lock=False):
    statement = select(EvaluationDataset).where(EvaluationDataset.id == identifier)
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    row = db.scalar(statement)
    if row is None:
        raise HTTPException(404, "Dataset not found")
    membership(db, row.workspace_id, actor, write=write)
    return row


def dataset_view(db, row, *, cases=False):
    output = {
        "id": row.id,
        "workspace_id": row.workspace_id,
        "name": row.name,
        "version": row.version,
        "created_at": row.created_at,
        "case_count": db.scalar(
            select(func.count())
            .select_from(EvaluationCase)
            .where(EvaluationCase.dataset_id == row.id)
        ),
    }
    if cases:
        output["cases"] = [
            {k: getattr(c, k) for k in CASE_FIELDS}
            for c in db.scalars(
                select(EvaluationCase)
                .where(EvaluationCase.dataset_id == row.id)
                .order_by(EvaluationCase.created_at, EvaluationCase.id)
            )
        ]
    return output


@router.post("/workspaces/{workspace_id}/datasets", status_code=201)
def create_dataset(workspace_id: str, body: DatasetName, db: Db, actor: Actor):
    membership(db, workspace_id, actor, write=True)
    row = EvaluationDataset(workspace_id=workspace_id, name=body.name)
    db.add(row)
    db.flush()
    return dataset_view(db, row, cases=True)


@router.get("/workspaces/{workspace_id}/datasets")
def list_datasets(
    workspace_id: str,
    db: Db,
    actor: Actor,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    membership(db, workspace_id, actor)
    rows = db.scalars(
        select(EvaluationDataset)
        .where(EvaluationDataset.workspace_id == workspace_id)
        .order_by(EvaluationDataset.created_at.desc(), EvaluationDataset.id)
        .offset(offset)
        .limit(limit)
    )
    return {
        "items": [dataset_view(db, row) for row in rows],
        "offset": offset,
        "limit": limit,
        "total": db.scalar(
            select(func.count())
            .select_from(EvaluationDataset)
            .where(EvaluationDataset.workspace_id == workspace_id)
        ),
    }


@router.get("/datasets/{dataset_id}")
def read_dataset(dataset_id: str, db: Db, actor: Actor):
    return dataset_view(db, get_dataset(db, dataset_id, actor), cases=True)


@router.patch("/datasets/{dataset_id}")
def rename_dataset(dataset_id: str, body: DatasetRename, db: Db, actor: Actor):
    row = get_dataset(db, dataset_id, actor, write=True, lock=True)
    if body.version != row.version:
        raise HTTPException(409, "Dataset changed; reload before editing")
    row.name = body.name
    row.version += 1
    db.flush()
    return dataset_view(db, row, cases=True)


@router.put("/datasets/{dataset_id}/cases")
def replace_cases(dataset_id: str, body: CasesReplace, db: Db, actor: Actor):
    row = get_dataset(db, dataset_id, actor, write=True, lock=True)
    if body.version != row.version:
        raise HTTPException(409, "Dataset changed; reload before editing")
    db.execute(delete(EvaluationCase).where(EvaluationCase.dataset_id == dataset_id))
    db.add_all([EvaluationCase(dataset_id=dataset_id, **case.model_dump()) for case in body.cases])
    row.version += 1
    db.flush()
    return dataset_view(db, row, cases=True)


@router.get("/datasets/{dataset_id}/export")
def export_dataset(dataset_id: str, db: Db, actor: Actor):
    data = dataset_view(db, get_dataset(db, dataset_id, actor), cases=True)
    return {
        "schema_version": 1,
        "name": data["name"],
        "version": data["version"],
        "cases": [{k: v for k, v in c.items() if k != "id"} for c in data["cases"]],
    }


def get_run(db, identifier, actor):
    row = db.get(EvaluationRun, identifier)
    if row is None:
        raise HTTPException(404, "Evaluation run not found")
    membership(db, row.workspace_id, actor)
    return row


def run_view(db, row, *, detail=False):
    fields = [
        "id",
        "workspace_id",
        "dataset_id",
        "knowledge_base_id",
        "name",
        "status",
        "config",
        "dataset_hash",
        "corpus_hash",
        "metrics",
        "started_at",
        "completed_at",
        "error_code",
        "created_at",
    ]
    result = {key: getattr(row, key) for key in fields}
    result["total_cases"] = len(row.dataset_snapshot)
    result["completed_cases"] = db.scalar(
        select(func.count()).select_from(EvaluationResult).where(EvaluationResult.run_id == row.id)
    )
    if detail:
        result.update(dataset_snapshot=row.dataset_snapshot, corpus_snapshot=row.corpus_snapshot)
    return result


@router.post("/workspaces/{workspace_id}/evaluation-runs", status_code=201)
def create_run(
    workspace_id: str,
    body: RunInput,
    request: Request,
    db: Db,
    actor: Actor,
    idempotency_key: IdempotencyKey,
):
    membership(db, workspace_id, actor, write=True)
    data = get_dataset(db, body.dataset_id, actor)
    kb = knowledge_base(db, body.knowledge_base_id, actor)
    if data.workspace_id != workspace_id or kb.workspace_id != workspace_id:
        raise HTTPException(404, "Evaluation inputs not found in this workspace")
    key = f"eval-request:{actor.id}:{idempotency_key}"
    lock = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big", signed=True)
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock})
    submission_hash = digest({"workspace_id": workspace_id, **body.model_dump(exclude_unset=True)})
    prior = db.scalar(select(Job).where(Job.idempotency_key == key))
    if prior:
        row = db.get(EvaluationRun, prior.resource_id)
        if row.config.get("submission_hash") != submission_hash:
            raise HTTPException(
                409, "Idempotency key was already used with different run parameters"
            )
        return run_view(db, row)
    settings = request.app.state.settings
    values = body.query.model_dump(exclude_unset=True) if body.query else {}
    values.setdefault("model", settings.generation_model)
    query = QueryConfig(**values)
    evaluator = body.evaluator_model or settings.generation_model
    if query.model not in allowed_models(settings) or (
        body.evaluate_semantics and evaluator not in allowed_models(settings)
    ):
        raise HTTPException(422, "Generation/evaluator model is not configured for this deployment")
    try:
        row = build_run(
            db,
            dataset_id=data.id,
            kb_id=kb.id,
            name=body.name,
            query=query,
            evaluate_semantics=body.evaluate_semantics,
            evaluator_model=evaluator,
            provider_identity=QueryProviders(settings).identity,
            requested_by=actor.id,
            job_key=key,
            submission_hash=submission_hash,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return run_view(db, row)


@router.get("/workspaces/{workspace_id}/evaluation-runs")
def list_runs(
    workspace_id: str,
    db: Db,
    actor: Actor,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    membership(db, workspace_id, actor)
    rows = db.scalars(
        select(EvaluationRun)
        .where(EvaluationRun.workspace_id == workspace_id)
        .order_by(EvaluationRun.created_at.desc(), EvaluationRun.id)
        .offset(offset)
        .limit(limit)
    )
    return {
        "items": [run_view(db, row) for row in rows],
        "offset": offset,
        "limit": limit,
        "total": db.scalar(
            select(func.count())
            .select_from(EvaluationRun)
            .where(EvaluationRun.workspace_id == workspace_id)
        ),
    }


@router.get("/evaluation-runs/{run_id}")
def read_run(run_id: str, db: Db, actor: Actor):
    return run_view(db, get_run(db, run_id, actor), detail=True)


@router.get("/evaluation-runs/{run_id}/results")
def read_results(
    run_id: str,
    db: Db,
    actor: Actor,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    run = get_run(db, run_id, actor)
    cases = {c["id"]: c for c in run.dataset_snapshot}
    rows = db.execute(
        select(
            EvaluationResult,
            QueryTrace.answer,
            QueryTrace.abstained,
            QueryTrace.error_code,
            QueryTrace.latency_ms,
        )
        .join(QueryTrace, QueryTrace.id == EvaluationResult.trace_id)
        .where(EvaluationResult.run_id == run.id)
        .order_by(EvaluationResult.created_at, EvaluationResult.id)
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "items": [
            {
                "id": r.id,
                "case": cases[r.case_id],
                "trace_id": r.trace_id,
                "metrics": r.metrics,
                "answer": answer,
                "abstained": abstained,
                "error_code": error,
                "latency_ms": latency,
            }
            for r, answer, abstained, error, latency in rows
        ],
        "total": db.scalar(
            select(func.count())
            .select_from(EvaluationResult)
            .where(EvaluationResult.run_id == run.id)
        ),
        "offset": offset,
        "limit": limit,
    }


@router.get("/evaluation-runs/{candidate_id}/compare/{baseline_id}")
def compare(
    candidate_id: str,
    baseline_id: str,
    db: Db,
    actor: Actor,
    quality_tolerance: float = Query(0.05, ge=0, le=1, allow_inf_nan=False),
    operational_tolerance: float = Query(0.2, ge=0, le=10, allow_inf_nan=False),
):
    baseline, candidate = get_run(db, baseline_id, actor), get_run(db, candidate_id, actor)
    try:
        return compare_runs(
            baseline,
            candidate,
            quality_tolerance=quality_tolerance,
            operational_tolerance=operational_tolerance,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
