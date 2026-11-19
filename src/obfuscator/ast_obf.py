# -*- coding: utf-8 -*-
"""生成 Python 的 AST 级混淆 v2。

变换管线（顺序敏感）：

1. 删除 docstring；
2. 重命名模块级函数/类；
3. 重命名类方法（黑名单 + 外来属性收集，避免破坏 threading/os 等同名方法）；
4. 属性访问派发表：Load -> ``getattr(obj, key)``，Store/Delete 语句 ->
   ``setattr``/``delattr``——把 Scratch 方法名从 ``co_names`` 中清除；
5. 全部字符串常量进入链式加密表（含派发表 key）；
6. 注入垃圾函数与死分支；
7. 顶层 ``def`` 拆分为函数簇（懒加载 trampoline）；
8. 抹平所有 AST 行号。

处理后的 AST 由 payload 模块编译、加密并嵌入加载器。
"""

from __future__ import annotations

import ast
import copy
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

# loader 会在 exec(stage1) 前注入这些模块绑定
LOADER_MODULES = (
    'math', 'time', 'random', 're', 'array', 'decimal', 'os', 'io',
    'base64', 'argparse', 'threading', 'json', 'functools', 'heapq',
    '_thread', 'pygame',
)

# 与外部对象（threading/lock/io/str/os/pygame 等）可能撞名的方法名一律不重命名
_METHOD_BLACKLIST = {
    'join', 'start', 'run', 'is_alive', 'acquire', 'release', 'wait',
    'notify', 'notify_all', 'set', 'get', 'items', 'keys', 'values',
    'append', 'insert', 'pop', 'remove', 'clear', 'index', 'count',
    'sort', 'reverse', 'extend', 'copy', 'update', 'split', 'rsplit',
    'strip', 'lstrip', 'rstrip', 'replace', 'encode', 'decode', 'read',
    'readline', 'readlines', 'write', 'writelines', 'close', 'seek',
    'tell', 'flush', 'fileno', 'readable', 'writable', 'seekable',
    'format', 'upper', 'lower', 'title', 'capitalize', 'casefold',
    'center', 'ljust', 'rjust', 'zfill', 'isdigit', 'isalpha',
    'isalnum', 'isspace', 'islower', 'isupper', 'istitle',
    'startswith', 'endswith', 'find', 'rfind', 'partition',
    'rpartition', 'splitlines', 'expandtabs', 'swapcase',
    'group', 'groups', 'groupdict', 'sub', 'subn', 'search', 'match',
    'fromkeys', 'popitem', 'setdefault', 'connect', 'send', 'recv',
    'bind', 'listen', 'accept', 'sleep', 'groupby', 'reduce',
    'cancel', 'result', 'exception', 'running', 'done',
    # pygame Rect / Surface / 显示与事件 API
    'move', 'move_ip', 'inflate', 'inflate_ip', 'clamp', 'clamp_ip',
    'clip', 'union', 'union_ip', 'unionall', 'unionall_ip', 'fit',
    'normalize', 'contains', 'collidepoint', 'colliderect',
    'collidelist', 'collidelistall', 'collidedict', 'collidedictall',
    'blit', 'fill', 'get_at', 'set_at', 'get_at_mapped', 'set_at_mapped',
    'get_palette', 'set_palette', 'set_palette_at', 'map_rgb', 'unmap_rgb',
    'set_colorkey', 'get_colorkey', 'set_alpha', 'get_alpha',
    'get_shifts', 'set_shifts', 'get_masks', 'set_masks', 'get_losses',
    'get_bounding_rect', 'get_flags', 'get_pitch', 'get_bitsize',
    'get_views', 'get_buffer', 'get_offset', 'get_parent', 'premul_alpha',
    'subsurface', 'convert', 'convert_alpha', 'get_size', 'get_width',
    'get_height', 'get_rect', 'get_frect', 'scroll',
    'set_mode', 'set_caption', 'get_caption', 'get_surface', 'flip',
    'set_icon', 'iconify', 'toggle_fullscreen', 'get_driver', 'info',
    'get_wm_info', 'set_gamma', 'set_gamma_ramp', 'set_allow_screen_saver',
    'get_allow_screen_saver', 'get_num_displays', 'get_window_size',
    'get_desktop_sizes', 'is_fullscreen', 'get_desktops',
    'poll', 'peek', 'post', 'pump', 'set_blocked', 'set_allowed',
    'get_blocked', 'set_grab', 'get_grab', 'set_text_input_rect',
    'start_text_input', 'stop_text_input', 'set_locale',
    'get_pressed', 'get_mods', 'set_mods', 'get_mods', 'get_focused',
    'set_visible', 'get_visible', 'get_rel', 'set_pos', 'set_cursor',
    'get_cursor', 'has_screen_keyboard_support',
    'delay', 'set_timer', 'get_ticks',
    'render', 'metrics', 'get_ascent', 'get_descent', 'get_linesize',
    'set_bold', 'get_bold', 'set_italic', 'get_italic', 'set_underline',
    'get_underline', 'set_point_size', 'get_point_size',
    'play', 'fadeout', 'get_volume', 'set_volume', 'get_busy',
    'get_length', 'get_raw', 'get_init', 'get_num_channels',
    'set_num_channels', 'set_reserved', 'find_channel', 'get_busy',
    'get_sdl_mixer_version', 'get_default_volume', 'set_check_volume',
    'music_load', 'playto',
    'smoothscale', 'scale', 'scale_by', 'rotate', 'rotozoom',
    'get_smoothscale_backend', 'set_smoothscale_backend',
    'get_extended', 'tobytes', 'frombytes', 'frombuffer',
    'aaline', 'aalines', 'arc', 'circle', 'ellipse', 'line', 'lines',
    'polygon', 'rect_draw',
    'tick', 'get_fps', 'get_rawtime', 'tick_busy_loop',
    'pause', 'unpause', 'music', 'Sound', 'init', 'quit', 'pre_init',
    'set_pos', 'get_pos', 'get_count', 'get_sdl_device_index',
}


@dataclass
class ObfResult:
    """混淆结果：stage1 AST、字符串表、函数簇、注入名"""
    tree: ast.Module
    main_name: str
    strtable_name: str
    str_entries: List[str] = field(default_factory=list)
    cluster_helper: str = ''
    clusters: List[str] = field(default_factory=list)  # index = cluster id


def _random_name(rng: random.Random, used: Set[str]) -> str:
    while True:
        name = f"_q{rng.randrange(16 ** 8):08x}"
        if name not in used:
            used.add(name)
            return name


def _n(name: str, ctx=ast.Load()) -> ast.Name:
    return ast.Name(id=name, ctx=ctx)


# ===================== 基础变换 =====================

def _remove_docstrings(tree: ast.Module) -> None:
    for node in ast.walk(tree):
        body = getattr(node, 'body', None)
        if not isinstance(body, list) or not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(
                first.value, ast.Constant) and isinstance(
                    first.value.value, str):
            body.pop(0)
            if not body:
                body.append(ast.Pass())


def _collect_function_bound_names(tree: ast.Module) -> Set[str]:
    bound = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.Lambda)):
            continue
        args = node.args
        for arg in (list(args.posonlyargs) + list(args.args)
                    + list(args.kwonlyargs)):
            bound.add(arg.arg)
        if args.vararg:
            bound.add(args.vararg.arg)
        if args.kwarg:
            bound.add(args.kwarg.arg)
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and isinstance(
                    sub.ctx, (ast.Store, ast.Del)):
                bound.add(sub.id)
    return bound


class _TopLevelRenamer(ast.NodeTransformer):
    def __init__(self, mapping: Dict[str, str], bound: Set[str]):
        self.mapping = mapping
        self.bound = bound

    def visit_Name(self, node: ast.Name):
        if node.id in self.mapping and node.id not in self.bound:
            node.id = self.mapping[node.id]
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if node.name in self.mapping:
            node.name = self.mapping[node.name]
        self.generic_visit(node)
        return node

    def visit_ClassDef(self, node: ast.ClassDef):
        if node.name in self.mapping:
            node.name = self.mapping[node.name]
        self.generic_visit(node)
        return node

    def visit_Global(self, node: ast.Global):
        node.names = [self.mapping.get(name, name) for name in node.names]
        return node

    def visit_Nonlocal(self, node: ast.Nonlocal):
        node.names = [self.mapping.get(name, name) for name in node.names]
        return node


def _rename_top_level(tree: ast.Module, rng: random.Random) -> Dict[str, str]:
    bound = _collect_function_bound_names(tree)
    names = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            if not node.name.startswith('__') and node.name not in bound:
                names.append(node.name)
    used: Set[str] = set()
    mapping = {name: _random_name(rng, used) for name in names}
    if mapping:
        _TopLevelRenamer(mapping, bound).visit(tree)
    return mapping


# ===================== import 隐藏 =====================

def _hide_imports(tree: ast.Module) -> None:
    """删除 import 语句（模块由 loader 注入），包括 pygame 的 try 块"""
    body = []
    for node in tree.body:
        if isinstance(node, ast.Import) and all(
                alias.name in LOADER_MODULES for alias in node.names):
            continue
        if isinstance(node, ast.ImportFrom) and node.module in LOADER_MODULES:
            continue
        if isinstance(node, ast.Try) and len(node.body) == 1 \
                and isinstance(node.body[0], ast.Import) \
                and node.body[0].names \
                and node.body[0].names[0].name == 'pygame' \
                and not node.orelse:
            # try: import pygame / except ImportError: pygame = None
            handlers_ok = all(
                len(handler.body) == 1
                and isinstance(handler.body[0], ast.Assign)
                and isinstance(handler.body[0].value, ast.Constant)
                for handler in node.handlers)
            if handlers_ok:
                continue
        body.append(node)
    tree.body = body


# ===================== 类方法重命名 =====================

def _collect_foreign_attr_names(tree: ast.Module) -> Set[str]:
    """收集以 import 绑定为根的属性名（os.path.join 等），禁止重命名"""
    foreign: Set[str] = set()
    roots = set(LOADER_MODULES) | {'super', 'object', 'type', 'self._runtime'}
    for node in ast.walk(tree):
        cur = node
        while isinstance(cur, ast.Attribute):
            if isinstance(cur.value, ast.Name) and cur.value.id in roots:
                foreign.add(cur.attr)
            cur = cur.value
    return foreign


def _rename_methods(tree: ast.Module, rng: random.Random,
                    used: Set[str], foreign_names: Optional[Set[str]] = None
                    ) -> Dict[str, str]:
    blacklist = set(_METHOD_BLACKLIST) | _collect_foreign_attr_names(tree)
    if foreign_names:
        blacklist |= set(foreign_names)
    mapping: Dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for child in node.body:
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            name = child.name
            if name.startswith('__') and name.endswith('__'):
                continue
            if name in blacklist or name in mapping:
                continue
            mapping[name] = _random_name(rng, used)
    if not mapping:
        return mapping

    def rename_class_local_names(cls) -> None:
        """同步类体中对类局部名字的直接引用（如 @_running.setter）。

        只遍历类体的直接子节点与非方法体部分，避免误改方法内的
        全局/参数同名名字。
        """

        def visit_shallow(node) -> None:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for decorator in child.decorator_list:
                        visit_shallow(decorator)
                    for default in list(child.args.defaults) + list(
                            child.args.kw_defaults):
                        if default is not None:
                            visit_shallow(default)
                    continue
                if isinstance(child, ast.Name) and isinstance(
                        child.ctx, ast.Load) and child.id in mapping:
                    child.id = mapping[child.id]
                    continue
                visit_shallow(child)

        visit_shallow(cls)

    class _M(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            self.generic_visit(node)
            if node.name in mapping:
                node.name = mapping[node.name]
            return node

        def visit_Attribute(self, node):
            self.generic_visit(node)
            if node.attr in mapping:
                node.attr = mapping[node.attr]
            return node

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            rename_class_local_names(node)
    _M().visit(tree)
    return mapping


# ===================== 属性派发表 =====================

class _DispatchLoadTransformer(ast.NodeTransformer):
    """Load 上下文的属性访问 -> getattr(obj, key)；跳过 dunder"""

    def visit_Attribute(self, node: ast.Attribute):
        self.generic_visit(node)
        if node.attr.startswith('__') and node.attr.endswith('__'):
            return node
        if isinstance(node.ctx, ast.Load):
            return ast.copy_location(ast.Call(
                func=_n('getattr'),
                args=[node.value, ast.Constant(value=node.attr)],
                keywords=[]), node)
        return node


def _rewrite_attr_statements(tree: ast.Module, rng: random.Random) -> None:
    """Assign/AugAssign/Delete 的属性目标 -> setattr/delattr 语句"""
    counter = [0]

    def tmp_name() -> str:
        counter[0] += 1
        return f"_w{counter[0]:x}{rng.randrange(16 ** 4):04x}"

    def call(func: str, args: list) -> ast.Expr:
        return ast.copy_location(ast.Expr(ast.Call(
            func=_n(func), args=args, keywords=[])), _placeholder[0])

    def emit_target(target, valnode, out):
        if isinstance(target, ast.Attribute):
            out.append(call('setattr', [
                target.value, ast.Constant(value=target.attr), valnode]))
        elif isinstance(target, ast.Name):
            out.append(ast.copy_location(ast.Assign(
                targets=[ast.Name(id=target.id, ctx=ast.Store())],
                value=valnode), _placeholder[0]))
        elif isinstance(target, (ast.Tuple, ast.List)):
            for i, elt in enumerate(target.elts):
                emit_target(elt, ast.Subscript(
                    value=valnode, slice=ast.Constant(value=i),
                    ctx=ast.Load()), out)
        # Starred/下标目标等保持原样（由调用方回退）

    def rewrite_stmt(stmt):
        _placeholder[0] = stmt
        if isinstance(stmt, ast.Assign):
            attrs = any(_has_attr_target(t) for t in stmt.targets)
            if not attrs:
                return [stmt]
            if len(stmt.targets) == 1 and isinstance(
                    stmt.targets[0], ast.Attribute):
                target = stmt.targets[0]
                return [call('setattr', [
                    target.value, ast.Constant(value=target.attr),
                    stmt.value])]
            # 复杂目标：先存临时变量再逐个赋值，保证 value 只求值一次；
            # 仅当 value 是等长的元组字面量时才按下标分解，否则保持原样
            if not isinstance(stmt.value, ast.Tuple) or len(
                    stmt.value.elts) != _target_arity(stmt.targets[0]):
                return [stmt]
            tmp = tmp_name()
            out = [ast.copy_location(ast.Assign(
                targets=[_n(tmp, ast.Store())], value=stmt.value), stmt)]
            for target in stmt.targets:
                emit_target(
                    target, ast.copy_location(_n(tmp), stmt), out)
            return out
        if isinstance(stmt, ast.AugAssign) and isinstance(
                stmt.target, ast.Attribute):
            target = stmt.target
            current = ast.Call(func=_n('getattr'), args=[
                copy.deepcopy(target.value),
                ast.Constant(value=target.attr)], keywords=[])
            value = ast.BinOp(left=current, op=stmt.op, right=stmt.value)
            return [call('setattr', [
                copy.deepcopy(target.value),
                ast.Constant(value=target.attr), value])]
        if isinstance(stmt, ast.Delete) and any(
                isinstance(t, ast.Attribute) for t in stmt.targets):
            out = []
            for target in stmt.targets:
                if isinstance(target, ast.Attribute):
                    out.append(call('delattr', [
                        target.value, ast.Constant(value=target.attr)]))
                else:
                    out.append(ast.Delete(targets=[target]))
            return out
        return [stmt]

    _placeholder = [None]
    for holder in list(ast.walk(tree)):
        for fld in ('body', 'orelse', 'finalbody'):
            lst = getattr(holder, fld, None)
            if not isinstance(lst, list) or not lst or not isinstance(
                    lst[0], ast.stmt):
                continue
            new: List[ast.stmt] = []
            for stmt in lst:
                new.extend(rewrite_stmt(stmt))
            setattr(holder, fld, new)


def _has_attr_target(node) -> bool:
    if isinstance(node, ast.Attribute):
        return True
    if isinstance(node, (ast.Tuple, ast.List)):
        return any(_has_attr_target(elt) for elt in node.elts)
    return False


def _target_arity(node) -> int:
    if isinstance(node, (ast.Tuple, ast.List)):
        return len(node.elts)
    return 1


# ===================== 链式字符串表 =====================

class _StringTable:
    def __init__(self):
        self.entries: List[str] = []
        self.index: Dict[str, int] = {}

    def idx(self, value: str) -> int:
        if value not in self.index:
            self.index[value] = len(self.entries)
            self.entries.append(value)
        return self.index[value]


class _StrEncodeTransformer(ast.NodeTransformer):
    def __init__(self, table: _StringTable, table_name: str):
        self.table = table
        self.table_name = table_name

    def visit_Constant(self, node: ast.Constant):
        if not isinstance(node.value, str):
            return node
        if node.value == '__main__':
            return node
        index = self.table.idx(node.value)
        return ast.copy_location(ast.Subscript(
            value=_n(self.table_name),
            slice=ast.Constant(value=index),
            ctx=ast.Load()), node)

    def visit_JoinedStr(self, node: ast.JoinedStr):
        # f-string 字面量部分不能替换成下标（unparse 不支持），
        # 只编码插值表达式内部的字符串常量；format_spec 保持原样
        for value in node.values:
            if isinstance(value, ast.FormattedValue):
                self.visit(value.value)
        return node


def _encode_strings(tree: ast.Module, table: _StringTable,
                    table_name: str) -> None:
    _StrEncodeTransformer(table, table_name).visit(tree)


# ===================== 垃圾代码 =====================

def _inject_junk(tree: ast.Module, rng: random.Random, used: Set[str]) -> None:
    names = [_random_name(rng, used) for _ in range(3)]
    source = (
        f"def {names[0]}(a, b):\n"
        f"    if a == 0x{rng.randrange(0x10000, 0xFFFFF):X}:\n"
        f"        return b * 0x{rng.randrange(0x1000, 0xFFFF):X}\n"
        f"    return a ^ b\n"
        f"def {names[1]}(a, b):\n"
        f"    c = a + b\n"
        f"    return (c << 1) ^ (a - b)\n"
        f"def {names[2]}(a):\n"
        f"    return ((a * 0x{rng.randrange(0x100, 0xFFFF):X}) "
        f"+ 0x{rng.randrange(0x100, 0xFFFF):X}) & 0xFFFFFFFF\n"
        f"if {names[0]}({rng.randrange(1, 100)}, "
        f"{rng.randrange(1, 100)}) == 0x7FFFFFFF:\n"
        f"    {names[1]}({rng.randrange(1, 100)}, "
        f"{rng.randrange(1, 100)})\n"
    )
    tree.body[0:0] = ast.parse(source).body


# ===================== 函数簇拆分 =====================

def _split_clusters(tree: ast.Module, rng: random.Random,
                    helper: str, max_size: int = 6
                    ) -> List[str]:
    """把顶层 def 替换为懒加载 trampoline，返回各簇源码（index=cid）"""
    clusters: List[str] = []
    body = tree.body
    i = 0
    cid = 0
    while i < len(body):
        node = body[i]
        if not isinstance(node, ast.FunctionDef) or node.decorator_list:
            i += 1
            continue
        group = [node]
        j = i + 1
        while (j < len(body) and len(group) < max_size
               and isinstance(body[j], ast.FunctionDef)
               and not body[j].decorator_list):
            group.append(body[j])
            j += 1

        sources = [ast.unparse(func) for func in group]
        for func in group:
            tramp = ast.parse(
                f"def {func.name}(*_a, **_k):\n"
                f"    {helper}({cid}, globals())\n"
                f"    return {func.name}(*_a, **_k)\n").body[0]
            tramp.decorator_list = copy.deepcopy(func.decorator_list)
            ast.copy_location(tramp, func)
            body[body.index(func)] = tramp
        clusters.append("\n\n".join(sources))
        cid += 1
        i = j
    return clusters


# ===================== 位置抹平 =====================

def _flatten_locations(tree: ast.Module) -> None:
    for node in ast.walk(tree):
        if hasattr(node, 'lineno'):
            node.lineno = 1
        if hasattr(node, 'col_offset'):
            node.col_offset = 0
        if hasattr(node, 'end_lineno'):
            node.end_lineno = 1
        if hasattr(node, 'end_col_offset'):
            node.end_col_offset = 0


# ===================== 入口 =====================

def obfuscate_module(tree: ast.Module,
                     seed: Optional[int] = None,
                     foreign_names: Optional[Set[str]] = None) -> ObfResult:
    rng = random.Random(seed)
    tree = ast.fix_missing_locations(tree)
    _remove_docstrings(tree)
    _hide_imports(tree)

    mapping = _rename_top_level(tree, rng)
    used = set(mapping.values())
    _rename_methods(tree, rng, used, foreign_names)
    _inject_junk(tree, rng, used)

    strtable_name = _random_name(rng, used)
    cluster_helper = _random_name(rng, used)

    _DispatchLoadTransformer().visit(tree)
    ast.fix_missing_locations(tree)
    _rewrite_attr_statements(tree, rng)
    ast.fix_missing_locations(tree)

    table = _StringTable()
    _encode_strings(tree, table, strtable_name)

    clusters = _split_clusters(tree, rng, cluster_helper)

    _flatten_locations(tree)
    tree = ast.fix_missing_locations(tree)
    return ObfResult(
        tree=tree,
        main_name=mapping.get('main', 'main'),
        strtable_name=strtable_name,
        str_entries=table.entries,
        cluster_helper=cluster_helper,
        clusters=clusters,
    )
