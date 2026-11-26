"""コマンドラインの入口。終了コードへの変換を担う。

終了コード：0 正常／2 使い方の誤り／3 索引がない・版が合わない／4 実行失敗
"""
import argparse
import json
import sys

from .config import ConfigError, find_config, load_config
from .embedder import EmbedderError
from .eval import EvalFormatError, format_summary_table, run_eval
from .ingest import run_ingest
from .search import Searcher, format_text
from .vectorstore import IndexMissingError, IndexVersionError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ragcli", description="個人用ナレッジRAG")
    parser.add_argument("--config", default=None, help="設定ファイルのパス")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("ingest", help="文書を取り込んで索引を作る")

    p_search = sub.add_parser("search", help="質問で検索する")
    p_search.add_argument("question", help="質問文")
    p_search.add_argument("--top-k", type=int, default=5)
    p_search.add_argument("--method", default=None,
                          choices=["hybrid", "keyword", "vector"])
    p_search.add_argument("--format", default="json", choices=["json", "text"])

    p_eval = sub.add_parser("eval", help="質問セットで評価する")
    p_eval.add_argument("--method", default="hybrid",
                        choices=["hybrid", "keyword", "vector"])
    p_eval.add_argument("--questions", default=None, help="質問セットのパス")
    p_eval.add_argument("--format", default="json", choices=["json", "text"])

    args = parser.parse_args(argv)
    try:
        cfg = load_config(find_config(args.config))
        if args.command == "ingest":
            report = run_ingest(cfg)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
        if args.command == "search":
            searcher = Searcher(cfg)
            result = searcher.search(args.question, top_k=args.top_k,
                                     method=args.method or cfg.default_method)
            if args.format == "text":
                print(format_text(result))
            else:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "eval":
            qpath = args.questions or cfg.questions_file
            if not qpath:
                print("質問セットの場所が決まっていません（--questions か設定の questions_file）",
                      file=sys.stderr)
                return 2
            result = run_eval(cfg, qpath, method=args.method)
            if args.format == "text":
                print(format_summary_table(result))
            else:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
    except ConfigError as e:
        print(f"設定の誤り：{e}", file=sys.stderr)
        return 2
    except FileNotFoundError as e:
        print(f"使い方の誤り：{e}", file=sys.stderr)
        return 2
    except (IndexMissingError, IndexVersionError) as e:
        print(str(e), file=sys.stderr)
        return 3
    except (EmbedderError, EvalFormatError, RuntimeError, ValueError) as e:
        print(f"実行失敗：{e}", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
