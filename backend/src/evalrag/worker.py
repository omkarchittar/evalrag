"""Durable ingestion worker. Run separately from the API with python -m evalrag.worker."""

import argparse
import json
import logging
import signal
import threading
from contextlib import contextmanager

from sqlalchemy import select

from evalrag.config import Settings
from evalrag.db import Database
from evalrag.ingestion import build_index, commit_index, index_input
from evalrag.jobs import LeaseLost, assert_owned, claim, complete, fail, heartbeat
from evalrag.models import Document, Job
from evalrag.providers import OpenAIEmbeddingProvider, ProviderError

logger = logging.getLogger("evalrag.worker")


@contextmanager
def keep_lease(database, lease):
    stopped = threading.Event()

    def renew():
        while not stopped.wait(30):
            try:
                with database.transaction() as db:
                    heartbeat(db, lease)
            except Exception:
                # Final ownership check remains the authority; never commit a stale result.
                logger.warning(json.dumps({"event": "heartbeat_failed", "job_id": lease.id}))
                return

    thread = threading.Thread(target=renew, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stopped.set()
        thread.join(timeout=2)


def reconcile_failures(database):
    with database.transaction() as db:
        rows = db.execute(
            select(Document, Job.last_error_code)
            .join(Job, Job.resource_id == Document.id)
            .where(
                Job.kind == "ingest_document",
                Job.status == "failed",
                Document.status.in_(["queued", "processing"]),
            )
            .with_for_update(of=Document, skip_locked=True)
            .limit(100)
        ).all()
        for document, code in rows:
            document.status = "failed"
            document.error_code = code or "worker_failed"


def run_once(database: Database, settings: Settings, *, embedding_factory=None) -> bool:
    with database.transaction() as db:
        lease = claim(db)
    reconcile_failures(database)
    if lease is None:
        return False
    try:
        if lease.kind != "ingest_document":
            raise ValueError("Unsupported job kind")
        with database.transaction() as db:
            assert_owned(db, lease)
            document = db.get(Document, lease.resource_id)
            if document is None:
                raise ValueError("Document no longer exists")
            if document.status == "ready":
                complete(db, lease)
                return True
            document.status = "processing"
            source = index_input(db, document.id)
        with keep_lease(database, lease):
            if embedding_factory is not None:
                provider = embedding_factory(source)
            else:
                key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
                provider = OpenAIEmbeddingProvider(
                    key,
                    model=source.embedding_model,
                    dimensions=source.embedding_dimension,
                    base_url=settings.openai_base_url,
                    timeout=settings.provider_timeout_seconds,
                )
            prepared = build_index(source, provider)
        with database.transaction() as db:
            assert_owned(db, lease)
            commit_index(db, prepared)
            complete(db, lease)
        logger.info(json.dumps({"event": "job_completed", "job_id": lease.id, "kind": lease.kind}))
    except LeaseLost:
        logger.warning(json.dumps({"event": "lease_lost", "job_id": lease.id}))
    except Exception as exc:
        code = (
            exc.code
            if isinstance(exc, ProviderError)
            else "invalid_document"
            if isinstance(exc, ValueError)
            else "worker_failed"
        )
        retryable = isinstance(exc, ProviderError) and exc.retryable
        try:
            with database.transaction() as db:
                status = fail(db, lease, code=code, retryable=retryable)
                row = db.get(Document, lease.resource_id)
                if row and row.status != "ready":
                    row.status = status
                    row.error_code = code
        except LeaseLost:
            logger.warning(json.dumps({"event": "lease_lost", "job_id": lease.id}))
        logger.warning(
            json.dumps(
                {"event": "job_failed", "job_id": lease.id, "code": code, "retryable": retryable}
            )
        )
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = Settings()
    database = Database(settings.database_url)
    stop = threading.Event()
    for signum in [signal.SIGTERM, signal.SIGINT]:
        signal.signal(signum, lambda *_: stop.set())
    try:
        while not stop.is_set():
            worked = run_once(database, settings)
            if args.once:
                break
            if not worked:
                stop.wait(settings.worker_poll_seconds)
    finally:
        database.close()


if __name__ == "__main__":
    main()
