import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from evalrag.models import Base, Chunk, Document, KnowledgeBase, Workspace

pytestmark = pytest.mark.postgres


def knowledge_base(db, name="Engineering"):
    workspace = Workspace(name=name)
    db.add(workspace)
    db.flush()
    kb = KnowledgeBase(
        workspace_id=workspace.id,
        name="Handbook",
        embedding_model="test-vector",
        embedding_dimension=3,
    )
    db.add(kb)
    db.flush()
    return kb


def document(db, kb, checksum="a" * 64):
    doc = Document(
        knowledge_base_id=kb.id,
        filename="handbook.md",
        checksum=checksum,
        media_type="text/markdown",
        size_bytes=20,
        content=b"hello evidence",
    )
    db.add(doc)
    db.flush()
    return doc


def test_checksum_is_unique_within_knowledge_base(db):
    kb = knowledge_base(db)
    document(db, kb)
    with pytest.raises(IntegrityError):
        document(db, kb)


def test_checksum_can_exist_in_independent_knowledge_bases(db):
    first, second = knowledge_base(db, "One"), knowledge_base(db, "Two")
    assert document(db, first).id != document(db, second).id


def test_pgvector_ranks_actual_vectors(db):
    kb = knowledge_base(db)
    doc = document(db, kb)
    for ordinal, vector in enumerate([[1, 0, 0], [0, 1, 0], [0.8, 0.2, 0]]):
        db.add(
            Chunk(
                document_id=doc.id,
                knowledge_base_id=kb.id,
                ordinal=ordinal,
                page=1,
                content=f"Evidence {ordinal}",
                token_count=4,
                embedding=vector,
                embedding_dimension=3,
                index_version=1,
            )
        )
    db.flush()
    ranked = db.scalars(
        select(Chunk)
        .where(Chunk.knowledge_base_id == kb.id)
        .order_by(Chunk.embedding.cosine_distance([1, 0, 0]))
        .limit(2)
    ).all()
    assert [row.ordinal for row in ranked] == [0, 2]


def test_chunk_cannot_reference_document_in_another_knowledge_base(db):
    first, second = knowledge_base(db, "One"), knowledge_base(db, "Two")
    doc = document(db, first)
    db.add(
        Chunk(
            document_id=doc.id,
            knowledge_base_id=second.id,
            ordinal=0,
            page=1,
            content="wrong tenant",
            token_count=2,
            embedding=[1, 0, 0],
            embedding_dimension=3,
            index_version=1,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_embedding_dimension_is_enforced_by_postgres(db):
    kb = knowledge_base(db)
    doc = document(db, kb)
    db.add(
        Chunk(
            document_id=doc.id,
            knowledge_base_id=kb.id,
            ordinal=0,
            page=1,
            content="bad dimension",
            token_count=2,
            embedding=[1, 0],
            embedding_dimension=3,
            index_version=1,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_table_names_cover_persisted_rag_contract():
    assert {
        "workspaces",
        "memberships",
        "knowledge_bases",
        "documents",
        "chunks",
        "query_traces",
        "evaluation_datasets",
        "evaluation_cases",
        "evaluation_runs",
        "evaluation_results",
        "jobs",
        "users",
        "sessions",
    } <= set(Base.metadata.tables)


def test_evaluation_inputs_cannot_change_after_run_creation(db):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from evalrag.models import EvaluationDataset, EvaluationRun

    kb = knowledge_base(db)
    dataset = EvaluationDataset(workspace_id=kb.workspace_id, name="Regression suite")
    db.add(dataset)
    db.flush()
    run = EvaluationRun(
        workspace_id=kb.workspace_id,
        dataset_id=dataset.id,
        knowledge_base_id=kb.id,
        name="Baseline",
        config={"top_k": 5},
        dataset_snapshot=[],
        corpus_snapshot=[],
        dataset_hash="a" * 64,
        corpus_hash="b" * 64,
    )
    db.add(run)
    db.flush()
    with pytest.raises(DBAPIError, match="immutable"):
        db.execute(text("UPDATE evaluation_runs SET config='{}' WHERE id=:id"), {"id": run.id})


def test_metrics_can_be_finalized_but_completed_runs_are_immutable(db):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from evalrag.models import EvaluationDataset, EvaluationRun

    kb = knowledge_base(db)
    dataset = EvaluationDataset(workspace_id=kb.workspace_id, name="Regression suite")
    db.add(dataset)
    db.flush()
    run = EvaluationRun(
        workspace_id=kb.workspace_id,
        dataset_id=dataset.id,
        knowledge_base_id=kb.id,
        name="Baseline",
        config={"top_k": 5},
        dataset_snapshot=[],
        corpus_snapshot=[],
        dataset_hash="a" * 64,
        corpus_hash="b" * 64,
    )
    db.add(run)
    db.flush()
    run.status = "completed"
    run.metrics = {"recall_at_k": 0.8}
    db.flush()
    with pytest.raises(DBAPIError, match="immutable"):
        db.execute(text("UPDATE evaluation_runs SET metrics='{}' WHERE id=:id"), {"id": run.id})
