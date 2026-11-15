"""通用 Python -> Scratch 转换（实验性）

与 ``python_parser.PythonParser`` 不同：后者专门解析本转换器生成的
Scratch DSL（``ScratchSprite`` 类、``when_green_flag``、``self.move()`` 等），
准确率最高；本模块尝试把**普通 Python 脚本**翻译成 Scratch 3 积木。

支持的核心子集：
- 顶层语句 -> 绿旗脚本
- ``def`` 函数 -> 自制积木；返回值写入 ``__py_ret_<函数名>`` 变量
- 变量、赋值/增量赋值、算术/比较/布尔表达式
- ``if/elif/else``、``while``、``for ... in range(...)``、``for ... in 列表``、
  ``for ... in 字符串``、``for i, v in enumerate(...)``
- ``break`` / ``continue``（循环标志变量 + 条件包裹）
- 列表字面量、``append/insert/clear/pop/remove/index/count/reverse/sort``、
  ``extend/copy``、``sorted(...)`` / ``reversed(...)``、下标读写
- ``print`` -> 说话；``input`` -> 询问并等待
- ``len``、``str/int/float``、``abs/round(x, n)``、``min/max/sum``、``pow``、``**``
- ``math`` 常量与函数（``sqrt/floor/ceil/sin/cos/...``、``fabs``、``pow``）
- ``random.randint/random/uniform/random/choice``、``time.sleep``
- 条件表达式 ``a if cond else b``、``"分隔符".join(列表)``、``f"{x:.2f}"``
- 元组交换赋值 ``a, b = b, a``、``enumerate(列表, start)``

不支持：类、异常、生成器、装饰器、多返回值、``match``、
大部分字符串方法（``upper/lower/replace/split`` 等），会记入转换报告，
而不是静默丢失。
"""

import ast
import hashlib
import math
import re
from typing import Any, Dict, List, Optional, Tuple

from ir import (
    BlockType, ExprType, Expr, Statement, ProjectIR, SpriteIR,
    make_number, make_string, make_boolean, make_variable,
    make_binary_op, make_list_access, make_random,

)
from python_parser import PythonParser


DEFAULT_COSTUME_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" '
    'viewBox="0 0 64 64">'
    '<rect x="4" y="4" width="56" height="56" rx="14" fill="#3b7ddd"/>'
    '<text x="32" y="43" font-family="Arial,Helvetica,sans-serif" '
    'font-size="26" font-weight="bold" fill="#ffffff" '
    'text-anchor="middle">Py</text>'
    '</svg>'
).encode('utf-8')


DEFAULT_BACKDROP_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" '
    'viewBox="0 0 480 360">'
    '<rect width="480" height="360" fill="#ffffff"/>'
    '</svg>'
).encode('utf-8')


def default_costume() -> Tuple[Dict[str, Any], Dict[str, bytes]]:
    """生成一个默认造型（蓝色圆角方块 + Py），并返回需要写入sb3的资源"""
    digest = hashlib.md5(DEFAULT_COSTUME_SVG).hexdigest()
    costume = {
        'name': 'python',
        'assetId': digest,
        'md5ext': f'{digest}.svg',
        'dataFormat': 'svg',
        'bitmapResolution': 1,
        'rotationCenterX': 32,
        'rotationCenterY': 32,
    }
    return costume, {f'{digest}.svg': DEFAULT_COSTUME_SVG}


def default_backdrop() -> Tuple[Dict[str, Any], Dict[str, bytes]]:
    """生成一个纯白默认背景，保证项目在 Scratch 里能正常打开"""
    digest = hashlib.md5(DEFAULT_BACKDROP_SVG).hexdigest()
    costume = {
        'name': 'backdrop1',
        'assetId': digest,
        'md5ext': f'{digest}.svg',
        'dataFormat': 'svg',
        'bitmapResolution': 1,
        'rotationCenterX': 240,
        'rotationCenterY': 180,
    }
    return costume, {f'{digest}.svg': DEFAULT_BACKDROP_SVG}


class GeneralPythonParser(PythonParser):
    """把普通 Python 脚本解析为 Scratch IR"""

    # 这些调用可以交给父类的DSL表达式解析器（math/类型转换等）
    PASSTHROUGH_CALLS = {
        'abs', 'round', 'str', 'int', 'float',
        'floor', 'ceiling', 'sqrt', 'sin', 'cos', 'tan', 'asin', 'acos',
        'atan', 'log', 'ln', 'randint', 'random',
    }

    def __init__(self):
        super().__init__()
        self.warnings: Dict[str, int] = {}
        self._pending: List[Statement] = []
        self._user_functions: Dict[str, Dict[str, Any]] = {}
        self._result_vars: Dict[str, str] = {}
        self._list_vars: set = set()
        self._current_function: Optional[str] = None
        self._loop_serial = 0
        self._loop_stack: List[Dict[str, Any]] = []
        self._temp_serial = 0
        self._string_vars: set = set()

    # ---------- 基础工具 ----------

    def warn(self, feature: str):
        self.warnings[feature] = self.warnings.get(feature, 0) + 1

    def _chain(self, statements: List[Statement]) -> Optional[Statement]:
        """把语句列表串成 next 链；保留语句自身已有的链（for/return 会产生）"""
        previous = None
        for stmt in statements:
            if previous is not None:
                tail = previous
                while tail.next is not None:
                    tail = tail.next
                tail.next = stmt
            previous = stmt
        return statements[0] if statements else None

    def _parse_stmt_list(self, nodes: List[ast.stmt]) -> List[Statement]:
        """解析语句列表，并把表达式里提升出来的调用语句插到对应位置

        在循环体内：一旦某条语句可能执行 break/continue，后续语句会被包进
        `如果 <没有 break 且没有 continue>` 里，保证控制流立刻生效。
        """
        result: List[Statement] = []
        target: List[Statement] = result
        for node in nodes:
            saved = self._pending
            self._pending = []
            context = self._loop_stack[-1] if self._loop_stack else None
            if context is not None:
                context['saw_control'] = False
            try:
                stmt = self._parse_statement(node)
                pending = self._pending
            finally:
                self._pending = saved
            target.extend(pending)
            if stmt is not None:
                target.append(stmt)
            if context is not None and context['saw_control']:
                # 后续语句必须等 break/continue 标志检查通过才执行；
                # 用嵌套的“如果”保证同一层里多次控制流也正确。
                nested = Statement(type=BlockType.IF,
                                   condition=self._loop_guard(context))
                target.append(nested)
                target = nested.body
        return result

    @staticmethod
    def _loop_guard(context: Dict[str, Any]) -> Expr:
        return Expr(
            ExprType.AND,
            left=Expr(ExprType.NOT, right=make_variable(context['break'])),
            right=Expr(ExprType.NOT, right=make_variable(context['continue'])))

    def _new_loop_context(self) -> Dict[str, Any]:
        self._loop_serial += 1
        return {
            'break': f'__py_break_{self._loop_serial}',
            'continue': f'__py_continue_{self._loop_serial}',
            'used': False,
            'saw_control': False,
        }

    def _loop_flags_init(self, context: Dict[str, Any]) -> List[Statement]:
        self.sprite.variables[context['break']] = 0
        self.sprite.variables[context['continue']] = 0
        return [
            Statement(type=BlockType.SET_VARIABLE,
                      extra={'name': context['break']}, value=make_number(0)),
            Statement(type=BlockType.SET_VARIABLE,
                      extra={'name': context['continue']}, value=make_number(0)),
        ]

    def _parse_loop_body(self, nodes: List[ast.stmt],
                         context: Dict[str, Any]) -> List[Statement]:
        self._loop_stack.append(context)
        try:
            return self._parse_stmt_list(nodes)
        finally:
            self._loop_stack.pop()

    @staticmethod
    def _chain_list(statements: List[Statement]) -> Optional[Statement]:
        for current, following in zip(statements, statements[1:]):
            current.next = following
        return statements[0] if statements else None

    def _new_temp(self, prefix: str = '__py_tmp') -> str:
        """分配一个临时变量（Scratch 里没有局部临时变量，统一放到角色变量）"""
        self._temp_serial += 1
        name = f'{prefix}_{self._temp_serial}'
        self.sprite.variables[name] = 0
        return name

    def _py_index(self, index: Expr) -> Expr:
        """Python 0 起始下标 -> Scratch 1 起始下标"""
        if isinstance(index, Expr) and index.type == ExprType.NUMBER:
            return make_number(index.value + 1)
        return make_binary_op('+', index, make_number(1))

    def _ensure_list(self, name: str):
        self.sprite.lists.setdefault(name, [])
        self._list_vars.add(name)

    def _is_list(self, name: str) -> bool:
        return name in self._list_vars or name in self.sprite.lists

    def _is_string_expr(self, node: ast.AST) -> bool:
        """粗略判断表达式是不是字符串，用于决定 + 用连接还是数值加法"""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return True
        if isinstance(node, ast.JoinedStr):
            return True
        if isinstance(node, ast.Name):
            return node.id in self._string_vars
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return self._is_string_expr(node.left) \
                or self._is_string_expr(node.right)
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                return func.id in ('str', 'input')
            if isinstance(func, ast.Attribute):
                return func.attr in ('join', 'format', 'upper', 'lower')
        return False

    @staticmethod
    def _const_int(node: ast.AST) -> Optional[int]:
        if isinstance(node, ast.Constant) and isinstance(node.value, int) \
                and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            value = GeneralPythonParser._const_int(node.operand)
            return -value if value is not None else None
        return None

    @staticmethod
    def _const_values(node: ast.List) -> Optional[List[Any]]:
        values: List[Any] = []
        for item in node.elts:
            if isinstance(item, ast.Constant) and isinstance(
                    item.value, (int, float, str, bool)):
                values.append(item.value)
            elif isinstance(item, ast.UnaryOp) and isinstance(item.op, ast.USub):
                value = GeneralPythonParser._const_int(item)
                if value is None:
                    return None
                values.append(value)
            else:
                return None
        return values

    # ---------- 入口 ----------

    def parse_code(self, code: str, sprite_name: str = 'Python'):
        self.sprite_name = sprite_name
        self.sprite = SpriteIR(name=sprite_name)
        self.local_vars = {}
        self._procedure_meta = {}
        self._pending = []
        self._user_functions = {}
        self._result_vars = {}
        self._list_vars = set()
        self._loop_serial = 0
        self._loop_stack = []
        self._temp_serial = 0
        self._string_vars = set()
        self._current_function = None
        self.warnings = {}

        try:
            tree = ast.parse(code)
        except SyntaxError as error:
            self.warn(f'语法错误: {error.msg}')
            return self.sprite

        top_level: List[ast.stmt] = []
        functions: List[ast.FunctionDef] = []
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in node.names]
                for name in names:
                    if name.split('.')[0] not in ('math', 'random', 'time'):
                        self.warn(f'import {name}')
            elif isinstance(node, ast.FunctionDef):
                functions.append(node)
            elif isinstance(node, ast.AsyncFunctionDef):
                self.warn('async def')
            elif isinstance(node, ast.ClassDef):
                self.warn('class')
            elif isinstance(node, (ast.With, ast.Try, ast.Raise)):
                self.warn(type(node).__name__)
            else:
                top_level.append(node)

        # 预先识别列表变量，便于后续 len()/下标/for 使用
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Name) \
                    and isinstance(node.value, ast.List):
                self._list_vars.add(node.targets[0].id)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and isinstance(node.func.value, ast.Name) \
                    and node.func.attr in ('append', 'insert', 'pop', 'remove',
                                           'clear', 'sort', 'reverse', 'index',
                                           'count', 'extend', 'copy'):
                self._list_vars.add(node.func.value.id)
            elif isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Name):
                target = node.targets[0].id
                value = node.value
                if isinstance(value, ast.Call) \
                        and isinstance(value.func, ast.Attribute) \
                        and value.func.attr in ('copy', 'extend') \
                        and isinstance(value.func.value, ast.Name):
                    self._list_vars.add(target)
                    self._list_vars.add(value.func.value.id)
                elif isinstance(value, ast.Call) \
                        and isinstance(value.func, ast.Name) \
                        and value.func.id in ('sorted', 'reversed') \
                        and value.args and isinstance(value.args[0], ast.Name):
                    self._list_vars.add(target)
                    self._list_vars.add(value.args[0].id)
            elif isinstance(node, ast.For) and isinstance(node.target, ast.Name) \
                    and isinstance(node.iter, ast.Name):
                self._list_vars.add(node.iter.id)

        for node in functions:
            self._parse_general_function(node)

        if top_level:
            body = self._parse_stmt_list(top_level)
            if body:
                hat = Statement(type=BlockType.WHEN_FLAG_CLICKED)
                hat.next = self._chain(body)
                self.sprite.statements.insert(0, hat)

        return self.sprite

    # ---------- 函数定义 ----------

    def _parse_general_function(self, node: ast.FunctionDef):
        if node.args.vararg or node.args.kwarg or node.args.kwonlyargs:
            self.warn('可变参数函数')
            return
        if node.decorator_list:
            self.warn('函数装饰器')
        name = node.name
        args = [arg.arg for arg in node.args.args]
        result_var = f'__py_ret_{name}'
        self.sprite.variables[result_var] = 0
        self._result_vars[name] = result_var
        meta = {
            'name': name,
            'args': args,
            'arg_types': ['s'] * len(args),
            'warp': False,
        }
        self._user_functions[name] = meta
        self._procedure_meta[name] = meta
        stmt = Statement(type=BlockType.PROCEDURE_DEFINE, extra=meta)

        previous_args = self._procedure_args
        previous_function = self._current_function
        self._procedure_args = {arg: arg for arg in args}
        self._current_function = name
        try:
            stmt.body = self._parse_stmt_list(node.body)
        finally:
            self._procedure_args = previous_args
            self._current_function = previous_function
        self.sprite.add_statement(stmt)

    # ---------- 语句 ----------

    def _parse_statement(self, node: ast.AST) -> Optional[Statement]:
        if isinstance(node, ast.Break):
            return self._parse_break_or_continue(node, 'break')
        if isinstance(node, ast.Continue):
            return self._parse_break_or_continue(node, 'continue')
        if isinstance(node, ast.FunctionDef):
            self.warn('嵌套函数')
            return None
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal)):
            return None
        if isinstance(node, ast.Return):
            return self._parse_return(node)
        if isinstance(node, ast.AnnAssign):
            if node.value is None:
                return None
            fake = ast.Assign(targets=[node.target], value=node.value)
            ast.copy_location(fake, node)
            return self._parse_assignment(fake)
        if isinstance(node, (ast.Assert, ast.Try, ast.With, ast.Raise)):
            self.warn(type(node).__name__)
            return None
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            return None  # docstring / 无副作用的常量
        return super()._parse_statement(node)

    def _parse_break_or_continue(self, node: ast.stmt, kind: str) -> Optional[Statement]:
        if not self._loop_stack:
            self.warn(f'循环外 {kind}')
            return None
        context = self._loop_stack[-1]
        context['used'] = True
        context['saw_control'] = True
        return Statement(type=BlockType.SET_VARIABLE,
                         extra={'name': context[kind]}, value=make_number(1))

    def _parse_return(self, node: ast.Return) -> Optional[Statement]:
        func_name = self._current_function
        if func_name is None:
            self.warn('顶层 return')
            return Statement(type=BlockType.STOP, extra={'option': 'this script'})
        if node.value is None:
            return Statement(type=BlockType.STOP, extra={'option': 'this script'})
        value = self._parse_expr_to_ir(node.value)
        set_stmt = Statement(type=BlockType.SET_VARIABLE,
                             extra={'name': self._result_vars[func_name]},
                             value=value)
        set_stmt.next = Statement(type=BlockType.STOP,
                                  extra={'option': 'this script'})
        return set_stmt

    def _parse_if(self, node: ast.If) -> Statement:
        condition = self._parse_expr_to_ir(node.test)
        if node.orelse:
            stmt = Statement(type=BlockType.IF_ELSE, condition=condition)
            stmt.body = self._parse_stmt_list(node.body)
            if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
                stmt.else_body = [self._parse_if(node.orelse[0])]
            else:
                stmt.else_body = self._parse_stmt_list(node.orelse)
            return stmt
        stmt = Statement(type=BlockType.IF, condition=condition)
        stmt.body = self._parse_stmt_list(node.body)
        return stmt

    def _parse_while_loop(self, node: ast.While) -> Optional[Statement]:
        if isinstance(node.test, ast.Constant) and node.test.value is False:
            return None
        if node.orelse:
            self.warn('循环 else')
        is_forever = isinstance(node.test, ast.Constant) and node.test.value is True

        # 条件里可能包含 min/sum/函数调用等需要提升成语句的表达式
        saved = self._pending
        self._pending = []
        condition = None if is_forever else self._parse_expr_to_ir(node.test)
        condition_stmts = self._pending
        self._pending = saved

        context = self._new_loop_context()
        body = self._parse_loop_body(node.body, context)

        if condition_stmts and condition is not None:
            # 条件每轮都要重新求值：放进循环体开头，用 break 标志结束循环
            statements = self._loop_flags_init(context)
            loop = Statement(type=BlockType.REPEAT_UNTIL,
                             condition=make_variable(context['break']))
            failed = Statement(
                type=BlockType.IF,
                condition=Expr(ExprType.NOT, right=condition))
            failed.body = [Statement(type=BlockType.SET_VARIABLE,
                                     extra={'name': context['break']},
                                     value=make_number(1))]
            guarded = Statement(type=BlockType.IF,
                                condition=self._loop_guard(context))
            guarded.body = body
            loop.body = list(condition_stmts) + [
                failed, guarded,
                Statement(type=BlockType.SET_VARIABLE,
                          extra={'name': context['continue']},
                          value=make_number(0)),
            ]
            statements.append(loop)
            return self._chain_list(statements)

        if context['used']:
            if condition is None:
                loop_condition = make_variable(context['break'])
            else:
                loop_condition = Expr(
                    ExprType.OR,
                    left=Expr(ExprType.NOT, right=condition),
                    right=make_variable(context['break']))
            loop = Statement(type=BlockType.REPEAT_UNTIL,
                             condition=loop_condition)
            body.append(Statement(type=BlockType.SET_VARIABLE,
                                  extra={'name': context['continue']},
                                  value=make_number(0)))
            loop.body = body
            return self._chain_list(self._loop_flags_init(context) + [loop])

        stmt = Statement(type=BlockType.FOREVER) if is_forever else Statement(
            type=BlockType.REPEAT_UNTIL,
            condition=Expr(ExprType.NOT, right=condition))
        stmt.body = body
        return stmt

    def _parse_for_loop(self, node: ast.For) -> Optional[Statement]:
        if node.orelse:
            self.warn('循环 else')

        # for i, v in enumerate(...)：解构目标必须恰好两个名字
        enumerate_var: Optional[str] = None
        if isinstance(node.target, ast.Tuple):
            if len(node.target.elts) != 2 or not all(
                    isinstance(item, ast.Name) for item in node.target.elts):
                self.warn('for 解构赋值')
                return None
            enumerate_var = node.target.elts[0].id
            var = node.target.elts[1].id
        elif isinstance(node.target, ast.Name):
            var = node.target.id
        else:
            self.warn('for 解构赋值')
            return None

        iterable = node.iter

        # for x in range(...)
        if isinstance(iterable, ast.Call) and isinstance(iterable.func, ast.Name) \
                and iterable.func.id == 'range':
            if enumerate_var is not None:
                self.warn('enumerate(range(...))')
                return None
            return self._parse_range_loop(var, iterable.args, node.body)

        # for i, v in enumerate(<列表/字符串/字面量>, start)
        if isinstance(iterable, ast.Call) and isinstance(iterable.func, ast.Name) \
                and iterable.func.id == 'enumerate':
            if enumerate_var is None:
                self.warn('for 元组目标 enumerate')
                return None
            if not 1 <= len(iterable.args) <= 2:
                self.warn('enumerate 参数数量')
                return None
            start = (self._parse_expr_to_ir(iterable.args[1])
                     if len(iterable.args) == 2 else None)
            inner = iterable.args[0]
            if isinstance(inner, ast.Constant) and isinstance(inner.value, str):
                return self._parse_string_loop(
                    var, make_string(inner.value), node.body, enumerate_var,
                    start)
            if isinstance(inner, ast.Name):
                if self._is_list(inner.id):
                    return self._parse_list_loop(
                        var, inner.id, node.body, enumerate_var, start)
                return self._parse_string_loop(
                    var, make_variable(inner.id), node.body, enumerate_var,
                    start)
            if isinstance(inner, ast.List):
                list_name = self._literal_list(inner)
                if list_name is None:
                    return None
                return self._parse_list_loop(
                    var, list_name, node.body, enumerate_var, start)
            if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name) \
                    and inner.func.id in ('sorted', 'reversed'):
                list_name = self._prepare_sorted_iterable(inner)
                if list_name is None:
                    return None
                return self._parse_list_loop(
                    var, list_name, node.body, enumerate_var, start)
            self.warn('enumerate 其它可迭代对象')
            return None

        if enumerate_var is not None:
            self.warn('for 元组目标')
            return None

        # for x in sorted(...) / reversed(...)
        if isinstance(iterable, ast.Call) and isinstance(iterable.func, ast.Name) \
                and iterable.func.id in ('sorted', 'reversed'):
            list_name = self._prepare_sorted_iterable(iterable)
            if list_name is None:
                return None
            return self._parse_list_loop(var, list_name, node.body)

        # for x in <list_name>
        if isinstance(iterable, ast.Name):
            if self._is_list(iterable.id):
                return self._parse_list_loop(var, iterable.id, node.body)
            # 非列表变量按字符串处理：for ch in text
            return self._parse_string_loop(var, make_variable(iterable.id),
                                           node.body)

        # for x in "字符串字面量"
        if isinstance(iterable, ast.Constant) and isinstance(iterable.value, str):
            return self._parse_string_loop(var, make_string(iterable.value),
                                           node.body)

        # for x in [字面量列表]
        if isinstance(iterable, ast.List):
            list_name = self._literal_list(iterable)
            if list_name is None:
                return None
            return self._parse_list_loop(var, list_name, node.body)

        self.warn('for 其它可迭代对象')
        return None

    def _literal_list(self, node: ast.List) -> Optional[str]:
        """把列表字面量落到一个隐藏的 Scratch 列表里，返回列表名"""
        values = self._const_values(node)
        if values is None:
            self.warn('for 动态列表字面量')
            return None
        self._loop_serial += 1
        list_name = f'__py_list_{self._loop_serial}'
        self.sprite.lists[list_name] = values
        self._list_vars.add(list_name)
        return list_name

    def _copy_list_statements(self, source: str, target: str) -> List[Statement]:
        """把 source 列表逐项复制到 target（target 先清空）"""
        self.sprite.lists.setdefault(target, [])
        self._list_vars.add(target)
        cursor = self._new_temp()
        loop = Statement(
            type=BlockType.REPEAT,
            value=Expr(ExprType.LENGTH_OF_LIST, name=source))
        loop.body = [
            Statement(type=BlockType.ADD_TO_LIST,
                      value=make_list_access(source, make_binary_op(
                          '+', make_variable(cursor), make_number(1))),
                      extra={'name': target}),
            Statement(type=BlockType.CHANGE_VARIABLE, extra={'name': cursor},
                      value=make_number(1)),
        ]
        return [
            Statement(type=BlockType.DELETE_ALL_FROM_LIST, extra={'name': target}),
            Statement(type=BlockType.SET_VARIABLE, extra={'name': cursor},
                      value=make_number(0)),
            loop,
        ]

    def _sorted_reverse(self, node: ast.Call) -> Optional[bool]:
        """读取 sorted(..., reverse=True/False)；不支持的参数返回 None"""
        reverse = False
        for keyword in node.keywords:
            if keyword.arg == 'reverse':
                if isinstance(keyword.value, ast.Constant):
                    reverse = bool(keyword.value.value)
                else:
                    return None
            else:
                self.warn(f'sorted 参数 {keyword.arg}')
                return None
        return reverse

    def _prepare_sorted_iterable(self, node: ast.Call) -> Optional[str]:
        """sorted(...)/reversed(...) -> 一个隐藏列表（副本已排序/反转）"""
        if not node.args:
            self.warn(f'内置函数 {node.func.id}')
            return None
        inner = node.args[0]
        if isinstance(inner, ast.Name) and self._is_list(inner.id):
            source = inner.id
        elif isinstance(inner, ast.List):
            source = self._literal_list(inner)
            if source is None:
                return None
        elif isinstance(inner, ast.Constant) and isinstance(inner.value, str):
            self._loop_serial += 1
            source = f'__py_iterlit_{self._loop_serial}'
            self.sprite.lists[source] = list(inner.value)
            self._list_vars.add(source)
        elif isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name) \
                and inner.func.id in ('sorted', 'reversed'):
            source = self._prepare_sorted_iterable(inner)
            if source is None:
                return None
        else:
            self.warn(f'内置函数 {node.func.id}')
            return None

        self._loop_serial += 1
        target = f'__py_iter_{self._loop_serial}'
        self._pending.extend(self._copy_list_statements(source, target))

        if node.func.id == 'sorted':
            reverse = self._sorted_reverse(node)
            if reverse is None:
                self.warn('sorted reverse 参数')
                reverse = False
            method = 'sort'
        else:
            if len(node.args) > 1:
                self.warn('reversed 参数数量')
            method = 'reverse'
            reverse = False

        call = ast.Call(
            func=ast.Attribute(value=ast.Name(id=target), attr=method),
            args=[], keywords=[])
        ast.fix_missing_locations(call)
        self._parse_list_method(target, call, want_value=False)

        if reverse:
            flip = ast.Call(
                func=ast.Attribute(value=ast.Name(id=target), attr='reverse'),
                args=[], keywords=[])
            ast.fix_missing_locations(flip)
            self._parse_list_method(target, flip, want_value=False)
        return target

    def _parse_range_loop(self, var: str, args: List[ast.expr],
                          body: List[ast.stmt]) -> Optional[Statement]:
        values = [self._const_int(arg) for arg in args]
        if len(args) == 1:
            start = make_number(0)
            step = make_number(1)
            if values[0] is None:
                count = self._parse_expr_to_ir(args[0])
            else:
                count = make_number(max(0, values[0]))
        elif len(args) == 2:
            start = self._parse_expr_to_ir(args[0])
            step = make_number(1)
            if values[0] is not None and values[1] is not None:
                count = make_number(max(0, values[1] - values[0]))
            else:
                count = make_binary_op('-', self._parse_expr_to_ir(args[1]), start)
        elif len(args) == 3:
            # 支持动态起止和步长：次数 = ceil((stop - start) / step)
            if values[2] == 0:
                self.warn('range 步长为0')
                return None
            start = self._parse_expr_to_ir(args[0])
            stop = self._parse_expr_to_ir(args[1])
            step = self._parse_expr_to_ir(args[2])
            count = Expr(
                ExprType.CEILING,
                right=make_binary_op(
                    '/', make_binary_op('-', stop, start), step))
        else:
            self.warn('range 参数数量')
            return None

        context = self._new_loop_context()
        parsed_body = self._parse_loop_body(body, context)
        if context['used']:
            counter = f'__py_i_{self._loop_serial}'
            self.sprite.variables[counter] = 0
            init = [Statement(type=BlockType.SET_VARIABLE,
                              extra={'name': var}, value=start),
                    Statement(type=BlockType.SET_VARIABLE,
                              extra={'name': counter}, value=make_number(0))]
            init.extend(self._loop_flags_init(context))
            loop = Statement(
                type=BlockType.REPEAT_UNTIL,
                condition=Expr(
                    ExprType.OR,
                    left=Expr(ExprType.NOT, right=Expr(
                        ExprType.LESS_THAN,
                        left=make_variable(counter), right=count)),
                    right=make_variable(context['break'])))
            parsed_body.append(Statement(
                type=BlockType.SET_VARIABLE,
                extra={'name': context['continue']}, value=make_number(0)))
            parsed_body.append(Statement(
                type=BlockType.CHANGE_VARIABLE,
                extra={'name': counter}, value=make_number(1)))
            parsed_body.append(Statement(
                type=BlockType.CHANGE_VARIABLE,
                extra={'name': var}, value=step))
            loop.body = parsed_body
            return self._chain_list(init + [loop])

        init = Statement(type=BlockType.SET_VARIABLE,
                         extra={'name': var}, value=start)
        loop = Statement(type=BlockType.REPEAT, value=count)
        loop.body = parsed_body
        loop.body.append(Statement(type=BlockType.CHANGE_VARIABLE,
                                   extra={'name': var}, value=step))
        init.next = loop
        return init

    def _parse_list_loop(self, var: str, list_name: str,
                         body: List[ast.stmt],
                         enumerate_var: Optional[str] = None,
                         enumerate_start: Optional[Expr] = None) -> Statement:
        context = self._new_loop_context()
        parsed_body = self._parse_loop_body(body, context)
        index_var = f'__py_idx_{self._loop_serial}'
        self.sprite.variables[index_var] = 0
        init = Statement(type=BlockType.SET_VARIABLE,
                         extra={'name': index_var}, value=make_number(0))
        prefix: List[Statement] = []
        if enumerate_var is not None:
            # Python 的 enumerate 下标从 0 开始，内部计数器正好也是 0 起始
            value: Expr = make_variable(index_var)
            if enumerate_start is not None:
                value = make_binary_op('+', value, enumerate_start)
            prefix.append(Statement(type=BlockType.SET_VARIABLE,
                                    extra={'name': enumerate_var},
                                    value=value))
        first = Statement(
            type=BlockType.SET_VARIABLE, extra={'name': var},
            value=make_list_access(
                list_name,
                make_binary_op('+', make_variable(index_var), make_number(1))))

        if context['used']:
            statements = [
                init,
                Statement(type=BlockType.SET_VARIABLE,
                          extra={'name': context['break']}, value=make_number(0)),
                Statement(type=BlockType.SET_VARIABLE,
                          extra={'name': context['continue']}, value=make_number(0)),
            ]
            loop = Statement(
                type=BlockType.REPEAT_UNTIL,
                condition=Expr(
                    ExprType.OR,
                    left=Expr(ExprType.NOT, right=Expr(
                        ExprType.LESS_THAN,
                        left=make_variable(index_var),
                        right=Expr(ExprType.LENGTH_OF_LIST, name=list_name))),
                    right=make_variable(context['break'])))
            loop.body = prefix + [first] + parsed_body
            loop.body.append(Statement(
                type=BlockType.SET_VARIABLE,
                extra={'name': context['continue']}, value=make_number(0)))
            loop.body.append(Statement(
                type=BlockType.CHANGE_VARIABLE,
                extra={'name': index_var}, value=make_number(1)))
            statements.append(loop)
            return self._chain_list(statements)

        loop = Statement(type=BlockType.REPEAT,
                         value=Expr(ExprType.LENGTH_OF_LIST, name=list_name))
        loop.body = prefix + [first] + parsed_body
        loop.body.append(Statement(type=BlockType.CHANGE_VARIABLE,
                                   extra={'name': index_var},
                                   value=make_number(1)))
        init.next = loop
        return init

    def _parse_string_loop(self, var: str, string_expr: Expr,
                           body: List[ast.stmt],
                           enumerate_var: Optional[str] = None,
                           enumerate_start: Optional[Expr] = None) -> Statement:
        """for ch in "abc"：用“第 n 个字符”积木按索引遍历字符串"""
        context = self._new_loop_context()
        parsed_body = self._parse_loop_body(body, context)
        self._string_vars.add(var)
        counter = f'__py_ci_{self._loop_serial}'
        self.sprite.variables[counter] = 0
        init = Statement(type=BlockType.SET_VARIABLE,
                         extra={'name': counter}, value=make_number(0))

        prefix: List[Statement] = []
        if enumerate_var is not None:
            value: Expr = make_variable(counter)
            if enumerate_start is not None:
                value = make_binary_op('+', value, enumerate_start)
            prefix.append(Statement(type=BlockType.SET_VARIABLE,
                                    extra={'name': enumerate_var},
                                    value=value))
        prefix.append(Statement(
            type=BlockType.SET_VARIABLE, extra={'name': var},
            value=Expr(ExprType.LETTER_OF,
                       left=make_binary_op('+', make_variable(counter),
                                           make_number(1)),
                       right=string_expr)))

        if context['used']:
            statements = self._loop_flags_init(context)
            statements.insert(0, init)
            loop = Statement(
                type=BlockType.REPEAT_UNTIL,
                condition=Expr(
                    ExprType.OR,
                    left=Expr(ExprType.NOT, right=Expr(
                        ExprType.LESS_THAN,
                        left=make_variable(counter),
                        right=Expr(ExprType.LENGTH_OF_STRING,
                                   right=string_expr))),
                    right=make_variable(context['break'])))
            loop.body = prefix + parsed_body
            loop.body.append(Statement(
                type=BlockType.SET_VARIABLE,
                extra={'name': context['continue']}, value=make_number(0)))
            loop.body.append(Statement(
                type=BlockType.CHANGE_VARIABLE,
                extra={'name': counter}, value=make_number(1)))
            statements.append(loop)
            return self._chain_list(statements)

        loop = Statement(
            type=BlockType.REPEAT,
            value=Expr(ExprType.LENGTH_OF_STRING, right=string_expr))
        loop.body = prefix + parsed_body
        loop.body.append(Statement(type=BlockType.CHANGE_VARIABLE,
                                   extra={'name': counter},
                                   value=make_number(1)))
        init.next = loop
        return init

    def _parse_assignment(self, node: ast.Assign) -> Optional[Statement]:
        if len(node.targets) > 1:
            # a = b = 0：右侧只求值一次，再依次赋值
            if not all(isinstance(item, ast.Name) for item in node.targets):
                self.warn('链式解构赋值')
                return None
            value = self._parse_expr_to_ir(node.value)
            if self._is_string_expr(node.value):
                for item in node.targets:
                    self._string_vars.add(item.id)
            statements = [
                Statement(type=BlockType.SET_VARIABLE,
                          extra={'name': item.id}, value=value)
                for item in node.targets
            ]
            for current, following in zip(statements, statements[1:]):
                current.next = following
            return statements[0]
        target = node.targets[0]

        # 元组交换/解构：a, b = b, a
        if isinstance(target, ast.Tuple) and isinstance(
                node.value, (ast.Tuple, ast.List)) \
                and len(target.elts) == len(node.value.elts) \
                and all(isinstance(item, ast.Name) for item in target.elts):
            statements: List[Statement] = []
            temps: List[str] = []
            for element in node.value.elts:
                # 每个右侧表达式单独收集提升语句，避免自制积木返回值互相覆盖
                saved = self._pending
                self._pending = []
                expr = self._parse_expr_to_ir(element)
                pending = self._pending
                self._pending = saved
                statements.extend(pending)
                temp = self._new_temp()
                statements.append(Statement(type=BlockType.SET_VARIABLE,
                                            extra={'name': temp}, value=expr))
                temps.append(temp)
            for item, element in zip(target.elts, node.value.elts):
                if self._is_string_expr(element):
                    self._string_vars.add(item.id)
            for item, temp in zip(target.elts, temps):
                statements.append(Statement(type=BlockType.SET_VARIABLE,
                                            extra={'name': item.id},
                                            value=make_variable(temp)))
            return self._chain_list(statements)

        # 列表按值拷贝：alias = old_list（Python 语义是复制，不是别名）
        if isinstance(target, ast.Name) and isinstance(node.value, ast.Name) \
                and self._is_list(node.value.id) and node.value.id != target.id:
            return self._chain_list(
                self._copy_list_statements(node.value.id, target.id))

        # b = a.copy() / b = sorted(a) / b = reversed(a)
        if isinstance(target, ast.Name) and isinstance(node.value, ast.Call):
            value = node.value
            if isinstance(value.func, ast.Attribute) \
                    and value.func.attr == 'copy' \
                    and isinstance(value.func.value, ast.Name) \
                    and self._is_list(value.func.value.id):
                return self._chain_list(
                    self._copy_list_statements(value.func.value.id, target.id))
            if isinstance(value.func, ast.Name) \
                    and value.func.id in ('sorted', 'reversed'):
                prepared = self._prepare_sorted_iterable(value)
                if prepared is None:
                    return None
                return self._chain_list(
                    self._copy_list_statements(prepared, target.id))

        # 列表字面量：nums = [1, 2, 3]
        if isinstance(target, ast.Name) and isinstance(node.value, ast.List):
            values = self._const_values(node.value)
            if values is None:
                self.warn('动态列表字面量')
                return None
            self.sprite.lists[target.id] = values
            self._list_vars.add(target.id)
            return None

        # 列表下标赋值：nums[i] = v
        if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
            list_name = target.value.id
            self._ensure_list(list_name)
            index = self._py_index(self._parse_expr_to_ir(target.slice))
            item = self._parse_expr_to_ir(node.value)
            return Statement(type=BlockType.REPLACE_IN_LIST, value=index,
                             extra={'name': list_name, 'item': item})

        if isinstance(target, ast.Attribute):
            self.warn('对象属性赋值')
            return None

        if isinstance(target, ast.Name):
            if self._is_string_expr(node.value):
                self._string_vars.add(target.id)
            else:
                self._string_vars.discard(target.id)
        return super()._parse_assignment(node)

    def _parse_aug_assignment(self, node: ast.AugAssign) -> Optional[Statement]:
        if isinstance(node.target, ast.Name):
            name = node.target.id
            value = self._parse_expr_to_ir(node.value)
            if isinstance(node.op, ast.Add):
                if name in self._string_vars or self._is_string_expr(node.value):
                    # 字符串累加：Python 是拼接，Scratch 的“增加”会转成数字
                    self._string_vars.add(name)
                    return Statement(type=BlockType.SET_VARIABLE,
                                     extra={'name': name},
                                     value=Expr(ExprType.JOIN,
                                                left=make_variable(name),
                                                right=value))
                return Statement(type=BlockType.CHANGE_VARIABLE,
                                 extra={'name': name}, value=value)
            if isinstance(node.op, ast.Sub):
                return Statement(type=BlockType.CHANGE_VARIABLE,
                                 extra={'name': name},
                                 value=make_binary_op('-', make_number(0), value))
            if isinstance(node.op, ast.Mult):
                item = make_binary_op('*', make_variable(name), value)
            elif isinstance(node.op, ast.Div):
                item = make_binary_op('/', make_variable(name), value)
            elif isinstance(node.op, ast.FloorDiv):
                item = Expr(ExprType.FLOOR, right=make_binary_op(
                    '/', make_variable(name), value))
            elif isinstance(node.op, ast.Mod):
                item = Expr(ExprType.MOD, left=make_variable(name), right=value)
            elif isinstance(node.op, ast.Pow):
                item = self._power(make_variable(name), node.value)
            else:
                self.warn('复合赋值运算符')
                return None
            return Statement(type=BlockType.SET_VARIABLE,
                             extra={'name': name}, value=item)
        if isinstance(node.target, ast.Subscript) and isinstance(node.target.value, ast.Name):
            list_name = node.target.value.id
            self._ensure_list(list_name)
            index = self._py_index(self._parse_expr_to_ir(node.target.slice))
            operators = {
                ast.Add: '+', ast.Sub: '-', ast.Mult: '*', ast.Div: '/',
                ast.Mod: '%',
            }
            operator = operators.get(type(node.op))
            if operator is None:
                self.warn('列表复合赋值运算符')
                return None
            item = make_binary_op(operator, make_list_access(list_name, index),
                                  self._parse_expr_to_ir(node.value))
            return Statement(type=BlockType.REPLACE_IN_LIST, value=index,
                             extra={'name': list_name, 'item': item})
        return super()._parse_aug_assignment(node)

    # ---------- 运算辅助 ----------

    def _power(self, base: Expr, exponent_node: ast.expr) -> Expr:
        """Python ** -> 重复乘法（小整数指数）或 e^(b*ln(a))（一般指数）"""
        exponent = self._const_int(exponent_node)
        if exponent == 0:
            return make_number(1)
        if exponent is not None and 0 < exponent <= 16:
            result = base
            for _ in range(exponent - 1):
                result = make_binary_op('*', result, base)
            return result
        if exponent is not None and exponent < 0:
            return make_binary_op(
                '/', make_number(1),
                self._power(base, ast.Constant(value=-exponent)))
        self.warn('幂运算（非整数指数按对数近似）')
        exponent_expr = self._parse_expr_to_ir(exponent_node)
        return Expr(ExprType.EXP, right=make_binary_op(
            '*', exponent_expr, Expr(ExprType.LN, right=base)))

    @staticmethod
    def _minmax_pair(kind: str, first: Expr, second: Expr) -> Expr:
        """min = (a+b-|a-b|)/2，max = (a+b+|a-b|)/2，避免依赖条件表达式"""
        total = make_binary_op('+', first, second)
        span = Expr(ExprType.ABS, right=make_binary_op('-', first, second))
        combined = make_binary_op('-' if kind == 'min' else '+', total, span)
        return make_binary_op('/', combined, make_number(2))

    def _list_minmax(self, kind: str, list_name: str) -> Expr:
        """min(列表)/max(列表)：遍历列表，用 min/max 公式逐个归并"""
        result = self._new_temp()
        cursor = self._new_temp()
        loop = Statement(type=BlockType.REPEAT,
                         value=make_binary_op(
                             '-', Expr(ExprType.LENGTH_OF_LIST, name=list_name),
                             make_number(1)))
        loop.body = [
            Statement(type=BlockType.SET_VARIABLE, extra={'name': result},
                      value=self._minmax_pair(
                          kind, make_variable(result),
                          make_list_access(list_name,
                                           make_variable(cursor)))),
            Statement(type=BlockType.CHANGE_VARIABLE,
                      extra={'name': cursor}, value=make_number(1)),
        ]
        self._pending.extend([
            Statement(type=BlockType.SET_VARIABLE, extra={'name': result},
                      value=make_list_access(list_name, make_number(1))),
            Statement(type=BlockType.SET_VARIABLE, extra={'name': cursor},
                      value=make_number(2)),
            loop,
        ])
        return make_variable(result)

    def _minmax_expr(self, kind: str, args: List[ast.expr]) -> Expr:
        if len(args) == 1:
            target = args[0]
            if isinstance(target, ast.Name) and self._is_list(target.id):
                return self._list_minmax(kind, target.id)
            if isinstance(target, ast.List):
                list_name = self._literal_list(target)
                if list_name is not None:
                    return self._list_minmax(kind, list_name)
            self.warn(f'内置函数 {kind}')
            return make_number(0)
        if len(args) >= 2:
            result = self._parse_expr_to_ir(args[0])
            for arg in args[1:]:
                result = self._minmax_pair(kind, result,
                                           self._parse_expr_to_ir(arg))
            return result
        self.warn(f'内置函数 {kind}')
        return make_number(0)

    def _sum_expr(self, args: List[ast.expr]) -> Expr:
        if len(args) == 1 and isinstance(args[0], ast.Name) \
                and self._is_list(args[0].id):
            list_name = args[0].id
            result = self._new_temp()
            cursor = self._new_temp()
            loop = Statement(
                type=BlockType.REPEAT,
                value=Expr(ExprType.LENGTH_OF_LIST, name=list_name))
            loop.body = [
                Statement(type=BlockType.CHANGE_VARIABLE,
                          extra={'name': result},
                          value=make_list_access(list_name,
                                                 make_variable(cursor))),
                Statement(type=BlockType.CHANGE_VARIABLE,
                          extra={'name': cursor}, value=make_number(1)),
            ]
            self._pending.extend([
                Statement(type=BlockType.SET_VARIABLE,
                          extra={'name': result}, value=make_number(0)),
                Statement(type=BlockType.SET_VARIABLE,
                          extra={'name': cursor}, value=make_number(1)),
                loop,
            ])
            return make_variable(result)
        self.warn('内置函数 sum')
        return make_number(0)

    def _join_list(self, separator: Expr, list_name: str) -> Expr:
        """sep.join(列表)：用连接积木拼接，列表元素自动转成字符串"""
        result = self._new_temp()
        cursor = self._new_temp()
        join = Statement(
            type=BlockType.SET_VARIABLE, extra={'name': result},
            value=Expr(ExprType.JOIN, left=Expr(
                ExprType.JOIN, left=make_variable(result), right=separator),
                right=make_list_access(list_name, make_variable(cursor))))
        loop = Statement(type=BlockType.REPEAT,
                         value=make_binary_op(
                             '-', Expr(ExprType.LENGTH_OF_LIST, name=list_name),
                             make_number(1)))
        loop.body = [join,
                     Statement(type=BlockType.CHANGE_VARIABLE,
                               extra={'name': cursor}, value=make_number(1))]
        self._pending.extend([
            Statement(type=BlockType.SET_VARIABLE, extra={'name': result},
                      value=make_list_access(list_name, make_number(1))),
            Statement(type=BlockType.SET_VARIABLE, extra={'name': cursor},
                      value=make_number(2)),
            loop,
        ])
        return make_variable(result)

    def _parse_list_method(self, list_name: str, call: ast.Call,
                           want_value: bool) -> Optional[Expr]:
        """表达式位置的列表方法，返回读取结果的表达式（操作语句进入 pending）"""
        method = call.func.attr
        statements: List[Statement] = []
        result: Optional[Expr] = None

        if method == 'pop':
            if call.args:
                const = self._const_int(call.args[0])
                if const is not None and const < 0:
                    index = make_binary_op(
                        '+', Expr(ExprType.LENGTH_OF_LIST, name=list_name),
                        make_number(const + 1))
                else:
                    index = self._py_index(
                        self._parse_expr_to_ir(call.args[0]))
            else:
                index = Expr(ExprType.LENGTH_OF_LIST, name=list_name)
            temp = self._new_temp()
            statements.append(Statement(
                type=BlockType.SET_VARIABLE, extra={'name': temp},
                value=make_list_access(list_name, index)))
            statements.append(Statement(
                type=BlockType.DELETE_FROM_LIST, value=index,
                extra={'name': list_name}))
            result = make_variable(temp)

        elif method in ('index', 'count', 'remove'):
            item = self._parse_expr_to_ir(call.args[0]) \
                if call.args else make_string('')
            cursor = self._new_temp()
            position = make_binary_op('+', make_variable(cursor),
                                      make_number(1))
            current = make_list_access(list_name, position)
            length = Expr(ExprType.LENGTH_OF_LIST, name=list_name)
            found = Expr(
                ExprType.AND,
                left=Expr(ExprType.LESS_THAN,
                          left=make_variable(cursor), right=length),
                right=Expr(ExprType.EQUAL, left=current, right=item))
            statements.append(Statement(
                type=BlockType.SET_VARIABLE, extra={'name': cursor},
                value=make_number(0)))

            if method == 'count':
                seen = self._new_temp()
                statements.append(Statement(
                    type=BlockType.SET_VARIABLE, extra={'name': seen},
                    value=make_number(0)))
                loop = Statement(
                    type=BlockType.REPEAT,
                    value=Expr(ExprType.LENGTH_OF_LIST, name=list_name))
                tally = Statement(
                    type=BlockType.IF,
                    condition=Expr(ExprType.EQUAL,
                                   left=make_list_access(
                                       list_name, position),
                                   right=item))
                tally.body = [Statement(type=BlockType.CHANGE_VARIABLE,
                                        extra={'name': seen},
                                        value=make_number(1))]
                loop.body = [tally, Statement(
                    type=BlockType.CHANGE_VARIABLE,
                    extra={'name': cursor}, value=make_number(1))]
                statements.append(loop)
                result = make_variable(seen)
            else:
                search = Statement(
                    type=BlockType.REPEAT_UNTIL,
                    condition=Expr(
                        ExprType.OR,
                        left=Expr(ExprType.NOT, right=Expr(
                            ExprType.LESS_THAN,
                            left=make_variable(cursor), right=length)),
                        right=Expr(ExprType.EQUAL,
                                   left=make_list_access(
                                       list_name, position),
                                   right=item)))
                search.body = [Statement(type=BlockType.CHANGE_VARIABLE,
                                         extra={'name': cursor},
                                         value=make_number(1))]
                statements.append(search)
                if method == 'index':
                    target = self._new_temp()
                    statements.append(Statement(
                        type=BlockType.SET_VARIABLE, extra={'name': target},
                        value=make_number(-1)))
                    hit = Statement(type=BlockType.IF, condition=found)
                    hit.body = [Statement(type=BlockType.SET_VARIABLE,
                                          extra={'name': target},
                                          value=make_variable(cursor))]
                    statements.append(hit)
                    result = make_variable(target)
                else:
                    # remove：找到后删除；没找到时 Python 会抛异常，这里保持静默
                    hit = Statement(type=BlockType.IF, condition=found)
                    hit.body = [Statement(type=BlockType.DELETE_FROM_LIST,
                                          value=make_binary_op(
                                              '+', make_variable(cursor),
                                              make_number(1)),
                                          extra={'name': list_name})]
                    statements.append(hit)
                    result = make_string('')

        elif method == 'reverse':
            cursor = self._new_temp()
            temp = self._new_temp()
            length = Expr(ExprType.LENGTH_OF_LIST, name=list_name)
            position = make_binary_op('+', make_variable(cursor),
                                      make_number(1))
            mirror = make_binary_op('-', length, make_variable(cursor))
            loop = Statement(
                type=BlockType.REPEAT,
                value=Expr(ExprType.FLOOR, right=make_binary_op(
                    '/', length, make_number(2))))
            loop.body = [
                Statement(type=BlockType.SET_VARIABLE, extra={'name': temp},
                          value=make_list_access(list_name, position)),
                Statement(type=BlockType.REPLACE_IN_LIST,
                          value=position,
                          extra={'name': list_name,
                                 'item': make_list_access(list_name, mirror)}),
                Statement(type=BlockType.REPLACE_IN_LIST,
                          value=mirror,
                          extra={'name': list_name,
                                 'item': make_variable(temp)}),
                Statement(type=BlockType.CHANGE_VARIABLE,
                          extra={'name': cursor}, value=make_number(1)),
            ]
            statements.append(Statement(
                type=BlockType.SET_VARIABLE, extra={'name': cursor},
                value=make_number(0)))
            statements.append(loop)
            result = make_string('')

        elif method == 'sort':
            outer = self._new_temp()
            inner = self._new_temp()
            temp = self._new_temp()
            length = Expr(ExprType.LENGTH_OF_LIST, name=list_name)

            def left_item() -> Expr:
                return make_list_access(list_name, make_binary_op(
                    '+', make_variable(inner), make_number(1)))

            def right_item() -> Expr:
                return make_list_access(list_name, make_binary_op(
                    '+', make_variable(inner), make_number(2)))

            swap = Statement(
                type=BlockType.IF,
                condition=Expr(ExprType.GREATER_THAN,
                               left=left_item(), right=right_item()))
            swap.body = [
                Statement(type=BlockType.SET_VARIABLE, extra={'name': temp},
                          value=left_item()),
                Statement(type=BlockType.REPLACE_IN_LIST,
                          value=make_binary_op('+', make_variable(inner),
                                               make_number(1)),
                          extra={'name': list_name,
                                 'item': right_item()}),
                Statement(type=BlockType.REPLACE_IN_LIST,
                          value=make_binary_op('+', make_variable(inner),
                                               make_number(2)),
                          extra={'name': list_name,
                                 'item': make_variable(temp)}),
            ]
            inner_loop = Statement(
                type=BlockType.REPEAT,
                value=make_binary_op(
                    '-', Expr(ExprType.LENGTH_OF_LIST, name=list_name),
                    make_binary_op('+', make_variable(outer),
                                   make_number(1))))
            inner_loop.body = [
                Statement(type=BlockType.SET_VARIABLE, extra={'name': inner},
                          value=make_number(0)),
                swap,
                Statement(type=BlockType.CHANGE_VARIABLE,
                          extra={'name': inner}, value=make_number(1)),
            ]
            outer_loop = Statement(
                type=BlockType.REPEAT,
                value=make_binary_op('-', length, make_number(1)))
            outer_loop.body = [
                inner_loop,
                Statement(type=BlockType.CHANGE_VARIABLE,
                          extra={'name': outer}, value=make_number(1)),
            ]
            statements.append(Statement(
                type=BlockType.SET_VARIABLE, extra={'name': outer},
                value=make_number(0)))
            statements.append(outer_loop)
            result = make_string('')

        else:
            return None

        self._pending.extend(statements)
        if want_value and result is not None:
            return result
        return make_string('')

    # ---------- 调用与表达式 ----------

    def _parse_function_call(self, call: ast.Call) -> Optional[Statement]:
        func = call.func
        func_name = ''
        if isinstance(func, ast.Name):
            func_name = func.id
        elif isinstance(func, ast.Attribute):
            func_name = func.attr

        # 列表方法：nums.append(x) / insert / clear
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
                and self._is_list(func.value.id):
            list_name = func.value.id
            if func.attr == 'append':
                item = self._parse_expr_to_ir(call.args[0]) if call.args else make_string('')
                return Statement(type=BlockType.ADD_TO_LIST, value=item,
                                 extra={'name': list_name})
            if func.attr == 'insert':
                index = self._parse_expr_to_ir(call.args[0]) if call.args else make_number(0)
                item = self._parse_expr_to_ir(call.args[1]) if len(call.args) > 1 else make_string('')
                return Statement(type=BlockType.INSERT_IN_LIST,
                                 value=self._py_index(index),
                                 extra={'name': list_name, 'item': item})
            if func.attr == 'clear':
                return Statement(type=BlockType.DELETE_ALL_FROM_LIST,
                                 extra={'name': list_name})
            if func.attr == 'extend' and call.args:
                source = None
                argument = call.args[0]
                if isinstance(argument, ast.Name) and self._is_list(argument.id):
                    source = argument.id
                elif isinstance(argument, ast.List):
                    source = self._literal_list(argument)
                if source is None:
                    self.warn('列表方法 extend')
                    return None
                cursor = self._new_temp()
                loop = Statement(
                    type=BlockType.REPEAT,
                    value=Expr(ExprType.LENGTH_OF_LIST, name=source))
                loop.body = [
                    Statement(type=BlockType.ADD_TO_LIST,
                              value=make_list_access(source, make_binary_op(
                                  '+', make_variable(cursor), make_number(1))),
                              extra={'name': list_name}),
                    Statement(type=BlockType.CHANGE_VARIABLE,
                              extra={'name': cursor}, value=make_number(1)),
                ]
                return self._chain_list([
                    Statement(type=BlockType.SET_VARIABLE,
                              extra={'name': cursor}, value=make_number(0)),
                    loop,
                ])
            if func.attr in ('pop', 'index', 'count', 'remove',
                             'reverse', 'sort'):
                self._parse_list_method(list_name, call, want_value=False)
                return None
            self.warn(f'列表方法 {func.attr}')
            return None

        # "分隔符".join(列表)
        if isinstance(func, ast.Attribute) and func.attr == 'join' and call.args \
                and isinstance(call.args[0], ast.Name) \
                and self._is_list(call.args[0].id):
            self._join_list(self._parse_expr_to_ir(func.value),
                            call.args[0].id)
            return None

        # 字符串方法（Scratch 没有对应积木，明确记录）
        if isinstance(func, ast.Attribute) and func.attr in (
                'upper', 'lower', 'strip', 'replace', 'split', 'find',
                'startswith', 'endswith', 'format'):
            self.warn(f'字符串方法 {func.attr}')
            return None

        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
                and func.value.id == 'time' and func.attr == 'sleep':
            seconds = self._parse_expr_to_ir(call.args[0]) \
                if call.args else make_number(1)
            return Statement(type=BlockType.WAIT, value=seconds)

        if func_name == 'print':
            return Statement(type=BlockType.SAY, value=self._print_value(call.args))

        if func_name == 'input':
            prompt = self._parse_expr_to_ir(call.args[0]) if call.args else make_string('')
            return Statement(type=BlockType.ASK_AND_WAIT, value=prompt)

        if func_name in self._user_functions:
            args = [self._parse_expr_to_ir(arg) for arg in call.args]
            return Statement(type=BlockType.PROCEDURE_CALL,
                             extra={'name': func_name, 'args': args})

        if func_name in ('range', 'enumerate', 'zip', 'map', 'filter'):
            self.warn(f'迭代器 {func_name}')
            return None

        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
                and func.value.id == 'self':
            self.warn('self 方法调用')
            return None

        self.warn(f'函数调用 {func_name}')
        return None

    def _print_value(self, args: List[ast.expr]) -> Expr:
        if not args:
            return make_string('')
        value = self._parse_expr_to_ir(args[0])
        for arg in args[1:]:
            value = Expr(ExprType.JOIN, left=value,
                         right=Expr(ExprType.JOIN, left=make_string(' '),
                                    right=self._parse_expr_to_ir(arg)))
        return value

    def _parse_expr_to_ir(self, node: ast.AST) -> Expr:
        if isinstance(node, ast.JoinedStr):
            return self._joined_str(node)

        if isinstance(node, ast.IfExp):
            return self._if_expr(node)

        if isinstance(node, ast.BinOp):
            if isinstance(node.op, ast.Pow):
                return self._power(self._parse_expr_to_ir(node.left),
                                   node.right)
            if isinstance(node.op, ast.FloorDiv):
                # Python // -> floor(a / b)
                return Expr(ExprType.FLOOR, right=make_binary_op(
                    '/', self._parse_expr_to_ir(node.left),
                    self._parse_expr_to_ir(node.right)))
            if isinstance(node.op, ast.Add):
                if self._is_string_expr(node.left) \
                        or self._is_string_expr(node.right):
                    return Expr(ExprType.JOIN,
                                left=self._parse_expr_to_ir(node.left),
                                right=self._parse_expr_to_ir(node.right))

        if isinstance(node, ast.Compare):
            if len(node.ops) > 1:
                parts = []
                left_node = node.left
                for operator, comparator in zip(node.ops, node.comparators):
                    parts.append(self._compare_node(operator, left_node, comparator))
                    left_node = comparator
                result = parts[0]
                for part in parts[1:]:
                    result = Expr(ExprType.AND, left=result, right=part)
                return result
            if isinstance(node.ops[0], (ast.In, ast.NotIn)):
                return self._compare_node(node.ops[0], node.left, node.comparators[0])

        if isinstance(node, ast.Call):
            return self._parse_call_expr(node)

        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            list_name = node.value.id
            if self._is_list(list_name):
                index = self._py_index(self._parse_expr_to_ir(node.slice))
                return make_list_access(list_name, index)

        if isinstance(node, ast.List):
            self.warn('列表字面量（仅赋值时支持）')
            return make_string('')

        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                and node.value.id == 'math':
            constants = {'pi': math.pi, 'e': math.e, 'tau': math.tau}
            if node.attr in constants:
                return make_number(constants[node.attr])

        return super()._parse_expr_to_ir(node)

    def _if_expr(self, node: ast.IfExp) -> Expr:
        """a if cond else b -> 临时变量 + 如果/否则（两条分支都会先求值）"""
        condition = self._parse_expr_to_ir(node.test)
        else_value = self._parse_expr_to_ir(node.orelse)
        then_value = self._parse_expr_to_ir(node.body)
        flag = self._new_temp()
        temp = self._new_temp()
        if self._is_string_expr(node.body) or self._is_string_expr(node.orelse):
            self._string_vars.add(temp)
        branch = Statement(type=BlockType.IF, condition=make_variable(flag))
        branch.body = [Statement(type=BlockType.SET_VARIABLE,
                                 extra={'name': temp}, value=then_value)]
        self._pending.extend([
            Statement(type=BlockType.SET_VARIABLE, extra={'name': flag},
                      value=condition),
            Statement(type=BlockType.SET_VARIABLE, extra={'name': temp},
                      value=else_value),
            branch,
        ])
        return make_variable(temp)

    def _joined_str(self, node: ast.JoinedStr) -> Expr:
        """f-string -> 连接积木（支持 .Nf 格式说明）"""
        parts: List[Expr] = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(make_string(str(value.value)))
            elif isinstance(value, ast.FormattedValue):
                expr = self._parse_expr_to_ir(value.value)
                if value.format_spec is not None:
                    formatted = self._format_expr(expr, value.format_spec)
                    if formatted is None:
                        self.warn('f-string 格式说明')
                    else:
                        expr = formatted
                parts.append(expr)
            else:
                self.warn('f-string')
        if not parts:
            return make_string('')
        result = parts[0]
        for part in parts[1:]:
            result = Expr(ExprType.JOIN, left=result, right=part)
        return result

    def _format_expr(self, expr: Expr, spec_node: ast.AST) -> Optional[Expr]:
        """f-string 格式说明 -> Scratch 表达式

        只支持 ``:.Nf``：四舍五入到 N 位小数（Scratch 会省略末尾的 0）。
        """
        spec = ''
        if isinstance(spec_node, ast.JoinedStr) \
                and all(isinstance(item, ast.Constant) for item in spec_node.values):
            spec = ''.join(str(item.value) for item in spec_node.values)
        matched = re.fullmatch(r'\.(\d+)f', spec)
        if matched:
            factor = 10 ** int(matched.group(1))
            return make_binary_op(
                '/', Expr(ExprType.ROUND,
                          right=make_binary_op('*', expr,
                                               make_number(factor))),
                make_number(factor))
        if spec in ('', 'd', 's'):
            return expr
        return None

    def _compare_node(self, operator: ast.cmpop, left_node: ast.expr,
                      right_node: ast.expr) -> Expr:
        left = self._parse_expr_to_ir(left_node)
        right = self._parse_expr_to_ir(right_node)
        if isinstance(operator, (ast.In, ast.NotIn)):
            if isinstance(right_node, ast.Name) and self._is_list(right_node.id):
                contains = Expr(ExprType.LIST_CONTAINS, name=right_node.id,
                                left=left)
            else:
                # 字符串包含：Scratch 的“包含”积木是“大字符串包含小字符串”
                contains = Expr(ExprType.CONTAINS_STRING, left=right,
                                right=left)
            return Expr(ExprType.NOT, right=contains) \
                if isinstance(operator, ast.NotIn) else contains
        if isinstance(operator, ast.Lt):
            return Expr(ExprType.LESS_THAN, left=left, right=right)
        if isinstance(operator, ast.LtE):
            return Expr(ExprType.NOT, right=Expr(
                ExprType.GREATER_THAN, left=left, right=right))
        if isinstance(operator, ast.Gt):
            return Expr(ExprType.GREATER_THAN, left=left, right=right)
        if isinstance(operator, ast.GtE):
            return Expr(ExprType.NOT, right=Expr(
                ExprType.LESS_THAN, left=left, right=right))
        if isinstance(operator, (ast.Eq, ast.Is)):
            return Expr(ExprType.EQUAL, left=left, right=right)
        if isinstance(operator, (ast.NotEq, ast.IsNot)):
            return Expr(ExprType.NOT, right=Expr(
                ExprType.EQUAL, left=left, right=right))
        self.warn('比较运算符')
        return make_boolean(False)

    def _parse_delete(self, node: ast.Delete) -> Optional[Statement]:
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Subscript) \
                and isinstance(node.targets[0].value, ast.Name):
            list_name = node.targets[0].value.id
            self._ensure_list(list_name)
            index = self._py_index(
                self._parse_expr_to_ir(node.targets[0].slice))
            return Statement(type=BlockType.DELETE_FROM_LIST, value=index,
                             extra={'name': list_name})
        self.warn('del 非列表下标')
        return None

    def _parse_call_expr(self, node: ast.Call) -> Expr:
        func = node.func
        func_name = ''
        if isinstance(func, ast.Name):
            func_name = func.id
        elif isinstance(func, ast.Attribute):
            func_name = func.attr

        # 用户函数：先调用，再从结果变量读取（Scratch自制积木没有返回值）
        if func_name in self._user_functions:
            args = [self._parse_expr_to_ir(arg) for arg in node.args]
            self._pending.append(Statement(
                type=BlockType.PROCEDURE_CALL,
                extra={'name': func_name, 'args': args}))
            return make_variable(self._result_vars[func_name])

        if func_name == 'input':
            prompt = self._parse_expr_to_ir(node.args[0]) if node.args else make_string('')
            self._pending.append(Statement(type=BlockType.ASK_AND_WAIT, value=prompt))
            return Expr(ExprType.ANSWER)

        if func_name == 'len':
            if not node.args:
                return make_number(0)
            arg = node.args[0]
            if isinstance(arg, ast.Name) and self._is_list(arg.id):
                return Expr(ExprType.LENGTH_OF_LIST, name=arg.id)
            return Expr(ExprType.LENGTH_OF_STRING,
                        right=self._parse_expr_to_ir(arg))

        if func_name in ('int', 'float', 'str', 'bool'):
            return self._parse_expr_to_ir(node.args[0]) if node.args else make_string('')

        if func_name in ('min', 'max'):
            return self._minmax_expr(func_name, node.args)

        if func_name == 'sum':
            return self._sum_expr(node.args)

        # time.sleep(n) -> 等待 n 秒
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
                and func.value.id == 'time' and func.attr == 'sleep':
            seconds = self._parse_expr_to_ir(node.args[0]) \
                if node.args else make_number(1)
            self._pending.append(Statement(type=BlockType.WAIT, value=seconds))
            return make_string('')

        # random 模块
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
                and func.value.id == 'random':
            if func.attr == 'random':
                return make_random(make_number(0), make_number(1))
            if func.attr == 'randint' and len(node.args) >= 2:
                return make_random(self._parse_expr_to_ir(node.args[0]),
                                   self._parse_expr_to_ir(node.args[1]))
            if func.attr == 'uniform' and len(node.args) >= 2:
                low = self._parse_expr_to_ir(node.args[0])
                high = self._parse_expr_to_ir(node.args[1])
                span = make_binary_op('-', high, low)
                return make_binary_op(
                    '+', low,
                    make_binary_op('*', make_random(make_number(0),
                                                    make_number(1)), span))
            if func.attr == 'choice' and node.args:
                target = node.args[0]
                if isinstance(target, ast.Name) and self._is_list(target.id):
                    return make_list_access(target.id, make_string('random'))
                if isinstance(target, ast.Constant) \
                        and isinstance(target.value, str) and target.value:
                    index = make_random(make_number(1),
                                        make_number(len(target.value)))
                    return Expr(ExprType.LETTER_OF, left=index,
                                right=make_string(target.value))
            self.warn(f'random.{func.attr}')
            return make_string('')

        # pow(a, b) / math.pow(a, b) / math.fabs(x)
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
                and func.value.id == 'math':
            if func.attr == 'pow' and len(node.args) >= 2:
                return self._power(self._parse_expr_to_ir(node.args[0]),
                                   node.args[1])
            if func.attr == 'fabs' and node.args:
                return Expr(ExprType.ABS,
                            right=self._parse_expr_to_ir(node.args[0]))
        if func_name == 'pow' and len(node.args) >= 2:
            return self._power(self._parse_expr_to_ir(node.args[0]),
                               node.args[1])

        # round(x, n) -> round(x * 10^n) / 10^n
        if func_name == 'round' and len(node.args) >= 2:
            digits = self._const_int(node.args[1])
            value = self._parse_expr_to_ir(node.args[0])
            if digits is None:
                self.warn('round 动态位数')
                return value
            if digits == 0:
                return Expr(ExprType.ROUND, right=value)
            factor = 10 ** digits
            return make_binary_op(
                '/', Expr(ExprType.ROUND,
                          right=make_binary_op('*', value,
                                               make_number(factor))),
                make_number(factor))

        if func_name in ('sorted', 'reversed', 'open'):
            self.warn(f'内置函数 {func_name}')
            return make_string('')

        # 列表方法：nums.pop() / nums.index(x) / nums.count(x)
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
                and self._is_list(func.value.id):
            result = self._parse_list_method(func.value.id, node,
                                             want_value=True)
            if result is not None:
                return result
            self.warn(f'列表方法 {func_name}')
            return make_string('')

        # "分隔符".join(列表)
        if isinstance(func, ast.Attribute) and func.attr == 'join' \
                and node.args and isinstance(node.args[0], ast.Name) \
                and self._is_list(node.args[0].id):
            return self._join_list(self._parse_expr_to_ir(func.value),
                                   node.args[0].id)

        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
                and func.attr in ('upper', 'lower', 'strip', 'replace', 'split',
                                  'find', 'startswith', 'endswith', 'format'):
            self.warn(f'字符串方法 {func.attr}')
            return make_string('')

        if func_name in self.PASSTHROUGH_CALLS:
            return super()._parse_expr_to_ir(node)

        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
                and func.value.id == 'math' and func_name in self.PASSTHROUGH_CALLS:
            return super()._parse_expr_to_ir(node)

        self.warn(f'函数调用 {func_name}')
        return make_string('')


def parse_general_project(code: str, sprite_name: str = 'Python'):
    """把普通 Python 源码解析为带默认造型/背景的 ProjectIR"""
    parser = GeneralPythonParser()
    sprite = parser.parse_code(code, sprite_name)
    costume, assets = default_costume()
    sprite.costumes = [costume]
    sprite.sounds = []

    backdrop, backdrop_assets = default_backdrop()
    stage = SpriteIR(name='Stage', is_stage=True)
    stage.costumes = [backdrop]
    stage.sounds = []
    assets.update(backdrop_assets)

    project = ProjectIR()
    project.add_sprite(stage)
    project.add_sprite(sprite)
    project.assets = assets
    project.warnings = dict(parser.warnings)
    return project
