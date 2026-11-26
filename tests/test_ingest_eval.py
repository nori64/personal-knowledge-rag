import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ragcli.config import Config
from ragcli.eval import EvalFormatError, load_questions, run_eval
from ragcli.ingest import run_ingest


def make_cfg(root: Path) -> Config:
    return Config(document_folders=[str(root / "docs")],
                  index_dir=str(root / "idx"),
                  embedding_model="hash-test-double", embedder="hash",
                  tokenizer="bigram", source_path=str(root / "c.toml"))


class TestIngestDiff(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "docs").mkdir()
        (self.root / "docs" / "文書A.md").write_text(
            "# 文書A\n## ルール\n作業は専用パソコンで行う。\n", encoding="utf-8")
        (self.root / "docs" / "文書B.md").write_text(
            "# 文書B\n## 頻度\nバックアップは週に1回取る。\n", encoding="utf-8")
        self.cfg = make_cfg(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_first_and_diff_ingest(self):
        r1 = run_ingest(self.cfg)
        self.assertEqual(r1["documents_added_or_changed"], 2)
        r2 = run_ingest(self.cfg)
        self.assertEqual(r2["documents_added_or_changed"], 0)
        # 変更したら1件だけ差分になる
        (self.root / "docs" / "文書A.md").write_text(
            "# 文書A\n## ルール\n作業は専用タブレットで行う。\n", encoding="utf-8")
        r3 = run_ingest(self.cfg)
        self.assertEqual(r3["documents_added_or_changed"], 1)

    def test_deleted_file_removed_from_index(self):
        run_ingest(self.cfg)
        (self.root / "docs" / "文書B.md").unlink()
        r = run_ingest(self.cfg)
        self.assertEqual(r["documents"], 1)


class TestEval(unittest.TestCase):
    def test_format_error_reports_line(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "q.jsonl"
            p.write_text('{"question": "x"}\n', encoding="utf-8")
            with self.assertRaises(EvalFormatError) as cm:
                load_questions(str(p))
            self.assertIn("1行目", str(cm.exception))

    def test_recall_on_tiny_data(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs").mkdir()
            (root / "docs" / "文書A.md").write_text(
                "# 文書A\n## ルール\n作業は専用パソコンで行う。\n", encoding="utf-8")
            cfg = make_cfg(root)
            run_ingest(cfg)
            q = root / "q.jsonl"
            q.write_text(json.dumps(
                {"question": "作業は専用パソコンで行いますか",
                 "expected_document": "文書A", "expected_heading": "ルール",
                 "unanswerable": False}, ensure_ascii=False) + "\n",
                encoding="utf-8")
            result = run_eval(cfg, str(q), method="keyword")
            self.assertEqual(result["summary"]["recall_at_5"], 1.0)
            self.assertEqual(result["summary"]["citation_accuracy"], 1.0)


if __name__ == "__main__":
    unittest.main()


class TestDocumentNaming(unittest.TestCase):
    def test_nested_same_name_files_are_distinct_documents(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs" / "a").mkdir(parents=True)
            (root / "docs" / "b").mkdir(parents=True)
            (root / "docs" / "a" / "SKILL.md").write_text(
                "# 手順A\n内容A。\n", encoding="utf-8")
            (root / "docs" / "b" / "SKILL.md").write_text(
                "# 手順B\n内容B。\n", encoding="utf-8")
            cfg = make_cfg(root)
            r = run_ingest(cfg)
            self.assertEqual(r["documents"], 2)
            from ragcli.vectorstore import load_index
            chunks, _, _ = load_index(cfg.index_dir)
            names = {c.document for c in chunks}
            self.assertEqual(names, {"a/SKILL", "b/SKILL"})


class TestSearchOutput(unittest.TestCase):
    def test_hit_includes_position(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs").mkdir()
            (root / "docs" / "文書A.md").write_text(
                "# 文書A\n## ルール\n作業は専用パソコンで行う。\n", encoding="utf-8")
            cfg = make_cfg(root)
            run_ingest(cfg)
            from ragcli.search import Searcher
            result = Searcher(cfg).search("作業は専用パソコンで行いますか",
                                          method="keyword")
            self.assertTrue(result["hits"])
            self.assertIn("position", result["hits"][0])
            self.assertIsInstance(result["hits"][0]["position"], int)


class TestEmbedContext(unittest.TestCase):
    def test_context_recorded_and_change_forces_reembed(self):
        import dataclasses
        import numpy as np
        from ragcli.vectorstore import load_index
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs").mkdir()
            (root / "docs" / "文書A.md").write_text(
                "# 文書A\n## ルール\n作業は専用パソコンで行う。\n", encoding="utf-8")
            (root / "docs" / "文書B.md").write_text(
                "# 文書B\n## 頻度\nバックアップは週に1回取る。\n", encoding="utf-8")
            cfg_h = dataclasses.replace(make_cfg(root), embed_context="heading")
            run_ingest(cfg_h)
            _, vec_h, man_h = load_index(cfg_h.index_dir)
            self.assertEqual(man_h.get("embed_context"), "heading")
            # 作り方を変えたら、文書が同じでも全部作り直しになる
            cfg_n = dataclasses.replace(make_cfg(root), embed_context="none")
            r = run_ingest(cfg_n)
            self.assertEqual(r["documents_added_or_changed"], 2)
            _, vec_n, _ = load_index(cfg_n.index_dir)
            self.assertFalse(np.array_equal(vec_h, vec_n))


class TestCliDefaultMethod(unittest.TestCase):
    def test_search_without_method_uses_config_default(self):
        import io
        from contextlib import redirect_stdout
        from ragcli.cli import main
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs").mkdir()
            (root / "docs" / "文書A.md").write_text(
                "# 文書A\n## ルール\n作業は専用パソコンで行う。\n", encoding="utf-8")
            cfg_path = root / "c.toml"
            cfg_path.write_text(
                'document_folders = ["docs"]\n'
                'index_dir = "idx"\n'
                'embedding_model = "hash-test-double"\n'
                'embedder = "hash"\n'
                'tokenizer = "bigram"\n'
                'default_method = "keyword"\n', encoding="utf-8")
            cfg = make_cfg(root)
            run_ingest(cfg)
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["--config", str(cfg_path), "search",
                             "作業は専用パソコンで行いますか"])
            self.assertEqual(code, 0)
            result = json.loads(out.getvalue())
            self.assertEqual(result["hits"][0]["document"], "文書A")


class TestCollectFilesPattern(unittest.TestCase):
    def test_glob_pattern_scopes_files(self):
        from ragcli.ingest import collect_files
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "a").mkdir(); (root / "b").mkdir()
            (root / "a" / "SKILL.md").write_text("# A", encoding="utf-8")
            (root / "a" / "note.md").write_text("# N", encoding="utf-8")
            (root / "b" / "SKILL.md").write_text("# B", encoding="utf-8")
            got = collect_files([str(root / "*" / "SKILL.md")])
            self.assertEqual(len(got), 2)

    def test_document_name_with_pattern(self):
        from ragcli.ingest import document_name_for
        cfg = type("C", (), {"document_folders": ["/x/skills/*/SKILL.md"]})()
        self.assertEqual(
            document_name_for(cfg, Path("/x/skills/abc/SKILL.md")), "abc/SKILL")
