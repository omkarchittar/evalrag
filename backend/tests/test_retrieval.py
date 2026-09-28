import pytest
from test_persistence import document, knowledge_base

from evalrag.models import Chunk
from evalrag.retrieval import IndexSpec, retrieve

pytestmark = pytest.mark.postgres


def populate(db, kb, vector, *, status="ready", content="Retention is 30 days."):
    doc = document(db, kb)
    doc.status = status
    chunk = Chunk(
        document_id=doc.id,
        knowledge_base_id=kb.id,
        ordinal=0,
        page=2,
        content=content,
        token_count=6,
        embedding=vector,
        embedding_dimension=kb.embedding_dimension,
        index_version=kb.index_version,
    )
    db.add(chunk)
    db.flush()
    return doc, chunk


def test_retrieval_uses_ready_scoped_index_and_returns_provenance(db):
    first, second = knowledge_base(db), knowledge_base(db)
    doc, chunk = populate(db, first, [1, 0, 0])
    populate(db, second, [1, 0, 0], content="Private other workspace")
    results = retrieve(db, IndexSpec.from_kb(first), [1, 0, 0], top_k=5, minimum_score=0)
    assert len(results) == 1
    assert results[0].chunk_id == chunk.id
    assert results[0].document_id == doc.id
    assert results[0].page == 2
    assert results[0].score == pytest.approx(1)
    assert "Private" not in results[0].content


def test_retrieval_respects_threshold_corpus_and_document_state(db):
    kb = knowledge_base(db)
    doc, _ = populate(db, kb, [0, 1, 0], status="processing")
    spec = IndexSpec.from_kb(kb)
    assert retrieve(db, spec, [1, 0, 0], top_k=5, minimum_score=-1) == []
    doc.status = "ready"
    db.flush()
    assert retrieve(db, spec, [1, 0, 0], top_k=5, minimum_score=0.5) == []
    assert retrieve(db, spec, [0, 1, 0], top_k=5, minimum_score=0, document_ids=[]) == []
    assert len(retrieve(db, spec, [0, 1, 0], top_k=5, minimum_score=0, document_ids=[doc.id])) == 1


@pytest.mark.parametrize("vector", [[1, 0], [0, 0, 0], [float("nan"), 0, 1], [True, 0, 1]])
def test_invalid_search_vectors_fail_before_database_operation(db, vector):
    kb = knowledge_base(db)
    with pytest.raises(ValueError):
        retrieve(db, IndexSpec.from_kb(kb), vector, top_k=5, minimum_score=0)
