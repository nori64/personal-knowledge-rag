import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ragcli.chunker import chunk_sections
from ragcli.parser import Section


class TestChunker(unittest.TestCase):
    def test_heading_becomes_chunk_heading(self):
        secs = [Section(heading="作業場所", text="本文です。")]
        chunks = chunk_sections("文書A", secs)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].heading, "作業場所")
        self.assertEqual(chunks[0].document, "文書A")
        self.assertEqual(chunks[0].position, 1)

    def test_long_section_split_within_max(self):
        text = "\n".join(f"段落{i}。" + "あ" * 90 for i in range(10))
        chunks = chunk_sections("文書A", [Section(heading="H", text=text)],
                                max_chars=300, overlap=30)
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertLessEqual(len(c.text), 300)

    def test_single_long_paragraph_hard_split_overlap(self):
        text = "あ" * 1000
        chunks = chunk_sections("文書A", [Section(heading="H", text=text)],
                                max_chars=300, overlap=50)
        self.assertGreaterEqual(len(chunks), 4)
        # 重なり：次のチャンクの先頭が前のチャンクの末尾と重なる
        self.assertTrue(chunks[1].text.startswith(chunks[0].text[-50:]))

    def test_empty_section_produces_no_chunk(self):
        chunks = chunk_sections("文書A", [Section(heading="H", text="   ")])
        self.assertEqual(chunks, [])


if __name__ == "__main__":
    unittest.main()
