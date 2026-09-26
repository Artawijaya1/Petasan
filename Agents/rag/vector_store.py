from __future__ import annotations

import asyncio
import json
import logging
import os

import numpy as np

from rag.embeddings_client import get_embeddings_batch, get_embedding
from rag.knowledge_seed import KNOWLEDGE_SEED

logger = logging.getLogger("vector_store")

# Cache embedding ke disk supaya tidak perlu re-compute tiap kali server restart
CACHE_PATH = os.path.join(os.path.dirname(__file__), "_embedding_cache.json")


class VectorStore:
    def __init__(self) -> None:
        self._entries: list[dict] = []
        self._vectors: np.ndarray | None = None
        self._ready = False
        self._lock = asyncio.Lock()

    async def build_index(self) -> None:
        """
        Membangun index embedding dari KNOWLEDGE_SEED.
        Dipanggil sekali saat startup (lihat main.py / agent_cli.py).
        Menggunakan cache disk supaya tidak boros komputasi tiap restart.
        """
        async with self._lock:
            if self._ready:
                return

            cached = self._load_cache()
            if cached is not None:
                self._entries, self._vectors = cached
                self._ready = True
                logger.info("Vector store dimuat dari cache (%d entries).", len(self._entries))
                return

            texts = [entry["text"] for entry in KNOWLEDGE_SEED]
            embeddings = await get_embeddings_batch(texts)

            valid_entries = []
            valid_vectors = []
            for entry, emb in zip(KNOWLEDGE_SEED, embeddings):
                if emb is not None:
                    valid_entries.append(entry)
                    valid_vectors.append(emb)

            if not valid_vectors:
                logger.error("Tidak ada embedding yang berhasil dibuat. RAG tidak akan aktif.")
                self._ready = False
                return

            self._entries = valid_entries
            self._vectors = np.array(valid_vectors, dtype=np.float32)
            self._ready = True

            self._save_cache()
            logger.info("Vector store berhasil dibangun (%d entries).", len(self._entries))

    def _load_cache(self) -> tuple[list[dict], np.ndarray] | None:
        if not os.path.exists(CACHE_PATH):
            return None
        try:
            with open(CACHE_PATH, "r") as f:
                data = json.load(f)
            if len(data["entries"]) != len(KNOWLEDGE_SEED):
                logger.info("Cache tidak sinkron dengan seed terbaru, membangun ulang.")
                return None
            vectors = np.array(data["vectors"], dtype=np.float32)
            return data["entries"], vectors
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            logger.warning("Gagal memuat cache embedding: %s", exc)
            return None

    def _save_cache(self) -> None:
        try:
            with open(CACHE_PATH, "w") as f:
                json.dump(
                    {"entries": self._entries, "vectors": self._vectors.tolist()},
                    f,
                )
        except OSError as exc:
            logger.warning("Gagal menyimpan cache embedding: %s", exc)

    async def retrieve(self, query: str, top_k: int = 3, min_similarity: float = 0.3) -> list[dict]:
        """
        Mencari entry knowledge base paling relevan dengan query (misal stderr log).
        Mengembalikan list kosong kalau vector store belum siap atau tidak ada
        hasil yang cukup mirip (di bawah min_similarity).
        """
        if not self._ready or self._vectors is None:
            logger.warning("Vector store belum siap, retrieval dilewati.")
            return []

        query_embedding = await get_embedding(query)
        if query_embedding is None:
            return []

        query_vec = np.array(query_embedding, dtype=np.float32)

        norms = np.linalg.norm(self._vectors, axis=1) * np.linalg.norm(query_vec)
        norms[norms == 0] = 1e-10  # cegah pembagian nol
        similarities = np.dot(self._vectors, query_vec) / norms

        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for idx in top_indices:
            score = float(similarities[idx])
            if score >= min_similarity:
                entry = dict(self._entries[idx])
                entry["similarity_score"] = score
                results.append(entry)

        return results


vector_store = VectorStore()