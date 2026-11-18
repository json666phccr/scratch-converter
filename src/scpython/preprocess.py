# -*- coding: utf-8 -*-
"""把 ScPython 的扩展语法预处理成合法 Python。

ScPython 保留 Python 的函数/控制流语法，但增加三类关键字：

- ``when <事件>:``  事件帽子
- ``init:``         角色初始化/元数据
- ``var x = 0`` / ``list xs = []``  变量/列表声明

预处理只改写这些行，行号保持不变，方便错误定位。
"""

from __future__ import annotations

import ast
import re
from typing import List, Tuple

from .errors import ScPythonSyntaxError

_WHEN_RE = re.compile(r'^(\s*)when\s+(.+):\s*(#.*)?$')
_INIT_RE = re.compile(r'^(\s*)init\s*:\s*(#.*)?$')
_VAR_RE = re.compile(r'^(\s*)var\s+([^\s=#]+)\s*(?:=\s*(.*))?$')
_LIST_RE = re.compile(r'^(\s*)list\s+([^\s=#]+)\s*(?:=\s*(.*))?$')

_HAT_NAMES = {
    'green_flag', 'greenflag', 'clicked', 'stage_clicked',
    'this_sprite_clicked', 'clone_start', 'key_pressed', 'broadcast',
    'backdrop_switches_to', 'timer', 'loudness', 'extension',
}


def _split_comment(text: str) -> Tuple[str, str]:
    """按引号状态拆出代码与行尾注释"""
    quote = None
    escaped = False
    for index, char in enumerate(text):
        if quote:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == quote:
                quote = None
        elif char in ("'", '"'):
            quote = char
        elif char == '#':
            return text[:index], text[index:]
    return text, ''


def _header_call(header: str) -> str:
    """把 ``when`` 后面的头表达式转成 __hat__(...) 调用"""
    text = header.strip()
    try:
        node = ast.parse(text, mode='eval').body
    except SyntaxError as error:
        raise ScPythonSyntaxError(
            f"无法解析 when 头表达式: {text!r}（{error.msg}）") from error

    if isinstance(node, ast.Name):
        if node.id not in _HAT_NAMES:
            raise ScPythonSyntaxError(f"未知事件头: {node.id}")
        return f"__hat__({node.id!r})"

    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            name = node.func.id
            if name not in _HAT_NAMES:
                raise ScPythonSyntaxError(f"未知事件头: {name}")
        elif isinstance(node.func, ast.Attribute):
            name = ast.unparse(node.func)  # 扩展帽子: myext.event
        else:
            raise ScPythonSyntaxError("when 头必须是事件名或事件调用")
        parts = [repr(name)]
        parts.extend(ast.unparse(arg) for arg in node.args)
        for keyword in node.keywords:
            if keyword.arg is None:
                raise ScPythonSyntaxError("when 头不支持 **kwargs")
            parts.append(f"{keyword.arg}={ast.unparse(keyword.value)}")
        return f"__hat__({', '.join(parts)})"

    if isinstance(node, ast.Compare):
        if not isinstance(node.left, ast.Name) or len(node.ops) != 1:
            raise ScPythonSyntaxError(
                "when 比较头只支持 timer/loudness 单次比较")
        if node.left.id not in ('timer', 'loudness'):
            raise ScPythonSyntaxError(
                f"when 比较头只支持 timer/loudness，收到 {node.left.id}")
        operator = {
            ast.Gt: '>', ast.GtE: '>=', ast.Lt: '<', ast.LtE: '<='
        }.get(type(node.ops[0]))
        if operator is None:
            raise ScPythonSyntaxError("when 比较头只支持 > >= < <=")
        right = ast.unparse(node.comparators[0])
        return f"__hat__({node.left.id!r}, {operator!r}, {right})"

    raise ScPythonSyntaxError(f"无法识别的 when 头: {text}")


def preprocess(code: str) -> str:
    """返回等行数的合法 Python 代码"""
    lines = code.splitlines()
    output: List[str] = []
    for lineno, line in enumerate(lines, 1):
        when_match = _WHEN_RE.match(line)
        if when_match:
            indent, header, comment = when_match.groups()
            call = _header_call(header)
            output.append(
                f"{indent}with {call}:"
                + (f"  {comment}" if comment else ""))
            continue

        init_match = _INIT_RE.match(line)
        if init_match:
            indent, comment = init_match.groups()
            output.append(
                f"{indent}with __sprite_init__():"
                + (f"  {comment}" if comment else ""))
            continue

        var_match = _VAR_RE.match(line)
        if var_match:
            indent, name, value = var_match.groups()
            code_part, comment = _split_comment(value or '0')
            value = code_part.strip() or '0'
            output.append(
                f"{indent}{name} = __var__({value})"
                + (f"  {comment}" if comment else ""))
            continue

        list_match = _LIST_RE.match(line)
        if list_match:
            indent, name, value = list_match.groups()
            code_part, comment = _split_comment(value or '[]')
            value = code_part.strip() or '[]'
            output.append(
                f"{indent}{name} = __list__({value})"
                + (f"  {comment}" if comment else ""))
            continue

        output.append(line)
    return "\n".join(output)
