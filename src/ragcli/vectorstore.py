"""ベクトルとチャンク情報をファイルで持ち、総当たりで類似度検索する。"""
import json
from pathlib import Path

import numpy as np

from . import INDEX_FORMAT_VERSION
from .chunker import Chunk

VECTORS_FILE = "vectors.npy"
CHUNKS_FILE = "chunks.jsonl"
MANIFEST_FILE = "manifest.json"


class IndexMissingError(Exception):
    pass


class IndexVersionError(Exception):
    pass


def index_paths(index_dir: str) -> dict[str, Path]:
    d = Path(index_dir)
    return {"dir": d, "vectors": d / VECTORS_FILE,
            "chunks": d / CHUNKS_FILE, "manifest": d / MANIFEST_FILE}


def save_index(index_dir: str, chunks: list[Chunk], vectors: np.ndarray,
               manifest: dict) -> None:
    paths = index_paths(index_dir)
    paths["dir"].mkdir(parents=True, exist_ok=True)
    np.save(paths["vectors"], vectors)
    with open(paths["chunks"], "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")
    manifest = dict(manifest)
    manifest["format_version"] = INDEX_FORMAT_VERSION
    with open(paths["manifest"], "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def load_index(index_dir: str, expected_model: str | None = None):
    paths = index_paths(index_dir)
    if not paths["manifest"].exists():
        raise IndexMissingError("索引がありません。先に取り込み（ingest）が必要です")
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    if manifest.get("format_version") != INDEX_FORMAT_VERSION:
        raise IndexVersionError("索引の形式の版が合いません。再取り込みが必要です")
    if expected_model and manifest.get("embedding_model") != expected_model:
        raise IndexVersionError(
            f"索引の埋め込みモデル（{manifest.get('embedding_model')}）と設定（{expected_model}）が合いません。再取り込みが必要です")
    chunks = []
    with open(paths["chunks"], encoding="utf-8") as f:
        for line in f:
            if line.strip():
                chunks.append(Chunk.from_dict(json.loads(line)))
    vectors = np.load(paths["vectors"]) if paths["vectors"].exists() else np.zeros((0, 0), dtype=np.float32)
    return chunks, vectors, manifest


def search_vectors(vectors: np.ndarray, query_vec: np.ndarray,
                   top_k: int = 50) -> list[tuple[int, float]]:
    if vectors.size == 0:
        return []
    sims = vectors @ query_vec  # 埋め込みは正規化済みの前提でコサイン類似度
    order = np.argsort(-sims, kind="stable")[:top_k]
    return [(int(i), float(sims[i])) for i in order if sims[i] > 0]
