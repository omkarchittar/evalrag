from contextlib import contextmanager

import pytest
from sqlalchemy import select
from test_generation import answer_payload
from test_persistence import knowledge_base
from test_retrieval import populate

from evalrag.generation import Completion, GroundedAnswer, ToolCall
from evalrag.models import Membership, QueryTrace
from evalrag.providers import EmbeddingBatch, ProviderError
from evalrag.rag import QueryConfig, ask

pytestmark = pytest.mark.postgres


class Transactions:
    def __init__(self, db):
        self.db = db
        self.active = False

    @contextmanager
    def transaction(self):
        assert not self.active
        self.active = True
        try:
            yield self.db
            self.db.flush()
        finally:
            self.active = False


class Embeddings:
    model = "test-vector"
    dimensions = 3

    def __init__(self, database):
        self.database = database

    def embed(self, texts):
        assert not self.database.active, "Provider IO must release database transaction"
        return EmbeddingBatch([[1, 0, 0]], 7, self.model, self.dimensions)


class Completions:
    model = "gpt-4.1-mini"

    def __init__(self, database, items):
        self.database, self.items = database, iter(items)

    def complete(self, messages, *, tools):
        assert not self.database.active
        item = next(self.items)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def corpus(db, api):
    _, actor, _ = api
    kb = knowledge_base(db)
    doc, chunk = populate(db, kb, [1, 0, 0])
    db.add(Membership(workspace_id=kb.workspace_id, user_id=actor.id, role="viewer"))
    db.flush()
    return Transactions(db), kb, actor, doc, chunk


def final(chunk_id, *, quote="Retention is 30 days."):
    data = answer_payload()
    data["claims"][0]["citations"][0] = {"chunk_id": chunk_id, "quote": quote}
    return Completion(
        "gpt-4.1-mini-2025-04-14", 100, 25, 20, GroundedAnswer.model_validate(data), []
    )


def run(corpus, completions, config=None):
    database, kb, actor, _, _ = corpus
    return ask(
        database,
        kb.id,
        actor_id=actor.id,
        question="What is the retention policy?",
        config=config or QueryConfig(),
        request_id="test-query",
        embedding_factory=lambda _: Embeddings(database),
        generation_factory=lambda _: Completions(database, completions),
    )


def test_grounded_answer_persists_provenance_usage_and_immutable_trace(corpus, db):
    result = run(corpus, [final(corpus[-1].id)])
    assert result.answer == "Retention is 30 days."
    assert not result.abstained and result.error_code is None
    assert result.input_tokens == 107 and result.output_tokens == 25
    assert result.citations[0]["valid"] is True
    assert result.citations[0]["page"] == 2
    assert result.config["usage_complete"] is True
    assert db.get(QueryTrace, result.id) is result
    assert result.cost_usd is None  # unknown test embedding model is never priced as OpenAI


@pytest.mark.parametrize("attack", ["unknown_source", "invented_quote"])
def test_unsupported_claims_are_withheld_and_trace_records_validation(corpus, attack):
    completion = final(
        "outside-kb" if attack == "unknown_source" else corpus[-1].id,
        quote="This is invented" if attack == "invented_quote" else "Retention is 30 days.",
    )
    result = run(corpus, [completion])
    assert result.abstained and result.answer is None
    assert result.error_code == "citation_validation_failed"
    assert result.citations[0]["valid"] is False
    assert result.config["answer_validation"]["citation_correctness"] == 0


def test_tool_loop_executes_only_allowlisted_validated_calls(corpus):
    calculator = Completion(
        "gpt-4.1-mini",
        50,
        10,
        0,
        None,
        [ToolCall("call_1", "calculator", '{"expression":"30 * 2"}')],
    )
    result = run(corpus, [calculator, final(corpus[-1].id)], QueryConfig(agent_mode=True))
    assert result.tool_calls[0]["name"] == "calculator"
    assert result.tool_calls[0]["output"]["result"] == 60
    assert result.tool_calls[0]["status"] == "success"
    assert result.input_tokens == 157 and result.output_tokens == 35


@pytest.mark.parametrize(
    "name,args",
    [
        ("shell", '{"command":"whoami"}'),
        ("calculator", '{"expression":"__import__("os")"}'),
        ("calculator", '{"expression":"1/0"}'),
    ],
)
def test_invalid_tool_calls_return_safe_failures_without_execution(corpus, name, args):
    bad = Completion("gpt-4.1-mini", 50, 10, 0, None, [ToolCall("call_1", name, args)])
    result = run(corpus, [bad, final(corpus[-1].id)], QueryConfig(agent_mode=True))
    assert result.tool_calls[0]["status"] == "error"
    assert result.tool_calls[0]["output"]["error"] in {"unknown_tool", "invalid_tool_arguments"}


def test_search_tool_remains_scoped_and_accumulates_embedding_usage(corpus):
    search = Completion(
        "gpt-4.1-mini",
        50,
        10,
        0,
        None,
        [ToolCall("call_1", "document_search", '{"query":"retention","top_k":3}')],
    )
    result = run(corpus, [search, final(corpus[-1].id)], QueryConfig(agent_mode=True))
    assert result.tool_calls[0]["output"]["sources"][0]["chunk_id"] == corpus[-1].id
    assert result.input_tokens == 164


def test_empty_corpus_abstains_without_generation(corpus, db):
    corpus[-2].status = "processing"
    db.flush()
    result = run(corpus, [])
    assert result.abstained and result.answer is None and result.error_code is None
    assert result.config["abstention_reason"] == "No evidence met the retrieval threshold."


def test_generation_failure_preserves_prior_usage_with_unknown_total_cost(corpus):
    result = run(corpus, [ProviderError("provider_unavailable", retryable=True)])
    assert result.error_code == "provider_unavailable"
    assert result.input_tokens == 7
    assert result.config["usage_complete"] is False
    assert result.cost_usd is None


def test_metadata_tool_cannot_read_foreign_document(corpus, db):
    other = knowledge_base(db)
    doc, _ = populate(db, other, [1, 0, 0])
    tool = Completion(
        "gpt-4.1-mini",
        50,
        10,
        0,
        None,
        [ToolCall("call_1", "metadata_lookup", '{"document_id":"' + doc.id + '"}')],
    )
    result = run(corpus, [tool, final(corpus[-1].id)], QueryConfig(agent_mode=True))
    assert result.tool_calls[0]["output"] == {"error": "document_not_found"}
    assert doc.id not in str(result.retrieved)


def test_agent_stops_after_three_tools_and_a_final_generation(corpus):
    tools = [
        Completion(
            "gpt-4.1-mini",
            50,
            10,
            0,
            None,
            [ToolCall(f"call_{i}", "calculator", '{"expression":"30 * 2"}')],
        )
        for i in range(4)
    ]
    result = run(corpus, tools, QueryConfig(agent_mode=True))
    assert result.error_code == "tool_budget_exceeded"
    assert len(result.tool_calls) == 3
    assert result.answer is None and result.abstained


def test_duplicate_tool_call_id_does_not_execute_twice(corpus):
    tool = Completion(
        "gpt-4.1-mini", 50, 10, 0, None, [ToolCall("same", "calculator", '{"expression":"30 * 2"}')]
    )
    result = run(corpus, [tool, tool], QueryConfig(agent_mode=True))
    assert result.error_code == "duplicate_tool_call"
    assert len(result.tool_calls) == 1


def test_membership_revoked_during_provider_call_prevents_response(corpus, db):
    from evalrag.rag import QueryAccessError

    database, kb, actor, _, chunk = corpus

    class RevokingProvider:
        def complete(self, messages, *, tools):
            membership = db.get(Membership, (kb.workspace_id, actor.id))
            db.delete(membership)
            db.flush()
            return final(chunk.id)

    with pytest.raises(QueryAccessError):
        ask(
            database,
            kb.id,
            actor_id=actor.id,
            question="What is the retention policy?",
            config=QueryConfig(),
            request_id="revoked",
            embedding_factory=lambda _: Embeddings(database),
            generation_factory=lambda _: RevokingProvider(),
        )
    assert db.scalar(select(QueryTrace.id)) is None


def test_context_budget_prevents_citing_retrieved_but_unseen_chunks(corpus, db):
    from evalrag.rag import MAX_CONTEXT_TOKENS

    # Stored metadata must reflect real token counts; using the exact budget boundary
    # here verifies selection rather than embedding/chunking behavior.
    chunk = corpus[-1]
    chunk.token_count = MAX_CONTEXT_TOKENS + 1
    db.flush()
    result = run(corpus, [])
    assert result.abstained
    assert len(result.retrieved) == 1
    assert result.retrieved[0]["included_in_context"] is False


def test_repeated_search_references_existing_context_without_duplicate_content(corpus):
    import json

    database, kb, actor, _, chunk = corpus

    class RepeatingProvider:
        def __init__(self):
            self.step = 0

        def complete(self, messages, *, tools):
            self.step += 1
            assert json.dumps(messages).count("Retention is 30 days.") == 1
            if self.step < 4:
                return Completion(
                    "gpt-4.1-mini",
                    50,
                    10,
                    0,
                    None,
                    [
                        ToolCall(
                            f"repeat_{self.step}",
                            "document_search",
                            '{"query":"retention","top_k":5}',
                        )
                    ],
                )
            return final(chunk.id)

    result = ask(
        database,
        kb.id,
        actor_id=actor.id,
        question="Retention?",
        config=QueryConfig(agent_mode=True),
        request_id="repeat",
        embedding_factory=lambda _: Embeddings(database),
        generation_factory=lambda _: RepeatingProvider(),
    )
    assert not result.abstained
    assert len(result.config["retrievals"]) == 4
    assert all(c["output"]["sources"][0]["already_in_context"] for c in result.tool_calls)


def test_refused_completion_keeps_reported_usage_in_persisted_trace(corpus):
    from test_generation import provider, response_payload

    database, kb, actor, _, _ = corpus
    payload = response_payload()
    payload["choices"][0]["message"]["refusal"] = "refused"
    result = ask(
        database,
        kb.id,
        actor_id=actor.id,
        question="Retention?",
        config=QueryConfig(),
        request_id="refusal",
        embedding_factory=lambda _: Embeddings(database),
        generation_factory=lambda _: provider(payload),
    )
    assert result.error_code == "model_refusal"
    assert result.input_tokens == 107 and result.output_tokens == 25
    assert result.config["usage_complete"] is True
    assert len(result.config["usage"]) == 2
