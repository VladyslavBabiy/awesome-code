import json
import os
from dataclasses import dataclass, asdict

import numpy as np

from awesome_code.indexing.chunker import Chunk


@dataclass
class SearchResult:
    file_path: str
    start_line: int
    end_line: int
    content: str
    score: float
    chunk_type: str


class VectorStore:

    def __init__(self, index_dir: str):
        self._index_dir = index_dir
        self._chunks_path = os.path.join(index_dir, "chunks.json")
        self._vectors_path = os.path.join(index_dir, "vectors.npy")
        self._meta_path = os.path.join(index_dir, "meta.json")

        self._chunks: list[dict] = []
        self._vectors: np.ndarray | None = None
        self._file_hashes: dict[str, str] = {}

    def load(self) -> bool:
        if not os.path.exists(self._chunks_path):
            return False

        with open(self._chunks_path, "r") as f:
            self._chunks = json.load(f)

        if os.path.exists(self._vectors_path):
            self._vectors = np.load(self._vectors_path)

        if os.path.exists(self._meta_path):
            with open(self._meta_path, "r") as f:
                self._file_hashes = json.load(f)

        return True

    def save(self):
        os.makedirs(self._index_dir, exist_ok=True)

        with open(self._chunks_path, "w") as f:
            json.dump(self._chunks, f)

        if self._vectors is not None:
            np.save(self._vectors_path, self._vectors)

        with open(self._meta_path, "w") as f:
            json.dump(self._file_hashes, f)

    def add(self, chunks: list[Chunk], vectors: list[list[float]],
            file_hashes: dict[str, str]):
        new_chunks = [
            {
                "file_path": c.file_path,
                "start_line": c.start_line,
                "end_line": c.end_line,
                "content": c.content[:500],
                "chunk_type": c.chunk_type,
            }
            for c in chunks
        ]
        new_vectors = np.array(vectors, dtype=np.float32)

        self._chunks.extend(new_chunks)

        if self._vectors is not None and len(self._vectors) > 0:
            self._vectors = np.vstack([self._vectors, new_vectors])
        else:
            self._vectors = new_vectors

        self._file_hashes.update(file_hashes)

    def remove_file(self, rel_path: str):
        if not self._chunks:
            return

        keep = [
            i for i, c in enumerate(self._chunks)
            if c["file_path"] != rel_path
        ]

        self._chunks = [self._chunks[i] for i in keep]

        if self._vectors is not None and keep:
            self._vectors = self._vectors[keep]
        elif not keep:
            self._vectors = None

        self._file_hashes.pop(rel_path, None)

    def search(self, query_vector: list[float], top_k: int = 10) -> list[SearchResult]:
        if self._vectors is None or len(self._chunks) == 0:
            return []

        query = np.array(query_vector, dtype=np.float32)
        scores = self._cosine_similarity(query, self._vectors)

        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            score = float(scores[idx])
            if score < 0.1:
                break

            c = self._chunks[idx]
            results.append(SearchResult(
                file_path=c["file_path"],
                start_line=c["start_line"],
                end_line=c["end_line"],
                content=c["content"],
                score=score,
                chunk_type=c["chunk_type"],
            ))

        return results

    def get_file_hashes(self) -> dict[str, str]:
        return dict(self._file_hashes)

    def chunk_count(self) -> int:
        return len(self._chunks)

    @staticmethod
    def _cosine_similarity(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
        query_norm = np.linalg.norm(query)
        if query_norm == 0:
            return np.zeros(len(matrix))

        norms = np.linalg.norm(matrix, axis=1)
        denom = norms * query_norm
        denom = np.where(denom == 0, 1.0, denom)
        return matrix @ query / denom
