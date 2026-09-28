import json

import httpx
import pytest

from evalrag.generation import OpenAIGenerationProvider
from evalrag.providers import ProviderError


def answer_payload():
    return {
        "abstained": False,
        "reason": None,
        "claims": [
            {
                "text": "Retention is 30 days.",
                "citations": [{"chunk_id": "source-1", "quote": "Retention is 30 days."}],
            }
        ],
    }


def response_payload(answer=None, tool=None):
    message = {"content": json.dumps(answer or answer_payload())}
    if tool:
        message = {
            "content": None,
            "tool_calls": [{"id": "call_1", "type": "function", "function": tool}],
        }
    return {
        "model": "gpt-4.1-mini-2025-04-14",
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 25,
            "prompt_tokens_details": {"cached_tokens": 20},
        },
        "choices": [{"finish_reason": "tool_calls" if tool else "stop", "message": message}],
    }


def provider(payload, *, status=200):
    def handler(request):
        body = json.loads(request.content)
        assert body["response_format"]["json_schema"]["strict"] is True
        if "tools" in body:
            assert body["parallel_tool_calls"] is False
            assert all(t["function"]["strict"] for t in body["tools"])
        return httpx.Response(status, json=payload)

    return OpenAIGenerationProvider(
        "test", model="gpt-4.1-mini", client=httpx.Client(transport=httpx.MockTransport(handler))
    )


def test_structured_answer_records_actual_model_and_usage():
    result = provider(response_payload()).complete(
        [{"role": "user", "content": "Retention?"}], tools=False
    )
    assert result.answer.claims[0].text == "Retention is 30 days."
    assert result.model == "gpt-4.1-mini-2025-04-14"
    assert (result.input_tokens, result.output_tokens, result.cached_tokens) == (100, 25, 20)


def test_function_call_preserves_safe_transport_for_dispatch():
    result = provider(
        response_payload(tool={"name": "calculator", "arguments": '{"expression":"30 * 2"}'})
    ).complete([], tools=True)
    assert result.tool_calls[0].name == "calculator"
    assert result.assistant_message()["tool_calls"][0]["id"] == "call_1"


@pytest.mark.parametrize(
    "mutation",
    [
        "identity",
        "usage",
        "refusal",
        "truncation",
        "schema",
        "uncited",
        "inconsistent",
        "parallel",
        "hidden_tool",
    ],
)
def test_invalid_provider_payloads_fail_closed(mutation):
    payload = response_payload()
    if mutation == "identity":
        payload["model"] = "gpt-4.1-mini-other-model"
    if mutation == "usage":
        payload["usage"]["prompt_tokens"] = True
    if mutation == "refusal":
        payload["choices"][0]["message"]["refusal"] = "Cannot answer"
    if mutation == "truncation":
        payload["choices"][0]["finish_reason"] = "length"
    if mutation == "schema":
        payload["choices"][0]["message"]["content"] = '{"answer":"made up"}'
    if mutation == "uncited":
        answer = answer_payload()
        answer["claims"][0]["citations"] = []
        payload["choices"][0]["message"]["content"] = json.dumps(answer)
    if mutation == "inconsistent":
        answer = answer_payload()
        answer["abstained"] = True
        payload["choices"][0]["message"]["content"] = json.dumps(answer)
    if mutation in {"parallel", "hidden_tool"}:
        payload = response_payload(tool={"name": "calculator", "arguments": "{}"})
        if mutation == "parallel":
            payload["choices"][0]["message"]["tool_calls"] *= 2
        else:
            payload["choices"][0]["finish_reason"] = "stop"
    with pytest.raises(ProviderError):
        provider(payload).complete([], tools=True)


def test_provider_failure_sanitized_and_retry_classified():
    with pytest.raises(ProviderError) as error:
        provider({"secret": "private prompt"}, status=429).complete([], tools=False)
    assert error.value.retryable
    assert "private" not in str(error.value)


@pytest.mark.parametrize("mutation", ["null_details", "list_message", "null_message", "list_usage"])
def test_malformed_nested_provider_objects_raise_sanitized_boundary_error(mutation):
    payload = response_payload()
    if mutation == "null_details":
        payload["usage"]["prompt_tokens_details"] = None
    if mutation == "list_message":
        payload["choices"][0]["message"] = []
    if mutation == "null_message":
        payload["choices"][0]["message"] = None
    if mutation == "list_usage":
        payload["usage"] = []
    with pytest.raises(ProviderError):
        provider(payload).complete([], tools=False)


@pytest.mark.parametrize("failure", ["refusal", "truncation", "schema"])
def test_rejected_completion_preserves_validated_billing_usage(failure):
    payload = response_payload()
    if failure == "refusal":
        payload["choices"][0]["message"]["refusal"] = "refused"
    if failure == "truncation":
        payload["choices"][0]["finish_reason"] = "length"
    if failure == "schema":
        payload["choices"][0]["message"]["content"] = "{}"
    with pytest.raises(ProviderError) as error:
        provider(payload).complete([], tools=False)
    assert error.value.usage == {
        "kind": "generation",
        "model": "gpt-4.1-mini-2025-04-14",
        "input_tokens": 100,
        "output_tokens": 25,
        "cached_tokens": 20,
    }


def test_protocol_disconnect_is_a_sanitized_retryable_provider_failure():
    def disconnect(request):
        raise httpx.RemoteProtocolError("private transport message")

    model = OpenAIGenerationProvider(
        "test", model="gpt-4.1-mini", client=httpx.Client(transport=httpx.MockTransport(disconnect))
    )
    with pytest.raises(ProviderError) as error:
        model.complete([], tools=False)
    assert error.value.code == "provider_unavailable" and error.value.retryable
    assert "private" not in str(error.value)
