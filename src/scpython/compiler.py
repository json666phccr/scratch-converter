# -*- coding: utf-8 -*-
"""ScPython -> Scratch IR 编译器。

该模块负责：

1. 把 ``.scpy`` 源码预处理为 Python AST；
2. 校验语言子集（无 class/装饰器/字典/集合/高级字符串操作等）；
3. 把事件头、初始化块、函数（自制积木）编译成 ``ir.py`` 的语句/表达式；
4. 处理列表、变量、扩展调用、宏函数复制与循环 break/continue。
"""

from __future__ import annotations

import ast
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ir import (
    BlockType, Expr, ExprType, ProjectIR, SpriteIR, Statement,
    make_boolean, make_number, make_string, make_variable,
    sanitize_name,
)

from .assets import AssetLibrary
from .errors import ScPythonError, ScPythonSyntaxError
from .extensions import (
    ExtensionBlock, ExtensionRegistry, bind_extension_args,
    builtin_extension,
)
from .preprocess import preprocess

# ===================== 规则表 =====================

_FORBIDDEN_NODES = (
    ast.ClassDef, ast.AsyncFunctionDef, ast.Lambda, ast.ListComp,
    ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.Try, ast.Raise,
    ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.Yield,
    ast.YieldFrom, ast.Await, ast.AsyncFor, ast.AsyncWith, ast.Match,
    ast.Set, ast.Dict, ast.JoinedStr, ast.FormattedValue, ast.NamedExpr,
    ast.Starred, ast.AnnAssign,
)

_LIST_METHODS = {'append', 'insert', 'clear', 'index'}
_LIST_STATEMENT_FUNCTIONS = {
    'add_to_list', 'delete_of_list', 'delete_item', 'delete_all_of_list',
    'insert_in_list', 'replace_in_list',
}
_LIST_EXPR_FUNCTIONS = {
    'item_of', 'item_number_of', 'length_of', 'contains_item',
    'list_contents',
}
_LIST_FUNCTIONS = _LIST_STATEMENT_FUNCTIONS | _LIST_EXPR_FUNCTIONS

_META_KEYS = {
    'name', 'costumes', 'sounds', 'extensions', 'x', 'y', 'direction',
    'visible', 'size', 'rotation_style', 'draggable', 'current_costume',
}

_PROPERTY_KEYS = {
    'x', 'y', 'direction', 'visible', 'size', 'rotation_style',
    'draggable', 'current_costume', 'layer_order',
}

_MATH_FUNCTIONS = {
    'sqrt': ExprType.SQRT, 'floor': ExprType.FLOOR,
    'ceiling': ExprType.CEILING, 'sin': ExprType.SIN,
    'cos': ExprType.COS, 'tan': ExprType.TAN,
    'asin': ExprType.ASIN, 'acos': ExprType.ACOS,
    'atan': ExprType.ATAN, 'ln': ExprType.LN, 'log': ExprType.LOG,
    'exp': ExprType.EXP, 'pow10': ExprType.POW10,
}

_SENSING_FUNCTIONS = {
    'answer': ExprType.ANSWER,
    'timer': ExprType.TIMER,
    'mouse_x': ExprType.MOUSE_X,
    'mouse_y': ExprType.MOUSE_Y,
    'mouse_down': ExprType.MOUSE_DOWN,
    'loudness': ExprType.LOUDNESS,
    'days_since_2000': ExprType.DAYS_SINCE_2000,
}

_PROPERTY_FUNCTIONS = {
    'x_position': 'x position',
    'y_position': 'y position',
    'direction_of_sprite': 'direction',
    'costume_number': 'costume #',
    'costume_name': 'costume name',
    'backdrop_number': 'backdrop #',
    'backdrop_name': 'backdrop name',
    'size_of_sprite': 'size',
    'volume': 'volume',
}


# ===================== 数据结构 =====================

@dataclass
class Param:
    name: str
    type: str = 's'
    default: Any = ''
    has_default: bool = False


@dataclass
class FunctionInfo:
    name: str
    node: ast.FunctionDef
    params: List[Param]
    proccode: str
    warp: bool = False
    path: str = ''
    is_macro: bool = False

    @property
    def argumentids(self) -> List[str]:
        used = set()
        result = []
        for index, param in enumerate(self.params):
            base = f"arg_{sanitize_name(param.name, 'arg')}"
            candidate = base
            suffix = 2
            while candidate in used:
                candidate = f"{base}_{suffix}"
                suffix += 1
            used.add(candidate)
            result.append(candidate)
        return result

    @property
    def argumentdefaults(self) -> List[Any]:
        return [param.default for param in self.params]


@dataclass
class ModuleInfo:
    path: str
    rel_path: str
    name: str
    is_stage: bool
    tree: ast.Module
    variables: Dict[str, Any] = field(default_factory=dict)
    lists: Dict[str, List[Any]] = field(default_factory=dict)
    declared_vars: set = field(default_factory=set)
    declared_lists: set = field(default_factory=set)
    explicit_vars: set = field(default_factory=set)
    explicit_lists: set = field(default_factory=set)
    costumes: List[str] = field(default_factory=list)
    sounds: List[str] = field(default_factory=list)
    extensions: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)
    functions: Dict[str, FunctionInfo] = field(default_factory=dict)
    scripts: List[ast.With] = field(default_factory=list)
    source_order: List[Tuple[str, Any]] = field(default_factory=list)


@dataclass
class LoopContext:
    break_var: str
    continue_var: str
    guarded: bool = True


# ===================== 分析 =====================

class ModuleAnalyzer:
    """把单个 .scpy 文件解析成 ModuleInfo"""

    def __init__(self, path: str, rel_path: str, is_stage: bool):
        self.path = path
        self.rel_path = rel_path
        self.is_stage = is_stage

    def analyze(self) -> ModuleInfo:
        try:
            with open(self.path, 'r', encoding='utf-8') as handle:
                source = handle.read()
        except OSError as error:
            raise ScPythonError(f"无法读取文件: {error}", path=self.path)

        try:
            transformed = preprocess(source)
        except ScPythonSyntaxError as error:
            error.path = self.path
            raise

        try:
            tree = ast.parse(transformed, filename=self.path)
        except SyntaxError as error:
            raise ScPythonError(
                f"语法错误: {error.msg}", path=self.path,
                line=error.lineno, column=error.offset) from error

        self._reject(tree)
        name = os.path.splitext(os.path.basename(self.path))[0]
        module = ModuleInfo(
            path=self.path,
            rel_path=self.rel_path,
            name='Stage' if self.is_stage else name,
            is_stage=self.is_stage,
            tree=tree,
        )
        self._collect_top_level(module)
        self._infer_lists(module)
        self._collect_variables(module)
        self._validate_names(module)
        return module

    # ---------- 语法限制 ----------

    def _reject(self, tree: ast.Module) -> None:
        for node in ast.walk(tree):
            if isinstance(node, _FORBIDDEN_NODES):
                raise ScPythonError(
                    f"ScPython 不支持 {type(node).__name__}；"
                    "仅支持 Python 基础语法（无 class/装饰器/字典/集合/"
                    "推导式/异常/生成器等）",
                    path=self.path, line=getattr(node, 'lineno', None))
            if isinstance(node, ast.With) and not _is_special_with(node):
                raise ScPythonError(
                    "with 语句仅用于 when/init 头",
                    path=self.path, line=getattr(node, 'lineno', None))
            if isinstance(node, ast.Attribute) and isinstance(
                    node.ctx, ast.Store):
                raise ScPythonError(
                    "不支持属性赋值；请使用变量或列表下标",
                    path=self.path, line=getattr(node, 'lineno', None))
            if isinstance(node, ast.Subscript) and isinstance(
                    node.slice, ast.Slice):
                raise ScPythonError(
                    "不支持列表/字符串切片；Scratch 列表只支持 1 起始下标",
                    path=self.path, line=getattr(node, 'lineno', None))

    # ---------- 顶层结构 ----------

    def _collect_top_level(self, module: ModuleInfo) -> None:
        for node in module.tree.body:
            if isinstance(node, ast.FunctionDef):
                # 兼容「初始化函数」写法：def init(): ...
                if node.name == 'init' and not node.decorator_list \
                        and not (node.args.posonlyargs or node.args.args
                                 or node.args.kwonlyargs or node.args.vararg
                                 or node.args.kwarg):
                    self._parse_init_body(module, node.body)
                    continue
                info = _parse_function(node, self.path)
                if info.name in module.functions:
                    raise ScPythonError(
                        f"重复的自定义积木/函数: {info.name}",
                        path=self.path, line=node.lineno)
                module.functions[info.name] = info
                module.source_order.append(('def', info))
            elif isinstance(node, ast.With):
                call = _with_call(node)
                fname = _call_name(call)
                if fname == '__sprite_init__':
                    self._parse_init(module, node)
                elif fname == '__hat__':
                    module.scripts.append(node)
                    module.source_order.append(('hat', node))
                else:
                    raise ScPythonError(
                        f"未知的 with 头: {fname}",
                        path=self.path, line=node.lineno)
            elif isinstance(node, ast.Assign):
                self._parse_init_assignment(module, node)
            elif isinstance(node, ast.Expr) \
                    and isinstance(node.value, ast.Constant) \
                    and isinstance(node.value.value, str):
                continue  # 模块 docstring
            elif isinstance(node, ast.Pass):
                continue
            else:
                raise ScPythonError(
                    "顶层只能出现 when 头、init 块、def 自定义积木"
                    "以及初始化赋值",
                    path=self.path, line=getattr(node, 'lineno', None))

    def _parse_init(self, module: ModuleInfo, node: ast.With) -> None:
        self._parse_init_body(module, node.body)

    def _parse_init_body(self, module: ModuleInfo,
                         body: List[ast.stmt]) -> None:
        for stmt in body:
            if isinstance(stmt, ast.Assign):
                self._parse_init_assignment(module, stmt)
            elif isinstance(stmt, ast.Pass):
                continue
            elif isinstance(stmt, ast.Expr) \
                    and isinstance(stmt.value, ast.Constant) \
                    and isinstance(stmt.value.value, str):
                continue
            elif isinstance(stmt, ast.Expr) \
                    and isinstance(stmt.value, ast.Call) \
                    and isinstance(stmt.value.func, ast.Attribute) \
                    and isinstance(stmt.value.func.value, ast.Name) \
                    and stmt.value.func.value.id == 'debug':
                self._parse_debug_init(module, stmt.value.func.attr,
                                       stmt.value, stmt.lineno)
            else:
                raise ScPythonError(
                    "init 块只能包含初始化赋值/调试指令",
                    path=self.path, line=getattr(stmt, 'lineno', None))

    def _parse_init_assignment(self, module: ModuleInfo,
                               node: ast.Assign) -> None:
        if len(node.targets) != 1 or not isinstance(
                node.targets[0], ast.Name):
            raise ScPythonError(
                "初始化赋值的目标必须是单个变量名",
                path=self.path, line=node.lineno)
        name = node.targets[0].id
        value = node.value

        if name == 'name':
            text = _constant(value, self.path, 'name')
            if not isinstance(text, str):
                raise ScPythonError("name 必须是字符串", path=self.path,
                                    line=node.lineno)
            module.name = text
            module.meta['name'] = text
            return
        if name == 'costume_names':
            module.meta['costume_names'] = _string_list(
                value, self.path, 'costume_names')
            return
        if name == 'sound_names':
            module.meta['sound_names'] = _string_list(
                value, self.path, 'sound_names')
            return
        if name == 'costumes':
            module.costumes = _string_list(value, self.path, 'costumes')
            return
        if name == 'sounds':
            module.sounds = _string_list(value, self.path, 'sounds')
            return
        if name == 'extensions':
            module.extensions = _string_list(value, self.path, 'extensions')
            return
        if name in _PROPERTY_KEYS:
            module.meta[name] = _constant(value, self.path, name)
            return

        # list xs = txt("data.txt") / list xs = __list__(txt("..."))
        if isinstance(value, ast.Call) and isinstance(
                value.func, ast.Name) and value.func.id == '__list__' \
                and len(value.args) == 1 \
                and isinstance(value.args[0], ast.Call) \
                and isinstance(value.args[0].func, ast.Name) \
                and value.args[0].func.id in ('txt', '__txt__'):
            items = self._read_text_lines(value.args[0], name, node.lineno)
            self._declare_list(module, name, items, node.lineno)
            return
        if isinstance(value, ast.Call) and isinstance(
                value.func, ast.Name) and value.func.id in ('txt', '__txt__'):
            items = self._read_text_lines(value, name, node.lineno)
            self._declare_list(module, name, items, node.lineno)
            return

        # var x = ... / list xs = [...]
        if isinstance(value, ast.Call) and isinstance(
                value.func, ast.Name) and value.func.id in (
                    '__var__', '__list__'):
            args = value.args
            if len(args) != 1:
                raise ScPythonError(
                    f"{value.func.id} 声明需要一个初始值",
                    path=self.path, line=node.lineno)
            initial = _constant(args[0], self.path, name)
            if value.func.id == '__list__':
                if not isinstance(initial, list):
                    raise ScPythonError(
                        f"列表 {name} 的初始值必须是列表字面量",
                        path=self.path, line=node.lineno)
                self._declare_list(module, name, initial, node.lineno)
            else:
                if isinstance(initial, (list, dict, set, tuple)):
                    raise ScPythonError(
                        f"变量 {name} 的初始值必须是数字/字符串/布尔",
                        path=self.path, line=node.lineno)
                self._declare_var(module, name, initial, node.lineno)
            return

        if isinstance(value, ast.List):
            items = _constant(value, self.path, name)
            self._declare_list(module, name, items, node.lineno)
            return

        initial = _constant(value, self.path, name)
        if isinstance(initial, (dict, set, tuple)):
            raise ScPythonError(
                f"变量 {name} 的初始值类型不受支持",
                path=self.path, line=node.lineno)
        self._declare_var(module, name, initial, node.lineno)

    def _read_text_lines(self, call: ast.Call, name: str,
                         lineno: int) -> List[str]:
        if not call.args or not isinstance(call.args[0], ast.Constant) \
                or not isinstance(call.args[0].value, str):
            raise ScPythonError(
                f"{name} 的 txt/文件路径必须是字符串字面量",
                path=self.path, line=lineno)
        relative = call.args[0].value
        base = os.path.dirname(os.path.abspath(self.path))
        full = os.path.abspath(os.path.join(base, relative))
        if not os.path.isfile(full):
            raise ScPythonError(
                f"找不到数据文件 {relative!r}（相对于 {base}）",
                path=self.path, line=lineno)
        with open(full, 'r', encoding='utf-8-sig') as handle:
            return handle.read().splitlines()

    def _parse_debug_init(self, module: ModuleInfo, action: str,
                          call: ast.Call, lineno: int) -> None:
        args = call.args
        if action == 'import_list':
            if len(args) != 2:
                raise ScPythonError(
                    "debug.import_list(list, path) 需要两个参数",
                    path=self.path, line=lineno)
            name = _target_name(args[0])
            if name is None:
                raise ScPythonError(
                    "debug.import_list 的第一个参数必须是列表名",
                    path=self.path, line=lineno)
            items = self._read_text_lines(
                ast.Call(func=ast.Name(id='txt', ctx=ast.Load()),
                         args=[args[1]], keywords=[]),
                name, lineno)
            self._declare_list(module, name, items, lineno)
            return
        if action == 'set_default':
            if len(args) != 2:
                raise ScPythonError(
                    "debug.set_default(var, value) 需要两个参数",
                    path=self.path, line=lineno)
            name = _target_name(args[0])
            if name is None:
                raise ScPythonError(
                    "debug.set_default 的第一个参数必须是变量名",
                    path=self.path, line=lineno)
            self._declare_var(module, name,
                              _constant(args[1], self.path, name), lineno)
            return
        if action == 'set_list_default':
            if len(args) != 2:
                raise ScPythonError(
                    "debug.set_list_default(list, values) 需要两个参数",
                    path=self.path, line=lineno)
            name = _target_name(args[0])
            values = _constant(args[1], self.path, str(name))
            if name is None or not isinstance(values, list):
                raise ScPythonError(
                    "debug.set_list_default 需要 (列表名, 列表字面量)",
                    path=self.path, line=lineno)
            self._declare_list(module, name, values, lineno)
            return
        if action in ('watch', 'print', 'trace', 'assert'):
            # 编译期调试指令：不生成 Scratch 块，记录到工程警告中
            module.meta.setdefault('debug_notes', []).append(
                f"{action}: {ast.unparse(call)}")
            return
        raise ScPythonError(
            f"未知 debug 初始化指令: {action}",
            path=self.path, line=lineno)

    def _declare_var(self, module: ModuleInfo, name: str,
                     value: Any, lineno: int) -> None:
        if name in module.declared_lists:
            raise ScPythonError(
                f"{name} 已声明为列表，不能再次声明为变量",
                path=self.path, line=lineno)
        module.declared_vars.add(name)
        module.explicit_vars.add(name)
        module.variables[name] = value

    def _declare_list(self, module: ModuleInfo, name: str,
                      items: List[Any], lineno: int) -> None:
        if name in module.declared_vars:
            raise ScPythonError(
                f"{name} 已声明为变量，不能再次声明为列表",
                path=self.path, line=lineno)
        module.declared_lists.add(name)
        module.explicit_lists.add(name)
        module.lists[name] = list(items)

    # ---------- 列表/变量推断 ----------

    def _scan_nodes(self, module: ModuleInfo):
        for node in module.tree.body:
            if isinstance(node, ast.FunctionDef):
                if node.name == 'init':
                    continue  # 初始化函数只提供元数据
                yield from ast.walk(node)
            elif isinstance(node, ast.With):
                call = _with_call(node)
                if _call_name(call) == '__hat__':
                    yield from ast.walk(node)

    def _infer_lists(self, module: ModuleInfo) -> None:
        for node in self._scan_nodes(module):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Subscript) and isinstance(
                            target.value, ast.Name):
                        module.declared_lists.add(target.value.id)
            elif isinstance(node, ast.AugAssign) and isinstance(
                    node.target, ast.Subscript) and isinstance(
                        node.target.value, ast.Name):
                module.declared_lists.add(node.target.value.id)
            elif isinstance(node, ast.Delete):
                for target in node.targets:
                    if isinstance(target, ast.Subscript) and isinstance(
                            target.value, ast.Name):
                        module.declared_lists.add(target.value.id)
            elif isinstance(node, ast.For):
                if isinstance(node.iter, ast.Name):
                    module.declared_lists.add(node.iter.id)
            elif isinstance(node, ast.Call) and isinstance(
                    node.func, ast.Attribute) and isinstance(
                        node.func.value, ast.Name):
                if node.func.attr in _LIST_METHODS:
                    module.declared_lists.add(node.func.value.id)
            elif isinstance(node, ast.Call) and isinstance(
                    node.func, ast.Name) and node.func.id in _LIST_FUNCTIONS:
                if node.args and isinstance(node.args[0], ast.Name):
                    module.declared_lists.add(node.args[0].id)

        for name in module.declared_lists:
            if name in module.declared_vars:
                raise ScPythonError(
                    f"{name} 同时被当作变量和列表使用",
                    path=self.path)

    def _collect_variables(self, module: ModuleInfo) -> None:
        for node in self._scan_nodes(module):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and \
                            target.id not in module.declared_lists:
                        module.declared_vars.add(target.id)
            elif isinstance(node, ast.AugAssign) and isinstance(
                    node.target, ast.Name) and \
                    node.target.id not in module.declared_lists:
                module.declared_vars.add(node.target.id)
            elif isinstance(node, ast.For) and isinstance(
                    node.target, ast.Name) and \
                    node.target.id not in module.declared_lists:
                if node.target.id != '_':
                    module.declared_vars.add(node.target.id)

        for name in module.declared_vars:
            module.variables.setdefault(name, 0)

    def _validate_names(self, module: ModuleInfo) -> None:
        for name in module.declared_lists:
            if name in _MATH_FUNCTIONS or name in _SENSING_FUNCTIONS:
                raise ScPythonError(
                    f"列表名 {name} 与内置函数冲突", path=self.path)


def analyze_macros(path: str) -> Dict[str, FunctionInfo]:
    """解析宏文件，只允许函数定义与 docstring"""
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            source = handle.read()
        tree = ast.parse(preprocess(source), filename=path)
    except (OSError, SyntaxError, ScPythonSyntaxError) as error:
        if isinstance(error, ScPythonSyntaxError):
            error.path = path
            raise
        raise ScPythonError(f"宏文件解析失败: {error}", path=path) from error

    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(
                node.value, ast.Constant) and isinstance(
                    node.value.value, str):
            continue
        if isinstance(node, ast.FunctionDef):
            continue
        raise ScPythonError(
            "宏文件只能包含 def 自定义积木定义",
            path=path, line=getattr(node, 'lineno', None))

    for node in ast.walk(tree):
        if isinstance(node, _FORBIDDEN_NODES):
            raise ScPythonError(
                f"宏文件中不支持 {type(node).__name__}",
                path=path, line=getattr(node, 'lineno', None))

    result = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            info = _parse_function(node, path)
            info.is_macro = True
            result[info.name] = info
    return result


# ===================== AST 辅助 =====================

def _is_special_with(node: ast.With) -> bool:
    if len(node.items) != 1:
        return False
    name = _call_name(node.items[0].context_expr)
    return name in ('__hat__', '__sprite_init__')


def _with_call(node: ast.With) -> ast.Call:
    expr = node.items[0].context_expr
    if not isinstance(expr, ast.Call):
        raise ScPythonError("内部错误: with 头不是调用")
    return expr


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            return ast.unparse(node.func)
    if isinstance(node, ast.Name):
        return node.id
    return ''


def _constant(node: ast.AST, path: str, what: str = '值') -> Any:
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError) as error:
        raise ScPythonError(
            f"{what} 必须是编译期常量（数字/字符串/布尔/列表字面量）",
            path=path, line=getattr(node, 'lineno', None)) from error


def _string_list(node: ast.AST, path: str, what: str) -> List[str]:
    value = _constant(node, path, what)
    if not isinstance(value, list) or any(
            not isinstance(item, str) for item in value):
        raise ScPythonError(f"{what} 必须是字符串列表", path=path,
                            line=getattr(node, 'lineno', None))
    return list(value)


def _literal_expr(value: Any) -> Expr:
    """把 Python 常量转成 IR 字面量表达式（用于 debug.reset 的默认值）"""
    if isinstance(value, bool):
        return make_boolean(value)
    if isinstance(value, (int, float)):
        return make_number(value)
    return make_string('' if value is None else str(value))


def _target_name(node: ast.AST) -> Optional[str]:
    """接受 "名字" 字符串字面量或裸变量名两种写法"""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return node.id
    return None


def _parse_function(node: ast.FunctionDef, path: str) -> FunctionInfo:
    if node.decorator_list:
        raise ScPythonError(
            "ScPython 不支持装饰器；自定义积木请用 def 的 * 元信息参数",
            path=path, line=node.lineno)
    args = node.args
    if args.vararg or args.kwarg:
        raise ScPythonError(
            "自定义积木不支持 *args / **kwargs",
            path=path, line=node.lineno)

    positional = list(args.posonlyargs) + list(args.args)
    defaults = [None] * (len(positional) - len(args.defaults)) + \
        list(args.defaults)
    params: List[Param] = []
    for index, arg in enumerate(positional):
        default_node = defaults[index]
        has_default = default_node is not None
        default = _constant(default_node, path, '参数默认值') \
            if has_default else ''
        params.append(Param(arg.arg, 's', default, has_default))

    metadata = {}
    for arg, default_node in zip(args.kwonlyargs, args.kw_defaults):
        if default_node is None:
            raise ScPythonError(
                f"元信息参数 {arg.arg} 必须有默认值",
                path=path, line=node.lineno)
        if arg.arg not in ('types', 'warp', 'label', 'proccode'):
            raise ScPythonError(
                f"未知的元信息参数 {arg.arg}；只支持 types/warp/label",
                path=path, line=node.lineno)
        metadata[arg.arg] = _constant(default_node, path, arg.arg)

    types = metadata.get('types')
    if types is not None:
        if not isinstance(types, str) or len(types) != len(params) or any(
                char not in 'snb' for char in types):
            raise ScPythonError(
                "types 必须是和参数数量相同的字符串，字符只能是 s/n/b",
                path=path, line=node.lineno)
        for param, char in zip(params, types):
            param.type = char
    else:
        for param in params:
            if isinstance(param.default, bool):
                param.type = 'b'
            elif isinstance(param.default, (int, float)):
                param.type = 'n'

    label = metadata.get('label') or metadata.get('proccode')
    for param in params:
        if not param.has_default:
            param.default = False if param.type == 'b' else ''
    if label is None:
        placeholders = ' '.join(
            '%b' if param.type == 'b'
            else '%n' if param.type == 'n' else '%s'
            for param in params)
        proccode = node.name + (f" {placeholders}" if placeholders else '')
    else:
        if not isinstance(label, str):
            raise ScPythonError("label 必须是字符串", path=path,
                                line=node.lineno)
        proccode = label
        if len(params) != proccode.count('%'):
            raise ScPythonError(
                "label 中的 %s/%n/%b 数量必须与参数数量一致",
                path=path, line=node.lineno)

    warp = metadata.get('warp', False)
    if not isinstance(warp, bool):
        raise ScPythonError("warp 必须是 True/False", path=path,
                            line=node.lineno)
    return FunctionInfo(node.name, node, params, proccode, warp, path)


# ===================== 角色编译 =====================

class RoleBuilder:
    """把 ModuleInfo 编译成 SpriteIR"""

    def __init__(self, module: ModuleInfo, index: int, compiler):
        self.module = module
        self.index = index
        self.compiler = compiler
        self.sprite = SpriteIR(
            name=module.name, is_stage=module.is_stage)
        self.local_vars: Dict[str, Any] = {}
        self.local_lists: Dict[str, List[Any]] = {}
        self.variable_ids: Dict[str, str] = {}
        self.list_ids: Dict[str, str] = {}
        self.used_extensions: set = set()
        self.loop_stack: List[LoopContext] = []
        self.param_stack: List[Dict[str, Param]] = []
        self.hidden_counter = 0
        self.id_counter = 0
        self.current_function: Optional[FunctionInfo] = None
        self.used_macros: set = set()
        # debug.reset() 一次可能要重置多个变量/列表，这里暂存多条语句
        self.pending_debug: List[Statement] = []

    # ---------- 入口 ----------

    def build(self) -> SpriteIR:
        self._apply_meta()
        self._init_symbols()

        for kind, obj in self.module.source_order:
            if kind == 'def':
                self.sprite.statements.append(self._compile_function(obj))
            elif kind == 'hat':
                self.sprite.statements.append(self._compile_hat(obj))

        self._finish_symbols()
        for note in self.module.meta.get('debug_notes', []):
            self.compiler.warnings.append(f"[{self.module.name}] {note}")
        if self.module.is_stage:
            # 舞台脚本里自动创建的变量也属于全局，必须在本角色编译完成后
            # 再同步给后续角色使用
            self.compiler.stage_vars = dict(self.local_vars)
            self.compiler.stage_var_ids = dict(self.variable_ids)
            self.compiler.stage_lists = dict(self.local_lists)
            self.compiler.stage_list_ids = dict(self.list_ids)
        self.sprite.costumes = self._load_costumes()
        self.sprite.sounds = self._load_sounds()
        return self.sprite

    # ---------- 元数据与符号 ----------

    def _apply_meta(self) -> None:
        meta = self.module.meta
        self.sprite.name = self.module.name
        self.sprite.x = _number(meta.get('x', 0))
        self.sprite.y = _number(meta.get('y', 0))
        self.sprite.direction = _number(meta.get('direction', 90))
        self.sprite.visible = bool(meta.get('visible', True))
        self.sprite.size = _number(meta.get('size', 100))
        self.sprite.draggable = bool(meta.get('draggable', False))
        style = str(meta.get('rotation_style', 'all around'))
        if style not in ('all around', 'left-right', "don't rotate"):
            raise ScPythonError(
                "rotation_style 只能是 'all around' / 'left-right' / "
                "\"don't rotate\"", path=self.module.path)
        self.sprite.rotation_style = style
        self.sprite.current_costume = int(
            meta.get('current_costume', 0) or 0)
        self.sprite.layer_order = int(meta.get('layer_order', 1) or 1)
        if self.module.is_stage:
            self.sprite.is_stage = True

    def _init_symbols(self) -> None:
        if self.module.is_stage:
            # 舞台上显式声明和脚本中出现的变量/列表都属于全局
            var_names = set(self.module.declared_vars)
            list_names = set(self.module.declared_lists)
        else:
            # 角色只把显式声明视为本地；脚本里推断出的名字可能引用全局
            var_names = set(self.module.explicit_vars)
            list_names = set(self.module.explicit_lists)
        self.local_vars = {
            name: self.module.variables.get(name, 0)
            for name in var_names
        }
        self.local_lists = {
            name: list(self.module.lists.get(name, []))
            for name in list_names
        }
        for name in self.local_vars:
            self.variable_ids[name] = self._new_id('var')
        for name in self.local_lists:
            self.list_ids[name] = self._new_id('list')

    def _finish_symbols(self) -> None:
        self.sprite.variables = dict(self.local_vars)
        self.sprite.lists = {name: list(items)
                             for name, items in self.local_lists.items()}
        self.sprite.variable_ids = dict(self.variable_ids)
        self.sprite.list_ids = dict(self.list_ids)
        self.sprite.variable_attrs = {
            name: sanitize_name(name, 'var') for name in self.local_vars}
        self.sprite.list_attrs = {
            name: sanitize_name(name, 'lst') for name in self.local_lists}
        if not self.module.is_stage:
            self.sprite.global_variable_names = {
                name for name in self.compiler.stage_vars
                if name not in self.local_vars}
            self.sprite.global_list_names = {
                name for name in self.compiler.stage_lists
                if name not in self.local_lists}

    def _new_id(self, prefix: str) -> str:
        self.id_counter += 1
        if self.module.is_stage:
            return f"{prefix}_g_{self.id_counter}"
        return f"{prefix}_s{self.index}_{self.id_counter}"

    def _is_list_name(self, name: str) -> bool:
        return (name in self.local_lists
                or name in self.module.declared_lists
                or name in self.compiler.stage_lists)

    def ensure_var(self, name: str) -> Tuple[str, str]:
        """返回 (存储名, ID)；无法解析时创建本地变量（舞台则全局）"""
        if name in self.local_vars:
            if name not in self.variable_ids:
                self.variable_ids[name] = self._new_id('var')
            return name, self.variable_ids[name]
        if self._is_list_name(name):
            raise ScPythonError(
                f"{name} 是列表，不能当变量使用", path=self.module.path)
        if not self.module.is_stage and name in self.compiler.stage_vars:
            return name, self.compiler.stage_var_ids[name]
        self.local_vars[name] = 0
        self.variable_ids[name] = self._new_id('var')
        return name, self.variable_ids[name]

    def ensure_list(self, name: str) -> Tuple[str, str]:
        if name in self.local_lists:
            if name not in self.list_ids:
                self.list_ids[name] = self._new_id('list')
            return name, self.list_ids[name]
        if name in self.local_vars or (
                name in self.module.declared_vars
                and name not in self.module.declared_lists):
            raise ScPythonError(
                f"{name} 是变量，不是列表", path=self.module.path)
        if not self.module.is_stage and name in self.compiler.stage_lists:
            return name, self.compiler.stage_list_ids[name]
        self.local_lists[name] = []
        self.list_ids[name] = self._new_id('list')
        return name, self.list_ids[name]

    def _hidden(self, hint: str) -> str:
        self.hidden_counter += 1
        name = f"__scpy_{hint}_{self.hidden_counter}"
        self.ensure_var(name)
        return name

    # ---------- 资产 ----------

    def _load_costumes(self) -> List[dict]:
        costumes = []
        names = set()
        explicit = self._explicit_asset_names('costume_names',
                                              len(self.module.costumes))
        for index, reference in enumerate(self.module.costumes):
            costume = self.compiler.asset_library.costume(
                reference, self.module.path,
                name=explicit[index] if explicit else None)
            if explicit:
                # 导入工程需要原样保留造型名（脚本按名字切换造型）
                costumes.append(costume)
                continue
            base = costume['name']
            name = base
            suffix = 2
            while name in names:
                name = f"{base}_{suffix}"
                suffix += 1
            names.add(name)
            costume['name'] = name
            costumes.append(costume)
        return costumes

    def _load_sounds(self) -> List[dict]:
        sounds = []
        names = set()
        explicit = self._explicit_asset_names('sound_names',
                                              len(self.module.sounds))
        for index, reference in enumerate(self.module.sounds):
            sound = self.compiler.asset_library.sound(
                reference, self.module.path,
                name=explicit[index] if explicit else None)
            if explicit:
                sounds.append(sound)
                continue
            base = sound['name']
            name = base
            suffix = 2
            while name in names:
                name = f"{base}_{suffix}"
                suffix += 1
            names.add(name)
            sound['name'] = name
            sounds.append(sound)
        return sounds

    def _explicit_asset_names(self, key: str,
                              count: int) -> Optional[List[str]]:
        names = self.module.meta.get(key)
        if not names:
            return None
        if len(names) != count:
            raise ScPythonError(
                f"{key} 有 {len(names)} 项，但共有 {count} 个资源",
                path=self.module.path)
        return [str(name) for name in names]

    # ---------- 函数与帽子 ----------

    def _compile_function(self, info: FunctionInfo) -> Statement:
        stmt = Statement(BlockType.PROCEDURE_DEFINE)
        stmt.extra.update({
            'name': info.name,
            'proccode': info.proccode,
            'args': [param.name for param in info.params],
            'arg_types': [param.type for param in info.params],
            'argumentids': info.argumentids,
            'argumentdefaults': info.argumentdefaults,
            'warp': info.warp,
        })
        old_function = self.current_function
        self.current_function = info
        self.param_stack.append(
            {param.name: param for param in info.params})
        try:
            stmt.body = self._compile_sequence(info.node.body)
        finally:
            self.param_stack.pop()
            self.current_function = old_function
        return stmt

    def _compile_hat(self, node: ast.With) -> Statement:
        call = _with_call(node)
        args = list(call.args)
        kwargs = list(call.keywords)
        name = ast.literal_eval(args[0]) if args else ''
        if not isinstance(name, str):
            raise ScPythonError("when 头缺少事件名",
                                path=self.module.path, line=node.lineno)
        rest = args[1:]

        hat: Statement
        if name in ('green_flag', 'greenflag'):
            hat = Statement(BlockType.WHEN_FLAG_CLICKED)
        elif name in ('clicked', 'stage_clicked', 'this_sprite_clicked'):
            hat = Statement(BlockType.WHEN_THIS_SPRITE_CLICKED)
        elif name == 'clone_start':
            hat = Statement(BlockType.START_AS_CLONE)
        elif name == 'key_pressed':
            key = self._const_arg(rest, 0, 'key_pressed')
            hat = Statement(BlockType.WHEN_KEY_PRESSED)
            hat.extra['key'] = str(key)
        elif name == 'broadcast':
            message = self._const_arg(rest, 0, 'broadcast')
            hat = Statement(BlockType.WHEN_BROADCAST_RECEIVED)
            hat.value = make_string(str(message))
            if str(message) not in self.sprite.broadcasts:
                self.sprite.broadcasts.append(str(message))
        elif name == 'backdrop_switches_to':
            backdrop = self._const_arg(rest, 0, 'backdrop_switches_to')
            hat = Statement(BlockType.WHEN_BACKDROP_SWITCHES)
            hat.extra['backdrop'] = str(backdrop)
        elif name in ('timer', 'loudness'):
            if len(rest) != 2:
                raise ScPythonError(
                    f"when {name} 需要比较符和阈值",
                    path=self.module.path, line=node.lineno)
            operator = ast.literal_eval(rest[0])
            value = self._expr(rest[1])
            # Scratch 的「当计时器 >」只有大于；其他比较取反后无法直接表达，
            # 因此这里只允许 >，其余报错以免语义错误。
            if operator != '>':
                raise ScPythonError(
                    f"when {name} 只支持 '>' 比较", path=self.module.path,
                    line=node.lineno)
            hat = Statement(BlockType.WHEN_GREATER_THAN)
            hat.extra['menu'] = 'TIMER' if name == 'timer' else 'LOUDNESS'
            hat.value = value
        elif name == 'extension' or '.' in name:
            hat = self._extension_hat(name, rest, kwargs, node)
        else:
            raise ScPythonError(f"未知事件头: {name}",
                                path=self.module.path, line=node.lineno)

        body = self._compile_sequence(node.body)
        hat.next = _chain(body)
        return hat

    def _extension_hat(self, name: str, args: List[ast.AST],
                       kwargs: List[ast.keyword],
                       node: ast.With) -> Statement:
        if name == 'extension':
            if len(args) < 2:
                raise ScPythonError(
                    "extension 帽子需要 namespace 和 opcode",
                    path=self.module.path, line=node.lineno)
            namespace = str(ast.literal_eval(args[0]))
            opcode = str(ast.literal_eval(args[1]))
            rest = args[2:]
            spec = ExtensionBlock(namespace, opcode, opcode, [], {})
        else:
            namespace, block_name = name.rsplit('.', 1)
            spec = self.compiler.extensions.resolve(namespace, block_name)
            if spec is None:
                raise ScPythonError(
                    f"extensions.json 中没有 {name}", path=self.module.path,
                    line=node.lineno)
            namespace, opcode = spec.namespace, spec.opcode
            rest = args
        inputs, fields = bind_extension_args(
            spec, rest, kwargs, self._expr, self._const_node,
            self.module.path)
        hat = Statement(BlockType.EXTENSION_HAT)
        hat.extra.update({
            'namespace': namespace,
            'opcode': opcode,
            'inputs': inputs,
            'fields': fields,
        })
        self.used_extensions.add(namespace)
        return hat

    # ---------- 语句 ----------

    def _compile_sequence(self, body: List[ast.stmt]) -> List[Statement]:
        result = []
        for node in body:
            statements = self._compile_statement(node)
            if not statements:
                continue
            for stmt in statements:
                loop = self.loop_stack[-1] if self.loop_stack else None
                if loop is not None and loop.guarded:
                    guard = Statement(BlockType.IF)
                    guard.condition = self._guard_condition(loop)
                    guard.body = [stmt]
                    stmt = guard
                result.append(stmt)
        return result

    def _compile_statement(self, node: ast.stmt) -> List[Statement]:
        if isinstance(node, ast.Pass):
            return []
        if isinstance(node, ast.If):
            return [self._compile_if(node)]
        if isinstance(node, ast.While):
            return self._compile_while(node)
        if isinstance(node, ast.For):
            return self._compile_for(node)
        if isinstance(node, ast.Break):
            return [self._compile_break(node)]
        if isinstance(node, ast.Continue):
            return [self._compile_continue(node)]
        if isinstance(node, ast.Return):
            return [self._compile_return(node)]
        if isinstance(node, ast.Assign):
            return [self._compile_assign(node)]
        if isinstance(node, ast.AugAssign):
            return [self._compile_aug_assign(node)]
        if isinstance(node, ast.Delete):
            return [self._compile_delete(node)]
        if isinstance(node, ast.Expr):
            if isinstance(node.value, ast.Constant) and \
                    isinstance(node.value.value, str):
                return []
            if isinstance(node.value, ast.Call):
                stmt = self._compile_call_statement(node.value)
                produced: List[Statement] = []
                if stmt is not None:
                    produced.append(stmt)
                if self.pending_debug:
                    produced.extend(self.pending_debug)
                    self.pending_debug = []
                return produced
            raise ScPythonError(
                "表达式语句只能是函数调用",
                path=self.module.path, line=node.lineno)
        raise ScPythonError(
            f"不支持的语句: {type(node).__name__}",
            path=self.module.path, line=getattr(node, 'lineno', None))

    def _compile_if(self, node: ast.If) -> Statement:
        stmt = Statement(
            BlockType.IF_ELSE if node.orelse else BlockType.IF)
        stmt.condition = self._expr(node.test)
        stmt.body = self._compile_sequence(node.body)
        if node.orelse:
            stmt.else_body = self._compile_sequence(node.orelse)
        return stmt

    def _compile_while(self, node: ast.While) -> List[Statement]:
        has_flags = _contains_break_continue(node.body)
        if has_flags:
            break_var = self._hidden('break')
            continue_var = self._hidden('continue')
            loop = LoopContext(break_var, continue_var)
            self.loop_stack.append(loop)
            try:
                body = [self._set_var(continue_var, make_number(0))]
                body.extend(self._compile_sequence(node.body))
            finally:
                self.loop_stack.pop()
            stop = self._or(
                self._eq_one(break_var),
                self._not(self._expr(node.test)))
            stmt = Statement(BlockType.REPEAT_UNTIL)
            stmt.condition = stop
            stmt.body = body
            return [
                self._set_var(break_var, make_number(0)),
                self._set_var(continue_var, make_number(0)),
                stmt,
            ]

        body = self._compile_sequence(node.body)
        if isinstance(node.test, ast.Constant) and node.test.value is True:
            stmt = Statement(BlockType.FOREVER)
            stmt.body = body
            return [stmt]
        stmt = Statement(BlockType.REPEAT_UNTIL)
        stmt.condition = self._not(self._expr(node.test))
        stmt.body = body
        return [stmt]

    def _compile_for(self, node: ast.For) -> List[Statement]:
        if node.orelse:
            raise ScPythonError("不支持 for...else",
                                path=self.module.path, line=node.lineno)
        if not isinstance(node.target, ast.Name):
            raise ScPythonError(
                "for 循环变量必须是单个名字", path=self.module.path,
                line=node.lineno)
        target = node.target.id
        if target != '_':
            self._check_not_param(target, node.lineno)
            if target in self.module.declared_lists or \
                    self._is_list_name(target):
                raise ScPythonError(
                    f"for 循环变量 {target} 是列表，不能作为循环变量",
                    path=self.module.path, line=node.lineno)

        if isinstance(node.iter, ast.Call) and isinstance(
                node.iter.func, ast.Name) and \
                node.iter.func.id in ('range', 'xrange'):
            return self._compile_for_range(node, target)
        if isinstance(node.iter, ast.Name):
            return self._compile_for_list(node, target, node.iter.id)
        raise ScPythonError(
            "for 只能遍历 range(...) 或列表变量",
            path=self.module.path, line=node.lineno)

    def _compile_for_range(self, node: ast.For,
                           target: str) -> List[Statement]:
        call = node.iter
        args = list(call.args)
        if call.keywords:
            raise ScPythonError("range 不支持关键字参数",
                                path=self.module.path, line=node.lineno)
        if len(args) == 1:
            start_node, stop_node, step = ast.Constant(0), args[0], 1
        elif len(args) == 2:
            start_node, stop_node, step = args[0], args[1], 1
        elif len(args) == 3:
            start_node, stop_node = args[0], args[1]
            step_value = _constant(args[2], self.module.path, 'range 步长')
            if not isinstance(step_value, (int, float)) or step_value == 0:
                raise ScPythonError(
                    "range 步长必须是非零常量数字",
                    path=self.module.path, line=node.lineno)
            step = step_value
        else:
            raise ScPythonError("range 参数数量应为 1-3",
                                path=self.module.path, line=node.lineno)

        counter = self._hidden('i')
        limit = self._hidden('stop')
        prefix = [
            self._set_var(counter, self._expr(start_node)),
            self._set_var(limit, self._expr(stop_node)),
        ]
        has_flags = _contains_break_continue(node.body)
        break_var = continue_var = ''
        if has_flags:
            break_var = self._hidden('break')
            continue_var = self._hidden('continue')
            prefix.append(self._set_var(break_var, make_number(0)))
            prefix.append(self._set_var(continue_var, make_number(0)))
            loop = LoopContext(break_var, continue_var)
        else:
            loop = None

        body: List[Statement] = []
        if loop is not None:
            body.append(self._set_var(continue_var, make_number(0)))
        if target != '_':
            body.append(self._set_var(target, self._var_expr(counter)))
        if loop is not None:
            self.loop_stack.append(loop)
        try:
            body.extend(self._compile_sequence(node.body))
        finally:
            if loop is not None:
                self.loop_stack.pop()
        body.append(self._change_var(counter, make_number(step)))

        comparison = self._ge if step > 0 else self._le
        termination = comparison(self._var_expr(counter), self._var_expr(limit))
        if break_var:
            termination = self._or(self._eq_one(break_var), termination)
        stmt = Statement(BlockType.REPEAT_UNTIL)
        stmt.condition = termination
        stmt.body = body
        return prefix + [stmt]

    def _compile_for_list(self, node: ast.For, target: str,
                          list_name: str) -> List[Statement]:
        list_name, list_id = self.ensure_list(list_name)
        index = self._hidden('idx')
        prefix = [self._set_var(index, make_number(1))]
        has_flags = _contains_break_continue(node.body)
        break_var = continue_var = ''
        if has_flags:
            break_var = self._hidden('break')
            continue_var = self._hidden('continue')
            prefix.append(self._set_var(break_var, make_number(0)))
            prefix.append(self._set_var(continue_var, make_number(0)))
            loop = LoopContext(break_var, continue_var)
        else:
            loop = None

        body: List[Statement] = []
        if loop is not None:
            body.append(self._set_var(continue_var, make_number(0)))
        if target != '_':
            body.append(self._set_var(
                target, self._list_expr(ExprType.ITEM_OF_LIST, list_name,
                                        list_id, self._var_expr(index))))
        if loop is not None:
            self.loop_stack.append(loop)
        try:
            body.extend(self._compile_sequence(node.body))
        finally:
            if loop is not None:
                self.loop_stack.pop()
        body.append(self._change_var(index, make_number(1)))

        length = self._list_expr(ExprType.LENGTH_OF_LIST, list_name, list_id)
        termination = self._gt(self._var_expr(index), length)
        if break_var:
            termination = self._or(self._eq_one(break_var), termination)
        stmt = Statement(BlockType.REPEAT_UNTIL)
        stmt.condition = termination
        stmt.body = body
        return prefix + [stmt]

    def _compile_break(self, node: ast.Break) -> Statement:
        if not self.loop_stack:
            raise ScPythonError("break 只能出现在循环内",
                                path=self.module.path, line=node.lineno)
        loop = self.loop_stack[-1]
        return self._set_var(loop.break_var, make_number(1))

    def _compile_continue(self, node: ast.Continue) -> Statement:
        if not self.loop_stack:
            raise ScPythonError("continue 只能出现在循环内",
                                path=self.module.path, line=node.lineno)
        loop = self.loop_stack[-1]
        return self._set_var(loop.continue_var, make_number(1))

    def _compile_return(self, node: ast.Return) -> Statement:
        if self.current_function is None:
            raise ScPythonError("return 只能出现在自定义积木内",
                                path=self.module.path, line=node.lineno)
        stmt = Statement(BlockType.PROCEDURE_RETURN)
        if node.value is not None:
            stmt.value = self._expr(node.value)
        return stmt

    def _compile_assign(self, node: ast.Assign) -> Statement:
        if len(node.targets) != 1:
            raise ScPythonError("不支持链式赋值",
                                path=self.module.path, line=node.lineno)
        target = node.targets[0]
        if isinstance(target, ast.Name):
            if self._is_list_name(target.id):
                raise ScPythonError(
                    "列表不能整体赋值；请使用 append/insert/clear 或下标",
                    path=self.module.path, line=node.lineno)
            self._check_not_param(target.id, node.lineno)
            value_node = node.value
            if isinstance(value_node, ast.Call) and isinstance(
                    value_node.func, ast.Name):
                if value_node.func.id == '__list__':
                    raise ScPythonError(
                        "list 声明只能出现在 init 块或文件顶层",
                        path=self.module.path, line=node.lineno)
                if value_node.func.id == '__var__':
                    if len(value_node.args) != 1:
                        raise ScPythonError(
                            "var 声明需要一个初始值",
                            path=self.module.path, line=node.lineno)
                    value_node = value_node.args[0]
            return self._set_var(target.id, self._expr(value_node))
        if isinstance(target, ast.Subscript):
            list_name = self._list_name(target.value, node.lineno)
            index = self._expr(target.slice)
            value = self._expr(node.value)
            list_name, list_id = self.ensure_list(list_name)
            stmt = Statement(BlockType.REPLACE_IN_LIST)
            stmt.extra.update({'name': list_name, 'id': list_id,
                               'item': value})
            stmt.value = index
            return stmt
        raise ScPythonError("赋值目标只能是变量名或列表下标",
                            path=self.module.path, line=node.lineno)

    def _compile_aug_assign(self, node: ast.AugAssign) -> Statement:
        operator = {
            ast.Add: '+', ast.Sub: '-', ast.Mult: '*',
            ast.Div: '/', ast.Mod: '%',
        }.get(type(node.op))
        if operator is None:
            raise ScPythonError(
                "只支持 += -= *= /= %= 增量赋值",
                path=self.module.path, line=node.lineno)
        value = self._expr(node.value)
        if isinstance(node.target, ast.Name):
            self._check_not_param(node.target.id, node.lineno)
            if operator == '+':
                return self._change_var(node.target.id, value)
            current = self._var_expr(node.target.id)
            return self._set_var(
                node.target.id, _binary(operator, current, value))
        if isinstance(node.target, ast.Subscript):
            list_name = self._list_name(node.target.value, node.lineno)
            list_name, list_id = self.ensure_list(list_name)
            index = self._expr(node.target.slice)
            current = self._list_expr(
                ExprType.ITEM_OF_LIST, list_name, list_id, index)
            stmt = Statement(BlockType.REPLACE_IN_LIST)
            stmt.extra.update({
                'name': list_name, 'id': list_id,
                'item': _binary(operator, current, value)})
            stmt.value = index
            return stmt
        raise ScPythonError("增量赋值目标只能是变量或列表下标",
                            path=self.module.path, line=node.lineno)

    def _compile_delete(self, node: ast.Delete) -> Statement:
        if len(node.targets) != 1 or not isinstance(
                node.targets[0], ast.Subscript):
            raise ScPythonError("只支持 del 列表[下标]",
                                path=self.module.path, line=node.lineno)
        target = node.targets[0]
        list_name = self._list_name(target.value, node.lineno)
        list_name, list_id = self.ensure_list(list_name)
        if isinstance(target.slice, ast.Slice):
            if target.slice.lower is not None or target.slice.upper is not None:
                raise ScPythonError("只支持 del 列表[:] 清空",
                                    path=self.module.path, line=node.lineno)
            stmt = Statement(BlockType.DELETE_ALL_FROM_LIST)
            stmt.extra.update({'name': list_name, 'id': list_id})
            return stmt
        stmt = Statement(BlockType.DELETE_FROM_LIST)
        stmt.extra.update({'name': list_name, 'id': list_id})
        stmt.value = self._expr(target.slice)
        return stmt

    # ---------- 语句辅助 ----------

    def _set_var(self, name: str, value: Expr) -> Statement:
        name, var_id = self.ensure_var(name)
        stmt = Statement(BlockType.SET_VARIABLE)
        stmt.extra.update({'name': name, 'id': var_id})
        stmt.value = value
        return stmt

    def _change_var(self, name: str, value: Expr) -> Statement:
        name, var_id = self.ensure_var(name)
        stmt = Statement(BlockType.CHANGE_VARIABLE)
        stmt.extra.update({'name': name, 'id': var_id})
        stmt.value = value
        return stmt

    def _var_expr(self, name: str) -> Expr:
        name, var_id = self.ensure_var(name)
        expr = make_variable(name)
        expr.extra['id'] = var_id
        expr.extra['attr'] = sanitize_name(name, 'var')
        return expr

    def _list_expr(self, kind: ExprType, name: str, list_id: str,
                   left: Optional[Expr] = None) -> Expr:
        expr = Expr(kind, name=name, left=left)
        expr.extra['id'] = list_id
        return expr

    def _eq_one(self, name: str) -> Expr:
        return Expr(ExprType.EQUAL, left=self._var_expr(name),
                    right=make_number(1))

    def _guard_condition(self, loop: LoopContext) -> Expr:
        # 只有 break/continue 都未设置时才执行剩余语句
        return Expr(
            ExprType.AND,
            left=Expr(ExprType.NOT, right=self._eq_one(loop.break_var)),
            right=Expr(ExprType.NOT, right=self._eq_one(loop.continue_var)))

    @staticmethod
    def _not(expr: Expr) -> Expr:
        return Expr(ExprType.NOT, right=expr)

    @staticmethod
    def _or(left: Expr, right: Expr) -> Expr:
        return Expr(ExprType.OR, left=left, right=right)

    @staticmethod
    def _gt(left: Expr, right: Expr) -> Expr:
        return Expr(ExprType.GREATER_THAN, left=left, right=right)

    @staticmethod
    def _ge(left: Expr, right: Expr) -> Expr:
        return Expr(ExprType.NOT, right=Expr(
            ExprType.LESS_THAN, left=left, right=right))

    @staticmethod
    def _le(left: Expr, right: Expr) -> Expr:
        return Expr(ExprType.NOT, right=Expr(
            ExprType.GREATER_THAN, left=left, right=right))

    def _check_not_param(self, name: str, lineno: int) -> None:
        if self.param_stack and name in self.param_stack[-1]:
            raise ScPythonError(
                f"不能给自制积木参数 {name} 赋值；先赋给普通变量",
                path=self.module.path, line=lineno)

    def _list_name(self, node: ast.AST, lineno: int) -> str:
        if isinstance(node, ast.Name):
            name = node.id
            if self._is_list_name(name):
                return name
            if name in self.local_vars or name in self.module.declared_vars:
                raise ScPythonError(
                    f"{name} 是变量，不是列表", path=self.module.path,
                    line=lineno)
            return name
        raise ScPythonError("列表下标必须是变量名",
                            path=self.module.path, line=lineno)

    def _const_arg(self, args: List[ast.AST], index: int,
                   what: str) -> Any:
        if index >= len(args):
            raise ScPythonError(f"{what} 缺少参数",
                                path=self.module.path)
        return _constant(args[index], self.module.path, what)

    def _const_node(self, node: ast.AST) -> Any:
        return _constant(node, self.module.path, '扩展字段')

    # ---------- 调用语句 ----------

    def _compile_call_statement(self, call: ast.Call
                                ) -> Optional[Statement]:
        if isinstance(call.func, ast.Attribute) \
                and isinstance(call.func.value, ast.Name) \
                and call.func.value.id == 'debug':
            return self._compile_debug_statement(call.func.attr, call)
        if isinstance(call.func, ast.Name):
            name = call.func.id
            if name == 'ext':
                return self._generic_extension_statement(call)
            builtin = self._builtin_statement(name, call)
            if builtin is not None:
                return builtin
            function = self.module.functions.get(name)
            if function is not None:
                return self._procedure_call_statement(function, call)
            if name in _LIST_STATEMENT_FUNCTIONS:
                return self._list_statement(name, call)
            raise ScPythonError(
                f"未知函数 {name}；宏/自定义积木需要先定义",
                path=self.module.path, line=call.lineno)
        if isinstance(call.func, ast.Attribute):
            value = call.func.value
            if isinstance(value, ast.Name):
                if call.func.attr in _LIST_METHODS:
                    return self._list_method_statement(
                        value.id, call.func.attr, call)
                spec = self.compiler.extensions.resolve(
                    value.id, call.func.attr)
                if spec is not None:
                    return self._extension_statement(spec, call)
            raise ScPythonError(
                f"不支持的方法调用 {ast.unparse(call.func)}",
                path=self.module.path, line=call.lineno)
        raise ScPythonError("不支持的调用形式",
                            path=self.module.path, line=call.lineno)

    # ---------- 调试指令 ----------

    def _debug_target(self, node: ast.AST, action: str) -> str:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            return node.id
        raise ScPythonError(
            f"debug.{action} 的目标必须是变量名或字符串字面量",
            path=self.module.path, line=getattr(node, 'lineno', None))

    def _debug_default(self, name: str, action: str,
                       lineno: int) -> Any:
        """查找变量/列表在 init 中声明的默认值"""
        if name in self.module.variables:
            return self.module.variables[name]
        if name in self.module.lists:
            return list(self.module.lists[name])
        if not self.module.is_stage and name in self.compiler.stage_vars:
            return self.compiler.stage_vars[name]
        if not self.module.is_stage and name in self.compiler.stage_lists:
            return list(self.compiler.stage_lists[name])
        if name in self.local_vars:
            return self.local_vars[name]
        if name in self.local_lists:
            return list(self.local_lists[name])
        raise ScPythonError(
            f"debug.{action}: 找不到 {name} 的默认值；"
            "请先在 init 中用 var/list 声明",
            path=self.module.path, line=lineno)

    def _reset_statements(self, name: str, lineno: int) -> List[Statement]:
        if self._is_list_name(name):
            default = self._debug_default(name, 'reset', lineno)
            name, list_id = self.ensure_list(name)
            clear = Statement(BlockType.DELETE_ALL_FROM_LIST)
            clear.extra.update({'name': name, 'id': list_id})
            result = [clear]
            for item in default:
                add = Statement(BlockType.ADD_TO_LIST)
                add.extra.update({'name': name, 'id': list_id})
                add.value = _literal_expr(item)
                result.append(add)
            return result
        default = self._debug_default(name, 'reset', lineno)
        if isinstance(default, list):
            raise ScPythonError(
                f"{name} 是列表，不能按变量重置",
                path=self.module.path, line=lineno)
        return [self._set_var(name, _literal_expr(default))]

    def _compile_debug_statement(self, action: str, call: ast.Call
                                 ) -> Optional[Statement]:
        if call.keywords:
            raise ScPythonError(
                "debug 指令不支持关键字参数",
                path=self.module.path, line=call.lineno)
        args = list(call.args)
        lineno = call.lineno

        if action in ('set_var', 'set_value'):
            if len(args) != 2:
                raise ScPythonError(
                    "debug.set_var(变量, 值) 需要两个参数",
                    path=self.module.path, line=lineno)
            name = self._debug_target(args[0], action)
            if self._is_list_name(name):
                raise ScPythonError(
                    f"{name} 是列表；请使用 debug.reset({name!r})",
                    path=self.module.path, line=lineno)
            return self._set_var(name, self._expr(args[1]))

        if action == 'reset':
            names = [self._debug_target(arg, action) for arg in args]
            if not names:
                names = sorted(self.module.explicit_vars
                               | self.module.explicit_lists)
            for name in names:
                self.pending_debug.extend(
                    self._reset_statements(name, lineno))
            return None

        if action in ('print', 'trace', 'watch', 'log', 'assert'):
            # 编译期调试指令：不生成 Scratch 块，只在导出时提示
            self.compiler.warnings.append(
                f"[{self.module.name}] debug.{action}: {ast.unparse(call)}")
            return None

        raise ScPythonError(
            f"未知 debug 指令: {action}；支持 set_var / reset / "
            "print / trace / watch / assert",
            path=self.module.path, line=lineno)

    def _procedure_call_statement(self, function: FunctionInfo,
                                  call: ast.Call) -> Statement:
        args = self._call_args(call)
        if len(args) > len(function.params):
            raise ScPythonError(
                f"{function.name} 最多接受 {len(function.params)} 个参数",
                path=self.module.path, line=call.lineno)
        stmt = Statement(BlockType.PROCEDURE_CALL)
        stmt.extra.update({
            'name': function.name,
            'proccode': function.proccode,
            'args': [self._expr(arg) for arg in args],
            'arg_types': [param.type for param in function.params[:len(args)]],
            'argumentids': function.argumentids[:len(args)],
            'warp': function.warp,
        })
        return stmt

    def _call_args(self, call: ast.Call) -> List[ast.AST]:
        if call.keywords:
            raise ScPythonError(
                "自定义积木/内置积木不支持关键字参数",
                path=self.module.path, line=call.lineno)
        return list(call.args)

    def _list_statement(self, name: str, call: ast.Call) -> Statement:
        args = self._call_args(call)
        list_name = self._list_arg(args, 0, name)
        list_name, list_id = self.ensure_list(list_name)
        if name == 'add_to_list':
            self._require_args(args, 2, name)
            stmt = Statement(BlockType.ADD_TO_LIST)
            stmt.value = self._expr(args[1])
        elif name in ('delete_of_list', 'delete_item'):
            self._require_args(args, 2, name)
            stmt = Statement(BlockType.DELETE_FROM_LIST)
            stmt.value = self._expr(args[1])
        elif name == 'delete_all_of_list':
            self._require_args(args, 1, name)
            stmt = Statement(BlockType.DELETE_ALL_FROM_LIST)
        elif name == 'insert_in_list':
            self._require_args(args, 3, name)
            stmt = Statement(BlockType.INSERT_IN_LIST)
            stmt.value = self._expr(args[1])
            stmt.extra['item'] = self._expr(args[2])
        elif name == 'replace_in_list':
            self._require_args(args, 3, name)
            stmt = Statement(BlockType.REPLACE_IN_LIST)
            stmt.value = self._expr(args[1])
            stmt.extra['item'] = self._expr(args[2])
        else:
            raise ScPythonError(f"未知列表函数 {name}",
                                path=self.module.path, line=call.lineno)
        stmt.extra.update({'name': list_name, 'id': list_id})
        return stmt

    def _list_method_statement(self, list_name: str, method: str,
                               call: ast.Call) -> Statement:
        if (list_name in self.local_vars
                or (list_name in self.module.declared_vars
                    and not self._is_list_name(list_name))):
            raise ScPythonError(
                f"{list_name} 是变量，不能调用列表方法",
                path=self.module.path, line=call.lineno)
        list_name, list_id = self.ensure_list(list_name)
        args = self._call_args(call)
        if method == 'append':
            self._require_args(args, 1, 'append')
            stmt = Statement(BlockType.ADD_TO_LIST)
            stmt.value = self._expr(args[0])
        elif method == 'insert':
            self._require_args(args, 2, 'insert')
            stmt = Statement(BlockType.INSERT_IN_LIST)
            stmt.value = self._expr(args[0])
            stmt.extra['item'] = self._expr(args[1])
        elif method == 'clear':
            self._require_args(args, 0, 'clear')
            stmt = Statement(BlockType.DELETE_ALL_FROM_LIST)
        else:
            raise ScPythonError(
                f"列表方法 {method} 不能作为语句；仅支持 append/insert/clear",
                path=self.module.path, line=call.lineno)
        stmt.extra.update({'name': list_name, 'id': list_id})
        return stmt

    def _generic_extension_statement(self, call: ast.Call):
        if not isinstance(call.func, ast.Name) or call.func.id != 'ext':
            return None
        args = list(call.args)
        if len(args) < 2:
            raise ScPythonError("ext 需要 namespace 和 opcode",
                                path=self.module.path, line=call.lineno)
        namespace = str(self._const_node(args[0]))
        opcode = str(self._const_node(args[1]))
        inputs = []
        for keyword in call.keywords:
            if keyword.arg is None:
                raise ScPythonError("ext 不支持 **kwargs",
                                    path=self.module.path, line=call.lineno)
            inputs.append((keyword.arg, self._expr(keyword.value)))
        stmt = Statement(BlockType.EXTENSION)
        stmt.extra.update({
            'namespace': namespace,
            'opcode': opcode,
            'inputs': inputs,
            'fields': {},
        })
        self.used_extensions.add(namespace)
        return stmt

    def _extension_statement(self, spec: ExtensionBlock,
                             call: ast.Call) -> Statement:
        inputs, fields = bind_extension_args(
            spec, call.args, call.keywords, self._expr, self._const_node,
            self.module.path)
        stmt = Statement(BlockType.EXTENSION)
        stmt.extra.update({
            'namespace': spec.namespace,
            'opcode': spec.opcode,
            'inputs': inputs,
            'fields': fields,
        })
        self.used_extensions.add(spec.namespace)
        return stmt

    def _builtin_statement(self, name: str,
                           call: ast.Call) -> Optional[Statement]:
        if name in ('pen_clear', 'pen_down', 'pen_up', 'pen_stamp',
                    'set_pen_color', 'set_pen_size', 'change_pen_size',
                    'set_pen_param', 'change_pen_param',
                    'play_note', 'play_drum', 'set_tempo', 'rest',
                    'set_instrument'):
            spec = builtin_extension(name)
            if spec is None:
                return None
            namespace, opcode, slots = spec
            args = self._call_args(call)
            if len(args) != len(slots):
                raise ScPythonError(
                    f"{name} 需要 {len(slots)} 个参数",
                    path=self.module.path, line=call.lineno)
            stmt = Statement(BlockType.EXTENSION)
            stmt.extra.update({
                'namespace': namespace,
                'opcode': opcode,
                'inputs': [(slot, self._expr(arg))
                           for slot, arg in zip(slots, args)],
                'fields': {},
            })
            self.used_extensions.add(namespace)
            return stmt

        args = self._call_args(call)
        stmt: Optional[Statement] = None
        if name == 'move':
            stmt = Statement(BlockType.MOVE_STEPS)
            stmt.value = self._arg_or(args, 0, make_number(10))
        elif name == 'turn_right':
            stmt = Statement(BlockType.TURN_RIGHT)
            stmt.value = self._arg_or(args, 0, make_number(15))
        elif name == 'turn_left':
            stmt = Statement(BlockType.TURN_LEFT)
            stmt.value = self._arg_or(args, 0, make_number(15))
        elif name == 'goto':
            self._require_args(args, 2, name)
            stmt = Statement(BlockType.GO_TO_XY)
            stmt.extra['x'] = self._expr(args[0])
            stmt.extra['y'] = self._expr(args[1])
        elif name == 'goto_random':
            stmt = Statement(BlockType.GO_TO_RANDOM)
            stmt.extra['target'] = '_random_'
        elif name in ('glide', 'glide_to'):
            self._require_args(args, 3, name)
            stmt = Statement(BlockType.GLIDE_SECS_TO)
            stmt.value = self._expr(args[0])
            stmt.extra['x'] = self._expr(args[1])
            stmt.extra['y'] = self._expr(args[2])
        elif name == 'glide_to_target':
            self._require_args(args, 2, name)
            stmt = Statement(BlockType.GLIDE_TO)
            stmt.value = self._expr(args[0])
            stmt.extra['target'] = str(
                self._const_node(self._need(args, 1, name)))
        elif name == 'point_in_direction':
            stmt = Statement(BlockType.POINT_IN_DIRECTION)
            stmt.value = self._arg_or(args, 0, make_number(90))
        elif name == 'point_towards':
            stmt = Statement(BlockType.POINT_TOWARDS)
            stmt.extra['target'] = str(
                self._const_node(self._need(args, 0, name)))
        elif name == 'set_rotation_style':
            stmt = Statement(BlockType.SET_ROTATION_STYLE)
            stmt.extra['style'] = str(
                self._const_node(self._need(args, 0, name)))
        elif name == 'change_x':
            stmt = Statement(BlockType.CHANGE_X)
            stmt.value = self._arg_or(args, 0, make_number(10))
        elif name == 'set_x':
            stmt = Statement(BlockType.SET_X)
            stmt.value = self._arg_or(args, 0, make_number(0))
        elif name == 'change_y':
            stmt = Statement(BlockType.CHANGE_Y)
            stmt.value = self._arg_or(args, 0, make_number(10))
        elif name == 'set_y':
            stmt = Statement(BlockType.SET_Y)
            stmt.value = self._arg_or(args, 0, make_number(0))
        elif name == 'if_on_edge_bounce':
            stmt = Statement(BlockType.IF_ON_EDGE_BOUNCE)
        elif name == 'say':
            stmt = Statement(BlockType.SAY)
            stmt.value = self._arg_or(args, 0, make_string(''))
        elif name == 'say_for':
            self._require_args(args, 2, name)
            stmt = Statement(BlockType.SAY_FOR_SECS)
            stmt.extra['message'] = self._expr(args[0])
            stmt.value = self._expr(args[1])
        elif name == 'think':
            stmt = Statement(BlockType.THINK)
            stmt.value = self._arg_or(args, 0, make_string(''))
        elif name == 'think_for':
            self._require_args(args, 2, name)
            stmt = Statement(BlockType.THINK_FOR_SECS)
            stmt.extra['message'] = self._expr(args[0])
            stmt.value = self._expr(args[1])
        elif name == 'show':
            stmt = Statement(BlockType.SHOW)
        elif name == 'hide':
            stmt = Statement(BlockType.HIDE)
        elif name == 'switch_costume':
            stmt = Statement(BlockType.SWITCH_COSTUME)
            stmt.value = self._arg_or(args, 0, make_string('costume1'))
        elif name == 'next_costume':
            stmt = Statement(BlockType.NEXT_COSTUME)
        elif name == 'switch_backdrop':
            stmt = Statement(BlockType.SWITCH_BACKDROP)
            stmt.value = self._arg_or(args, 0, make_string('backdrop1'))
        elif name == 'next_backdrop':
            stmt = Statement(BlockType.NEXT_BACKDROP)
        elif name == 'set_size':
            stmt = Statement(BlockType.SET_SIZE)
            stmt.value = self._arg_or(args, 0, make_number(100))
        elif name == 'change_size':
            stmt = Statement(BlockType.CHANGE_SIZE)
            stmt.value = self._arg_or(args, 0, make_number(10))
        elif name in ('set_effect', 'change_effect'):
            self._require_args(args, 2, name)
            stmt = Statement(
                BlockType.SET_EFFECT if name == 'set_effect'
                else BlockType.CHANGE_EFFECT)
            stmt.extra['effect'] = str(self._const_node(args[0]))
            stmt.value = self._expr(args[1])
        elif name == 'clear_effects':
            stmt = Statement(BlockType.CLEAR_EFFECTS)
        elif name in ('go_to_front', 'go_to_back'):
            stmt = Statement(
                BlockType.GO_TO_FRONT if name == 'go_to_front'
                else BlockType.GO_TO_BACK)
            stmt.extra['where'] = 'front' if name == 'go_to_front' else 'back'
        elif name in ('go_forward', 'go_backward'):
            stmt = Statement(
                BlockType.GO_FORWARD_LAYERS if name == 'go_forward'
                else BlockType.GO_BACKWARD_LAYERS)
            stmt.extra['direction'] = (
                'forward' if name == 'go_forward' else 'backward')
            stmt.value = self._arg_or(args, 0, make_number(1))
        elif name == 'play_sound':
            stmt = Statement(BlockType.PLAY_SOUND)
            stmt.value = self._arg_or(args, 0, make_string('sound1'))
        elif name == 'play_sound_until_done':
            stmt = Statement(BlockType.PLAY_SOUND_UNTIL_DONE)
            stmt.value = self._arg_or(args, 0, make_string('sound1'))
        elif name == 'stop_all_sounds':
            stmt = Statement(BlockType.STOP_ALL_SOUNDS)
        elif name == 'set_volume':
            stmt = Statement(BlockType.SET_VOLUME)
            stmt.value = self._arg_or(args, 0, make_number(100))
        elif name == 'change_volume':
            stmt = Statement(BlockType.CHANGE_VOLUME)
            stmt.value = self._arg_or(args, 0, make_number(10))
        elif name == 'wait':
            stmt = Statement(BlockType.WAIT)
            stmt.value = self._arg_or(args, 0, make_number(1))
        elif name == 'wait_until':
            stmt = Statement(BlockType.WAIT_UNTIL)
            stmt.condition = self._arg_or(args, 0, make_boolean(True))
        elif name == 'broadcast':
            message = str(self._const_node(self._need(args, 0, name)))
            stmt = Statement(BlockType.BROADCAST)
            stmt.value = make_string(message)
            if message not in self.sprite.broadcasts:
                self.sprite.broadcasts.append(message)
        elif name == 'broadcast_and_wait':
            message = str(self._const_node(self._need(args, 0, name)))
            stmt = Statement(BlockType.BROADCAST_AND_WAIT)
            stmt.value = make_string(message)
            if message not in self.sprite.broadcasts:
                self.sprite.broadcasts.append(message)
        elif name == 'create_clone':
            stmt = Statement(BlockType.CREATE_CLONE_OF)
            target = '_myself_'
            if args:
                target = str(self._const_node(args[0]))
            stmt.value = make_string(target)
        elif name == 'delete_this_clone':
            stmt = Statement(BlockType.DELETE_THIS_CLONE)
        elif name == 'stop_all':
            stmt = Statement(BlockType.STOP)
            stmt.extra['option'] = 'all'
        elif name == 'stop_this_script':
            stmt = Statement(BlockType.STOP)
            stmt.extra['option'] = 'this script'
        elif name == 'stop_other_scripts':
            stmt = Statement(BlockType.STOP)
            stmt.extra['option'] = 'other scripts in sprite'
        elif name == 'reset_timer':
            stmt = Statement(BlockType.RESET_TIMER)
        elif name in ('ask_and_wait', 'ask'):
            stmt = Statement(BlockType.ASK_AND_WAIT)
            stmt.value = self._arg_or(args, 0, make_string(''))
        elif name == 'set_drag_mode':
            stmt = Statement(BlockType.SET_DRAG_MODE)
            stmt.extra['mode'] = str(
                self._const_node(self._need(args, 0, name)))
        elif name == 'show_variable':
            var_name = str(self._const_node(self._need(args, 0, name)))
            _, var_id = self.ensure_var(var_name)
            stmt = Statement(BlockType.SHOW_VARIABLE)
            stmt.extra.update({'name': var_name, 'id': var_id})
        elif name == 'hide_variable':
            var_name = str(self._const_node(self._need(args, 0, name)))
            _, var_id = self.ensure_var(var_name)
            stmt = Statement(BlockType.HIDE_VARIABLE)
            stmt.extra.update({'name': var_name, 'id': var_id})
        elif name == 'show_list':
            list_name = str(self._const_node(self._need(args, 0, name)))
            _, list_id = self.ensure_list(list_name)
            stmt = Statement(BlockType.SHOW_LIST)
            stmt.extra.update({'name': list_name, 'id': list_id})
        elif name == 'hide_list':
            list_name = str(self._const_node(self._need(args, 0, name)))
            _, list_id = self.ensure_list(list_name)
            stmt = Statement(BlockType.HIDE_LIST)
            stmt.extra.update({'name': list_name, 'id': list_id})
        elif name == 'incr_counter':
            stmt = Statement(BlockType.INCR_COUNTER)
        elif name == 'clear_counter':
            stmt = Statement(BlockType.CLEAR_COUNTER)
        return stmt

    # ---------- 表达式 ----------

    def _expr(self, node: ast.AST) -> Expr:
        if isinstance(node, ast.Constant):
            value = node.value
            if isinstance(value, bool):
                return make_boolean(value)
            if isinstance(value, (int, float)):
                return make_number(value)
            if isinstance(value, str):
                return make_string(value)
            raise ScPythonError(
                f"不支持的字面量: {value!r}", path=self.module.path,
                line=getattr(node, 'lineno', None))

        if isinstance(node, ast.Name):
            if self.param_stack and node.id in self.param_stack[-1]:
                param = self.param_stack[-1][node.id]
                expr = Expr(ExprType.ARGUMENT, name=param.name)
                expr.extra['boolean'] = param.type == 'b'
                return expr
            if node.id in self.local_vars:
                return self._var_expr(node.id)
            if self._is_list_name(node.id):
                raise ScPythonError(
                    "列表不能作为值使用；请用 item_of/length_of/"
                    "list_contents/contains_item",
                    path=self.module.path, line=node.lineno)
            return self._var_expr(node.id)

        if isinstance(node, ast.BinOp):
            operator = {
                ast.Add: '+', ast.Sub: '-', ast.Mult: '*',
                ast.Div: '/', ast.Mod: '%',
            }.get(type(node.op))
            if operator is None:
                raise ScPythonError(
                    "只支持 + - * / % 运算（Scratch 没有幂运算积木）",
                    path=self.module.path, line=node.lineno)
            return _binary(operator, self._expr(node.left),
                           self._expr(node.right))

        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.Not):
                return Expr(ExprType.NOT, right=self._expr(node.operand))
            if isinstance(node.op, ast.USub):
                return Expr(ExprType.BINARY_OP, name='-',
                            left=make_number(0),
                            right=self._expr(node.operand))
            if isinstance(node.op, ast.UAdd):
                return self._expr(node.operand)
            raise ScPythonError("不支持的一元运算",
                                path=self.module.path, line=node.lineno)

        if isinstance(node, ast.BoolOp):
            values = [self._expr(item) for item in node.values]
            result = values[0]
            kind = ExprType.AND if isinstance(node.op, ast.And) else ExprType.OR
            for value in values[1:]:
                result = Expr(kind, left=result, right=value)
            return result

        if isinstance(node, ast.Compare):
            return self._compare(node)

        if isinstance(node, ast.Call):
            return self._call_expr(node)

        if isinstance(node, ast.Subscript):
            list_name = self._list_name(node.value, node.lineno)
            list_name, list_id = self.ensure_list(list_name)
            return self._list_expr(
                ExprType.ITEM_OF_LIST, list_name, list_id,
                self._expr(node.slice))

        if isinstance(node, ast.IfExp):
            raise ScPythonError(
                "不支持条件表达式 a if c else b；请用 if 语句",
                path=self.module.path, line=node.lineno)

        raise ScPythonError(
            f"不支持的表达式: {type(node).__name__}",
            path=self.module.path, line=getattr(node, 'lineno', None))

    def _compare(self, node: ast.Compare) -> Expr:
        if len(node.ops) == 1:
            op = node.ops[0]
            if isinstance(op, (ast.In, ast.NotIn)):
                return self._compare_in(
                    op, node.left, node.comparators[0], node)
            return self._compare_one(
                op, self._expr(node.left),
                self._expr(node.comparators[0]), node)
        # a < b < c -> (a < b) and (b < c)
        result = None
        left = node.left
        for op, right in zip(node.ops, node.comparators):
            if isinstance(op, (ast.In, ast.NotIn)):
                part = self._compare_in(op, left, right, node)
            else:
                part = self._compare_one(
                    op, self._expr(left), self._expr(right), node)
            result = part if result is None else Expr(
                ExprType.AND, left=result, right=part)
            left = right
        return result

    def _compare_one(self, op: ast.cmpop, left: Expr, right: Expr,
                     node: ast.AST) -> Expr:
        if isinstance(op, ast.Eq):
            return Expr(ExprType.EQUAL, left=left, right=right)
        if isinstance(op, ast.NotEq):
            return Expr(ExprType.NOT, right=Expr(
                ExprType.EQUAL, left=left, right=right))
        if isinstance(op, ast.Lt):
            return Expr(ExprType.LESS_THAN, left=left, right=right)
        if isinstance(op, ast.Gt):
            return Expr(ExprType.GREATER_THAN, left=left, right=right)
        if isinstance(op, ast.LtE):
            return Expr(ExprType.NOT, right=Expr(
                ExprType.GREATER_THAN, left=left, right=right))
        if isinstance(op, ast.GtE):
            return Expr(ExprType.NOT, right=Expr(
                ExprType.LESS_THAN, left=left, right=right))
        raise ScPythonError("不支持 is / is not 比较",
                            path=self.module.path,
                            line=getattr(node, 'lineno', None))

    def _compare_in(self, op: ast.cmpop, left_node: ast.AST,
                    right_node: ast.AST, node: ast.AST) -> Expr:
        needle = self._expr(left_node)
        if isinstance(right_node, ast.Name) and \
                self._is_list_name(right_node.id):
            name, list_id = self.ensure_list(right_node.id)
            contains = self._list_expr(
                ExprType.LIST_CONTAINS, name, list_id, needle)
        elif isinstance(right_node, ast.Constant) and \
                isinstance(right_node.value, str):
            contains = Expr(ExprType.CONTAINS_STRING, left=needle,
                            right=make_string(right_node.value))
        else:
            raise ScPythonError(
                "in 只支持「值 in 列表变量」或「子串 in '字符串常量'」；"
                "其他情况请用 contains/has_item 函数",
                path=self.module.path,
                line=getattr(node, 'lineno', None))
        if isinstance(op, ast.NotIn):
            return Expr(ExprType.NOT, right=contains)
        return contains

    def _call_expr(self, call: ast.Call) -> Expr:
        if isinstance(call.func, ast.Name):
            name = call.func.id
            if name == 'ext':
                return self._generic_extension_expr(call)
            builtin = self._builtin_expr(name, call)
            if builtin is not None:
                return builtin
            function = self.module.functions.get(name)
            if function is not None:
                return self._procedure_call_expr(function, call)
            if name in _LIST_EXPR_FUNCTIONS:
                return self._list_expr_function(name, call)
            raise ScPythonError(
                f"未知函数 {name}；宏/自定义积木需要先定义",
                path=self.module.path, line=call.lineno)
        if isinstance(call.func, ast.Attribute):
            value = call.func.value
            if isinstance(value, ast.Name):
                if call.func.attr == 'index':
                    list_name, list_id = self.ensure_list(value.id)
                    args = self._call_args(call)
                    self._require_args(args, 1, 'index')
                    return self._list_expr(
                        ExprType.ITEM_NUMBER_OF_LIST, list_name, list_id,
                        self._expr(args[0]))
                spec = self.compiler.extensions.resolve(
                    value.id, call.func.attr)
                if spec is not None:
                    inputs, fields = bind_extension_args(
                        spec, call.args, call.keywords, self._expr,
                        self._const_node, self.module.path)
                    self.used_extensions.add(spec.namespace)
                    expr = Expr(ExprType.EXTENSION_CALL)
                    expr.extra.update({
                        'namespace': spec.namespace,
                        'opcode': spec.opcode,
                        'inputs': inputs,
                        'fields': fields,
                    })
                    return expr
                # math.xxx / random.xxx 语法糖
                if value.id == 'math' and call.func.attr in _MATH_FUNCTIONS:
                    return self._math_expr(call.func.attr, call)
                if value.id == 'random' and call.func.attr in (
                        'randint', 'random'):
                    return self._random_expr(call)
            raise ScPythonError(
                f"不支持的表达式调用 {ast.unparse(call.func)}",
                path=self.module.path, line=call.lineno)
        raise ScPythonError("不支持的表达式调用",
                            path=self.module.path, line=call.lineno)

    def _procedure_call_expr(self, function: FunctionInfo,
                             call: ast.Call) -> Expr:
        args = self._call_args(call)
        if len(args) > len(function.params):
            raise ScPythonError(
                f"{function.name} 最多接受 {len(function.params)} 个参数",
                path=self.module.path, line=call.lineno)
        expr = Expr(ExprType.PROCEDURE_CALL, name=function.name,
                    args=[self._expr(arg) for arg in args])
        expr.extra.update({
            'proccode': function.proccode,
            'arg_types': [param.type
                          for param in function.params[:len(args)]],
            'argumentids': function.argumentids[:len(args)],
            'warp': function.warp,
        })
        return expr

    def _list_expr_function(self, name: str, call: ast.Call) -> Expr:
        args = self._call_args(call)
        list_name = self._list_arg(args, 0, name)
        list_name, list_id = self.ensure_list(list_name)
        if name == 'item_of':
            self._require_args(args, 2, name)
            return self._list_expr(
                ExprType.ITEM_OF_LIST, list_name, list_id,
                self._expr(args[1]))
        if name == 'item_number_of':
            self._require_args(args, 2, name)
            return self._list_expr(
                ExprType.ITEM_NUMBER_OF_LIST, list_name, list_id,
                self._expr(args[1]))
        if name == 'length_of':
            self._require_args(args, 1, name)
            return self._list_expr(
                ExprType.LENGTH_OF_LIST, list_name, list_id)
        if name == 'contains_item':
            self._require_args(args, 2, name)
            return self._list_expr(
                ExprType.LIST_CONTAINS, list_name, list_id,
                self._expr(args[1]))
        if name == 'list_contents':
            self._require_args(args, 1, name)
            return self._list_expr(
                ExprType.LIST_ACCESS, list_name, list_id)
        raise ScPythonError(f"未知列表表达式 {name}",
                            path=self.module.path, line=call.lineno)

    def _builtin_expr(self, name: str,
                      call: ast.Call) -> Optional[Expr]:
        args = self._call_args(call)
        if name in _MATH_FUNCTIONS:
            return self._math_expr(name, call)
        if name == 'round':
            self._require_args(args, 1, name)
            return Expr(ExprType.ROUND, right=self._expr(args[0]))
        if name == 'abs':
            self._require_args(args, 1, name)
            return Expr(ExprType.ABS, right=self._expr(args[0]))
        if name == 'join':
            self._require_args(args, 2, name)
            return Expr(ExprType.JOIN, left=self._expr(args[0]),
                        right=self._expr(args[1]))
        if name == 'letter_of':
            self._require_args(args, 2, name)
            return Expr(ExprType.LETTER_OF, left=self._expr(args[0]),
                        right=self._expr(args[1]))
        if name in ('length', 'len'):
            self._require_args(args, 1, name)
            if isinstance(args[0], ast.Name) and \
                    self._is_list_name(args[0].id):
                list_name, list_id = self.ensure_list(args[0].id)
                return self._list_expr(
                    ExprType.LENGTH_OF_LIST, list_name, list_id)
            return Expr(ExprType.LENGTH_OF_STRING,
                        right=self._expr(args[0]))
        if name == 'contains':
            self._require_args(args, 2, name)
            return Expr(ExprType.CONTAINS_STRING,
                        left=self._expr(args[0]),
                        right=self._expr(args[1]))
        if name in ('random', 'randint'):
            return self._random_expr(call)
        if name in _SENSING_FUNCTIONS:
            self._require_args(args, 0, name)
            return Expr(_SENSING_FUNCTIONS[name])
        if name == 'username':
            self._require_args(args, 0, name)
            return Expr(ExprType.FUNCTION_CALL, name='username')
        if name == 'current':
            self._require_args(args, 1, name)
            unit = str(self._const_node(args[0])).upper()
            return Expr(ExprType.CURRENT, name=unit)
        if name == 'key_pressed':
            self._require_args(args, 1, name)
            key = str(self._const_node(args[0]))
            return Expr(ExprType.FUNCTION_CALL, name='key_pressed',
                        args=[make_string(key)])
        if name == 'touching':
            self._require_args(args, 1, name)
            target = str(self._const_node(args[0]))
            return Expr(ExprType.FUNCTION_CALL, name='touching',
                        args=[make_string(target)])
        if name == 'distance_to':
            self._require_args(args, 1, name)
            target = str(self._const_node(args[0]))
            return Expr(ExprType.FUNCTION_CALL, name='distance_to',
                        args=[make_string(target)])
        if name in _PROPERTY_FUNCTIONS:
            self._require_args(args, 0, name)
            return Expr(ExprType.PROPERTY,
                        name=_PROPERTY_FUNCTIONS[name])
        if name == 'to_number':
            self._require_args(args, 1, name)
            return _binary('+', self._expr(args[0]), make_number(0))
        if name == 'to_string':
            self._require_args(args, 1, name)
            return Expr(ExprType.JOIN, left=self._expr(args[0]),
                        right=make_string(''))
        if name == 'to_boolean':
            self._require_args(args, 1, name)
            return Expr(ExprType.NOT,
                        right=Expr(ExprType.NOT, right=self._expr(args[0])))
        if name in ('str', 'int', 'float', 'bool'):
            self._require_args(args, 1, name)
            value = self._expr(args[0])
            if name == 'str':
                return Expr(ExprType.JOIN, left=value,
                            right=make_string(''))
            if name == 'bool':
                return Expr(ExprType.NOT,
                            right=Expr(ExprType.NOT, right=value))
            return _binary('+', value, make_number(0))
        if name == 'ext':
            return self._generic_extension_expr(call)
        return None

    def _math_expr(self, name: str, call: ast.Call) -> Expr:
        args = self._call_args(call)
        self._require_args(args, 1, name)
        return Expr(_MATH_FUNCTIONS[name], right=self._expr(args[0]))

    def _random_expr(self, call: ast.Call) -> Expr:
        args = self._call_args(call)
        self._require_args(args, 2, 'random')
        return Expr(ExprType.RANDOM, left=self._expr(args[0]),
                    right=self._expr(args[1]))

    def _generic_extension_expr(self, call: ast.Call) -> Expr:
        args = list(call.args)
        if len(args) < 2:
            raise ScPythonError("ext 需要 namespace 和 opcode",
                                path=self.module.path, line=call.lineno)
        namespace = str(self._const_node(args[0]))
        opcode = str(self._const_node(args[1]))
        inputs = []
        for keyword in call.keywords:
            if keyword.arg is None:
                raise ScPythonError("ext 不支持 **kwargs",
                                    path=self.module.path, line=call.lineno)
            inputs.append((keyword.arg, self._expr(keyword.value)))
        expr = Expr(ExprType.EXTENSION_CALL)
        expr.extra.update({
            'namespace': namespace,
            'opcode': opcode,
            'inputs': inputs,
            'fields': {},
        })
        self.used_extensions.add(namespace)
        return expr

    # ---------- 参数辅助 ----------

    def _arg_or(self, args: List[ast.AST], index: int, default: Expr) -> Expr:
        return self._expr(args[index]) if index < len(args) else default

    @staticmethod
    def _require_args(args: List[ast.AST], count: int, name: str,
                      path: str = '') -> None:
        if len(args) != count:
            raise ScPythonError(
                f"{name} 需要 {count} 个参数，收到 {len(args)} 个", path=path)

    def _need(self, args: List[ast.AST], index: int,
              name: str) -> ast.AST:
        if index >= len(args):
            raise ScPythonError(f"{name} 缺少第 {index + 1} 个参数",
                                path=self.module.path)
        return args[index]

    def _list_arg(self, args: List[ast.AST], index: int,
                  name: str) -> str:
        node = self._need(args, index, name)
        return self._list_name(node, getattr(node, 'lineno', 0))


# ===================== 项目编译 =====================

class ProjectCompiler:
    """扫描工程目录并编译为 ProjectIR"""

    def __init__(self, project_root: str, verbose: bool = False):
        self.project_root = os.path.abspath(project_root)
        self.verbose = verbose
        self.warnings: List[str] = []
        self.assets: Dict[str, bytes] = {}
        self.asset_library = AssetLibrary(self.project_root, self.assets)
        self.extensions = ExtensionRegistry(self.project_root)
        self.stage_vars: Dict[str, Any] = {}
        self.stage_var_ids: Dict[str, str] = {}
        self.stage_lists: Dict[str, List[Any]] = {}
        self.stage_list_ids: Dict[str, str] = {}
        self.declared_extensions: set = set()
        self.used_extensions: set = set()
        self.last_project: Optional[ProjectIR] = None

    # ---------- 扫描 ----------

    def find_stage(self) -> str:
        candidates = []
        for entry in os.listdir(self.project_root):
            path = os.path.join(self.project_root, entry)
            if not os.path.isfile(path) or not entry.lower().endswith(
                    '.scpy'):
                continue
            if os.path.splitext(entry)[0].lower() == 'stage':
                candidates.append(path)
        if not candidates:
            raise ScPythonError(
                "工程根目录缺少舞台文件 stage.scpy", path=self.project_root)
        if len(candidates) > 1:
            raise ScPythonError(
                "工程根目录只能有一个舞台文件 stage.scpy",
                path=self.project_root)
        return candidates[0]

    def find_macros(self) -> str:
        path = os.path.join(self.project_root, 'macros.scpy')
        return path if os.path.isfile(path) else ''

    def _load_extension_urls(self) -> Dict[str, str]:
        """读取 TurboWarp 第三方扩展 URL（extension_urls.json）"""
        path = os.path.join(self.project_root, 'extension_urls.json')
        if not os.path.isfile(path):
            return {}
        try:
            with open(path, encoding='utf-8') as handle:
                data = json.load(handle)
        except (OSError, ValueError) as error:
            raise ScPythonError(
                f"extension_urls.json 解析失败: {error}", path=path) from error
        if not isinstance(data, dict):
            raise ScPythonError(
                "extension_urls.json 必须是 {扩展ID: URL} 对象", path=path)
        return {str(name): str(url) for name, url in data.items() if url}

    def find_roles(self, stage_path: str) -> List[Tuple[str, str]]:
        roles = []
        stage_abs = os.path.abspath(stage_path)
        macros_abs = os.path.abspath(self.find_macros()) \
            if self.find_macros() else ''
        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = sorted(
                name for name in dirs
                if name not in ('assets', '__pycache__')
                and not name.startswith('.'))
            for filename in sorted(files):
                if not filename.lower().endswith('.scpy'):
                    continue
                path = os.path.abspath(os.path.join(root, filename))
                if path == stage_abs or path == macros_abs:
                    continue
                stem = os.path.splitext(filename)[0].lower()
                if stem == 'macros':
                    self.warnings.append(
                        f"忽略子目录中的宏文件: {path}")
                    continue
                if stem == 'stage':
                    raise ScPythonError(
                        "舞台文件 stage.scpy 只能放在工程根目录",
                        path=path)
                rel = os.path.relpath(path, self.project_root)
                rel_no_ext = os.path.splitext(rel)[0]
                parts = rel_no_ext.replace('\\', '/').split('/')
                name = '//'.join(parts)
                roles.append((path, name))
        return roles

    # ---------- 宏 ----------

    def merge_macros(self, module: ModuleInfo,
                     macros: Dict[str, FunctionInfo]) -> None:
        if not macros:
            return
        used = set()

        def scan(node):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call) and isinstance(
                        sub.func, ast.Name) and sub.func.id in macros:
                    used.add(sub.func.id)

        scan(module.tree)
        changed = True
        while changed:
            changed = False
            for name in list(used):
                info = macros[name]
                before = len(used)
                scan(info.node)
                if len(used) != before:
                    changed = True

        for name in sorted(used):
            if name in module.functions:
                continue
            info = macros[name]
            module.functions[name] = info
            module.source_order.insert(0, ('def', info))
            self._infer_macro_symbols(module, info.node)

    def _infer_macro_symbols(self, module: ModuleInfo,
                             node: ast.FunctionDef) -> None:
        for sub in ast.walk(node):
            if isinstance(sub, ast.Assign):
                for target in sub.targets:
                    if isinstance(target, ast.Name):
                        module.declared_vars.add(target.id)
                        module.variables.setdefault(target.id, 0)
                    elif isinstance(target, ast.Subscript) and isinstance(
                            target.value, ast.Name):
                        module.declared_lists.add(target.value.id)
            elif isinstance(sub, ast.For) and isinstance(
                    sub.iter, ast.Name):
                module.declared_lists.add(sub.iter.id)

    # ---------- 编译 ----------

    def compile(self) -> ProjectIR:
        if self.last_project is not None:
            return self.last_project
        if not os.path.isdir(self.project_root):
            raise ScPythonError(
                f"工程目录不存在: {self.project_root}",
                path=self.project_root)
        stage_path = self.find_stage()
        macros_path = self.find_macros()
        macros = analyze_macros(macros_path) if macros_path else {}

        stage_module = ModuleAnalyzer(
            stage_path, 'stage.scpy', True).analyze()
        self.merge_macros(stage_module, macros)
        self.declared_extensions.update(stage_module.extensions)

        project = ProjectIR()
        project.extensions = set()
        project.extension_urls = self._load_extension_urls()
        project.meta = {
            'semver': '3.0.0',
            # 必须是 x.y.z 或 x.y.z-suffix；TurboWarp 会按该正则校验
            'vm': '0.11.0',
            'agent': 'ScPython exporter',
        }

        stage_builder = RoleBuilder(stage_module, 0, self)
        stage_sprite = stage_builder.build()
        project.add_sprite(stage_sprite)
        self.used_extensions.update(stage_builder.used_extensions)

        role_specs = self.find_roles(stage_path)
        for index, (path, name) in enumerate(role_specs, 1):
            rel_path = os.path.relpath(path, self.project_root)
            module = ModuleAnalyzer(path, rel_path, False).analyze()
            # init 中显式写的 name 优先于文件名
            module.name = module.meta.get('name') or name
            self.merge_macros(module, macros)
            self.declared_extensions.update(module.extensions)
            builder = RoleBuilder(module, index, self)
            sprite = builder.build()
            self.used_extensions.update(builder.used_extensions)
            project.add_sprite(sprite)

        project.assets = self.assets
        project.extensions = self.declared_extensions | self.used_extensions
        project.warnings = {}
        self.last_project = project
        return project

    def export(self, output_path: str) -> str:
        from scratch_writer import write_scratch_project

        project = self.compile()
        data = write_scratch_project(project)
        validate_sb3_json(data, output_path)
        # 舞台背景/角色资源已经由 write_project 写入 costumes/sounds；
        # 这里只负责把资源字节写入 sb3。
        output_path = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        if output_path.lower().endswith('.json'):
            with open(output_path, 'w', encoding='utf-8') as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False)
            return output_path

        import zipfile
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                'project.json',
                json.dumps(data, ensure_ascii=False))
            for name, content in self.assets.items():
                archive.writestr(name, content)
        return output_path


_SB3_VERSION_RE = re.compile(r'^(\d+\.\d+\.\d+)(-.+)?$')


def validate_sb3_json(data: dict, path: str = '') -> None:
    """校验 Scratch/TurboWarp 加载 sb3 时会检查的关键结构。

    主要防止 ``meta.vm`` 之类的小问题导致整个项目无法打开。
    不追求完整 JSON Schema，只覆盖必需字段与类型。
    """
    if not isinstance(data, dict):
        raise ScPythonError("project.json 顶层必须是对象", path=path)
    meta = data.get('meta')
    if not isinstance(meta, dict):
        raise ScPythonError("project.json 缺少 meta", path=path)
    vm = meta.get('vm')
    if not isinstance(vm, str) or not _SB3_VERSION_RE.match(vm):
        raise ScPythonError(
            f"meta.vm 必须是 x.y.z（可带 -suffix），当前为 {vm!r}",
            path=path)
    semver = meta.get('semver')
    if not isinstance(semver, str) or not _SB3_VERSION_RE.match(semver):
        raise ScPythonError(
            f"meta.semver 必须是 x.y.z（可带 -suffix），当前为 {semver!r}",
            path=path)

    targets = data.get('targets')
    if not isinstance(targets, list) or not targets:
        raise ScPythonError("targets 必须是非空数组", path=path)
    if not targets[0].get('isStage'):
        raise ScPythonError("targets[0] 必须是舞台", path=path)

    common = ('isStage', 'name', 'variables', 'lists', 'broadcasts',
              'blocks', 'comments', 'currentCostume', 'costumes',
              'sounds', 'volume', 'layerOrder')
    stage_keys = ('tempo', 'videoTransparency', 'videoState',
                  'textToSpeechLanguage')
    sprite_keys = ('visible', 'x', 'y', 'size', 'direction', 'draggable',
                   'rotationStyle')
    for index, target in enumerate(targets):
        if not isinstance(target, dict):
            raise ScPythonError(f"targets[{index}] 必须是对象", path=path)
        missing = [key for key in common if key not in target]
        if missing:
            raise ScPythonError(
                f"target {target.get('name', index)!r} 缺少字段: "
                f"{', '.join(missing)}", path=path)
        required = stage_keys if target.get('isStage') else sprite_keys
        missing = [key for key in required if key not in target]
        if missing:
            raise ScPythonError(
                f"target {target.get('name', index)!r} 缺少字段: "
                f"{', '.join(missing)}", path=path)
        for key in ('variables', 'lists', 'broadcasts', 'blocks', 'comments'):
            if not isinstance(target.get(key), dict):
                raise ScPythonError(
                    f"target {target.get('name', index)!r} 的 {key} 必须是对象",
                    path=path)
        if not isinstance(target.get('costumes'), list):
            raise ScPythonError(
                f"target {target.get('name', index)!r} 的 costumes 必须是数组",
                path=path)
        for costume in target['costumes']:
            for key in ('name', 'assetId', 'md5ext', 'dataFormat',
                        'rotationCenterX', 'rotationCenterY'):
                if key not in costume:
                    raise ScPythonError(
                        f"造型缺少字段 {key}: {costume!r}", path=path)
        if not isinstance(target.get('sounds'), list):
            raise ScPythonError(
                f"target {target.get('name', index)!r} 的 sounds 必须是数组",
                path=path)
        for sound in target['sounds']:
            for key in ('name', 'assetId', 'md5ext', 'dataFormat'):
                if key not in sound:
                    raise ScPythonError(
                        f"声音缺少字段 {key}: {sound!r}", path=path)

    extensions = data.get('extensions')
    if not isinstance(extensions, list) or any(
            not isinstance(item, str) for item in extensions):
        raise ScPythonError("extensions 必须是字符串数组", path=path)
    if not isinstance(data.get('monitors'), list):
        raise ScPythonError("monitors 必须是数组", path=path)


def _chain(statements: List[Statement]) -> Optional[Statement]:
    result = None
    for stmt in reversed(statements):
        stmt.next = result
        result = stmt
    return result


def _with_prefix(prefix: List[Statement], stmt: Statement) -> Statement:
    """把前置语句接到 stmt 前面，返回新的链头"""
    return _chain(prefix + [stmt])


def _binary(operator: str, left: Expr, right: Expr) -> Expr:
    return Expr(ExprType.BINARY_OP, name=operator, left=left, right=right)


def _number(value: Any) -> Any:
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return value
    return 0


def _contains_break_continue(body: List[ast.stmt]) -> bool:
    for stmt in body:
        if isinstance(stmt, (ast.Break, ast.Continue)):
            return True
        if isinstance(stmt, ast.If):
            if _contains_break_continue(stmt.body) or \
                    _contains_break_continue(stmt.orelse):
                return True
        # 嵌套循环自己处理 break/continue
    return False
