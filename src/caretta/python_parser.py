#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tree-sitter の Python 構文木からクラス情報を抽出する."""

import ast
from pathlib import Path

from tree_sitter import Node

from caretta.models import Class, Member, Method, SourceDocument


# モジュール直下のクラスと関数を順に解析結果へ追加する。
def parse_python(path: Path, source: bytes, root: Node) -> SourceDocument:
    """Python ファイルからクラス、変数、メソッドを抽出する."""
    document = SourceDocument(path=path, language="Python")
    for index, node in enumerate(root.children):
        if node.type == "class_definition":
            document.classes.append(
                _parse_class(node, source, root.children, index)
            )
        elif node.type == "function_definition":
            document.functions.append(
                _parse_method(node, source, root.children, index, set())
            )
        elif node.type == "decorated_definition":
            definition = _definition(node)
            if (
                definition is not None
                and definition.type == "class_definition"
            ):
                document.classes.append(
                    _parse_class(node, source, root.children, index)
                )
            elif (
                definition is not None
                and definition.type == "function_definition"
            ):
                document.functions.append(
                    _parse_method(
                        definition, source, root.children, index, set()
                    )
                )
    return document


# クラス本体の変数とメソッドを抽出して参照情報を結び付ける。
def _parse_class(
    node: Node, source: bytes, siblings: list[Node], index: int
) -> Class:
    """Python クラスとその直接のメンバーを解析する."""
    definition = _definition(node) or node
    name_node = definition.child_by_field_name("name")
    body = definition.child_by_field_name("body")
    name = _text(name_node, source) or "Unknown"
    description = _docstring(body, source) or _comment_before(
        siblings, index, source
    )
    parents_node = definition.child_by_field_name("superclasses")
    parents = (
        [_text(child, source) for child in parents_node.named_children]
        if parents_node
        else []
    )
    class_doc = Class(
        name=name,
        description=description,
        parents=[item for item in parents if item],
    )
    if body is None:
        return class_doc

    for child_index, child in enumerate(body.children):
        if child.type in {"assignment", "annotated_assignment"}:
            member = _class_member(child, source, body.children, child_index)
            if member:
                class_doc.members.extend(member)
        elif child.type == "function_definition":
            method = _parse_method(
                child, source, body.children, child_index, set()
            )
            class_doc.methods.append(method)
            class_doc.members.extend(
                _instance_members(child, source, body.children, child_index)
            )
        elif child.type == "decorated_definition":
            method_node = _definition(child)
            if (
                method_node is not None
                and method_node.type == "function_definition"
            ):
                method = _parse_method(
                    method_node, source, body.children, child_index, set()
                )
                class_doc.methods.append(method)
                class_doc.members.extend(
                    _instance_members(
                        method_node, source, body.children, child_index
                    )
                )

    field_names = {member.name for member in class_doc.members}
    for method in class_doc.methods:
        method.references = sorted(set(method.references) & field_names)
    return class_doc


# 関数定義からシグネチャ、説明、メンバー参照を生成する。
def _parse_method(
    node: Node,
    source: bytes,
    siblings: list[Node],
    index: int,
    field_names: set[str],
) -> Method:
    """Python 関数のシグネチャ、説明、実装を抽出する."""
    name = _text(node.child_by_field_name("name"), source) or "unknown"
    body = node.child_by_field_name("body")
    description = _docstring(body, source) or _comment_before(
        siblings, index, source
    )
    parameters = node.child_by_field_name("parameters")
    return_type = node.child_by_field_name("return_type")
    signature = f"def {name}{_text(parameters, source)}"
    if return_type is not None:
        signature += f" -> {_text(return_type, source)}"
    references = _self_references(body, source) if body else []
    return Method(
        name=name,
        signature=signature,
        description=description,
        references=(
            sorted(set(references) & field_names)
            if field_names
            else references
        ),
        implementation=_text(body, source),
    )


# クラス直下の代入式を型と初期値の情報に変換する。
def _class_member(
    node: Node, source: bytes, siblings: list[Node], index: int
) -> list[Member]:
    """クラス直下の代入式をクラス変数として抽出する."""
    left = node.child_by_field_name("left")
    value = node.child_by_field_name("right") or node.child_by_field_name(
        "value"
    )
    annotation = node.child_by_field_name("type")
    if left is None:
        return []
    comment = _comment_before(siblings, index, source)
    return [
        Member(
            name=_text(target, source),
            type_name=_text(annotation, source) or _infer_type(value),
            description=comment,
            kind="クラス変数",
            initializer=_text(value, source),
        )
        for target in _assignment_names(left)
    ]


# self と cls への代入を調べてインスタンス変数を抽出する。
def _instance_members(
    node: Node, source: bytes, siblings: list[Node], index: int
) -> list[Member]:
    """メソッド内の self/cls への代入をインスタンス変数として集める."""
    body = node.child_by_field_name("body")
    if body is None:
        return []
    members: dict[str, Member] = {}
    for current in _walk(body):
        if current.type not in {"assignment", "annotated_assignment"}:
            continue
        target = current.child_by_field_name("left")
        if target is None or target.type != "attribute":
            continue
        owner = target.child_by_field_name("object")
        name_node = target.child_by_field_name("attribute")
        if _text(owner, source) not in {"self", "cls"} or name_node is None:
            continue
        value = current.child_by_field_name(
            "right"
        ) or current.child_by_field_name("value")
        annotation = current.child_by_field_name("type")
        members[_text(name_node, source)] = Member(
            name=_text(name_node, source),
            type_name=_text(annotation, source) or _infer_type(value),
            description=_comment_before(siblings, index, source),
            kind="インスタンス変数",
            initializer=_text(value, source),
        )
    return list(members.values())


# self/cls 属性を走査してメソッドが使うフィールド名を返す。
def _self_references(node: Node | None, source: bytes) -> list[str]:
    """メソッド本体から self/cls 経由で参照する変数名を取得する."""
    if node is None:
        return []
    names: list[str] = []
    for current in _walk(node):
        if current.type != "attribute":
            continue
        owner = current.child_by_field_name("object")
        name = current.child_by_field_name("attribute")
        if _text(owner, source) in {"self", "cls"} and name is not None:
            names.append(_text(name, source))
    return names


# アンパック代入も含めて代入先の識別子を再帰的に列挙する。
def _assignment_names(node: Node) -> list[Node]:
    """単純代入やアンパック代入から変数名ノードを集める."""
    if node.type == "identifier":
        return [node]
    return [
        name
        for child in node.named_children
        for name in _assignment_names(child)
    ]


# デコレータラッパーから本体の定義ノードを特定する。
def _definition(node: Node) -> Node | None:
    """デコレータ付き定義からクラスまたは関数ノードを取り出す."""
    if node.type != "decorated_definition":
        return node
    return next(
        (
            child
            for child in node.named_children
            if child.type in {"class_definition", "function_definition"}
        ),
        None,
    )


# 関数やクラスの先頭文字列リテラルを安全に読み取る。
def _docstring(body: Node | None, source: bytes) -> str:
    """関数またはクラス本体の先頭文字列を docstring として読む."""
    if body is None or not body.named_children:
        return ""
    first = body.named_children[0]
    if first.type != "string":
        return ""
    try:
        value = ast.literal_eval(_text(first, source))
    except (SyntaxError, ValueError):
        return ""
    return value.strip() if isinstance(value, str) else ""


# 定義に隣接するコメントだけを説明文として結合する。
def _comment_before(siblings: list[Node], index: int, source: bytes) -> str:
    """直前に連続する Python コメントを説明文として返す."""
    comments: list[str] = []
    for node in reversed(siblings[:index]):
        if node.type != "comment":
            break
        comments.append(_text(node, source).lstrip("#").strip())
    return "\n".join(reversed(comments))


# Tree-sitter のリテラル種別から基本型を推定する。
def _infer_type(node: Node | None) -> str:
    """値リテラルから明確に判断できる基本型を返す."""
    if node is None:
        return ""
    return {
        "integer": "int",
        "float": "float",
        "string": "str",
        "true": "bool",
        "false": "bool",
        "none": "None",
        "list": "list",
        "dictionary": "dict",
        "set": "set",
        "tuple": "tuple",
    }.get(node.type, "")


# 構文木を深さ優先で走査するための反復子を提供する。
def _walk(node: Node):
    """ノードとすべての子孫ノードを順に返す."""
    yield node
    for child in node.named_children:
        yield from _walk(child)


# 構文ノードのバイト範囲を UTF-8 文字列に変換する。
def _text(node: Node | None, source: bytes) -> str:
    """構文ノードの元ソース文字列を返す."""
    # fmt: off
    return (
        source[node.start_byte:node.end_byte].decode("utf-8").strip()
        if node
        else ""
    )
    # fmt: off
