# -*- coding: utf-8 -*-
"""Scratch VM 命令行入口与交互调试器。"""

from __future__ import annotations

import argparse
import random
import sys
import threading
from typing import List, Optional

from .debugger import DebugController
from .interpreter import VMInterpreter
from .loader import LoadError, load_project
from .module import build_module

try:
    import pygame
except ImportError:
    pygame = None


COMMAND_HELP = """可用命令:
  help | h                 显示本帮助
  continue | c             继续运行
  pause | p                暂停
  step | s                 单步一个积木
  frame | sf               单步一帧
  trace | t [n]            最近 n 条执行记录（默认 20）
  stack | bt               所有线程的调用栈
  threads | th             活动线程列表
  vars | v [角色]          查看变量/列表
  watch | w [表达式]       查看或添加 watch 表达式
  break | b <类型> <值>    断点: opcode / sprite / block / if
  breaks | bl              断点列表
  delete | bd <N|all>      删除断点
  stats | st               执行统计
  overlay | o              切换可视化调试面板
  quit | q                 退出
"""


def _parse_stage_size(text: Optional[str]):
    if not text:
        return None
    try:
        width, height = text.lower().split("x")
        return int(width), int(height)
    except (ValueError, AttributeError):
        raise argparse.ArgumentTypeError("舞台尺寸格式应为 WIDTHxHEIGHT")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scratch_vm",
        description="Scratch 3.0 虚拟机：读取 sb3 并解释执行，支持命令行与可视化调试")
    parser.add_argument("project", help="项目文件（.sb3 / .zip / .json）")

    runtime_group = parser.add_argument_group("运行控制")
    runtime_group.add_argument("--headless", action="store_true", help="无窗口模式")
    runtime_group.add_argument("--fps", type=int, help="覆盖帧率")
    runtime_group.add_argument("--frames", type=int, help="运行指定帧数后退出")
    runtime_group.add_argument("--seconds", type=float, help="运行指定秒数后退出")
    runtime_group.add_argument("--seed", type=int, help="随机种子")
    runtime_group.add_argument("--turbo", action="store_true", help="立即模式")
    runtime_group.add_argument("--no-fencing", dest="fencing",
                               action="store_false", help="关闭舞台边界限制")
    runtime_group.add_argument("--no-audio", dest="audio",
                               action="store_false", help="关闭声音")
    runtime_group.add_argument("--stage-size", help="舞台尺寸，如 640x360")
    runtime_group.add_argument("--infinite-clones", action="store_true",
                               help="解除克隆体数量限制")
    runtime_group.add_argument("--windowed", action="store_true",
                               help="以普通窗口启动（默认最大化）")

    debug_group = parser.add_argument_group("调试")
    debug_group.add_argument("--debug", action="store_true",
                             help="启用交互调试（从 stdin 读取命令）")
    debug_group.add_argument("--pause-on-start", action="store_true",
                             help="启动后立即暂停")
    debug_group.add_argument("--trace", action="store_true",
                             help="打印每条执行的积木")
    debug_group.add_argument("--trace-size", type=int, default=2000,
                             help="trace 环形缓冲大小（默认 2000）")
    debug_group.add_argument("--break-opcode", action="append", default=[],
                             metavar="OP", help="按 opcode 设断点，可逗号分隔")
    debug_group.add_argument("--break-sprite", action="append", default=[],
                             metavar="NAME", help="按角色名设断点")
    debug_group.add_argument("--break-block", action="append", default=[],
                             metavar="ID", help="按 block id 设断点")
    debug_group.add_argument("--break-if", action="append", default=[],
                             metavar="EXPR", help="条件断点（Python 表达式）")
    debug_group.add_argument("--watch", action="append", default=[],
                             metavar="EXPR", help="watch 表达式")
    debug_group.add_argument("--no-overlay", action="store_true",
                             help="关闭窗口内可视化调试面板")
    debug_group.add_argument("--stats", action="store_true",
                             help="退出时打印执行统计")
    debug_group.add_argument("--dump-vars", action="store_true",
                             help="退出时打印变量/列表")
    return parser


class CommandShell:
    """stdin 命令循环（daemon 线程）"""

    def __init__(self, debug: DebugController, runtime, overlay=None):
        self.debug = debug
        self.runtime = runtime
        self.overlay = overlay
        self.thread = None
        self._quit = False

    def start(self) -> None:
        self.thread = threading.Thread(
            target=self._loop, name="vm-debug-console", daemon=True)
        self.thread.start()

    def _prompt(self) -> str:
        try:
            return "vm> " if sys.stdin.isatty() else ""
        except Exception:
            return ""

    def _loop(self) -> None:
        print("[debug] 交互调试已启用，输入 help 查看命令，q 退出。", flush=True)
        while not self._quit and self.runtime.running:
            try:
                line = input(self._prompt())
            except (EOFError, KeyboardInterrupt):
                print("[debug] stdin 已关闭，继续运行。", flush=True)
                return
            if not line.strip():
                continue
            try:
                self.dispatch(line.strip())
            except Exception as error:
                print(f"[debug] 命令执行失败: {error}", flush=True)

    # ===================== 命令分派 =====================

    def dispatch(self, line: str) -> None:
        parts = line.split(maxsplit=1)
        command = parts[0].lower()
        argument = parts[1].strip() if len(parts) > 1 else ""

        if command in ("help", "h", "?"):
            print(COMMAND_HELP, flush=True)
        elif command in ("continue", "c", "run", "r"):
            self.debug.resume()
        elif command in ("pause", "p"):
            self.debug.pause()
        elif command in ("step", "s"):
            self.debug.step_block()
        elif command in ("frame", "sf"):
            self.debug.step_frame()
        elif command in ("trace", "t"):
            self._print_trace(argument)
        elif command in ("stack", "bt"):
            self._print_stacks()
        elif command in ("threads", "th"):
            self._print_threads()
        elif command in ("vars", "v"):
            self._print_vars(argument or None)
        elif command in ("watch", "w"):
            self._watch(argument)
        elif command in ("break", "b"):
            self._break(argument)
        elif command in ("breaks", "bl"):
            self._print_breaks()
        elif command in ("delete", "bd"):
            ok = self.debug.delete_breakpoint(argument or "all")
            print("[debug] 已删除" if ok else "[debug] 删除失败", flush=True)
        elif command in ("stats", "st"):
            self._print_stats()
        elif command in ("overlay", "o"):
            if self.overlay is None:
                print("[debug] 可视化面板不可用", flush=True)
            else:
                state = self.overlay.toggle()
                print(f"[debug] 可视化面板: {'开' if state else '关'}",
                      flush=True)
        elif command in ("quit", "q", "exit"):
            self._quit = True
            self.debug.shutdown()
            self.runtime.running = False
            self.runtime.stop_all_scripts()
            print("[debug] 正在退出...", flush=True)
        else:
            print(f"[debug] 未知命令: {command}（输入 help 查看）", flush=True)

    # ===================== 输出 =====================

    def _print_trace(self, argument: str) -> None:
        try:
            count = int(argument) if argument else 20
        except ValueError:
            count = 20
        records = self.debug.recent_trace(count)
        if not records:
            print("[trace] 暂无记录", flush=True)
            return
        for item in records:
            print(
                f"#{item['seq']} f{item['frame']} t{item['tid']} "
                f"{item['sprite']} {item['opcode']} "
                f"block={item['block_id'] or '-'} [{item['script']}]",
                flush=True)

    def _print_stacks(self) -> None:
        stacks = self.debug.call_stacks()
        if not stacks:
            print("[debug] 没有活动线程", flush=True)
            return
        for tid, frames in stacks.items():
            print(f"线程 {tid}: " + " > ".join(frames), flush=True)

    def _print_threads(self) -> None:
        threads = self.debug.thread_list()
        if not threads:
            print("[debug] 没有活动线程", flush=True)
            return
        for item in threads:
            suffix = "#clone" if item["is_clone"] else ""
            print(
                f"线程 {item['tid']}  {item['sprite']}{suffix}  "
                f"{item['script']}  当前={item['block']}  "
                f"深度={item['depth']}  步数={item['steps']}  "
                f"运行={item['elapsed']:.2f}s",
                flush=True)

    def _print_vars(self, sprite_name: Optional[str]) -> None:
        entries = self.debug.dump_variables(sprite_name)
        if not entries:
            print("[debug] 没有变量", flush=True)
            return
        for entry in entries:
            suffix = "#clone" if entry["is_clone"] else ""
            print(f"[{entry['name']}{suffix}]", flush=True)
            for name, value in entry["variables"].items():
                print(f"  变量 {name} = {value!r}", flush=True)
            for name, value in entry["lists"].items():
                print(f"  列表 {name} = {value!r}", flush=True)

    def _watch(self, expression: str) -> None:
        if expression:
            self.debug.add_watch(expression)
        results = self.debug.eval_watches()
        if not results:
            print("[debug] 没有 watch 表达式", flush=True)
            return
        for expr, value in results:
            print(f"  {expr} = {value!r}", flush=True)

    def _break(self, argument: str) -> None:
        parts = argument.split(maxsplit=1)
        if len(parts) < 2:
            print("[debug] 用法: break opcode|sprite|block|if <值>", flush=True)
            return
        kind, value = parts[0].lower(), parts[1].strip()
        if kind in ("if", "cond", "condition"):
            kind = "cond"
        if kind not in ("opcode", "sprite", "block", "cond"):
            print("[debug] 断点类型应为 opcode/sprite/block/if", flush=True)
            return
        if kind == "opcode":
            for item in value.split(","):
                if item.strip():
                    self.debug.add_breakpoint("opcode", item.strip())
        else:
            self.debug.add_breakpoint(kind, value)
        self._print_breaks()

    def _print_breaks(self) -> None:
        if not self.debug.breakpoints:
            print("[debug] 没有断点", flush=True)
            return
        for index, entry in enumerate(self.debug.breakpoints, 1):
            print(f"  {index}. {entry['label']}  命中 {entry['hits']} 次",
                  flush=True)

    def _print_stats(self) -> None:
        report = self.debug.stats_report()
        print(
            f"[stats] 语句 {report['total_steps']} 帧 {report['frames']} "
            f"线程 {report['threads']} 克隆 {report['clones']} "
            f"耗时 {report['elapsed']:.2f}s 错误 {report['errors']}",
            flush=True)
        print("[stats] 按 opcode:", flush=True)
        for opcode, count in list(report["opcodes"].items())[:20]:
            print(f"  {opcode}: {count}", flush=True)
        print("[stats] 按角色:", flush=True)
        for name, count in report["sprites"].items():
            print(f"  {name}: {count}", flush=True)


def _configure_debug(debug: DebugController, args) -> None:
    for value in args.break_opcode:
        for item in value.split(","):
            if item.strip():
                debug.add_breakpoint("opcode", item.strip())
    for value in args.break_sprite:
        debug.add_breakpoint("sprite", value)
    for value in args.break_block:
        debug.add_breakpoint("block", value)
    for value in args.break_if:
        debug.add_breakpoint("cond", value)
    for value in args.watch:
        debug.add_watch(value)
    debug.trace_print = bool(args.trace)
    debug.interactive = bool(args.debug)


def _print_final(debug: DebugController, args) -> None:
    if args.stats:
        shell = CommandShell(debug, debug.runtime)
        shell._print_stats()
    if args.dump_vars:
        for entry in debug.dump_variables():
            suffix = "#clone" if entry["is_clone"] else ""
            print(f"[{entry['name']}{suffix}]", flush=True)
            for name, value in entry["variables"].items():
                print(f"  变量 {name} = {value!r}", flush=True)
            for name, value in entry["lists"].items():
                print(f"  列表 {name} = {value!r}", flush=True)


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if pygame is None:
        print("错误: 运行 Scratch VM 需要 pygame，请先执行 pip install pygame",
              file=sys.stderr)
        return 2

    try:
        stage_size = _parse_stage_size(args.stage_size)
    except argparse.ArgumentTypeError as error:
        parser.error(str(error))

    if args.seed is not None:
        random.seed(args.seed)

    try:
        loaded = load_project(args.project)
    except LoadError as error:
        print(f"加载失败: {error}", file=sys.stderr)
        return 2

    runtime = None
    debug = None
    overlay = None
    try:
        module = build_module(loaded.project, loaded.assets_dir)
        runtime = module.create_runtime(
            headless=args.headless,
            fps=args.fps,
            audio=args.audio,
            assets_dir=loaded.assets_dir,
            turbo=args.turbo,
            fencing=args.fencing,
            infinite_clones=args.infinite_clones,
            stage_size=stage_size,
            maximize=not args.windowed,
        )

        need_debug = bool(
            args.debug or args.trace or args.pause_on_start
            or args.break_opcode or args.break_sprite or args.break_block
            or args.break_if or args.watch or args.stats or args.dump_vars
            or (not args.no_overlay and not args.headless))
        interpreter = VMInterpreter(loaded.project, module, runtime, debug=None)
        if need_debug:
            debug = DebugController(
                interpreter, runtime, loaded.project,
                trace_size=args.trace_size)
            interpreter.debug = debug
            _configure_debug(debug, args)

        from .overlay import DebugOverlay
        if debug is not None and not args.no_overlay:
            overlay = DebugOverlay(runtime, debug, enabled=True)

        module.create_sprites(runtime)

        shell = None
        if args.debug:
            shell = CommandShell(debug, runtime, overlay)
            shell.start()

        if debug is not None and args.pause_on_start:
            debug.pause()

        try:
            runtime.start(max_frames=args.frames, max_seconds=args.seconds)
        except KeyboardInterrupt:
            pass
        finally:
            if debug is not None:
                debug.shutdown()
                if args.stats or args.dump_vars:
                    _print_final(debug, args)
            runtime.shutdown()
        return 0
    finally:
        loaded.close()


if __name__ == "__main__":
    sys.exit(main())
