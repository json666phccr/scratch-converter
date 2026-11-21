# -*- coding: utf-8 -*-
"""把 .sb3 / project.json 转换为 ScPython 工程目录。

目标不是逐字节还原 Scratch 工程，而是生成可编辑、可再导出的
``stage.scpy + <角色>.scpy + macros.scpy + assets/``：

- 事件帽子 -> ``when ...:``
- 变量/列表 -> ``init:`` 中的 ``var`` / ``list``
- 自制积木 -> ``def ...(*, types=..., warp=..., label=...)``
- Scratch 注释 -> ``# ...``（附着块放在语句前，独立注释放在文件头）
- 多个角色中**完全相同**的自制积木默认抽到 ``macros.scpy``
"""

from __future__ import annotations

import json
import os
import re
import zipfile
from collections import Counter
from typing import Dict, List, Optional, Tuple

from ir import (BlockType, Expr, ExprType, ProjectIR, Statement, sanitize_name)
from scratch_parser import parse_scratch_project

from .errors import ScPythonError

_EVENT_TYPES = {
    BlockType.WHEN_FLAG_CLICKED, BlockType.WHEN_KEY_PRESSED,
    BlockType.WHEN_THIS_SPRITE_CLICKED, BlockType.WHEN_BROADCAST_RECEIVED,
    BlockType.WHEN_BACKDROP_SWITCHES, BlockType.WHEN_GREATER_THAN,
    BlockType.WHEN_LOUDNESS, BlockType.WHEN_TIMER,
    BlockType.START_AS_CLONE, BlockType.EXTENSION_HAT,
}


def _q(value: str) -> str:
    return repr(value)


def _chain(stmt: Optional[Statement]) -> List[Statement]:
    """把 parser 的 next 链展开成语句列表"""
    items: List[Statement] = []
    while stmt is not None:
        items.append(stmt)
        stmt = stmt.next
    return items


def _san(text: str, prefix: str) -> str:
    return sanitize_name(str(text), prefix) or prefix


# ===================== 表达式 =====================

def expr_source(expr: Optional[Expr],
                warnings: Optional[List[str]] = None) -> str:
    if expr is None:
        return '0'
    t = expr.type
    if t in (ExprType.NUMBER, ExprType.STRING, ExprType.BOOLEAN):
        return expr.to_python_source()
    if t == ExprType.VARIABLE:
        return _san(expr.name, 'var')
    if t == ExprType.ARGUMENT:
        return _san(expr.name, 'arg')
    if t == ExprType.BINARY_OP:
        return f"({expr_source(expr.left)} {expr.name} " \
               f"{expr_source(expr.right)})"
    if t == ExprType.UNARY_OP:
        return f"({expr.name}{expr_source(expr.right)})"
    if t == ExprType.NOT:
        return f"(not {expr_source(expr.right)})"
    if t == ExprType.AND:
        return f"({expr_source(expr.left)} and {expr_source(expr.right)})"
    if t == ExprType.OR:
        return f"({expr_source(expr.left)} or {expr_source(expr.right)})"
    if t == ExprType.MOD:
        return f"({expr_source(expr.left)} % {expr_source(expr.right)})"
    if t in (ExprType.EQUAL, ExprType.LESS_THAN, ExprType.GREATER_THAN):
        op = {ExprType.EQUAL: '==', ExprType.LESS_THAN: '<',
              ExprType.GREATER_THAN: '>'}[t]
        return f"({expr_source(expr.left)} {op} {expr_source(expr.right)})"
    if t == ExprType.ITEM_OF_LIST:
        index = expr_source(expr.left) if expr.left is not None else '1'
        return f"item_of({_san(expr.name, 'lst')}, {index})"
    if t == ExprType.ITEM_NUMBER_OF_LIST:
        item = expr_source(expr.left) if expr.left is not None else "''"
        return f"item_number_of({_san(expr.name, 'lst')}, {item})"
    if t == ExprType.LENGTH_OF_LIST:
        return f"length_of({_san(expr.name, 'lst')})"
    if t == ExprType.LIST_ACCESS:
        return f"list_contents({_san(expr.name, 'lst')})"
    if t == ExprType.LIST_CONTAINS:
        item = expr_source(expr.left) if expr.left is not None else "''"
        return f"contains_item({_san(expr.name, 'lst')}, {item})"
    if t == ExprType.RANDOM:
        return f"random.randint({expr_source(expr.left)}, " \
               f"{expr_source(expr.right)})"
    if t == ExprType.JOIN:
        return f"join({expr_source(expr.left)}, {expr_source(expr.right)})"
    if t == ExprType.LETTER_OF:
        return f"letter_of({expr_source(expr.left)}, " \
               f"{expr_source(expr.right)})"
    if t == ExprType.LENGTH_OF_STRING:
        return f"len({expr_source(expr.right)})"
    if t == ExprType.CONTAINS_STRING:
        return f"contains({expr_source(expr.left)}, " \
               f"{expr_source(expr.right)})"
    if t == ExprType.PROCEDURE_CALL:
        args = ', '.join(expr_source(a) for a in expr.args)
        return f"{_san(expr.name, 'proc')}({args})"
    if t == ExprType.FUNCTION_CALL:
        args = ', '.join(expr_source(a) for a in expr.args)
        return f"{_san(expr.name, 'fn')}({args})"
    if t == ExprType.EXTENSION_CALL:
        namespace = str(expr.extra.get('namespace', ''))
        opcode = str(expr.extra.get('opcode', ''))
        parts = [_q(namespace), _q(opcode)]
        for slot, value in expr.extra.get('inputs', []):
            if re.match(r'^[A-Za-z_]\w*$', str(slot)):
                parts.append(f"{slot}={expr_source(value)}")
        fields = expr.extra.get('fields') or {}
        if fields and warnings is not None:
            warnings.append(
                f"扩展 {opcode} 的字段 {sorted(fields)} 未转换")
        return f"ext({', '.join(parts)})"
    if t == ExprType.PROPERTY:
        prop = expr.name
        mapping = {
            'x position': 'x_position', 'y position': 'y_position',
            'direction': 'direction_of_sprite', 'costume #': 'costume_number',
            'costume name': 'costume_name', 'backdrop #': 'backdrop_number',
            'backdrop name': 'backdrop_name', 'size': 'size_of_sprite',
            'volume': 'volume',
        }
        if prop in mapping:
            return f"{mapping[prop]}()"
        return f"{_san(prop, 'fn')}()"
    math_names = {
        ExprType.ROUND: 'round', ExprType.ABS: 'abs',
        ExprType.FLOOR: 'floor', ExprType.CEILING: 'ceiling',
        ExprType.SQRT: 'sqrt', ExprType.SIN: 'sin', ExprType.COS: 'cos',
        ExprType.TAN: 'tan', ExprType.ASIN: 'asin', ExprType.ACOS: 'acos',
        ExprType.ATAN: 'atan', ExprType.LN: 'ln', ExprType.LOG: 'log',
        ExprType.EXP: 'exp', ExprType.POW10: 'pow10',
    }
    if t in math_names:
        arg = expr.right if expr.right is not None else expr.left
        return f"{math_names[t]}({expr_source(arg)})"
    sensing = {
        ExprType.ANSWER: 'answer', ExprType.TIMER: 'timer',
        ExprType.LOUDNESS: 'loudness', ExprType.MOUSE_X: 'mouse_x',
        ExprType.MOUSE_Y: 'mouse_y', ExprType.MOUSE_DOWN: 'mouse_down',
        ExprType.DAYS_SINCE_2000: 'days_since_2000',
    }
    if t in sensing:
        return f"{sensing[t]}()"
    if t == ExprType.CURRENT:
        return f"current({_q(str(expr.name))})"
    # 兜底：去掉 self. 前缀（未覆盖的表达式会被编译器明确报错）
    return expr.to_python_source().replace('self.', '')


# ===================== 语句 =====================

class _Emitter:
    def __init__(self, comments: Dict[str, List[str]], warnings: List[str]):
        self.comments = comments
        self.warnings = warnings

    def _comments(self, stmt: Statement) -> List[str]:
        block_id = stmt.extra.get('block_id')
        lines: List[str] = []
        for text in self.comments.get(block_id, []):
            for part in str(text).splitlines() or ['']:
                lines.append(f"# {part}".rstrip())
        return lines

    def emit(self, stmt: Statement, indent: int = 0) -> List[str]:
        spaces = '    ' * indent
        out = [spaces + line for line in self._comments(stmt)]
        t = stmt.type
        exp = lambda node: expr_source(node, self.warnings)

        def call(name: str, *args: str) -> None:
            out.append(f"{spaces}{name}({', '.join(args)})")

        if t == BlockType.MOVE_STEPS:
            call('move', exp(stmt.value))
        elif t == BlockType.TURN_RIGHT:
            call('turn_right', exp(stmt.value))
        elif t == BlockType.TURN_LEFT:
            call('turn_left', exp(stmt.value))
        elif t == BlockType.GO_TO_XY:
            call('goto', exp(stmt.extra.get('x')), exp(stmt.extra.get('y')))
        elif t == BlockType.GO_TO_RANDOM:
            target = str(stmt.extra.get('target', '_random_'))
            if target in ('_random_', '_random_position_'):
                call('goto_random')
            else:
                self.warnings.append(
                    f"未转换“移到 {target}”，ScPython 暂不支持指定目标")
                out.append(f"{spaces}# TODO goto {target}")
        elif t == BlockType.GLIDE_SECS_TO:
            call('glide', exp(stmt.value), exp(stmt.extra.get('x')),
                 exp(stmt.extra.get('y')))
        elif t == BlockType.GLIDE_TO:
            call('glide_to_target', exp(stmt.value),
                 _q(str(stmt.extra.get('target', '_random_'))))
        elif t == BlockType.POINT_IN_DIRECTION:
            call('point_in_direction', exp(stmt.value))
        elif t == BlockType.POINT_TOWARDS:
            call('point_towards',
                 _q(str(stmt.extra.get('target', '_mouse_'))))
        elif t == BlockType.SET_ROTATION_STYLE:
            call('set_rotation_style',
                 _q(str(stmt.extra.get('style', 'all around'))))
        elif t in (BlockType.CHANGE_X, BlockType.SET_X,
                   BlockType.CHANGE_Y, BlockType.SET_Y):
            name = {BlockType.CHANGE_X: 'change_x',
                    BlockType.SET_X: 'set_x',
                    BlockType.CHANGE_Y: 'change_y',
                    BlockType.SET_Y: 'set_y'}[t]
            call(name, exp(stmt.value))
        elif t == BlockType.IF_ON_EDGE_BOUNCE:
            call('if_on_edge_bounce')
        elif t == BlockType.SAY:
            call('say', exp(stmt.value))
        elif t == BlockType.SAY_FOR_SECS:
            call('say_for', exp(stmt.extra.get('message')), exp(stmt.value))
        elif t == BlockType.THINK:
            call('think', exp(stmt.value))
        elif t == BlockType.THINK_FOR_SECS:
            call('think_for', exp(stmt.extra.get('message')), exp(stmt.value))
        elif t == BlockType.SHOW:
            call('show')
        elif t == BlockType.HIDE:
            call('hide')
        elif t == BlockType.SWITCH_COSTUME:
            call('switch_costume', exp(stmt.value))
        elif t == BlockType.NEXT_COSTUME:
            call('next_costume')
        elif t == BlockType.SWITCH_BACKDROP:
            call('switch_backdrop', exp(stmt.value))
        elif t == BlockType.NEXT_BACKDROP:
            call('next_backdrop')
        elif t == BlockType.SET_SIZE:
            call('set_size', exp(stmt.value))
        elif t == BlockType.CHANGE_SIZE:
            call('change_size', exp(stmt.value))
        elif t == BlockType.SET_EFFECT:
            call('set_effect', _q(str(stmt.extra.get('effect', 'color'))),
                 exp(stmt.value))
        elif t == BlockType.CHANGE_EFFECT:
            call('change_effect', _q(str(stmt.extra.get('effect', 'color'))),
                 exp(stmt.value))
        elif t == BlockType.CLEAR_EFFECTS:
            call('clear_effects')
        elif t in (BlockType.GO_TO_FRONT, BlockType.GO_TO_BACK):
            call('go_to_front' if t == BlockType.GO_TO_FRONT
                 else 'go_to_back')
        elif t in (BlockType.GO_FORWARD_LAYERS, BlockType.GO_BACKWARD_LAYERS):
            call('go_forward' if t == BlockType.GO_FORWARD_LAYERS
                 else 'go_backward', exp(stmt.value))
        elif t == BlockType.PLAY_SOUND:
            call('play_sound', exp(stmt.value))
        elif t == BlockType.PLAY_SOUND_UNTIL_DONE:
            call('play_sound_until_done', exp(stmt.value))
        elif t == BlockType.STOP_ALL_SOUNDS:
            call('stop_all_sounds')
        elif t == BlockType.SET_VOLUME:
            call('set_volume', exp(stmt.value))
        elif t == BlockType.CHANGE_VOLUME:
            call('change_volume', exp(stmt.value))
        elif t == BlockType.WAIT:
            call('wait', exp(stmt.value))
        elif t == BlockType.ASK_AND_WAIT:
            call('ask_and_wait', exp(stmt.value))
        elif t == BlockType.RESET_TIMER:
            call('reset_timer')
        elif t == BlockType.SET_DRAG_MODE:
            call('set_drag_mode', _q(str(stmt.extra.get('mode', 'draggable'))))
        elif t == BlockType.INCR_COUNTER:
            call('incr_counter')
        elif t == BlockType.CLEAR_COUNTER:
            call('clear_counter')
        elif t == BlockType.WAIT_UNTIL:
            call('wait_until', exp(stmt.condition))
        elif t == BlockType.REPEAT:
            out.append(f"{spaces}for _repeat in range({exp(stmt.value)}):")
            out.extend(self._body(stmt.body, indent + 1))
        elif t == BlockType.FOREVER:
            out.append(f"{spaces}while True:")
            out.extend(self._body(stmt.body, indent + 1))
        elif t == BlockType.IF:
            out.append(f"{spaces}if {exp(stmt.condition)}:")
            out.extend(self._body(stmt.body, indent + 1))
        elif t == BlockType.IF_ELSE:
            out.append(f"{spaces}if {exp(stmt.condition)}:")
            out.extend(self._body(stmt.body, indent + 1))
            out.append(f"{spaces}else:")
            out.extend(self._body(stmt.else_body, indent + 1))
        elif t == BlockType.REPEAT_UNTIL:
            out.append(f"{spaces}while not ({exp(stmt.condition)}):")
            out.extend(self._body(stmt.body, indent + 1))
        elif t == BlockType.STOP:
            option = str(stmt.extra.get('option', 'all'))
            stop_name = {
                'all': 'stop_all',
                'this script': 'stop_this_script',
                'other scripts in sprite': 'stop_other_scripts',
                'other scripts in stage': 'stop_other_scripts',
            }.get(option)
            if stop_name:
                call(stop_name)
            else:
                self.warnings.append(f"未知的 stop 选项: {option}")
        elif t == BlockType.SET_VARIABLE:
            out.append(f"{spaces}{_san(stmt.extra.get('name', 'var'), 'var')}"
                       f" = {exp(stmt.value)}")
        elif t == BlockType.CHANGE_VARIABLE:
            out.append(f"{spaces}{_san(stmt.extra.get('name', 'var'), 'var')}"
                       f" += {exp(stmt.value)}")
        elif t == BlockType.ADD_TO_LIST:
            call('add_to_list', _san(stmt.extra.get('name', 'list'), 'lst'),
                 exp(stmt.value))
        elif t == BlockType.DELETE_FROM_LIST:
            call('delete_of_list',
                 _san(stmt.extra.get('name', 'list'), 'lst'), exp(stmt.value))
        elif t == BlockType.DELETE_ALL_FROM_LIST:
            call('delete_all_of_list',
                 _san(stmt.extra.get('name', 'list'), 'lst'))
        elif t == BlockType.INSERT_IN_LIST:
            call('insert_in_list',
                 _san(stmt.extra.get('name', 'list'), 'lst'),
                 exp(stmt.value), exp(stmt.extra.get('item')))
        elif t == BlockType.REPLACE_IN_LIST:
            call('replace_in_list',
                 _san(stmt.extra.get('name', 'list'), 'lst'),
                 exp(stmt.value), exp(stmt.extra.get('item')))
        elif t == BlockType.SHOW_VARIABLE:
            call('show_variable', _q(str(stmt.extra.get('name', 'var'))))
        elif t == BlockType.HIDE_VARIABLE:
            call('hide_variable', _q(str(stmt.extra.get('name', 'var'))))
        elif t == BlockType.SHOW_LIST:
            call('show_list', _q(str(stmt.extra.get('name', 'list'))))
        elif t == BlockType.HIDE_LIST:
            call('hide_list', _q(str(stmt.extra.get('name', 'list'))))
        elif t in (BlockType.BROADCAST, BlockType.BROADCAST_AND_WAIT):
            kind = ('broadcast' if t == BlockType.BROADCAST
                    else 'broadcast_and_wait')
            value = stmt.value
            if value is not None and value.type in (
                    ExprType.STRING, ExprType.NUMBER):
                call(kind, exp(value))
            else:
                self.warnings.append(
                    "未转换动态广播（Scratch 只允许常量广播名）")
                out.append(f"{spaces}# TODO 动态广播")
        elif t == BlockType.CREATE_CLONE_OF:
            call('create_clone', exp(stmt.value))
        elif t == BlockType.DELETE_THIS_CLONE:
            call('delete_this_clone')
        elif t == BlockType.PROCEDURE_CALL:
            call(_san(stmt.extra.get('name', 'proc'), 'proc'),
                 *(exp(a) for a in stmt.extra.get('args', [])))
        elif t == BlockType.PROCEDURE_RETURN:
            if stmt.value is not None:
                out.append(f"{spaces}return {exp(stmt.value)}")
            else:
                out.append(f"{spaces}return")
        elif t == BlockType.COMMENT:
            text = str(stmt.extra.get('text', ''))
            for part in text.splitlines() or ['']:
                out.append(f"{spaces}# {part}".rstrip())
        elif t == BlockType.EXTENSION:
            namespace = str(stmt.extra.get('namespace', ''))
            opcode = str(stmt.extra.get('opcode', ''))
            parts = [_q(namespace), _q(opcode)]
            for slot, value in (stmt.extra.get('inputs') or []):
                if re.match(r'^[A-Za-z_]\w*$', str(slot)):
                    parts.append(f"{slot}={exp(value)}")
            fields = stmt.extra.get('fields') or {}
            if fields:
                self.warnings.append(
                    f"扩展 {opcode} 的字段 {sorted(fields)} 未转换")
            out.append(f"{spaces}ext({', '.join(parts)})")
        else:
            self.warnings.append(f"未转换块 {t.name}")
            out.append(f"{spaces}# TODO: {t.name}")
        return out

    def _body(self, body: List[Statement], indent: int) -> List[str]:
        if not body:
            return ['    ' * indent + 'pass']
        out: List[str] = []
        for item in body:
            out.extend(self.emit(item, indent))
        # 未转换的块只会留下注释，需要补 pass 避免空块语法错误
        if not any(line.strip() and not line.strip().startswith('#')
                   for line in out):
            out.append('    ' * indent + 'pass')
        return out


# ===================== 事件/角色 =====================

def _event_header(stmt: Statement) -> Optional[str]:
    t = stmt.type
    if t == BlockType.WHEN_FLAG_CLICKED:
        return 'when green_flag:'
    if t == BlockType.WHEN_KEY_PRESSED:
        return f"when key_pressed({_q(str(stmt.extra.get('key', 'space')))}):"
    if t == BlockType.WHEN_THIS_SPRITE_CLICKED:
        return 'when this_sprite_clicked:'
    if t == BlockType.WHEN_BROADCAST_RECEIVED:
        return f"when broadcast({expr_source(stmt.value)}):"
    if t == BlockType.WHEN_BACKDROP_SWITCHES:
        return ("when backdrop_switches_to("
                f"{_q(str(stmt.extra.get('backdrop', 'backdrop1')))}):")
    if t == BlockType.WHEN_GREATER_THAN:
        menu = str(stmt.extra.get('menu', 'TIMER')).lower()
        return f"when {menu} > {expr_source(stmt.value)}:"
    if t == BlockType.WHEN_TIMER:
        # ScPython 只支持 "when timer > x" 形式，裸 timer 帽子无法表达
        return None
    if t == BlockType.WHEN_LOUDNESS:
        return None
    if t == BlockType.START_AS_CLONE:
        return 'when clone_start:'
    if t == BlockType.EXTENSION_HAT:
        ns = stmt.extra.get('namespace', 'ext')
        op = stmt.extra.get('opcode', 'event')
        return f"when {ns}.{op}:"
    return None


def _procedure_source(stmt: Statement,
                      comments: Optional[Dict[str, List[str]]] = None
                      ) -> Tuple[str, str, str]:
    """返回 (函数名, 完整源码, 用于宏比较的正文 key)。"""
    name = _san(stmt.extra.get('name', 'procedure'), 'proc')
    args = [ _san(a, 'arg') for a in stmt.extra.get('args', []) ]
    types = ''.join(stmt.extra.get('arg_types') or [])
    if len(types) != len(args):
        types = 's' * len(args)
    warp = bool(stmt.extra.get('warp', False))
    label = str(stmt.extra.get('proccode', '') or '')
    meta = []
    if types:
        meta.append(f"types={_q(types)}")
    if warp:
        meta.append('warp=True')
    if label:
        meta.append(f"label={_q(label)}")
    signature = ', '.join(args)
    if meta:
        if signature:
            signature += ', *, ' + ', '.join(meta)
        else:
            signature = '*, ' + ', '.join(meta)
    body_lines: List[str] = []
    for item in stmt.body:
        body_lines.extend(_Emitter(comments or {}, []).emit(item, 1))
    if not body_lines:
        body_lines = ['    pass']
    text = '\n'.join([f"def {name}({signature}):"] + body_lines)
    key = (name, tuple(args), types, warp, label,
           re.sub(r'\s+', ' ', '\n'.join(line.strip()
                                         for line in body_lines)))
    return name, text, repr(key)


_RESERVED_INIT = {
    'name', 'costumes', 'sounds', 'extensions', 'x', 'y', 'direction',
    'visible', 'size', 'rotation_style', 'draggable', 'current_costume',
}


def _init_lines(sprite, comments: List[str],
                skip_vars=None, skip_lists=None) -> List[str]:
    skip_vars = skip_vars or set()
    skip_lists = skip_lists or set()
    lines: List[str] = []
    for text in comments:
        for part in str(text).splitlines() or ['']:
            lines.append(f"# {part}".rstrip())
    body: List[str] = []
    costumes = [str(c.get('md5ext') or c.get('name') or '')
                for c in (sprite.costumes or [])]
    costumes = [c for c in costumes if c]
    if costumes:
        body.append(f"costumes = {costumes!r}")
    sounds = [str(s.get('md5ext') or s.get('name') or '')
              for s in (sprite.sounds or [])]
    sounds = [s for s in sounds if s]
    if sounds:
        body.append(f"sounds = {sounds!r}")
    for name, value in (sprite.variables or {}).items():
        if name in skip_vars:
            continue  # 全局变量只在舞台声明一次
        ident = _san(name, 'var')
        if name in _RESERVED_INIT:
            # x/y/size 等名字在 init 中会被当成角色属性，改用调试声明
            body.append(f"debug.set_default({ident!r}, {value!r})")
        else:
            body.append(f"var {ident} = {value!r}")
    for name, value in (sprite.lists or {}).items():
        if name in skip_lists:
            continue
        ident = _san(name, 'lst')
        if name in _RESERVED_INIT:
            body.append(
                f"debug.set_list_default({ident!r}, {list(value)!r})")
        else:
            body.append(f"list {ident} = {list(value)!r}")
    if not sprite.is_stage:
        body.extend([
            f"x = {sprite.x}", f"y = {sprite.y}",
            f"direction = {sprite.direction}", f"size = {sprite.size}",
            f"visible = {sprite.visible}",
            f"rotation_style = {sprite.rotation_style!r}",
            f"draggable = {sprite.draggable}",
        ])
    if not body:
        return lines
    if lines:
        lines.append('')
    lines.append('init:')
    lines.extend(f"    {line}" for line in body)
    return lines


def _sprite_source(sprite, comments: Dict[str, List[str]],
                   standalone: List[str], warnings: List[str],
                   include_procedures: bool = True,
                   exclude_keys=None,
                   skip_vars=None, skip_lists=None) -> Tuple[str, List[str]]:
    lines = _init_lines(sprite, standalone, skip_vars, skip_lists)
    emitter = _Emitter(comments, warnings)
    procedures: List[str] = []
    for stmt in sprite.statements:
        if stmt.type == BlockType.PROCEDURE_DEFINE:
            if include_procedures:
                _name, text, key = _procedure_source(stmt, comments)
                if exclude_keys is None or key not in exclude_keys:
                    procedures.append(text)
            continue
        if stmt.type in _EVENT_TYPES:
            header = _event_header(stmt)
            if header is None:
                warnings.append(
                    f"{sprite.name}: 未转换事件头 {stmt.type.name}")
                continue
            if lines:
                lines.append('')
            lines.append(header)
            body = _chain(stmt.next) if stmt.next is not None else stmt.body
            lines.extend(emitter._body(body, 1))
    for text in procedures:
        lines.append('')
        lines.extend(text.splitlines())
    return '\n'.join(lines).rstrip() + '\n', procedures


# ===================== 入口 =====================

def _read_project(path: str) -> Tuple[dict, Optional[zipfile.ZipFile]]:
    if path.lower().endswith('.json'):
        with open(path, encoding='utf-8') as handle:
            return json.load(handle), None
    archive = zipfile.ZipFile(path)
    try:
        data = json.loads(archive.read('project.json').decode('utf-8'))
    except KeyError as error:
        archive.close()
        raise ScPythonError("sb3 中缺少 project.json", path=path) from error
    return data, archive


def import_sb3(path: str, output_dir: str, *,
               split_macros: bool = True) -> str:
    """把 .sb3 转成 ScPython 工程目录，返回目录路径。"""
    path = os.path.abspath(path)
    output_dir = os.path.abspath(output_dir)
    if not os.path.isfile(path):
        raise ScPythonError(f"输入文件不存在: {path}", path=path)
    data, archive = _read_project(path)
    try:
        project: ProjectIR = parse_scratch_project(data)
        os.makedirs(output_dir, exist_ok=True)
        assets_dir = os.path.join(output_dir, 'assets')
        os.makedirs(assets_dir, exist_ok=True)
        if archive is not None:
            for name in archive.namelist():
                if name == 'project.json' or name.endswith('/'):
                    continue
                safe = os.path.basename(name)
                if not safe:
                    continue
                with open(os.path.join(assets_dir, safe), 'wb') as handle:
                    handle.write(archive.read(name))

        target_comments: Dict[str, Dict[str, List[str]]] = {}
        standalone: Dict[str, List[str]] = {}
        for target in data.get('targets', []):
            tname = str(target.get('name', ''))
            by_block: Dict[str, List[str]] = {}
            top: List[str] = []
            for comment in (target.get('comments') or {}).values():
                if not isinstance(comment, dict):
                    continue
                text = str(comment.get('text', ''))
                if not text:
                    continue
                block_id = comment.get('blockId')
                if block_id:
                    by_block.setdefault(str(block_id), []).append(text)
                else:
                    top.append(text)
            target_comments[tname] = by_block
            standalone[tname] = top

        warnings: List[str] = []
        duplicated = set()
        macro_texts: Dict[str, str] = {}

        stage_target = next(
            (target for target in data.get('targets', [])
             if target.get('isStage')), {})
        global_vars = {str(value[0]) for value in
                       (stage_target.get('variables') or {}).values()
                       if isinstance(value, list) and value}
        global_lists = {str(value[0]) for value in
                        (stage_target.get('lists') or {}).values()
                        if isinstance(value, list) and value}

        if split_macros:
            counts = Counter()
            for sprite in project.sprites:
                for stmt in sprite.statements:
                    if stmt.type != BlockType.PROCEDURE_DEFINE:
                        continue
                    _name, text, key = _procedure_source(
                        stmt, target_comments.get(sprite.name, {}))
                    counts[key] += 1
                    macro_texts[key] = text
            duplicated = {key for key, count in counts.items() if count > 1}

        for sprite in project.sprites:
            base = 'stage' if sprite.is_stage else _san(sprite.name, 'Sprite')
            filename = 'stage.scpy' if sprite.is_stage else f"{base}.scpy"
            comments = target_comments.get(sprite.name, {})
            src, _ = _sprite_source(
                sprite, comments, standalone.get(sprite.name, []), warnings,
                include_procedures=True, exclude_keys=duplicated,
                skip_vars=global_vars if not sprite.is_stage else None,
                skip_lists=global_lists if not sprite.is_stage else None)
            with open(os.path.join(output_dir, filename), 'w',
                      encoding='utf-8') as handle:
                handle.write(src)

        if duplicated:
            with open(os.path.join(output_dir, 'macros.scpy'), 'w',
                      encoding='utf-8') as handle:
                handle.write('\n\n'.join(
                    macro_texts[key] for key in sorted(duplicated)
                ).rstrip() + '\n')

        for warning in warnings:
            print(f"[警告] {warning}")
        return output_dir
    finally:
        if archive is not None:
            archive.close()
