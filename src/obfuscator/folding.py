# -*- coding: utf-8 -*-
"""IR 常量折叠与恒定条件简化。

在生成 Python 之前运行：

- 纯常量表达式直接算出结果（例如 ``_sc_add(1, 2)`` -> ``3``）；
- 把恒定条件的分支/空循环删掉（例如 ``if True:`` 只保留分支体）。

折叠使用运行时模板里的 ``_sc_*`` 函数，保证与 Scratch 的类型转换、比较、
字符串与列表语义一致。
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional

from ir import BlockType, Expr, ExprType, ProjectIR, Statement
from runtime_code.helpers import HELPERS


def _build_helpers() -> Dict[str, Any]:
    """执行运行时 helpers，得到 _sc_* 函数集合"""
    namespace: Dict[str, Any] = {}
    import array
    import base64
    import decimal
    import functools
    import heapq
    import io
    import json
    import os
    import random
    import re
    import threading
    import time
    namespace.update({
        'math': math, 'time': time, 'random': random, 're': re,
        'array': array, 'decimal': decimal, 'os': os, 'io': io,
        'base64': base64, 'threading': threading, 'json': json,
        'functools': functools, 'heapq': heapq, 'pygame': None,
        '_thread': __import__('_thread'),
    })
    exec(HELPERS, namespace)
    return namespace


_HELPERS = _build_helpers()

_BINARY_HELPERS = {
    '+': '_sc_add', '-': '_sc_sub', '*': '_sc_mul', '/': '_sc_div',
}

_MATH_TYPES = {
    ExprType.ABS: 'abs', ExprType.FLOOR: 'floor',
    ExprType.CEILING: 'ceiling', ExprType.SQRT: 'sqrt',
    ExprType.SIN: 'sin', ExprType.COS: 'cos', ExprType.TAN: 'tan',
    ExprType.ASIN: 'asin', ExprType.ACOS: 'acos', ExprType.ATAN: 'atan',
    ExprType.LN: 'ln', ExprType.LOG: 'log',
    ExprType.EXP: 'e^', ExprType.POW10: '10^',
}

_MAX_STRING = 200000


def _const(expr: Optional[Expr]):
    if expr is None:
        return False, None
    if expr.type == ExprType.NUMBER:
        return True, expr.value
    if expr.type == ExprType.STRING:
        return True, expr.value
    if expr.type == ExprType.BOOLEAN:
        return True, bool(expr.value)
    return False, None


def _make_const(value: Any) -> Optional[Expr]:
    if isinstance(value, bool):
        return Expr(ExprType.BOOLEAN, value=value)
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (
                math.isnan(value) or math.isinf(value)):
            return None
        return Expr(ExprType.NUMBER, value=value)
    if isinstance(value, str):
        if len(value) > _MAX_STRING:
            return None
        return Expr(ExprType.STRING, value=value)
    return None


def fold_expression(expr: Optional[Expr]) -> Optional[Expr]:
    """递归折叠表达式；返回可能被替换后的表达式"""
    if expr is None:
        return None

    expr.left = fold_expression(expr.left)
    expr.right = fold_expression(expr.right)
    expr.children = [fold_expression(child) for child in expr.children]
    expr.args = [fold_expression(arg) for arg in expr.args]
    for key, value in list((expr.extra or {}).items()):
        expr.extra[key] = _fold_container(value)

    left_ok, left = _const(expr.left)
    right_ok, right = _const(expr.right)
    both = left_ok and right_ok

    try:
        if expr.type == ExprType.BINARY_OP and both:
            helper = _BINARY_HELPERS.get(expr.name)
            if helper:
                return _make_const(_HELPERS[helper](left, right)) or expr
        elif expr.type == ExprType.EQUAL and both:
            return _make_const(_HELPERS['_sc_eq'](left, right)) or expr
        elif expr.type == ExprType.LESS_THAN and both:
            return _make_const(_HELPERS['_sc_lt'](left, right)) or expr
        elif expr.type == ExprType.GREATER_THAN and both:
            return _make_const(_HELPERS['_sc_gt'](left, right)) or expr
        elif expr.type == ExprType.AND and both:
            return _make_const(_HELPERS['_sc_and'](left, right)) or expr
        elif expr.type == ExprType.OR and both:
            return _make_const(_HELPERS['_sc_or'](left, right)) or expr
        elif expr.type == ExprType.NOT and right_ok:
            return _make_const(_HELPERS['_sc_not'](right)) or expr
        elif expr.type == ExprType.JOIN and both:
            return _make_const(_HELPERS['_sc_join'](left, right)) or expr
        elif expr.type == ExprType.LETTER_OF and both:
            return _make_const(
                _HELPERS['_sc_letter_of'](left, right)) or expr
        elif expr.type == ExprType.LENGTH_OF_STRING and right_ok:
            return _make_const(_HELPERS['_sc_length'](right)) or expr
        elif expr.type == ExprType.CONTAINS_STRING and both:
            return _make_const(
                _HELPERS['_sc_contains'](left, right)) or expr
        elif expr.type == ExprType.MOD and both:
            return _make_const(_HELPERS['_sc_mod'](left, right)) or expr
        elif expr.type == ExprType.ROUND and right_ok:
            return _make_const(_HELPERS['_sc_round'](right)) or expr
        elif expr.type in _MATH_TYPES and right_ok:
            operator = _MATH_TYPES[expr.type]
            return _make_const(
                _HELPERS['_sc_mathop'](operator, right)) or expr
        elif expr.type == ExprType.MATH_OP and right_ok:
            operator = str(expr.name or '').lower().replace(' ', '')
            return _make_const(
                _HELPERS['_sc_mathop'](operator, right)) or expr
    except Exception:
        return expr
    return expr


def _fold_container(value: Any) -> Any:
    if isinstance(value, Expr):
        return fold_expression(value)
    if isinstance(value, dict):
        return {key: _fold_container(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_fold_container(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_fold_container(item) for item in value)
    return value


def _fold_statement_exprs(stmt: Statement) -> None:
    stmt.value = fold_expression(stmt.value)
    stmt.condition = fold_expression(stmt.condition)
    stmt.target = fold_expression(stmt.target)
    stmt.expr = fold_expression(stmt.expr)
    stmt.extra = _fold_container(stmt.extra or {})


def _flatten(statements) -> list:
    result = []
    for stmt in statements:
        current = stmt
        while current is not None:
            nxt = current.next
            result.append(current)
            current = nxt
    return result


def _chain(statements, tail: Optional[Statement]) -> Optional[Statement]:
    result = tail
    for stmt in reversed(statements):
        stmt.next = result
        result = stmt
    return result


def simplify_chain(stmt: Optional[Statement],
                   seen: set) -> Optional[Statement]:
    """递归简化语句链，返回新的链头"""
    if stmt is None or id(stmt) in seen:
        return stmt
    seen.add(id(stmt))
    _fold_statement_exprs(stmt)
    stmt.body = simplify_list(stmt.body, seen)
    stmt.else_body = simplify_list(stmt.else_body, seen)
    stmt.next = simplify_chain(stmt.next, seen)

    if stmt.type in (BlockType.IF, BlockType.IF_ELSE):
        ok, value = _const(stmt.condition)
        if ok:
            chosen = stmt.body if bool(value) else stmt.else_body
            return _chain(_flatten(chosen), stmt.next)
    if stmt.type in (BlockType.WAIT_UNTIL, BlockType.REPEAT_UNTIL):
        ok, value = _const(stmt.condition)
        if ok and bool(value):
            return stmt.next
    if stmt.type == BlockType.REPEAT:
        ok, value = _const(stmt.value)
        if ok:
            try:
                if float(value) <= 0:
                    return stmt.next
            except (TypeError, ValueError):
                pass
    return stmt


def simplify_list(statements, seen: set) -> list:
    result = []
    for stmt in statements or ():
        simplified = simplify_chain(stmt, seen)
        if simplified is not None:
            result.append(simplified)
    return result


def fold_project(project: ProjectIR) -> ProjectIR:
    """原地折叠整个项目，返回同一 ProjectIR"""
    for sprite in project.sprites:
        for stmt in sprite.statements:
            simplify_chain(stmt, set())
    return project
