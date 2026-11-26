"""Markdownの設計文書を、Word（.docx）とExcel（.xlsx）に変換する。

- 要件定義書は Word、設計書は Excel という成果物形式に合わせるための変換器
- 2026-11-26の移行で使った変換器。正本はOffice版へ移行済みで、通常は再実行しない（再実行すると正本を上書きしてしまう）
"""
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent


def parse_blocks(md: str):
    """Markdownを（種類, 内容）のブロック列に分ける。"""
    blocks = []
    lines = md.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            buf = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i]); i += 1
            i += 1
            blocks.append(("code", "\n".join(buf)))
            continue
        if line.strip().startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                rows.append(cells)
                i += 1
                if i < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i].strip()):
                    i += 1  # 区切り行を飛ばす
            blocks.append(("table", rows))
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            blocks.append((f"h{len(m.group(1))}", m.group(2).strip()))
            i += 1
            continue
        if line.startswith("> "):
            blocks.append(("quote", line[2:].strip()))
            i += 1
            continue
        if re.match(r"^\s*-\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\s*-\s+", lines[i]):
                items.append(re.sub(r"^\s*-\s+", "", lines[i]).strip())
                i += 1
            blocks.append(("bullets", items))
            continue
        if re.match(r"^\s*\d+\.\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\s*\d+\.\s+", lines[i]):
                items.append(re.sub(r"^\s*\d+\.\s+", "", lines[i]).strip())
                i += 1
            blocks.append(("numbers", items))
            continue
        if line.strip() in ("---", "***"):
            i += 1
            continue
        if line.strip():
            blocks.append(("p", line.strip()))
        i += 1
    return blocks


def clean(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text


# ---------------- Word ----------------

def add_rich(paragraph, text):
    """**太字** を解釈して段落に足す。"""
    parts = re.split(r"(\*\*.+?\*\*)", text)
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            run = paragraph.add_run(part[2:-2])
            run.bold = True
        elif part:
            paragraph.add_run(re.sub(r"`([^`]+)`", r"\1", part))


def to_docx(md_path: Path, out_path: Path, images: list[tuple[Path, str]]):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt

    blocks = parse_blocks(md_path.read_text(encoding="utf-8"))
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Yu Gothic"
    style.font.size = Pt(10.5)
    images_done = False
    for kind, content in blocks:
        if kind == "h1":
            p = doc.add_heading(clean(content), level=0)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif kind == "h2":
            doc.add_heading(clean(content), level=1)
        elif kind == "h3":
            doc.add_heading(clean(content), level=2)
        elif kind == "h4":
            doc.add_heading(clean(content), level=3)
        elif kind == "quote":
            p = doc.add_paragraph()
            add_rich(p, content)
            p.paragraph_format.left_indent = Cm(0.8)
            if not images_done and images:
                for img, caption in images:
                    doc.add_picture(str(img), width=Cm(15.5))
                    cap = doc.add_paragraph(caption)
                    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                images_done = True
        elif kind == "bullets":
            for item in content:
                p = doc.add_paragraph(style="List Bullet")
                add_rich(p, item)
        elif kind == "numbers":
            for item in content:
                p = doc.add_paragraph(style="List Number")
                add_rich(p, item)
        elif kind == "table":
            table = doc.add_table(rows=len(content), cols=len(content[0]))
            table.style = "Table Grid"
            for r, row in enumerate(content):
                for c, cell in enumerate(row):
                    cell_p = table.cell(r, c).paragraphs[0]
                    add_rich(cell_p, cell)
                    if r == 0:
                        for run in cell_p.runs:
                            run.bold = True
        elif kind == "code":
            p = doc.add_paragraph()
            run = p.add_run(content)
            run.font.name = "Consolas"
            run.font.size = Pt(9)
        else:
            p = doc.add_paragraph()
            add_rich(p, content)
    if images and not images_done:
        doc.add_heading("図", level=1)
        for img, caption in images:
            doc.add_picture(str(img), width=Cm(15.5))
            cap = doc.add_paragraph(caption)
            cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.save(out_path)
    print("wrote", out_path.name)


# ---------------- Excel ----------------

def sheet_name(title: str, used: set) -> str:
    name = re.sub(r'[\\/*?:\[\]]', "", clean(title))[:28] or "章"
    base = name
    n = 2
    while name in used:
        name = f"{base}（{n}）"; n += 1
    used.add(name)
    return name


def to_xlsx(md_path: Path, out_path: Path, title: str,
            images: list[tuple[Path, str]]):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    blocks = parse_blocks(md_path.read_text(encoding="utf-8"))
    wb = Workbook()
    thin = Side(style="thin", color="808080")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    header_fill = PatternFill("solid", fgColor="DCE9F7")
    section_fill = PatternFill("solid", fgColor="FCE8D5")

    # 表紙
    cover = wb.active
    cover.title = "表紙"
    cover.column_dimensions["B"].width = 90
    cover["B2"] = title
    cover["B2"].font = Font(size=16, bold=True)
    row = 4
    for kind, content in blocks:
        if kind == "p" and content.startswith("- "):
            cover.cell(row=row, column=2, value=clean(content[2:]))
            row += 1
        elif kind == "p" and content.startswith("-"):
            cover.cell(row=row, column=2, value=clean(content[1:].strip()))
            row += 1
        if row > 12:
            break
    cover.cell(row=row + 1, column=2, value="変更履歴")
    cover.cell(row=row + 1, column=2).font = Font(bold=True)
    cover.cell(row=row + 2, column=2, value="版は各章の内容とあわせて管理する。正本はMarkdown版とし、本ファイルはその変換版である。")

    # 章ごとにシートを分ける
    used = {"表紙", "図"}
    ws = None
    r = 1

    def new_sheet(name):
        nonlocal ws, r
        ws = wb.create_sheet(sheet_name(name, used))
        ws.column_dimensions["A"].width = 4
        for col, w in zip("BCDEFG", (34, 34, 34, 26, 26, 26)):
            ws.column_dimensions[col].width = w
        ws.sheet_view.showGridLines = False
        r = 1

    for kind, content in blocks:
        if kind == "h1":
            continue
        if kind == "h2":
            new_sheet(content)
            c = ws.cell(row=r, column=2, value=clean(content))
            c.font = Font(size=13, bold=True)
            r += 2
            continue
        if ws is None:
            new_sheet("本文")
        if kind == "h3":
            ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=7)
            c = ws.cell(row=r, column=2, value=clean(content))
            c.font = Font(size=11, bold=True)
            c.fill = section_fill
            r += 1
        elif kind == "h4":
            c = ws.cell(row=r, column=2, value=clean(content))
            c.font = Font(bold=True)
            r += 1
        elif kind == "table":
            ncols = len(content[0])
            for rowdata in content:
                for j, cell in enumerate(rowdata):
                    c = ws.cell(row=r, column=2 + j, value=clean(cell))
                    c.alignment = Alignment(wrap_text=True, vertical="top")
                    c.border = border
                    if content.index(rowdata) == 0:
                        c.fill = header_fill
                        c.font = Font(bold=True)
                r += 1
            r += 1
        elif kind == "bullets":
            for item in content:
                ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=7)
                c = ws.cell(row=r, column=2, value="・" + clean(item))
                c.alignment = Alignment(wrap_text=True, vertical="top")
                r += 1
        elif kind == "numbers":
            for idx, item in enumerate(content, start=1):
                ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=7)
                c = ws.cell(row=r, column=2, value=f"{idx}. " + clean(item))
                c.alignment = Alignment(wrap_text=True, vertical="top")
                r += 1
        elif kind == "code":
            for line in content.split("\n"):
                ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=7)
                c = ws.cell(row=r, column=2, value=line)
                c.font = Font(name="Consolas", size=9)
                r += 1
        elif kind == "quote":
            ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=7)
            c = ws.cell(row=r, column=2, value=clean(content))
            c.font = Font(italic=True)
            c.alignment = Alignment(wrap_text=True, vertical="top")
            r += 2
        else:
            ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=7)
            c = ws.cell(row=r, column=2, value=clean(content))
            c.alignment = Alignment(wrap_text=True, vertical="top")
            r += 1

    if images:
        from openpyxl.drawing.image import Image as XLImage
        ws_img = wb.create_sheet("図")
        ws_img.sheet_view.showGridLines = False
        r = 2
        for img, caption in images:
            ws_img.cell(row=r, column=2, value=caption).font = Font(bold=True)
            r += 1
            xl = XLImage(str(img))
            scale = 880 / xl.width
            xl.width = 880
            xl.height = int(xl.height * scale)
            ws_img.add_image(xl, f"B{r}")
            r += int(xl.height / 15) + 3
    wb.save(out_path)
    print("wrote", out_path.name)


if __name__ == "__main__":
    fig = BASE / "docs" / "figures"
    to_docx(BASE / "docs" / "01_requirements.md",
            BASE / "docs" / "01_要件定義書.docx",
            [(fig / "system_architecture.png", "図1 システム構成図")])
    to_xlsx(BASE / "docs" / "02_外部設計書.md",
            BASE / "docs" / "02_外部設計書.xlsx", "外部設計書 ― 個人用ナレッジRAG",
            [(fig / "system_architecture.png", "図1 システム構成図")])
    to_xlsx(BASE / "docs" / "03_内部設計書.md",
            BASE / "docs" / "03_内部設計書.xlsx", "内部設計書 ― 個人用ナレッジRAG",
            [(fig / "flow_ingest.png", "図1 処理フロー図（取り込み）"),
             (fig / "flow_search.png", "図2 処理フロー図（検索）")])
