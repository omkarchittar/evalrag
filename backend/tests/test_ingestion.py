import hashlib
import json

import httpx
import pytest
from sqlalchemy import func, select
from test_persistence import knowledge_base

from evalrag.documents import DocumentError, extract_pages
from evalrag.ingestion import ingest_document, submit_document
from evalrag.models import Chunk, Document, Job
from evalrag.providers import OpenAIEmbeddingProvider, ProviderError


@pytest.mark.parametrize(
    "filename,data",
    [
        ("file.exe", b"executable"),
        ("file.pdf", b"not a PDF"),
        ("file.txt", b"\x00\x01\xff"),
        ("empty.md", b""),
    ],
)
def test_bad_uploads_are_rejected(filename, data):
    with pytest.raises(DocumentError):
        extract_pages(filename, data)


def test_markdown_preserves_source_text():
    assert extract_pages("policy.md", b"# Security\n\nRetention is 30 days.") == [
        (1, "# Security\n\nRetention is 30 days.")
    ]


def test_text_limit_is_enforced_before_parsing():
    with pytest.raises(DocumentError, match="size"):
        extract_pages("policy.txt", b"a" * 100, max_bytes=99)


def embedding_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_embedding_adapter_records_actual_usage_and_orders_results():
    def handler(request):
        body = json.loads(request.content)
        assert body["model"] == "text-embedding-3-small"
        assert body["dimensions"] == 3
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0, 1, 0]},
                    {"index": 0, "embedding": [1, 0, 0]},
                ],
                "usage": {"prompt_tokens": 8, "total_tokens": 8},
            },
        )

    with embedding_client(handler) as client:
        provider = OpenAIEmbeddingProvider(
            "secret", model="text-embedding-3-small", dimensions=3, client=client
        )
        batch = provider.embed(["alpha", "beta"])
        assert batch.vectors == [[1, 0, 0], [0, 1, 0]]
        assert batch.input_tokens == 8


@pytest.mark.parametrize(
    "payload",
    [
        {"data": [{"index": 0, "embedding": [1, 0]}], "usage": {"prompt_tokens": 1}},
        {"data": [], "usage": {"prompt_tokens": 1}},
        {"data": [{"index": 0, "embedding": [0, 0, 0]}], "usage": {"prompt_tokens": 1}},
        {"data": [{"index": 0, "embedding": [1, 0, 0]}]},
    ],
)
def test_invalid_provider_responses_are_not_indexed(payload):
    with embedding_client(lambda _: httpx.Response(200, json=payload)) as client:
        provider = OpenAIEmbeddingProvider(
            "secret", model="text-embedding-3-small", dimensions=3, client=client
        )
        with pytest.raises(ProviderError) as error:
            provider.embed(["alpha"])
        assert not error.value.retryable


@pytest.mark.parametrize(
    "status,retryable", [(400, False), (401, False), (429, True), (500, True), (503, True)]
)
def test_provider_error_classification_does_not_leak_response_body(status, retryable):
    with embedding_client(lambda _: httpx.Response(status, text="SECRET FROM PROVIDER")) as client:
        provider = OpenAIEmbeddingProvider(
            "secret", model="text-embedding-3-small", dimensions=3, client=client
        )
        with pytest.raises(ProviderError) as error:
            provider.embed(["alpha"])
        assert error.value.retryable == retryable
        assert "SECRET" not in str(error.value)


@pytest.mark.postgres
def test_duplicate_submission_creates_one_document_and_one_job(db):
    kb = knowledge_base(db)
    first = submit_document(db, kb.id, "policy.md", b"The policy is 30 days.")
    second = submit_document(db, kb.id, "renamed.md", b"The policy is 30 days.")
    assert first.id == second.id
    assert first.checksum == hashlib.sha256(b"The policy is 30 days.").hexdigest()
    assert db.scalar(select(func.count()).select_from(Document)) == 1
    assert db.scalar(select(func.count()).select_from(Job)) == 1


@pytest.mark.postgres
def test_ingestion_persists_chunks_and_replay_is_idempotent(db):
    kb = knowledge_base(db)
    kb.embedding_model = "text-embedding-3-small"
    document = submit_document(db, kb.id, "policy.md", b"The policy is 30 days.")

    def handler(request):
        items = json.loads(request.content)["input"]
        return httpx.Response(
            200,
            json={
                "data": [{"index": i, "embedding": [1, 0, 0]} for i in range(len(items))],
                "usage": {"prompt_tokens": 8},
            },
        )

    with embedding_client(handler) as client:
        provider = OpenAIEmbeddingProvider(
            "secret", model=kb.embedding_model, dimensions=3, client=client
        )
        ingest_document(db, document.id, provider=provider)
        ingest_document(db, document.id, provider=provider)
    assert document.status == "ready"
    assert document.chunk_count == 1
    assert db.scalar(select(func.count()).select_from(Chunk)) == 1
    assert document.ingestion_ms >= 0
