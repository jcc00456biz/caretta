#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解析結果を Markdown と Mermaid の文書に整形する."""

from collections.abc import Sequence

from caretta.models import Class, Method, SourceDocument


# クラス図を先に置き、各ソースファイルの詳細を続けて出力する。
def render_markdown(documents: Sequence[SourceDocument]) -> str:
    """複数の解析結果を 1 つの Markdown 文書に変換する."""
    lines = ["# Caretta ソースコード解説", ""]
    lines.extend(["## クラス図", "", "```mermaid", "classDiagram"])
    for document in documents:
        for class_doc in document.classes:
            lines.append(f"    class {class_doc.name} {{")

            # メンバ変数（属性）の追加
            for member in class_doc.members:
                type_str = member.type_name or "unknown"
                lines.append(f"        {member.name} : {type_str}")

            # メソッドの追加
            for method in class_doc.methods:
                lines.append(f"        {method.name}()")

            lines.append("    }")

            # 継承関係の追加
            for parent in class_doc.parents:
                lines.append(f"    {parent} <|-- {class_doc.name}")

    lines.extend(["```", ""])

    for document in documents:
        lines.extend([f"## {document.path.name} ({document.language})", ""])
        if not document.classes:
            lines.extend(["クラス宣言はありません。", ""])
        for class_doc in document.classes:
            lines.extend(_render_class(class_doc))
        if document.functions:
            lines.extend(["### モジュール関数", ""])
            for function in document.functions:
                lines.extend(_render_method(function, "####"))
    return "\n".join(lines).rstrip() + "\n"


# クラスの概要、変数一覧、メソッド詳細の見出しを組み立てる。
def _render_class(class_doc: Class) -> list[str]:
    """クラスの説明、変数、メソッド情報を Markdown にする."""
    lines = [f"### class {class_doc.name}", ""]
    lines.extend([class_doc.description or "説明コメントはありません。", ""])
    if class_doc.parents:
        lines.extend([f"**継承・実装:** {', '.join(class_doc.parents)}", ""])
    lines.extend(["#### クラス変数・フィールド", ""])
    if class_doc.members:
        lines.extend(
            ["| 名前 | 区分 | 型 | 初期値 | 説明 |", "|---|---|---|---|---|"]
        )
        for member in class_doc.members:
            lines.append(
                f"| {_cell(member.name)} | {_cell(member.kind)} | "
                "{_cell(member.type_name or '不明')} "
                f"| {_cell(member.initializer or 'なし')} | "
                "{_cell(member.description or '説明コメントはありません。')} |"
            )
    else:
        lines.append("変数・フィールドはありません。")
    lines.extend(["", "#### クラスメソッド", ""])
    if class_doc.methods:
        for method in class_doc.methods:
            lines.extend(_render_method(method, "#####"))
    else:
        lines.append("メソッドはありません。")
    return lines + [""]


# メソッドの説明と参照フィールド、実装コードを出力する。
def _render_method(method: Method, heading: str) -> list[str]:
    """メソッドの説明、参照変数、実装コードを Markdown にする."""
    lines = [
        f"{heading} `{method.name}`",
        "",
        f"```text\n{method.signature}\n```",
        "",
    ]
    lines.extend([method.description or "説明コメントはありません。", ""])
    references = ", ".join(f"`{name}`" for name in method.references) or "なし"
    lines.extend([f"**参照するメンバー変数:** {references}", ""])
    if method.implementation:
        lines.extend(
            [
                "**処理実装:**",
                "",
                f"```text\n{_limit(method.implementation)}\n```",
                "",
            ]
        )
    return lines


# Markdown 表の列構造を壊さないよう改行と縦棒を処理する。
def _cell(value: str) -> str:
    """表セル内の改行と縦棒を Markdown 用にエスケープする."""
    return (
        value.replace("|", r"\|").replace("\r\n", "<br>").replace("\n", "<br>")
    )


# 文書が過度に大きくならないよう実装コードを制限する。
def _limit(value: str, limit: int = 3000) -> str:
    """長い実装の表示を指定文字数で切り詰める."""
    return value if len(value) <= limit else value[:limit] + "\n... (省略)"
