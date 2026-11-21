# -*- coding: utf-8 -*-
"""ScPython 工程的静态检查（未使用声明、未调用积木/宏）。

只报告“确定无害”的提示，不改变编译结果：

- ``W001`` 变量声明后从未读取
- ``W002`` 列表声明后从未使用
- ``W003`` 自制积木定义后从未调用
- ``W004`` macros.scpy 中的宏从未被任何角色使用
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from .compiler import ModuleAnalyzer, ProjectCompiler, analyze_macros
from .errors import ScPythonError

_LIST_FUNCTIONS = {
    'add_to_list', 'delete_of_list', 'delete_item', 'delete_all_of_list',
    'insert_in_list', 'replace_in_list', 'item_of', 'item_number_of',
    'length_of', 'contains_item', 'list_contents',
}
_LIST_METHODS = {'append', 'insert', 'clear', 'index'}


@dataclass
class LintIssue:
    path: str
    line: Optional[int]
    code: str
    message: str

    def __str__(self) -> str:
        location = self.path
        if self.line:
            location += f":{self.line}"
        return f"{location}: [{self.code}] {self.message}"


@dataclass
class _Usage:
    variables: Set[str]
    lists: Set[str]
    calls: Set[str]


def _scan_usage(tree: ast.Module) -> _Usage:
    variables: Set[str] = set()
    lists: Set[str] = set()
    calls: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Load):
                variables.add(node.id)
        elif isinstance(node, ast.Subscript):
            if isinstance(node.value, ast.Name):
                lists.add(node.value.id)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                calls.add(func.id)
                if func.id in _LIST_FUNCTIONS and node.args \
                        and isinstance(node.args[0], ast.Name):
                    lists.add(node.args[0].id)
            elif isinstance(func, ast.Attribute) \
                    and isinstance(func.value, ast.Name):
                if func.attr in _LIST_METHODS:
                    lists.add(func.value.id)
    return _Usage(variables, lists, calls)


def _declaration_lines(tree: ast.Module) -> Dict[str, int]:
    """名称 -> 首次声明行号（var/list/普通赋值）"""
    lines: Dict[str, int] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                lines.setdefault(target.id, node.lineno)
            elif isinstance(target, ast.Subscript) \
                    and isinstance(target.value, ast.Name):
                lines.setdefault(target.value.id, node.lineno)
    return lines


def lint_project(folder: str) -> List[LintIssue]:
    """检查工程，返回所有提示（按文件/行排序）"""
    folder = os.path.abspath(folder)
    if not os.path.isdir(folder):
        raise ScPythonError(f"工程目录不存在: {folder}", path=folder)
    compiler = ProjectCompiler(folder)
    stage_path = compiler.find_stage()
    macros_path = compiler.find_macros()
    macros = analyze_macros(macros_path) if macros_path else {}

    modules = [ModuleAnalyzer(stage_path, 'stage.scpy', True).analyze()]
    for path, name in compiler.find_roles(stage_path):
        module = ModuleAnalyzer(path, os.path.relpath(path, folder),
                                False).analyze()
        module.name = name
        modules.append(module)

    issues: List[LintIssue] = []
    role_calls: Set[str] = set()
    scanned = []
    all_vars: Set[str] = set()
    all_lists: Set[str] = set()
    for module in modules:
        usage = _scan_usage(module.tree)
        role_calls |= usage.calls
        all_vars |= usage.variables
        all_lists |= usage.lists
        scanned.append((module, usage, _declaration_lines(module.tree)))

    for module, usage, lines in scanned:
        # 舞台变量是全局的，任何角色引用都算使用
        used_vars = all_vars if module.is_stage else usage.variables
        used_lists = all_lists if module.is_stage else usage.lists

        for name in sorted(module.explicit_vars):
            if name.startswith('__'):
                continue
            if name not in used_vars:
                issues.append(LintIssue(
                    module.path, lines.get(name), 'W001',
                    f"变量 {name!r} 声明后从未读取"))
        for name in sorted(module.explicit_lists):
            if name not in used_lists:
                issues.append(LintIssue(
                    module.path, lines.get(name), 'W002',
                    f"列表 {name!r} 声明后从未使用"))

        for info in module.functions.values():
            if info.name not in usage.calls:
                issues.append(LintIssue(
                    module.path, info.node.lineno, 'W003',
                    f"自制积木 {info.name!r} 定义后从未调用"))

    used_macros: Set[str] = set()
    pending = [name for name in role_calls if name in macros]
    while pending:
        name = pending.pop()
        if name in used_macros:
            continue
        used_macros.add(name)
        info = macros[name]
        usage = _scan_usage(ast.Module(body=[info.node], type_ignores=[]))
        pending.extend(call for call in usage.calls if call in macros)

    for name in sorted(macros):
        if name not in used_macros:
            info = macros[name]
            issues.append(LintIssue(
                macros_path, info.node.lineno, 'W004',
                f"宏 {name!r} 从未被任何角色使用"))

    issues.sort(key=lambda item: (item.path, item.line or 0, item.code))
    return issues
