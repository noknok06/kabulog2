"""
Swappable text embeddings for semantic search.

Two backends behind one interface (chosen by ``settings.EMBEDDING_BACKEND``):

- ``local``    — an on-box HF sentence-transformer (default
  ``intfloat/multilingual-e5-base``, 768-dim). Private: nothing leaves the
  machine. Loaded lazily and cached; the first call pays the model load.
- ``fallback`` — a deterministic, dependency-free hash embedding. Same text
  always yields the same vector and texts that share tokens land closer, so the
  pgvector wiring and ranking are verifiable offline. It is NOT semantic — tests
  use it; production uses ``local``.

If the local backend can't load (package missing / download blocked) we degrade
to the fallback rather than crash, so the app keeps working.

e5 note: queries must be prefixed ``"query: "`` and documents ``"passage: "``,
and vectors are L2-normalized (we rank by cosine distance).
"""
from __future__ import annotations

import hashlib
import logging
import math
import re
from functools import lru_cache

from django.conf import settings

logger = logging.getLogger(__name__)

EMBEDDING_DIM = getattr(settings, "EMBEDDING_DIM", 768)

_local_broken = False


# --- Fallback: deterministic feature-hash embedding -------------------------
def _features(text: str) -> list[str]:
    """Tokens used as hashing features. Word tokens plus character bigrams so
    Japanese (no spaces) and ASCII both produce overlap."""
    text = (text or "").lower().strip()
    if not text:
        return []
    words = re.findall(r"\w+", text)
    chars = re.sub(r"\s+", "", text)
    bigrams = [chars[i : i + 2] for i in range(len(chars) - 1)] if len(chars) >= 2 else [chars]
    return words + bigrams


def _hash_embed(text: str) -> list[float]:
    vec = [0.0] * EMBEDDING_DIM
    for feat in _features(text):
        digest = hashlib.md5(feat.encode("utf-8")).digest()  # noqa: S324 (not security)
        h = int.from_bytes(digest[:8], "big")
        vec[h % EMBEDDING_DIM] += 1.0 if (h >> 8) & 1 else -1.0
    norm = math.sqrt(sum(x * x for x in vec))
    if norm:
        vec = [x / norm for x in vec]
    return vec


class _FallbackEmbedder:
    def encode(self, texts: list[str], *, is_query: bool = False) -> list[list[float]]:
        return [_hash_embed(t) for t in texts]


# --- Local: HF sentence-transformer -----------------------------------------
class _LocalEmbedder:
    def __init__(self) -> None:
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # lazy, heavy import

            self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
        return self._model

    def encode(self, texts: list[str], *, is_query: bool = False) -> list[list[float]]:
        prefix = "query: " if is_query else "passage: "
        prepped = [prefix + (t or "") for t in texts]
        arr = self.model.encode(prepped, normalize_embeddings=True)
        return [[float(x) for x in row] for row in arr]


@lru_cache(maxsize=1)
def _local() -> _LocalEmbedder:
    return _LocalEmbedder()


@lru_cache(maxsize=1)
def _fallback() -> _FallbackEmbedder:
    return _FallbackEmbedder()


def _encode(texts: list[str], *, is_query: bool) -> list[list[float]]:
    global _local_broken
    backend = getattr(settings, "EMBEDDING_BACKEND", "local")
    if backend == "local" and not _local_broken:
        try:
            return _local().encode(texts, is_query=is_query)
        except Exception:  # noqa: BLE001 — degrade, don't crash the request
            _local_broken = True
            logger.warning("Local embedding backend unavailable; using fallback.", exc_info=True)
    return _fallback().encode(texts, is_query=is_query)


# --- Public API -------------------------------------------------------------
def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed stored content (passages)."""
    return _encode(list(texts), is_query=False)


def embed_query(text: str) -> list[float]:
    """Embed a search query."""
    return _encode([text], is_query=True)[0]
