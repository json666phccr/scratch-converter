#!/usr/bin/env python3
"""
中间表示 (Intermediate Representation)
Scratch <-> 高级语言 双向转换的核心数据结构
所有Scratch块和高级语言结构都映射到这个统一的IR
"""

from __future__ import annotations
import json
import copy
import re
import hashlib
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum, auto
import uuid


def sanitize_name(name: str, prefix: str = "") -> str:
    """将Scratch名称转换为合法的Python标识符
    规则：
    - 中文字符、字母、数字、下划线保留
    - 冒号、连字符等替换为下划线
    - 不能以数字开头（加前缀）
    - 不能是Python关键字（加前缀）
    """
    # 只替换非合法字符，保留下划线；Scratch 中 "_i" 和 "i" 是两个不同变量，
    # 如果把下划线归一化掉它们会撞成同一个属性。
    sanitized = re.sub(r'[^\w\u4e00-\u9fff]+', '_', name)
    if not sanitized.strip('_'):
        # 纯符号名字（如 "."）用hash保证唯一且可追溯，避免都撞成 unnamed
        digest = hashlib.md5(name.encode('utf-8')).hexdigest()[:6]
        sanitized = f"{prefix or 'v'}_unnamed_{digest}"

    # 如果以数字开头，加前缀
    if sanitized[0].isdigit():
        sanitized = (prefix or "n") + sanitized

    # 避免Python关键字
    python_keywords = {
        'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await',
        'break', 'class', 'continue', 'def', 'del', 'elif', 'else', 'except',
        'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is',
        'lambda', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return',
        'try', 'while', 'with', 'yield',
    }
    if sanitized in python_keywords:
        sanitized = prefix + sanitized if prefix else "s_" + sanitized

    return sanitized


_PROCEDURE_NAME_RESOLVER = None


def set_procedure_name_resolver(resolver):
    """设置proccode -> 唯一Python方法名的解析器（由生成器使用）"""
    global _PROCEDURE_NAME_RESOLVER
    _PROCEDURE_NAME_RESOLVER = resolver


SPECIAL_KEYS = {
    'space': 'space',
    'up arrow': 'up_arrow',
    'down arrow': 'down_arrow',
    'left arrow': 'left_arrow',
    'right arrow': 'right_arrow',
    'any': 'any',
    'enter': 'enter',
}


def key_to_identifier(key: str) -> str:
    """Scratch按键名 -> Python标识符片段（避免"up arrow"这类含空格的名字）"""
    return SPECIAL_KEYS.get(key, sanitize_name(key, 'key'))


def identifier_to_key(identifier: str) -> str:
    """Python标识符片段 -> Scratch按键名"""
    for key, ident in SPECIAL_KEYS.items():
        if ident == identifier:
            return key
    return identifier


# ===================== Scratch块类型枚举 =====================

class BlockType(Enum):
    """Scratch块类型"""
    # 事件
    WHEN_FLAG_CLICKED = auto()
    WHEN_KEY_PRESSED = auto()
    WHEN_THIS_SPRITE_CLICKED = auto()
    WHEN_BACKDROP_SWITCHES = auto()
    WHEN_BROADCAST_RECEIVED = auto()
    WHEN_GREATER_THAN = auto()
    WHEN_LOUDNESS = auto()
    WHEN_TIMER = auto()

    # 运动
    MOVE_STEPS = auto()
    TURN_RIGHT = auto()
    TURN_LEFT = auto()
    GO_TO_XY = auto()
    GO_TO_RANDOM = auto()
    GLIDE_TO = auto()
    GLIDE_SECS_TO = auto()
    POINT_IN_DIRECTION = auto()
    POINT_TOWARDS = auto()
    CHANGE_X = auto()
    SET_X = auto()
    CHANGE_Y = auto()
    SET_Y = auto()
    SET_ROTATION_STYLE = auto()
    IF_ON_EDGE_BOUNCE = auto()

    # 外观
    SAY = auto()
    SAY_FOR_SECS = auto()
    THINK = auto()
    THINK_FOR_SECS = auto()
    SHOW = auto()
    HIDE = auto()
    SWITCH_COSTUME = auto()
    NEXT_COSTUME = auto()
    SWITCH_BACKDROP = auto()
    NEXT_BACKDROP = auto()
    SWITCH_BACKDROP_AND_WAIT = auto()
    CHANGE_SIZE = auto()
    SET_SIZE = auto()
    CHANGE_EFFECT = auto()
    SET_EFFECT = auto()
    CLEAR_EFFECTS = auto()
    GO_TO_FRONT = auto()
    GO_TO_BACK = auto()
    GO_FORWARD_LAYERS = auto()
    GO_BACKWARD_LAYERS = auto()

    # 声音
    PLAY_SOUND = auto()
    PLAY_SOUND_UNTIL_DONE = auto()
    STOP_ALL_SOUNDS = auto()
    CHANGE_VOLUME = auto()
    SET_VOLUME = auto()
    SET_SOUND_EFFECT = auto()
    CHANGE_SOUND_EFFECT = auto()
    CLEAR_SOUND_EFFECTS = auto()

    # 事件(控制)
    WAIT = auto()
    REPEAT = auto()
    FOREVER = auto()
    IF = auto()
    IF_ELSE = auto()
    WAIT_UNTIL = auto()
    REPEAT_UNTIL = auto()
    FOR_EACH = auto()
    ALL_AT_ONCE = auto()
    INCR_COUNTER = auto()
    CLEAR_COUNTER = auto()
    STOP = auto()
    START_AS_CLONE = auto()
    CREATE_CLONE_OF = auto()
    DELETE_THIS_CLONE = auto()

    # 侦测
    TOUCHING_OBJECT = auto()
    TOUCHING_COLOR = auto()
    COLOR_TOUCHING_COLOR = auto()
    DISTANCE_TO = auto()
    ASK_AND_WAIT = auto()
    KEY_PRESSED = auto()
    MOUSE_DOWN = auto()
    SET_DRAG_MODE = auto()
    RESET_TIMER = auto()
    OF_PROPERTY = auto()
    CURRENT = auto()

    # 运算
    ADD = auto()
    SUBTRACT = auto()
    MULTIPLY = auto()
    DIVIDE = auto()
    RANDOM = auto()
    LESS_THAN = auto()
    EQUALS = auto()
    GREATER_THAN = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    JOIN = auto()
    LETTER_OF = auto()
    LENGTH = auto()
    CONTAINS = auto()
    MOD = auto()
    ROUND = auto()
    MATH_OP = auto()

    # 变量和列表
    SET_VARIABLE = auto()
    CHANGE_VARIABLE = auto()
    SHOW_VARIABLE = auto()
    HIDE_VARIABLE = auto()
    ADD_TO_LIST = auto()
    DELETE_FROM_LIST = auto()
    DELETE_ALL_FROM_LIST = auto()
    INSERT_IN_LIST = auto()
    REPLACE_IN_LIST = auto()
    ITEM_OF_LIST = auto()
    ITEM_NUMBER_OF_LIST = auto()
    LENGTH_OF_LIST = auto()
    LIST_CONTAINS_ITEM = auto()
    SHOW_LIST = auto()
    HIDE_LIST = auto()

    # 广播
    BROADCAST = auto()
    BROADCAST_AND_WAIT = auto()

    # 自制积木
    PROCEDURE_DEFINE = auto()
    PROCEDURE_CALL = auto()
    PROCEDURE_RETURN = auto()
    ARGUMENT_REPORTER = auto()

    # 值(字面量/变量引用/表达式)
    NUMBER = auto()
    STRING = auto()
    BOOLEAN = auto()
    VARIABLE = auto()
    LIST_REFERENCE = auto()
    PROPERTY = auto()  # x position, y position, direction, etc.
    SENSING = auto()

    # TurboWarp扩展
    EXTENSION = auto()

    # 特殊
    COMMENT = auto()
    UNKNOWN = auto()


# ===================== 表达式节点 =====================

class ExprType(Enum):
    """表达式类型"""
    NUMBER = auto()
    STRING = auto()
    BOOLEAN = auto()
    VARIABLE = auto()
    PROPERTY = auto()    # sprite的属性: x, y, direction等
    BINARY_OP = auto()   # 二元运算
    UNARY_OP = auto()    # 一元运算
    FUNCTION_CALL = auto()  # 函数调用
    PROCEDURE_CALL = auto()  # 自制积木/reporter调用
    EXTENSION_CALL = auto()  # TurboWarp扩展调用
    LIST_ACCESS = auto()
    ITEM_OF_LIST = auto()
    ITEM_NUMBER_OF_LIST = auto()
    LENGTH_OF_LIST = auto()
    LIST_CONTAINS = auto()
    SENSING = auto()
    RANDOM = auto()
    MATH_OP = auto()
    JOIN = auto()
    LETTER_OF = auto()
    LENGTH_OF_STRING = auto()
    CONTAINS_STRING = auto()
    ANSWER = auto()
    TIMER = auto()
    LOUDNESS = auto()
    MOUSE_X = auto()
    MOUSE_Y = auto()
    MOUSE_DOWN = auto()
    DAYS_SINCE_2000 = auto()
    CURRENT = auto()
    ARGUMENT = auto()
    NOT = auto()
    AND = auto()
    OR = auto()
    EQUAL = auto()
    LESS_THAN = auto()
    GREATER_THAN = auto()
    MOD = auto()
    ROUND = auto()
    ABS = auto()
    FLOOR = auto()
    CEILING = auto()
    SQRT = auto()
    SIN = auto()
    COS = auto()
    TAN = auto()
    ASIN = auto()
    ACOS = auto()
    ATAN = auto()
    LN = auto()
    LOG = auto()
    EXP = auto()
    POW10 = auto()
    TOUCHING_COLOR = auto()
    COLOR_TOUCHING_COLOR = auto()


@dataclass
class Expr:
    """表达式节点 - 所有值和表达式的统一表示"""
    type: ExprType
    value: Any = None
    left: Optional[Expr] = None
    right: Optional[Expr] = None
    children: List[Expr] = field(default_factory=list)
    name: str = ""
    args: List[Expr] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def __repr__(self):
        if self.type == ExprType.NUMBER:
            return f"Num({self.value})"
        elif self.type == ExprType.STRING:
            return f"Str({self.value!r})"
        elif self.type == ExprType.BOOLEAN:
            return f"Bool({self.value})"
        elif self.type == ExprType.VARIABLE:
            return f"Var({self.name})"
        elif self.type == ExprType.BINARY_OP:
            return f"({self.left} {self.name} {self.right})"
        elif self.type == ExprType.UNARY_OP:
            return f"({self.name}{self.right})"
        elif self.type == ExprType.FUNCTION_CALL:
            args_str = ", ".join(repr(a) for a in self.args)
            return f"{self.name}({args_str})"
        return f"Expr({self.type.name}, {self.value})"

    def to_python_source(self) -> str:
        """将表达式转换为Python源代码字符串

        所有涉及类型转换/比较的运算都走 _sc_* 辅助函数，以复刻Scratch运行时语义。
        """
        if self.type == ExprType.NUMBER:
            if isinstance(self.value, float) and self.value == int(self.value):
                return str(int(self.value))
            return str(self.value)
        elif self.type == ExprType.STRING:
            return repr(self.value)
        elif self.type == ExprType.BOOLEAN:
            return "True" if self.value else "False"
        elif self.type == ExprType.VARIABLE:
            return f"self.{sanitize_name(self.name, 'var')}"
        elif self.type == ExprType.PROPERTY:
            sprite = "self"
            prop = self.name
            target = self.extra.get('sprite', '_sprite_')
            if target not in ('_sprite_', '_stage_'):
                return f"self.sensing_of({target!r}, {prop!r})"
            if prop == 'x position':
                return f"{sprite}.x"
            elif prop == 'y position':
                return f"{sprite}.y"
            elif prop == 'direction':
                return f"{sprite}.direction"
            elif prop == 'costume #':
                return f"{sprite}.costume_number"
            elif prop == 'costume name':
                return f"{sprite}.costume_name"
            elif prop == 'backdrop #':
                return f"{sprite}.backdrop_number"
            elif prop == 'backdrop name':
                return f"{sprite}.backdrop_name"
            elif prop == 'size':
                return f"{sprite}.size"
            elif prop == 'volume':
                return f"{sprite}.volume"
            return f"{sprite}.{prop}"
        elif self.type == ExprType.BINARY_OP:
            left = self.left.to_python_source() if self.left else "0"
            right = self.right.to_python_source() if self.right else "0"
            func = {
                '+': '_sc_add', '-': '_sc_sub',
                '*': '_sc_mul', '/': '_sc_div',
            }.get(self.name)
            if func:
                return f"{func}({left}, {right})"
            return f"({left} {self.name} {right})"
        elif self.type == ExprType.UNARY_OP:
            right = self.right.to_python_source() if self.right else "0"
            if self.name == 'not':
                return f"_sc_not({right})"
            return f"({self.name}{right})"
        elif self.type == ExprType.FUNCTION_CALL:
            args_str = ", ".join(a.to_python_source() for a in self.args)
            if self.name in ('key_pressed', 'touching', 'distance_to',
                             'get_counter', 'username'):
                return f"self.{self.name}({args_str})"
            return f"{self.name}({args_str})"
        elif self.type == ExprType.PROCEDURE_CALL:
            args_str = ", ".join(a.to_python_source() for a in self.args)
            name = self.name
            if _PROCEDURE_NAME_RESOLVER is not None:
                name = _PROCEDURE_NAME_RESOLVER(
                    self.extra.get('proccode'), name)
            return f"self.{sanitize_name(name, 'proc')}({args_str})"
        elif self.type == ExprType.EXTENSION_CALL:
            inputs = ', '.join(
                f"{key!r}: {value.to_python_source()}"
                for key, value in self.extra.get('inputs', []))
            return (f"self.extension({self.extra.get('namespace', '')!r}, "
                    f"{self.extra.get('opcode', '')!r}, {{{inputs}}}, "
                    f"{self.extra.get('fields', {})!r})")
        elif self.type == ExprType.RANDOM:
            low = self.left.to_python_source() if self.left else "1"
            high = self.right.to_python_source() if self.right else "10"
            return f"_sc_random({low}, {high})"
        elif self.type == ExprType.ANSWER:
            return "self.answer"
        elif self.type == ExprType.TIMER:
            return "self.timer"
        elif self.type == ExprType.LOUDNESS:
            return "self.loudness"
        elif self.type == ExprType.MOUSE_X:
            return "self.mouse_x"
        elif self.type == ExprType.MOUSE_Y:
            return "self.mouse_y"
        elif self.type == ExprType.MOUSE_DOWN:
            return "self.mouse_down"
        elif self.type == ExprType.DAYS_SINCE_2000:
            return "self.days_since_2000"
        elif self.type == ExprType.LIST_ACCESS:
            return f"_sc_list_contents(self.{sanitize_name(self.name, 'lst')})"
        elif self.type == ExprType.ITEM_OF_LIST:
            list_name = f"self.{sanitize_name(self.name, 'lst')}"
            index = self.left.to_python_source() if self.left else "1"
            return f"_sc_item_of({list_name}, {index})"
        elif self.type == ExprType.ITEM_NUMBER_OF_LIST:
            item = self.left.to_python_source() if self.left else "''"
            return f"_sc_list_item_number(self.{sanitize_name(self.name, 'lst')}, {item})"
        elif self.type == ExprType.LENGTH_OF_LIST:
            return f"len(self.{sanitize_name(self.name, 'lst')})"
        elif self.type == ExprType.LIST_CONTAINS:
            item = self.left.to_python_source() if self.left else "''"
            return f"_sc_list_contains(self.{sanitize_name(self.name, 'lst')}, {item})"
        elif self.type in (ExprType.MATH_OP, ExprType.ABS, ExprType.FLOOR,
                           ExprType.CEILING, ExprType.SQRT, ExprType.SIN,
                           ExprType.COS, ExprType.TAN, ExprType.ASIN,
                           ExprType.ACOS, ExprType.ATAN, ExprType.LN,
                           ExprType.LOG, ExprType.EXP, ExprType.POW10):
            op_map = {
                ExprType.ABS: 'abs', ExprType.FLOOR: 'floor',
                ExprType.CEILING: 'ceiling', ExprType.SQRT: 'sqrt',
                ExprType.SIN: 'sin', ExprType.COS: 'cos',
                ExprType.TAN: 'tan', ExprType.ASIN: 'asin',
                ExprType.ACOS: 'acos', ExprType.ATAN: 'atan',
                ExprType.LN: 'ln', ExprType.LOG: 'log',
                ExprType.EXP: 'e^', ExprType.POW10: '10^',
            }
            op = op_map.get(self.type, self.name.replace(' ', ''))
            num = self.right.to_python_source() if self.right else "0"
            return f"_sc_mathop('{op}', {num})"
        elif self.type == ExprType.JOIN:
            left = self.left.to_python_source() if self.left else "''"
            right = self.right.to_python_source() if self.right else "''"
            return f"_sc_join({left}, {right})"
        elif self.type == ExprType.LETTER_OF:
            letter = self.left.to_python_source() if self.left else "1"
            string = self.right.to_python_source() if self.right else "''"
            return f"_sc_letter_of({letter}, {string})"
        elif self.type == ExprType.LENGTH_OF_STRING:
            string = self.right.to_python_source() if self.right else "''"
            return f"_sc_length({string})"
        elif self.type == ExprType.CONTAINS_STRING:
            left = self.left.to_python_source() if self.left else "''"
            right = self.right.to_python_source() if self.right else "''"
            return f"_sc_contains({left}, {right})"
        elif self.type == ExprType.EQUAL:
            left = self.left.to_python_source() if self.left else "None"
            right = self.right.to_python_source() if self.right else "None"
            return f"_sc_eq({left}, {right})"
        elif self.type == ExprType.LESS_THAN:
            left = self.left.to_python_source() if self.left else "0"
            right = self.right.to_python_source() if self.right else "0"
            return f"_sc_lt({left}, {right})"
        elif self.type == ExprType.GREATER_THAN:
            left = self.left.to_python_source() if self.left else "0"
            right = self.right.to_python_source() if self.right else "0"
            return f"_sc_gt({left}, {right})"
        elif self.type == ExprType.AND:
            left = self.left.to_python_source() if self.left else "True"
            right = self.right.to_python_source() if self.right else "True"
            return f"_sc_and({left}, {right})"
        elif self.type == ExprType.OR:
            left = self.left.to_python_source() if self.left else "False"
            right = self.right.to_python_source() if self.right else "False"
            return f"_sc_or({left}, {right})"
        elif self.type == ExprType.NOT:
            right = self.right.to_python_source() if self.right else "True"
            return f"_sc_not({right})"
        elif self.type == ExprType.MOD:
            left = self.left.to_python_source() if self.left else "0"
            right = self.right.to_python_source() if self.right else "1"
            return f"_sc_mod({left}, {right})"
        elif self.type == ExprType.ROUND:
            num = self.right.to_python_source() if self.right else "0"
            return f"_sc_round({num})"
        elif self.type == ExprType.CURRENT:
            return f"self.current_time('{self.name}')"
        elif self.type == ExprType.TOUCHING_COLOR:
            color = self.left.to_python_source() if self.left else "''"
            return f"self.touching_color({color})"
        elif self.type == ExprType.COLOR_TOUCHING_COLOR:
            left = self.left.to_python_source() if self.left else "''"
            right = self.right.to_python_source() if self.right else "''"
            return f"self.color_touching_color({left}, {right})"
        elif self.type == ExprType.ARGUMENT:
            return f"arg_{sanitize_name(self.name, 'arg')}"
        return f"# Unknown expr: {self.type.name}"

    def to_scratch_value(self) -> Any:
        """将表达式转换为Scratch JSON值格式 [shadow, value, ...]"""
        if self.type == ExprType.NUMBER:
            num = self.value
            if isinstance(num, float) and num == int(num):
                num = int(num)
            return num
        elif self.type == ExprType.STRING:
            return self.value
        elif self.type == ExprType.BOOLEAN:
            return self.value
        return self.value


# ===================== 语句节点 =====================

@dataclass
class Statement:
    """语句节点 - 所有Scratch块和Python语句的统一表示"""
    type: BlockType
    args: Dict[str, Any] = field(default_factory=dict)
    body: List[Statement] = field(default_factory=list)        # 子语句块(循环/if体)
    else_body: List[Statement] = field(default_factory=list)   # else体
    substack: Optional[Statement] = None    # 子堆栈引用
    next: Optional[Statement] = None        # 下一个语句
    expr: Optional[Expr] = None             # 关联的表达式
    target: Optional[Expr] = None           # 目标(赋值目标)
    value: Optional[Expr] = None            # 值
    condition: Optional[Expr] = None        # 条件
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    extra: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self):
        return f"Stmt({self.type.name})"

    def append_body(self, stmt: Statement):
        """追加子语句"""
        self.body.append(stmt)

    def to_python_source(self, indent: int = 0) -> str:
        """将语句转换为Python源代码"""
        spaces = "    " * indent
        lines = []

        if self.type == BlockType.MOVE_STEPS:
            steps = self.value.to_python_source() if self.value else "10"
            lines.append(f"{spaces}move({steps})")

        elif self.type == BlockType.TURN_RIGHT:
            deg = self.value.to_python_source() if self.value else "15"
            lines.append(f"{spaces}turn_right({deg})")

        elif self.type == BlockType.TURN_LEFT:
            deg = self.value.to_python_source() if self.value else "15"
            lines.append(f"{spaces}turn_left({deg})")

        elif self.type == BlockType.GO_TO_XY:
            x = self.extra.get('x', Expr(ExprType.NUMBER, 0)).to_python_source()
            y = self.extra.get('y', Expr(ExprType.NUMBER, 0)).to_python_source()
            lines.append(f"{spaces}goto_xy({x}, {y})")

        elif self.type == BlockType.SAY:
            msg = self.value.to_python_source() if self.value else "''"
            lines.append(f"{spaces}say({msg})")

        elif self.type == BlockType.SAY_FOR_SECS:
            msg = self.extra.get('message', Expr(ExprType.STRING, '')).to_python_source()
            secs = self.value.to_python_source() if self.value else "1"
            lines.append(f"{spaces}say_for({msg}, {secs})")

        elif self.type == BlockType.THINK:
            msg = self.value.to_python_source() if self.value else "''"
            lines.append(f"{spaces}think({msg})")

        elif self.type == BlockType.THINK_FOR_SECS:
            msg = self.extra.get('message', Expr(ExprType.STRING, '')).to_python_source()
            secs = self.value.to_python_source() if self.value else "1"
            lines.append(f"{spaces}think_for({msg}, {secs})")

        elif self.type == BlockType.SHOW:
            lines.append(f"{spaces}show()")

        elif self.type == BlockType.HIDE:
            lines.append(f"{spaces}hide()")

        elif self.type == BlockType.SWITCH_COSTUME:
            name = self.value.to_python_source() if self.value else "'costume1'"
            lines.append(f"{spaces}switch_costume({name})")

        elif self.type == BlockType.NEXT_COSTUME:
            lines.append(f"{spaces}next_costume()")

        elif self.type == BlockType.CHANGE_SIZE:
            change = self.value.to_python_source() if self.value else "10"
            lines.append(f"{spaces}change_size({change})")

        elif self.type == BlockType.SET_SIZE:
            size = self.value.to_python_source() if self.value else "100"
            lines.append(f"{spaces}set_size({size})")

        elif self.type == BlockType.CHANGE_EFFECT:
            effect = self.extra.get('effect', 'color')
            change = self.value.to_python_source() if self.value else "25"
            lines.append(f"{spaces}change_effect('{effect}', {change})")

        elif self.type == BlockType.SET_EFFECT:
            effect = self.extra.get('effect', 'color')
            val = self.value.to_python_source() if self.value else "100"
            lines.append(f"{spaces}set_effect('{effect}', {val})")

        elif self.type == BlockType.CLEAR_EFFECTS:
            lines.append(f"{spaces}clear_effects()")

        elif self.type == BlockType.PLAY_SOUND:
            sound = self.value.to_python_source() if self.value else "'sound1'"
            lines.append(f"{spaces}play_sound({sound})")

        elif self.type == BlockType.STOP_ALL_SOUNDS:
            lines.append(f"{spaces}stop_all_sounds()")

        elif self.type == BlockType.CHANGE_VOLUME:
            change = self.value.to_python_source() if self.value else "10"
            lines.append(f"{spaces}change_volume({change})")

        elif self.type == BlockType.SET_VOLUME:
            vol = self.value.to_python_source() if self.value else "100"
            lines.append(f"{spaces}set_volume({vol})")

        elif self.type == BlockType.IF_ON_EDGE_BOUNCE:
            lines.append(f"{spaces}if_on_edge_bounce()")

        elif self.type == BlockType.WAIT:
            secs = self.value.to_python_source() if self.value else "1"
            lines.append(f"{spaces}wait({secs})")

        elif self.type == BlockType.REPEAT:
            times = self.value.to_python_source() if self.value else "10"
            lines.append(f"{spaces}for _repeat in range({times}):")
            for stmt in self.body:
                lines.append(stmt.to_python_source(indent + 1))
            if not self.body:
                lines.append(f"{spaces}    pass")

        elif self.type == BlockType.FOREVER:
            lines.append(f"{spaces}while True:")
            for stmt in self.body:
                lines.append(stmt.to_python_source(indent + 1))
            if not self.body:
                lines.append(f"{spaces}    pass")

        elif self.type == BlockType.IF:
            cond = self.condition.to_python_source() if self.condition else "True"
            lines.append(f"{spaces}if {cond}:")
            for stmt in self.body:
                lines.append(stmt.to_python_source(indent + 1))
            if not self.body:
                lines.append(f"{spaces}    pass")

        elif self.type == BlockType.IF_ELSE:
            cond = self.condition.to_python_source() if self.condition else "True"
            lines.append(f"{spaces}if {cond}:")
            for stmt in self.body:
                lines.append(stmt.to_python_source(indent + 1))
            if not self.body:
                lines.append(f"{spaces}    pass")
            lines.append(f"{spaces}else:")
            for stmt in self.else_body:
                lines.append(stmt.to_python_source(indent + 1))
            if not self.else_body:
                lines.append(f"{spaces}    pass")

        elif self.type == BlockType.WAIT_UNTIL:
            cond = self.condition.to_python_source() if self.condition else "True"
            lines.append(f"{spaces}wait_until(lambda: {cond})")

        elif self.type == BlockType.REPEAT_UNTIL:
            cond = self.condition.to_python_source() if self.condition else "False"
            lines.append(f"{spaces}while not ({cond}):")
            for stmt in self.body:
                lines.append(stmt.to_python_source(indent + 1))
            if not self.body:
                lines.append(f"{spaces}    pass")

        elif self.type == BlockType.STOP:
            lines.append(f"{spaces}stop()")

        elif self.type == BlockType.SET_VARIABLE:
            var_name = self.extra.get('name', 'var')
            val = self.value.to_python_source() if self.value else "0"
            lines.append(f"{spaces}{var_name} = {val}")

        elif self.type == BlockType.CHANGE_VARIABLE:
            var_name = self.extra.get('name', 'var')
            val = self.value.to_python_source() if self.value else "1"
            lines.append(f"{spaces}{var_name} += {val}")

        elif self.type == BlockType.ADD_TO_LIST:
            list_name = self.extra.get('name', 'list')
            item = self.value.to_python_source() if self.value else "''"
            lines.append(f"{spaces}{list_name}.append({item})")

        elif self.type == BlockType.DELETE_FROM_LIST:
            list_name = self.extra.get('name', 'list')
            index = self.value.to_python_source() if self.value else "1"
            lines.append(f"{spaces}del {list_name}[{index} - 1]")

        elif self.type == BlockType.DELETE_ALL_FROM_LIST:
            list_name = self.extra.get('name', 'list')
            lines.append(f"{spaces}{list_name}.clear()")

        elif self.type == BlockType.INSERT_IN_LIST:
            list_name = self.extra.get('name', 'list')
            item = self.extra.get('item', Expr(ExprType.STRING, '')).to_python_source()
            index = self.value.to_python_source() if self.value else "1"
            lines.append(f"{spaces}{list_name}.insert({index} - 1, {item})")

        elif self.type == BlockType.REPLACE_IN_LIST:
            list_name = self.extra.get('name', 'list')
            item = self.extra.get('item', Expr(ExprType.STRING, '')).to_python_source()
            index = self.value.to_python_source() if self.value else "1"
            lines.append(f"{spaces}{list_name}[{index} - 1] = {item}")

        elif self.type == BlockType.SHOW_VARIABLE:
            var_name = self.extra.get('name', 'var')
            lines.append(f"{spaces}show_variable('{var_name}')")

        elif self.type == BlockType.HIDE_VARIABLE:
            var_name = self.extra.get('name', 'var')
            lines.append(f"{spaces}hide_variable('{var_name}')")

        elif self.type == BlockType.SHOW_LIST:
            list_name = self.extra.get('name', 'list')
            lines.append(f"{spaces}show_list('{list_name}')")

        elif self.type == BlockType.HIDE_LIST:
            list_name = self.extra.get('name', 'list')
            lines.append(f"{spaces}hide_list('{list_name}')")

        elif self.type == BlockType.BROADCAST:
            msg = self.value.to_python_source() if self.value else "''"
            lines.append(f"{spaces}broadcast({msg})")

        elif self.type == BlockType.BROADCAST_AND_WAIT:
            msg = self.value.to_python_source() if self.value else "''"
            lines.append(f"{spaces}broadcast_and_wait({msg})")

        elif self.type == BlockType.CREATE_CLONE_OF:
            target = self.value.to_python_source() if self.value else "'_myself_'"
            lines.append(f"{spaces}create_clone_of({target})")

        elif self.type == BlockType.DELETE_THIS_CLONE:
            lines.append(f"{spaces}delete_this_clone()")

        elif self.type == BlockType.PROCEDURE_DEFINE:
            name = self.extra.get('name', 'procedure')
            args_list = self.extra.get('args', [])
            args_str = ", ".join(f"arg_{a}" for a in args_list)
            lines.append(f"{spaces}def {name}({args_str}):")
            for stmt in self.body:
                lines.append(stmt.to_python_source(indent + 1))
            if not self.body:
                lines.append(f"{spaces}    pass")

        elif self.type == BlockType.PROCEDURE_CALL:
            name = self.extra.get('name', 'procedure')
            args_list = self.extra.get('args', [])
            args_str = ", ".join(a.to_python_source() for a in args_list)
            lines.append(f"{spaces}{name}({args_str})")

        elif self.type == BlockType.PROCEDURE_RETURN:
            lines.append(f"{spaces}return")

        elif self.type == BlockType.COMMENT:
            text = self.extra.get('text', '')
            lines.append(f"{spaces}# {text}")

        else:
            lines.append(f"{spaces}# TODO: {self.type.name}")

        return "\n".join(lines)


# ===================== 精灵/角色 =====================

@dataclass
class SpriteIR:
    """精灵的中间表示"""
    name: str
    is_stage: bool = False
    statements: List[Statement] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    lists: Dict[str, List[Any]] = field(default_factory=dict)
    broadcasts: List[str] = field(default_factory=list)
    costumes: List[Dict[str, Any]] = field(default_factory=list)
    sounds: List[Dict[str, Any]] = field(default_factory=list)
    current_costume: int = 0
    x: int = 0
    y: int = 0
    direction: float = 90
    visible: bool = True
    size: float = 100
    draggable: bool = False
    rotation_style: str = "all around"

    def add_statement(self, stmt: Statement):
        self.statements.append(stmt)

    def get_event_handlers(self) -> List[Statement]:
        """获取所有事件处理块"""
        event_types = {
            BlockType.WHEN_FLAG_CLICKED, BlockType.WHEN_KEY_PRESSED,
            BlockType.WHEN_THIS_SPRITE_CLICKED, BlockType.WHEN_BROADCAST_RECEIVED,
            BlockType.WHEN_BACKDROP_SWITCHES, BlockType.WHEN_GREATER_THAN,
            BlockType.WHEN_LOUDNESS, BlockType.WHEN_TIMER,
        }
        return [s for s in self.statements if s.type in event_types]

    def get_procedures(self) -> List[Statement]:
        """获取所有过程定义"""
        return [s for s in self.statements if s.type == BlockType.PROCEDURE_DEFINE]


# ===================== 项目 =====================

@dataclass
class ProjectIR:
    """整个项目的中间表示"""
    sprites: List[SpriteIR] = field(default_factory=list)
    stage: Optional[SpriteIR] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    warnings: Dict[str, int] = field(default_factory=dict)
    monitors: List[Dict[str, Any]] = field(default_factory=list)
    runtime_options: Dict[str, Any] = field(default_factory=dict)

    def add_sprite(self, sprite: SpriteIR):
        self.sprites.append(sprite)
        if sprite.is_stage:
            self.stage = sprite

    def get_all_sprites(self) -> List[SpriteIR]:
        return self.sprites

    def get_non_stage_sprites(self) -> List[SpriteIR]:
        return [s for s in self.sprites if not s.is_stage]


# ===================== 工具函数 =====================

def make_number(value: Union[int, float]) -> Expr:
    return Expr(ExprType.NUMBER, value=value)

def make_string(value: str) -> Expr:
    return Expr(ExprType.STRING, value=value)

def make_boolean(value: bool) -> Expr:
    return Expr(ExprType.BOOLEAN, value=value)

def make_variable(name: str) -> Expr:
    return Expr(ExprType.VARIABLE, name=name)

def make_property(sprite: str, prop: str) -> Expr:
    return Expr(ExprType.PROPERTY, name=prop, extra={'sprite': sprite})

def make_binary_op(op: str, left: Expr, right: Expr) -> Expr:
    return Expr(ExprType.BINARY_OP, name=op, left=left, right=right)

def make_unary_op(op: str, operand: Expr) -> Expr:
    return Expr(ExprType.UNARY_OP, name=op, right=operand)

def make_random(low: Expr, high: Expr) -> Expr:
    return Expr(ExprType.RANDOM, left=low, right=high)

def make_list_access(list_name: str, index: Expr) -> Expr:
    return Expr(ExprType.ITEM_OF_LIST, name=list_name, left=index)

def make_list_length(list_name: str) -> Expr:
    return Expr(ExprType.LENGTH_OF_LIST, name=list_name)

def make_list_contains(list_name: str, item: Expr) -> Expr:
    return Expr(ExprType.LIST_CONTAINS, name=list_name, left=item)
