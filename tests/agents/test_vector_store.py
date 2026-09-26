"""
Tests untuk Agents/rag/vector_store.py — VectorStore.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

# Mock sentence_transformers sebelum modul di-import
sys.modules.setdefault("sentence_transformers", MagicMock())

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Agents"))

from rag.vector_store import VectorStore


def _make_store() -> VectorStore:
    """Buat VectorStore baru yang bersih (tidak shared state)."""
    return VectorStore()


# ---------------------------------------------------------------------------
# build_index
# ---------------------------------------------------------------------------

class TestBuildIndex:
    @pytest.mark.asyncio
    async def test_build_from_scratch_when_no_cache(self) -> None:
        """Harus memanggil get_embeddings_batch dan set _ready=True jika tidak ada cache."""
        store = _make_store()
        fake_vectors = [[0.1, 0.2, 0.3]] * 6  # 6 entries di KNOWLEDGE_SEED

        with patch("rag.vector_store.VectorStore._load_cache", return_value=None), \
             patch("rag.vector_store.VectorStore._save_cache"), \
             patch("rag.vector_store.get_embeddings_batch", new=AsyncMock(return_value=fake_vectors)):
            await store.build_index()

        assert store._ready is True
        assert len(store._entries) == 6
        assert store._vectors is not None
        assert store._vectors.shape[0] == 6

    @pytest.mark.asyncio
    async def test_build_index_loads_from_cache(self) -> None:
        """Jika cache tersedia, tidak perlu memanggil API embedding."""
        store = _make_store()
        cached_entries = [{"id": "x", "text": "foo", "known_fix": "bar", "category": "test"}]
        cached_vectors = np.array([[0.5, 0.5, 0.5]], dtype=np.float32)

        with patch("rag.vector_store.VectorStore._load_cache", return_value=(cached_entries, cached_vectors)), \
             patch("rag.vector_store.get_embeddings_batch") as mock_embed:
            await store.build_index()

        mock_embed.assert_not_called()
        assert store._ready is True
        assert store._entries == cached_entries

    @pytest.mark.asyncio
    async def test_build_index_idempotent(self) -> None:
        """build_index kedua kali harus langsung return tanpa rebuild."""
        store = _make_store()
        store._ready = True  # Paksa status ready

        with patch("rag.vector_store.get_embeddings_batch") as mock_embed:
            await store.build_index()

        mock_embed.assert_not_called()

    @pytest.mark.asyncio
    async def test_build_index_handles_all_none_embeddings(self) -> None:
        """Jika semua embedding None, store tidak aktif."""
        store = _make_store()
        none_vectors = [None] * 6

        with patch("rag.vector_store.VectorStore._load_cache", return_value=None), \
             patch("rag.vector_store.get_embeddings_batch", new=AsyncMock(return_value=none_vectors)):
            await store.build_index()

        assert store._ready is False


# ---------------------------------------------------------------------------
# retrieve
# ---------------------------------------------------------------------------

class TestRetrieve:
    def _ready_store(self) -> VectorStore:
        """Buat store yang sudah ready dengan 2 entries."""
        store = _make_store()
        store._entries = [
            {"id": "a", "text": "npm module not found", "known_fix": "npm install", "category": "dep"},
            {"id": "b", "text": "port already in use EADDRINUSE", "known_fix": "npx kill-port 3000", "category": "port"},
        ]
        store._vectors = np.array(
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32
        )
        store._ready = True
        return store

    @pytest.mark.asyncio
    async def test_returns_empty_if_not_ready(self) -> None:
        store = _make_store()
        store._ready = False
        result = await store.retrieve("npm error")
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_if_embedding_fails(self) -> None:
        store = self._ready_store()
        with patch("rag.vector_store.get_embedding", new=AsyncMock(return_value=None)):
            result = await store.retrieve("npm error")
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_top_k_results(self) -> None:
        """Harus mengembalikan entri paling relevan berdasarkan cosine similarity."""
        store = self._ready_store()
        # Query vector yang dekat dengan entry pertama [1,0,0]
        query_vec = [0.99, 0.1, 0.0]

        with patch("rag.vector_store.get_embedding", new=AsyncMock(return_value=query_vec)):
            results = await store.retrieve("npm error", top_k=1)

        assert len(results) == 1
        assert results[0]["id"] == "a"
        assert "similarity_score" in results[0]

    @pytest.mark.asyncio
    async def test_filters_low_similarity(self) -> None:
        """Entry dengan similarity di bawah min_similarity tidak dikembalikan."""
        store = self._ready_store()
        # Query vector orthogonal terhadap semua entries (similarity ≈ 0)
        query_vec = [0.0, 0.0, 1.0]

        with patch("rag.vector_store.get_embedding", new=AsyncMock(return_value=query_vec)):
            results = await store.retrieve("some query", top_k=3, min_similarity=0.5)

        assert results == []


# ---------------------------------------------------------------------------
# _load_cache / _save_cache
# ---------------------------------------------------------------------------

class TestCacheIO:
    def test_load_cache_returns_none_if_file_missing(self, tmp_path: Path) -> None:
        store = _make_store()
        with patch("rag.vector_store.CACHE_PATH", str(tmp_path / "no_file.json")):
            result = store._load_cache()
        assert result is None

    def test_load_cache_returns_none_on_json_error(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "cache.json"
        cache_file.write_text("INVALID JSON")
        store = _make_store()
        with patch("rag.vector_store.CACHE_PATH", str(cache_file)):
            result = store._load_cache()
        assert result is None

    def test_save_and_load_cache_roundtrip(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "cache.json"
        store = _make_store()
        # Isi store dengan data dari KNOWLEDGE_SEED (6 items)
        from rag.knowledge_seed import KNOWLEDGE_SEED
        store._entries = list(KNOWLEDGE_SEED)
        store._vectors = np.array([[float(i), 0.0] for i in range(len(KNOWLEDGE_SEED))], dtype=np.float32)

        with patch("rag.vector_store.CACHE_PATH", str(cache_file)):
            store._save_cache()
            result = store._load_cache()

        assert result is not None
        entries, vectors = result
        assert len(entries) == len(KNOWLEDGE_SEED)
        assert vectors.shape[0] == len(KNOWLEDGE_SEED)
