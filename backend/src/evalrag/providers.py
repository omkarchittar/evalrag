"""Provider boundary: strict payload checks and sanitized, retry-classified failures."""

import math
from dataclasses import dataclass
from typing import Protocol

import httpx


class ProviderError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool = False, usage: dict | None = None):
        super().__init__(code)
        self.code = code
        self.retryable = retryable
        self.usage = usage


@dataclass(frozen=True)
class EmbeddingBatch:
    vectors: list[list[float]]
    input_tokens: int
    model: str
    dimensions: int


class EmbeddingProvider(Protocol):
    model: str
    dimensions: int

    def embed(self, texts: list[str]) -> EmbeddingBatch: ...


class OpenAIEmbeddingProvider:
    SUPPORTED = {"text-embedding-3-small": 1536, "text-embedding-3-large": 3072}

    def __init__(
        self,
        api_key: str,
        *,
        model: str,
        dimensions: int = 1536,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 45,
        client: httpx.Client | None = None,
    ):
        if model not in self.SUPPORTED or not 1 <= dimensions <= self.SUPPORTED[model]:
            raise ValueError("Unsupported embedding model or dimensions")
        if not api_key:
            raise ProviderError("provider_not_configured")
        self.model, self.dimensions = model, dimensions
        self.api_key, self.base_url, self.timeout = api_key, base_url.rstrip("/"), timeout
        self.client = client

    def embed(self, texts: list[str]) -> EmbeddingBatch:
        if not texts or len(texts) > 32 or any(not text.strip() for text in texts):
            raise ValueError("Embedding batches must contain 1–32 nonempty texts")
        payload = {
            "model": self.model,
            "dimensions": self.dimensions,
            "input": texts,
            "encoding_format": "float",
        }
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
        try:
            data = response.json()
            if not isinstance(data, dict) or data.get("model") != self.model:
                raise ValueError("Embedding model mismatch")
            entries = sorted(data["data"], key=lambda item: item["index"])
            if [entry["index"] for entry in entries] != list(range(len(texts))):
                raise ValueError("Invalid embedding indices")
            vectors = [entry["embedding"] for entry in entries]
            for vector in vectors:
                if len(vector) != self.dimensions or any(
                    type(x) not in {int, float} or not math.isfinite(x) for x in vector
                ):
                    raise ValueError("Invalid vector shape or values")
                if not any(vector):
                    raise ValueError("Zero vectors cannot be searched by cosine distance")
            tokens = data["usage"]["prompt_tokens"]
            if type(tokens) is not int or tokens < 0:
                raise ValueError("Invalid usage")
        except (KeyError, ValueError, TypeError) as exc:
            raise ProviderError("invalid_embedding_response") from exc
        return EmbeddingBatch(vectors, tokens, self.model, self.dimensions)

    def _request(self, client: httpx.Client, payload: dict) -> httpx.Response:
        return client.post(
            f"{self.base_url}/embeddings",
            json=payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=self.timeout,
        )
