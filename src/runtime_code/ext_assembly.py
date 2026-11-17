# -*- coding: utf-8 -*-
"""运行时扩展按需拼装

extensions.py 里保存了完整扩展源码（字符串模板）。生成脚本时只把项目
实际用到的扩展及其依赖函数拼进去，避免每个作品都携带全部扩展定义。

实现方式：把模板当作 Python 源码解析成顶层定义，从用到的扩展处理器出发
做名称可达性分析，再按原始顺序拼回源码。
"""

import ast

from .extensions import (
    EXTENSIONS,
    HANDLER_GROUPS,
    CORE_ROOTS,
    EXTRA_ROOTS,
)


# 扩展 ID 的可接受写法（小写） -> 规范 ID
_ALIASES = {}
for _canonical, (_handler, _names) in HANDLER_GROUPS.items():
    _ALIASES[_canonical] = _canonical
    for _name in _names:
        _ALIASES[_name.lower()] = _canonical


class _Segment:
    __slots__ = ('name', 'start', 'end', 'node')

    def __init__(self, name, start, end, node):
        self.name = name
        self.start = start
        self.end = end
        self.node = node


def _parse_segments(source):
    """把源码拆成顶层定义片段（函数/类/赋值）"""
    tree = ast.parse(source)
    lines = source.splitlines()
    segments = []
    for node in tree.body:
        name = None
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = node.name
        elif isinstance(node, ast.Assign):
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name = node.target.id
        if not name:
            continue
        start = node.lineno
        for decorator in getattr(node, 'decorator_list', []):
            start = min(start, decorator.lineno)
        end = getattr(node, 'end_lineno', None)
        if end is None:
            continue
        segments.append(_Segment(name, start - 1, end, node))
    return segments, lines


def _referenced_names(node):
    names = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
    return names


def assemble_extensions(used_ids, extra_roots=()):
    """返回 (扩展源码, {注册名: 处理器函数名}, 实际包含的函数名集合)

    无法识别或模板解析失败时退回完整扩展源码，保证生成结果始终可用。
    """
    used = {str(item).lower() for item in (used_ids or ()) if item}
    groups = sorted({_ALIASES[name] for name in used if name in _ALIASES})
    registrations = {}
    for canonical in groups:
        handler, names = HANDLER_GROUPS[canonical]
        for name in names:
            registrations[name] = handler

    roots = set(CORE_ROOTS)
    roots.update(extra_roots)
    for canonical in groups:
        roots.add(HANDLER_GROUPS[canonical][0])
    for canonical, names in EXTRA_ROOTS.items():
        if canonical in groups:
            roots.update(names)

    source = EXTENSIONS.strip('\n')
    try:
        segments, lines = _parse_segments(source)
    except SyntaxError:
        return source, registrations, set()

    by_name = {segment.name: segment for segment in segments}
    included = set()
    pending = [name for name in roots if name in by_name]
    while pending:
        name = pending.pop()
        if name in included:
            continue
        segment = by_name[name]
        included.add(name)
        for reference in _referenced_names(segment.node):
            if reference in by_name and reference not in included:
                pending.append(reference)

    if not included:
        return '', registrations, set()

    chunks = []
    for segment in segments:
        if segment.name in included:
            chunks.append('\n'.join(lines[segment.start:segment.end]))
    return '\n\n\n'.join(chunks), registrations, included


def extension_registrations_source(registrations):
    """生成 `_BUILTIN_EXTENSIONS = {...}` 常量源码"""
    if not registrations:
        return '_BUILTIN_EXTENSIONS = {}'
    items = ', '.join('%r: %s' % (name, handler)
                      for name, handler in sorted(registrations.items()))
    return '_BUILTIN_EXTENSIONS = {%s}' % items
