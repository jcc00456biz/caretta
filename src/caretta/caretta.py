#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""caretta コマンドラインアプリケーション."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from caretta.markdown import render_markdown
from caretta.parser import parse_path


# 引数を処理し、解析結果を指定された UTF-8 Markdown ファイルへ保存する。
def main(argv: Sequence[str] | None = None) -> int:
    """CLI 引数を検証し、解析したソースの Markdown を出力する."""
    parser = argparse.ArgumentParser(
        prog="caretta",
        description="Java/Python ソースから解説 Markdown と Mermaid クラス図を生成します。",
    )
    parser.add_argument(
        "path", type=Path, help="解析するソースファイルまたはディレクトリ"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("documentation.md"),
        help="出力 Markdown ファイル (既定: documentation.md)",
    )
    args = parser.parse_args(argv)

    try:
        documents = parse_path(args.path)
        if (
            args.path.is_file()
            and args.path.resolve() == args.output.resolve()
        ):
            raise ValueError("出力先に入力ソースファイルは指定できません。")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(render_markdown(documents), encoding="utf-8")
    except (OSError, ValueError) as error:
        print("caretta: エラー: {}".format(error), file=sys.stderr)
        return 1

    print("Markdown を出力しました: {}".format(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
