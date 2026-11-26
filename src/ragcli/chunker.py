"""見出し単位を基本に、長さ上限でチャンクに切る。出典情報を付ける。"""
from dataclasses import dataclass

from .parser import Section


@dataclass
class Chunk:
    document: str
    heading: str
    text: str
    position: int  # 文書内の通し番号

    def to_dict(self) -> dict:
        return {"document": self.document, "heading": self.heading,
                "text": self.text, "position": self.position}

    @staticmethod
    def from_dict(d: dict) -> "Chunk":
        return Chunk(document=d["document"], heading=d["heading"],
                     text=d["text"], position=int(d["position"]))


def _split_long(text: str, max_chars: int, overlap: int) -> list[str]:
    """段落境界を優先して上限以下に分ける。1段落が上限を超えたら文字で切る。"""
    paras = [p.strip() for p in text.split("\n") if p.strip()]
    pieces: list[str] = []
    cur = ""
    for para in paras:
        if len(para) > max_chars:
            if cur:
                pieces.append(cur)
                cur = ""
            start = 0
            while start < len(para):
                end = min(start + max_chars, len(para))
                pieces.append(para[start:end])
                if end >= len(para):
                    break
                start = end - overlap
            continue
        candidate = f"{cur}\n{para}" if cur else para
        if len(candidate) <= max_chars:
            cur = candidate
        else:
            if cur:
                pieces.append(cur)
            cur = para
    if cur:
        pieces.append(cur)
    return pieces


def chunk_sections(document: str, sections: list[Section],
                   max_chars: int = 800, overlap: int = 80) -> list[Chunk]:
    chunks: list[Chunk] = []
    pos = 0
    for sec in sections:
        for piece in _split_long(sec.text, max_chars, overlap):
            pos += 1
            chunks.append(Chunk(document=document, heading=sec.heading,
                                text=piece, position=pos))
    return chunks
