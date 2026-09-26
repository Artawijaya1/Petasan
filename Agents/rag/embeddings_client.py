from __future__ import annotations

import asyncio
import logging

from sentence_transformers import SentenceTransformer

logger = logging.getLogger("embeddings_client")

# Model kecil, cepat, jalan baik di CPU. Didownload otomatis sekali saat
# pertama kali dipakai (disimpan di cache lokal ~/.cache/huggingface),
# setelah itu tidak perlu internet lagi.
_MODEL_NAME = "all-MiniLM-L6-v2"
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info("Memuat model embedding lokal (unduhan pertama kali bisa memakan waktu)...")
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def _encode_sync(texts: list[str]) -> list[list[float]]:
    """Fungsi sinkron (CPU-bound) — dijalankan lewat asyncio.to_thread."""
    model = _get_model()
    embeddings = model.encode(texts, convert_to_numpy=True)
    return embeddings.tolist()


async def get_embedding(text: str) -> list[float] | None:
    """
    Mengubah teks menjadi vector embedding secara LOKAL,
    tanpa API key atau koneksi internet (setelah model terdownload).
    """
    try:
        result = await asyncio.to_thread(_encode_sync, [text])
        return result[0]
    except Exception as exc:  # noqa: BLE001
        logger.error("Gagal membuat embedding lokal: %s", exc)
        return None


async def get_embeddings_batch(texts: list[str]) -> list[list[float] | None]:
    """Versi batch — lebih efisien untuk build index awal (banyak teks sekaligus)."""
    try:
        results = await asyncio.to_thread(_encode_sync, texts)
        return results
    except Exception as exc:  # noqa: BLE001
        logger.error("Gagal membuat batch embeddings lokal: %s", exc)
        return [None] * len(texts)