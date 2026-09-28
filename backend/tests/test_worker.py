import json
import os
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import delete, select

from evalrag.config import Settings
from evalrag.db import Database, utcnow
from evalrag.ingestion import submit_document
from evalrag.models import Chunk, Document, Job, KnowledgeBase, Workspace
from evalrag.providers import OpenAIEmbeddingProvider
from evalrag.worker import run_once

pytestmark = pytest.mark.postgres


@pytest.fixture
def work():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires PostgreSQL")
    database = Database(url)
    with database.transaction() as db:
        workspace = Workspace(name="Worker integration")
        db.add(workspace)
        db.flush()
        kb = KnowledgeBase(
            workspace_id=workspace.id,
            name="Worker KB",
            embedding_model="text-embedding-3-small",
            embedding_dimension=3,
        )
        db.add(kb)
        db.flush()
        document = submit_document(db, kb.id, "worker.txt", b"The retention policy is thirty days.")
        ids = (workspace.id, kb.id, document.id)
    try:
        yield database, ids, Settings(database_url=url)
    finally:
        with database.transaction() as db:
            db.execute(delete(Job).where(Job.resource_id == ids[2]))
            db.execute(delete(Chunk).where(Chunk.document_id == ids[2]))
            db.execute(delete(Document).where(Document.id == ids[2]))
            db.execute(delete(KnowledgeBase).where(KnowledgeBase.id == ids[1]))
            db.execute(delete(Workspace).where(Workspace.id == ids[0]))
        database.close()


def provider_factory(status=200):
    def factory(kb):
        def handle(request):
            items = json.loads(request.content)["input"]
            return httpx.Response(
                status,
                json={
                    "model": kb.embedding_model,
                    "data": [{"index": i, "embedding": [1, 0, 0]} for i in range(len(items))],
                    "usage": {"prompt_tokens": 8},
                },
            )

        return OpenAIEmbeddingProvider(
            "test",
            model=kb.embedding_model,
            dimensions=3,
            client=httpx.Client(transport=httpx.MockTransport(handle)),
        )

    return factory


def test_worker_claims_ingests_and_completes_in_real_transactions(work):
    database, ids, settings = work
    assert run_once(database, settings, embedding_factory=provider_factory())
    with database.transaction() as db:
        document = db.get(Document, ids[2])
        assert document.status == "ready"
        assert document.embedding_tokens == 8
        assert db.scalar(select(Job.status).where(Job.resource_id == document.id)) == "completed"
    assert not run_once(database, settings, embedding_factory=provider_factory())


@pytest.mark.parametrize("status,expected", [(401, "failed"), (429, "queued")])
def test_worker_records_classified_provider_failures(work, status, expected):
    database, ids, settings = work
    assert run_once(database, settings, embedding_factory=provider_factory(status))
    with database.transaction() as db:
        row = db.get(Document, ids[2])
        assert row.status == expected
        assert row.error_code == f"provider_http_{status}"
        assert db.scalar(select(Job.status).where(Job.resource_id == row.id)) == expected


def test_exhausted_crash_recovery_marks_document_failed(work):
    database, ids, settings = work
    with database.transaction() as db:
        job = db.scalar(select(Job).where(Job.resource_id == ids[2]))
        job.status = "running"
        job.attempts = job.max_attempts
        job.lease_until = utcnow() - timedelta(seconds=1)
        job.lease_token = "abandoned"
    run_once(database, settings, embedding_factory=provider_factory())
    with database.transaction() as db:
        assert db.get(Document, ids[2]).status == "failed"
        assert db.get(Document, ids[2]).error_code == "lease_exhausted"


def test_configured_large_pdf_limit_is_honored_through_indexing(work):
    from test_ingestion import make_pdf

    database, ids, settings = work
    settings.upload_limit_bytes = 12_000_000
    data = make_pdf(padding=10_000_000)
    assert len(data) > 10_000_000
    with database.transaction() as db:
        db.execute(delete(Job).where(Job.resource_id == ids[2]))
        db.execute(delete(Document).where(Document.id == ids[2]))
        row = submit_document(db, ids[1], "large.pdf", data, max_bytes=settings.upload_limit_bytes)
        # Reuse the fixture identity so its cleanup remains exact.
        db.execute(delete(Job).where(Job.resource_id == row.id))
        row.id = ids[2]
        db.add(
            Job(
                kind="ingest_document",
                resource_id=ids[2],
                idempotency_key=f"large:{ids[2]}",
                payload={},
            )
        )
    assert run_once(database, settings, embedding_factory=provider_factory())
    with database.transaction() as db:
        assert db.get(Document, ids[2]).status == "ready"
