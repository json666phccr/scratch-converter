# -*- coding: utf-8 -*-
"""命令行调试器的控制核心。

解释器在每个语句执行前调用 :meth:`DebugController.before_statement`，
调试器负责：

- 统计与 trace 环形缓冲；
- 断点判断（opcode / 角色 / block id / 条件）；
- 暂停、继续、单步积木、单帧；
- 线程、调用栈、变量、watch、执行统计与错误上下文。

暂停通过独立的 ``threading.Condition`` 实现，不修改运行时的调度逻辑：
被暂停的脚本线程仍然持有执行权，其他脚本无法继续，但 pygame 主循环
照常渲染与响应窗口事件。
"""

from __future__ import annotations

import collections
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from ir import Statement, sanitize_name


def describe_statement(stmt: Optional[Statement]) -> str:
    """把语句转成便于阅读的一行描述"""
    if stmt is None:
        return "?"
    opcode = str(stmt.extra.get("opcode") or "")
    label = opcode or stmt.type.name.lower()
    detail = ""
    for key in ("proccode", "name", "message", "attr"):
        value = stmt.extra.get(key)
        if value:
            detail = f" {value}"
            break
    return f"{label}{detail}"


def statement_opcode(stmt: Optional[Statement]) -> str:
    if stmt is None:
        return ""
    return str(stmt.extra.get("opcode") or stmt.type.name.lower())


def statement_block_id(stmt: Optional[Statement]) -> str:
    if stmt is None:
        return ""
    return str(stmt.extra.get("block_id") or "")


class DebugController:
    """调试控制核心（线程安全）"""

    def __init__(self, interpreter, runtime, project,
                 trace_size: int = 2000, trace_print: bool = False):
        self.interpreter = interpreter
        self.runtime = runtime
        self.project = project
        self.namespace = interpreter.module.namespace
        self.trace_print = trace_print
        # 交互模式下断点会暂停等待命令；非交互模式只报告一次并继续
        self.interactive = True

        self.cond = threading.Condition()
        self.paused = False
        self.mode = "run"          # run / pause / step_block / step_frame
        self.step_tid: Optional[int] = None
        self.frame_target: Optional[int] = None
        self._stop = False

        self.breakpoints: List[dict] = []
        self.trace = collections.deque(maxlen=max(16, int(trace_size)))
        self.watches: List[str] = []
        self.stats = collections.Counter()
        self.sprite_stats = collections.Counter()
        self.errors = collections.deque(maxlen=50)
        self.threads: Dict[int, Any] = {}
        self.last_state = None
        self.last_stmt: Optional[Statement] = None
        self._seq = 0
        self._print_lock = threading.Lock()
        self._pause_reported = False

    # ===================== 生命周期 =====================

    def thread_started(self, state) -> None:
        with self.cond:
            self.threads[state.tid] = state

    def thread_finished(self, state) -> None:
        with self.cond:
            if self.threads.get(state.tid) is state:
                self.threads.pop(state.tid, None)

    def shutdown(self) -> None:
        """释放所有暂停中的线程；CLI 退出时必须先调用"""
        with self.cond:
            self._stop = True
            self.paused = False
            self.mode = "run"
            self.cond.notify_all()

    # ===================== 语句钩子 =====================

    def before_statement(self, state, stmt: Statement) -> None:
        """每个语句执行前调用；可能阻塞在暂停状态"""
        opcode = statement_opcode(stmt)
        sprite_name = getattr(state.sprite, "name", "?")
        self.stats[opcode] += 1
        self.sprite_stats[sprite_name] += 1

        self._seq += 1
        record = (
            self._seq,
            time.time(),
            state.tid,
            self.runtime.frame,
            f"{sprite_name}#clone" if getattr(state.sprite, "_is_clone", False)
            else sprite_name,
            opcode,
            statement_block_id(stmt),
            describe_statement(stmt),
            state.script_title,
        )
        self.trace.append(record)
        if self.trace_print:
            self._emit(
                f"[trace] f{record[3]} {record[4]} {record[5]} "
                f"({record[6] or '-'})")

        self.last_state = state
        self.last_stmt = stmt

        hit = self._match_breakpoints(state, stmt)
        if hit is not None:
            if self.interactive:
                with self.cond:
                    if not self.paused:
                        self.paused = True
                        self.mode = "pause"
                    self._pause_reported = False
                self._report_pause(state, stmt, reason=hit)
            else:
                self._emit(
                    f"[vm] 断点命中（非交互模式，继续）: {hit} -> "
                    f"{getattr(state.sprite, 'name', '?')} "
                    f"{describe_statement(stmt)}")

        self._wait_if_paused(state)

    def _wait_if_paused(self, state) -> None:
        with self.cond:
            while self.paused and not self._stop:
                # 单步：只放行发起单步的那个线程一条语句
                if self.mode == "step_block" and self.step_tid == state.tid:
                    self.mode = "pause"
                    self.step_tid = None
                    return
                # 单帧由 step_frame() 负责在帧推进后重新暂停，
                # 这里只需要让线程继续跑
                if self.mode == "step_frame":
                    return
                self.cond.wait(0.1)

    # ===================== 断点 =====================

    def add_breakpoint(self, kind: str, value: Any) -> dict:
        kind = str(kind).lower()
        if kind not in ("opcode", "sprite", "block", "cond"):
            raise ValueError(f"未知断点类型: {kind}")
        entry = {
            "kind": kind,
            "value": value,
            "enabled": True,
            "hits": 0,
            "label": f"{kind}: {value}",
        }
        self.breakpoints.append(entry)
        return entry

    def delete_breakpoint(self, index: Any) -> bool:
        """index 为 1 起始编号；'all' 清空"""
        if isinstance(index, str) and index.lower() in ("all", "*"):
            self.breakpoints.clear()
            return True
        try:
            position = int(index) - 1
        except (TypeError, ValueError):
            return False
        if 0 <= position < len(self.breakpoints):
            self.breakpoints.pop(position)
            return True
        return False

    def _match_breakpoints(self, state, stmt: Statement) -> Optional[str]:
        if not self.breakpoints:
            return None
        opcode = statement_opcode(stmt).lower()
        block_id = statement_block_id(stmt)
        sprite_name = getattr(state.sprite, "name", "")
        is_clone = bool(getattr(state.sprite, "_is_clone", False))
        sprite_key = f"{sprite_name}#clone" if is_clone else sprite_name
        for entry in self.breakpoints:
            if not entry["enabled"]:
                continue
            kind = entry["kind"]
            value = entry["value"]
            matched = False
            if kind == "opcode":
                wanted = {item.strip().lower()
                          for item in str(value).split(",") if item.strip()}
                matched = opcode in wanted
            elif kind == "sprite":
                matched = sprite_key == str(value) or sprite_name == str(value)
            elif kind == "block":
                matched = block_id == str(value)
            elif kind == "cond":
                matched = self._eval_condition(str(value), state, stmt)
            if matched:
                entry["hits"] += 1
                return entry["label"]
        return None

    def _eval_condition(self, expression: str, state, stmt: Statement) -> bool:
        try:
            code = compile(expression, "<break-if>", "eval")
        except SyntaxError as error:
            self._emit(f"[debug] 条件断点语法错误: {error}")
            return False
        env = self._base_env(state.sprite, state, stmt)
        try:
            return bool(eval(code, self.namespace, env))
        except Exception as error:
            self._emit(f"[debug] 条件断点求值失败: {error}")
            return False

    # ===================== 控制命令 =====================

    def pause(self) -> None:
        with self.cond:
            if self.paused:
                return
            self.paused = True
            self.mode = "pause"
            self._pause_reported = False
            self.cond.notify_all()
        if self.last_state is not None:
            self._report_pause(self.last_state, self.last_stmt,
                               reason="user pause")
        else:
            self._emit("[debug] 已暂停（尚未执行任何积木）")

    def resume(self) -> None:
        with self.cond:
            self.paused = False
            self.mode = "run"
            self.step_tid = None
            self.frame_target = None
            self.cond.notify_all()
        self._emit("[debug] 继续运行")

    def step_block(self) -> None:
        with self.cond:
            if not self.paused:
                self.paused = True
            self.mode = "step_block"
            self.step_tid = (self.last_state.tid
                             if self.last_state is not None else None)
            self.cond.notify_all()
        if self.step_tid is None:
            self._emit("[debug] 没有活动线程，无法单步")

    def step_frame(self) -> None:
        """放行到下一帧结束，然后重新暂停（在调用者线程等待）"""
        target = self.runtime.frame + 1
        with self.cond:
            self.mode = "step_frame"
            self.frame_target = target
            self.paused = False
            self.cond.notify_all()
        deadline = time.time() + 30.0
        while (self.runtime.running and self.runtime.frame < target
               and time.time() < deadline and not self._stop):
            time.sleep(0.005)
        with self.cond:
            self.paused = True
            self.mode = "pause"
            self.frame_target = None
            self.cond.notify_all()
        if self.last_state is not None:
            self._report_pause(self.last_state, self.last_stmt,
                               reason=f"单帧 -> frame {self.runtime.frame}")

    # ===================== 查询 =====================

    def _report_pause(self, state, stmt, reason: str = "") -> None:
        with self.cond:
            if self._pause_reported:
                return
            self._pause_reported = True
        opcode = statement_opcode(stmt)
        block_id = statement_block_id(stmt)
        sprite_name = getattr(state.sprite, "name", "?")
        if getattr(state.sprite, "_is_clone", False):
            sprite_name += "#clone"
        suffix = f" [{reason}]" if reason else ""
        self._emit(
            f"[vm] 暂停{suffix}: {sprite_name} {describe_statement(stmt)} "
            f"(block={block_id or '-'}, frame={self.runtime.frame}, "
            f"thread={state.tid})")

    def active_states(self) -> List[Any]:
        with self.cond:
            return list(self.threads.values())

    def call_stacks(self) -> Dict[int, List[str]]:
        result = {}
        for state in self.active_states():
            result[state.tid] = [frame.title for frame in state.frames]
        return result

    def thread_list(self) -> List[dict]:
        now = time.time()
        threads = []
        for state in self.active_states():
            threads.append({
                "tid": state.tid,
                "sprite": getattr(state.sprite, "name", "?"),
                "is_clone": bool(getattr(state.sprite, "_is_clone", False)),
                "script": state.script_title,
                "block": describe_statement(state.block),
                "steps": state.steps,
                "depth": len(state.frames),
                "elapsed": max(0.0, now - state.started),
            })
        return threads

    def recent_trace(self, count: int = 20) -> List[dict]:
        items = list(self.trace)[-max(1, int(count)):]
        return [
            {
                "seq": item[0],
                "time": item[1],
                "tid": item[2],
                "frame": item[3],
                "sprite": item[4],
                "opcode": item[5],
                "block_id": item[6],
                "block": item[7],
                "script": item[8],
            }
            for item in items
        ]

    def stats_report(self) -> dict:
        return {
            "total_steps": sum(self.stats.values()),
            "opcodes": dict(self.stats.most_common()),
            "sprites": dict(self.sprite_stats.most_common()),
            "frames": self.runtime.frame,
            "elapsed": self.runtime.elapsed(),
            "threads": len(self.threads),
            "clones": sum(1 for sprite in self.runtime.sprites
                          if getattr(sprite, "_is_clone", False)),
            "errors": len(self.errors),
        }

    # ===================== 变量 / watch =====================

    def dump_variables(self, sprite_name: Optional[str] = None) -> List[dict]:
        result = []
        for sprite_ir, sprite in self.interpreter.iter_sprites():
            name = getattr(sprite, "name", "?")
            if sprite_name and name != sprite_name:
                continue
            entry = {
                "name": name,
                "is_clone": bool(getattr(sprite, "_is_clone", False)),
                "variables": {},
                "lists": {},
            }
            for var_name, attr in sprite_ir.variable_attrs.items():
                try:
                    entry["variables"][var_name] = getattr(sprite, attr)
                except Exception as error:
                    entry["variables"][var_name] = f"<error: {error}>"
            for list_name, attr in sprite_ir.list_attrs.items():
                try:
                    entry["lists"][list_name] = list(getattr(sprite, attr))
                except Exception as error:
                    entry["lists"][list_name] = f"<error: {error}>"
            result.append(entry)
        return result

    def add_watch(self, expression: str) -> None:
        self.watches.append(expression)

    def eval_watches(self) -> List[Tuple[str, Any]]:
        results = []
        for expression in self.watches:
            try:
                code = compile(expression, "<watch>", "eval")
                env = self._base_env(self._default_sprite(), None, None)
                value = eval(code, self.namespace, env)
            except Exception as error:
                value = f"<error: {error}>"
            results.append((expression, value))
        return results

    def _default_sprite(self):
        sprites = list(getattr(self.runtime, "sprites", ()))
        for sprite in sprites:
            if not getattr(sprite, "is_stage", False):
                return sprite
        return sprites[0] if sprites else None

    def _base_env(self, sprite, state, stmt) -> dict:
        env = {
            "sprite": sprite,
            "runtime": self.runtime,
            "frame": self.runtime.frame,
            "stmt": stmt,
            "opcode": statement_opcode(stmt),
            "block_id": statement_block_id(stmt),
            "var": lambda name, target=None: self._read_var(
                target or sprite, name),
            "lst": lambda name, target=None: self._read_list(
                target or sprite, name),
        }
        if state is not None:
            env["thread"] = state
        return env

    def _read_var(self, sprite, name: str) -> Any:
        if sprite is None:
            return 0
        targets = [sprite]
        stage = getattr(self.runtime, "stage_sprite", None)
        if stage is not None and stage is not sprite:
            targets.append(stage)
        for target in targets:
            sprite_ir = getattr(type(target), "VM_IR", None)
            attr = sprite_ir.variable_attrs.get(str(name)) \
                if sprite_ir is not None else None
            if attr is not None:
                return getattr(target, attr, 0)
        return getattr(sprite, sanitize_name(str(name), "var"), 0)

    def _read_list(self, sprite, name: str) -> list:
        if sprite is None:
            return []
        targets = [sprite]
        stage = getattr(self.runtime, "stage_sprite", None)
        if stage is not None and stage is not sprite:
            targets.append(stage)
        for target in targets:
            sprite_ir = getattr(type(target), "VM_IR", None)
            attr = sprite_ir.list_attrs.get(str(name)) \
                if sprite_ir is not None else None
            if attr is not None:
                try:
                    return list(getattr(target, attr))
                except Exception:
                    return []
        try:
            return list(getattr(sprite, sanitize_name(str(name), "lst")))
        except Exception:
            return []

    # ===================== 错误 =====================

    def record_error(self, state, stmt: Optional[Statement],
                     error: BaseException) -> None:
        sprite_name = getattr(getattr(state, "sprite", None), "name", "?")
        record = {
            "time": time.time(),
            "sprite": sprite_name,
            "opcode": statement_opcode(stmt),
            "block_id": statement_block_id(stmt),
            "message": f"{type(error).__name__}: {error}",
            "block": describe_statement(stmt),
        }
        self.errors.append(record)
        self._emit(
            f"[vm] 执行错误: {record['sprite']} {record['block']} "
            f"(block={record['block_id'] or '-'}): {record['message']}")

    # ===================== 输出 =====================

    def _emit(self, message: str) -> None:
        with self._print_lock:
            print(message, flush=True)
