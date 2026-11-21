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

    lint = subparsers.add_parser(
        "lint", help="静态检查未使用的变量/列表/自制积木/宏")
    lint.add_argument("folder", help="工程目录")

    run = subparsers.add_parser("run", help="编译后在本机 VM 中无头运行")
    run.add_argument("folder", help="工程目录")
    run.add_argument("--seconds", type=float, default=2.0,
                     help="运行秒数上限（默认 2.0）")
    run.add_argument("--frames", type=int, help="运行帧数上限")
    run.add_argument("--seed", type=int, help="随机种子")
    run.add_argument("--turbo", action="store_true", help="立即模式")
    run.add_argument("--audio", action="store_true", help="启用声音")
    run.add_argument("--trace", type=int, metavar="N",
                     help="打印最近 N 条执行记录")
    run.add_argument("--watch", action="append", default=[], metavar="EXPR",
                     help="运行结束后求值的表达式，可重复；"
                          "用 var('名字') / lst('名字') 读取变量/列表")
    run.add_argument("--stats", action="store_true", help="打印执行统计")
    run.add_argument("--no-vars", action="store_true",
                     help="结束后不打印变量/列表")
    run.add_argument("--json", action="store_true",
                     help="以 JSON 输出运行结果")

    imp = subparsers.add_parser("import", help="把 sb3 转成 ScPython 工程目录")
    imp.add_argument("input", help="输入 .sb3/.json")
    imp.add_argument("-o", "--output", required=True, help="输出工程目录")
    imp.add_argument("--no-macros", action="store_true",
                     help="不把相同的自制积木抽到 macros.scpy")
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


def _source_excerpt(error: ScPythonError) -> str:
    """返回出错行与列指示"""
    if not error.path or not error.line or not os.path.isfile(error.path):
        return ''
    try:
        with open(error.path, encoding='utf-8') as handle:
            lines = handle.read().splitlines()
    except OSError:
        return ''
    if not 1 <= error.line <= len(lines):
        return ''
    width = len(str(error.line))
    text = lines[error.line - 1]
    parts = [f"  {error.line:>{width}} | {text}"]
    column = error.column or (len(text) - len(text.lstrip()) + 1)
    caret = ' ' * max(0, column - 1)
    parts.append(f"  {' ' * width} | {caret}^")
    return '\n'.join(parts)


def _print_error(error: ScPythonError) -> None:
    print(f"错误: {error}", file=sys.stderr)
    excerpt = _source_excerpt(error)
    if excerpt:
        print(excerpt, file=sys.stderr)


def _print_variables(entries) -> None:
    for entry in entries:
        suffix = '#clone' if entry.get('is_clone') else ''
        print(f"[{entry['name']}{suffix}]")
        for name, value in entry['variables'].items():
            if name.startswith('__scpy_'):
                continue  # 编译器内部临时变量
            print(f"  变量 {name} = {value!r}")
        for name, value in entry['lists'].items():
            print(f"  列表 {name} = {value!r}")


def _run_command(folder: str, args) -> int:
    import json
    import random
    import tempfile

    os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
    from scratch_vm import run_project

    if args.seed is not None:
        random.seed(args.seed)
    with tempfile.TemporaryDirectory() as tmp:
        sb3 = os.path.join(tmp, 'project.sb3')
        compiler = ProjectCompiler(folder)
        compiler.export(sb3)
        for warning in compiler.warnings:
            print(f"[警告] {warning}", file=sys.stderr)
        result = run_project(
            sb3, headless=True, max_seconds=args.seconds,
            max_frames=args.frames, audio=args.audio,
            turbo=args.turbo, trace=args.trace, watch=args.watch)

    errors = result['errors']
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 1 if errors else 0

    for error in errors:
        print(f"运行时错误: {error['sprite']} {error['block']} "
              f"(block={error['block_id'] or '-'}): {error['message']}",
              file=sys.stderr)
    if result.get('trace'):
        print("[trace]")
        for item in result['trace']:
            print(f"  #{item['seq']} f{item['frame']} {item['sprite']} "
                  f"{item['opcode']} block={item['block_id'] or '-'}")
    if result.get('watches'):
        print("[watch]")
        for expression, value in result['watches']:
            print(f"  {expression} = {value!r}")
    if args.stats:
        stats = result['stats']
        print(f"帧 {stats['frames']} 语句 {stats['total_steps']} "
              f"克隆 {stats['clones']} 耗时 {stats['elapsed']:.2f}s")
    if not args.no_vars:
        _print_variables(result['variables'])
    return 1 if errors else 0


def _lint_command(folder: str) -> int:
    from .lint import lint_project
    issues = lint_project(folder)
    for issue in issues:
        print(issue)
    if not issues:
        print("未发现问题")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == 'import':
        from .importer import import_sb3
        try:
            path = import_sb3(args.input, args.output,
                              split_macros=not args.no_macros)
            print(f"已导入: {path}")
            return 0
        except ScPythonError as error:
            _print_error(error)
            return 2
    folder = os.path.abspath(args.folder)
    try:
        if args.command == 'lint':
            return _lint_command(folder)
        if args.command == 'run':
            return _run_command(folder, args)
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
        _print_error(error)
        return 2


if __name__ == '__main__':
    sys.exit(main())
