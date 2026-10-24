#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ソース解析結果を表すデータモデル."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Member:
    """クラスのフィールドまたは変数を表す."""

    name: str
    type_name: str
    description: str
    kind: str
    initializer: str = ""


@dataclass
class Method:
    """メソッドまたはモジュール関数を表す."""

    name: str
    signature: str
    description: str
    references: list[str] = field(default_factory=list)
    implementation: str = ""


@dataclass
class Class:
    """解析したクラスとそのメンバーを表す."""

    name: str
    description: str
    parents: list[str] = field(default_factory=list)
    members: list[Member] = field(default_factory=list)
    methods: list[Method] = field(default_factory=list)


@dataclass
class SourceDocument:
    """1 つのソースファイルの解析結果を表す."""

    path: Path
    language: str
    classes: list[Class] = field(default_factory=list)
    functions: list[Method] = field(default_factory=list)
