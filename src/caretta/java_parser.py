#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tree-sitter の Java 構文木からクラス情報を抽出する."""

import re
from pathlib import Path

from tree_sitter import Node

from caretta.models import Class, Member, Method, SourceDocument

_CLASS_TYPES = {
    "class_declaration",
    "interface_declaration",
    "enum_declaration",
    "record_declaration",
}
_METHOD_TYPES = {"method_declaration", "constructor_declaration"}
_COMMENT_TYPES = {"line_comment", "block_comment"}


# 構文木から Java のクラス宣言を見つけて解析する。
def parse_java(path: Path, source: bytes, root: Node) -> SourceDocument:
    """Java ファイルからクラス、フィールド、メソッドを抽出する."""
    document = SourceDocument(path=path, language="Java")
    nodes = list(_walk(root))
    for node in nodes:
        if node.type in _CLASS_TYPES:
            document.classes.append(_parse_class(node, source))
    return document


# クラス本体を走査してフィールドとメソッドを関連付ける。
def _parse_class(node: Node, source: bytes) -> Class:
    """Java クラス宣言と直接のメンバーを解析する."""
    name = _text(node.child_by_field_name("name"), source) or "Unknown"
    description = _preceding_comment(node, source)
    body = node.child_by_field_name("body")
    parents = _parents(node, source)
    class_doc = Class(name=name, description=description, parents=parents)
    if body is None:
        return class_doc

    for index, child in enumerate(body.named_children):
        if child.type == "field_declaration":
            class_doc.members.extend(
                _parse_field(child, body.named_children, index, source)
            )
        elif child.type in _METHOD_TYPES:
            class_doc.methods.append(
                _parse_method(child, body.named_children, index, source)
            )

    field_names = {member.name for member in class_doc.members}
    for method in class_doc.methods:
        method.references = sorted(set(method.references) & field_names)
    return class_doc


# 複数変数を含むフィールド宣言を個別のメンバーに分ける。
def _parse_field(
    node: Node, siblings: list[Node], index: int, source: bytes
) -> list[Member]:
    """Java フィールド宣言から型、名前、初期値を読み取る."""
    type_name = _text(node.child_by_field_name("type"), source)
    description = _preceding_comment_from(siblings, index, source)
    members: list[Member] = []
    for child in node.named_children:
        if child.type != "variable_declarator":
            continue
        name = _text(child.child_by_field_name("name"), source)
        value = _text(child.child_by_field_name("value"), source)
        members.append(
            Member(
                name=name,
                type_name=type_name,
                description=description,
                kind="フィールド",
                initializer=value,
            )
        )
    return members


# メソッド本体から宣言、説明、使用フィールドを抽出する。
def _parse_method(
    node: Node, siblings: list[Node], index: int, source: bytes
) -> Method:
    """Java メソッドの説明、シグネチャ、参照フィールドを抽出する."""
    name = _text(node.child_by_field_name("name"), source) or "constructor"
    body = node.child_by_field_name("body")
    header_end = body.start_byte if body else node.end_byte
    # fmt:off
    signature = (
        source[node.start_byte:header_end]
        .decode("utf-8")
        .strip()
        .rstrip("{")
        .strip()
    )
    # fmt:on
    references = (
        [
            _text(current, source)
            for current in _walk(body)
            if current.type == "identifier"
        ]
        if body
        else []
    )
    return Method(
        name=name,
        signature=signature,
        description=_preceding_comment_from(siblings, index, source),
        references=references,
        implementation=_text(body, source),
    )


# extends と implements の型名をクラス図用に抽出する。
def _parents(node: Node, source: bytes) -> list[str]:
    """Java の extends/implements 宣言から親型名を取り出す."""
    parent_nodes = [
        child
        for child in node.named_children
        if child.type
        in {"superclass", "super_interfaces", "extends_interfaces"}
    ]
    names: list[str] = []
    for parent in parent_nodes:
        names.extend(_parent_types(parent, source))
    return names


# 継承宣言のキーワードを除き型ノードだけを収集する。
def _parent_types(node: Node, source: bytes) -> list[str]:
    """継承句からクラス図に使う親型名を抽出する."""
    type_nodes = {
        "array_type",
        "generic_type",
        "scoped_type_identifier",
        "type_identifier",
    }
    names: list[str] = []
    for current in _walk(node):
        if current.type not in type_nodes:
            continue
        if current.parent is not None and current.parent.type in type_nodes:
            continue
        names.append(_text(current, source))
    return names


# 宣言の親ノードから直前コメントの位置を求める。
def _preceding_comment(node: Node, source: bytes) -> str:
    """クラス宣言の直前にあるコメントを説明文として返す."""
    parent = node.parent
    if parent is None:
        return ""
    siblings = parent.named_children
    index = next(
        (i for i, child in enumerate(siblings) if child.id == node.id), -1
    )
    return _preceding_comment_from(siblings, index, source)


# 直前コメント群から JavaDoc の装飾を除いて説明を作る。
def _preceding_comment_from(
    siblings: list[Node], index: int, source: bytes
) -> str:
    """直前に連続する JavaDoc またはコメントを整形して返す."""
    comments: list[str] = []
    for sibling in reversed(siblings[:index]):
        if sibling.type not in _COMMENT_TYPES:
            break
        text = _text(sibling, source)
        text = re.sub(
            r"^/\*\*?|\*/$|^//", "", text.strip(), flags=re.MULTILINE
        )
        text = re.sub(r"(?m)^\s*\* ?", "", text)
        comments.append(text.strip())
    return "\n".join(reversed(comments))


# 構文木の全ノードを深さ優先で順番に返す。
def _walk(node: Node):
    """ノードとすべての子孫ノードを順に返す."""
    yield node
    for child in node.named_children:
        yield from _walk(child)


# ノード範囲から元の Java コードを取り出す。
def _text(node: Node | None, source: bytes) -> str:
    """構文ノードの元ソース文字列を返す."""
    # fmt:off
    return (
        source[node.start_byte:node.end_byte].decode("utf-8").strip()
        if node
        else ""
    )
    # fmt:on
