from __future__ import annotations

import hashlib
from typing import Any

import numpy as np

from app.config import CHROMA_PATH


def embed_texts(texts: list[str], dim: int = 256) -> list[list[float]]:
    vecs = []
    for text in texts:
        v = np.zeros(dim, dtype=np.float32)
        tokens = (text or "").lower().split()
        if not tokens:
            vecs.append(v.tolist())
            continue
        for tok in tokens:
            h = hashlib.md5(tok.encode("utf-8")).hexdigest()
            idx = int(h, 16) % dim
            sign = 1.0 if int(h[8:10], 16) % 2 == 0 else -1.0
            v[idx] += sign
        n = np.linalg.norm(v)
        if n:
            v = v / n
        vecs.append(v.tolist())
    return vecs


class VectorStore:
    def __init__(self) -> None:
        self._chroma = None
        self._mem: dict[str, dict[str, Any]] = {}
        try:
            import chromadb

            CHROMA_PATH.mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(path=str(CHROMA_PATH))
            self._chroma = client.get_or_create_collection("finint_chunks", metadata={"hnsw:space": "cosine"})
        except Exception:
            self._chroma = None

    def upsert(self, ids: list[str], documents: list[str], metadatas: list[dict[str, Any]]) -> None:
        embeddings = embed_texts(documents)
        if self._chroma is not None:
            try:
                self._chroma.upsert(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)
                return
            except Exception:
                self._chroma = None
        for i, _id in enumerate(ids):
            self._mem[_id] = {"doc": documents[i], "meta": metadatas[i], "emb": np.array(embeddings[i])}

    def query(self, text: str, n: int = 6, where: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        q = np.array(embed_texts([text])[0])
        if self._chroma is not None:
            try:
                kwargs: dict[str, Any] = {"query_embeddings": [q.tolist()], "n_results": n}
                if where:
                    kwargs["where"] = where
                res = self._chroma.query(**kwargs)
                out = []
                docs = (res.get("documents") or [[]])[0]
                metas = (res.get("metadatas") or [[]])[0]
                dists = (res.get("distances") or [[]])[0]
                ids = (res.get("ids") or [[]])[0]
                for i, doc in enumerate(docs):
                    dist = dists[i] if i < len(dists) else 1
                    rel = max(0.0, 1.0 - float(dist))
                    out.append({"id": ids[i], "text": doc, "metadata": metas[i], "relevance": round(rel, 3)})
                return out
            except Exception:
                pass
        scored = []
        for _id, row in self._mem.items():
            if where:
                if any(row["meta"].get(k) != v for k, v in where.items()):
                    continue
            sim = float(np.dot(q, row["emb"]))
            scored.append((sim, _id, row))
        scored.sort(reverse=True)
        return [
            {"id": i, "text": r["doc"], "metadata": r["meta"], "relevance": round(float(s), 3)}
            for s, i, r in scored[:n]
        ]


vector_store = VectorStore()
