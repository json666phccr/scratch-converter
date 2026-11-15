#!/usr/bin/env python3
"""
Python 代码生成器
将中间表示 (IR) 转换为 Python 源代码

生成的Python代码使用一种特殊DSL，与Scratch块一一对应：
- 每个Scratch块 -> 一个Python函数调用
- Scratch循环 -> Python for/while循环
- Scratch变量 -> Python变量
- Scratch自制积木 -> Python函数
- Scratch事件 -> 装饰器标记的函数
"""

import math
from typing import Dict, List, Optional, Set
from ir import (
    BlockType, ExprType, Expr, Statement, SpriteIR, ProjectIR,
    sanitize_name, key_to_identifier, set_procedure_name_resolver,
)


class PythonGenerator:
    """将ProjectIR转换为Python源代码"""

    RUNTIME_HELPERS = r'''
_SCRATCH_LIST_LIMIT = 200000
_RUNTIME_VERSION = '0.9.9'


def _sc_is_white(value):
    return value is None or (isinstance(value, str) and value.strip() == '')


def _sc_str(value):
    cls = value.__class__
    if cls is str:
        return value
    if cls is int:
        return str(value)
    if cls is bool:
        return 'true' if value else 'false'
    if value is None:
        return 'null'
    if cls is float:
        if math.isnan(value):
            return 'NaN'
        if math.isinf(value):
            return 'Infinity' if value > 0 else '-Infinity'
        if value == int(value) and abs(value) < 1e21:
            return str(int(value))
        text = repr(value)
        if 'e' in text:
            if 1e-6 <= abs(value) < 1e-4:
                try:
                    return format(decimal.Decimal(text), 'f')
                except Exception:
                    pass
            mantissa, exponent = text.split('e', 1)
            sign = ''
            if exponent[:1] in ('+', '-'):
                sign, exponent = exponent[0], exponent[1:]
            exponent = exponent.lstrip('0') or '0'
            text = mantissa + 'e' + sign + exponent
        return text
    return str(value)


def _sc_num(value):
    cls = value.__class__
    if cls is int:
        return value
    if cls is float:
        return 0 if value != value else value
    if cls is bool:
        return 1 if value else 0
    text = _sc_str(value).strip()
    if text == '':
        return 0
    if '_' in text:
        # JS的Number()不接受Python风格的数字分隔符
        return 0
    if text in ('Infinity', '+Infinity'):
        return math.inf
    if text == '-Infinity':
        return -math.inf
    lowered = text.lower()
    if 'inf' in lowered or 'nan' in lowered:
        return 0
    stripped = text.lstrip('+-')
    if stripped.lower().startswith(('0x', '0o', '0b')):
        if text[:1] in ('+', '-'):
            return 0
        try:
            return int(text, 0)
        except ValueError:
            return 0
    try:
        return float(text)
    except ValueError:
        return 0


def _sc_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return not (value == '' or value == '0' or value.lower() == 'false')
    if isinstance(value, float) and math.isnan(value):
        return False
    return bool(value)


def _sc_number_or_nan(value):
    cls = value.__class__
    if cls is int:
        try:
            return float(value)
        except OverflowError:
            # Scratch 使用双精度，超大整数视为无穷
            return math.inf if value > 0 else -math.inf
    if cls is float:
        return value
    if _sc_is_white(value):
        return math.nan
    if cls is bool:
        return 1.0 if value else 0.0
    text = _sc_str(value).strip()
    if text == '':
        return math.nan
    if '_' in text:
        return math.nan
    if text in ('Infinity', '+Infinity'):
        return math.inf
    if text == '-Infinity':
        return -math.inf
    lowered = text.lower()
    if 'inf' in lowered or 'nan' in lowered:
        return math.nan
    stripped = text.lstrip('+-')
    if stripped.lower().startswith(('0x', '0o', '0b')):
        if text[:1] in ('+', '-'):
            return math.nan
        try:
            return float(int(text, 0))
        except ValueError:
            return math.nan
    try:
        return float(text)
    except ValueError:
        return math.nan


def _sc_compare(a, b):
    na = _sc_number_or_nan(a)
    nb = _sc_number_or_nan(b)
    if math.isnan(na) or math.isnan(nb):
        sa = _sc_str(a).lower()
        sb = _sc_str(b).lower()
        if sa < sb:
            return -1
        if sa > sb:
            return 1
        return 0
    if na == nb:
        return 0
    return -1 if na < nb else 1


def _sc_eq(a, b):
    return _sc_compare(a, b) == 0


def _sc_lt(a, b):
    return _sc_compare(a, b) < 0


def _sc_gt(a, b):
    return _sc_compare(a, b) > 0


def _sc_and(a, b):
    return _sc_bool(a) and _sc_bool(b)


def _sc_or(a, b):
    return _sc_bool(a) or _sc_bool(b)


def _sc_not(a):
    return not _sc_bool(a)


def _sc_add(a, b):
    return _sc_num(a) + _sc_num(b)


def _sc_sub(a, b):
    return _sc_num(a) - _sc_num(b)


def _sc_mul(a, b):
    return _sc_num(a) * _sc_num(b)


def _sc_div(a, b):
    a = _sc_num(a)
    b = _sc_num(b)
    if b == 0:
        if a == 0 or (isinstance(a, float) and math.isnan(a)):
            return math.nan
        return math.inf if a > 0 else -math.inf
    return a / b


def _sc_mod(a, b):
    a = _sc_num(a)
    b = _sc_num(b)
    if b == 0:
        return math.nan
    return a % b


def _sc_round(value):
    value = _sc_num(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return value
    return math.floor(value + 0.5)


def _sc_is_int(value):
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return True
        return value == int(value)
    if isinstance(value, str):
        return '.' not in value
    return False


def _sc_random(a, b):
    low = _sc_num(a)
    high = _sc_num(b)
    if low > high:
        low, high = high, low
    if low == high:
        return low
    if _sc_is_int(a) and _sc_is_int(b):
        return random.randint(int(low), int(high))
    return random.random() * (high - low) + low


def _sc_join(a, b):
    return _sc_str(a) + _sc_str(b)


def _sc_letter_of(index, string):
    # 与 Scratch 一致：先减 1，再用未取整的浮点下标判断越界
    index = _sc_num(index) - 1
    text = _sc_str(string)
    if isinstance(index, float) and not math.isfinite(index):
        return ''
    if index < 0 or index >= len(text):
        return ''
    return text[int(index)]


def _sc_length(string):
    return len(_sc_str(string))


def _sc_contains(string, part):
    return _sc_str(part).lower() in _sc_str(string).lower()


def _sc_mathop(operator, value):
    operator = _sc_str(operator).lower().replace(' ', '')
    number = _sc_num(value)
    try:
        if operator == 'abs':
            return abs(number)
        if operator == 'floor':
            return number if math.isinf(number) or math.isnan(number) else math.floor(number)
        if operator == 'ceiling':
            return number if math.isinf(number) or math.isnan(number) else math.ceil(number)
        if operator == 'sqrt':
            return math.sqrt(number) if number >= 0 else math.nan
        if operator == 'sin':
            return round(math.sin(math.radians(number)), 10)
        if operator == 'cos':
            return round(math.cos(math.radians(number)), 10)
        if operator == 'tan':
            angle = number % 360
            if angle in (90, -270):
                return math.inf
            if angle in (-90, 270):
                return -math.inf
            return round(math.tan(math.radians(angle)), 10)
        if operator == 'asin':
            return math.degrees(math.asin(number)) if -1 <= number <= 1 else math.nan
        if operator == 'acos':
            return math.degrees(math.acos(number)) if -1 <= number <= 1 else math.nan
        if operator == 'atan':
            return math.degrees(math.atan(number))
        if operator == 'ln':
            if number > 0:
                return math.log(number)
            return -math.inf if number == 0 else math.nan
        if operator == 'log':
            if number > 0:
                return math.log10(number)
            return -math.inf if number == 0 else math.nan
        if operator == 'e^':
            try:
                return math.exp(number)
            except OverflowError:
                return math.inf
        if operator == '10^':
            try:
                return math.pow(10, number)
            except OverflowError:
                return math.inf
    except (ValueError, OverflowError):
        return math.nan
    return 0


def _sc_repeat_count(value):
    value = _sc_round(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return 0
    return max(0, int(value))


def _sc_wait_time(value):
    value = _sc_num(value)
    if isinstance(value, float) and not math.isfinite(value):
        return 0
    return max(0, value)


def _sc_parse_int10(value):
    """复刻 JS parseInt(value, 10)：取开头的整数部分，失败返回 None"""
    text = _sc_str(value).lstrip()
    match = re.match(r'[+-]?\d+', text)
    if not match:
        return None
    return int(match.group(0))


def _sc_list_index(index, length, accept_all):
    if index.__class__ is int:
        return index if 1 <= index <= length else None
    if not isinstance(index, (int, float)) or isinstance(index, bool):
        text = _sc_str(index)
        if text == 'all':
            return 'ALL' if accept_all else None
        if text == 'last':
            return length if length > 0 else None
        if text in ('random', 'any'):
            return random.randint(1, length) if length > 0 else None
    number = math.floor(_sc_num(index))
    if number < 1 or number > length:
        return None
    return int(number)


def _sc_item_of(items, index):
    # Scratch允许越界读取，越界时返回空字符串。
    # 同时列表可能被其他脚本并发修改，这里也要避免下标失效。
    try:
        position = _sc_list_index(index, len(items), False)
        if position is None:
            return ''
        return items[position - 1]
    except (IndexError, TypeError, ValueError):
        return ''


def _sc_list_delete(items, index):
    position = _sc_list_index(index, len(items), True)
    if position is None:
        return
    if position == 'ALL':
        items.clear()
        return
    try:
        del items[position - 1]
    except IndexError:
        pass


def _sc_list_insert(items, index, item):
    position = _sc_list_index(index, len(items) + 1, False)
    if position is None or position > _SCRATCH_LIST_LIMIT:
        return
    items.insert(position - 1, item)
    if len(items) > _SCRATCH_LIST_LIMIT:
        items.pop()


def _sc_list_replace(items, index, item):
    position = _sc_list_index(index, len(items), False)
    if position is None:
        return
    try:
        items[position - 1] = item
    except IndexError:
        pass


def _sc_list_contains(items, item):
    if item in items:
        return True
    for existing in items:
        if _sc_compare(existing, item) == 0:
            return True
    return False


def _sc_list_item_number(items, item):
    for position, existing in enumerate(items):
        if _sc_compare(existing, item) == 0:
            return position + 1
    return 0


def _sc_list_contents(items):
    if items and all(isinstance(item, str) and len(item) == 1 for item in items):
        return ''.join(items)
    return ' '.join(_sc_str(item) for item in items)


def _sc_list_values(value):
    """把for-each的列表输入统一成list"""
    if isinstance(value, list):
        return list(value)
    text = _sc_str(value)
    return text.split(' ') if text else []


def _sc_clamp_effect(key, value):
    """按Scratch规则限制图形特效范围"""
    value = _sc_num(value)
    if key == 'color':
        return max(0.0, min(200.0, value))
    if key == 'ghost':
        return max(0.0, min(100.0, value))
    if key == 'brightness':
        return max(-100.0, min(100.0, value))
    return value


def _sc_ident(name, prefix):
    """与ir.sanitize_name一致的运行时标识符清洗"""
    text = re.sub(r'[^\w\u4e00-\u9fff]', '_', _sc_str(name))
    text = re.sub(r'_+', '_', text).strip('_')
    if not text:
        import hashlib
        digest = hashlib.md5(_sc_str(name).encode('utf-8')).hexdigest()[:6]
        text = f"{prefix}_unnamed_{digest}"
    if text[0].isdigit():
        text = prefix + text
    return text


def _sc_color(value, default=(0, 0, 0)):
    """解析Scratch颜色：#rrggbb / rgb(r,g,b) / 十进制"""
    if isinstance(value, (tuple, list)) and len(value) >= 3:
        return tuple(max(0, min(255, int(_sc_num(item)))) for item in value[:3])
    text = _sc_str(value).strip()
    if text.startswith('#'):
        digits = text[1:]
        if len(digits) >= 6:
            try:
                return (int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16))
            except ValueError:
                return default
        return default
    if text.lower().startswith('rgb'):
        body = text[text.find('(') + 1:text.rfind(')')] if '(' in text else ''
        parts = [part for part in body.replace(' ', '').split(',') if part]
        if len(parts) >= 3:
            try:
                return tuple(max(0, min(255, int(float(part)))) for part in parts[:3])
            except ValueError:
                return default
    try:
        number = int(_sc_num(text))
    except (ValueError, TypeError):
        return default
    return ((number >> 16) & 255, (number >> 8) & 255, number & 255)


def _svg_attr(tag, name, default=''):
    match = re.search(r'\b' + name + r'\s*=\s*"([^"]*)"', tag or '')
    return match.group(1) if match else default


def _svg_mul(first, second):
    a1, b1, c1, d1, e1, f1 = first
    a2, b2, c2, d2, e2, f2 = second
    return (a1 * a2 + c1 * b2, b1 * a2 + d1 * b2,
            a1 * c2 + c1 * d2, b1 * c2 + d1 * d2,
            a1 * e2 + c1 * f2 + e1, b1 * e2 + d1 * f2 + f1)


def _svg_point(matrix, x, y):
    a, b, c, d, e, f = matrix
    return (a * x + c * y + e, b * x + d * y + f)


def _svg_transform(text):
    matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    for name, args in re.findall(r'(matrix|translate|scale|rotate)\s*\(([^)]*)\)', text or ''):
        values = [float(item) for item in re.split(r'[ ,]+', args.strip()) if item]
        if name == 'translate':
            step = (1.0, 0.0, 0.0, 1.0,
                    values[0] if values else 0.0,
                    values[1] if len(values) > 1 else 0.0)
        elif name == 'scale':
            sx = values[0] if values else 1.0
            sy = values[1] if len(values) > 1 else sx
            step = (sx, 0.0, 0.0, sy, 0.0, 0.0)
        elif name == 'rotate':
            angle = math.radians(values[0] if values else 0.0)
            cos, sin = math.cos(angle), math.sin(angle)
            step = (cos, sin, -sin, cos, 0.0, 0.0)
            if len(values) >= 3:
                cx, cy = values[1], values[2]
                step = _svg_mul((1.0, 0.0, 0.0, 1.0, cx, cy), step)
                step = _svg_mul(step, (1.0, 0.0, 0.0, 1.0, -cx, -cy))
        else:
            padded = (values + [1.0, 0.0, 0.0, 1.0, 0.0, 0.0])[:6]
            step = tuple(padded)
        # SVG变换列表从右往左作用于坐标，等价于 M = M_prev * step
        matrix = _svg_mul(matrix, step)
    return matrix


def _svg_path_points(data):
    """把SVG path的d属性展平成折线点"""
    tokens = re.findall(r'[MmLlHhVvCcSsQqTtAaZz]|-?\d*\.?\d+(?:[eE][-+]?\d+)?',
                        data or '')
    points = []
    index = 0
    command = 'M'
    current = (0.0, 0.0)
    start = (0.0, 0.0)
    control = None

    def number():
        nonlocal index
        value = float(tokens[index])
        index += 1
        return value

    def line_to(x, y):
        nonlocal current
        current = (x, y)
        points.append(current)

    while index < len(tokens):
        token = tokens[index]
        if token.isalpha():
            command = token
            index += 1
            if command in 'Zz':
                current = start
                points.append(start)
                continue
        relative = command.islower()
        letter = command.upper()
        try:
            if letter == 'M':
                x, y = number(), number()
                if relative:
                    x, y = x + current[0], y + current[1]
                current = start = (x, y)
                points.append(current)
                command = 'l' if relative else 'L'
            elif letter == 'L':
                x, y = number(), number()
                line_to(x + current[0], y + current[1]) if relative else line_to(x, y)
            elif letter == 'H':
                x = number()
                line_to(x + current[0], current[1]) if relative else line_to(x, current[1])
            elif letter == 'V':
                y = number()
                line_to(current[0], y + current[1]) if relative else line_to(current[0], y)
            elif letter in ('C', 'S', 'Q', 'T'):
                if letter == 'C':
                    x1, y1 = number(), number()
                    x2, y2 = number(), number()
                elif letter == 'S':
                    x2, y2 = number(), number()
                    x1, y1 = control if control else current
                elif letter == 'Q':
                    x1, y1 = number(), number()
                    x2 = y2 = None
                else:
                    x2 = y2 = None
                    x1, y1 = control if control else current
                x, y = number(), number()
                end = (x + current[0], y + current[1]) if relative else (x, y)
                if relative:
                    x1, y1 = x1 + current[0], y1 + current[1]
                    if x2 is not None:
                        x2, y2 = x2 + current[0], y2 + current[1]
                if x2 is None:
                    x2, y2 = end
                if letter in ('Q', 'T'):
                    # 二次贝塞尔用三次近似
                    cx1 = current[0] + (x1 - current[0]) * 2 / 3
                    cy1 = current[1] + (y1 - current[1]) * 2 / 3
                    cx2 = end[0] + (x1 - end[0]) * 2 / 3
                    cy2 = end[1] + (y1 - end[1]) * 2 / 3
                    x1, y1, x2, y2 = cx1, cy1, cx2, cy2
                for step in range(1, 11):
                    t = step / 10.0
                    mt = 1 - t
                    px = (mt ** 3 * current[0] + 3 * mt ** 2 * t * x1 +
                          3 * mt * t ** 2 * x2 + t ** 3 * end[0])
                    py = (mt ** 3 * current[1] + 3 * mt ** 2 * t * y1 +
                          3 * mt * t ** 2 * y2 + t ** 3 * end[1])
                    points.append((px, py))
                current = end
                control = (x2, y2)
            elif letter == 'A':
                number(); number(); number(); number(); number()
                x, y = number(), number()
                end = (x + current[0], y + current[1]) if relative else (x, y)
                line_to(*end)
                control = None
            else:
                index += 1
        except (IndexError, ValueError):
            break
    return points


def _svg_color(value, default=None):
    if not value or value == 'none':
        return None
    text = _sc_str(value).strip()
    if text.startswith('#'):
        digits = text[1:]
        try:
            if len(digits) == 3:
                return tuple(int(ch * 2, 16) for ch in digits)
            if len(digits) >= 6:
                return (int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16))
        except ValueError:
            return default
        return default
    if text.startswith('rgb'):
        body = text[text.find('(') + 1:text.rfind(')')] if '(' in text else ''
        parts = [part for part in body.replace(' ', '').split(',') if part]
        if len(parts) >= 3:
            try:
                return tuple(max(0, min(255, int(float(part)))) for part in parts[:3])
            except ValueError:
                return default
    named = {
        'white': (255, 255, 255), 'black': (0, 0, 0), 'red': (255, 0, 0),
        'green': (0, 128, 0), 'blue': (0, 0, 255), 'yellow': (255, 255, 0),
        'gray': (128, 128, 128), 'grey': (128, 128, 128),
    }
    return named.get(text.lower(), default)


def _svg_resolve_paint(value, gradients):
    """解析fill/stroke，支持 url(#gradientId)"""
    if isinstance(value, str) and value.startswith('url('):
        start = value.find('#')
        end = value.find(')', start + 1)
        if start >= 0 and end > start:
            return gradients.get(value[start + 1:end])
        return None
    return _svg_color(value)


class _ScriptContext:
    def __init__(self):
        self.running = True
        self.sprite = None


class _ProcedureReturn(Exception):
    """在自制积木内执行“停止这个脚本”时，只返回上一层调用"""
    pass


def _as_procedure(func=None, *, warp=False, **meta):
    def decorate(fn):
        def wrapper(self, *args, **kwargs):
            runtime = getattr(self, "_runtime", None)
            tracing = runtime is not None and getattr(runtime, "trace", False)
            if tracing:
                print("[trace] call", fn.__name__)
            self._enter_procedure(warp)
            try:
                return fn(self, *args, **kwargs)
            except _ProcedureReturn:
                return None
            finally:
                self._leave_procedure(warp)
                if tracing:
                    print("[trace] return", fn.__name__)

        wrapper.__name__ = fn.__name__
        wrapper.__doc__ = fn.__doc__
        wrapper.scratch_meta = dict(meta, warp=warp)
        return wrapper

    return decorate(func) if func is not None else decorate
'''

    RUNTIME_EXTENSIONS = r'''
def _ext_input(inputs, fields, *names, default=None):
    """从扩展积木的inputs/fields里按名字取值（忽略大小写）"""
    for source in (inputs or {}, fields or {}):
        for name in names:
            if name in source:
                return source[name]
    lowered = {}
    for source in (inputs or {}, fields or {}):
        for key, value in source.items():
            lowered[str(key).lower()] = value
    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return default


def _ext_bool(value):
    """TurboWarp菜单开关值：on/off、true/false、1/0"""
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ('off', 'false', 'no', 'disabled', '0', ''):
            return False
        if text in ('on', 'true', 'yes', 'enabled', '1'):
            return True
    return _sc_bool(value)


def _ext_color(value):
    """解析扩展颜色输入：'#rrggbb' / 'rgb(r,g,b)' / 整数"""
    if isinstance(value, (tuple, list)) and len(value) >= 3:
        return tuple(max(0, min(255, int(_sc_num(item)))) for item in value[:3])
    text = _sc_str(value).strip()
    if text.startswith('#'):
        digits = text[1:]
        if len(digits) >= 6:
            try:
                return (int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16))
            except ValueError:
                return (0, 0, 255)
        return (0, 0, 255)
    if text.lower().startswith('rgb'):
        body = text[text.find('(') + 1:text.rfind(')')] if '(' in text else ''
        parts = [part for part in body.replace(' ', '').split(',') if part]
        if len(parts) >= 3:
            try:
                return tuple(max(0, min(255, int(float(part)))) for part in parts[:3])
            except ValueError:
                return (0, 0, 255)
    number = int(_sc_num(text))
    return ((number >> 16) & 255, (number >> 8) & 255, number & 255)


def _hsv_to_rgb(hue, saturation, brightness):
    hue = (_sc_num(hue) % 100) * 3.6
    saturation = max(0.0, min(1.0, _sc_num(saturation) / 100.0))
    brightness = max(0.0, min(1.0, _sc_num(brightness) / 100.0))
    chroma = brightness * saturation
    second = chroma * (1 - abs((hue / 60.0) % 2 - 1))
    offset = brightness - chroma
    if hue < 60:
        red, green, blue = chroma, second, 0.0
    elif hue < 120:
        red, green, blue = second, chroma, 0.0
    elif hue < 180:
        red, green, blue = 0.0, chroma, second
    elif hue < 240:
        red, green, blue = 0.0, second, chroma
    elif hue < 300:
        red, green, blue = second, 0.0, chroma
    else:
        red, green, blue = chroma, 0.0, second
    return (int((red + offset) * 255), int((green + offset) * 255), int((blue + offset) * 255))


def _rgb_to_hsv(red, green, blue):
    red, green, blue = red / 255.0, green / 255.0, blue / 255.0
    maximum = max(red, green, blue)
    minimum = min(red, green, blue)
    delta = maximum - minimum
    if delta == 0:
        hue = 0.0
    elif maximum == red:
        hue = 60 * (((green - blue) / delta) % 6)
    elif maximum == green:
        hue = 60 * ((blue - red) / delta + 2)
    else:
        hue = 60 * ((red - green) / delta + 4)
    saturation = 0.0 if maximum == 0 else delta / maximum
    return [hue / 3.6, saturation * 100.0, maximum * 100.0]


def _set_pen_param(sprite, param, value, absolute):
    hsv = list(getattr(sprite, '_pen_hsv', [0.0, 100.0, 100.0]))
    if param in ('color', 'colour', 'hue'):
        hsv[0] = value % 100 if absolute else (hsv[0] + value) % 100
    elif param in ('saturation', 'sat'):
        hsv[1] = max(0.0, min(100.0, value if absolute else hsv[1] + value))
    elif param in ('brightness', 'shade', 'value', 'lightness'):
        hsv[2] = max(0.0, min(100.0, value if absolute else hsv[2] + value))
    elif param in ('transparency', 'alpha', 'opacity'):
        current = _sc_num(getattr(sprite, '_pen_alpha', 0))
        alpha = value if absolute else current + value
        sprite._pen_alpha = max(0.0, min(100.0, alpha))
    else:
        hsv[0] = (hsv[0] + value) % 100 if not absolute else value % 100
    sprite._pen_hsv = hsv


def _extension_pen(runtime, sprite, opcode, inputs, fields):
    """pen扩展：画笔"""
    key = str(opcode).lower().replace('_', '')
    if key.endswith('penclear'):
        runtime.pen_clear()
    elif key.endswith('stamp'):
        runtime.pen_stamp(sprite)
    elif key.endswith('pendown'):
        sprite._pen_down = True
        sprite._pen_last = (float(_sc_num(sprite.x)), float(_sc_num(sprite.y)))
    elif key.endswith('penup'):
        sprite._pen_down = False
        sprite._pen_last = None
    elif key.endswith('pencolortocolor'):
        color = _ext_input(inputs, fields, 'COLOR', 'color', default='#0000ff')
        red, green, blue = _ext_color(color)
        sprite._pen_hsv = _rgb_to_hsv(red, green, blue)
    elif key.endswith('pencolorparamby') or key.endswith('pencolorparamto'):
        param = _ext_input(inputs, fields, 'COLOR_PARAM', 'colorParam', 'COLOR', default='color')
        value = _sc_num(_ext_input(inputs, fields, 'VALUE', 'value', default=0))
        _set_pen_param(sprite, _sc_str(param).lower(), value,
                       key.endswith('pencolorparamto'))
    elif key.endswith('penhueby') or key.endswith('penhuetonumber'):
        value = _sc_num(_ext_input(inputs, fields, 'VALUE', 'value', default=0))
        _set_pen_param(sprite, 'color', value, key.endswith('penhuetonumber'))
    elif key.endswith('penhue'):
        value = _sc_num(_ext_input(inputs, fields, 'HUE', 'value', default=0))
        sprite._pen_hsv = [value % 100, getattr(sprite, '_pen_hsv', [0, 100, 100])[1],
                           getattr(sprite, '_pen_hsv', [0, 100, 100])[2]]
    elif key.endswith('penshadeby') or key.endswith('penshadetonumber'):
        value = _sc_num(_ext_input(inputs, fields, 'VALUE', 'value', default=0))
        _set_pen_param(sprite, 'brightness', value, key.endswith('penshadetonumber'))
    elif key.endswith('pensizeby'):
        value = _sc_num(_ext_input(inputs, fields, 'SIZE', 'size', 'VALUE', default=1))
        sprite._pen_size = max(1.0, _sc_num(getattr(sprite, '_pen_size', 1)) + value)
    elif key.endswith('pensizeto'):
        value = _sc_num(_ext_input(inputs, fields, 'SIZE', 'size', 'VALUE', default=1))
        sprite._pen_size = max(1.0, value)
    return 0


def _extension_runtimeoptions(runtime, sprite, opcode, inputs, fields):
    """TurboWarp Runtime Options扩展"""
    key = str(opcode).lower().replace('_', '')
    value = _ext_input(inputs, fields, 'VALUE', 'value', 'STATE', 'state', default=None)
    if 'framerate' in key or 'fps' in key:
        runtime.set_framerate(int(_sc_num(value)))
    elif 'interpolation' in key:
        runtime.interpolation = _ext_bool(value)
    elif 'turbo' in key:
        runtime.turbo = _ext_bool(value)
    elif 'compiler' in key:
        runtime.disable_compiler = not _ext_bool(value)
    elif 'fencing' in key:
        runtime.fencing = _ext_bool(value)
    elif 'infiniteclone' in key:
        runtime.clone_limit = None
    elif 'clone' in key:
        number = int(_sc_num(value))
        runtime.clone_limit = None if number < 0 else number
    elif 'misc' in key or 'limit' in key:
        runtime.misc_limits = _ext_bool(value)
    elif 'stagewidth' in key:
        runtime.resize_stage(int(_sc_num(value)), runtime.stage_height)
    elif 'stageheight' in key:
        runtime.resize_stage(runtime.stage_width, int(_sc_num(value)))
    elif 'stagesize' in key:
        width = _ext_input(inputs, fields, 'WIDTH', 'w', default=runtime.stage_width)
        height = _ext_input(inputs, fields, 'HEIGHT', 'h', default=runtime.stage_height)
        runtime.resize_stage(int(_sc_num(width)), int(_sc_num(height)))
    return 0


def _extension_music(runtime, sprite, opcode, inputs, fields):
    """music扩展：音符/鼓点/节拍/速度"""
    key = str(opcode).lower().replace('_', '')
    if 'gettempo' in key:
        return runtime.music_tempo
    if 'settempo' in key:
        value = _sc_num(_ext_input(inputs, fields, 'TEMPO', 'tempo', default=60))
        runtime.music_tempo = max(20.0, min(500.0, value))
        return 0
    if 'changetempo' in key:
        value = _sc_num(_ext_input(inputs, fields, 'TEMPO', 'tempo', default=0))
        runtime.music_tempo = max(20.0, min(500.0, runtime.music_tempo + value))
        return 0
    if 'setinstrument' in key:
        runtime.music_instrument = int(_sc_num(
            _ext_input(inputs, fields, 'INSTRUMENT', 'instrument', default=1)))
        return 0
    if 'restforbeats' in key:
        runtime.music_wait(sprite, _sc_num(_ext_input(inputs, fields, 'BEATS', 'beats', default=0.25)))
        return 0
    if 'playdrum' in key:
        drum = int(_sc_num(_ext_input(inputs, fields, 'DRUM', 'drum', default=1)))
        beats = _sc_num(_ext_input(inputs, fields, 'BEATS', 'beats', default=0.25))
        runtime.music_play_drum(sprite, drum, beats)
        return 0
    if 'playnote' in key:
        note = _sc_num(_ext_input(inputs, fields, 'NOTE', 'note', default=60))
        beats = _sc_num(_ext_input(inputs, fields, 'BEATS', 'beats', default=0.5))
        runtime.music_play_note(sprite, note, beats)
        return 0
    return 0
'''

    RUNTIME_CLASS = r'''class ScratchRuntime:
    """Scratch 3.0 / TurboWarp pygame运行时。

    通过 ScratchRuntime.register_extension(name, handler) 注册扩展，
    扩展handler签名为 handler(runtime, sprite, opcode, inputs, fields)。
    内置 pen 与 runtimeoptions 两个TurboWarp扩展。
    """

    EXTENSIONS = {}
    FPS = 30
    STAGE_WIDTH = 480
    STAGE_HEIGHT = 360

    def __init__(self, headless=False, fps=None, trace=False, audio=True,
                 assets_dir=None, interpolation=False, turbo=False,
                 fencing=True, infinite_clones=False, misc_limits=True,
                 hq_pen=False, stage_size=None, warp_timer=0.5,
                 disable_compiler=False, maximize=True):
        if pygame is None:
            raise RuntimeError("运行生成的脚本需要pygame: pip install pygame")
        self.headless = headless
        self.maximize = maximize
        self.fps = fps or self.FPS
        self.trace = trace
        self.assets_dir = assets_dir or ASSETS_DIR
        self.interpolation = interpolation
        self.turbo = turbo
        self.fencing = fencing
        self.infinite_clones = infinite_clones
        self.clone_limit = None if infinite_clones else 300
        self.misc_limits = misc_limits
        self.hq_pen = hq_pen
        self.warp_timer = warp_timer
        self.disable_compiler = disable_compiler
        if stage_size:
            self.stage_width, self.stage_height = int(stage_size[0]), int(stage_size[1])
        else:
            self.stage_width, self.stage_height = self.STAGE_WIDTH, self.STAGE_HEIGHT
        if headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.display.init()
        pygame.font.init()
        self._create_display(maximize=self.maximize)
        pygame.display.set_caption(
            "Scratch 3.0 Runtime " + _RUNTIME_VERSION
            + " (ESC 退出，F1 调试信息，可自由拉伸窗口)")
        if not self.headless:
            print("[runtime] Scratch 3 运行时 v" + _RUNTIME_VERSION
                  + "，按 F1 显示/隐藏调试面板")
        self.pen_layer = pygame.Surface((self.stage_width, self.stage_height),
                                        pygame.SRCALPHA)
        self.clock = pygame.time.Clock()
        self.sprites = []
        self.scripts = []
        self.turn_lock = threading.Lock()
        self.running = True
        self.frame = 0
        self.frame_condition = threading.Condition()
        self.start_time = time.time()
        self.timer_offset = 0.0
        # “2000年以来的天数”按本地时间计算，与Scratch一致
        self.epoch_2000 = time.mktime((2000, 1, 1, 0, 0, 0, 0, 0, -1))
        self.keys = set()
        self.mouse_down = False
        self.mouse_x = 0
        self.mouse_y = 0
        self.current_backdrop = 0
        self.stage_sprite = None
        self.counter = 0
        self.dragging = None
        self.dragging_offset = (0, 0)
        self.ask_pending = False
        self.ask_visible = False
        self.ask_question = ''
        self.ask_buffer = ''
        self.ask_composition = ''
        self.ask_key_pending = ''
        self.ask_answer = ''
        self.ask_token = 0
        self.ask_lock = threading.Lock()
        self.debug_overlay = False
        self._debug_events = []
        # pygame 2 起文本输入走 TEXTINPUT（支持中文输入法），不再用 KEYDOWN.unicode
        self._has_text_input = hasattr(pygame, 'TEXTINPUT')
        self.answer = ''
        self.music_tempo = 60.0
        self.music_instrument = 1
        self.music_cache = {}
        self.dynamic_monitors = []
        self.mask_cache = {}
        font_path = None
        for filename in ("msyh.ttc", "simhei.ttf", "arial.ttf"):
            candidate = os.path.join(os.environ.get("WINDIR", "C:\Windows"),
                                     "Fonts", filename)
            if os.path.exists(candidate):
                font_path = candidate
                break
        self.font = pygame.font.Font(font_path, 14) if font_path else pygame.font.Font(None, 14)
        self.font_path = font_path
        self.costume_cache = {}
        self.sound_cache = {}
        self.mixer_ready = False
        if audio:
            try:
                pygame.mixer.init()
                self.mixer_ready = True
            except Exception:
                pass
        self.background = self._load_image(STAGE_COSTUME) if STAGE_COSTUME else None
        if self.background is not None:
            self.background = pygame.transform.smoothscale(
                self.background, (self.stage_width, self.stage_height))
        # 内置TurboWarp扩展
        self.register_extension('pen', _extension_pen)
        self.register_extension('runtimeoptions', _extension_runtimeoptions)
        self.register_extension('runtime-options', _extension_runtimeoptions)
        self.register_extension('turbowarp', _extension_runtimeoptions)
        self.register_extension('tw', _extension_runtimeoptions)
        self.register_extension('music', _extension_music)

    @classmethod
    def register_extension(cls, name, handler):
        cls.EXTENSIONS[name] = handler

    def call_extension(self, sprite, namespace, opcode, inputs=None, fields=None):
        handler = self.EXTENSIONS.get(namespace)
        if handler is None:
            return 0
        return handler(self, sprite, opcode, inputs or {}, fields or {})

    def set_framerate(self, fps):
        self.fps = max(1, min(250, int(fps))) if fps else 0

    def _create_display(self, maximize=False):
        """创建可自由拉伸的窗口，启动时最大化，舞台按宽高比缩放到最大可用区域。

        不使用 pygame.SCALED：在高DPI屏幕上 SCALED 可能只按固定整数倍放大，
        导致舞台只占窗口一部分。这里始终把逻辑舞台软件缩放到窗口实际像素，
        保证最大化后一定填满可用区域（保留宽高比，多余部分补黑边）。
        """
        width, height = self.stage_width, self.stage_height
        self._scaled_view = False
        self._manual_view = False
        self.view_scale = 1.0
        self.view_offset = (0, 0)
        self._view_size = None
        self._view_scaled = None
        if self.headless:
            self.toolbar_height = 0
            self.screen = pygame.display.set_mode((width, height))
            self.stage_surface = self.screen
            return
        # 窗口顶部留一条工具栏放绿旗（类似 Scratch），舞台在工具栏下方缩放
        self.toolbar_height = 34
        try:
            self.screen = pygame.display.set_mode(
                (width, height + self.toolbar_height), pygame.RESIZABLE)
        except pygame.error:
            self.screen = pygame.display.set_mode(
                (width, height + self.toolbar_height))
        self.stage_surface = pygame.Surface((width, height))
        self._manual_view = True
        if maximize:
            self._maximize_window()

    def _maximize_window(self):
        """把窗口最大化到桌面可用区域（类似 Scratch 舞台放大到最大）"""
        try:
            if os.name == 'nt':
                import ctypes
                hwnd = pygame.display.get_wm_info().get('window')
                if hwnd:
                    ctypes.windll.user32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE
                    return
            maximize = getattr(pygame.display, 'maximize', None)
            if maximize is not None:
                maximize()
        except Exception:
            pass

    def _view_geometry(self):
        """返回 (缩放比, 黑边偏移, 绘制尺寸)；工具栏占用的高度不计入舞台区域"""
        window_width, window_height = self.screen.get_size()
        toolbar = getattr(self, 'toolbar_height', 0)
        if window_width <= 0 or window_height <= 0:
            return 1.0, (0, toolbar), (self.stage_width, self.stage_height)
        available = max(1, window_height - toolbar)
        scale = min(window_width / float(self.stage_width),
                    available / float(self.stage_height))
        draw_width = max(1, int(self.stage_width * scale))
        draw_height = max(1, int(self.stage_height * scale))
        return (draw_width / float(self.stage_width),
                ((window_width - draw_width) // 2,
                 toolbar + (available - draw_height) // 2),
                (draw_width, draw_height))

    def _window_to_stage(self, pos):
        """窗口坐标 -> 舞台逻辑坐标（窗口缩放/最大化后仍能正确点击）"""
        if not self._manual_view:
            return pos
        scale, offset, _size = self._view_geometry()
        return ((pos[0] - offset[0]) / scale, (pos[1] - offset[1]) / scale)

    def _present(self):
        """把逻辑舞台呈现到窗口；按宽高比居中放大到窗口最大可用区域"""
        if self._manual_view:
            scale, offset, (draw_width, draw_height) = self._view_geometry()
            self.view_scale = scale
            self.view_offset = offset
            window_width, window_height = self.screen.get_size()
            if window_width <= 0 or window_height <= 0:
                return
            if self._view_scaled is None or self._view_size != (draw_width, draw_height):
                self._view_size = (draw_width, draw_height)
                self._view_scaled = pygame.Surface((draw_width, draw_height)).convert()
            if self._view_size == (self.stage_width, self.stage_height):
                self._view_scaled.blit(self.stage_surface, (0, 0))
            else:
                pygame.transform.smoothscale(self.stage_surface,
                                             (draw_width, draw_height),
                                             self._view_scaled)
            self.screen.fill((0, 0, 0))
            self.screen.blit(self._view_scaled, offset)
            self._draw_toolbar()
        pygame.display.flip()

    def _green_flag_rect(self):
        """绿旗按钮在窗口中的位置（位于顶部工具栏内）"""
        return pygame.Rect(8, 6, 22, 22)

    def _draw_toolbar(self):
        """窗口顶部工具栏：只放绿旗按钮，避免和舞台内容重叠"""
        toolbar = getattr(self, 'toolbar_height', 0)
        if toolbar <= 0:
            return
        width = self.screen.get_width()
        pygame.draw.rect(self.screen, (245, 245, 245), (0, 0, width, toolbar))
        pygame.draw.line(self.screen, (200, 200, 200),
                         (0, toolbar - 1), (width, toolbar - 1))
        flag = self._green_flag_rect()
        pygame.draw.rect(self.screen, (255, 255, 255),
                         flag.inflate(4, 4), border_radius=5)
        pygame.draw.polygon(self.screen, (60, 170, 90), [
            (flag.x + 4, flag.bottom - 3), (flag.x + 4, flag.y + 2),
            (flag.right - 2, flag.y + 2), (flag.right - 2, flag.centery),
            (flag.x + 4, flag.centery)])

    def resize_stage(self, width, height):
        width = max(1, int(width))
        height = max(1, int(height))
        if width == self.stage_width and height == self.stage_height:
            return
        self.stage_width, self.stage_height = width, height
        self.pen_layer = pygame.Surface((width, height), pygame.SRCALPHA)
        if self.background is not None:
            self.background = pygame.transform.smoothscale(self.background, (width, height))
        self._create_display(maximize=self.maximize)

    def pen_clear(self):
        self.pen_layer.fill((0, 0, 0, 0))

    def pen_draw_segment(self, start, end, color, size):
        size = max(1, int(size))
        sx = int(self.stage_width / 2 + start[0])
        sy = int(self.stage_height / 2 - start[1])
        ex = int(self.stage_width / 2 + end[0])
        ey = int(self.stage_height / 2 - end[1])
        pygame.draw.line(self.pen_layer, color, (sx, sy), (ex, ey), size)
        if size > 1:
            radius = size // 2
            pygame.draw.circle(self.pen_layer, color, (sx, sy), radius)
            pygame.draw.circle(self.pen_layer, color, (ex, ey), radius)
        if self.hq_pen:
            pygame.draw.aaline(self.pen_layer, color, (sx, sy), (ex, ey))

    def pen_stamp(self, sprite):
        # 图章使用角色当前外观：颜色/亮度/透明度/形状特效都会一起盖上去
        transformed, rect, x, y, scale, _direction = sprite._rendered_image()
        if transformed is not None:
            self.pen_layer.blit(transformed, rect)
        else:
            pygame.draw.circle(self.pen_layer, sprite._placeholder_color(),
                               (x, y), max(6, int(20 * scale)))

    def add_sprite(self, sprite):
        sprite._runtime = self
        self.sprites.append(sprite)
        if getattr(sprite, 'is_stage', False):
            self.stage_sprite = sprite

    def remove_sprite(self, sprite):
        if sprite in self.sprites:
            self.sprites.remove(sprite)

    def find_sprite(self, name):
        """按名字找角色，优先返回本体（原版Scratch的sensing/运动积木都基于本体）"""
        fallback = None
        for sprite in self.sprites:
            if sprite.name != name:
                continue
            if not getattr(sprite, '_is_clone', False):
                return sprite
            if fallback is None:
                fallback = sprite
        return fallback

    def elapsed(self):
        return max(0.0, time.time() - self.start_time - self.timer_offset)

    def reset_timer(self):
        self.timer_offset = time.time() - self.start_time

    def green_flag(self):
        self.running = True
        self.start_time = time.time()
        self.timer_offset = 0.0
        self.answer = ''
        if self.trace:
            print("[trace] green flag")
        # 绿旗会删除所有克隆体，并重启动原有脚本
        for sprite in list(self.sprites):
            if getattr(sprite, "_is_clone", False):
                self.sprites.remove(sprite)
        self.stop_all_scripts()
        self.stop_sounds()
        for sprite in list(self.sprites):
            # 绿旗会清空音效，但保留图形特效与造型
            sprite._sound_effects = {'pitch': 0.0, 'pan': 0.0}
        time.sleep(0.02)
        for sprite in list(self.sprites):
            sprite._global_running = True
            for func in list(sprite._handlers.get("green_flag", [])):
                self.start_script(func)

    def start_script(self, func):
        sprite = getattr(func, "__self__", None)
        context = _ScriptContext()
        context.sprite = sprite
        self.scripts.append(context)

        def runner():
            # threading.local 必须在线程内部赋值，否则主线程的context会串到脚本线程
            if sprite is not None:
                sprite._local.context = context
                sprite._local.turn_owned = False
                sprite._turn_acquire()
            name = getattr(sprite, "name", getattr(func, "__name__", "script"))
            if self.trace:
                print("[trace] start", name, getattr(func, "__name__", ""))
            try:
                func()
            except StopIteration:
                pass
            except Exception:
                import traceback
                traceback.print_exc()
            finally:
                if sprite is not None:
                    sprite._turn_release()
                if context in self.scripts:
                    self.scripts.remove(context)
                if sprite is not None and getattr(sprite._local, "context", None) is context:
                    sprite._local.context = None
                if self.trace:
                    print("[trace] finish", name)

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        return thread

    def wait_frame(self, context=None):
        with self.frame_condition:
            current = self.frame
            while (self.running and self.frame == current and
                   (context is None or context.running)):
                self.frame_condition.wait(0.1)

    def ask(self, question, context=None):
        """在舞台上显示输入框并等待玩家输入

        同一时刻只允许一个询问：多个脚本同时询问时排队执行，
        避免后者清空前者的输入状态，导致输入框“卡住”。
        """
        def alive():
            return self.running and (context is None or context.running)

        # 抢询问锁；脚本被停止时也能退出等待
        while alive():
            if self.ask_lock.acquire(timeout=0.1):
                break
        else:
            return ''
        token = 0
        try:
            if not alive():
                return ''
            self.ask_token += 1
            token = self.ask_token
            self.ask_question = _sc_str(question)
            self.ask_buffer = ''
            self.ask_composition = ''
            self.ask_key_pending = ''
            self.ask_answer = ''
            self.ask_visible = True
            self.ask_pending = True
            if self.trace:
                print("[trace] ask", repr(self.ask_question))
            while alive() and self.ask_pending and self.ask_token == token:
                self.wait_frame()
            return self.ask_answer
        finally:
            if token and self.ask_token == token:
                self.ask_pending = False
                self.ask_visible = False
                self.ask_question = ''
                self.ask_composition = ''
                if self.trace:
                    print("[trace] ask done", repr(self.ask_answer))
            self.ask_lock.release()

    def _ask_rect(self):
        return pygame.Rect(20, self.stage_height - 60,
                           max(80, self.stage_width - 40), 40)

    def _ask_button_rect(self):
        rect = self._ask_rect()
        return pygame.Rect(rect.right - 66, rect.y + 7, 58, 26)

    def _ask_append_text(self, text):
        """TEXTINPUT 兜底：KEYDOWN 已经加入过的字符不重复添加"""
        pending = self.ask_key_pending
        for ch in text:
            if pending.startswith(ch):
                pending = pending[1:]
            else:
                self.ask_buffer += ch
        self.ask_key_pending = pending

    def _submit_ask(self):
        """回车/点击确认时提交输入"""
        self.ask_answer = self.ask_buffer + self.ask_composition
        self.ask_key_pending = ''
        self.ask_pending = False
        # 点击确认/回车后立刻停止渲染询问框，不等脚本线程调度
        self.ask_visible = False
        if self.trace:
            print("[trace] ask submit", repr(self.ask_answer))

    def _draw_ask(self):
        if not self.ask_visible or not self.ask_pending:
            return
        rect = self._ask_rect()
        pygame.draw.rect(self.stage_surface, (255, 255, 255), rect, border_radius=6)
        pygame.draw.rect(self.stage_surface, (90, 90, 90), rect, 1, border_radius=6)
        text = self.ask_question + ' ' + self.ask_buffer + self.ask_composition + '_'
        surface = self.font.render(text, True, (30, 30, 30))
        area_width = max(20, rect.width - 90)
        if surface.get_width() > area_width:
            # 文字太长时只显示末尾（当前输入的内容）
            clipped = pygame.Surface((area_width, rect.height - 8), pygame.SRCALPHA)
            clipped.blit(surface, (area_width - surface.get_width(), 0))
            surface = clipped
        self.stage_surface.blit(surface, (rect.x + 8, rect.y + 11))
        button = self._ask_button_rect()
        pygame.draw.rect(self.stage_surface, (80, 135, 220), button, border_radius=5)
        label = self.font.render('确认', True, (255, 255, 255))
        self.stage_surface.blit(label, label.get_rect(center=button.center))

    def stop_all_scripts(self):
        for context in list(self.scripts):
            context.running = False
        for sprite in self.sprites:
            sprite._global_running = False
        with self.frame_condition:
            self.frame_condition.notify_all()

    def stop_other_scripts(self, sprite):
        current = getattr(sprite._local, "context", None)
        for context in list(self.scripts):
            if context.sprite is sprite and context is not current:
                context.running = False
        with self.frame_condition:
            self.frame_condition.notify_all()

    def broadcast(self, message):
        message = _sc_str(message)
        if self.trace:
            print("[trace] broadcast", message)
        threads = []
        for sprite in list(self.sprites):
            sprite._running = True
            for func in list(sprite._handlers.get("broadcast:" + message, [])):
                threads.append(self.start_script(func))
        return threads

    def broadcast_and_wait(self, message, context=None):
        for thread in self.broadcast(message):
            while (thread.is_alive() and self.running and
                   (context is None or context.running)):
                self.wait_frame(context)

    def _key_name(self, key):
        names = {
            pygame.K_SPACE: "space", pygame.K_RETURN: "enter",
            pygame.K_UP: "up arrow", pygame.K_DOWN: "down arrow",
            pygame.K_LEFT: "left arrow", pygame.K_RIGHT: "right arrow",
            pygame.K_BACKSPACE: "backspace", pygame.K_TAB: "tab",
        }
        if key in names:
            return names[key]
        name = pygame.key.name(key)
        if len(name) == 1:
            return name.lower()
        return name

    def _screen_to_scratch(self, pos):
        """窗口坐标 -> 舞台坐标；超出舞台范围时取边界值（与 Scratch 一致）"""
        x, y = self._window_to_stage(pos)
        scratch_x = int(round(x)) - self.stage_width // 2
        scratch_y = self.stage_height // 2 - int(round(y))
        limit_x = self.stage_width // 2
        limit_y = self.stage_height // 2
        return (max(-limit_x, min(limit_x, scratch_x)),
                max(-limit_y, min(limit_y, scratch_y)))

    def music_seconds(self, beats):
        tempo = _sc_num(self.music_tempo) or 60.0
        return max(0.0, _sc_num(beats)) * 60.0 / max(20.0, tempo)

    def music_tone(self, frequency, seconds):
        if not self.mixer_ready or seconds <= 0:
            return None
        key = (round(frequency, 2), round(seconds, 3))
        cached = self.music_cache.get(key)
        if cached is not None:
            return cached
        info = pygame.mixer.get_init()
        if not info:
            return None
        rate, _size, channels = info
        count = max(1, int(rate * seconds))
        samples = array.array('h')
        amplitude = 11000
        for index in range(count):
            moment = index / float(rate)
            envelope = min(1.0, moment * 80) * min(1.0, (seconds - moment) * 40)
            value = int(math.sin(2 * math.pi * frequency * moment) *
                        amplitude * max(0.0, envelope))
            for _channel in range(channels or 1):
                samples.append(value)
        try:
            sound = pygame.mixer.Sound(buffer=samples.tobytes())
        except Exception:
            return None
        if len(self.music_cache) > 96:
            self.music_cache.clear()
        self.music_cache[key] = sound
        return sound

    def music_play_note(self, sprite, note, beats):
        seconds = self.music_seconds(beats)
        frequency = 440.0 * (2 ** ((_sc_num(note) - 69) / 12.0))
        if self.mixer_ready:
            sound = self.music_tone(frequency, seconds)
            if sound is not None:
                sound.play()
        if seconds > 0:
            self._coop_sleep(sprite, seconds)

    def music_play_drum(self, sprite, drum, beats):
        seconds = self.music_seconds(beats)
        if self.mixer_ready:
            frequencies = {1: 261.63, 2: 196.0, 3: 130.81, 4: 523.25}
            sound = self.music_tone(frequencies.get(int(drum), 220.0),
                                    min(0.3, max(0.06, seconds)))
            if sound is not None:
                sound.play()
        if seconds > 0:
            self._coop_sleep(sprite, seconds)

    def music_wait(self, sprite, beats):
        seconds = self.music_seconds(beats)
        if seconds > 0:
            self._coop_sleep(sprite, seconds)

    def _coop_sleep(self, sprite, seconds):
        if sprite is None:
            time.sleep(seconds)
            return
        sprite._turn_release()
        try:
            time.sleep(seconds)
        finally:
            sprite._turn_acquire()

    def _start_drag(self, pos):
        """按下鼠标时，找到可拖动的角色开始拖动"""
        x, y = self._screen_to_scratch(pos)
        for sprite in reversed(list(self.sprites)):
            if not getattr(sprite, 'draggable', False) or not sprite.visible:
                continue
            if sprite._contains_point(x, y):
                self.dragging = sprite
                self.dragging_offset = (_sc_num(sprite.x) - x,
                                        _sc_num(sprite.y) - y)
                return

    def _handle_click(self, pos):
        if self.trace:
            print("[trace] click", pos)
        if self._green_flag_rect().collidepoint(pos):
            # 绿旗在窗口顶部工具栏里，用窗口坐标判断
            self.green_flag()
            return
        stage_pos = self._window_to_stage(pos)
        x, y = self._screen_to_scratch(pos)
        for sprite in reversed(list(self.sprites)):
            if not sprite.visible:
                continue
            if sprite._contains_point(x, y):
                for func in list(sprite._handlers.get("clicked", [])):
                    sprite._running = True
                    self.start_script(func)
                return

    def step(self):
        if not self.running or pygame is None:
            return
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F1:
                self.debug_overlay = not self.debug_overlay
                self._debug_events = []
                continue
            self._log_event(event)
            if event.type == pygame.QUIT:
                self.running = False
                return
            elif self._has_text_input and event.type == pygame.TEXTINPUT:
                # pygame 2 的文本输入（含中文输入法提交的文本）；
                # 部分环境只发 KEYDOWN，不去重会重复输入
                if self.ask_pending:
                    if self.trace:
                        print("[trace] ask text", repr(event.text))
                    self._ask_append_text(event.text)
                    self.ask_composition = ''
            elif self._has_text_input and event.type == pygame.TEXTEDITING:
                # 输入法正在拼写的文本，先显示出来但不计入答案
                if self.ask_pending:
                    if self.trace:
                        print("[trace] ask editing", repr(event.text))
                    self.ask_composition = event.text
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                    return
                if self.ask_pending:
                    if self.trace:
                        print("[trace] ask key", event.key,
                              repr(getattr(event, "unicode", "")))
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        self._submit_ask()
                    elif event.key == pygame.K_BACKSPACE:
                        if self.ask_composition:
                            self.ask_composition = self.ask_composition[:-1]
                        else:
                            self.ask_buffer = self.ask_buffer[:-1]
                        self.ask_key_pending = ''
                    elif event.unicode and event.unicode.isprintable():
                        # 始终接受 KEYDOWN 文本：有些环境不会发 TEXTINPUT
                        self.ask_buffer += event.unicode
                        if self._has_text_input:
                            self.ask_key_pending += event.unicode
                    continue
                key = self._key_name(event.key)
                if key:
                    if self.trace:
                        print("[trace] key", key)
                    self.keys.add(key)
                    for sprite in list(self.sprites):
                        handlers = list(sprite._handlers.get("key:" + key, []))
                        handlers += list(sprite._handlers.get("key:any", []))
                        for func in handlers:
                            sprite._running = True
                            self.start_script(func)
            elif event.type == pygame.KEYUP:
                if self.ask_pending and \
                        event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    # 输入法可能吞掉 KEYDOWN，回车松开时再兜底提交
                    self._submit_ask()
                    continue
                self.keys.discard(self._key_name(event.key))
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                stage_pos = self._window_to_stage(event.pos)
                if self.ask_pending:
                    if self.trace:
                        print("[trace] ask click", stage_pos,
                              self._ask_button_rect().collidepoint(stage_pos))
                    if self._ask_button_rect().collidepoint(stage_pos):
                        # 只有“确认”按钮提交；点击输入框本身不应提交
                        self._submit_ask()
                        continue
                self.mouse_down = True
                self.mouse_x, self.mouse_y = self._screen_to_scratch(event.pos)
                self._start_drag(event.pos)
                self._handle_click(event.pos)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if self.ask_pending:
                    stage_pos = self._window_to_stage(event.pos)
                    if self._ask_button_rect().collidepoint(stage_pos):
                        # 窗口激活时按下事件可能被系统吞掉，松开时再兜底
                        self._submit_ask()
                        continue
                self.mouse_down = False
                self.dragging = None
            elif event.type == pygame.MOUSEMOTION:
                self.mouse_x, self.mouse_y = self._screen_to_scratch(event.pos)
                if self.dragging is not None:
                    offset_x, offset_y = self.dragging_offset
                    self.dragging.x = self.mouse_x + offset_x
                    self.dragging.y = self.mouse_y + offset_y
                    self.dragging._apply_fencing()
        self._update_state()
        self._draw()
        self._present()
        with self.frame_condition:
            self.frame += 1
            self.frame_condition.notify_all()
        if not self.headless:
            self.clock.tick(self.fps)

    def _log_event(self, event):
        """记录最近的事件，供 F1 调试面板显示"""
        if not self.debug_overlay:
            return
        if event.type == pygame.KEYDOWN:
            text = "KEYDOWN %s %r" % (event.key, getattr(event, 'unicode', ''))
        elif self._has_text_input and event.type == pygame.TEXTINPUT:
            text = "TEXTINPUT %r" % (event.text,)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            text = "MOUSEDOWN %s %s" % (event.button, event.pos)
        elif event.type == pygame.MOUSEBUTTONUP:
            text = "MOUSEUP %s %s" % (event.button, event.pos)
        else:
            return
        self._debug_events.append(text)
        if len(self._debug_events) > 9:
            del self._debug_events[0]

    def _draw_debug(self):
        alive = sum(1 for context in self.scripts if context.running)
        lines = [
            "v%s frame=%s scripts=%s" % (_RUNTIME_VERSION, self.frame, alive),
            "ask pending=%s visible=%s token=%s buffer=%r comp=%r" % (
                self.ask_pending, self.ask_visible, self.ask_token,
                self.ask_buffer, self.ask_composition),
            "mouse=(%s,%s) down=%s keys=%s" % (
                self.mouse_x, self.mouse_y, self.mouse_down,
                sorted(self.keys)),
        ] + list(self._debug_events)
        width = max(self.font.size(line)[0] for line in lines) + 14
        height = len(lines) * 16 + 10
        panel = pygame.Surface((width, height), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 190))
        self.stage_surface.blit(panel, (6, 6))
        for index, line in enumerate(lines):
            surface = self.font.render(line, True, (255, 255, 255))
            self.stage_surface.blit(surface, (12, 10 + index * 16))

    def _update_state(self):
        elapsed = self.elapsed()
        days = (time.time() - self.epoch_2000) / 86400.0
        for sprite in list(self.sprites):
            sprite.timer = elapsed
            sprite.days_since_2000 = days
            sprite.mouse_x = self.mouse_x
            sprite.mouse_y = self.mouse_y
            sprite.mouse_down = self.mouse_down
            sprite.answer = self.answer
            sprite._update_say()
            if self.interpolation:
                target_x = _sc_num(sprite.x)
                target_y = _sc_num(sprite.y)
                target_d = _sc_num(sprite.direction)
                target_s = _sc_num(sprite.size)
                if getattr(sprite, "_render_x", None) is None:
                    sprite._render_x = target_x
                    sprite._render_y = target_y
                    sprite._render_direction = target_d
                    sprite._render_size = target_s
                else:
                    sprite._render_x += (target_x - sprite._render_x) * 0.5
                    sprite._render_y += (target_y - sprite._render_y) * 0.5
                    delta = ((target_d - sprite._render_direction + 180) % 360) - 180
                    sprite._render_direction = (sprite._render_direction + delta * 0.5) % 360
                    sprite._render_size += (target_s - sprite._render_size) * 0.5

    def _draw(self):
        background = self.background
        ghost = 0.0
        stage = self.stage_sprite
        if background is not None and stage is not None:
            # 舞台自身的图形特效要作用在背景上（Scratch 中舞台也是角色）
            effects = stage._effects
            color = _sc_num(effects.get('color', 0))
            brightness = _sc_num(effects.get('brightness', 0))
            ghost = max(0.0, min(100.0, _sc_num(effects.get('ghost', 0))))
            if color:
                background = stage._color_effect_image(background, color)
            if brightness:
                background = stage._brightness_image(background, brightness)
            background = stage._distortion_image(background)
            if ghost > 0:
                background = background.copy()
                background.set_alpha(int(255 * (1 - ghost / 100.0)))
        # 每帧先铺白底再画背景：背景可能只是 2x2 的空白造型（Scratch 默认背景），
        # 只 blit 背景无法覆盖整个舞台，上一帧的输入框/文字会残留。
        self.stage_surface.fill((255, 255, 255))
        if background is not None:
            self.stage_surface.blit(background, (0, 0))
        self.stage_surface.blit(self.pen_layer, (0, 0))
        for sprite in list(self.sprites):
            if sprite.visible and not getattr(sprite, 'is_stage', False):
                sprite._draw(self.stage_surface, self.font)
        self._draw_monitors()
        self._draw_ask()
        if self.debug_overlay:
            self._draw_debug()

    def _all_monitors(self):
        return list(MONITORS) + self.dynamic_monitors

    def show_monitor(self, kind, name, owner, visible):
        """显示/隐藏变量或列表监视器（不存在时动态创建）"""
        prefix = 'lst' if kind == 'list' else 'var'
        attr = _sc_ident(name, prefix)
        target = None
        for monitor in self._all_monitors():
            if (monitor.get('kind') == kind and monitor.get('attr') == attr
                    and monitor.get('sprite') == owner):
                target = monitor
                break
        if target is None:
            label = name if not owner or name.startswith(owner + ':') else f"{owner}: {name}"
            target = {
                'kind': kind, 'name': name, 'sprite': owner, 'label': label,
                'attr': attr, 'visible': visible,
                'x': 5, 'y': 5 + 22 * len(self.dynamic_monitors),
                'width': 200 if kind == 'list' else 120,
                'height': 150 if kind == 'list' else 20,
            }
            self.dynamic_monitors.append(target)
        target['visible'] = visible

    def _draw_monitors(self):
        for monitor in self._all_monitors():
            if monitor.get('visible') is False:
                continue
            rect = pygame.Rect(int(monitor["x"]), int(monitor["y"]),
                               int(monitor["width"]), int(monitor["height"]))
            label = monitor.get("label") or monitor["name"]
            owner = monitor.get("sprite")
            if owner:
                target = self.find_sprite(owner)
                value = getattr(target, monitor["attr"], None) if target else None
            else:
                value = GLOBALS.get(monitor["attr"])
            if monitor["kind"] == "list":
                pygame.draw.rect(self.stage_surface, (255, 255, 255), rect, border_radius=4)
                pygame.draw.rect(self.stage_surface, (130, 130, 130), rect, 1, border_radius=4)
                title = self.font.render(label, True, (40, 40, 40))
                self.stage_surface.blit(title, (rect.x + 5, rect.y + 3))
                if isinstance(value, list):
                    line_y = rect.y + 21
                    for item in value:
                        if line_y + 14 > rect.bottom - 2:
                            break
                        text = self.font.render(_sc_str(item), True, (60, 60, 60))
                        self.stage_surface.blit(text, (rect.x + 8, line_y))
                        line_y += 15
            else:
                text = f"{label} {_sc_str(value)}"
                pygame.draw.rect(self.stage_surface, (255, 255, 255), rect, border_radius=3)
                pygame.draw.rect(self.stage_surface, (130, 130, 130), rect, 1, border_radius=3)
                surface = self.font.render(text, True, (40, 40, 40))
                self.stage_surface.blit(surface, (rect.x + 5, rect.y + 3))

    @property
    def backdrop_name(self):
        if BACKDROPS:
            index = self.current_backdrop % len(BACKDROPS)
            return BACKDROPS[index][0]
        return ''

    @property
    def backdrop_number(self):
        return self.current_backdrop + 1

    def set_backdrop(self, name):
        # 与 scratch-vm 的 _setBackdrop 保持一致：
        # 数字→编号；字符串→名字/next/previous/random backdrop/数字字符串。
        # 无法识别的名字不切换背景，也不触发“当背景换成”帽子。
        if not BACKDROPS:
            return []
        count = len(BACKDROPS)
        names = [item[0] for item in BACKDROPS]
        if isinstance(name, (int, float)) and not isinstance(name, bool):
            number = float(name)
            if math.isnan(number) or math.isinf(number):
                index = 0
            else:
                index = _sc_round(number) - 1
        else:
            value = _sc_str(name)
            if value in names:
                index = names.index(value)
            elif value == 'next backdrop':
                index = self.current_backdrop + 1
            elif value == 'previous backdrop':
                index = self.current_backdrop - 1
            elif value == 'random backdrop':
                if count <= 1:
                    return []
                index = random.randrange(count - 1)
                if index >= self.current_backdrop:
                    index += 1
            elif _sc_is_white(value):
                return []
            else:
                number = _sc_number_or_nan(value)
                if math.isnan(number) or math.isinf(number):
                    return []
                index = _sc_round(number) - 1
        return self._apply_backdrop(index)

    def next_backdrop(self):
        if BACKDROPS:
            return self._apply_backdrop(self.current_backdrop + 1)
        return []

    def _apply_backdrop(self, index):
        self.current_backdrop = int(index) % len(BACKDROPS)
        filename = BACKDROPS[self.current_backdrop][1]
        image = self._load_image(filename) if filename else None
        self.background = None
        if image is not None:
            self.background = pygame.transform.smoothscale(
                image, (self.stage_width, self.stage_height))
        name = BACKDROPS[self.current_backdrop][0]
        threads = []
        for sprite in list(self.sprites):
            sprite._running = True
            for func in list(sprite._handlers.get('backdrop:' + name, [])):
                threads.append(self.start_script(func))
            for func in list(sprite._handlers.get('backdrop:any', [])):
                threads.append(self.start_script(func))
        return threads

    def go_to_layer(self, sprite, where):
        if sprite not in self.sprites:
            return
        self.sprites.remove(sprite)
        if _sc_str(where).lower().startswith('back'):
            self.sprites.insert(0, sprite)
        else:
            self.sprites.append(sprite)

    def change_layer(self, sprite, layers):
        if sprite not in self.sprites:
            return
        index = self.sprites.index(sprite)
        target = max(0, min(len(self.sprites) - 1, index + layers))
        self.sprites.remove(sprite)
        self.sprites.insert(target, sprite)

    def sensing_of(self, target, prop):
        prop = _sc_str(prop).lower()
        target = _sc_str(target)
        if target in ('_stage_', 'Stage', '舞台'):
            if prop in ('backdrop #', 'backdrop number'):
                return self.backdrop_number
            if prop == 'backdrop name':
                return self.backdrop_name
            if prop == 'volume':
                return 100
            return 0
        other = self.find_sprite(target)
        if other is None:
            return 0
        sprite_props = {
            'x position': 'x', 'y position': 'y',
            'direction': 'direction', 'costume #': 'costume_number',
            'costume name': 'costume_name', 'size': 'size',
            'volume': 'volume',
        }
        attr = sprite_props.get(prop)
        if attr is None:
            return 0
        return getattr(other, attr)

    def apply_color_effect(self, surface, effect):
        """颜色特效：按Scratch语义旋转HSV色相"""
        angle = (_sc_num(effect) / 200.0) * 360.0
        if abs(angle) < 0.1:
            return surface
        try:
            import numpy
            result = surface.copy()
            pixels = pygame.surfarray.pixels3d(result)
            data = pixels.astype(numpy.float32) / 255.0
            red, green, blue = data[:, :, 0], data[:, :, 1], data[:, :, 2]
            maximum = data.max(axis=2)
            minimum = data.min(axis=2)
            delta = maximum - minimum
            safe = numpy.where(delta == 0, 1.0, delta)
            hue = numpy.zeros_like(maximum)
            mask = delta > 1e-6
            red_mask = mask & (maximum == red)
            green_mask = mask & (maximum == green) & ~red_mask
            blue_mask = mask & (maximum == blue) & ~red_mask & ~green_mask
            hue[red_mask] = ((green - blue) / safe)[red_mask] % 6.0
            hue[green_mask] = ((blue - red) / safe)[green_mask] + 2.0
            hue[blue_mask] = ((red - green) / safe)[blue_mask] + 4.0
            hue = (hue * 60.0 + angle) % 360.0
            saturation = numpy.where(maximum > 0, delta / numpy.where(maximum == 0, 1.0, maximum), 0.0)

            chroma = maximum * saturation
            sector = hue / 60.0
            second = chroma * (1.0 - numpy.abs(sector % 2.0 - 1.0))
            offset = maximum - chroma
            out_red = numpy.select(
                [sector < 1, sector < 2, sector < 3, sector < 4, sector < 5],
                [chroma, second, 0.0, 0.0, second], default=chroma)
            out_green = numpy.select(
                [sector < 1, sector < 2, sector < 3, sector < 4, sector < 5],
                [second, chroma, chroma, second, 0.0], default=0.0)
            out_blue = numpy.select(
                [sector < 1, sector < 2, sector < 3, sector < 4, sector < 5],
                [0.0, 0.0, second, chroma, chroma], default=second)
            shifted = numpy.stack([out_red, out_green, out_blue], axis=2)
            shifted = numpy.clip((shifted + offset[:, :, None]) * 255.0, 0, 255)
            pixels[:, :, :] = shifted.astype(numpy.uint8)
            del pixels
            return result
        except Exception:
            # 没有numpy时退化为色相着色
            color = pygame.Color(0)
            color.hsva = (int(angle % 360), 100, 100, 100)
            gray = pygame.transform.grayscale(surface).convert_alpha()
            gray.fill((color.r, color.g, color.b, 255),
                      special_flags=pygame.BLEND_RGB_MULT)
            return gray

    def _costume_color_mask(self, sprite, color):
        image = sprite._costume_surface()
        if image is None:
            return None
        return pygame.mask.from_threshold(
            image, _sc_color(color), (16, 16, 16, 255))

    def touching_color(self, sprite, color):
        mask = self._costume_color_mask(sprite, color)
        return bool(mask and mask.count() > 0)

    def color_touching_color(self, sprite, color, other):
        first = self._costume_color_mask(sprite, color)
        second = self._costume_color_mask(sprite, other)
        return bool(first and second and first.count() > 0 and second.count() > 0)

    def get_sprite_image(self, name):
        if not name:
            return None
        if name in self.costume_cache:
            return self.costume_cache[name]
        image = self._load_image(name)
        self.costume_cache[name] = image
        return image

    def _sprite_rect(self, sprite):
        rect = getattr(sprite, "_screen_rect", None)
        if rect is not None:
            return rect
        radius = max(6, int(20 * _sc_num(sprite.size) / 100.0))
        center = (int(self.stage_width / 2 + _sc_num(sprite.x)),
                  int(self.stage_height / 2 - _sc_num(sprite.y)))
        return pygame.Rect(center[0] - radius, center[1] - radius,
                           radius * 2, radius * 2)

    def _sprite_mask(self, sprite):
        image = sprite._costume_surface()
        if image is None:
            return None
        scale = max(1.0, _sc_num(sprite.size)) / 100.0
        key = (id(sprite), sprite.costume_number, int(round(scale * 100)))
        cached = self.mask_cache.get(key)
        if cached is not None:
            return cached
        if abs(scale - 1.0) > 0.01:
            image = pygame.transform.smoothscale(
                image, (max(1, int(image.get_width() * scale)),
                        max(1, int(image.get_height() * scale))))
        mask = pygame.mask.from_surface(image)
        if len(self.mask_cache) > 256:
            self.mask_cache.clear()
        self.mask_cache[key] = mask
        return mask

    def touching(self, sprite, target):
        rect = self._sprite_rect(sprite)
        if target == "_edge_":
            return (rect.left <= 0 or rect.right >= self.stage_width or
                    rect.top <= 0 or rect.bottom >= self.stage_height)
        if target == "_mouse_":
            x = self.stage_width // 2 + self.mouse_x
            y = self.stage_height // 2 - self.mouse_y
            return rect.collidepoint(x, y)
        # “碰到角色”应检查该角色的所有可见克隆体（不包括自己）
        first = None
        for other in list(self.sprites):
            if other is sprite or not other.visible or other.name != target:
                continue
            other_rect = self._sprite_rect(other)
            if not rect.colliderect(other_rect):
                continue
            if first is None:
                first = self._sprite_mask(sprite)
            second = self._sprite_mask(other)
            if first is None or second is None:
                return True
            offset = (other_rect.x - rect.x, other_rect.y - rect.y)
            if first.overlap(second, offset) is not None:
                return True
        return False

    def distance_to(self, sprite, target):
        if getattr(sprite, 'is_stage', False):
            return 10000
        if target == "_mouse_":
            return math.hypot(_sc_num(sprite.x) - self.mouse_x,
                              _sc_num(sprite.y) - self.mouse_y)
        other = self.find_sprite(target)
        if other is None:
            return 10000
        return math.hypot(_sc_num(sprite.x) - _sc_num(other.x),
                          _sc_num(sprite.y) - _sc_num(other.y))

    def play_sound(self, sprite, name):
        if not self.mixer_ready:
            return 0
        sounds = getattr(sprite, "sounds", [])
        if not sounds:
            return 0
        # scratch-vm 的 _getSoundIndex：先按名字找，再按1起编号找
        text = _sc_str(name)
        filename = None
        for sound in sounds:
            if sound.get("name") == text:
                filename = sound.get("md5ext")
                break
        if not filename:
            number = _sc_parse_int10(text)
            if number is None:
                return 0
            index = int(number - 1) % len(sounds)
            filename = sounds[index].get("md5ext")
        if not filename:
            return 0
        path = self._asset_path(filename)
        if not path:
            return 0
        sound = self.sound_cache.get(path)
        if sound is None:
            try:
                sound = pygame.mixer.Sound(path)
            except Exception:
                sound = False
            self.sound_cache[path] = sound
        if not sound:
            return 0
        channel = sound.play()
        pan = _sc_num(getattr(sprite, '_sound_effects', {}).get('pan', 0))
        volume = max(0.0, min(1.0,
                                _sc_num(getattr(sprite, 'volume', 100)) / 100.0))
        left = max(0.0, min(1.0, 1.0 - max(0.0, pan) / 100.0))
        right = max(0.0, min(1.0, 1.0 + min(0.0, pan) / 100.0))
        if channel is not None and (pan or volume != 1.0):
            channel.set_volume(left * volume, right * volume)
        return sound.get_length()

    def stop_sounds(self):
        if self.mixer_ready:
            pygame.mixer.stop()

    def start(self, max_frames=None, max_seconds=None):
        if pygame is None:
            raise RuntimeError("运行生成的脚本需要pygame: pip install pygame")
        for sprite in list(self.sprites):
            sprite.run()
        self.green_flag()
        frames = 0
        deadline = None if max_seconds is None else time.time() + max_seconds
        try:
            while self.running:
                try:
                    self.step()
                except Exception:
                    # 单帧绘制/事件异常不应让整个窗口卡死
                    import traceback
                    traceback.print_exc()
                frames += 1
                if max_frames is not None and frames >= max_frames:
                    break
                if deadline is not None and time.time() >= deadline:
                    break
        finally:
            self.running = False
            with self.frame_condition:
                self.frame_condition.notify_all()

    def shutdown(self):
        self.running = False
        with self.frame_condition:
            self.frame_condition.notify_all()
        try:
            pygame.display.quit()
        except Exception:
            pass

    def _asset_path(self, filename):
        """素材优先从脚本同目录读取，其次兼容旧的assets子目录"""
        if not filename:
            return None
        name = os.path.basename(filename)
        for folder in (self.assets_dir, os.path.join(self.assets_dir, 'assets')):
            path = os.path.join(folder, name)
            if os.path.exists(path):
                return path
        return None

    def _load_image(self, filename):
        path = self._asset_path(filename)
        if not path:
            return None
        if path.lower().endswith(".svg"):
            try:
                import cairosvg
                png_data = cairosvg.svg2png(url=path)
                image = pygame.image.load(io.BytesIO(png_data))
                try:
                    return image.convert_alpha()
                except Exception:
                    return image
            except Exception:
                return self._render_svg(path)
        try:
            image = pygame.image.load(path)
        except Exception:
            return None
        try:
            return image.convert_alpha()
        except Exception:
            return image

    def _svg_style_at(self, text, position, base):
        """计算position处继承的 fill/stroke/font-size"""
        fill, stroke, width, font_size = base
        for match in re.finditer(r'<g\b([^>]*)>|</g>', text[:position]):
            tag = match.group(0)
            if tag.startswith('</g'):
                continue
            attrs = match.group(1)
            fill = _svg_attr(attrs, 'fill', fill)
            stroke = _svg_attr(attrs, 'stroke', stroke)
            width = _svg_attr(attrs, 'stroke-width', width)
            font_size = _svg_attr(attrs, 'font-size', font_size)
        return fill, stroke, width, font_size

    def _svg_matrix_at(self, text, position):
        stack = [(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)]
        for match in re.finditer(r'<g\b([^>]*)>|</g>', text[:position]):
            tag = match.group(0)
            if tag.startswith('</g'):
                if len(stack) > 1:
                    stack.pop()
            else:
                current = _svg_mul(stack[-1],
                                   _svg_transform(_svg_attr(match.group(1), 'transform')))
                stack.append(current)
        return stack[-1]

    def _render_svg(self, path):
        """没有cairosvg时的简易SVG渲染：支持text/常见形状/path"""
        try:
            with open(path, encoding='utf-8', errors='ignore') as handle:
                text = handle.read()
        except OSError:
            return None
        root = text.split('>', 1)[0]
        width = _sc_num(_svg_attr(root, 'width', '0') or 0)
        height = _sc_num(_svg_attr(root, 'height', '0') or 0)
        view = _svg_attr(root, 'viewBox')
        if view:
            parts = [item for item in re.split(r'[ ,]+', view.strip()) if item]
            if len(parts) == 4:
                if not width:
                    width = _sc_num(parts[2])
                if not height:
                    height = _sc_num(parts[3])
        width = max(1, int(round(width or 100)))
        height = max(1, int(round(height or 100)))
        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        default_style = ('#000000', 'none', '1', '16')

        # 渐变用平均色近似（完整渐变渲染成本过高）
        gradients = {}
        for gradient in re.finditer(
                r'<(linearGradient|radialGradient)\b([^>]*)>(.*?)</\1>', text, re.S):
            ident = _svg_attr(gradient.group(2), 'id')
            colors = [_svg_color(item) for item in
                      re.findall(r'stop-color="([^"]*)"', gradient.group(3))]
            colors = [color for color in colors if color]
            if ident and colors:
                gradients[ident] = tuple(
                    sum(color[index] for color in colors) // len(colors)
                    for index in range(3))

        # 内嵌位图（data:image/png;base64,...）
        for match in re.finditer(r'<image\b([^>]*?)/?>', text):
            attrs = match.group(1)
            href = _svg_attr(attrs, 'xlink:href') or _svg_attr(attrs, 'href')
            if not href.startswith('data:image') or 'base64,' not in href:
                continue
            try:
                import base64
                raw = base64.b64decode(href.split('base64,', 1)[1])
                image = pygame.image.load(io.BytesIO(raw))
            except Exception:
                continue
            matrix = _svg_mul(self._svg_matrix_at(text, match.start()),
                              _svg_transform(_svg_attr(attrs, 'transform')))
            width = _sc_num(_svg_attr(attrs, 'width', '0'))
            height = _sc_num(_svg_attr(attrs, 'height', '0'))
            if width <= 0 or height <= 0:
                width, height = float(image.get_width()), float(image.get_height())
            scale = math.hypot(matrix[0], matrix[1]) or 1.0
            angle = -math.degrees(math.atan2(matrix[1], matrix[0]))
            drawn = pygame.transform.rotozoom(image, angle, scale)
            offset_x = _sc_num(_svg_attr(attrs, 'x', '0'))
            offset_y = _sc_num(_svg_attr(attrs, 'y', '0'))
            center_x, center_y = _svg_point(matrix, offset_x + width / 2,
                                            offset_y + height / 2)
            surface.blit(drawn, drawn.get_rect(center=(int(center_x), int(center_y))))

        # 形状
        shape_re = r'<(rect|circle|ellipse|line|polygon|polyline|path)\b([^>]*?)/?>'
        for match in re.finditer(shape_re, text):
            kind, attrs = match.group(1), match.group(2)
            base_fill, base_stroke, base_width, _size = self._svg_style_at(
                text, match.start(), default_style)
            fill = _svg_resolve_paint(_svg_attr(attrs, 'fill', base_fill), gradients)
            stroke = _svg_resolve_paint(_svg_attr(attrs, 'stroke', base_stroke), gradients)
            stroke_width_value = _sc_num(_svg_attr(attrs, 'stroke-width', base_width))
            if stroke_width_value <= 0:
                stroke = None
            stroke_width = max(1, int(stroke_width_value))
            matrix = _svg_mul(self._svg_matrix_at(text, match.start()),
                              _svg_transform(_svg_attr(attrs, 'transform')))
            points = []
            try:
                if kind == 'rect':
                    rx = _sc_num(_svg_attr(attrs, 'x', '0'))
                    ry = _sc_num(_svg_attr(attrs, 'y', '0'))
                    rw = _sc_num(_svg_attr(attrs, 'width', '0'))
                    rh = _sc_num(_svg_attr(attrs, 'height', '0'))
                    points = [_svg_point(matrix, rx, ry),
                              _svg_point(matrix, rx + rw, ry),
                              _svg_point(matrix, rx + rw, ry + rh),
                              _svg_point(matrix, rx, ry + rh)]
                elif kind == 'circle':
                    cx = _sc_num(_svg_attr(attrs, 'cx', '0'))
                    cy = _sc_num(_svg_attr(attrs, 'cy', '0'))
                    radius = _sc_num(_svg_attr(attrs, 'r', '0'))
                    center = _svg_point(matrix, cx, cy)
                    points = [(center[0] - radius * abs(matrix[0]),
                               center[1] - radius * abs(matrix[3])),
                              (center[0] + radius * abs(matrix[0]),
                               center[1] + radius * abs(matrix[3]))]
                elif kind == 'ellipse':
                    cx = _sc_num(_svg_attr(attrs, 'cx', '0'))
                    cy = _sc_num(_svg_attr(attrs, 'cy', '0'))
                    rx = _sc_num(_svg_attr(attrs, 'rx', '0'))
                    ry = _sc_num(_svg_attr(attrs, 'ry', '0'))
                    center = _svg_point(matrix, cx, cy)
                    points = [(center[0] - rx, center[1] - ry),
                              (center[0] + rx, center[1] + ry)]
                elif kind == 'line':
                    points = [
                        _svg_point(matrix, _sc_num(_svg_attr(attrs, 'x1', '0')),
                                   _sc_num(_svg_attr(attrs, 'y1', '0'))),
                        _svg_point(matrix, _sc_num(_svg_attr(attrs, 'x2', '0')),
                                   _sc_num(_svg_attr(attrs, 'y2', '0'))),
                    ]
                elif kind in ('polygon', 'polyline'):
                    values = [_sc_num(item) for item in
                              re.split(r'[ ,]+', _svg_attr(attrs, 'points').strip())
                              if item]
                    points = [_svg_point(matrix, values[i], values[i + 1])
                              for i in range(0, len(values) - 1, 2)]
                elif kind == 'path':
                    points = [_svg_point(matrix, px, py)
                              for px, py in _svg_path_points(_svg_attr(attrs, 'd'))]
            except (ValueError, IndexError):
                continue
            if not points:
                continue
            if kind in ('circle', 'ellipse') and len(points) == 2:
                left, size = points[0], (points[1][0] - points[0][0],
                                         points[1][1] - points[0][1])
                rect = pygame.Rect(int(left[0]), int(left[1]),
                                   int(size[0]), int(size[1]))
                if fill:
                    pygame.draw.ellipse(surface, fill, rect)
                if stroke:
                    pygame.draw.ellipse(surface, stroke, rect, stroke_width)
                continue
            if len(points) >= 2:
                if fill and len(points) >= 3:
                    pygame.draw.polygon(surface, fill, [(int(px), int(py))
                                                        for px, py in points])
                if stroke:
                    pygame.draw.lines(surface, stroke, kind == 'polygon',
                                      [(int(px), int(py)) for px, py in points],
                                      stroke_width)

        # 文本最后绘制，避免被前面的背景形状遮住
        for match in re.finditer(r'<text\b([^>]*)>(.*?)</text>', text, re.S):
            attrs, inner = match.group(1), match.group(2)
            base_fill, _stroke, _width, base_size = self._svg_style_at(
                text, match.start(), default_style)
            fill = _svg_resolve_paint(_svg_attr(attrs, 'fill', base_fill), gradients)
            if fill is None:
                continue
            matrix = _svg_mul(self._svg_matrix_at(text, match.start()),
                              _svg_transform(_svg_attr(attrs, 'transform')))
            size = _sc_num(_svg_attr(attrs, 'font-size', base_size)) or 16
            scale = abs(matrix[0]) or 1.0
            font_size = max(1, int(round(size * scale)))
            font = self._font(font_size)
            contents = re.findall(r'<tspan[^>]*>(.*?)</tspan>', inner, re.S)
            label = (contents[0] if contents else inner)
            label = re.sub(r'<[^>]+>', '', label).strip()
            if not label:
                continue
            rendered = font.render(label, True, fill)
            x, y = matrix[4], matrix[5]
            anchor = _svg_attr(attrs, 'text-anchor')
            if anchor == 'middle':
                x -= rendered.get_width() / 2
            elif anchor == 'end':
                x -= rendered.get_width()
            surface.blit(rendered, (int(x), int(y - font.get_ascent())))
        try:
            return surface.convert_alpha()
        except Exception:
            return surface

    def _font(self, size):
        cache = getattr(self, '_font_cache', None)
        if cache is None:
            cache = {}
            self._font_cache = cache
        if size not in cache:
            cache[size] = pygame.font.Font(self.font_path, size) if self.font_path else pygame.font.Font(None, size)
        return cache[size]

'''

    SPRITE_BASE = r'''class ScratchSprite:
    """Scratch精灵基类"""

    GLOBAL_NAMES = ()
    GLOBAL_NAMES_SET = frozenset()

    def __init__(self):
        self.x = 0
        self.y = 0
        self.direction = 90
        self.visible = True
        self.size = 100
        self.costume = 0
        self.costume_number = 0
        self.costume_name = ''
        self.volume = 100
        self.answer = ''
        self.mouse_x = 0
        self.mouse_y = 0
        self.mouse_down = False
        self.timer = 0
        self.loudness = 0
        self.days_since_2000 = 0
        self.rotation_style = 'all around'
        self._local = threading.local()
        self._global_running = True
        self._clones = []
        self.name = ''
        self.costumes = []
        self.sounds = []
        self._handlers = {}
        self._runtime = None
        self._say_text = ''
        self._say_until = None
        self._say_kind = 'say'
        self._is_clone = False
        self._render_x = None
        self._render_y = None
        self._render_direction = None
        self._render_size = None
        self._pen_down = False
        self._pen_alpha = 0.0
        self._pen_hsv = [0.0, 100.0, 100.0]
        self._pen_size = 1.0
        self._pen_last = None
        self._effects = {}
        self._sound_effects = {'pitch': 0.0, 'pan': 0.0}
        self.draggable = False

    def __getattr__(self, name):
        if name in GLOBALS:
            return GLOBALS[name]
        raise AttributeError(name)

    def __setattr__(self, name, value):
        # 用 frozenset 做 O(1) 判断，替代逐项扫描GLOBAL_NAMES元组
        if name in type(self).GLOBAL_NAMES_SET:
            GLOBALS[name] = value
        else:
            object.__setattr__(self, name, value)

    def move(self, steps):
        """移动指定步数"""
        steps = _sc_num(steps)
        rad = math.radians(self.direction)
        # Scratch方向: 0=上, 90=右
        self.x += steps * math.sin(rad)
        self.y += steps * math.cos(rad)
        self._apply_fencing()
        self._pen_update()

    def turn_right(self, degrees):
        """右转指定度数"""
        degrees = _sc_num(degrees)
        self.direction = (self.direction + degrees) % 360

    def turn_left(self, degrees):
        """左转指定度数"""
        degrees = _sc_num(degrees)
        self.direction = (self.direction - degrees) % 360
        if self.direction < 0:
            self.direction += 360

    def goto_xy(self, x, y):
        """跳转到指定坐标"""
        self.x = _sc_num(x)
        self.y = _sc_num(y)
        self._apply_fencing()
        self._pen_update()

    def set_x(self, x):
        self.x = _sc_num(x)
        self._apply_fencing()
        self._pen_update()

    def set_y(self, y):
        self.y = _sc_num(y)
        self._apply_fencing()
        self._pen_update()

    def change_x(self, dx):
        self.x += _sc_num(dx)
        self._apply_fencing()
        self._pen_update()

    def change_y(self, dy):
        self.y += _sc_num(dy)
        self._apply_fencing()
        self._pen_update()

    def if_on_edge_bounce(self):
        """碰到边缘反弹"""
        width = self._runtime.stage_width / 2 if self._runtime else 240
        height = self._runtime.stage_height / 2 if self._runtime else 180
        if self.x > width:
            self.x = width
            self.direction = (-self.direction) % 360
        elif self.x < -width:
            self.x = -width
            self.direction = (-self.direction) % 360
        if self.y > height:
            self.y = height
            self.direction = (180 - self.direction) % 360
        elif self.y < -height:
            self.y = -height
            self.direction = (180 - self.direction) % 360
        self.direction = self.direction % 360
        self._pen_update()

    def _clamp_position(self):
        width = self._runtime.stage_width / 2 if self._runtime else 240
        height = self._runtime.stage_height / 2 if self._runtime else 180
        self.x = max(-width, min(width, self.x))
        self.y = max(-height, min(height, self.y))

    def _sprite_bounds(self):
        """当前造型旋转/缩放后的半宽、半高（用于舞台边界约束）"""
        image = self._costume_surface()
        if image is None:
            return max(1.0, 20 * abs(_sc_num(self.size)) / 200.0), \
                max(1.0, 20 * abs(_sc_num(self.size)) / 200.0)
        scale = max(1.0, _sc_num(self.size)) / 100.0
        width = image.get_width() * scale
        height = image.get_height() * scale
        angle = math.radians(90 - _sc_num(self.direction))
        if self.rotation_style in ('left-right', "don't rotate"):
            angle = 0.0
        cos_value, sin_value = abs(math.cos(angle)), abs(math.sin(angle))
        return ((width * cos_value + height * sin_value) / 2.0,
                (width * sin_value + height * cos_value) / 2.0)

    def _apply_fencing(self):
        """角色不能离开舞台（Scratch 的 Fencing，可用 TurboWarp 高级选项关闭）"""
        if self._runtime is None or not self._runtime.fencing:
            return
        half_w, half_h = self._sprite_bounds()
        stage_w = self._runtime.stage_width
        stage_h = self._runtime.stage_height
        if half_w * 2 > stage_w:
            # 比舞台还宽时居中（与 Scratch 一致）
            self.x = 0
        else:
            limit_x = stage_w / 2 - half_w
            self.x = max(-limit_x, min(limit_x, _sc_num(self.x)))
        if half_h * 2 > stage_h:
            self.y = 0
        else:
            limit_y = stage_h / 2 - half_h
            self.y = max(-limit_y, min(limit_y, _sc_num(self.y)))

    def _pen_update(self):
        """画笔落下时，把移动轨迹画到画布上"""
        runtime = self._runtime
        if runtime is None:
            return
        current = (float(_sc_num(self.x)), float(_sc_num(self.y)))
        if not getattr(self, '_pen_down', False):
            self._pen_last = None
            return
        last = getattr(self, '_pen_last', None)
        if last is not None and last != current:
            hue, saturation, brightness = getattr(self, '_pen_hsv',
                                                    [0.0, 100.0, 100.0])
            color = _hsv_to_rgb(hue, saturation, brightness)
            alpha = max(0.0, min(100.0, _sc_num(getattr(self, '_pen_alpha', 0))))
            if alpha > 0:
                color = color + (int(255 * (1 - alpha / 100.0)),)
            runtime.pen_draw_segment(
                last, current, color,
                max(1, int(_sc_num(getattr(self, '_pen_size', 1)))))
        self._pen_last = current

    def say(self, message):
        """说话（显示对话气泡）"""
        self._say_text = _sc_str(message)
        self._say_until = None
        self._say_kind = 'say'

    def say_for(self, message, secs):
        text = _sc_str(message)
        self._say_text = text
        self._say_kind = 'say'
        duration = _sc_wait_time(secs)
        self._say_until = time.time() + duration
        self._sleep(duration)
        if self._say_text == text:
            self._say_text = ''
            self._say_until = None

    def think(self, message):
        """思考（显示思考气泡）"""
        self._say_text = _sc_str(message)
        self._say_until = None
        self._say_kind = 'think'

    def think_for(self, message, secs):
        text = _sc_str(message)
        self._say_text = text
        self._say_kind = 'think'
        duration = _sc_wait_time(secs)
        self._say_until = time.time() + duration
        self._sleep(duration)
        if self._say_text == text:
            self._say_text = ''
            self._say_until = None

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def switch_costume(self, costume):
        # 与 scratch-vm 的 _setCostume/setCostume 保持一致：
        # - 数字类型一律当作1起的造型编号（四舍五入，越界循环）
        # - 字符串先按名字匹配，再处理 next/previous costume，最后才尝试转数字
        names = [item.get('name', '') for item in self.costumes]
        count = len(names)
        if not count:
            return
        if isinstance(costume, (int, float)) and not isinstance(costume, bool):
            number = float(costume)
            if math.isnan(number) or math.isinf(number):
                index = 0
            else:
                index = _sc_round(number) - 1
        else:
            value = _sc_str(costume)
            if value in names:
                index = names.index(value)
            elif value == 'next costume':
                index = int(_sc_num(self.costume_number))
            elif value == 'previous costume':
                index = int(_sc_num(self.costume_number)) - 2
            elif _sc_is_white(value):
                return
            else:
                number = _sc_number_or_nan(value)
                if math.isnan(number) or math.isinf(number):
                    return
                index = _sc_round(number) - 1
        index = int(index) % count
        self.costume_number = index + 1
        self.costume_name = names[index]

    def next_costume(self):
        count = len(self.costumes)
        if count:
            index = (self.costume_number) % count
            self.costume_number = index + 1
            self.costume_name = self.costumes[index].get('name', '')

    def change_size(self, change):
        self.size += _sc_num(change)
        self._apply_fencing()

    def set_size(self, size):
        self.size = _sc_num(size)
        self._apply_fencing()

    def change_effect(self, effect, change):
        key = str(effect).lower()
        self._effects[key] = _sc_clamp_effect(
            key, _sc_num(self._effects.get(key, 0)) + _sc_num(change))

    def set_effect(self, effect, value):
        key = str(effect).lower()
        self._effects[key] = _sc_clamp_effect(key, _sc_num(value))

    def clear_effects(self):
        self._effects = {}

    def play_sound(self, sound, wait=False):
        duration = 0
        if self._runtime is not None:
            duration = self._runtime.play_sound(self, _sc_str(sound))
        if wait and duration:
            self._sleep(duration)

    def stop_all_sounds(self):
        if self._runtime is not None:
            self._runtime.stop_sounds()

    def change_volume(self, change):
        self.volume = _sc_add(self.volume, change)
        if self._runtime is None or self._runtime.misc_limits:
            self.volume = max(0, min(100, self.volume))

    def set_volume(self, volume):
        self.volume = _sc_num(volume)
        if self._runtime is None or self._runtime.misc_limits:
            self.volume = max(0, min(100, self.volume))

    def wait(self, seconds):
        """等待指定秒数"""
        self._sleep(seconds)

    def wait_until(self, condition_func):
        """等待直到条件为真"""
        while self._running and not condition_func():
            self._yield_frame()

    def stop(self, option='all'):
        option = _sc_str(option)
        if option == 'all':
            if self._runtime is not None:
                self._runtime.stop_all_scripts()
            raise StopIteration('stop all')
        if option.startswith('other scripts'):
            if self._runtime is not None:
                self._runtime.stop_other_scripts(self)
            return
        # 停止这个脚本：在自制积木内相当于return到调用处
        if getattr(self._local, 'depth', 0) > 0:
            raise _ProcedureReturn()
        context = getattr(self._local, 'context', None)
        if context is not None:
            context.running = False
        else:
            self._global_running = False
        raise StopIteration('stop this script')

    def create_clone_of(self, target):
        target = _sc_str(target)
        if self._runtime is None:
            return
        clone_source = self if target in ('_myself_', self.name) \
            else self._runtime.find_sprite(target)
        if clone_source is not None:
            clone_source._make_clone()

    def delete_this_clone(self):
        if not self._is_clone:
            return
        if self._runtime is not None:
            self._runtime.remove_sprite(self)
        raise StopIteration('Clone deleted')

    def broadcast(self, message):
        if self._runtime is not None:
            self._runtime.broadcast(message)

    def broadcast_and_wait(self, message):
        if self._runtime is not None:
            self._turn_release()
            try:
                self._runtime.broadcast_and_wait(
                    message, getattr(self._local, 'context', None))
            finally:
                self._turn_acquire()

    def touching(self, object):
        if self._runtime is None:
            return False
        return self._runtime.touching(self, _sc_str(object))

    def distance_to(self, object):
        if self._runtime is None:
            return 0
        return self._runtime.distance_to(self, _sc_str(object))

    def key_pressed(self, key):
        if self._runtime is None:
            return False
        key = _sc_str(key)
        if key == 'any':
            return bool(self._runtime.keys)
        return key in self._runtime.keys

    def ask_and_wait(self, question):
        question = _sc_str(question)
        if self._runtime is None:
            self.answer = input(question)
            return
        self._turn_release()
        try:
            context = getattr(self._local, 'context', None)
            self.answer = self._runtime.ask(question, context)
            self._runtime.answer = self.answer
        finally:
            self._turn_acquire()

    def reset_timer(self):
        if self._runtime is not None:
            self._runtime.reset_timer()
        self.timer = 0

    def current_time(self, unit):
        """当前日期/时间（对应Scratch的“当前时间”积木）"""
        t = time.localtime()
        values = {
            'YEAR': t.tm_year,
            'MONTH': t.tm_mon,
            'DATE': t.tm_mday,
            'DAYOFWEEK': ((t.tm_wday + 1) % 7) + 1,
            'HOUR': t.tm_hour,
            'MINUTE': t.tm_min,
            'SECOND': t.tm_sec,
        }
        return values.get(unit, 0)

    def goto_random(self):
        """移动到随机位置"""
        width = self._runtime.stage_width if self._runtime else 480
        height = self._runtime.stage_height if self._runtime else 360
        self.x = random.randint(-width // 2, width // 2)
        self.y = random.randint(-height // 2, height // 2)
        self._apply_fencing()
        self._pen_update()

    def glide_to(self, secs, x, y):
        """在指定秒数内滑行到目标坐标"""
        secs = _sc_wait_time(secs)
        x = _sc_num(x)
        y = _sc_num(y)
        start_x, start_y = self.x, self.y
        steps = 20
        for i in range(1, steps + 1):
            self._sleep(secs / steps)
            self.x = start_x + (x - start_x) * i / steps
            self.y = start_y + (y - start_y) * i / steps
            self._apply_fencing()
            self._pen_update()

    def show_variable(self, name):
        if self._runtime is None:
            return
        text = _sc_str(name)
        local = _sc_ident(text, 'var') in self.__dict__
        self._runtime.show_monitor('var', text, self.name if local else None, True)

    def hide_variable(self, name):
        if self._runtime is None:
            return
        text = _sc_str(name)
        local = _sc_ident(text, 'var') in self.__dict__
        self._runtime.show_monitor('var', text, self.name if local else None, False)

    def show_list(self, name):
        if self._runtime is None:
            return
        text = _sc_str(name)
        local = _sc_ident(text, 'lst') in self.__dict__
        self._runtime.show_monitor('list', text, self.name if local else None, True)

    def hide_list(self, name):
        if self._runtime is None:
            return
        text = _sc_str(name)
        local = _sc_ident(text, 'lst') in self.__dict__
        self._runtime.show_monitor('list', text, self.name if local else None, False)

    def list_item_number(self, items, item):
        """返回item在列表中的位置(1起始)，不存在返回0"""
        return _sc_list_item_number(items, item)

    @property
    def _running(self):
        context = getattr(self._local, 'context', None)
        return context.running if context is not None else self._global_running

    @_running.setter
    def _running(self, value):
        context = getattr(self._local, 'context', None)
        if context is not None:
            context.running = value
        else:
            self._global_running = value

    def _enter_procedure(self, warp=False):
        self._local.depth = getattr(self._local, 'depth', 0) + 1
        if warp:
            self._local.warp_depth = getattr(self._local, 'warp_depth', 0) + 1

    def _leave_procedure(self, warp=False):
        self._local.depth = max(0, getattr(self._local, 'depth', 0) - 1)
        if warp:
            self._local.warp_depth = max(0, getattr(self._local, 'warp_depth', 0) - 1)
            if self._local.warp_depth == 0:
                self._local.warp_start = None

    def _register(self, event, func):
        handlers = self._handlers.setdefault(event, [])
        if func not in handlers:
            handlers.append(func)

    def _turn_acquire(self):
        """获取脚本执行权（同一时刻只让一个脚本执行，模拟Scratch单线程调度）"""
        runtime = self._runtime
        if runtime is not None and not getattr(self._local, 'turn_owned', False):
            runtime.turn_lock.acquire()
            self._local.turn_owned = True

    def _turn_release(self):
        runtime = self._runtime
        if runtime is not None and getattr(self._local, 'turn_owned', False):
            self._local.turn_owned = False
            runtime.turn_lock.release()

    def _sleep(self, seconds):
        """等待期间让出执行权，避免阻塞其他脚本"""
        seconds = _sc_wait_time(seconds)
        if seconds <= 0:
            return
        self._turn_release()
        try:
            time.sleep(seconds)
        finally:
            self._turn_acquire()

    def _yield_frame(self):
        """让当前脚本等待到下一帧；warp/turbo模式下不等待"""
        if self._runtime is None:
            time.sleep(0.01)
            return
        context = getattr(self._local, 'context', None)
        warp = getattr(self._local, 'warp_depth', 0) > 0 or getattr(self._runtime, 'turbo', False)
        if not warp:
            self._turn_release()
            self._runtime.wait_frame(context)
            self._turn_acquire()
            return
        limit = getattr(self._runtime, 'warp_timer', 0.5)
        if limit:
            now = time.time()
            start = getattr(self._local, 'warp_start', None)
            if start is None:
                self._local.warp_start = now
            elif now - start >= limit:
                self._local.warp_start = now
                self._turn_release()
                self._runtime.wait_frame(context)
                self._turn_acquire()

    def _update_say(self):
        if self._say_until is not None and time.time() >= self._say_until:
            self._say_text = ''
            self._say_until = None

    def _contains_point(self, x, y):
        rect = getattr(self, '_screen_rect', None)
        if rect is None:
            return False
        width = self._runtime.stage_width // 2 if self._runtime else 240
        height = self._runtime.stage_height // 2 if self._runtime else 180
        return rect.collidepoint(width + x, height - y)

    def _costume_info(self):
        if not self.costumes:
            return {}
        index = max(0, int(_sc_num(self.costume_number)) - 1) if self.costume_number else 0
        return self.costumes[index % len(self.costumes)]

    def _costume_surface(self):
        if self._runtime is None or not self.costumes:
            return None
        costume = self._costume_info()
        name = costume.get('md5ext') or costume.get('name')
        return self._runtime.get_sprite_image(name)

    def _placeholder_color(self):
        seed = sum(ord(ch) for ch in self.name) if self.name else 0
        return (70 + seed * 37 % 150, 70 + seed * 67 % 150, 70 + seed * 97 % 150)

    def _color_effect_image(self, image, effect):
        """按(造型Surface, 特效值)缓存颜色特效结果，避免每帧做HSV转换"""
        cache = getattr(self, '_color_cache', None)
        if cache is None:
            cache = self._color_cache = {}
        key = (id(image), round(_sc_num(effect), 3))
        surface = cache.get(key)
        if surface is None:
            surface = self._runtime.apply_color_effect(image, effect)
            if len(cache) >= 8:
                cache.clear()
            cache[key] = surface
        return surface

    def _brightness_image(self, image, brightness):
        """按(造型Surface, 亮度值)缓存亮度特效结果，避免每帧fill整张图"""
        cache = getattr(self, '_brightness_cache', None)
        if cache is None:
            cache = self._brightness_cache = {}
        delta = int(255 * max(-100.0, min(100.0, _sc_num(brightness))) / 100.0)
        if delta == 0:
            return image
        key = (id(image), delta)
        surface = cache.get(key)
        if surface is None:
            surface = image.copy()
            if delta > 0:
                surface.fill((delta, delta, delta, 0),
                             special_flags=pygame.BLEND_RGB_ADD)
            else:
                surface.fill((-delta, -delta, -delta, 0),
                             special_flags=pygame.BLEND_RGB_SUB)
            if len(cache) >= 8:
                cache.clear()
            cache[key] = surface
        return surface

    def _distortion_image(self, image):
        """鱼眼/旋涡/像素化/马赛克：按(造型Surface, 特效值)缓存结果"""
        effects = self._effects
        mosaic = _sc_num(effects.get('mosaic', 0))
        pixelate = _sc_num(effects.get('pixelate', 0))
        whirl = _sc_num(effects.get('whirl', 0))
        fisheye = _sc_num(effects.get('fisheye', 0))
        if abs(mosaic) < 1e-3 and abs(pixelate) < 1e-3 \
                and abs(whirl) < 1e-3 and abs(fisheye) < 1e-3:
            return image
        cache = getattr(self, '_distortion_cache', None)
        if cache is None:
            cache = self._distortion_cache = {}
        key = (id(image), round(mosaic, 2), round(pixelate, 2),
               round(whirl, 2), round(fisheye, 2))
        surface = cache.get(key)
        if surface is None:
            surface = self._distort_surface(
                image, mosaic, pixelate, whirl, fisheye)
            if len(cache) >= 6:
                cache.clear()
            cache[key] = surface
        return surface

    def _distort_surface(self, image, mosaic, pixelate, whirl, fisheye):
        """复刻 scratch-render 的 EffectTransform：马赛克→像素化→旋涡→鱼眼"""
        width, height = image.get_size()
        if width <= 0 or height <= 0:
            return image
        try:
            import numpy
        except ImportError:
            return self._distort_fallback(image, mosaic, pixelate)
        try:
            xs = (numpy.arange(width, dtype=numpy.float32) + 0.5) / width
            ys = (numpy.arange(height, dtype=numpy.float32) + 0.5) / height
            u = numpy.repeat(xs[:, None], height, axis=1)
            v = numpy.repeat(ys[None, :], width, axis=0)

            if abs(mosaic) > 1e-3:
                tiles = max(1.0, min(
                    float(round((abs(mosaic) + 10.0) / 10.0)), 512.0))
                u = numpy.mod(u * tiles, 1.0)
                v = numpy.mod(v * tiles, 1.0)

            if abs(pixelate) > 1e-3:
                block = max(abs(pixelate) / 10.0, 1e-3)
                columns = max(1.0, width / block)
                rows = max(1.0, height / block)
                u = (numpy.floor(u * columns) + 0.5) / columns
                v = (numpy.floor(v * rows) + 0.5) / rows

            if abs(whirl) > 1e-3:
                angle = -whirl * math.pi / 180.0
                offset_x = u - 0.5
                offset_y = v - 0.5
                radius = numpy.sqrt(offset_x * offset_x + offset_y * offset_y)
                factor = numpy.maximum(1.0 - radius / 0.5, 0.0)
                actual = angle * factor * factor
                cos_value = numpy.cos(actual)
                sin_value = numpy.sin(actual)
                u = cos_value * offset_x + sin_value * offset_y + 0.5
                v = -sin_value * offset_x + cos_value * offset_y + 0.5

            if abs(fisheye) > 1e-3:
                power = max(0.0, (fisheye + 100.0) / 100.0)
                vec_x = (u - 0.5) / 0.5
                vec_y = (v - 0.5) / 0.5
                length = numpy.sqrt(vec_x * vec_x + vec_y * vec_y)
                safe = numpy.where(length < 1e-6, 1.0, length)
                r = numpy.power(numpy.minimum(length, 1.0), power) \
                    * numpy.maximum(1.0, length)
                u = 0.5 + r * (vec_x / safe) * 0.5
                v = 0.5 + r * (vec_y / safe) * 0.5

            x_index = numpy.clip(
                numpy.floor(u * width).astype(numpy.int32), 0, width - 1)
            y_index = numpy.clip(
                numpy.floor(v * height).astype(numpy.int32), 0, height - 1)
            source = pygame.surfarray.pixels3d(image)
            source_alpha = pygame.surfarray.pixels_alpha(image)
            sampled = source[x_index, y_index]
            sampled_alpha = source_alpha[x_index, y_index]
            result = pygame.Surface((width, height), pygame.SRCALPHA)
            target = pygame.surfarray.pixels3d(result)
            target[:, :, :] = sampled
            target_alpha = pygame.surfarray.pixels_alpha(result)
            target_alpha[:, :] = sampled_alpha
            del source, source_alpha, target, target_alpha
            return result
        except Exception:
            return self._distort_fallback(image, mosaic, pixelate)

    def _distort_fallback(self, image, mosaic, pixelate):
        """没有 numpy 时用 pygame 缩放/平铺近似像素化与马赛克"""
        try:
            width, height = image.get_size()
            if abs(mosaic) > 0.5:
                tiles = int(max(1, min(
                    round((abs(mosaic) + 10.0) / 10.0), 128)))
                if tiles > 1:
                    tile = pygame.transform.scale(
                        image, (max(1, width // tiles),
                                max(1, height // tiles)))
                    result = pygame.Surface((width, height), pygame.SRCALPHA)
                    tile_width, tile_height = tile.get_size()
                    for y in range(0, height, tile_height):
                        for x in range(0, width, tile_width):
                            result.blit(tile, (x, y))
                    return result
            if abs(pixelate) > 0.5:
                block = max(1, int(abs(pixelate) / 10.0))
                small = pygame.transform.scale(
                    image, (max(1, width // block),
                            max(1, height // block)))
                return pygame.transform.scale(small, (width, height))
        except Exception:
            pass
        return image

    def _rendered_image(self):
        """当前外观（含颜色/亮度/形状特效、旋转、缩放、旋转中心）

        返回 (surface, rect, x, y, scale, direction)；没有造型时 surface 为 None。
        图章（stamp）复用同一份结果，保证图章与画面一致。
        """
        image = self._costume_surface()
        runtime = self._runtime
        use_interp = runtime is not None and runtime.interpolation and getattr(self, '_render_x', None) is not None
        draw_x = self._render_x if use_interp else _sc_num(self.x)
        draw_y = self._render_y if use_interp else _sc_num(self.y)
        draw_direction = self._render_direction if use_interp else _sc_num(self.direction)
        draw_size = self._render_size if use_interp else _sc_num(self.size)
        stage_width = runtime.stage_width if runtime else 480
        stage_height = runtime.stage_height if runtime else 360
        scale = max(1.0, draw_size) / 100.0
        x = int(stage_width / 2 + draw_x)
        y = int(stage_height / 2 - draw_y)
        if image is None:
            return None, None, x, y, scale, draw_direction
        angle = 90 - draw_direction
        if self.rotation_style in ('left-right', "don't rotate"):
            angle = 0
        color_effect = _sc_num(self._effects.get('color', 0))
        brightness = _sc_num(self._effects.get('brightness', 0))
        ghost = max(0.0, min(100.0, _sc_num(self._effects.get('ghost', 0))))
        # 颜色/亮度特效很耗CPU，按(造型Surface, 特效值)缓存；特效值不变时直接复用
        base = image
        if color_effect and runtime is not None:
            base = self._color_effect_image(image, color_effect)
        if brightness and runtime is not None:
            base = self._brightness_image(base, brightness)
        # 鱼眼/旋涡/像素化/马赛克作用在造型上，再参与旋转与缩放
        if runtime is not None:
            base = self._distortion_image(base)
        # 无旋转/无缩放时直接复用缓存的Surface，避免每帧rotozoom拷贝
        if angle == 0 and scale == 1.0:
            transformed = base
            fresh = False
        else:
            transformed = pygame.transform.rotozoom(base, angle, scale)
            fresh = True
        if self.rotation_style == 'left-right' and math.cos(math.radians(draw_direction)) < 0:
            transformed = pygame.transform.flip(transformed, True, False)
            fresh = True
        # 幽灵特效需要修改Surface，不能污染缓存
        if ghost > 0:
            if not fresh:
                transformed = transformed.copy()
            transformed.set_alpha(int(255 * (1 - ghost / 100.0)))
        rect = transformed.get_rect(center=(x, y))
        info = self._costume_info()
        center_x = info.get('rotationCenterX')
        center_y = info.get('rotationCenterY')
        center_x = image.get_width() / 2 if center_x is None else _sc_num(center_x)
        center_y = image.get_height() / 2 if center_y is None else _sc_num(center_y)
        if angle == 0:
            # Scratch的position对应旋转中心，旋转中心坐标以图片左上角为原点(y向下)
            rect.center = (x - int((center_x - image.get_width() / 2) * scale),
                           y - int((center_y - image.get_height() / 2) * scale))
        return transformed, rect, x, y, scale, draw_direction

    def _draw(self, screen, font):
        transformed, rect, x, y, scale, direction = self._rendered_image()
        if transformed is not None:
            screen.blit(transformed, rect)
        else:
            radius = max(6, int(20 * scale))
            pygame.draw.circle(screen, self._placeholder_color(), (x, y), radius)
            end = (x + int(math.sin(math.radians(direction)) * radius),
                   y - int(math.cos(math.radians(direction)) * radius))
            pygame.draw.line(screen, (40, 40, 40), (x, y), end, 2)
            rect = pygame.Rect(x - radius, y - radius, radius * 2, radius * 2)
        self._screen_rect = rect
        self._draw_bubble(screen, font)

    def _draw_bubble(self, screen, font):
        text = self._say_text
        if not text:
            return
        chunk = 16
        lines = [text[i:i + chunk] for i in range(0, len(text), chunk)] or ['']
        width = max(font.size(line)[0] for line in lines) + 12
        height = len(lines) * 15 + 8
        rect = getattr(self, '_screen_rect', pygame.Rect(220, 160, 40, 40))
        stage_width = self._runtime.stage_width if self._runtime else 480
        x = max(2, min(stage_width - width - 2, rect.centerx - width // 2))
        y = max(2, rect.top - height - 8)
        bubble = pygame.Rect(x, y, width, height)
        pygame.draw.rect(screen, (255, 255, 255), bubble, border_radius=6)
        pygame.draw.rect(screen, (120, 120, 120), bubble, 1, border_radius=6)
        for index, line in enumerate(lines):
            surface = font.render(line, True, (30, 30, 30))
            screen.blit(surface, (x + 6, y + 4 + index * 15))

    def _make_clone(self):
        if self._runtime is None:
            return None
        if self._runtime.clone_limit is not None:
            clones = sum(1 for item in self._runtime.sprites if getattr(item, '_is_clone', False))
            if clones >= self._runtime.clone_limit:
                return None
        clone = self.__class__()
        for key, value in self.__dict__.items():
            if key.startswith('_') or key in getattr(type(self), 'GLOBAL_NAMES', ()):
                continue
            setattr(clone, key, value.copy() if isinstance(value, (list, dict)) else value)
        clone._handlers = {}
        clone._runtime = self._runtime
        clone._running = True
        clone._is_clone = True
        clone.run()
        self._runtime.sprites.append(clone)
        for func in list(clone._handlers.get('clone_start', [])):
            self._runtime.start_script(func)
        return clone

    def point_in_direction(self, direction):
        """面向指定方向"""
        self.direction = _sc_num(direction) % 360

    def point_towards(self, target):
        """面向鼠标指针或另一个角色"""
        if target == '_mouse_':
            dx = _sc_num(self.mouse_x) - _sc_num(self.x)
            dy = _sc_num(self.mouse_y) - _sc_num(self.y)
        else:
            other = self._runtime.find_sprite(target) if self._runtime else None
            if other is None:
                return
            dx = _sc_num(other.x) - _sc_num(self.x)
            dy = _sc_num(other.y) - _sc_num(self.y)
        if dx == 0 and dy == 0:
            return
        self.direction = math.degrees(math.atan2(dx, dy)) % 360

    def goto_target(self, target):
        """移到随机位置/鼠标指针/某个角色"""
        if target == '_mouse_':
            self.goto_xy(self.mouse_x, self.mouse_y)
        elif target in ('_random_', ''):
            self.goto_random()
        else:
            other = self._runtime.find_sprite(target) if self._runtime else None
            if other is not None:
                self.goto_xy(other.x, other.y)

    def glide_to_target(self, secs, target):
        """在指定秒数内滑行到随机位置/鼠标指针/某个角色"""
        if target == '_mouse_':
            self.glide_to(secs, self.mouse_x, self.mouse_y)
        elif target in ('_random_', ''):
            width = self._runtime.stage_width if self._runtime else 480
            height = self._runtime.stage_height if self._runtime else 360
            self.glide_to(secs, random.randint(-width // 2, width // 2),
                          random.randint(-height // 2, height // 2))
        else:
            other = self._runtime.find_sprite(target) if self._runtime else None
            if other is not None:
                self.glide_to(secs, other.x, other.y)

    def set_rotation_style(self, style):
        """设置旋转方式"""
        style = _sc_str(style)
        if style in ('left-right', 'left right', '左右翻转'):
            self.rotation_style = 'left-right'
        elif "don't" in style or 'none' in style or '不旋转' in style:
            self.rotation_style = "don't rotate"
        else:
            self.rotation_style = 'all around'
        self._apply_fencing()

    def set_backdrop(self, name):
        """切换舞台背景"""
        if self._runtime is not None:
            self._runtime.set_backdrop(name)

    def set_backdrop_and_wait(self, name):
        """切换背景并等待这次切换触发的“当背景换成”脚本结束"""
        if self._runtime is None:
            return
        threads = self._runtime.set_backdrop(name)
        if not threads:
            self._yield_frame()
            return
        context = getattr(self._local, 'context', None)
        self._turn_release()
        try:
            for thread in threads:
                while (thread.is_alive() and self._runtime.running
                       and (context is None or context.running)):
                    self._runtime.wait_frame(context)
        finally:
            self._turn_acquire()

    def next_backdrop(self):
        if self._runtime is not None:
            self._runtime.next_backdrop()

    @property
    def backdrop_number(self):
        return self._runtime.backdrop_number if self._runtime else 1

    @property
    def backdrop_name(self):
        return self._runtime.backdrop_name if self._runtime else ''

    def go_to_layer(self, where):
        """移到最前面/最后面"""
        if self._runtime is not None:
            self._runtime.go_to_layer(self, _sc_str(where))

    def change_layer(self, layers):
        """向前/向后移动若干层"""
        if self._runtime is not None:
            self._runtime.change_layer(self, int(_sc_num(layers)))

    def set_drag_mode(self, mode):
        self.draggable = 'not' not in _sc_str(mode).lower()

    def set_sound_effect(self, effect, value):
        key = _sc_str(effect).lower()
        self._sound_effects[key] = _sc_num(value)

    def change_sound_effect(self, effect, value):
        key = _sc_str(effect).lower()
        self._sound_effects[key] = _sc_num(self._sound_effects.get(key, 0)) + _sc_num(value)

    def clear_sound_effects(self):
        self._sound_effects = {'pitch': 0.0, 'pan': 0.0}

    def touching_color(self, color):
        if self._runtime is None:
            return False
        return self._runtime.touching_color(self, color)

    def color_touching_color(self, color, other):
        if self._runtime is None:
            return False
        return self._runtime.color_touching_color(self, color, other)

    def sensing_of(self, target, prop):
        if self._runtime is None:
            return 0
        return self._runtime.sensing_of(_sc_str(target), _sc_str(prop))

    def get_counter(self):
        return self._runtime.counter if self._runtime is not None else 0

    def incr_counter(self):
        if self._runtime is not None:
            self._runtime.counter += 1

    def clear_counter(self):
        if self._runtime is not None:
            self._runtime.counter = 0

    def username(self):
        return 'player'

    def extension(self, name, opcode, inputs=None, fields=None):
        """TurboWarp扩展调用入口"""
        if self._runtime is None:
            return 0
        return self._runtime.call_extension(
            self, name, opcode, inputs or {}, fields or {})

    def run(self):
        """注册事件脚本（由运行时调用）"""
        pass
'''

    def __init__(self):
        self.imports: Set[str] = set()
        self.indent_level = 0
        self.current_sprite: Optional[SpriteIR] = None
        self.procedure_names: Dict[str, str] = {}
        self.stage_globals: Dict[str, object] = {}
        self.global_names: Set[str] = set()

    def generate_project(self, project: ProjectIR) -> str:
        """生成整个项目的Python代码"""
        self.imports = {"import math", "import time", "import random"}

        # Scratch全局变量/列表存放在舞台上；生成后放进共享的GLOBALS字典，
        # 所有角色通过 __getattr__/__setattr__ 读写同一份数据。
        self.stage_globals = {}
        if project.stage is not None:
            for name, value in project.stage.variables.items():
                self.stage_globals[sanitize_name(name, 'var')] = value
            for name, items in project.stage.lists.items():
                self.stage_globals[sanitize_name(name, 'lst')] = list(items)
        self.global_names = set(self.stage_globals)

        lines = []
        lines.append("# -*- coding: utf-8 -*-")
        lines.append('"""')
        lines.append("Scratch 3.0 / TurboWarp -> Python 转换代码")
        lines.append("由 scratch-converter 自动生成")
        lines.append('"""')
        lines.append("")
        if project.warnings:
            summary = ', '.join(f"{opcode} x{count}"
                                for opcode, count in sorted(project.warnings.items()))
            lines.append(f"# 转换报告: 以下积木暂未支持，已从脚本中忽略: {summary}")
            lines.append("")
        lines.append("import math")
        lines.append("import time")
        lines.append("import random")
        lines.append("import re")
        lines.append("import array")
        lines.append("import decimal")
        lines.append("import os")
        lines.append("import io")
        lines.append("import argparse")
        lines.append("import threading")
        lines.append("")
        lines.append("try:")
        lines.append("    import pygame")
        lines.append("except ImportError:")
        lines.append("    pygame = None")
        lines.append("")

        lines.extend(self._generate_runtime_helpers())
        lines.append("")

        lines.extend(self._generate_runtime_constants(project))
        lines.extend(self._generate_runtime_class())
        lines.append("")

        lines.extend(self._generate_base_class())
        lines.append("")

        for sprite in project.sprites:
            lines.extend(self._generate_sprite_class(sprite))
            lines.append("")

        lines.extend(self._generate_main(project))
        set_procedure_name_resolver(None)
        return "\n".join(lines)

    def _generate_runtime_helpers(self) -> List[str]:
        """生成复刻Scratch类型转换与运算语义的模块级辅助函数"""
        lines = self.RUNTIME_HELPERS.strip('\n').splitlines()
        lines.append("")
        lines.extend(self.RUNTIME_EXTENSIONS.strip('\n').splitlines())
        return lines

    def _generate_runtime_constants(self, project: ProjectIR) -> List[str]:
        """生成资源目录、全局变量与监视器常量"""
        lines = []
        lines.append("try:")
        lines.append("    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))")
        lines.append("except NameError:")
        lines.append("    _SCRIPT_DIR = os.getcwd()")
        lines.append("ASSETS_DIR = _SCRIPT_DIR")

        stage_costume = ''
        backdrops = []
        if project.stage is not None and project.stage.costumes:
            stage_costume = (project.stage.costumes[0].get('md5ext') or
                             project.stage.costumes[0].get('name') or '')
            backdrops = [
                (costume.get('name', ''),
                 costume.get('md5ext') or costume.get('name', ''))
                for costume in project.stage.costumes
            ]
        lines.append(f"STAGE_COSTUME = {stage_costume!r}")
        lines.append(f"BACKDROPS = {backdrops!r}")
        lines.append(f"GLOBALS = {self.stage_globals!r}")
        lines.append("")

        monitors = []
        for monitor in project.monitors:
            if not monitor.get('visible'):
                continue
            owner = monitor.get('spriteName')
            params = monitor.get('params', {})
            if monitor.get('mode') == 'list' or monitor.get('opcode') == 'data_listcontents':
                name = str(params.get('LIST', ''))
                monitors.append({
                    'kind': 'list', 'name': name,
                    'sprite': owner,
                    # 局部列表按Scratch习惯加角色名前缀
                    'label': name if not owner or name.startswith(owner + ':')
                             else f"{owner}: {name}",
                    'attr': sanitize_name(name, 'lst'),
                    'x': monitor.get('x', 0), 'y': monitor.get('y', 0),
                    'width': monitor.get('width') or 200,
                    'height': monitor.get('height') or 150,
                })
            else:
                name = str(params.get('VARIABLE', ''))
                monitors.append({
                    'kind': 'var', 'name': name,
                    'sprite': owner,
                    # 局部变量按Scratch习惯加角色名前缀
                    'label': name if not owner or name.startswith(owner + ':')
                             else f"{owner}: {name}",
                    'attr': sanitize_name(name, 'var'),
                    'x': monitor.get('x', 0), 'y': monitor.get('y', 0),
                    'width': monitor.get('width') or 120,
                    'height': monitor.get('height') or 20,
                })
        lines.append(f"MONITORS = {monitors!r}")
        lines.append("")
        return lines

    def _generate_runtime_class(self) -> List[str]:
        """生成pygame运行时类"""
        return self.RUNTIME_CLASS.strip('\n').splitlines()

    def _generate_base_class(self) -> List[str]:
        """生成精灵基类"""
        return self.SPRITE_BASE.strip('\n').splitlines()

    # ===================== 自制积木命名 =====================

    def _build_procedure_names(self, sprite: SpriteIR):
        """为每个自制积木生成唯一方法名，并建立proccode -> 方法名映射"""
        self.procedure_names = {}
        used = set()
        for stmt in sprite.statements:
            if stmt.type != BlockType.PROCEDURE_DEFINE:
                continue
            key = stmt.extra.get('proccode') or stmt.extra.get('name') or 'procedure'
            base = sanitize_name(stmt.extra.get('name') or 'procedure', 'proc')
            name = base
            index = 2
            while name in used:
                name = f"{base}_{index}"
                index += 1
            used.add(name)
            self.procedure_names[key] = name
            stmt.extra['python_name'] = name

        mapping = dict(self.procedure_names)

        def resolver(proccode, fallback):
            return mapping.get(proccode, fallback)

        set_procedure_name_resolver(resolver)

    def _procedure_name(self, stmt: Statement) -> str:
        proccode = stmt.extra.get('proccode')
        if proccode and proccode in self.procedure_names:
            return self.procedure_names[proccode]
        return (stmt.extra.get('python_name') or
                sanitize_name(stmt.extra.get('name') or 'procedure', 'proc'))

    # ===================== 事件 =====================

    def _event_info(self, stmt: Statement):
        """返回 (方法名, docstring, 运行时事件key)"""
        if stmt.type == BlockType.WHEN_FLAG_CLICKED:
            return 'when_green_flag', '当绿旗被点击时', 'green_flag'
        if stmt.type == BlockType.WHEN_KEY_PRESSED:
            key = stmt.extra.get('key') or 'space'
            name = f"when_key_pressed_{key_to_identifier(key)}"
            return name, f'当按下{key}键时', f'key:{key}'
        if stmt.type == BlockType.WHEN_THIS_SPRITE_CLICKED:
            return 'when_clicked', '当角色被点击时', 'clicked'
        if stmt.type == BlockType.START_AS_CLONE:
            return 'when_clone_starts', '当作为克隆体启动时', 'clone_start'
        if stmt.type == BlockType.WHEN_BROADCAST_RECEIVED:
            msg = stmt.value.to_scratch_value() if stmt.value is not None else ''
            msg = str(msg)
            name = f"when_broadcast_{sanitize_name(msg, 'msg')}"
            # 反向解析依赖这句docstring恢复含空格的广播名
            return name, f"当接收到广播'{msg}'时", f'broadcast:{msg}'
        if stmt.type == BlockType.WHEN_BACKDROP_SWITCHES:
            backdrop = stmt.extra.get('backdrop') or 'backdrop1'
            name = f"when_backdrop_{sanitize_name(backdrop, 'backdrop')}"
            return name, f"当背景换成'{backdrop}'时", f'backdrop:{backdrop}'
        return None, None, None

    def _generate_event_handler(self, stmt: Statement,
                                name: Optional[str] = None,
                                doc: Optional[str] = None) -> List[str]:
        if name is None or doc is None:
            name, doc, _event = self._event_info(stmt)
        lines = [f"    def {name}(self):", f'        """{doc}"""']
        body = self._emit_chain(stmt.next, 2)
        if body:
            lines.extend(body)
        else:
            lines.append("        pass")
        lines.append("")
        return lines

    def _emit_chain(self, stmt: Optional[Statement], indent: int) -> List[str]:
        lines = []
        seen = set()
        while stmt is not None and id(stmt) not in seen:
            seen.add(id(stmt))
            lines.extend(self._generate_statement(stmt, indent))
            stmt = stmt.next
        return lines

    def _emit_body(self, body: List[Statement], indent: int) -> List[str]:
        lines = []
        for child in body:
            lines.extend(self._generate_statement(child, indent))
        return lines

    # ===================== 自制积木定义 =====================

    def _generate_procedure(self, stmt: Statement) -> List[str]:
        name = self._procedure_name(stmt)
        args = list(stmt.extra.get('args') or [])
        arg_types = list(stmt.extra.get('arg_types') or [])
        while len(arg_types) < len(args):
            arg_types.append('s')
        if len(arg_types) > len(args):
            arg_types = arg_types[:len(args)]

        python_args = []
        used = set()
        for index, arg in enumerate(args):
            base = f"arg_{sanitize_name(str(arg), 'arg')}"
            candidate = base
            suffix = 2
            while candidate in used:
                candidate = f"{base}_{suffix}"
                suffix += 1
            used.add(candidate)
            python_args.append(candidate)

        meta = [f"warp={bool(stmt.extra.get('warp'))}",
                f"arg_types={arg_types!r}", f"arg_names={args!r}"]
        proccode = stmt.extra.get('proccode')
        if proccode:
            meta.append(f"proccode={proccode!r}")
        arg_ids = stmt.extra.get('argumentids')
        if arg_ids:
            meta.append(f"arg_ids={list(arg_ids)!r}")
        arg_defaults = list(stmt.extra.get('argumentdefaults') or [])
        if arg_defaults:
            meta.append(f"arg_defaults={arg_defaults!r}")

        lines = [f"    @_as_procedure({', '.join(meta)})"]
        signature = ["self"]
        for index, python_arg in enumerate(python_args):
            # 与 Scratch 一致：未填参数取 definition 的 argumentdefaults，
            # 新建积木的默认值是空字符串（布尔为 False）。
            if index < len(arg_defaults):
                default = repr(arg_defaults[index])
            else:
                default = repr(False if arg_types[index] == 'b' else '')
            signature.append(f"{python_arg}={default}")
        lines.append(f"    def {name}({', '.join(signature)}):")
        title = proccode or stmt.extra.get('name') or 'procedure'
        lines.append(f'        """自制积木: {title}"""')
        body = self._emit_body(stmt.body, 2)
        if body:
            lines.extend(body)
        else:
            lines.append("        pass")
        lines.append("")
        return lines

    # ===================== 精灵类 =====================

    def _generate_sprite_class(self, sprite: SpriteIR) -> List[str]:
        """生成单个精灵的Python类"""
        self.current_sprite = sprite
        self._build_procedure_names(sprite)
        lines = []

        class_name = sanitize_name(sprite.name, "Sprite")
        lines.append(f"class {class_name}(ScratchSprite):")
        lines.append(f'    """精灵: {sprite.name}"""')
        lines.append("")

        local_names = {sanitize_name(name, 'var') for name in sprite.variables}
        local_names |= {sanitize_name(name, 'lst') for name in sprite.lists}
        if sprite.is_stage:
            # 舞台声明的是Scratch全局变量/列表，必须全部走共享GLOBALS
            global_names = tuple(sorted(self.global_names))
        else:
            global_names = tuple(sorted(self.global_names - local_names))
        lines.append(f"    GLOBAL_NAMES = {global_names!r}")
        lines.append("    GLOBAL_NAMES_SET = frozenset(GLOBAL_NAMES)")
        lines.append("")

        lines.append("    def __init__(self):")
        lines.append("        super().__init__()")
        lines.append(f"        self.x = {sprite.x!r}")
        lines.append(f"        self.y = {sprite.y!r}")
        lines.append(f"        self.direction = {sprite.direction!r}")
        lines.append(f"        self.visible = {sprite.visible!r}")
        lines.append(f"        self.size = {sprite.size!r}")
        lines.append(f"        self.name = {sprite.name!r}")
        if sprite.is_stage:
            lines.append("        self.is_stage = True")
        lines.append(f"        self.rotation_style = {sprite.rotation_style!r}")
        lines.append(f"        self.draggable = {bool(sprite.draggable)!r}")
        costumes = [
            {
                'name': costume.get('name', ''),
                'md5ext': costume.get('md5ext', ''),
                'dataFormat': costume.get('dataFormat', ''),
                'rotationCenterX': costume.get('rotationCenterX'),
                'rotationCenterY': costume.get('rotationCenterY'),
            }
            for costume in sprite.costumes
        ]
        lines.append(f"        self.costumes = {costumes!r}")
        sounds = [
            {'name': sound.get('name', ''), 'md5ext': sound.get('md5ext', '')}
            for sound in sprite.sounds
        ]
        lines.append(f"        self.sounds = {sounds!r}")
        lines.append(f"        self.costume_number = {sprite.current_costume + 1}")
        if costumes:
            index = sprite.current_costume % len(costumes)
            lines.append(f"        self.costume_name = {costumes[index]['name']!r}")
        lines.append("")

        if not sprite.is_stage:
            for name, value in sprite.variables.items():
                lines.append(f"        self.{sanitize_name(name, 'var')} = {value!r}")
            if sprite.variables:
                lines.append("")

            for name, items in sprite.lists.items():
                lines.append(f"        self.{sanitize_name(name, 'lst')} = {list(items)!r}")
            if sprite.lists:
                lines.append("")

        for stmt in sprite.statements:
            if stmt.type == BlockType.PROCEDURE_DEFINE:
                lines.extend(self._generate_procedure(stmt))
                lines.append("")

        # 同一帽子事件可以有多个并列脚本，必须各自生成独立方法并全部注册
        event_entries = self._collect_event_entries(sprite)
        for stmt, name, doc, _event in event_entries:
            lines.extend(self._generate_event_handler(stmt, name, doc))
            lines.append("")

        lines.extend(self._generate_run_method(event_entries))
        return lines

    def _collect_event_entries(self, sprite: SpriteIR):
        """为每个事件脚本分配唯一方法名（重复帽子事件加 _2/_3 后缀）"""
        entries = []
        used = set()
        for stmt in sprite.statements:
            base, doc, event = self._event_info(stmt)
            if not base or not event:
                continue
            name = base
            index = 2
            while name in used:
                name = f"{base}_{index}"
                index += 1
            used.add(name)
            entries.append((stmt, name, doc, event))
        return entries

    def _generate_run_method(self, event_entries) -> List[str]:
        lines = ["    def run(self):", '        """向运行时注册事件脚本"""']
        if not event_entries:
            lines.append("        pass")
            return lines
        for _stmt, name, _doc, event in event_entries:
            lines.append(f"        self._register({event!r}, self.{name})")
        return lines

    # ===================== 语句 =====================

    def _generate_statement(self, stmt: Statement, indent: int) -> List[str]:
        spaces = "    " * indent

        if stmt.type == BlockType.MOVE_STEPS:
            value = stmt.value.to_python_source() if stmt.value else "10"
            return [f"{spaces}self.move({value})"]

        if stmt.type == BlockType.TURN_RIGHT:
            value = stmt.value.to_python_source() if stmt.value else "15"
            return [f"{spaces}self.turn_right({value})"]

        if stmt.type == BlockType.TURN_LEFT:
            value = stmt.value.to_python_source() if stmt.value else "15"
            return [f"{spaces}self.turn_left({value})"]

        if stmt.type == BlockType.GO_TO_XY:
            x = stmt.extra.get('x', Expr(ExprType.NUMBER, 0)).to_python_source()
            y = stmt.extra.get('y', Expr(ExprType.NUMBER, 0)).to_python_source()
            return [f"{spaces}self.goto_xy({x}, {y})"]

        if stmt.type == BlockType.GO_TO_RANDOM:
            target = stmt.extra.get('target', '_random_')
            return [f"{spaces}self.goto_target({target!r})"]

        if stmt.type == BlockType.GLIDE_TO:
            secs = stmt.value.to_python_source() if stmt.value else "1"
            target = stmt.extra.get('target', '_random_')
            return [f"{spaces}self.glide_to_target({secs}, {target!r})"]

        if stmt.type == BlockType.POINT_IN_DIRECTION:
            value = stmt.value.to_python_source() if stmt.value else "90"
            return [f"{spaces}self.point_in_direction({value})"]

        if stmt.type == BlockType.POINT_TOWARDS:
            target = stmt.extra.get('target', '_mouse_')
            return [f"{spaces}self.point_towards({target!r})"]

        if stmt.type == BlockType.SET_ROTATION_STYLE:
            style = stmt.extra.get('style', 'all around')
            return [f"{spaces}self.set_rotation_style({style!r})"]

        if stmt.type == BlockType.GLIDE_SECS_TO:
            secs = stmt.value.to_python_source() if stmt.value else "1"
            x = stmt.extra.get('x', Expr(ExprType.NUMBER, 0)).to_python_source()
            y = stmt.extra.get('y', Expr(ExprType.NUMBER, 0)).to_python_source()
            return [f"{spaces}self.glide_to({secs}, {x}, {y})"]

        if stmt.type == BlockType.SET_X:
            value = stmt.value.to_python_source() if stmt.value else "0"
            return [f"{spaces}self.set_x({value})"]

        if stmt.type == BlockType.SET_Y:
            value = stmt.value.to_python_source() if stmt.value else "0"
            return [f"{spaces}self.set_y({value})"]

        if stmt.type == BlockType.CHANGE_X:
            value = stmt.value.to_python_source() if stmt.value else "10"
            return [f"{spaces}self.change_x({value})"]

        if stmt.type == BlockType.CHANGE_Y:
            value = stmt.value.to_python_source() if stmt.value else "10"
            return [f"{spaces}self.change_y({value})"]

        if stmt.type == BlockType.IF_ON_EDGE_BOUNCE:
            return [f"{spaces}self.if_on_edge_bounce()"]

        if stmt.type == BlockType.SAY:
            value = stmt.value.to_python_source() if stmt.value else "''"
            return [f"{spaces}self.say({value})"]

        if stmt.type == BlockType.SAY_FOR_SECS:
            message = stmt.extra.get('message', Expr(ExprType.STRING, '')).to_python_source()
            secs = stmt.value.to_python_source() if stmt.value else "1"
            return [f"{spaces}self.say_for({message}, {secs})"]

        if stmt.type == BlockType.THINK:
            value = stmt.value.to_python_source() if stmt.value else "''"
            return [f"{spaces}self.think({value})"]

        if stmt.type == BlockType.THINK_FOR_SECS:
            message = stmt.extra.get('message', Expr(ExprType.STRING, '')).to_python_source()
            secs = stmt.value.to_python_source() if stmt.value else "1"
            return [f"{spaces}self.think_for({message}, {secs})"]

        if stmt.type == BlockType.SHOW:
            return [f"{spaces}self.show()"]

        if stmt.type == BlockType.HIDE:
            return [f"{spaces}self.hide()"]

        if stmt.type == BlockType.SWITCH_COSTUME:
            value = stmt.value.to_python_source() if stmt.value else "'costume1'"
            return [f"{spaces}self.switch_costume({value})"]

        if stmt.type == BlockType.NEXT_COSTUME:
            return [f"{spaces}self.next_costume()"]

        if stmt.type == BlockType.CHANGE_SIZE:
            value = stmt.value.to_python_source() if stmt.value else "10"
            return [f"{spaces}self.change_size({value})"]

        if stmt.type == BlockType.SET_SIZE:
            value = stmt.value.to_python_source() if stmt.value else "100"
            return [f"{spaces}self.set_size({value})"]

        if stmt.type == BlockType.CHANGE_EFFECT:
            effect = stmt.extra.get('effect', 'color')
            value = stmt.value.to_python_source() if stmt.value else "25"
            return [f"{spaces}self.change_effect({effect!r}, {value})"]

        if stmt.type == BlockType.SET_EFFECT:
            effect = stmt.extra.get('effect', 'color')
            value = stmt.value.to_python_source() if stmt.value else "100"
            return [f"{spaces}self.set_effect({effect!r}, {value})"]

        if stmt.type == BlockType.CLEAR_EFFECTS:
            return [f"{spaces}self.clear_effects()"]

        if stmt.type == BlockType.PLAY_SOUND:
            value = stmt.value.to_python_source() if stmt.value else "'sound1'"
            return [f"{spaces}self.play_sound({value})"]

        if stmt.type == BlockType.PLAY_SOUND_UNTIL_DONE:
            value = stmt.value.to_python_source() if stmt.value else "'sound1'"
            return [f"{spaces}self.play_sound({value}, wait=True)"]

        if stmt.type == BlockType.STOP_ALL_SOUNDS:
            return [f"{spaces}self.stop_all_sounds()"]

        if stmt.type == BlockType.CHANGE_VOLUME:
            value = stmt.value.to_python_source() if stmt.value else "10"
            return [f"{spaces}self.change_volume({value})"]

        if stmt.type == BlockType.SET_VOLUME:
            value = stmt.value.to_python_source() if stmt.value else "100"
            return [f"{spaces}self.set_volume({value})"]

        if stmt.type == BlockType.WAIT:
            value = stmt.value.to_python_source() if stmt.value else "1"
            return [f"{spaces}self.wait({value})"]

        if stmt.type == BlockType.REPEAT:
            times = stmt.value.to_python_source() if stmt.value else "10"
            lines = [f"{spaces}for _repeat in range(_sc_repeat_count({times})):"]
            body = self._emit_body(stmt.body, indent + 1)
            lines.extend(body if body else [f"{spaces}    pass"])
            lines.append(f"{spaces}    self._yield_frame()")
            return lines

        if stmt.type == BlockType.FOREVER:
            lines = [f"{spaces}while self._running:"]
            body = self._emit_body(stmt.body, indent + 1)
            lines.extend(body if body else [f"{spaces}    pass"])
            lines.append(f"{spaces}    self._yield_frame()")
            return lines

        if stmt.type == BlockType.IF:
            condition = stmt.condition.to_python_source() if stmt.condition else "True"
            lines = [f"{spaces}if _sc_bool({condition}):"]
            body = self._emit_body(stmt.body, indent + 1)
            lines.extend(body if body else [f"{spaces}    pass"])
            return lines

        if stmt.type == BlockType.IF_ELSE:
            condition = stmt.condition.to_python_source() if stmt.condition else "True"
            lines = [f"{spaces}if _sc_bool({condition}):"]
            body = self._emit_body(stmt.body, indent + 1)
            lines.extend(body if body else [f"{spaces}    pass"])
            lines.append(f"{spaces}else:")
            else_body = self._emit_body(stmt.else_body, indent + 1)
            lines.extend(else_body if else_body else [f"{spaces}    pass"])
            return lines

        if stmt.type == BlockType.WAIT_UNTIL:
            condition = stmt.condition.to_python_source() if stmt.condition else "True"
            return [f"{spaces}self.wait_until(lambda: _sc_bool({condition}))"]

        if stmt.type == BlockType.REPEAT_UNTIL:
            condition = stmt.condition.to_python_source() if stmt.condition else "False"
            lines = [f"{spaces}while not _sc_bool({condition}):"]
            body = self._emit_body(stmt.body, indent + 1)
            lines.extend(body if body else [f"{spaces}    pass"])
            lines.append(f"{spaces}    self._yield_frame()")
            return lines

        if stmt.type == BlockType.STOP:
            option = stmt.extra.get('option', 'all')
            return [f"{spaces}self.stop({option!r})"]

        if stmt.type == BlockType.CREATE_CLONE_OF:
            value = stmt.value.to_python_source() if stmt.value else "'_myself_'"
            return [f"{spaces}self.create_clone_of({value})"]

        if stmt.type == BlockType.DELETE_THIS_CLONE:
            return [f"{spaces}self.delete_this_clone()"]

        if stmt.type == BlockType.ASK_AND_WAIT:
            value = stmt.value.to_python_source() if stmt.value else "''"
            return [f"{spaces}self.ask_and_wait({value})"]

        if stmt.type == BlockType.RESET_TIMER:
            return [f"{spaces}self.reset_timer()"]

        if stmt.type == BlockType.SET_VARIABLE:
            name = sanitize_name(stmt.extra.get('name') or 'var', 'var')
            value = stmt.value.to_python_source() if stmt.value else "0"
            return [f"{spaces}self.{name} = {value}"]

        if stmt.type == BlockType.CHANGE_VARIABLE:
            name = sanitize_name(stmt.extra.get('name') or 'var', 'var')
            value = stmt.value.to_python_source() if stmt.value else "1"
            return [f"{spaces}self.{name} = _sc_add(self.{name}, {value})"]

        if stmt.type == BlockType.ADD_TO_LIST:
            name = sanitize_name(stmt.extra.get('name') or 'list', 'lst')
            item = stmt.value.to_python_source() if stmt.value else "''"
            return [f"{spaces}self.{name}.append({item})"]

        if stmt.type == BlockType.DELETE_FROM_LIST:
            name = sanitize_name(stmt.extra.get('name') or 'list', 'lst')
            index = stmt.value.to_python_source() if stmt.value else "1"
            return [f"{spaces}_sc_list_delete(self.{name}, {index})"]

        if stmt.type == BlockType.DELETE_ALL_FROM_LIST:
            name = sanitize_name(stmt.extra.get('name') or 'list', 'lst')
            return [f"{spaces}self.{name}.clear()"]

        if stmt.type == BlockType.INSERT_IN_LIST:
            name = sanitize_name(stmt.extra.get('name') or 'list', 'lst')
            item = stmt.extra.get('item', Expr(ExprType.STRING, '')).to_python_source()
            index = stmt.value.to_python_source() if stmt.value else "1"
            return [f"{spaces}_sc_list_insert(self.{name}, {index}, {item})"]

        if stmt.type == BlockType.REPLACE_IN_LIST:
            name = sanitize_name(stmt.extra.get('name') or 'list', 'lst')
            item = stmt.extra.get('item', Expr(ExprType.STRING, '')).to_python_source()
            index = stmt.value.to_python_source() if stmt.value else "1"
            return [f"{spaces}_sc_list_replace(self.{name}, {index}, {item})"]

        if stmt.type == BlockType.SHOW_VARIABLE:
            return [f"{spaces}self.show_variable({str(stmt.extra.get('name', 'var'))!r})"]

        if stmt.type == BlockType.HIDE_VARIABLE:
            return [f"{spaces}self.hide_variable({str(stmt.extra.get('name', 'var'))!r})"]

        if stmt.type == BlockType.SHOW_LIST:
            return [f"{spaces}self.show_list({str(stmt.extra.get('name', 'list'))!r})"]

        if stmt.type == BlockType.HIDE_LIST:
            return [f"{spaces}self.hide_list({str(stmt.extra.get('name', 'list'))!r})"]

        if stmt.type == BlockType.BROADCAST:
            value = stmt.value.to_python_source() if stmt.value else "''"
            return [f"{spaces}self.broadcast({value})"]

        if stmt.type == BlockType.BROADCAST_AND_WAIT:
            value = stmt.value.to_python_source() if stmt.value else "''"
            return [f"{spaces}self.broadcast_and_wait({value})"]

        if stmt.type == BlockType.PROCEDURE_CALL:
            name = self._procedure_name(stmt)
            call_args = stmt.extra.get('args', [])
            args_str = ", ".join(a.to_python_source() for a in call_args)
            return [f"{spaces}self.{name}({args_str})"]

        if stmt.type == BlockType.PROCEDURE_RETURN:
            if stmt.value is not None:
                return [f"{spaces}return {stmt.value.to_python_source()}"]
            return [f"{spaces}return"]

        if stmt.type == BlockType.EXTENSION:
            inputs = ', '.join(
                f"{key!r}: {value.to_python_source()}"
                for key, value in stmt.extra.get('inputs', []))
            lines = [f"{spaces}self.extension("
                     f"{stmt.extra.get('namespace', '')!r}, "
                     f"{stmt.extra.get('opcode', '')!r}, "
                     f"{{{inputs}}}, {stmt.extra.get('fields', {})!r})"]
            lines.extend(self._emit_body(stmt.body, indent))
            return lines

        if stmt.type == BlockType.COMMENT:
            return [f"{spaces}# {stmt.extra.get('text', '')}"]

        if stmt.type == BlockType.SWITCH_BACKDROP:
            value = stmt.value.to_python_source() if stmt.value else "'backdrop1'"
            return [f"{spaces}self.set_backdrop({value})"]

        if stmt.type == BlockType.SWITCH_BACKDROP_AND_WAIT:
            value = stmt.value.to_python_source() if stmt.value else "'backdrop1'"
            return [f"{spaces}self.set_backdrop_and_wait({value})"]

        if stmt.type == BlockType.NEXT_BACKDROP:
            return [f"{spaces}self.next_backdrop()"]

        if stmt.type in (BlockType.GO_TO_FRONT, BlockType.GO_TO_BACK):
            where = stmt.extra.get('where', 'front')
            return [f"{spaces}self.go_to_layer({where!r})"]

        if stmt.type in (BlockType.GO_FORWARD_LAYERS, BlockType.GO_BACKWARD_LAYERS):
            direction = stmt.extra.get('direction', 'forward')
            value = stmt.value.to_python_source() if stmt.value else "1"
            sign = "-" if str(direction).lower().startswith('back') else ""
            return [f"{spaces}self.change_layer({sign}_sc_num({value}))"]

        if stmt.type == BlockType.SET_DRAG_MODE:
            mode = stmt.extra.get('mode', 'draggable')
            return [f"{spaces}self.set_drag_mode({mode!r})"]

        if stmt.type in (BlockType.SET_SOUND_EFFECT,
                         BlockType.CHANGE_SOUND_EFFECT):
            effect = stmt.extra.get('effect', 'PITCH')
            value = stmt.value.to_python_source() if stmt.value else "10"
            method = ('set_sound_effect' if stmt.type == BlockType.SET_SOUND_EFFECT
                      else 'change_sound_effect')
            return [f"{spaces}self.{method}({effect!r}, {value})"]

        if stmt.type == BlockType.CLEAR_SOUND_EFFECTS:
            return [f"{spaces}self.clear_sound_effects()"]

        if stmt.type == BlockType.FOR_EACH:
            name = sanitize_name(stmt.extra.get('name') or 'item', 'var')
            items = stmt.value.to_python_source() if stmt.value else "[]"
            lines = [f"{spaces}for _each in _sc_list_values({items}):",
                     f"{spaces}    self.{name} = _each"]
            body = self._emit_body(stmt.body, indent + 1)
            lines.extend(body if body else [f"{spaces}    pass"])
            lines.append(f"{spaces}    self._yield_frame()")
            return lines

        if stmt.type == BlockType.ALL_AT_ONCE:
            return self._emit_body(stmt.body, indent)

        if stmt.type == BlockType.INCR_COUNTER:
            return [f"{spaces}self.incr_counter()"]

        if stmt.type == BlockType.CLEAR_COUNTER:
            return [f"{spaces}self.clear_counter()"]

        return [f"{spaces}# TODO: {stmt.type.name}"]

    # ===================== main =====================

    def _generate_main(self, project: ProjectIR) -> List[str]:
        """生成主函数：启动pygame运行时，支持多种调试参数"""
        lines = []
        lines.append("def main(argv=None):")
        lines.append('    """启动Scratch 3.0 pygame运行时"""')
        lines.append("    parser = argparse.ArgumentParser(description='Scratch 3.0 runtime')")
        lines.append("    parser.add_argument('--headless', action='store_true', help='无窗口模式')")
        lines.append("    parser.add_argument('--frames', type=int, help='运行指定帧数后退出')")
        lines.append("    parser.add_argument('--seconds', type=float, help='运行指定秒数后退出')")
        lines.append("    parser.add_argument('--fps', type=int, help='覆盖帧率')")
        lines.append("    parser.add_argument('--seed', type=int, help='随机种子')")
        lines.append("    parser.add_argument('--trace', action='store_true', help='打印事件/脚本/过程调用')")
        lines.append("    parser.add_argument('--no-audio', action='store_true', help='禁用声音')")
        lines.append("    parser.add_argument('--assets', help='覆盖素材目录')")
        lines.append("    parser.add_argument('--interpolation', action='store_true', help='TurboWarp插值')")
        lines.append("    parser.add_argument('--turbo', action='store_true', help='Turbo模式')")
        lines.append("    parser.add_argument('--no-fencing', dest='fencing', action='store_false', help='移除舞台边界限制')")
        lines.append("    parser.add_argument('--infinite-clones', action='store_true', help='解除克隆体数量限制')")
        lines.append("    parser.add_argument('--remove-misc-limits', dest='misc_limits', action='store_false', help='移除杂项限制')")
        lines.append("    parser.add_argument('--stage-size', help='自定义舞台尺寸，如 640x360')")
        lines.append("    parser.add_argument('--hq-pen', action='store_true', help='高质量画笔')")
        lines.append("    parser.add_argument('--warp-timer', type=float, default=0.5, help='warp模式超时秒数')")
        lines.append("    parser.add_argument('--disable-compiler', action='store_true', help='兼容参数（无操作）')")
        lines.append("    parser.add_argument('--windowed', action='store_true', help='以普通窗口启动（默认自动最大化）')")
        # TurboWarp把高级选项保存在 project.json 的 _twconfig_ 注释里
        options = project.runtime_options or {}
        runtime_options = options.get('runtimeOptions') or {}

        def tw_value(name, default=None):
            if name in options:
                return options[name]
            return runtime_options.get(name, default)

        framerate = tw_value('framerate', tw_value('fps'))
        if framerate:
            lines.append(f"    parser.set_defaults(fps={int(float(framerate))})")
        if tw_value('fencing', True) is False:
            lines.append("    parser.set_defaults(fencing=False)")
        if tw_value('miscLimits', True) is False:
            lines.append("    parser.set_defaults(misc_limits=False)")
        if tw_value('interpolation', False):
            lines.append("    parser.set_defaults(interpolation=True)")
        if tw_value('turbo', False):
            lines.append("    parser.set_defaults(turbo=True)")
        if tw_value('hqPen', False):
            lines.append("    parser.set_defaults(hq_pen=True)")
        if tw_value('compiler', True) is False:
            lines.append("    parser.set_defaults(disable_compiler=True)")
        clone_limit = tw_value('cloneLimit')
        if clone_limit is not None:
            try:
                if int(clone_limit) <= 0:
                    lines.append("    parser.set_defaults(infinite_clones=True)")
            except (TypeError, ValueError):
                pass
        warp_timer = tw_value('warpTimer')
        if warp_timer is not None:
            lines.append(f"    parser.set_defaults(warp_timer={float(warp_timer)!r})")
        stage_width = tw_value('stageWidth')
        stage_height = tw_value('stageHeight')
        if stage_width and stage_height:
            lines.append(
                f"    parser.set_defaults(stage_size='{int(float(stage_width))}x"
                f"{int(float(stage_height))}')")
        lines.append("    args = parser.parse_args(argv)")
        lines.append("    if args.seed is not None:")
        lines.append("        random.seed(args.seed)")
        lines.append("    stage_size = None")
        lines.append("    if args.stage_size:")
        lines.append("        try:")
        lines.append("            width, height = args.stage_size.lower().split('x')")
        lines.append("            stage_size = (int(width), int(height))")
        lines.append("        except ValueError:")
        lines.append("            parser.error('--stage-size 格式应为 WIDTHxHEIGHT')")
        lines.append("    runtime = ScratchRuntime(")
        lines.append("        headless=args.headless, fps=args.fps, trace=args.trace,")
        lines.append("        audio=not args.no_audio, assets_dir=args.assets,")
        lines.append("        interpolation=args.interpolation, turbo=args.turbo,")
        lines.append("        fencing=args.fencing, infinite_clones=args.infinite_clones,")
        lines.append("        misc_limits=args.misc_limits, hq_pen=args.hq_pen,")
        lines.append("        stage_size=stage_size, warp_timer=args.warp_timer,")
        lines.append("        disable_compiler=args.disable_compiler,")
        lines.append("        maximize=not args.windowed)")
        lines.append("")

        # 实例名必须避开类名和 main() 里的局部变量名。
        # 中文/无大小写的角色名（如“角色1”）lower() 后与类名相同，
        # 直接写 `角色1 = 角色1()` 会触发 UnboundLocalError。
        reserved_names = {'parser', 'args', 'runtime', 'stage_size',
                          'width', 'height'}
        class_names = {sanitize_name(item.name, "Sprite")
                       for item in project.sprites}
        used_instances = set()
        for sprite in project.sprites:
            safe_class = sanitize_name(sprite.name, "Sprite")
            instance = sanitize_name(sprite.name.lower(), "inst")
            if instance == safe_class or instance in class_names \
                    or instance in reserved_names:
                instance = f'inst_{instance}'
            while instance in used_instances or instance in class_names \
                    or instance in reserved_names:
                instance = f'{instance}_'
            used_instances.add(instance)
            lines.append(f"    {instance} = {safe_class}()")
            lines.append(f"    runtime.add_sprite({instance})")

        lines.append("")
        lines.append("    try:")
        lines.append("        runtime.start(max_frames=args.frames, max_seconds=args.seconds)")
        lines.append("    except KeyboardInterrupt:")
        lines.append("        pass")
        lines.append("    finally:")
        lines.append("        runtime.shutdown()")
        lines.append("")
        lines.append("")
        lines.append('if __name__ == "__main__":')
        lines.append("    main()")
        return lines


def generate_python(project: ProjectIR) -> str:
    """便捷函数：生成Python代码"""
    gen = PythonGenerator()
    return gen.generate_project(project)


def save_python(project: ProjectIR, file_path: str):
    """将Python代码保存到文件"""
    code = generate_python(project)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(code)
