#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ソースファイルの言語判定と構文解析の入口."""

import os
from pathlib import Path
from typing import Literal

from tree_sitter import Node
from tree_sitter_language_pack import get_parser

from caretta.java_parser import parse_java
from caretta.models import SourceDocument
from caretta.python_parser import parse_python


# 拡張子を確認して適切な構文パーサーを選択する。
def parse_file(path: Path) -> SourceDocument:
    """拡張子に応じてソースファイルを解析する."""
    language_by_suffix: dict[str, Literal["java", "python"]] = {
        ".java": "java",
        ".py": "python",
    }
    language = language_by_suffix.get(path.suffix.lower())
    if language is None:
        raise ValueError(
            f"未対応のファイル形式です: {path.suffix or '(拡張子なし)'}"
        )

    source = path.read_bytes()
    tree = get_parser(language).parse(source)
    if tree.root_node.has_error:
        error_node = _first_error(tree.root_node)
        location = (
            f"{error_node.start_point.row + 1} 行目"
            if error_node
            else "位置不明"
        )
        raise ValueError(f"{path}: 構文エラー ({location})")

    if language == "java":
        return parse_java(path, source, tree.root_node)
    return parse_python(path, source, tree.root_node)


# ファイル単体とディレクトリ入力を共通の解析結果にそろえる。
def parse_path(path: Path) -> list[SourceDocument]:
    """ファイルまたはディレクトリ以下の対応ソースを解析する."""
    if not path.exists():
        raise FileNotFoundError(f"指定されたパスが見つかりません: {path}")
    if path.is_file():
        return [parse_file(path)]

    ignored = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        "build",
        "dist",
    }
    files: list[Path] = []
    for current, directories, names in os.walk(
        path, onerror=_raise_walk_error
    ):
        directories[:] = sorted(
            name for name in directories if name not in ignored
        )
        files.extend(
            Path(current) / name
            for name in names
            if Path(name).suffix.lower() in {".java", ".py"}
        )
    files.sort()
    if not files:
        raise ValueError(
            f"解析対象の Java/Python ファイルがありません: {path}"
        )
    return [parse_file(item) for item in files]


# ディレクトリ走査中のアクセスエラーを呼び出し元へ伝える。
def _raise_walk_error(error: OSError) -> None:
    """ディレクトリ走査エラーを握りつぶさず再送出する."""
    raise error


# 構文木を深さ優先で調べて診断位置を特定する。
def _first_error(node: Node) -> Node | None:
    """構文木から最初のエラーノードを探す."""
    if node.type == "ERROR" or node.is_missing:
        return node
    for child in node.children:
        error = _first_error(child)
        if error is not None:
            return error
    return None
