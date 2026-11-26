"""MCPサーバー：検索コアを `search_knowledge` ツールとして公開する（第2段階）。

MCP側に検索ロジックは持たず、search モジュールをそのまま呼ぶ。
通信は標準入出力（stdio）。設定ファイルは引数 --config か、
環境変数 RAGCLI_CONFIG で指定する（無ければ ragcli.local.toml →
ragcli.toml の順に探す）。
"""
import argparse
import json
import os
import sys

from mcp.server.mcpserver import MCPServer

from .config import find_config, load_config
from .search import Searcher

mcp = MCPServer("personal-knowledge-rag")

_searcher: Searcher | None = None


def _get_searcher() -> Searcher:
    global _searcher
    if _searcher is None:
        config_path = os.environ.get("RAGCLI_CONFIG") or find_config(None)
        cfg = load_config(config_path)
        _searcher = Searcher(cfg)
    return _searcher


@mcp.tool()
def search_knowledge(question: str, top_k: int = 5) -> str:
    """個人の文書セットを検索し、出典つきのチャンクをJSONで返す。

    答えの候補がない場合は has_answer_candidate が false になる。
    その場合は、返ってきた内容を根拠に答えを作らないこと。
    """
    searcher = _get_searcher()
    result = searcher.search(question, top_k=top_k,
                             method=searcher.cfg.default_method)
    return json.dumps(result, ensure_ascii=False)


def main() -> int:
    parser = argparse.ArgumentParser(prog="ragcli-mcp")
    parser.add_argument("--config", default=None)
    args = parser.parse_args()
    if args.config:
        os.environ["RAGCLI_CONFIG"] = args.config
    mcp.run(transport="stdio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
