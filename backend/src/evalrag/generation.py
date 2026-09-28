"""Strict structured answers and bounded function calls at the provider boundary."""

import json
import re
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from evalrag.providers import ProviderError


class Structured(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Citation(Structured):
    chunk_id: str = Field(min_length=1, max_length=100)
    quote: str = Field(min_length=1, max_length=4000)


class Claim(Structured):
    text: str = Field(min_length=1, max_length=4000)
    citations: list[Citation] = Field(min_length=1, max_length=8)


class GroundedAnswer(Structured):
    abstained: bool
    reason: str | None = Field(max_length=1000)
    claims: list[Claim] = Field(max_length=20)

    @model_validator(mode="after")
    def consistent(self):
        if self.abstained and (self.claims or not self.reason or not self.reason.strip()):
            raise ValueError("Abstention requires a reason and no claims")
        if not self.abstained and (not self.claims or self.reason is not None):
            raise ValueError("An answer requires cited claims and no abstention reason")
        if any(not c.text.strip() for c in self.claims):
            raise ValueError("Claims cannot be blank")
        return self


class SearchArguments(Structured):
    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(ge=1, le=20)


class CalculateArguments(Structured):
    expression: str = Field(min_length=1, max_length=256)


class MetadataArguments(Structured):
    document_id: str = Field(min_length=1, max_length=100)


TOOL_ARGUMENTS = {
    "document_search": SearchArguments,
    "calculator": CalculateArguments,
    "metadata_lookup": MetadataArguments,
}
TOOL_DESCRIPTIONS = {
    "document_search": "Search this knowledge base for additional document evidence. No other knowledge bases are accessible.",
    "calculator": "Evaluate bounded numeric arithmetic only. Cite document evidence for the input numbers in the final answer.",
    "metadata_lookup": "Read filename, checksum, page/chunk counts and ingestion metadata for a document in this knowledge base.",
}


def tool_definitions():
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": TOOL_DESCRIPTIONS[name],
                "strict": True,
                "parameters": schema.model_json_schema(),
            },
        }
        for name, schema in TOOL_ARGUMENTS.items()
    ]


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class Completion:
    model: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    answer: BaseModel | None
    tool_calls: list[ToolCall]

    def assistant_message(self):
        if self.tool_calls:
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {"name": c.name, "arguments": c.arguments},
                    }
                    for c in self.tool_calls
                ],
            }
        return {"role": "assistant", "content": self.answer.model_dump_json()}


class OpenAIGenerationProvider:
    def __init__(
        self,
        api_key: str,
        *,
        model: str,
        base_url="https://api.openai.com/v1",
        timeout: float = 45,
        client: httpx.Client | None = None,
    ):
        if not api_key:
            raise ProviderError("provider_not_configured")
        self.api_key, self.model = api_key, model
        self.base_url, self.timeout, self.client = base_url.rstrip("/"), timeout, client

    def complete(
        self,
        messages: list[dict],
        *,
        tools: bool,
        response_schema: type[BaseModel] = GroundedAnswer,
        schema_name: str = "grounded_answer",
    ) -> Completion:
        if len(json.dumps(messages)) > 1_000_000:
            raise ProviderError("context_budget_exceeded")
        payload = {
            "model": self.model,
            "messages": messages,
            "max_completion_tokens": 4096,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": response_schema.model_json_schema(),
                },
            },
        }
        if tools:
            payload.update(tools=tool_definitions(), tool_choice="auto", parallel_tool_calls=False)
        try:
            if self.client is None:
                with httpx.Client() as client:
                    response = self._request(client, payload)
            else:
                response = self._request(self.client, payload)
        except httpx.TransportError as exc:
            raise ProviderError("provider_unavailable", retryable=True) from exc
        if not response.is_success:
            raise ProviderError(
                f"provider_http_{response.status_code}",
                retryable=response.status_code in {408, 409, 429} or response.status_code >= 500,
            )
        observed_usage = None
        try:
            data = response.json()
            actual = data["model"]
            if actual != self.model and not re.fullmatch(
                re.escape(self.model) + r"-\d{4}-\d{2}-\d{2}", actual
            ):
                raise ValueError("Model identity mismatch")
            usage = data["usage"]
            input_tokens, output_tokens = usage["prompt_tokens"], usage["completion_tokens"]
            details = usage.get("prompt_tokens_details", {})
            if not isinstance(details, dict):
                raise ValueError("Invalid usage detail object")
            cached = details.get("cached_tokens", 0)
            if (
                any(type(n) is not int or n < 0 for n in [input_tokens, output_tokens, cached])
                or cached > input_tokens
            ):
                raise ValueError("Invalid usage")
            observed_usage = {
                "kind": "generation",
                "model": actual,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cached_tokens": cached,
            }
            if len(data["choices"]) != 1:
                raise ValueError("Expected one completion")
            choice = data["choices"][0]
            message = choice["message"]
            if not isinstance(message, dict):
                raise ValueError("Invalid message object")
            if message.get("refusal"):
                raise ProviderError("model_refusal")
            calls = []
            answer = None
            if choice["finish_reason"] == "tool_calls":
                entries = message["tool_calls"]
                if not tools or len(entries) != 1:
                    raise ValueError("Unexpected function calls")
                for item in entries:
                    if item["type"] != "function" or not re.fullmatch(
                        r"[A-Za-z0-9_-]{1,100}", item["id"]
                    ):
                        raise ValueError("Invalid tool call identity")
                    name, args = item["function"]["name"], item["function"]["arguments"]
                    if (
                        not isinstance(name, str)
                        or len(name) > 100
                        or not isinstance(args, str)
                        or len(args) > 8192
                    ):
                        raise ValueError("Unbounded tool call")
                    calls.append(ToolCall(item["id"], name, args))
            elif choice["finish_reason"] == "stop":
                if message.get("tool_calls"):
                    raise ValueError("Unexpected tool payload")
                answer = response_schema.model_validate_json(message["content"])
            else:
                raise ProviderError("incomplete_generation")
        except ProviderError as exc:
            exc.usage = observed_usage
            raise
        except (
            KeyError,
            IndexError,
            TypeError,
            ValueError,
            ValidationError,
            AttributeError,
        ) as exc:
            raise ProviderError("invalid_generation_response", usage=observed_usage) from exc
        return Completion(actual, input_tokens, output_tokens, cached, answer, calls)

    def _request(self, client, payload):
        return client.post(
            self.base_url + "/chat/completions",
            json=payload,
            headers={"Authorization": "Bearer " + self.api_key},
            timeout=self.timeout,
        )
