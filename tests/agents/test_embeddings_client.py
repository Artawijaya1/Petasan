"""
Tests untuk Agents/rag/embeddings_client.py — get_embedding dan get_embeddings_batch.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

# Mock sentence_transformers sebelum modul di-import (agar tidak butuh instalasi)
sys.modules.setdefault("sentence_transformers", MagicMock())

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Agents"))


class TestGetEmbedding:
    """Unit tests untuk get_embedding dengan model di-mock."""

    @pytest.mark.asyncio
    async def test_returns_float_list_for_valid_text(self) -> None:
        """get_embedding harus mengembalikan list of float untuk teks valid."""
        from rag.embeddings_client import get_embedding

        fake_vector = [0.1, 0.2, 0.3]
        with patch("rag.embeddings_client._encode_sync", return_value=[fake_vector]):
            result = await get_embedding("npm install error")

        assert result == fake_vector

    @pytest.mark.asyncio
    async def test_returns_none_on_encode_exception(self) -> None:
        """get_embedding harus mengembalikan None jika encode gagal."""
        from rag.embeddings_client import get_embedding

        with patch("rag.embeddings_client._encode_sync", side_effect=RuntimeError("model error")):
            result = await get_embedding("some text")

        assert result is None

    @pytest.mark.asyncio
    async def test_empty_string_input(self) -> None:
        """get_embedding harus tetap mencoba encode string kosong."""
        from rag.embeddings_client import get_embedding

        fake_vector = [0.0, 0.0, 0.0]
        with patch("rag.embeddings_client._encode_sync", return_value=[fake_vector]):
            result = await get_embedding("")

        assert result == fake_vector


class TestGetEmbeddingsBatch:
    """Unit tests untuk get_embeddings_batch."""

    @pytest.mark.asyncio
    async def test_returns_list_of_vectors(self) -> None:
        """Batch encode harus mengembalikan list vector sesuai jumlah input."""
        from rag.embeddings_client import get_embeddings_batch

        texts = ["error npm", "python crash", "port conflict"]
        fake_vectors = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
        with patch("rag.embeddings_client._encode_sync", return_value=fake_vectors):
            result = await get_embeddings_batch(texts)

        assert result == fake_vectors
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_returns_none_list_on_failure(self) -> None:
        """Jika encode batch gagal, semua item harus None."""
        from rag.embeddings_client import get_embeddings_batch

        texts = ["a", "b", "c"]
        with patch("rag.embeddings_client._encode_sync", side_effect=RuntimeError("crash")):
            result = await get_embeddings_batch(texts)

        assert result == [None, None, None]

    @pytest.mark.asyncio
    async def test_empty_input_list(self) -> None:
        """Batch encode dengan list kosong harus mengembalikan list kosong."""
        from rag.embeddings_client import get_embeddings_batch

        with patch("rag.embeddings_client._encode_sync", return_value=[]):
            result = await get_embeddings_batch([])

        assert result == []
