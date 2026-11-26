"""設定ファイルの読み込みと検証。"""
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


class ConfigError(Exception):
    pass


@dataclass
class Config:
    document_folders: list[str]
    index_dir: str
    questions_file: str = ""
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedder: str = "sentence-transformers"  # or "hash" (test double)
    tokenizer: str = "janome"  # or "bigram"
    chunk_max_chars: int = 800
    chunk_overlap_chars: int = 80
    rrf_k: int = 60
    candidate_threshold: float = 0.35
    cosine_threshold: float = 0.85
    embed_query_prefix: str = ""
    embed_context: str = "none"  # "none" or "heading"（埋め込み本文に文書名・見出しを付ける）
    default_method: str = "hybrid"
    embed_passage_prefix: str = ""
    source_path: str = ""

    @property
    def base_dir(self) -> Path:
        return Path(self.source_path).resolve().parent if self.source_path else Path.cwd()


def _resolve(cfg: Config, p: str) -> str:
    path = Path(p)
    if not path.is_absolute():
        path = cfg.base_dir / path
    return str(path)


def load_config(path: str) -> Config:
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"設定ファイルがありません: {path}")
    try:
        data = tomllib.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise ConfigError(f"設定ファイルが読めません: {e}") from e
    if "document_folders" not in data or not data["document_folders"]:
        raise ConfigError("設定に document_folders（取り込み対象フォルダ）がありません")
    if "index_dir" not in data:
        raise ConfigError("設定に index_dir（索引の置き場所）がありません")
    cfg = Config(
        document_folders=list(data["document_folders"]),
        index_dir=str(data["index_dir"]),
        questions_file=str(data.get("questions_file", "")),
        embedding_model=str(data.get("embedding_model", "intfloat/multilingual-e5-small")),
        embedder=str(data.get("embedder", "sentence-transformers")),
        tokenizer=str(data.get("tokenizer", "janome")),
        chunk_max_chars=int(data.get("chunk_max_chars", 800)),
        chunk_overlap_chars=int(data.get("chunk_overlap_chars", 80)),
        rrf_k=int(data.get("rrf_k", 60)),
        candidate_threshold=float(data.get("candidate_threshold", 0.35)),
        cosine_threshold=float(data.get("cosine_threshold", 0.85)),
        embed_query_prefix=str(data.get("embed_query_prefix", "")),
        embed_context=str(data.get("embed_context", "none")),
        default_method=str(data.get("default_method", "hybrid")),
        embed_passage_prefix=str(data.get("embed_passage_prefix", "")),
        source_path=str(p),
    )
    cfg.document_folders = [_resolve(cfg, d) for d in cfg.document_folders]
    cfg.index_dir = _resolve(cfg, cfg.index_dir)
    if cfg.questions_file:
        cfg.questions_file = _resolve(cfg, cfg.questions_file)
    return cfg


def find_config(explicit: str | None) -> str:
    """明示指定が無ければ ragcli.local.toml を優先し、無ければ ragcli.toml を使う。"""
    if explicit:
        return explicit
    if Path("ragcli.local.toml").exists():
        return "ragcli.local.toml"
    return "ragcli.toml"
