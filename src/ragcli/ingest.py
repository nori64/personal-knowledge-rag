"""取り込み：文書フォルダ → チャンク → 埋め込み → 索引。差分対応。"""
import hashlib
import json
from pathlib import Path

import numpy as np

from .chunker import chunk_sections
from .embedder import make_embedder
from .parser import ParseWarning, parse_file
from .vectorstore import index_paths, load_index, save_index

SUPPORTED = {".md", ".markdown", ".txt", ".pdf"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect_files(folders: list[str]) -> list[Path]:
    """対象フォルダ（配下すべて）か、globパターン（* ? を含む指定）から集める。

    パターン指定を使うと、フォルダ配下の一部（例：スキルの本体ファイルだけ）を
    対象にできる。コーパスの範囲は検索品質に直結するため、設定で明示する。
    """
    import glob as glob_mod
    files: list[Path] = []
    for folder in folders:
        if any(ch in folder for ch in "*?["):
            for name in sorted(glob_mod.glob(folder, recursive=True)):
                p = Path(name)
                if p.is_file() and p.suffix.lower() in SUPPORTED:
                    files.append(p)
            continue
        d = Path(folder)
        if not d.exists():
            raise FileNotFoundError(f"対象フォルダがありません: {folder}")
        for p in sorted(d.rglob("*")):
            if p.is_file() and p.suffix.lower() in SUPPORTED:
                files.append(p)
    return files


def document_name_for(cfg, path: Path) -> str:
    """文書名は、対象フォルダからの相対パス（拡張子なし）とする。

    フォルダごとに同じ名前のファイル（例：各フォルダの SKILL.md）があっても
    文書として区別できるようにするため。フォルダ直下のファイルは従来どおり
    ファイル名そのものになる。
    """
    for folder in cfg.document_folders:
        d = _base_dir_for(folder)
        try:
            rel = path.relative_to(d)
        except ValueError:
            continue
        return str(rel.with_suffix(""))
    return path.stem


def _base_dir_for(entry: str) -> Path:
    """フォルダ指定ならそのフォルダ、globパターンなら静的な部分のフォルダを返す。"""
    if any(ch in entry for ch in "*?["):
        cut = min(entry.index(ch) for ch in "*?[" if ch in entry)
        static = entry[:cut]
        return Path(static) if static.endswith("/") else Path(static).parent
    return Path(entry)


def run_ingest(cfg) -> dict:
    embedder = make_embedder(cfg)
    model_name = getattr(embedder, "model_name", cfg.embedding_model)
    files = collect_files(cfg.document_folders)

    # 既存の索引があれば差分のために読む（版やモデルが違えば作り直し）
    old_chunks, old_vectors, old_manifest = [], None, {}
    paths = index_paths(cfg.index_dir)
    if paths["manifest"].exists():
        try:
            old_chunks, old_vectors, old_manifest = load_index(cfg.index_dir)
            if old_manifest.get("embedding_model") != model_name:
                old_chunks, old_vectors, old_manifest = [], None, {}
            # 埋め込みの作り方（見出し等を付けるか）が変わったら、古いベクトルは使えない
            if old_manifest.get("embed_context", "none") != cfg.embed_context:
                old_chunks, old_vectors, old_manifest = [], None, {}
        except Exception:
            old_chunks, old_vectors, old_manifest = [], None, {}
    old_files: dict = old_manifest.get("files", {})

    warnings: list[str] = []
    new_manifest_files: dict = {}
    kept_chunks: list = []
    kept_vectors: list = []
    old_by_doc: dict[str, list[int]] = {}
    for i, c in enumerate(old_chunks):
        old_by_doc.setdefault(c.document, []).append(i)

    to_embed_texts: list[str] = []
    to_embed_chunks: list = []
    added_or_changed = 0
    for path in files:
        doc_name = document_name_for(cfg, path)
        rel = str(path)
        digest = _sha256(path)
        new_manifest_files[rel] = {"sha256": digest, "document": doc_name}
        old_info = old_files.get(rel)
        if old_info and old_info.get("sha256") == digest and doc_name in old_by_doc:
            for i in old_by_doc[doc_name]:
                kept_chunks.append(old_chunks[i])
                if old_vectors is not None and len(old_vectors) > i:
                    kept_vectors.append(old_vectors[i])
            continue
        added_or_changed += 1
        try:
            sections = parse_file(path)
        except ParseWarning as e:
            warnings.append(f"{path.name}: {e}")
            continue
        chunks = chunk_sections(doc_name, sections, cfg.chunk_max_chars,
                                cfg.chunk_overlap_chars)
        for c in chunks:
            to_embed_chunks.append(c)
            if cfg.embed_context == "heading":
                to_embed_texts.append(f"{c.document}\n{c.heading}\n{c.text}")
            else:
                to_embed_texts.append(c.text)

    all_chunks = kept_chunks + to_embed_chunks
    vectors_parts = []
    if kept_vectors:
        vectors_parts.append(np.array(kept_vectors, dtype=np.float32))
    if to_embed_texts:
        new_vecs = embedder.embed(to_embed_texts, kind="passage")
        vectors_parts.append(new_vecs)
    vectors = (np.vstack(vectors_parts) if vectors_parts
               else np.zeros((0, 0), dtype=np.float32))

    manifest = {"embedding_model": model_name, "files": new_manifest_files,
                "embed_context": cfg.embed_context}
    save_index(cfg.index_dir, all_chunks, vectors, manifest)
    return {
        "documents": len(new_manifest_files),
        "documents_added_or_changed": added_or_changed,
        "chunks": len(all_chunks),
        "warnings": warnings,
        "embedding_model": model_name,
    }
