"""評価：質問セットを一括実行し、集計する。"""
import json
from pathlib import Path

from .search import Searcher


class EvalFormatError(Exception):
    pass


def load_questions(path: str) -> list[dict]:
    questions = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                q = json.loads(line)
            except json.JSONDecodeError as e:
                raise EvalFormatError(f"{lineno}行目：JSONとして読めません（{e}）") from e
            for key in ("question", "expected_document", "expected_heading", "unanswerable"):
                if key not in q:
                    raise EvalFormatError(f"{lineno}行目：項目「{key}」がありません")
            questions.append(q)
    return questions


def run_eval(cfg, questions_path: str, method: str = "hybrid") -> dict:
    questions = load_questions(questions_path)
    searcher = Searcher(cfg)
    known = {(c.document, c.heading) for c in searcher.chunks}
    per_question = []
    answerable = [q for q in questions if not q["unanswerable"]]
    unanswerable = [q for q in questions if q["unanswerable"]]
    recall_hits = 0
    citation_total = 0
    citation_ok = 0
    unans_detected = 0
    unans_false_positive = 0
    ans_flagged_absent = 0
    for q in questions:
        result = searcher.search(q["question"], top_k=5, method=method)
        for h in result["hits"]:
            citation_total += 1
            if (h["document"], h["heading"]) in known:
                citation_ok += 1
        if q["unanswerable"]:
            if result["has_answer_candidate"]:
                unans_false_positive += 1
            else:
                unans_detected += 1
            ok = not result["has_answer_candidate"]
        else:
            if not result["has_answer_candidate"]:
                ans_flagged_absent += 1
            ok = any(h["document"] == q["expected_document"]
                     and h["heading"] == q["expected_heading"]
                     for h in result["hits"])
            if ok:
                recall_hits += 1
        per_question.append({"question": q["question"],
                             "unanswerable": bool(q["unanswerable"]),
                             "ok": bool(ok),
                             "has_answer_candidate": result["has_answer_candidate"],
                             "top_document": result["hits"][0]["document"] if result["hits"] else None})
    summary = {
        "method": method,
        "questions": len(questions),
        "recall_at_5": (recall_hits / len(answerable)) if answerable else None,
        "citation_accuracy": (citation_ok / citation_total) if citation_total else None,
        "unanswerable_detection_rate": (unans_detected / len(unanswerable)) if unanswerable else None,
        "unanswerable_false_positive_rate": (unans_false_positive / len(unanswerable)) if unanswerable else None,
        "answerable_flagged_absent_rate": (ans_flagged_absent / len(answerable)) if answerable else None,
    }
    return {"summary": summary, "per_question": per_question}


def format_summary_table(result: dict) -> str:
    s = result["summary"]
    def pct(v):
        return f"{v * 100:.1f}%" if v is not None else "―"
    return "\n".join([
        f"方式：{s['method']}／質問数：{s['questions']}",
        f"Recall@5：{pct(s['recall_at_5'])}",
        f"出典の正確率：{pct(s['citation_accuracy'])}",
        f"答えなし検出率：{pct(s['unanswerable_detection_rate'])}",
        f"答えなし誤判定率：{pct(s['unanswerable_false_positive_rate'])}",
        f"答えあり誤判定率：{pct(s['answerable_flagged_absent_rate'])}",
    ])
