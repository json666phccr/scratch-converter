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
    parser.add_argument("output", nargs="?",
                        help="输出 .py（默认 <输入名>_obf.py；"
                             "native 模式为目录 <输入名>_obf_native/）")
    parser.add_argument("--no-embed-assets", action="store_true",
                        help="资产不写入载荷，改为导出到 <输出名>_assets/")
    parser.add_argument("--no-fold", action="store_true",
                        help="关闭常量折叠与恒定条件简化")
    parser.add_argument("--seed", type=int, help="AST 混淆随机种子")
    parser.add_argument("--native", action="store_true",
                        help="Tier 2：loader 用 Cython 编译为原生扩展"
                             "（输出目录：main.py + core 扩展，"
                             "需要 Cython 与 C 编译器）")
    parser.add_argument("--license-pubkey", default=None,
                        help="Tier 2：Ed25519 公钥 hex（配合 "
                             "--license-file 与 --license-fp）")
    parser.add_argument("--license-file", default=None,
                        help="Tier 2：许可证文件路径（由 obfuscator.license "
                             "issue 签发）")
    parser.add_argument("--license-fp", default=None,
                        help="Tier 2：目标机器指纹 hex（obfuscator.license "
                             "fingerprint 输出；不随产物分发）")
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
            license_file=args.license_file,
            license_pubkey=args.license_pubkey,
            license_fp=args.license_fp,
            native=args.native,
        )
    except ObfuscationError as error:
        print(f"错误: {error}", file=sys.stderr)
        return 2
    print(f"已生成: {result.output}")
    print(f"大小: {result.size} 字节")
    print(f"资产: {result.asset_count} 个"
          + ("（已内嵌）" if result.embedded_assets else "（外部）"))
    print(f"常量折叠: {'开启' if result.folded else '关闭'}")
    if args.native:
        print("分发内容: main.py + 原生扩展（已剥离调试信息，"
              "字节码级工具无效）")
    if args.license_file:
        print("许可证绑定: 已启用（指纹不在分发物中，离线复算密钥不可行；"
              "产物只能在 --license-fp 对应的机器上运行）")
    return 0


if __name__ == '__main__':
    sys.exit(main())
