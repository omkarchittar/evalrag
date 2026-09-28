from datetime import timedelta

import pytest
from sqlalchemy import func, select
from test_evaluation import dataset
from test_persistence import knowledge_base
from test_rag import Embeddings, Transactions, final
from test_retrieval import populate

from evalrag.config import Settings
from evalrag.db import utcnow
from evalrag.evaluation import build_run
from evalrag.models import EvaluationCase, EvaluationResult, Job
from evalrag.rag import QueryConfig
from evalrag.worker import run_once

pytestmark = pytest.mark.postgres


class Providers:
    identity = "test-provider"
    standard_openai = True

    def __init__(self, database, chunk, crash=False):
        self.database, self.chunk, self.crash = database, chunk, crash
        self.calls = 0

    def embedding(self, index):
        return Embeddings(self.database)

    def generation(self, model):
        return self

    def complete(self, messages, *, tools):
        self.calls += 1
        if self.crash and self.calls == 2:
            raise KeyboardInterrupt("Simulated process termination")
        assert not self.database.active
        return final(self.chunk.id)


@pytest.fixture
def experiment(db):
    kb = knowledge_base(db)
    doc, chunk = populate(db, kb, [1, 0, 0])
    data, _ = dataset(db, kb)
    run = build_run(
        db,
        provider_identity="test-provider",
        dataset_id=data.id,
        kb_id=kb.id,
        name="Run",
        query=QueryConfig(),
        evaluate_semantics=False,
        evaluator_model=None,
    )
    database = Transactions(db)
    return database, run, chunk, data


def test_worker_completes_run_with_real_persisted_metrics(experiment, db):
    database, run, chunk, _ = experiment
    providers = Providers(database, chunk)
    assert run_once(database, Settings(), query_providers=providers)
    db.refresh(run)
    assert run.status == "completed"
    assert run.metrics["quality"]["exact_match"] == 1
    assert run.metrics["quality"]["recall_at_k"] == 1
    assert run.metrics["operations"]["queries"] == 1
    assert run.metrics["quality"]["semantic_similarity"] is None
    assert db.scalar(select(func.count()).select_from(EvaluationResult)) == 1
    assert not run_once(database, Settings(), query_providers=providers)


def test_corpus_change_fails_explicitly_before_provider_calls(experiment, db):
    database, run, chunk, _ = experiment
    chunk.content = "Modified after scheduling"
    db.flush()
    providers = Providers(database, chunk)
    run_once(database, Settings(), query_providers=providers)
    db.refresh(run)
    assert run.status == "failed" and run.error_code == "evaluation_corpus_changed"
    assert providers.calls == 0


def test_exhausted_lease_marks_evaluation_failed(experiment, db):
    database, run, chunk, _ = experiment
    job = db.scalar(select(Job).where(Job.resource_id == run.id))
    job.status = "running"
    job.attempts = job.max_attempts
    job.lease_until = utcnow() - timedelta(seconds=1)
    job.lease_token = "expired"
    db.flush()
    assert not run_once(database, Settings(), query_providers=Providers(database, chunk))
    db.refresh(run)
    assert run.status == "failed" and run.error_code == "lease_exhausted"


def test_recovery_resumes_only_unfinished_cases(db):
    kb = knowledge_base(db)
    _, chunk = populate(db, kb, [1, 0, 0])
    data, _ = dataset(db, kb)
    db.add(
        EvaluationCase(
            dataset_id=data.id,
            question="Confirm retention?",
            expected_answer="Retention is 30 days.",
            expected_sources=["a" * 64],
        )
    )
    db.flush()
    run = build_run(
        db,
        provider_identity="test-provider",
        dataset_id=data.id,
        kb_id=kb.id,
        name="Resume",
        query=QueryConfig(),
        evaluate_semantics=False,
        evaluator_model=None,
    )
    database = Transactions(db)
    with pytest.raises(KeyboardInterrupt):
        run_once(database, Settings(), query_providers=Providers(database, chunk, crash=True))
    assert db.scalar(select(func.count()).select_from(EvaluationResult)) == 1
    job = db.scalar(select(Job).where(Job.resource_id == run.id))
    job.lease_until = utcnow() - timedelta(seconds=1)
    db.flush()
    replacement = Providers(database, chunk)
    run_once(database, Settings(), query_providers=replacement)
    db.refresh(run)
    assert run.status == "completed" and run.metrics["case_count"] == 2
    assert replacement.calls == 1
    assert db.scalar(select(func.count()).select_from(EvaluationResult)) == 2


def test_changed_provider_fails_before_network_calls(experiment, db):
    database, run, chunk, _ = experiment
    providers = Providers(database, chunk)
    providers.identity = "changed-provider"
    run_once(database, Settings(), query_providers=providers)
    db.refresh(run)
    assert run.status == "failed" and run.error_code == "evaluation_protocol_changed"
    assert providers.calls == 0
