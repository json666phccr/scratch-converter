# -*- coding: utf-8 -*-
"""基于 IR 的 Scratch 解释器。

执行策略：

- **控制流**（repeat/forever/if/wait until/repeat until/for each/stop/
  自制积木/扩展循环）由解释器手写，负责 yield、帧栈、warp；
- **叶子语句**（运动/外观/声音/变量/列表/广播/克隆等）由
  ``PythonGenerator._generate_statement`` 生成源码并预编译，执行时用
  ``exec(code, runtime_namespace, frame_locals)``；
- **表达式**由 ``Expr.to_python_source()`` 预编译，执行时用
  ``eval(code, runtime_namespace, {"self": sprite, **frame_locals})``。

这样既复用现有生成器对每个积木的精确映射，又能让调试器在语句边界暂停。
"""

from __future__ import annotations

import copy
import threading
import time
from typing import Any, Dict, List, Optional

from ir import BlockType, Expr, ExprType, ProjectIR, Statement, sanitize_name
from python_generator import PythonGenerator


class _VMReturn(Exception):
    """自制积木 return 的控制流异常"""

    def __init__(self, value: Any = None):
        self.value = value
        super().__init__("vm return")


class VMFrame:
    """一次调用帧（脚本或自制积木）"""

    __slots__ = ("kind", "title", "proc_stmt", "locals", "warp")

    def __init__(self, kind: str, title: str,
                 proc_stmt: Optional[Statement] = None,
                 locals_: Optional[Dict[str, Any]] = None,
                 warp: bool = False):
        self.kind = kind
        self.title = title
        self.proc_stmt = proc_stmt
        self.locals = locals_ or {}
        self.warp = warp


class VMThreadState:
    """一个脚本线程的解释器状态"""

    __slots__ = ("tid", "sprite", "script_title", "frames", "block",
                 "steps", "started")

    def __init__(self, tid: int, sprite, script_title: str):
        self.tid = tid
        self.sprite = sprite
        self.script_title = script_title
        self.frames: List[VMFrame] = [VMFrame("script", script_title)]
        self.block: Optional[Statement] = None
        self.steps = 0
        self.started = time.time()


# 由解释器手写执行的语句类型
_MANUAL_TYPES = {
    BlockType.REPEAT,
    BlockType.FOREVER,
    BlockType.IF,
    BlockType.IF_ELSE,
    BlockType.WAIT_UNTIL,
    BlockType.REPEAT_UNTIL,
    BlockType.FOR_EACH,
    BlockType.ALL_AT_ONCE,
    BlockType.PROCEDURE_DEFINE,
    BlockType.PROCEDURE_CALL,
    BlockType.PROCEDURE_RETURN,
    BlockType.COMMENT,
    BlockType.UNKNOWN,
    BlockType.EXTENSION,
    # 帽子块不应作为普通语句执行
    BlockType.WHEN_FLAG_CLICKED,
    BlockType.WHEN_KEY_PRESSED,
    BlockType.WHEN_THIS_SPRITE_CLICKED,
    BlockType.WHEN_BACKDROP_SWITCHES,
    BlockType.WHEN_BROADCAST_RECEIVED,
    BlockType.WHEN_GREATER_THAN,
    BlockType.WHEN_LOUDNESS,
    BlockType.WHEN_TIMER,
    BlockType.START_AS_CLONE,
    BlockType.EXTENSION_HAT,
}

_HAT_TYPES = {
    BlockType.WHEN_FLAG_CLICKED,
    BlockType.WHEN_KEY_PRESSED,
    BlockType.WHEN_THIS_SPRITE_CLICKED,
    BlockType.WHEN_BACKDROP_SWITCHES,
    BlockType.WHEN_BROADCAST_RECEIVED,
    BlockType.WHEN_GREATER_THAN,
    BlockType.WHEN_LOUDNESS,
    BlockType.WHEN_TIMER,
    BlockType.START_AS_CLONE,
    BlockType.EXTENSION_HAT,
}

# 这些扩展语句由解释器特殊处理，不能直接编译成叶子代码
_EXT_SPECIAL_OPS = {"foreachitemvalue", "foreachitemnum"}


class VMInterpreter:
    """Scratch IR 解释器"""

    def __init__(self, project: ProjectIR, module, runtime, debug=None):
        self.project = project
        self.module = module
        self.runtime = runtime
        self.debug = debug
        self.namespace = module.namespace

        self.gen = PythonGenerator()
        self.gen._prepare_globals(project)

        self._local = threading.local()
        self._expr_codes: Dict[int, Optional[Any]] = {}
        self._leaf_codes: Dict[int, Optional[Any]] = {}
        self._warnings: Dict[str, int] = {}

        # 运行时控制流异常类
        self._ProcedureReturn = self.namespace.get("_ProcedureReturn")
        if self._ProcedureReturn is None:
            class _NoProcedureReturn(Exception):
                pass
            self._ProcedureReturn = _NoProcedureReturn
        self._sc_bool = self.namespace.get("_sc_bool", bool)
        self._sc_num = self.namespace.get("_sc_num", float)
        self._sc_str = self.namespace.get("_sc_str", str)
        self._sc_repeat_count = self.namespace.get(
            "_sc_repeat_count", lambda value: max(0, int(value or 0)))
        self._sc_list_values = self.namespace.get(
            "_sc_list_values", lambda value: list(value or ()))

        self._build_indexes()

    # ===================== 索引构建 =====================

    def _build_indexes(self) -> None:
        for index, sprite in enumerate(self.project.sprites):
            # 过程名解析器是全局状态，必须按角色依次构建
            self.gen._build_procedure_names(sprite)
            procedures = {}
            procedure_names = {}
            for stmt in sprite.statements:
                if stmt.type != BlockType.PROCEDURE_DEFINE:
                    continue
                proccode = (stmt.extra.get("proccode")
                            or stmt.extra.get("name") or "procedure")
                procedures[proccode] = stmt
                python_name = stmt.extra.get("python_name")
                if python_name:
                    procedure_names[python_name] = stmt
            sprite_cls = self.module.sprite_classes[index]
            setattr(sprite_cls, "VM", self)
            setattr(sprite_cls, "VM_IR", sprite)
            setattr(sprite_cls, "VM_PROCEDURES", procedures)
            setattr(sprite_cls, "VM_PROCEDURE_NAMES", procedure_names)
            setattr(
                sprite_cls, "VM_SCRIPTS",
                [stmt for stmt in sprite.statements
                 if stmt.type in _HAT_TYPES])
            self._install_class_methods(sprite_cls)

            for stmt in self._iter_statements(sprite.statements):
                self._compile_statement_exprs(stmt)
                self._compile_leaf(stmt)

    def _install_class_methods(self, cls) -> None:
        interpreter = self

        def run(sprite):
            interpreter.register_hats(sprite)

        cls.run = run

        scripts = getattr(cls, "VM_SCRIPTS", [])

        def make_script(index):
            def script(sprite):
                return interpreter.run_script(sprite, index)

            script.__name__ = f"_vm_script_{index}"
            script.__doc__ = "解释执行脚本"
            return script

        for index in range(len(scripts)):
            setattr(cls, f"_vm_script_{index}", make_script(index))

        for python_name, proc in getattr(cls, "VM_PROCEDURE_NAMES", {}).items():
            def make_proc(proc_stmt):
                def method(sprite, *args):
                    return interpreter._run_procedure(
                        sprite, proc_stmt, list(args))

                method.__name__ = python_name
                method.__doc__ = f"解释执行自制积木: {python_name}"
                return method

            setattr(cls, python_name, make_proc(proc))

    def _iter_statements(self, statements):
        seen = set()
        stack = list(statements)
        while stack:
            stmt = stack.pop()
            if stmt is None or id(stmt) in seen:
                continue
            seen.add(id(stmt))
            yield stmt
            stack.extend(stmt.body or ())
            stack.extend(stmt.else_body or ())
            if stmt.next is not None:
                stack.append(stmt.next)

    def _compile_statement_exprs(self, stmt: Statement) -> None:
        for attr in ("value", "condition", "target", "expr"):
            expr = getattr(stmt, attr, None)
            if isinstance(expr, Expr):
                self._compile_expr(expr)
        self._walk_expr_container(stmt.extra)

    def _walk_expr_container(self, value) -> None:
        if isinstance(value, Expr):
            self._compile_expr(value)
            self._walk_expr_container(value.left)
            self._walk_expr_container(value.right)
            for child in list(value.children) + list(value.args):
                self._walk_expr_container(child)
            for extra_value in (value.extra or {}).values():
                self._walk_expr_container(extra_value)
        elif isinstance(value, dict):
            for item in value.values():
                self._walk_expr_container(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                self._walk_expr_container(item)

    def _compile_expr(self, expr: Expr) -> None:
        key = id(expr)
        if key in self._expr_codes:
            return
        try:
            source = expr.to_python_source()
            self._expr_codes[key] = compile(source, "<scratch-expr>", "eval")
        except Exception as error:
            self._expr_codes[key] = None
            self._warn(f"表达式 {expr.type.name}: {error}")

    def _compile_leaf(self, stmt: Statement) -> None:
        original = stmt
        if stmt.type == BlockType.EXTENSION:
            opcode = str(stmt.extra.get("opcode") or "").lower()
            short = opcode.split("_", 1)[-1]
            namespace = str(stmt.extra.get("namespace") or "").lower()
            if (namespace == "lmslisttools" and short in _EXT_SPECIAL_OPS) \
                    or opcode.endswith("foreachthreadvariable"):
                return
            # 扩展语句的 body 由解释器执行；编译时只保留扩展调用本身
            if stmt.body:
                stmt = copy.copy(stmt)
                stmt.body = []
                stmt.next = None
        elif stmt.type in _MANUAL_TYPES:
            return
        try:
            lines = self.gen._generate_statement(stmt, 0)
            source = "\n".join(lines).strip()
            if not source or all(line.strip().startswith("#")
                                 for line in source.splitlines()):
                self._leaf_codes[id(original)] = None
                return
            self._leaf_codes[id(original)] = compile(
                source, "<scratch-block>", "exec")
        except Exception as error:
            self._leaf_codes[id(original)] = None
            self._warn(f"语句 {original.type.name}: {error}")

    def _warn(self, message: str) -> None:
        count = self._warnings.get(message, 0)
        self._warnings[message] = count + 1
        if count == 0:
            target = self.debug._emit if self.debug is not None else print
            target(f"[vm] 警告: {message}")

    # ===================== 线程状态 =====================

    def state(self) -> Optional[VMThreadState]:
        return getattr(self._local, "state", None)

    def _current_frame(self) -> Optional[VMFrame]:
        state = self.state()
        return state.frames[-1] if state else None

    def _alive(self, state: VMThreadState) -> bool:
        if state is None:
            return False
        try:
            return bool(state.sprite._running)
        except Exception:
            return True

    def iter_sprites(self):
        """遍历 (SpriteIR, 实例)，包含克隆体"""
        for sprite in list(getattr(self.runtime, "sprites", ())):
            sprite_ir = getattr(type(sprite), "VM_IR", None)
            if sprite_ir is not None:
                yield sprite_ir, sprite

    # ===================== 帽子注册 =====================

    def register_hats(self, sprite) -> None:
        cls = type(sprite)
        sprite._handlers = {}
        sprite._conditions = []
        sprite._frame_hats = []

        scripts = getattr(cls, "VM_SCRIPTS", [])
        for index, hat in enumerate(scripts):
            func = getattr(sprite, f"_vm_script_{index}", None)
            if func is None:
                continue
            _name, _doc, event = self.gen._event_info(hat)

            if hat.type == BlockType.EXTENSION_HAT:
                values = {}
                for key, expr in (hat.extra.get("inputs") or []):
                    values[key] = (
                        lambda e=expr, s=sprite: self.eval_expr(e, s))
                for key, value in (hat.extra.get("fields") or {}).items():
                    values.setdefault(key, value)
                sprite._register_extension_hat(
                    hat.extra.get("namespace", ""),
                    hat.extra.get("opcode", ""),
                    values, func)
                continue

            if hat.type == BlockType.WHEN_GREATER_THAN:
                menu = str(hat.extra.get("menu") or "TIMER").lower()
                sprite._register_greater_than(
                    menu,
                    lambda e=hat.value, s=sprite: self.eval_expr(e, s),
                    func)
                continue

            if event:
                sprite._register(event, func)

    def _describe_hat(self, hat: Statement) -> str:
        _name, doc, _event = self.gen._event_info(hat)
        if doc:
            return doc
        opcode = hat.extra.get("opcode") or hat.type.name.lower()
        return str(opcode)

    # ===================== 脚本执行 =====================

    def run_script(self, sprite, index: int) -> None:
        cls = type(sprite)
        scripts = getattr(cls, "VM_SCRIPTS", [])
        if index >= len(scripts):
            return
        hat = scripts[index]
        title = self._describe_hat(hat)
        state = VMThreadState(threading.get_ident(), sprite, title)
        self._local.state = state
        if self.debug is not None:
            self.debug.thread_started(state)
        try:
            self.execute_chain(hat.next)
        except StopIteration:
            pass
        except _VMReturn:
            pass
        except Exception as error:
            if self.debug is not None:
                self.debug.record_error(state, state.block, error)
            raise
        finally:
            if self.debug is not None:
                self.debug.thread_finished(state)
            self._local.state = None

    def execute_chain(self, stmt: Optional[Statement]) -> None:
        state = self.state()
        if state is None:
            return
        seen = set()
        while stmt is not None and self._alive(state):
            if id(stmt) in seen:
                break
            seen.add(id(stmt))
            state.block = stmt
            self.execute_statement(stmt)
            stmt = stmt.next

    def execute_body(self, body) -> None:
        for child in body or ():
            if not self._alive(self.state()):
                break
            self.execute_chain(child)

    def execute_statement(self, stmt: Statement) -> None:
        state = self.state()
        if state is None:
            return
        if self.debug is not None:
            self.debug.before_statement(state, stmt)
        state.steps += 1

        stmt_type = stmt.type
        if stmt_type == BlockType.REPEAT:
            self._exec_repeat(stmt, state)
        elif stmt_type == BlockType.FOREVER:
            self._exec_forever(stmt, state)
        elif stmt_type == BlockType.IF:
            self._exec_if(stmt, state)
        elif stmt_type == BlockType.IF_ELSE:
            self._exec_if_else(stmt, state)
        elif stmt_type == BlockType.WAIT_UNTIL:
            self._exec_wait_until(stmt, state)
        elif stmt_type == BlockType.REPEAT_UNTIL:
            self._exec_repeat_until(stmt, state)
        elif stmt_type == BlockType.FOR_EACH:
            self._exec_for_each(stmt, state)
        elif stmt_type == BlockType.ALL_AT_ONCE:
            self.execute_body(stmt.body)
        elif stmt_type == BlockType.PROCEDURE_DEFINE:
            return
        elif stmt_type == BlockType.PROCEDURE_CALL:
            self._exec_procedure_call(stmt, state)
        elif stmt_type == BlockType.PROCEDURE_RETURN:
            value = (self.eval_expr(stmt.value, state.sprite,
                                    self._current_frame())
                     if stmt.value is not None else None)
            raise _VMReturn(value)
        elif stmt_type == BlockType.EXTENSION:
            self._exec_extension(stmt, state)
        elif stmt_type in (BlockType.COMMENT, BlockType.UNKNOWN) \
                or stmt_type in _HAT_TYPES:
            return
        else:
            self._exec_leaf(stmt, state)

    # ===================== 控制流 =====================

    def _exec_repeat(self, stmt: Statement, state: VMThreadState) -> None:
        count = self._sc_repeat_count(
            self.eval_expr(stmt.value, state.sprite, self._current_frame()))
        if count <= 0:
            return
        skip_yield = (self.gen._repeat_count_is_small(stmt)
                      and self.gen._body_is_pure_computation(stmt.body))
        for _ in range(count):
            if not self._alive(state):
                break
            self.execute_body(stmt.body)
            if not skip_yield and self._alive(state):
                state.sprite._yield_frame()

    def _exec_forever(self, stmt: Statement, state: VMThreadState) -> None:
        while self._alive(state):
            self.execute_body(stmt.body)
            if self._alive(state):
                state.sprite._yield_frame()

    def _exec_if(self, stmt: Statement, state: VMThreadState) -> None:
        condition = self.eval_expr(stmt.condition, state.sprite,
                                   self._current_frame())
        if self._sc_bool(condition):
            self.execute_body(stmt.body)

    def _exec_if_else(self, stmt: Statement, state: VMThreadState) -> None:
        condition = self.eval_expr(stmt.condition, state.sprite,
                                   self._current_frame())
        if self._sc_bool(condition):
            self.execute_body(stmt.body)
        else:
            self.execute_body(stmt.else_body)

    def _exec_wait_until(self, stmt: Statement, state: VMThreadState) -> None:
        while self._alive(state):
            condition = self.eval_expr(stmt.condition, state.sprite,
                                       self._current_frame())
            if self._sc_bool(condition):
                return
            state.sprite._yield_frame()

    def _exec_repeat_until(self, stmt: Statement,
                           state: VMThreadState) -> None:
        while self._alive(state):
            condition = self.eval_expr(stmt.condition, state.sprite,
                                       self._current_frame())
            if self._sc_bool(condition):
                return
            self.execute_body(stmt.body)
            if self._alive(state):
                state.sprite._yield_frame()

    def _exec_for_each(self, stmt: Statement, state: VMThreadState) -> None:
        attr = (stmt.extra.get("attr")
                or sanitize_name(stmt.extra.get("name") or "item", "var"))
        values = self._sc_list_values(
            self.eval_expr(stmt.value, state.sprite, self._current_frame()))
        for item in values:
            if not self._alive(state):
                return
            setattr(state.sprite, attr, item)
            self.execute_body(stmt.body)
            if self._alive(state):
                state.sprite._yield_frame()

    # ===================== 自制积木 =====================

    def _find_procedure(self, sprite, stmt: Statement) -> Optional[Statement]:
        cls = type(sprite)
        proccode = stmt.extra.get("proccode")
        procedures = getattr(cls, "VM_PROCEDURES", {})
        if proccode and proccode in procedures:
            return procedures[proccode]
        name = stmt.extra.get("name")
        if name:
            for proc in procedures.values():
                if proc.extra.get("name") == name:
                    return proc
        return None

    def _exec_procedure_call(self, stmt: Statement,
                             state: VMThreadState) -> None:
        proc = self._find_procedure(state.sprite, stmt)
        if proc is None:
            self._warn(f"找不到自制积木: {stmt.extra.get('proccode') or stmt.extra.get('name')}")
            return
        frame = self._current_frame()
        args = [self.eval_expr(arg, state.sprite, frame)
                for arg in (stmt.extra.get("args") or [])]
        self._run_procedure(state.sprite, proc, args)

    def _run_procedure(self, sprite, proc: Statement, args: List[Any]) -> Any:
        arg_names = list(proc.extra.get("args") or [])
        arg_types = list(proc.extra.get("arg_types") or [])
        defaults = list(proc.extra.get("argumentdefaults") or [])
        while len(arg_types) < len(arg_names):
            arg_types.append("s")

        locals_ = {}
        for index, name in enumerate(arg_names):
            key = f"arg_{sanitize_name(str(name), 'arg')}"
            if index < len(args):
                locals_[key] = args[index]
            elif index < len(defaults):
                locals_[key] = defaults[index]
            else:
                locals_[key] = False if arg_types[index] == "b" else ""

        warp = bool(proc.extra.get("warp"))
        title = proc.extra.get("proccode") or proc.extra.get("name") \
            or "procedure"
        frame = VMFrame("procedure", str(title), proc, locals_, warp)
        state = self.state()
        if state is None:
            return None
        state.frames.append(frame)
        sprite._enter_procedure(warp)
        try:
            self.execute_body(proc.body)
            return None
        except _VMReturn as value:
            return value.value
        except self._ProcedureReturn:
            return None
        finally:
            state.frames.pop()
            sprite._leave_procedure(warp)

    # ===================== 扩展语句 =====================

    def _exec_extension(self, stmt: Statement, state: VMThreadState) -> None:
        if not stmt.body:
            self._exec_leaf(stmt, state)
            return

        opcode = str(stmt.extra.get("opcode") or "")
        short = opcode.lower().split("_", 1)[-1]
        namespace = str(stmt.extra.get("namespace") or "").lower()

        if namespace == "lmslisttools" and short in _EXT_SPECIAL_OPS:
            self._exec_list_tools(stmt, state, short)
            return
        if opcode.lower().endswith("foreachthreadvariable"):
            self._exec_temp_foreach(stmt, state)
            return

        # 普通扩展语句：先执行扩展调用，再执行子栈
        self._exec_leaf(stmt, state)
        self.execute_body(stmt.body)

    def _exec_list_tools(self, stmt: Statement, state: VMThreadState,
                         short: str) -> None:
        inputs = dict(stmt.extra.get("inputs") or [])
        variable = self.eval_expr(
            inputs.get("VAR", Expr(ExprType.STRING, "item")),
            state.sprite, self._current_frame())
        source = self.eval_expr(
            inputs.get("LIST", Expr(ExprType.STRING, "list")),
            state.sprite, self._current_frame())
        list_object = self.namespace.get("_ext_list_object")
        thread_vars = self.namespace.get("_ext_thread_vars")
        if list_object is None or thread_vars is None:
            self._warn("lmsListTools 扩展未加载")
            return
        values = list(list_object(state.sprite, self._sc_str(source)) or ())
        store = thread_vars(state.sprite)
        for index, item in enumerate(values, 1):
            if not self._alive(state):
                return
            store[str(self._sc_str(variable))] = \
                index if short == "foreachitemnum" else item
            self.execute_body(stmt.body)
            if self._alive(state):
                state.sprite._yield_frame()

    def _exec_temp_foreach(self, stmt: Statement,
                           state: VMThreadState) -> None:
        inputs = dict(stmt.extra.get("inputs") or [])
        variable = self.eval_expr(
            inputs.get("VAR", Expr(ExprType.STRING, "variable")),
            state.sprite, self._current_frame())
        count = self.eval_expr(
            inputs.get("NUM", Expr(ExprType.NUMBER, 10)),
            state.sprite, self._current_frame())
        try:
            total = max(0, int(self._sc_num(count)))
        except (TypeError, ValueError):
            total = 0
        namespace = stmt.extra.get("namespace", "")
        for index in range(total):
            if not self._alive(state):
                return
            state.sprite.extension(
                namespace, "setThreadVariable",
                {"VAR": variable, "STRING": index + 1}, {})
            self.execute_body(stmt.body)
            if self._alive(state):
                state.sprite._yield_frame()

    # ===================== 叶子语句 =====================

    def _exec_leaf(self, stmt: Statement, state: VMThreadState) -> None:
        code = self._leaf_codes.get(id(stmt))
        if code is None:
            return
        frame = self._current_frame()
        env = {"self": state.sprite}
        if frame is not None:
            env.update(frame.locals)
        try:
            exec(code, self.namespace, env)
        except (StopIteration, self._ProcedureReturn, _VMReturn):
            raise
        except Exception as error:
            if self.debug is not None:
                self.debug.record_error(state, stmt, error)
            raise

    # ===================== 表达式 =====================

    def eval_expr(self, expr: Optional[Expr], sprite,
                  frame: Optional[VMFrame] = None) -> Any:
        if expr is None:
            return ""
        code = self._expr_codes.get(id(expr))
        if code is None:
            return self._expr_fallback(expr)
        env = {"self": sprite}
        if frame is not None:
            env.update(frame.locals)
        try:
            return eval(code, self.namespace, env)
        except Exception as error:
            self._warn(f"表达式求值失败 {expr.type.name}: {error}")
            return self._expr_fallback(expr)

    @staticmethod
    def _expr_fallback(expr: Expr) -> Any:
        if expr.type in (ExprType.BOOLEAN, ExprType.AND, ExprType.OR,
                         ExprType.NOT, ExprType.EQUAL, ExprType.LESS_THAN,
                         ExprType.GREATER_THAN, ExprType.LIST_CONTAINS,
                         ExprType.MOUSE_DOWN, ExprType.KEY_PRESSED):
            return False
        if expr.type in (ExprType.LIST_ACCESS, ExprType.ITEM_OF_LIST,
                         ExprType.LIST_CONTAINS, ExprType.STRING,
                         ExprType.ANSWER, ExprType.JOIN,
                         ExprType.LETTER_OF, ExprType.CONTAINS_STRING):
            return ""
        return 0
