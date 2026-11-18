# -*- coding: utf-8 -*-
"""ScPython 命令行入口。"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

from .compiler import ProjectCompiler
from .errors import ScPythonError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scpython",
        description="ScPython：Python 风格、Scratch 语义的 .scpy 工程编译器")
    subparsers = parser.add_subparsers(dest="command", required=True)

    export = subparsers.add_parser("export", help="导出 sb3")
    export.add_argument("folder", help="工程目录")
    export.add_argument("-o", "--output", help="输出 .sb3/.json 路径")
    export.add_argument("--verbose", action="store_true", help="输出详细信息")

    check = subparsers.add_parser("check", help="只检查语法并打印摘要")
    check.add_argument("folder", help="工程目录")
    check.add_argument("--verbose", action="store_true", help="输出详细信息")
    return parser


def _summary(compiler: ProjectCompiler, project) -> None:
    print(f"舞台: {project.stage.name if project.stage else '-'}")
    print(f"角色: {len(project.sprites) - (1 if project.stage else 0)} 个")
    for sprite in project.sprites:
        if sprite.is_stage:
            continue
        variables = len(sprite.variables)
        lists = len(sprite.lists)
        scripts = len([stmt for stmt in sprite.statements
                       if stmt.type.name.startswith('WHEN_')
                       or stmt.type.name in ('START_AS_CLONE',
                                             'EXTENSION_HAT')])
        procedures = len([stmt for stmt in sprite.statements
                          if stmt.type.name == 'PROCEDURE_DEFINE'])
        print(f"  - {sprite.name}: 脚本 {scripts}，自制积木 {procedures}，"
              f"变量 {variables}，列表 {lists}")
    print(f"资产: {len(compiler.assets)} 个")
    print(f"扩展: {', '.join(sorted(project.extensions)) or '无'}")
    for warning in compiler.warnings:
        print(f"[警告] {warning}")


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    folder = os.path.abspath(args.folder)
    try:
        compiler = ProjectCompiler(folder, verbose=args.verbose)
        if args.command == 'check':
            project = compiler.compile()
            _summary(compiler, project)
            return 0

        output = args.output
        if not output:
            name = os.path.basename(folder.rstrip('\\/')) or 'project'
            output = os.path.join(os.path.dirname(folder), name + '.sb3')
        path = compiler.export(output)
        project = compiler.last_project
        _summary(compiler, project)
        print(f"已导出: {path}")
        return 0
    except ScPythonError as error:
        print(f"错误: {error}", file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
