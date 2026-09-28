import json

import httpx
import pytest

from evalrag.generation import OpenAIGenerationProvider
from evalrag.models import QueryTrace
from evalrag.providers import EmbeddingBatch
from evalrag.semantic_evaluation import evaluate_semantics


class Embeddings:
    model = "text-embedding-3-small"
    dimensions = 3

    def embed(self, texts):
        return EmbeddingBatch([[1, 0, 0], [0.8, 0.6, 0]], 12, self.model, self.dimensions)


def trace():
    return QueryTrace(
        answer="Retention is 30 days.",
        abstained=False,
        error_code=None,
        config={
            "claims": [
                {
                    "text": "Retention is 30 days.",
                    "citations": [{"chunk_id": "c", "quote": "Retention is 30 days."}],
                }
            ]
        },
        retrieved=[
            {"chunk_id": "c", "content": "Retention is 30 days.", "included_in_context": True}
        ],
        citations=[
            {"valid": True, "claim_index": 0, "chunk_id": "c", "quote": "Retention is 30 days."}
        ],
        question="Retention?",
    )


def judge(values):
    def handler(request):
        body = json.loads(request.content)
        assert body["response_format"]["json_schema"]["name"] == "rag_judgement"
        return httpx.Response(
            200,
            json={
                "model": "gpt-4.1-mini",
                "usage": {"prompt_tokens": 100, "completion_tokens": 20},
                "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(values)}}],
            },
        )

    return OpenAIGenerationProvider(
        "test", model="gpt-4.1-mini", client=httpx.Client(transport=httpx.MockTransport(handler))
    )


def test_semantic_metrics_are_actual_embedding_and_validated_judge_outputs():
    result = evaluate_semantics(
        trace(),
        {"expected_answer": "30 days"},
        embedding_provider=Embeddings(),
        judge_provider=judge(
            {
                "claim_support": [True],
                "citation_support": [False],
                "answer_relevance": 0.8,
                "explanation": "Claim supported; cited excerpt is insufficient.",
            }
        ),
    )
    assert result["semantic_similarity"] == pytest.approx(0.8)
    assert result["groundedness"] == 1 and result["unsupported_claim_rate"] == 0
    assert result["citation_correctness"] == 0 and result["answer_relevance"] == 0.8
    assert len(result["evaluator_usage"]) == 2
    assert result["evaluation_error"] is None


def test_judge_cannot_omit_claims_and_receive_a_perfect_score():
    result = evaluate_semantics(
        trace(),
        {"expected_answer": "30 days"},
        embedding_provider=Embeddings(),
        judge_provider=judge(
            {
                "claim_support": [],
                "citation_support": [],
                "answer_relevance": 1.0,
                "explanation": "omitted",
            }
        ),
    )
    assert result["evaluation_error"] == "invalid_judgement_alignment"
    assert result["groundedness"] is None
    assert result["semantic_similarity"] == pytest.approx(0.8)


def test_abstention_does_not_fabricate_semantic_perfection():
    item = trace()
    item.answer = None
    item.abstained = True
    result = evaluate_semantics(
        item, {"expected_answer": None}, embedding_provider=None, judge_provider=None
    )
    assert result["groundedness"] is None
    assert result["evaluator_usage"] == []
