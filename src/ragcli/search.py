"""検索：キーワードとベクトルの順位を統合し、外部設計のJSONを組み立てる。"""
import numpy as np

from .embedder import make_embedder
from .keyword import BM25Index, tokenize
from .vectorstore import load_index, search_vectors


def rrf_fuse(rankings: list[list[int]], k: int = 60) -> dict[int, float]:
    """順位の統合（Reciprocal Rank Fusion）。純粋な計算として切り出す。"""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, idx in enumerate(ranking, start=1):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank)
    return scores


def normalize_rrf(scores: dict[int, float], num_lists: int, k: int = 60) -> dict[int, float]:
    """両方で1位だった場合の理論上の最大値で割り、0〜1に収める。"""
    max_score = num_lists / (k + 1)
    if max_score <= 0:
        return dict(scores)
    return {i: min(1.0, s / max_score) for i, s in scores.items()}


def judge_candidate(top_cosine: float | None, top_bm25: float | None,
                    cosine_threshold: float) -> bool:
    """候補あり判定（純粋な計算）。

    統合後の正規化スコアは「何かしら返れば高くなる」ため判定には使わない。
    ベクトルが関わる場合は最上位チャンクのコサイン類似度を主証拠とし、
    ハイブリッドではBM25でも裏付ける（キーワードが全く当たらない質問は
    「答えがない」寄りに倒す）。
    """
    if top_cosine is not None and top_bm25 is not None:
        return top_cosine >= cosine_threshold and top_bm25 > 0
    if top_cosine is not None:
        return top_cosine >= cosine_threshold
    if top_bm25 is not None:
        return top_bm25 > 0
    return False


class Searcher:
    def __init__(self, cfg):
        self.cfg = cfg
        self.chunks, self.vectors, self.manifest = load_index(
            cfg.index_dir, expected_model=cfg.embedding_model)
        self.embedder = make_embedder(cfg)
        tokens = [tokenize(c.text, cfg.tokenizer) for c in self.chunks]
        self.bm25 = BM25Index(tokens)

    def search(self, question: str, top_k: int = 5,
               method: str = "hybrid") -> dict:
        cfg = self.cfg
        rankings: list[list[int]] = []
        kw_scores: dict[int, float] = {}
        vec_scores: dict[int, float] = {}
        if method in ("hybrid", "keyword"):
            qt = tokenize(question, cfg.tokenizer)
            kw = self.bm25.search(qt, top_k=50)
            kw_scores = dict(kw)
            rankings.append([i for i, _ in kw])
        if method in ("hybrid", "vector"):
            qv = self.embedder.embed([question], kind="query")[0]
            vv = search_vectors(self.vectors, qv, top_k=50)
            vec_scores = dict(vv)
            rankings.append([i for i, _ in vv])
        if not rankings:
            raise ValueError(f"未知の検索方式です: {method}")
        fused = rrf_fuse(rankings, k=cfg.rrf_k)
        normed = normalize_rrf(fused, num_lists=len(rankings), k=cfg.rrf_k)
        ordered = sorted(normed.items(), key=lambda kv: (-kv[1], kv[0]))
        hits = []
        for idx, score in ordered[:top_k]:
            c = self.chunks[idx]
            hits.append({"document": c.document, "heading": c.heading,
                         "position": c.position,
                         "text": c.text, "score": round(float(score), 4)})
        has_candidate = False
        if ordered:
            top_idx = ordered[0][0]
            has_candidate = judge_candidate(
                vec_scores.get(top_idx) if method in ("hybrid", "vector") else None,
                kw_scores.get(top_idx, 0.0) if method in ("hybrid", "keyword") else None,
                cfg.cosine_threshold)
        return {
            "question": question,
            "has_answer_candidate": has_candidate,
            "hits": hits,
        }


def format_text(result: dict) -> str:
    lines = [f"質問：{result['question']}"]
    if not result["has_answer_candidate"]:
        lines.append("答えの候補は見つかりませんでした。")
    for h in result["hits"]:
        lines.append(f"- 出典：{h['document']}／{h['heading']}（関連度 {h['score']}）")
        snippet = h["text"].replace("\n", " ")
        lines.append(f"  {snippet[:120]}")
    return "\n".join(lines)
