import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ragcli.parser import parse_markdown, parse_text


class TestParser(unittest.TestCase):
    def test_markdown_headings(self):
        md = "# タイトル\n導入文。\n## 見出し1\n内容1。\n## 見出し2\n内容2。\n"
        secs = parse_markdown(md, "文書")
        headings = [s.heading for s in secs]
        self.assertEqual(headings, ["タイトル", "見出し1", "見出し2"])
        self.assertEqual(secs[1].text, "内容1。")

    def test_markdown_without_heading_uses_doc_name(self):
        secs = parse_markdown("ただの本文。", "文書X")
        self.assertEqual(secs[0].heading, "文書X")

    def test_text_paragraphs(self):
        secs = parse_text("段落1。\n\n段落2。", "文書Y")
        self.assertEqual(len(secs), 2)
        self.assertEqual(secs[0].heading, "文書Y")


if __name__ == "__main__":
    unittest.main()
