"""文書ファイルを、見出しつき段落の列に変換する。"""
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Section:
    heading: str
    text: str


class ParseWarning(Exception):
    pass


def parse_markdown(text: str, doc_name: str) -> list[Section]:
    sections: list[Section] = []
    heading = doc_name
    buf: list[str] = []

    def flush():
        body = "\n".join(buf).strip()
        if body:
            sections.append(Section(heading=heading, text=body))

    for line in text.splitlines():
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            if level <= 3 and line[level:level + 1] in (" ", ""):
                flush()
                buf = []
                heading = line[level:].strip() or doc_name
                continue
        buf.append(line)
    flush()
    return sections


def parse_text(text: str, doc_name: str) -> list[Section]:
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    return [Section(heading=doc_name, text=p) for p in paras]


def parse_pdf(path: Path, doc_name: str) -> list[Section]:
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise ParseWarning("pypdf が入っていないためPDFを読めません") from e
    reader = PdfReader(str(path))
    sections = []
    for i, page in enumerate(reader.pages, start=1):
        body = (page.extract_text() or "").strip()
        if body:
            sections.append(Section(heading=f"{doc_name} p.{i}", text=body))
    return sections


def parse_file(path: Path) -> list[Section]:
    doc_name = path.stem
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(path, doc_name)
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as e:
        raise ParseWarning(f"読めませんでした: {e}") from e
    if suffix in (".md", ".markdown"):
        return parse_markdown(text, doc_name)
    return parse_text(text, doc_name)
