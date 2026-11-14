"""通用 Python -> Scratch 转换（实验性）

与 ``python_parser.PythonParser`` 不同：后者专门解析本转换器生成的
Scratch DSL（``ScratchSprite`` 类、``when_green_flag``、``self.move()`` 等），
准确率最高；本模块尝试把**普通 Python 脚本**翻译成 Scratch 3 积木。

支持的核心子集：
- 顶层语句 -> 绿旗脚本
- ``def`` 函数 -> 自制积木；返回值写入 ``__py_ret_<函数名>`` 变量
- 变量、赋值/增量赋值、算术/比较/布尔表达式
- ``if/elif/else``、``while``、``for ... in range(...)``、``for ... in 列表``
- 列表字面量、``append/insert/clear``、下标读写
- ``print`` -> 说话；``input`` -> 询问并等待
- ``len``、``str/int/float``、``abs/round``、常用 ``math`` 函数

不支持：类、异常、生成器、装饰器、多返回值、``break/continue`` 等，
这些会记入转换报告，而不是静默丢失。
"""

import ast
import hashlib
from typing import Any, Dict, List, Optional, Tuple

from ir import (
    BlockType, ExprType, Expr, Statement, ProjectIR, SpriteIR,
    make_number, make_string, make_boolean, make_variable,
    make_binary_op, make_list_access,

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
                                           'clear', 'sort', 'reverse'):
                self._list_vars.add(node.func.value.id)
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
        is_forever = isinstance(node.test, ast.Constant) and node.test.value is True
        condition = None if is_forever else self._parse_expr_to_ir(node.test)

        context = self._new_loop_context()
        body = self._parse_loop_body(node.body, context)
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
        if not isinstance(node.target, ast.Name):
            self.warn('for 解构赋值')
            return None
        var = node.target.id
        iterable = node.iter

        # for x in range(...)
        if isinstance(iterable, ast.Call) and isinstance(iterable.func, ast.Name) \
                and iterable.func.id == 'range':
            return self._parse_range_loop(var, iterable.args, node.body)

        # for x in <list_name>
        if isinstance(iterable, ast.Name):
            list_name = iterable.id
            self._ensure_list(list_name)
            return self._parse_list_loop(var, list_name, node.body)

        # for x in [字面量列表]
        if isinstance(iterable, ast.List):
            values = self._const_values(iterable)
            if values is None:
                self.warn('for 动态列表字面量')
                return None
            self._loop_serial += 1
            list_name = f'__py_list_{self._loop_serial}'
            self.sprite.lists[list_name] = values
            self._list_vars.add(list_name)
            return self._parse_list_loop(var, list_name, node.body)

        self.warn('for 其它可迭代对象')
        return None

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
                         body: List[ast.stmt]) -> Statement:
        context = self._new_loop_context()
        parsed_body = self._parse_loop_body(body, context)
        index_var = f'__py_idx_{self._loop_serial}'
        self.sprite.variables[index_var] = 0
        init = Statement(type=BlockType.SET_VARIABLE,
                         extra={'name': index_var}, value=make_number(0))
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
            loop.body = [first] + parsed_body
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
        loop.body = [first] + parsed_body
        loop.body.append(Statement(type=BlockType.CHANGE_VARIABLE,
                                   extra={'name': index_var},
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
            statements = [
                Statement(type=BlockType.SET_VARIABLE,
                          extra={'name': item.id}, value=value)
                for item in node.targets
            ]
            for current, following in zip(statements, statements[1:]):
                current.next = following
            return statements[0]
        target = node.targets[0]

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

        return super()._parse_assignment(node)

    def _parse_aug_assignment(self, node: ast.AugAssign) -> Optional[Statement]:
        if isinstance(node.target, ast.Name):
            name = node.target.id
            value = self._parse_expr_to_ir(node.value)
            if isinstance(node.op, ast.Add):
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
            self.warn(f'列表方法 {func.attr}')
            return None

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

        if isinstance(node, ast.BinOp):
            if isinstance(node.op, ast.Pow):
                self.warn('幂运算 **')
                return make_number(0)
            if isinstance(node.op, ast.FloorDiv):
                # Python // -> floor(a / b)
                return Expr(ExprType.FLOOR, right=make_binary_op(
                    '/', self._parse_expr_to_ir(node.left),
                    self._parse_expr_to_ir(node.right)))
            if isinstance(node.op, ast.Add):
                left_str = isinstance(node.left, ast.Constant) \
                    and isinstance(node.left.value, str)
                right_str = isinstance(node.right, ast.Constant) \
                    and isinstance(node.right.value, str)
                if left_str or right_str:
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

        return super()._parse_expr_to_ir(node)

    def _joined_str(self, node: ast.JoinedStr) -> Expr:
        """f-string -> 连接积木（忽略格式说明）"""
        parts: List[Expr] = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(make_string(str(value.value)))
            elif isinstance(value, ast.FormattedValue):
                if value.format_spec is not None:
                    self.warn('f-string 格式说明')
                parts.append(self._parse_expr_to_ir(value.value))
            else:
                self.warn('f-string')
        if not parts:
            return make_string('')
        result = parts[0]
        for part in parts[1:]:
            result = Expr(ExprType.JOIN, left=result, right=part)
        return result

    def _compare_node(self, operator: ast.cmpop, left_node: ast.expr,
                      right_node: ast.expr) -> Expr:
        left = self._parse_expr_to_ir(left_node)
        right = self._parse_expr_to_ir(right_node)
        if isinstance(operator, (ast.In, ast.NotIn)):
            if isinstance(right_node, ast.Name) and self._is_list(right_node.id):
                contains = Expr(ExprType.LIST_CONTAINS, name=right_node.id, left=left)
                return Expr(ExprType.NOT, right=contains) \
                    if isinstance(operator, ast.NotIn) else contains
            self.warn('in 非列表')
            return make_boolean(False)
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

        if func_name in ('min', 'max', 'sum', 'sorted', 'reversed', 'open'):
            self.warn(f'内置函数 {func_name}')
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
