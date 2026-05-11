import logging
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


async def _embed_one(client: httpx.AsyncClient, text: str) -> list[float]:
    """Embed a single text, truncating by words if it exceeds the model context."""
    words = text.split()
    while words:
        resp = await client.post(
            f"{settings.ollama_base_url}/api/embed",
            json={"model": settings.ollama_embedding_model, "input": [" ".join(words)]},
        )
        if resp.status_code == 400 and "context length" in resp.text:
            words = words[: int(len(words) * 0.75)]
            logger.warning("[EMBED] truncating to %d words due to context limit", len(words))
            continue
        resp.raise_for_status()
        return resp.json()["embeddings"][0]
    raise ValueError("Text could not be embedded even after truncation")


async def embed_texts(texts: list[str], is_query: bool = False) -> list[list[float]]:
    if not texts:
        return []
    async with httpx.AsyncClient(timeout=60.0) as client:
        results = []
        for text in texts:
            # nomic-embed-text is an asymmetric model:
            # queries need the "search_query:" prefix, documents do not.
            prefixed = f"search_query: {text.strip()}" if is_query else (text.strip() or " ")
            results.append(await _embed_one(client, prefixed))
        logger.debug("[EMBED] %d texts is_query=%s dim=%d", len(results), is_query, len(results[0]) if results else 0)
        return results


async def embed_text(text: str, is_query: bool = False) -> list[float]:
    return (await embed_texts([text], is_query=is_query))[0]


def embed_texts_sync(texts: list[str]) -> list[list[float]]:
    """Sync wrapper — for use inside background tasks (asyncio.run)."""
    import asyncio
    return asyncio.run(embed_texts(texts))
