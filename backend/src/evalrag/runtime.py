"""Construct configured provider boundaries independently of HTTP or workers."""

import hashlib
from urllib.parse import urlsplit, urlunsplit

from evalrag.generation import OpenAIGenerationProvider
from evalrag.providers import OpenAIEmbeddingProvider


def provider_identity(base_url: str) -> str:
    """Opaque endpoint identity; never persist credentials or the raw URL."""
    url = urlsplit(base_url.rstrip("/"))
    authority = url.netloc.rsplit("@", 1)[-1].lower()
    canonical = urlunsplit((url.scheme.lower(), authority, url.path, url.query, ""))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


class QueryProviders:
    def __init__(self, settings):
        self.settings = settings
        self.base_url = settings.openai_base_url
        self.identity = provider_identity(self.base_url)
        self.standard_openai = self.base_url.rstrip("/") == "https://api.openai.com/v1"

    def key(self):
        value = self.settings.openai_api_key
        return value.get_secret_value() if value else ""

    def embedding(self, index):
        return OpenAIEmbeddingProvider(
            self.key(),
            model=index.embedding_model,
            dimensions=index.embedding_dimension,
            base_url=self.base_url,
            timeout=self.settings.provider_timeout_seconds,
        )

    def generation(self, model):
        return OpenAIGenerationProvider(
            self.key(),
            model=model,
            base_url=self.base_url,
            timeout=self.settings.provider_timeout_seconds,
        )
