# -*- coding: utf-8 -*-
"""混淆导出命令行。"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import ObfuscationError, obfuscate_sb3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="obfuscator",
        description="把 Scratch .sb3 单向转换为混淆后的 Python")
    parser.add_argument("input", help="输入 .sb3/.json")
    parser.add_argument("output", nargs="?", help="输出 .py（默认 <输入名>_obf.py）")
    parser.add_argument("--no-embed-assets", action="store_true",
                        help="资产不写入载荷，改为导出到 <输出名>_assets/")
    parser.add_argument("--no-fold", action="store_true",
                        help="关闭常量折叠与恒定条件简化")
    parser.add_argument("--seed", type=int, help="AST 混淆随机种子")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = obfuscate_sb3(
            args.input,
            args.output,
            embed_assets=not args.no_embed_assets,
            fold=not args.no_fold,
            seed=args.seed,
        )
    except ObfuscationError as error:
        print(f"错误: {error}", file=sys.stderr)
        return 2
    print(f"已生成: {result.output}")
    print(f"大小: {result.size} 字节")
    print(f"资产: {result.asset_count} 个"
          + ("（已内嵌）" if result.embedded_assets else "（外部）"))
    print(f"常量折叠: {'开启' if result.folded else '关闭'}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
