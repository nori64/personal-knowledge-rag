"""テキストをベクトルに変える。実装は差し替え可能にする。"""
import hashlib

import numpy as np


class EmbedderError(Exception):
    pass


class SentenceTransformerEmbedder:
    """sentence-transformers による実装（初版の本命）。"""

    def __init__(self, model_name: str, query_prefix: str = "",
                 passage_prefix: str = ""):
        self.model_name = model_name
        self.query_prefix = query_prefix
        self.passage_prefix = passage_prefix
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as e:
                raise EmbedderError("sentence-transformers が入っていません") from e
            try:
                self._model = SentenceTransformer(self.model_name)
            except Exception as e:
                raise EmbedderError(f"埋め込みモデルを読み込めませんでした: {e}") from e
        return self._model

    def embed(self, texts: list[str], kind: str = "passage") -> np.ndarray:
        # モデルによっては、質問と本文で決まった接頭辞を付ける約束がある
        # （例：e5系は query: / passage: 。bge-m3 は付けない）。
        # 接頭辞は設定で切り替え、モデル名とは独立に扱う。
        prefix = self.query_prefix if kind == "query" else self.passage_prefix
        if prefix:
            texts = [prefix + t for t in texts]
        model = self._load()
        vecs = model.encode(texts, normalize_embeddings=True,
                            show_progress_bar=False)
        return np.asarray(vecs, dtype=np.float32)


class HashEmbedder:
    """テスト用の代役。意味は持たない決定的なベクトルを返す。

    単体テストと配線確認専用であり、意味検索の品質は表さない。
    """

    def __init__(self, dim: int = 256):
        self.model_name = "hash-test-double"
        self.dim = dim

    def embed(self, texts: list[str], kind: str = "passage") -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            for n in (2, 3):
                for j in range(len(text) - n + 1):
                    gram = text[j:j + n]
                    h = int(hashlib.sha256(gram.encode("utf-8")).hexdigest(), 16)
                    out[i, h % self.dim] += 1.0
            norm = np.linalg.norm(out[i])
            if norm > 0:
                out[i] /= norm
        return out


def make_embedder(cfg) -> object:
    if cfg.embedder == "hash":
        return HashEmbedder()
    return SentenceTransformerEmbedder(
        cfg.embedding_model,
        query_prefix=getattr(cfg, "embed_query_prefix", ""),
        passage_prefix=getattr(cfg, "embed_passage_prefix", ""))
