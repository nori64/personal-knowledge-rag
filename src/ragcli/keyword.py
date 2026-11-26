"""キーワード検索（BM25）。日本語の分かち書きは Janome、代替は文字2グラム。"""
import math
import re
from collections import Counter


def tokenize(text: str, mode: str) -> list[str]:
    if mode == "janome":
        try:
            from janome.tokenizer import Tokenizer
        except ImportError as e:
            raise RuntimeError("janome が入っていません。tokenizer を bigram にするか janome を入れてください") from e
        if not hasattr(tokenize, "_t"):
            tokenize._t = Tokenizer()  # type: ignore[attr-defined]
        t = tokenize._t  # type: ignore[attr-defined]
        tokens = []
        for tok in t.tokenize(text):
            pos = tok.part_of_speech.split(",")[0]
            if pos in ("名詞", "動詞", "形容詞", "副詞") or re.fullmatch(r"[0-9A-Za-z]+", tok.surface):
                tokens.append(tok.surface)
        return tokens
    # bigram
    cleaned = re.sub(r"\s+", "", text)
    return [cleaned[i:i + 2] for i in range(len(cleaned) - 1)]


class BM25Index:
    def __init__(self, docs_tokens: list[list[str]]):
        self.docs = docs_tokens
        self.n = len(docs_tokens)
        self.doc_len = [len(d) for d in docs_tokens]
        self.avgdl = (sum(self.doc_len) / self.n) if self.n else 0.0
        self.df: Counter = Counter()
        for d in docs_tokens:
            for term in set(d):
                self.df[term] += 1
        self.tf = [Counter(d) for d in docs_tokens]

    def idf(self, term: str) -> float:
        df = self.df.get(term, 0)
        return math.log(1 + (self.n - df + 0.5) / (df + 0.5))

    def search(self, query_tokens: list[str], top_k: int = 50) -> list[tuple[int, float]]:
        if self.n == 0:
            return []
        k1, b = 1.5, 0.75
        scores: dict[int, float] = {}
        for term in set(query_tokens):
            idf = self.idf(term)
            if idf <= 0:
                continue
            for i in range(self.n):
                f = self.tf[i].get(term, 0)
                if f == 0:
                    continue
                denom = f + k1 * (1 - b + b * self.doc_len[i] / (self.avgdl or 1))
                scores[i] = scores.get(i, 0.0) + idf * (f * (k1 + 1) / denom)
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        return ranked[:top_k]
