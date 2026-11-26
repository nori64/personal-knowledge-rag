import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ragcli.config import ConfigError, load_config


class TestConfig(unittest.TestCase):
    def test_missing_file(self):
        with self.assertRaises(ConfigError):
            load_config("/nonexistent/ragcli.toml")

    def test_missing_required_keys(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.toml"
            p.write_text('index_dir = "idx"\n', encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(str(p))

    def test_relative_paths_resolve_from_config_dir(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.toml"
            p.write_text('document_folders = ["docs"]\nindex_dir = "idx"\n',
                         encoding="utf-8")
            cfg = load_config(str(p))
            self.assertEqual(cfg.document_folders, [str(Path(d) / "docs")])
            self.assertEqual(cfg.index_dir, str(Path(d) / "idx"))


if __name__ == "__main__":
    unittest.main()
