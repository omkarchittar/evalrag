"""Token-bounded chunking with page provenance and Unicode-safe boundaries."""

import re
from dataclasses import dataclass
from functools import lru_cache

import tiktoken


@lru_cache(maxsize=1)
def tokenizer():
    return tiktoken.get_encoding("cl100k_base")


@dataclass(frozen=True)
class TextChunk:
    content: str
    page: int
    ordinal: int
    token_count: int


def chunk_pages(
    pages: list[tuple[int, str]], *, size: int = 400, overlap: int = 60, strategy: str = "recursive"
) -> list[TextChunk]:
    if not 8 <= size <= 8192 or not 0 <= overlap < size:
        raise ValueError("Chunk size must be 8–8192 tokens and overlap in [0, size)")
    if strategy not in {"fixed", "recursive"}:
        raise ValueError("Unknown chunking strategy")
    encoding = tokenizer()
    result = []
    for page, text in pages:
        tokens = encoding.encode(text, disallowed_special=())
        # A token can contain a partial UTF-8 codepoint. Only cut at valid UTF-8 boundaries.
        parts = [encoding.decode_single_token_bytes(token) for token in tokens]
        raw = b"".join(parts)
        offsets = [0]
        for part in parts:
            offsets.append(offsets[-1] + len(part))
        safe = {
            i
            for i, offset in enumerate(offsets)
            if offset == len(raw) or raw[offset] & 0xC0 != 0x80
        }
        start = 0
        while start < len(tokens):
            end = min(start + size, len(tokens))
            while end not in safe:
                end -= 1
            if end <= start:
                raise ValueError("Chunk size cannot contain a complete Unicode character")
            content = raw[offsets[start] : offsets[end]].decode("utf-8")
            if strategy == "recursive" and end < len(tokens):
                # Prefer a paragraph/sentence boundary in the latter half, keeping
                # actual token boundaries and a deterministic overlap.
                breaks = [m.end() for m in re.finditer(r"\n\s*\n|[.!?]\s+", content)]
                for cut in reversed(breaks):
                    if cut < len(content) // 2:
                        break
                    byte_cut = offsets[start] + len(content[:cut].encode())
                    possible = [
                        i for i in range(start + 1, end + 1) if offsets[i] <= byte_cut and i in safe
                    ]
                    if possible and possible[-1] - start > overlap:
                        end = possible[-1]
                        content = raw[offsets[start] : offsets[end]].decode("utf-8")
                        break
            content = content.strip()
            if content:
                count = len(encoding.encode(content, disallowed_special=()))
                result.append(TextChunk(content, page, len(result), count))
            if end == len(tokens):
                break
            next_start = max(start + 1, end - overlap)
            while next_start not in safe:
                next_start += 1
            start = next_start
    return result
