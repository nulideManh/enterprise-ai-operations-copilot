import hashlib
import math
import re

from openai import AsyncOpenAI

from app.core.config import get_settings


settings = get_settings()
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")


def _local_embedding(text: str, dimensions: int) -> list[float]:
    vector = [0.0] * dimensions
    tokens = TOKEN_PATTERN.findall(text.lower()) or [text.lower()]
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1 if digest[4] % 2 == 0 else -1
        vector[index] += sign * (1.0 + min(len(token), 24) / 24)

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


async def embed_text(text: str) -> tuple[list[float], str]:
    if settings.local_embedding_base_url and settings.local_embedding_model:
        try:
            client = AsyncOpenAI(
                api_key=settings.local_llm_api_key,
                base_url=settings.local_embedding_base_url.rstrip("/"),
            )
            response = await client.embeddings.create(
                model=settings.local_embedding_model,
                input=text,
                dimensions=settings.embedding_dimensions,
            )
            return response.data[0].embedding, settings.local_embedding_model
        except Exception:
            pass

    if settings.openai_api_key:
        try:
            client = AsyncOpenAI(api_key=settings.openai_api_key)
            response = await client.embeddings.create(
                model=settings.embedding_model,
                input=text,
                dimensions=settings.embedding_dimensions,
            )
            return response.data[0].embedding, settings.embedding_model
        except Exception:
            pass
    return _local_embedding(text, settings.embedding_dimensions), "local-hash-embedding"
