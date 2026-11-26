import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ragcli.search import normalize_rrf, rrf_fuse


class TestFusion(unittest.TestCase):
    def test_rrf_hand_computed(self):
        # 両リストで1位の要素は 1/61 + 1/61
        scores = rrf_fuse([[10, 20], [10, 30]], k=60)
        self.assertAlmostEqual(scores[10], 2 / 61, places=9)
        self.assertAlmostEqual(scores[20], 1 / 62, places=9)
        self.assertAlmostEqual(scores[30], 1 / 62, places=9)

    def test_normalize_top_is_one(self):
        scores = rrf_fuse([[10, 20], [10, 30]], k=60)
        normed = normalize_rrf(scores, num_lists=2, k=60)
        self.assertAlmostEqual(normed[10], 1.0, places=9)
        for v in normed.values():
            self.assertGreaterEqual(v, 0.0)
            self.assertLessEqual(v, 1.0)

    def test_normalize_single_list(self):
        scores = rrf_fuse([[5, 6]], k=60)
        normed = normalize_rrf(scores, num_lists=1, k=60)
        self.assertAlmostEqual(normed[5], 1.0, places=9)


if __name__ == "__main__":
    unittest.main()


class TestJudgeCandidate(unittest.TestCase):
    def test_hybrid_needs_cosine_and_keyword(self):
        from ragcli.search import judge_candidate
        self.assertTrue(judge_candidate(0.90, 3.0, 0.85))
        self.assertFalse(judge_candidate(0.90, 0.0, 0.85))   # キーワード裏付けなし
        self.assertFalse(judge_candidate(0.80, 3.0, 0.85))   # 意味が遠い

    def test_single_methods(self):
        from ragcli.search import judge_candidate
        self.assertTrue(judge_candidate(0.90, None, 0.85))
        self.assertFalse(judge_candidate(0.80, None, 0.85))
        self.assertTrue(judge_candidate(None, 1.5, 0.85))
        self.assertFalse(judge_candidate(None, 0.0, 0.85))
        self.assertFalse(judge_candidate(None, None, 0.85))
