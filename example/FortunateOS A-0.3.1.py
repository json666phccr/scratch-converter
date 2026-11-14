# -*- coding: utf-8 -*-
"""
Scratch 3.0 / TurboWarp -> Python 转换代码
由 scratch-converter 自动生成
"""

import math
import time
import random
import re
import array
import decimal
import os
import io
import argparse
import threading

try:
    import pygame
except ImportError:
    pygame = None

_SCRATCH_LIST_LIMIT = 200000


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
        return float(value)
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
    index = _sc_num(index) - 1
    text = _sc_str(string)
    if isinstance(index, float) and (math.isnan(index) or math.isinf(index)):
        return ''
    position = int(index)
    if position < 0 or position >= len(text):
        return ''
    return text[position]


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

try:
    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _SCRIPT_DIR = os.getcwd()
ASSETS_DIR = _SCRIPT_DIR
STAGE_COSTUME = '6a88e1d3600bb7b42af5713457c3ba0a.svg'
BACKDROPS = [('背景1', '6a88e1d3600bb7b42af5713457c3ba0a.svg'), ('背景3', '68bae05e4640b516482504cca8c7b3f1.svg'), ('背景2', '0cf937411065782c37618a3bbf1c1529.svg'), ('背景4', '3c810ea9e6f21e8734124357c1c0cb4d.svg'), ('背景5', 'be2de2bf8c0d4a4d5a5e3967bf3ae995.svg'), ('背景6', 'fd2360d34bc7561f5f63af2ccc17886b.svg'), ('背景7', '239f73b1714687feccf57d87b9e80b15.svg'), ('背景8', '0d5fee369f5b01c31312fd4b99a5cb59.svg'), ('背景9', '8e97f5261bd5a1b8d9f29d843305741f.svg'), ('背景10', 'a54f8189b40539e721763664dff07631.svg'), ('背景11', '2c44ba5df0f7c5fdbbdaccfedb8dd96d.svg'), ('背景12', '33f6a41df64e2232161cd863b951eeb5.svg')]
GLOBALS = {'我的变量': 0, 'FortunateOS_系统版本号': 'A-0.3.0 - 0013', 'FortunateOS_当前主题': 'fos', 'FortunateOS_分配窗口ID': 1, 'FortunateOS_鼠标是否被占用_': '0', 'FortunateOS_开始菜单是否被开启_': '0', 'FortunateOS_是否开启锁屏_': 0, '任务栏动画_i': 0, 'FortunateOS_当前是否进入桌面': '1', 'FortunateOS_窗口图层管理': [], 'FortunateOS_窗口ID管理': [1], 'FortunateOS_窗口大小管理': [], 'FortunateOS_窗口组件管理': [], 'FortunateOS_窗口坐标管理': [], 'FortunateOS_窗口图层偏移': ['', '0'], 'FortunateOS_全部主题名称': ['fos', 'os1'], 'FortunateOS_文件路径管理': ['C:/', 'C:/1/', 'C:/1/2/', 'C:/1/2/3/', 'C:/1/2/3/4/', 'C:/1/2/3/4/5/', 'C:/1/2/3/4/5/6/', 'C:/1/2/3/4/5/6/7/'], 'FortunateOS_文件内容管理': ['/', '/', '/', '/', '/', '/', '/', '/'], 'FortunateOS_文件系统执行': [], 'FortunateOS_窗口系统执行': [], 'FortunateOS_管理设置选项': ['标题栏颜色', '65', '标题栏透明度', '60', '标题栏亮度', '75'], 'FortunateOS_文件属性管理': ['/', '/', '/', '/', '/', '/', '/', '/'], 'FortunateOS_命令系统执行': [], 'FortunateOS_命令系统权限': [], 'FortunateOS_中转系统执行': [], 'FortunateOS_中转系统返回': [''], 'FortunateOS_中转执行类型': [], 'FortunateOS_文件执行类型': [], 'FortunateOS_文件系统返回': ['[100]'], 'FortunateOS_文件系统属性': []}

MONITORS = []

class ScratchRuntime:
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
        pygame.display.set_caption("Scratch 3.0 Runtime (ESC 退出，可自由拉伸窗口)")
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
        self.counter = 0
        self.dragging = None
        self.dragging_offset = (0, 0)
        self.ask_pending = False
        self.ask_question = ''
        self.ask_buffer = ''
        self.ask_answer = ''
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
            self.screen = pygame.display.set_mode((width, height))
            self.stage_surface = self.screen
            return
        try:
            self.screen = pygame.display.set_mode(
                (width, height), pygame.RESIZABLE)
        except pygame.error:
            self.screen = pygame.display.set_mode((width, height))
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
        """返回 (缩放比, 黑边偏移, 绘制尺寸)"""
        window_width, window_height = self.screen.get_size()
        if window_width <= 0 or window_height <= 0:
            return 1.0, (0, 0), (self.stage_width, self.stage_height)
        scale = min(window_width / float(self.stage_width),
                    window_height / float(self.stage_height))
        draw_width = max(1, int(self.stage_width * scale))
        draw_height = max(1, int(self.stage_height * scale))
        return (draw_width / float(self.stage_width),
                ((window_width - draw_width) // 2,
                 (window_height - draw_height) // 2),
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
        pygame.display.flip()

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
        image = sprite._costume_surface()
        x = int(self.stage_width / 2 + _sc_num(sprite.x))
        y = int(self.stage_height / 2 - _sc_num(sprite.y))
        scale = max(1.0, _sc_num(sprite.size)) / 100.0
        if image is not None:
            angle = 90 - _sc_num(sprite.direction)
            if sprite.rotation_style in ('left-right', "don't rotate"):
                angle = 0
            if angle == 0 and scale == 1.0:
                transformed = image
            else:
                transformed = pygame.transform.rotozoom(image, angle, scale)
            if sprite.rotation_style == 'left-right' \
                    and math.cos(math.radians(_sc_num(sprite.direction))) < 0:
                transformed = pygame.transform.flip(transformed, True, False)
            self.pen_layer.blit(transformed, transformed.get_rect(center=(x, y)))
        else:
            pygame.draw.circle(self.pen_layer, sprite._placeholder_color(),
                               (x, y), max(6, int(20 * scale)))

    def add_sprite(self, sprite):
        sprite._runtime = self
        self.sprites.append(sprite)

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

    def ask(self, question):
        """在舞台上显示输入框并等待玩家输入"""
        self.ask_question = _sc_str(question)
        self.ask_buffer = ''
        self.ask_answer = ''
        self.ask_pending = True
        while self.running and self.ask_pending:
            self.wait_frame()
        self.ask_pending = False
        self.ask_question = ''
        return self.ask_answer

    def _draw_ask(self):
        if not self.ask_pending:
            return
        rect = pygame.Rect(20, self.stage_height - 60,
                           max(80, self.stage_width - 40), 40)
        pygame.draw.rect(self.stage_surface, (255, 255, 255), rect, border_radius=6)
        pygame.draw.rect(self.stage_surface, (90, 90, 90), rect, 1, border_radius=6)
        text = self.ask_question + ' ' + self.ask_buffer + '_'
        surface = self.font.render(text, True, (30, 30, 30))
        self.stage_surface.blit(surface, (rect.x + 8, rect.y + 11))

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
        x, y = self._window_to_stage(pos)
        return (int(round(x)) - self.stage_width // 2,
                self.stage_height // 2 - int(round(y)))

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
        stage_pos = self._window_to_stage(pos)
        if stage_pos[0] < 28 and stage_pos[1] < 28:
            self.green_flag()
            return
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
            if event.type == pygame.QUIT:
                self.running = False
                return
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                    return
                if self.ask_pending:
                    if event.key == pygame.K_RETURN:
                        self.ask_answer = self.ask_buffer
                        self.ask_pending = False
                    elif event.key == pygame.K_BACKSPACE:
                        self.ask_buffer = self.ask_buffer[:-1]
                    elif event.unicode and event.unicode.isprintable():
                        self.ask_buffer += event.unicode
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
                self.keys.discard(self._key_name(event.key))
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.mouse_down = True
                self.mouse_x, self.mouse_y = self._screen_to_scratch(event.pos)
                self._start_drag(event.pos)
                self._handle_click(event.pos)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
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
        if self.background is not None:
            self.stage_surface.blit(self.background, (0, 0))
        else:
            self.stage_surface.fill((247, 247, 247))
        self.stage_surface.blit(self.pen_layer, (0, 0))
        pygame.draw.polygon(self.stage_surface, (60, 170, 90),
                            [(8, 22), (8, 6), (22, 6), (22, 12), (8, 12)])
        for sprite in list(self.sprites):
            if sprite.visible and not getattr(sprite, 'is_stage', False):
                sprite._draw(self.stage_surface, self.font)
        self._draw_monitors()
        self._draw_ask()

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
                self.step()
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

class ScratchSprite:
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

    def _apply_fencing(self):
        if self._runtime is None or not self._runtime.fencing:
            return
        half = max(1.0, 20 * abs(_sc_num(self.size)) / 100.0)
        limit_x = max(1.0, self._runtime.stage_width / 2 - half)
        limit_y = max(1.0, self._runtime.stage_height / 2 - half)
        self.x = max(-limit_x, min(limit_x, _sc_num(self.x)))
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
            self.answer = self._runtime.ask(question)
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

    def _draw(self, screen, font):
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
        if image is not None:
            angle = 90 - draw_direction
            if self.rotation_style in ('left-right', "don't rotate"):
                angle = 0
            color_effect = _sc_num(self._effects.get('color', 0))
            brightness = _sc_num(self._effects.get('brightness', 0))
            ghost = max(0.0, min(100.0, _sc_num(self._effects.get('ghost', 0))))
            # 颜色/亮度特效很耗CPU，按(造型Surface, 特效值)缓存；特效值不变时直接复用
            base = image
            if color_effect and self._runtime is not None:
                base = self._color_effect_image(image, color_effect)
            if brightness and self._runtime is not None:
                base = self._brightness_image(base, brightness)
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
            screen.blit(transformed, rect)
        else:
            radius = max(6, int(20 * scale))
            pygame.draw.circle(screen, self._placeholder_color(), (x, y), radius)
            end = (x + int(math.sin(math.radians(draw_direction)) * radius),
                   y - int(math.cos(math.radians(draw_direction)) * radius))
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

class Stage(ScratchSprite):
    """精灵: Stage"""

    GLOBAL_NAMES = ('FortunateOS_中转执行类型', 'FortunateOS_中转系统执行', 'FortunateOS_中转系统返回', 'FortunateOS_全部主题名称', 'FortunateOS_分配窗口ID', 'FortunateOS_命令系统执行', 'FortunateOS_命令系统权限', 'FortunateOS_开始菜单是否被开启_', 'FortunateOS_当前主题', 'FortunateOS_当前是否进入桌面', 'FortunateOS_文件内容管理', 'FortunateOS_文件属性管理', 'FortunateOS_文件执行类型', 'FortunateOS_文件系统属性', 'FortunateOS_文件系统执行', 'FortunateOS_文件系统返回', 'FortunateOS_文件路径管理', 'FortunateOS_是否开启锁屏_', 'FortunateOS_窗口ID管理', 'FortunateOS_窗口图层偏移', 'FortunateOS_窗口图层管理', 'FortunateOS_窗口坐标管理', 'FortunateOS_窗口大小管理', 'FortunateOS_窗口系统执行', 'FortunateOS_窗口组件管理', 'FortunateOS_管理设置选项', 'FortunateOS_系统版本号', 'FortunateOS_鼠标是否被占用_', '任务栏动画_i', '我的变量')
    GLOBAL_NAMES_SET = frozenset(GLOBAL_NAMES)

    def __init__(self):
        super().__init__()
        self.x = 0
        self.y = 0
        self.direction = 90
        self.visible = True
        self.size = 100
        self.name = 'Stage'
        self.is_stage = True
        self.rotation_style = 'all around'
        self.draggable = False
        self.costumes = [{'name': '背景1', 'md5ext': '6a88e1d3600bb7b42af5713457c3ba0a.svg', 'dataFormat': 'svg', 'rotationCenterX': 240.00000000000006, 'rotationCenterY': 180}, {'name': '背景3', 'md5ext': '68bae05e4640b516482504cca8c7b3f1.svg', 'dataFormat': 'svg', 'rotationCenterX': 480, 'rotationCenterY': 420}, {'name': '背景2', 'md5ext': '0cf937411065782c37618a3bbf1c1529.svg', 'dataFormat': 'svg', 'rotationCenterX': 480, 'rotationCenterY': 420}, {'name': '背景4', 'md5ext': '3c810ea9e6f21e8734124357c1c0cb4d.svg', 'dataFormat': 'svg', 'rotationCenterX': 360.22263499999997, 'rotationCenterY': 300}, {'name': '背景5', 'md5ext': 'be2de2bf8c0d4a4d5a5e3967bf3ae995.svg', 'dataFormat': 'svg', 'rotationCenterX': 239.999995, 'rotationCenterY': 300}, {'name': '背景6', 'md5ext': 'fd2360d34bc7561f5f63af2ccc17886b.svg', 'dataFormat': 'svg', 'rotationCenterX': 239.99996499999986, 'rotationCenterY': 180}, {'name': '背景7', 'md5ext': '239f73b1714687feccf57d87b9e80b15.svg', 'dataFormat': 'svg', 'rotationCenterX': 369.999995, 'rotationCenterY': 375.9999650000001}, {'name': '背景8', 'md5ext': '0d5fee369f5b01c31312fd4b99a5cb59.svg', 'dataFormat': 'svg', 'rotationCenterX': 239.89552999999995, 'rotationCenterY': 181.14914}, {'name': '背景9', 'md5ext': '8e97f5261bd5a1b8d9f29d843305741f.svg', 'dataFormat': 'svg', 'rotationCenterX': 240.66154723276134, 'rotationCenterY': 181.32309446552281}, {'name': '背景10', 'md5ext': 'a54f8189b40539e721763664dff07631.svg', 'dataFormat': 'svg', 'rotationCenterX': 242.386655, 'rotationCenterY': 180.47678000000013}, {'name': '背景11', 'md5ext': '2c44ba5df0f7c5fdbbdaccfedb8dd96d.svg', 'dataFormat': 'svg', 'rotationCenterX': 945.6735028255937, 'rotationCenterY': 787.3221750000002}, {'name': '背景12', 'md5ext': '33f6a41df64e2232161cd863b951eeb5.svg', 'dataFormat': 'svg', 'rotationCenterX': 1483.7020069299363, 'rotationCenterY': 937.3221850000002}]
        self.sounds = []
        self.costume_number = 10
        self.costume_name = '背景10'

    def when_broadcast_开机_FortunateOS(self):
        """当接收到广播'开机-FortunateOS'时"""
        self.FortunateOS_当前是否进入桌面 = '1'
        if _sc_bool(_sc_eq(self.FortunateOS_是否开启锁屏_, '0')):
            self.set_backdrop('背景10')
            for _repeat in range(_sc_repeat_count(60)):
                self.change_effect('BRIGHTNESS', _sc_div(50, 30))
                self._yield_frame()
            self.clear_effects()
        self.extension('music', 'music_playNoteForBeats', {'NOTE': 72, 'BEATS': _sc_div(1, 8)}, {})
        self.extension('music', 'music_playNoteForBeats', {'NOTE': 74, 'BEATS': _sc_div(1, 8)}, {})
        self.extension('music', 'music_playNoteForBeats', {'NOTE': 79, 'BEATS': _sc_div(1, 8)}, {})


    def when_broadcast_打开锁屏界面_FortunateOS(self):
        """当接收到广播'打开锁屏界面-FortunateOS'时"""
        self.set_backdrop('背景10')
        for _repeat in range(_sc_repeat_count(60)):
            self.change_effect('BRIGHTNESS', _sc_div(50, 30))
            self._yield_frame()
        self.clear_effects()


    def when_green_flag(self):
        """当绿旗被点击时"""
        self.FortunateOS_当前是否进入桌面 = '0'
        self.set_backdrop('背景1')
        self.set_effect('BRIGHTNESS', -100)


    def run(self):
        """向运行时注册事件脚本"""
        self._register('broadcast:开机-FortunateOS', self.when_broadcast_开机_FortunateOS)
        self._register('broadcast:打开锁屏界面-FortunateOS', self.when_broadcast_打开锁屏界面_FortunateOS)
        self._register('green_flag', self.when_green_flag)

class FortunateOS(ScratchSprite):
    """精灵: FortunateOS"""

    GLOBAL_NAMES = ('FortunateOS_中转执行类型', 'FortunateOS_中转系统执行', 'FortunateOS_中转系统返回', 'FortunateOS_全部主题名称', 'FortunateOS_分配窗口ID', 'FortunateOS_命令系统执行', 'FortunateOS_命令系统权限', 'FortunateOS_开始菜单是否被开启_', 'FortunateOS_当前主题', 'FortunateOS_当前是否进入桌面', 'FortunateOS_文件内容管理', 'FortunateOS_文件属性管理', 'FortunateOS_文件执行类型', 'FortunateOS_文件系统属性', 'FortunateOS_文件系统执行', 'FortunateOS_文件系统返回', 'FortunateOS_文件路径管理', 'FortunateOS_是否开启锁屏_', 'FortunateOS_窗口ID管理', 'FortunateOS_窗口图层偏移', 'FortunateOS_窗口图层管理', 'FortunateOS_窗口坐标管理', 'FortunateOS_窗口大小管理', 'FortunateOS_窗口系统执行', 'FortunateOS_窗口组件管理', 'FortunateOS_管理设置选项', 'FortunateOS_系统版本号', 'FortunateOS_鼠标是否被占用_', '任务栏动画_i', '我的变量')
    GLOBAL_NAMES_SET = frozenset(GLOBAL_NAMES)

    def __init__(self):
        super().__init__()
        self.x = 0
        self.y = 0
        self.direction = 90
        self.visible = True
        self.size = 100
        self.name = 'FortunateOS'
        self.rotation_style = 'all around'
        self.draggable = False
        self.costumes = [{'name': '造型1', 'md5ext': '3339a2953a3bf62bb80e54ff575dbced.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}]
        self.sounds = []
        self.costume_number = 1
        self.costume_name = '造型1'

    def run(self):
        """向运行时注册事件脚本"""
        pass

class BIOS(ScratchSprite):
    """精灵: BIOS"""

    GLOBAL_NAMES = ('FortunateOS_中转执行类型', 'FortunateOS_中转系统执行', 'FortunateOS_中转系统返回', 'FortunateOS_全部主题名称', 'FortunateOS_分配窗口ID', 'FortunateOS_命令系统执行', 'FortunateOS_命令系统权限', 'FortunateOS_开始菜单是否被开启_', 'FortunateOS_当前主题', 'FortunateOS_当前是否进入桌面', 'FortunateOS_文件内容管理', 'FortunateOS_文件属性管理', 'FortunateOS_文件执行类型', 'FortunateOS_文件系统属性', 'FortunateOS_文件系统执行', 'FortunateOS_文件系统返回', 'FortunateOS_文件路径管理', 'FortunateOS_是否开启锁屏_', 'FortunateOS_窗口ID管理', 'FortunateOS_窗口图层偏移', 'FortunateOS_窗口图层管理', 'FortunateOS_窗口坐标管理', 'FortunateOS_窗口大小管理', 'FortunateOS_窗口系统执行', 'FortunateOS_窗口组件管理', 'FortunateOS_管理设置选项', 'FortunateOS_系统版本号', 'FortunateOS_鼠标是否被占用_', '任务栏动画_i', '我的变量')
    GLOBAL_NAMES_SET = frozenset(GLOBAL_NAMES)

    def __init__(self):
        super().__init__()
        self.x = 0
        self.y = 0
        self.direction = 90
        self.visible = False
        self.size = 100
        self.name = 'BIOS'
        self.rotation_style = 'all around'
        self.draggable = False
        self.costumes = [{'name': 'S', 'md5ext': 'fbcff8729796b1f3defd8941fa272267.svg', 'dataFormat': 'svg', 'rotationCenterX': 74.89201097640989, 'rotationCenterY': 29.726550000000003}]
        self.sounds = []
        self.costume_number = 1
        self.costume_name = 'S'

        self.i = 0

    def when_broadcast_BIOS(self):
        """当接收到广播'BIOS'时"""
        self.broadcast('播放开机动画-FortunateOS')


    def when_green_flag(self):
        """当绿旗被点击时"""
        if _sc_bool(_sc_eq(_sc_random(1, 3), '1')):
            self.FortunateOS_当前主题 = 'os1'
        else:
            self.FortunateOS_当前主题 = 'fos'
        self.broadcast('BIOS')


    def run(self):
        """向运行时注册事件脚本"""
        self._register('broadcast:BIOS', self.when_broadcast_BIOS)
        self._register('green_flag', self.when_green_flag)

class FortunateOS_开机动画(ScratchSprite):
    """精灵: FortunateOS-开机动画"""

    GLOBAL_NAMES = ('FortunateOS_中转执行类型', 'FortunateOS_中转系统执行', 'FortunateOS_中转系统返回', 'FortunateOS_全部主题名称', 'FortunateOS_分配窗口ID', 'FortunateOS_命令系统执行', 'FortunateOS_命令系统权限', 'FortunateOS_开始菜单是否被开启_', 'FortunateOS_当前主题', 'FortunateOS_当前是否进入桌面', 'FortunateOS_文件内容管理', 'FortunateOS_文件属性管理', 'FortunateOS_文件执行类型', 'FortunateOS_文件系统属性', 'FortunateOS_文件系统执行', 'FortunateOS_文件系统返回', 'FortunateOS_文件路径管理', 'FortunateOS_是否开启锁屏_', 'FortunateOS_窗口ID管理', 'FortunateOS_窗口图层偏移', 'FortunateOS_窗口图层管理', 'FortunateOS_窗口坐标管理', 'FortunateOS_窗口大小管理', 'FortunateOS_窗口系统执行', 'FortunateOS_窗口组件管理', 'FortunateOS_管理设置选项', 'FortunateOS_系统版本号', 'FortunateOS_鼠标是否被占用_', '任务栏动画_i', '我的变量')
    GLOBAL_NAMES_SET = frozenset(GLOBAL_NAMES)

    def __init__(self):
        super().__init__()
        self.x = -117
        self.y = 0
        self.direction = 90
        self.visible = False
        self.size = 70
        self.name = 'FortunateOS-开机动画'
        self.rotation_style = 'all around'
        self.draggable = False
        self.costumes = [{'name': '造型1', 'md5ext': '3dfa3326baee59da725be32acfc5b357.svg', 'dataFormat': 'svg', 'rotationCenterX': 41.53864345341029, 'rotationCenterY': 41.627536401911044}, {'name': 'F', 'md5ext': '7c233e9594b48ebb4f3c905cb7ca57b9.svg', 'dataFormat': 'svg', 'rotationCenterX': 10.43731969604491, 'rotationCenterY': 29.726550000000003}, {'name': 'o', 'md5ext': 'de9fccfa1078dccac1028ad249982658.svg', 'dataFormat': 'svg', 'rotationCenterX': 11.966116287994367, 'rotationCenterY': 29.726550000000003}, {'name': 'r', 'md5ext': 'e7fc33710d4b3992e6d2078883bb8797.svg', 'dataFormat': 'svg', 'rotationCenterX': 8.493299999999977, 'rotationCenterY': 29.726550000000003}, {'name': 't', 'md5ext': '3ce33dab612c2b79790a4414d64b8f41.svg', 'dataFormat': 'svg', 'rotationCenterX': 7.70058825607299, 'rotationCenterY': 29.726550000000003}, {'name': 'u', 'md5ext': 'a6ec8c8d8f084a40e43e091ea1cb8f7a.svg', 'dataFormat': 'svg', 'rotationCenterX': 12.362468560028049, 'rotationCenterY': 29.726550000000003}, {'name': 'n', 'md5ext': '54070c432899343603013ec448a06e87.svg', 'dataFormat': 'svg', 'rotationCenterX': 12.362468560028049, 'rotationCenterY': 29.726550000000003}, {'name': 'a', 'md5ext': '94d0cfa83a0d775285cf32db2ba76230.svg', 'dataFormat': 'svg', 'rotationCenterX': 12.362468560028049, 'rotationCenterY': 29.726550000000003}, {'name': 'e', 'md5ext': '0e85acc586efb41eaff9d4e69708df40.svg', 'dataFormat': 'svg', 'rotationCenterX': 11.267773104095454, 'rotationCenterY': 29.726550000000003}, {'name': 'O', 'md5ext': 'df4b506041b9f021a5b681f4bae8532a.svg', 'dataFormat': 'svg', 'rotationCenterX': 15.287937120056142, 'rotationCenterY': 29.726550000000003}, {'name': 'S', 'md5ext': '96a8459c4e865015259a3d4bf6755609.svg', 'dataFormat': 'svg', 'rotationCenterX': 10.85254999999998, 'rotationCenterY': 29.726550000000003}]
        self.sounds = []
        self.costume_number = 1
        self.costume_name = '造型1'

        self.FortunateOS_i = '0'
        self.FortunateOS_y = 1.2180852121698073e-25
        self.FortunateOS_y1 = 22
        self.FortunateOS_x1 = -117
        self.FortunateOS_x = 3.7882099170118964
        self.拆分路径_i = 0
        self.拆分路径_t = 0
        self.添加一个目录或文件_i = 0
        self.添加一个目录或文件_t = 0
        self.添加一个目录或文件_j = 0
        self.添加一个目录或文件_返回值 = 0
        self.读取文件路径的内容_i = 0
        self.读取文件路径的内容_返回值 = 0
        self.读取文件路径的内容_内容 = 0
        self.删除文件路径的内容_返回值 = 0
        self.删除文件路径的内容_i = 0
        self.获取列表里面的所有元素_i = 0
        self.获取列表里面的所有元素_j = 0
        self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 0
        self.获取列表里面的所有元素_当前嵌套深度 = 0
        self.获取列表里面的所有元素_临时缓存当前代码块 = 0
        self.获取列表里面的所有元素_当前嵌套字符 = 0
        self.获取列表里面的所有元素_辅助变量2 = 0
        self.获取列表里面的所有元素_辅助变量 = 0
        self._i = 0
        self.去除字符串额外数据_返回值 = 0
        self._j = 0
        self.获取a该字符串的b_c个字符_返回值 = 0
        self.获取a该字符串的b_c个字符_i = 0

        self.lst_unnamed_5058f1 = [22, 25, 18, 17, 26, 26, '24', '17', '24', '32', '23']
        self.路径拆分 = []
        self.获取列表里面的所有元素_返回值 = []

    @_as_procedure(warp=False, arg_types=[], arg_names=[], proccode='开机动画-创建克隆体')
    def 开机动画_创建克隆体(self):
        """自制积木: 开机动画-创建克隆体"""
        self.FortunateOS_i = '0'
        self.goto_xy(-85, -80)
        self.set_size(70)
        for _repeat in range(_sc_repeat_count(_sc_length('FortunateOS'))):
            self.FortunateOS_i = _sc_add(self.FortunateOS_i, 1)
            self.switch_costume(_sc_letter_of(self.FortunateOS_i, 'FortunateOS'))
            self.create_clone_of('_myself_')
            self.change_x(_sc_add(_sc_div(_sc_mul(_sc_item_of(self.lst_unnamed_5058f1, self.FortunateOS_i), _sc_div(self.size, 100)), 2), _sc_div(_sc_mul(_sc_item_of(self.lst_unnamed_5058f1, _sc_add(self.FortunateOS_i, 1)), _sc_div(self.size, 100)), 2)))
            self._yield_frame()
        self.FortunateOS_i = '0'


    def when_broadcast_播放开机动画_2_FortunateOS(self):
        """当接收到广播'播放开机动画 2-FortunateOS'时"""
        if _sc_bool(_sc_eq(self.FortunateOS_i, '0')):
            self.show()
            self.goto_xy(-181, 0)
            self.switch_costume('造型1')
            self.FortunateOS_x1 = '-117'
            self.FortunateOS_x = '1'
            while not _sc_bool(_sc_or(_sc_eq(self.x, self.FortunateOS_x1), _sc_gt(_sc_add(self.x, self.FortunateOS_y), self.FortunateOS_x1))):
                self.change_x(self.FortunateOS_x)
                self.set_effect('GHOST', _sc_mul(_sc_div(100, 64), _sc_mathop('abs', _sc_sub(self.x, -117))))
                self.FortunateOS_x = _sc_mul(self.FortunateOS_x, _sc_add(1, _sc_div(0.17, 4)))
                self._yield_frame()
            self.set_x(self.FortunateOS_x1)
            self.clear_effects()
        else:
            self.FortunateOS_x1 = _sc_add(self.x, 64)
            self.FortunateOS_x = '1'
            while not _sc_bool(_sc_or(_sc_eq(self.x, self.FortunateOS_x1), _sc_gt(_sc_add(self.x, self.FortunateOS_y), self.FortunateOS_x1))):
                self.change_x(self.FortunateOS_x)
                self.FortunateOS_x = _sc_mul(self.FortunateOS_x, _sc_add(1, _sc_div(0.17, 4)))
                self._yield_frame()
            self.set_x(self.FortunateOS_x1)


    def when_broadcast_播放开机动画_FortunateOS(self):
        """当接收到广播'播放开机动画-FortunateOS'时"""
        self.hide()
        self.开机动画_创建克隆体()
        self.wait(2.5)
        self.broadcast('播放开机动画 2-FortunateOS')
        self.wait(5)
        if _sc_bool(_sc_eq(self.FortunateOS_是否开启锁屏_, '0')):
            self.broadcast('开机-FortunateOS')
        else:
            self.broadcast('打开锁屏界面-FortunateOS')


    def when_broadcast_开机_FortunateOS(self):
        """当接收到广播'开机-FortunateOS'时"""
        self.hide()
        self.delete_this_clone()


    def when_broadcast_打开锁屏界面_FortunateOS(self):
        """当接收到广播'打开锁屏界面-FortunateOS'时"""
        self.hide()
        self.delete_this_clone()


    def when_green_flag(self):
        """当绿旗被点击时"""
        self.FortunateOS_系统版本号 = 'A-0.3.1 - 0014'


    def when_clone_starts(self):
        """当作为克隆体启动时"""
        self.FortunateOS_y1 = _sc_random(18, 22)
        self.show()
        self.set_effect('GHOST', 100)
        self.wait(_sc_mul(self.FortunateOS_i, 0.1))
        self.FortunateOS_y = '1'
        while not _sc_bool(_sc_or(_sc_eq(self.y, '20'), _sc_gt(_sc_add(self.y, self.FortunateOS_y), '20'))):
            self.change_y(self.FortunateOS_y)
            self.set_effect('GHOST', _sc_mul(_sc_div(100, 160), _sc_mathop('abs', _sc_add(self.y, -80))))
            self.FortunateOS_y = _sc_mul(self.FortunateOS_y, _sc_add(1, _sc_div(0.17, 4)))
            self._yield_frame()
        self.clear_effects()
        self.FortunateOS_y = '1'
        while not _sc_bool(_sc_or(_sc_eq(self.y, self.FortunateOS_y1), _sc_gt(_sc_add(self.y, self.FortunateOS_y), self.FortunateOS_y1))):
            self.change_y(self.FortunateOS_y)
            self.FortunateOS_y = _sc_mul(self.FortunateOS_y, _sc_add(1, _sc_div(0.17, 4)))
            self._yield_frame()
        self.set_y(self.FortunateOS_y1)
        self.FortunateOS_y = '1'
        while not _sc_bool(_sc_or(_sc_eq(self.y, '0'), _sc_lt(_sc_sub(self.y, self.FortunateOS_y), '0'))):
            self.change_y(_sc_sub(0, self.FortunateOS_y))
            self.FortunateOS_y = _sc_mul(self.FortunateOS_y, _sc_add(1, _sc_div(0.055, 2)))
            self._yield_frame()
        self.set_y(0)


    def run(self):
        """向运行时注册事件脚本"""
        self._register('broadcast:播放开机动画 2-FortunateOS', self.when_broadcast_播放开机动画_2_FortunateOS)
        self._register('broadcast:播放开机动画-FortunateOS', self.when_broadcast_播放开机动画_FortunateOS)
        self._register('broadcast:开机-FortunateOS', self.when_broadcast_开机_FortunateOS)
        self._register('broadcast:打开锁屏界面-FortunateOS', self.when_broadcast_打开锁屏界面_FortunateOS)
        self._register('green_flag', self.when_green_flag)
        self._register('clone_start', self.when_clone_starts)

class FortunateOS_软件图标(ScratchSprite):
    """精灵: FortunateOS-软件图标"""

    GLOBAL_NAMES = ('FortunateOS_中转执行类型', 'FortunateOS_中转系统执行', 'FortunateOS_中转系统返回', 'FortunateOS_全部主题名称', 'FortunateOS_分配窗口ID', 'FortunateOS_命令系统执行', 'FortunateOS_命令系统权限', 'FortunateOS_开始菜单是否被开启_', 'FortunateOS_当前主题', 'FortunateOS_当前是否进入桌面', 'FortunateOS_文件内容管理', 'FortunateOS_文件属性管理', 'FortunateOS_文件执行类型', 'FortunateOS_文件系统属性', 'FortunateOS_文件系统执行', 'FortunateOS_文件系统返回', 'FortunateOS_文件路径管理', 'FortunateOS_是否开启锁屏_', 'FortunateOS_窗口ID管理', 'FortunateOS_窗口图层偏移', 'FortunateOS_窗口图层管理', 'FortunateOS_窗口坐标管理', 'FortunateOS_窗口大小管理', 'FortunateOS_窗口系统执行', 'FortunateOS_窗口组件管理', 'FortunateOS_管理设置选项', 'FortunateOS_系统版本号', 'FortunateOS_鼠标是否被占用_', '任务栏动画_i', '我的变量')
    GLOBAL_NAMES_SET = frozenset(GLOBAL_NAMES)

    def __init__(self):
        super().__init__()
        self.x = -155
        self.y = 50
        self.direction = 90
        self.visible = False
        self.size = 35
        self.name = 'FortunateOS-软件图标'
        self.rotation_style = 'all around'
        self.draggable = False
        self.costumes = [{'name': 'fos-造型1', 'md5ext': '0e761f56abd83e94b7fa9607ba9b01e6.svg', 'dataFormat': 'svg', 'rotationCenterX': 52.21963000000002, 'rotationCenterY': 52.21962999999994}, {'name': 'os1-造型1', 'md5ext': '0c63a1f7b376578ad78c53b03e1ceec9.svg', 'dataFormat': 'svg', 'rotationCenterX': 51.719629999999995, 'rotationCenterY': 51.719629999999995}, {'name': 'fos-造型2', 'md5ext': 'ce37d8fb5dc2abf9050a1c8e48bad523.svg', 'dataFormat': 'svg', 'rotationCenterX': 51.71961999999999, 'rotationCenterY': 51.71961999999999}, {'name': 'os1-造型2', 'md5ext': '325f946b9813d2c75a14dd9ee950824c.svg', 'dataFormat': 'svg', 'rotationCenterX': 51.719629999999995, 'rotationCenterY': 51.719629999999995}, {'name': 'fos-造型3', 'md5ext': 'a07e33928f2baf38b996a7c87783872e.svg', 'dataFormat': 'svg', 'rotationCenterX': 51.61185999999998, 'rotationCenterY': 51.53634499999998}, {'name': 'os1-造型3', 'md5ext': 'df0c21a3ac58c3b14aec413fba6f6f57.svg', 'dataFormat': 'svg', 'rotationCenterX': 51.719629999999995, 'rotationCenterY': 51.719629999999995}, {'name': 'fos-造型5', 'md5ext': 'bede67a613043f98179a97bb874c2073.svg', 'dataFormat': 'svg', 'rotationCenterX': 51.719629999999995, 'rotationCenterY': 51.71962999999997}, {'name': 'os1-造型5', 'md5ext': '19d9d83127fdf6bc96ab7e00941a39bb.svg', 'dataFormat': 'svg', 'rotationCenterX': 51.719629999999995, 'rotationCenterY': 51.719629999999995}, {'name': 'fos-造型4', 'md5ext': 'c19bd5747ce8ba7788a177c6e5db80d5.svg', 'dataFormat': 'svg', 'rotationCenterX': 51.92765499999999, 'rotationCenterY': 50.482590000000016}, {'name': 'os1-造型4', 'md5ext': 'ccd835835043fc32baaf9b051c865986.svg', 'dataFormat': 'svg', 'rotationCenterX': 51.719629999999995, 'rotationCenterY': 51.719629999999995}, {'name': 'fos-造型6', 'md5ext': 'b42d5f3e364b3092e65185ab95d9da04.svg', 'dataFormat': 'svg', 'rotationCenterX': 51.71963000000008, 'rotationCenterY': 51.719629999999825}, {'name': 'os1-造型6', 'md5ext': '519a1113bafc86e5c3b8305b1d8af0da.svg', 'dataFormat': 'svg', 'rotationCenterX': 51.719629999999995, 'rotationCenterY': 51.719629999999995}, {'name': 'fos-造型7', 'md5ext': '11901d8d31526870abef51e9041aa00e.svg', 'dataFormat': 'svg', 'rotationCenterX': 51.71962499999992, 'rotationCenterY': 51.71962499999995}, {'name': 'os1-造型7', 'md5ext': '8b720647685fb95ab59784440ff07b45.svg', 'dataFormat': 'svg', 'rotationCenterX': 51.72649019399029, 'rotationCenterY': 51.719629999999796}, {'name': 'fos-造型9', 'md5ext': '41ae2440592b4ecd9fdc88fa03df12a1.svg', 'dataFormat': 'svg', 'rotationCenterX': 51.719629999999995, 'rotationCenterY': 51.719629999999995}, {'name': 'os1-造型9', 'md5ext': 'bfd197e0fd72185d436c1b5848e45b96.svg', 'dataFormat': 'svg', 'rotationCenterX': 51.726485, 'rotationCenterY': 51.719629999999995}, {'name': 'fos-造型8', 'md5ext': 'dcf90df5a3bd549d691343e0ff7cab79.svg', 'dataFormat': 'svg', 'rotationCenterX': 51.71962500000009, 'rotationCenterY': 51.719625000000036}]
        self.sounds = []
        self.costume_number = 3
        self.costume_name = 'fos-造型2'

        self.i = 0
        self.x1 = 0
        self.x2 = 0
        self.y1 = 0
        self.y2 = 0
        self.xt = 0
        self.yt = 0
        self.窗口组件ID = 0
        self.绑定窗口ID = 0
        self._i = 0
        self.返回值 = 0
        self._i2 = 0
        self.返回值2 = 0
        self.获取列表里面的所有元素_i = 0
        self.获取列表里面的所有元素_j = 0
        self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 0
        self.获取列表里面的所有元素_当前嵌套深度 = 0
        self.获取列表里面的所有元素_临时缓存当前代码块 = 0
        self.获取列表里面的所有元素_当前嵌套字符 = 0
        self.获取列表里面的所有元素_辅助变量2 = 0
        self.获取列表里面的所有元素_辅助变量 = 0
        self.去除字符串额外数据_返回值 = 0
        self._j = 0
        self._i3 = 0
        self.克隆体组件ID = 0
        self.克隆体窗口ID = 0
        self.返回值3 = 0
        self.返回值4 = 0
        self.返回值5 = 0
        self.返回值6 = 0
        self.获取a该字符串的b_c个字符_返回值 = 0
        self.获取a该字符串的b_c个字符_i = 0
        self.返回值7 = 0
        self.窗口组件名称 = 0
        self.是否为克隆体_ = 0

        self.图标名称 = ['造型1', '造型2', '造型3', '造型4', '造型5', '造型6', '造型7', '造型9']
        self.临时列表 = []
        self.获取列表里面的所有元素_返回值 = []

    def when_clone_starts(self):
        """当作为克隆体启动时"""
        if _sc_bool(_sc_eq(self.FortunateOS_是否开启锁屏_, '0')):
            self.set_effect('BRIGHTNESS', -100)
            for _repeat in range(_sc_repeat_count(60)):
                self.change_effect('BRIGHTNESS', _sc_div(50, 30))
                self._yield_frame()
            self.clear_effects()


    def when_broadcast_开机_FortunateOS(self):
        """当接收到广播'开机-FortunateOS'时"""
        self.show()
        self.set_size(35)
        self.goto_xy(-200, 140)
        self.i = '1'
        for _repeat in range(_sc_repeat_count(8)):
            self.switch_costume(_sc_join(_sc_join(self.FortunateOS_当前主题, '-'), _sc_item_of(self.图标名称, self.i)))
            self.create_clone_of('_myself_')
            self.change_y(-45)
            if _sc_bool(_sc_or(_sc_eq(self.y, '-130'), _sc_lt(self.y, '-130'))):
                self.change_x(45)
                self.set_y(140)
            self.i = _sc_add(self.i, 1)
            self._yield_frame()
        self.hide()


    def when_green_flag(self):
        """当绿旗被点击时"""
        self.hide()


    def when_clicked(self):
        """当角色被点击时"""
        self.FortunateOS_窗口系统执行.append(_sc_join(_sc_join(_sc_join('[13,104,104,', _sc_join(_sc_random(-240, 240), ',')), _sc_join(_sc_random(-180, 180), ',')), '[关闭按钮,全屏按钮,窗口最小化,标题栏,底座,上拖动,下拖动,左拖动,右拖动,左上拖动,右上拖动,左下拖动,右下拖动],null]'))


    def run(self):
        """向运行时注册事件脚本"""
        self._register('clone_start', self.when_clone_starts)
        self._register('broadcast:开机-FortunateOS', self.when_broadcast_开机_FortunateOS)
        self._register('green_flag', self.when_green_flag)
        self._register('clicked', self.when_clicked)

class FortunateOS_窗口(ScratchSprite):
    """精灵: FortunateOS-窗口"""

    GLOBAL_NAMES = ('FortunateOS_中转执行类型', 'FortunateOS_中转系统执行', 'FortunateOS_中转系统返回', 'FortunateOS_全部主题名称', 'FortunateOS_分配窗口ID', 'FortunateOS_命令系统执行', 'FortunateOS_命令系统权限', 'FortunateOS_开始菜单是否被开启_', 'FortunateOS_当前主题', 'FortunateOS_当前是否进入桌面', 'FortunateOS_文件内容管理', 'FortunateOS_文件属性管理', 'FortunateOS_文件执行类型', 'FortunateOS_文件系统属性', 'FortunateOS_文件系统执行', 'FortunateOS_文件系统返回', 'FortunateOS_文件路径管理', 'FortunateOS_是否开启锁屏_', 'FortunateOS_窗口ID管理', 'FortunateOS_窗口图层偏移', 'FortunateOS_窗口图层管理', 'FortunateOS_窗口坐标管理', 'FortunateOS_窗口大小管理', 'FortunateOS_窗口系统执行', 'FortunateOS_窗口组件管理', 'FortunateOS_管理设置选项', 'FortunateOS_系统版本号', 'FortunateOS_鼠标是否被占用_', '任务栏动画_i', '我的变量')
    GLOBAL_NAMES_SET = frozenset(GLOBAL_NAMES)

    def __init__(self):
        super().__init__()
        self.x = 70
        self.y = 154
        self.direction = 90
        self.visible = False
        self.size = 100
        self.name = 'FortunateOS-窗口'
        self.rotation_style = 'all around'
        self.draggable = False
        self.costumes = [{'name': 'fos-底座', 'md5ext': '8ac730dab877000bf988d4deb086af35.svg', 'dataFormat': 'svg', 'rotationCenterX': 49.78940958454129, 'rotationCenterY': 49.78940958454098}, {'name': 'fos-上拖动', 'md5ext': 'e9f2690bad802b7340170322afee56a2.svg', 'dataFormat': 'svg', 'rotationCenterX': 49.789410000000004, 'rotationCenterY': 53.67830000000001}, {'name': 'fos-下拖动', 'md5ext': 'f0a3f2c07eb401c9ea576f4529d8568e.svg', 'dataFormat': 'svg', 'rotationCenterX': 49.789410000000004, 'rotationCenterY': -49.789410000000004}, {'name': 'fos-左拖动', 'md5ext': '7b73cfa5850488e6edcd0d2daa9ed30a.svg', 'dataFormat': 'svg', 'rotationCenterX': 53.67830000000001, 'rotationCenterY': 49.78941000000003}, {'name': 'fos-右拖动', 'md5ext': '1265bc9a535b9c5dbeb8463638891d9d.svg', 'dataFormat': 'svg', 'rotationCenterX': -49.78941000000003, 'rotationCenterY': 49.789410000000004}, {'name': 'fos-标题栏', 'md5ext': 'fb2e3e1e4352ecb0fb8604bc520a5e3a.svg', 'dataFormat': 'svg', 'rotationCenterX': 53.49255500000001, 'rotationCenterY': 49.789410000000004}, {'name': 'fos-左上拖动', 'md5ext': 'be879cac51e094cfcde9dfe60ab20008.svg', 'dataFormat': 'svg', 'rotationCenterX': 53.174832198976844, 'rotationCenterY': 53.397943695652174}, {'name': 'fos-右上拖动', 'md5ext': '93596c10fabf3629ab53b19e0fc97b44.svg', 'dataFormat': 'svg', 'rotationCenterX': -49.57201869565216, 'rotationCenterY': 53.463117175430256}, {'name': 'fos-左下拖动', 'md5ext': '0ac6a5a7f72053f9195326bc431556e5.svg', 'dataFormat': 'svg', 'rotationCenterX': 53.489492508607384, 'rotationCenterY': -49.54745869565221}, {'name': 'fos-右下拖动', 'md5ext': '9919809200f0cdffb2c8a5fa8847a33a.svg', 'dataFormat': 'svg', 'rotationCenterX': -49.54745869565221, 'rotationCenterY': -49.57201869565219}, {'name': 'fos-关闭按钮', 'md5ext': '7bab753c7b5703e39aec143dcecc39f2.svg', 'dataFormat': 'svg', 'rotationCenterX': -45.43518, 'rotationCenterY': 49.163735}, {'name': 'fos-关闭按钮-被碰到', 'md5ext': '7bab753c7b5703e39aec143dcecc39f2.svg', 'dataFormat': 'svg', 'rotationCenterX': -45.43518, 'rotationCenterY': 49.163735}, {'name': 'fos-全屏按钮', 'md5ext': 'aeae9cb74d518913b13b54742a6a4eec.svg', 'dataFormat': 'svg', 'rotationCenterX': -38.44023499999997, 'rotationCenterY': 49.16372500000003}, {'name': 'fos-全屏按钮-被碰到', 'md5ext': 'f559056cdf786dbfdf3fa3a06dddbdaf.svg', 'dataFormat': 'svg', 'rotationCenterX': -38.44025499999998, 'rotationCenterY': 49.163714999999996}, {'name': 'OS1-全屏按钮-恢复2', 'md5ext': 'c17c007703028bb52e162b95197d480e.svg', 'dataFormat': 'svg', 'rotationCenterX': -38.44023499999997, 'rotationCenterY': 49.16372500000011}, {'name': 'fos-全屏按钮-恢复-被碰到2', 'md5ext': 'ea8cbfa00a20f5e1fbec09a7ec5fc15d.svg', 'dataFormat': 'svg', 'rotationCenterX': -38.44023499999997, 'rotationCenterY': 49.163725000000085}, {'name': 'fos-窗口最小化', 'md5ext': 'a5f39f40a14a865c58316bfa45be3f2d.svg', 'dataFormat': 'svg', 'rotationCenterX': -31.47413499999999, 'rotationCenterY': 49.163725}, {'name': 'fos-窗口最小化-被碰到', 'md5ext': '71f14ed2c4e2fb04d121f7e8e1eac0a8.svg', 'dataFormat': 'svg', 'rotationCenterX': -31.47415000000001, 'rotationCenterY': 49.16374499999998}, {'name': 'os1-底座', 'md5ext': '8ac730dab877000bf988d4deb086af35.svg', 'dataFormat': 'svg', 'rotationCenterX': 49.78940958454129, 'rotationCenterY': 49.78940958454098}, {'name': 'os1-上拖动', 'md5ext': 'e0b79188fa13cfcd8d7b1b40d5ab9b8e.svg', 'dataFormat': 'svg', 'rotationCenterX': 49.78941000000006, 'rotationCenterY': 57.56718999999998}, {'name': 'os1-下拖动', 'md5ext': 'b8f4705ffce8ece873d40c92cfe8b60a.svg', 'dataFormat': 'svg', 'rotationCenterX': 49.789410000000004, 'rotationCenterY': -49.789410000000004}, {'name': 'os1-左拖动', 'md5ext': 'd2eb741c29016bb7f4b8a8dec03ac7b5.svg', 'dataFormat': 'svg', 'rotationCenterX': 57.56719000000001, 'rotationCenterY': 49.78941000000003}, {'name': 'os1-右拖动', 'md5ext': '1f41802955f711ab86f0d95356f1c5f3.svg', 'dataFormat': 'svg', 'rotationCenterX': -49.78941000000003, 'rotationCenterY': 49.78940999999995}, {'name': 'os1-标题栏', 'md5ext': '45c5a97bb3b527404139f4a75e76aa25.svg', 'dataFormat': 'svg', 'rotationCenterX': 53.492564999999985, 'rotationCenterY': 49.78941000000003}, {'name': 'os1-左上拖动', 'md5ext': '0a284f9f29be6dbf132d2789a85b789b.svg', 'dataFormat': 'svg', 'rotationCenterX': 57.52685714285724, 'rotationCenterY': 57.89266499999998}, {'name': 'os1-右上拖动', 'md5ext': '557143f9931d55eac40d2fad6662ff1e.svg', 'dataFormat': 'svg', 'rotationCenterX': -49.789409999999975, 'rotationCenterY': 57.56719}, {'name': 'os1-左下拖动', 'md5ext': 'd74d5fe8bfbc17d65cfaf77d47255269.svg', 'dataFormat': 'svg', 'rotationCenterX': 57.70239200000006, 'rotationCenterY': -49.463939999999866}, {'name': 'os1-右下拖动', 'md5ext': 'd8bd366be8d7a88963adc0de63430e0a.svg', 'dataFormat': 'svg', 'rotationCenterX': -49.78941000000003, 'rotationCenterY': -49.46393869565213}, {'name': 'os1-关闭按钮', 'md5ext': 'd7cd88a654b34f7189428b040f13b917.svg', 'dataFormat': 'svg', 'rotationCenterX': 51.28284999115246, 'rotationCenterY': 51.10191000186265}, {'name': 'os1-关闭按钮-被碰到', 'md5ext': '0327a2c666888dbc7c3ad85a10ee7671.svg', 'dataFormat': 'svg', 'rotationCenterX': 52.34897000000004, 'rotationCenterY': 52.069365000000005}, {'name': 'os1-全屏按钮', 'md5ext': 'e935b6df641b711dcd004c571ca6ae97.svg', 'dataFormat': 'svg', 'rotationCenterX': 34.327459990686776, 'rotationCenterY': 51.101910000000004}, {'name': 'os1-全屏按钮-被碰到', 'md5ext': 'ad95ba329d0872c90f56687e77eef927.svg', 'dataFormat': 'svg', 'rotationCenterX': 35.14619000000005, 'rotationCenterY': 51.935250000000025}, {'name': 'os1-全屏按钮-恢复', 'md5ext': '1c6923cd62c2b9233994c1b4a95b0da1.svg', 'dataFormat': 'svg', 'rotationCenterX': 34.32746999999998, 'rotationCenterY': 51.101910000000004}, {'name': 'os1-全屏按钮-恢复-被碰到', 'md5ext': 'c4cc7c095064767fc2555f4daa09f6ec.svg', 'dataFormat': 'svg', 'rotationCenterX': 34.810190000000006, 'rotationCenterY': 51.67838999999998}, {'name': 'os1-窗口最小化', 'md5ext': '09c20006ff4f649bb6e19191cd4afda8.svg', 'dataFormat': 'svg', 'rotationCenterX': 42.72382000000002, 'rotationCenterY': 51.101910000000004}, {'name': 'os1-窗口最小化-被碰到', 'md5ext': 'd6d2957083cc7e03b98e6e8f2f3943b5.svg', 'dataFormat': 'svg', 'rotationCenterX': 43.776024999999976, 'rotationCenterY': 52.069860000000006}, {'name': 'gen-窗口标题', 'md5ext': '78f1c8994065bafc771e04e2af4f7453.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'gen-按钮', 'md5ext': 'e52e85b0ea3a2273aeaeb386662cabaa.svg', 'dataFormat': 'svg', 'rotationCenterX': 9.0625, 'rotationCenterY': 9.062499999999972}, {'name': 'gen-窗口文本', 'md5ext': '78f1c8994065bafc771e04e2af4f7453.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'gen-窗口输入-单行', 'md5ext': '78f1c8994065bafc771e04e2af4f7453.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'gen-窗口输入-多行2', 'md5ext': '78f1c8994065bafc771e04e2af4f7453.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}]
        self.sounds = []
        self.costume_number = 37
        self.costume_name = 'gen-窗口标题'

        self.x1 = 0
        self.x2 = 0
        self.y1 = 0
        self.y2 = 0
        self.xt = 0
        self.yt = 0
        self.窗口组件ID = 1
        self.绑定窗口ID = 1
        self._i = 2
        self.返回值 = 'NO'
        self._i2 = 0
        self.返回值2 = 'YES'
        self.获取列表里面的所有元素_i = 60
        self.获取列表里面的所有元素_j = 14
        self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'YES'
        self.获取列表里面的所有元素_当前嵌套深度 = '0'
        self.获取列表里面的所有元素_临时缓存当前代码块 = '右下拖动'
        self.获取列表里面的所有元素_当前嵌套字符 = ''
        self.获取列表里面的所有元素_辅助变量2 = '0'
        self.获取列表里面的所有元素_辅助变量 = ''
        self.去除字符串额外数据_返回值 = 0
        self._j = 0
        self._i3 = 2
        self.克隆体组件ID = 0
        self.克隆体窗口ID = 0
        self.返回值3 = 'os1-底座'
        self.返回值4 = 0
        self.返回值5 = 75
        self.返回值6 = -100
        self.获取a该字符串的b_c个字符_返回值 = '-底'
        self.获取a该字符串的b_c个字符_i = 6
        self.返回值7 = 'YES'
        self.窗口组件名称 = '-底'
        self.i = 0
        self.是否为克隆体_ = '0'

        self.临时列表 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        self.获取列表里面的所有元素_返回值 = ['关闭按钮', '全屏按钮', '窗口最小化', '标题栏', '底座', '上拖动', '下拖动', '左拖动', '右拖动', '左上拖动', '右上拖动', '左下拖动', '右下拖动']

    @_as_procedure(warp=True, arg_types=['s', 's'], arg_names=['窗口ID', '新图层长度'], proccode='将 %s 窗口的图层长度扩充至 %s', arg_ids=['yR{U(TWe?r00lrhn@e=P', 'M@HnFzNE@iz;ZF+SOUMe'], arg_defaults=['', ''])
    def 将_窗口的图层长度扩充至(self, arg_窗口ID=0, arg_新图层长度=0):
        """自制积木: 将 %s 窗口的图层长度扩充至 %s"""
        self.临时列表.clear()
        self.返回值 = 'NO'
        self._i = '0'
        while not _sc_bool(_sc_eq(self._i, len(self.FortunateOS_窗口图层管理))):
            self._i = _sc_add(self._i, 1)
            if _sc_bool(_sc_eq(_sc_item_of(self.FortunateOS_窗口图层管理, self._i), arg_窗口ID)):
                self._i2 = _sc_item_of(self.FortunateOS_窗口图层管理, _sc_add(self._i, 1))
                if _sc_bool(_sc_lt(self._i2, arg_新图层长度)):
                    self.返回值 = 'YES'
                    _sc_list_replace(self.FortunateOS_窗口图层管理, _sc_add(self._i, 1), arg_新图层长度)
                    self._i = _sc_add(self._i, _sc_add(self._i2, 1))
                    self._i3 = _sc_sub(arg_新图层长度, self._i2)
                    for _repeat in range(_sc_repeat_count(_sc_sub(arg_新图层长度, self._i2))):
                        self._i3 = _sc_add(self._i3, -1)
                        self._i = _sc_add(self._i, 1)
                        _sc_list_insert(self.FortunateOS_窗口图层管理, self._i, _sc_sub(arg_新图层长度, self._i3))
                        self._yield_frame()
                else:
                    self.stop('this script')
            else:
                self._i = _sc_add(self._i, 1)
                self._i = _sc_add(self._i, _sc_item_of(self.FortunateOS_窗口图层管理, self._i))
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s', 's'], arg_names=['窗口ID', '组件ID'], proccode='获取 %s 该窗口ID中 %s 组件ID的窗口相对图层位置', arg_ids=['T`tB@dJ^H}*/4`LTiK1S', ':9xAjVj3jou5imD(!Uif'], arg_defaults=['', ''])
    def 获取_该窗口ID中_组件ID的窗口相对图层位置(self, arg_窗口ID=0, arg_组件ID=0):
        """自制积木: 获取 %s 该窗口ID中 %s 组件ID的窗口相对图层位置"""
        self.返回值 = 'NO'
        self._i = '0'
        while not _sc_bool(_sc_gt(self._i, len(self.FortunateOS_窗口图层管理))):
            self._i = _sc_add(self._i, 1)
            if _sc_bool(_sc_eq(_sc_item_of(self.FortunateOS_窗口图层管理, self._i), arg_窗口ID)):
                self._i2 = _sc_add(self._i, _sc_item_of(self.FortunateOS_窗口图层管理, _sc_add(self._i, 1)))
                self._i = _sc_add(self._i, 1)
                self._i3 = self._i
                while not _sc_bool(_sc_gt(self._i, self._i2)):
                    self._i = _sc_add(self._i, 1)
                    if _sc_bool(_sc_eq(_sc_item_of(self.FortunateOS_窗口图层管理, self._i), arg_组件ID)):
                        self.返回值 = _sc_sub(self._i, self._i3)
                        self.stop('this script')
                    self._yield_frame()
                self.stop('this script')
            else:
                self._i = _sc_add(self._i, 1)
                self._i = _sc_add(self._i, _sc_item_of(self.FortunateOS_窗口图层管理, self._i))
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s', 's'], arg_names=['窗口ID', 'n'], proccode='获取 %s 该窗口ID的第 %s 个图层的数据', arg_ids=['eIV#Z+x-j*[#wE87HY[y', '59ZF?)9x[HDB9x|Llp+y'], arg_defaults=['', ''])
    def 获取_该窗口ID的第_个图层的数据(self, arg_窗口ID=0, arg_n=0):
        """自制积木: 获取 %s 该窗口ID的第 %s 个图层的数据"""
        self.返回值 = 'NO'
        self._i = '0'
        while not _sc_bool(_sc_eq(self._i, len(self.FortunateOS_窗口图层管理))):
            self._i = _sc_add(self._i, 1)
            if _sc_bool(_sc_eq(_sc_item_of(self.FortunateOS_窗口图层管理, self._i), arg_窗口ID)):
                self.返回值 = _sc_item_of(self.FortunateOS_窗口图层管理, _sc_add(self._i, _sc_add(1, arg_n)))
                self.stop('this script')
            else:
                self._i = _sc_add(self._i, 1)
                self._i = _sc_add(self._i, _sc_item_of(self.FortunateOS_窗口图层管理, self._i))
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s', 's', 's'], arg_names=['窗口ID', 'a', 'b'], proccode='将 %s 该窗口ID中的 %s 位置的图层ID与 %s 位置的图层ID进行交换', arg_ids=['Bk~s=*{:%~3~EMlPtjF`', 'mszx*6?CG1ww#B?w{Gb/', 'f1^V3WLpKB4[m.U?Ye-o'], arg_defaults=['', '', ''])
    def 将_该窗口ID中的_位置的图层ID与_位置的图层ID进行交换(self, arg_窗口ID=0, arg_a=0, arg_b=0):
        """自制积木: 将 %s 该窗口ID中的 %s 位置的图层ID与 %s 位置的图层ID进行交换"""
        self.返回值 = 'NO'
        self._i = '0'
        while not _sc_bool(_sc_eq(self._i, len(self.FortunateOS_窗口图层管理))):
            self._i = _sc_add(self._i, 1)
            if _sc_bool(_sc_eq(_sc_item_of(self.FortunateOS_窗口图层管理, self._i), arg_窗口ID)):
                self._i = _sc_add(self._i, 1)
                self._i2 = _sc_item_of(self.FortunateOS_窗口图层管理, _sc_add(self._i, arg_a))
                self._i3 = _sc_item_of(self.FortunateOS_窗口图层管理, _sc_add(self._i, arg_b))
                _sc_list_delete(self.FortunateOS_窗口图层管理, _sc_add(self._i, arg_a))
                _sc_list_insert(self.FortunateOS_窗口图层管理, _sc_add(self._i, arg_a), self._i3)
                _sc_list_delete(self.FortunateOS_窗口图层管理, _sc_add(self._i, arg_b))
                _sc_list_insert(self.FortunateOS_窗口图层管理, _sc_add(self._i, arg_b), self._i2)
                self.返回值 = 'YES'
                self.stop('this script')
            else:
                self._i = _sc_add(self._i, 1)
                self._i = _sc_add(self._i, _sc_item_of(self.FortunateOS_窗口图层管理, self._i))
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s'], arg_names=['窗口ID'], proccode='查找 %s 该窗口ID是否存在', arg_ids=['Jtf,9ZNb:}VIQnTkK,jt'], arg_defaults=[''])
    def 查找_该窗口ID是否存在(self, arg_窗口ID=0):
        """自制积木: 查找 %s 该窗口ID是否存在"""
        self.返回值4 = 'NO'
        self._i = '0'
        while not _sc_bool(_sc_gt(self._i, len(self.FortunateOS_窗口图层管理))):
            self._i = _sc_add(self._i, 1)
            if _sc_bool(_sc_eq(_sc_item_of(self.FortunateOS_窗口图层管理, self._i), arg_窗口ID)):
                self.返回值4 = 'YES'
                self.stop('this script')
            else:
                self._i = _sc_add(self._i, 1)
                self._i = _sc_add(self._i, _sc_item_of(self.FortunateOS_窗口图层管理, self._i))
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s'], arg_names=['窗口ID'], proccode='将 %s 该窗口ID的窗口移到最前面', arg_ids=['Y.do)W%_NpXS)#EpV1zI'], arg_defaults=[''])
    def 将_该窗口ID的窗口移到最前面(self, arg_窗口ID=0):
        """自制积木: 将 %s 该窗口ID的窗口移到最前面"""
        self.临时列表.clear()
        self.返回值 = 'NO'
        self._i = '0'
        while not _sc_bool(_sc_gt(self._i, len(self.FortunateOS_窗口图层管理))):
            self._i = _sc_add(self._i, 1)
            if _sc_bool(_sc_eq(_sc_item_of(self.FortunateOS_窗口图层管理, self._i), arg_窗口ID)):
                self.返回值 = 'YES'
                _sc_list_delete(self.FortunateOS_窗口图层管理, self._i)
                self._i2 = _sc_item_of(self.FortunateOS_窗口图层管理, self._i)
                _sc_list_delete(self.FortunateOS_窗口图层管理, self._i)
                self.临时列表.append(_sc_item_of(self.FortunateOS_窗口图层管理, self._i))
                for _repeat in range(_sc_repeat_count(_sc_sub(self._i2, 1))):
                    _sc_list_delete(self.FortunateOS_窗口图层管理, self._i)
                    self.临时列表.append(_sc_item_of(self.FortunateOS_窗口图层管理, self._i))
                    self._yield_frame()
                _sc_list_delete(self.FortunateOS_窗口图层管理, self._i)
                self._i = '0'
                for _repeat in range(_sc_repeat_count(len(self.临时列表))):
                    _sc_list_insert(self.FortunateOS_窗口图层管理, 1, _sc_item_of(self.临时列表, _sc_sub(len(self.临时列表), self._i)))
                    self._i = _sc_add(self._i, 1)
                    self._yield_frame()
                _sc_list_insert(self.FortunateOS_窗口图层管理, 1, len(self.临时列表))
                _sc_list_insert(self.FortunateOS_窗口图层管理, 1, arg_窗口ID)
                self.stop('this script')
            else:
                self._i = _sc_add(self._i, 1)
                self._i = _sc_add(self._i, _sc_item_of(self.FortunateOS_窗口图层管理, self._i))
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s'], arg_names=['窗口ID'], proccode='删除掉 %s 该窗口ID所存储的XY大小数据', arg_ids=['%S.jGAA=N|,;2JTv@=u%'], arg_defaults=[''])
    def 删除掉_该窗口ID所存储的XY大小数据(self, arg_窗口ID=0):
        """自制积木: 删除掉 %s 该窗口ID所存储的XY大小数据"""
        self.返回值2 = 'NO'
        self._i = '0'
        while not _sc_bool(_sc_lt(len(self.FortunateOS_窗口大小管理), self._i)):
            self._i = _sc_add(self._i, 1)
            if _sc_bool(_sc_eq(arg_窗口ID, _sc_item_of(self.FortunateOS_窗口大小管理, self._i))):
                self.返回值2 = 'YES'
                for _repeat in range(_sc_repeat_count(3)):
                    _sc_list_delete(self.FortunateOS_窗口大小管理, self._i)
                    self._yield_frame()
                self.stop('this script')
            else:
                self._i = _sc_add(self._i, 2)
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=[], arg_names=[], proccode='删除所有管理窗口', arg_defaults=['', '', '', '', ''])
    def 删除所有管理窗口(self):
        """自制积木: 删除所有管理窗口"""
        self.FortunateOS_窗口坐标管理.clear()
        self.FortunateOS_窗口图层管理.clear()
        self.FortunateOS_窗口大小管理.clear()
        self.FortunateOS_窗口组件管理.clear()
        self.FortunateOS_窗口ID管理.clear()
        self.FortunateOS_窗口系统执行.clear()


    @_as_procedure(warp=True, arg_types=['s'], arg_names=['窗口ID'], proccode='删除掉 %s 该窗口ID所存储的XY坐标数据', arg_ids=['%S.jGAA=N|,;2JTv@=u%'], arg_defaults=[''])
    def 删除掉_该窗口ID所存储的XY坐标数据(self, arg_窗口ID=0):
        """自制积木: 删除掉 %s 该窗口ID所存储的XY坐标数据"""
        self.返回值2 = 'NO'
        self._i = '0'
        while not _sc_bool(_sc_lt(len(self.FortunateOS_窗口坐标管理), self._i)):
            self._i = _sc_add(self._i, 1)
            if _sc_bool(_sc_eq(arg_窗口ID, _sc_item_of(self.FortunateOS_窗口坐标管理, self._i))):
                self.返回值2 = 'YES'
                for _repeat in range(_sc_repeat_count(3)):
                    _sc_list_delete(self.FortunateOS_窗口坐标管理, self._i)
                    self._yield_frame()
                self.stop('this script')
            else:
                self._i = _sc_add(self._i, 2)
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s'], arg_names=['窗口ID'], proccode='删除 %s 该窗口ID的所有组件', arg_ids=['J8}Qb+fQ}$JExcC06*a]'], arg_defaults=[''])
    def 删除_该窗口ID的所有组件(self, arg_窗口ID=0):
        """自制积木: 删除 %s 该窗口ID的所有组件"""
        self.返回值7 = 'NO'
        self._i = '0'
        while not _sc_bool(_sc_gt(self._i, len(self.FortunateOS_窗口组件管理))):
            self._i = _sc_add(self._i, 1)
            if _sc_bool(_sc_eq(_sc_item_of(self.FortunateOS_窗口组件管理, self._i), arg_窗口ID)):
                self.返回值7 = 'YES'
                self._i2 = _sc_item_of(self.FortunateOS_窗口组件管理, _sc_add(self._i, 1))
                for _repeat in range(_sc_repeat_count(_sc_add(self._i2, 2))):
                    _sc_list_delete(self.FortunateOS_窗口组件管理, self._i)
                    self._yield_frame()
                self.stop('this script')
            else:
                self._i = _sc_add(self._i, 1)
                self._i = _sc_add(self._i, _sc_item_of(self.FortunateOS_窗口组件管理, self._i))
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=[], arg_names=[], proccode='生成所有窗口的偏移量')
    def 生成所有窗口的偏移量(self):
        """自制积木: 生成所有窗口的偏移量"""
        self.返回值 = 'NO'
        self._i = '0'
        self._i2 = '0'
        self.FortunateOS_窗口图层偏移.clear()
        while not _sc_bool(_sc_gt(self._i, len(self.FortunateOS_窗口图层管理))):
            self._i = _sc_add(self._i, 1)
            self.FortunateOS_窗口图层偏移.append(_sc_item_of(self.FortunateOS_窗口图层管理, self._i))
            self._i = _sc_add(self._i, 1)
            self.FortunateOS_窗口图层偏移.append(self._i2)
            self._i2 = _sc_add(self._i2, _sc_item_of(self.FortunateOS_窗口图层管理, self._i))
            self._i = _sc_add(self._i, _sc_item_of(self.FortunateOS_窗口图层管理, self._i))
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s'], arg_names=['窗口ID'], proccode='查找 %s 该窗口ID的XY坐标', arg_ids=['hD,_lF{mTfzCSo/fMJ$0'], arg_defaults=[''])
    def 查找_该窗口ID的XY坐标(self, arg_窗口ID=0):
        """自制积木: 查找 %s 该窗口ID的XY坐标"""
        self.返回值5 = 'NO'
        self._i = '0'
        while not _sc_bool(_sc_gt(self._i, len(self.FortunateOS_窗口坐标管理))):
            self._i = _sc_add(self._i, 1)
            if _sc_bool(_sc_eq(arg_窗口ID, _sc_item_of(self.FortunateOS_窗口坐标管理, self._i))):
                self.返回值5 = _sc_item_of(self.FortunateOS_窗口坐标管理, _sc_add(self._i, 1))
                self.返回值6 = _sc_item_of(self.FortunateOS_窗口坐标管理, _sc_add(self._i, 2))
                self.stop('this script')
            else:
                self._i = _sc_add(self._i, 2)
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s'], arg_names=['窗口ID'], proccode='获取 %s 该窗口ID的图层分配长度', arg_ids=['$@x][77OT1LeL3qkgn=l'], arg_defaults=[''])
    def 获取_该窗口ID的图层分配长度(self, arg_窗口ID=0):
        """自制积木: 获取 %s 该窗口ID的图层分配长度"""
        self.返回值 = 'NO'
        self._i = '0'
        while not _sc_bool(_sc_gt(self._i, len(self.FortunateOS_窗口图层管理))):
            self._i = _sc_add(self._i, 1)
            if _sc_bool(_sc_eq(_sc_item_of(self.FortunateOS_窗口图层管理, self._i), arg_窗口ID)):
                self.返回值 = _sc_item_of(self.FortunateOS_窗口图层管理, _sc_add(self._i, 1))
                self.stop('this script')
            else:
                self._i = _sc_add(self._i, 1)
                self._i = _sc_add(self._i, _sc_item_of(self.FortunateOS_窗口图层管理, self._i))
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=[], arg_names=[], proccode='标题栏-拖动相关逻辑-坐标替换')
    def 标题栏_拖动相关逻辑_坐标替换(self):
        """自制积木: 标题栏-拖动相关逻辑-坐标替换"""
        _sc_list_replace(self.FortunateOS_窗口坐标管理, self.i, _sc_add(self.mouse_x, self.x1))
        _sc_list_replace(self.FortunateOS_窗口坐标管理, _sc_add(self.i, 1), _sc_add(self.mouse_y, self.y1))
        self.切换对应图层()


    @_as_procedure(warp=True, arg_types=['s', 's', 's'], arg_names=['窗口ID', 'x', 'y'], proccode='将 %s 窗口ID的窗口的坐标设置为(x: %s ,y: %s )', arg_ids=['9b1aD#)gS5mX0w}U28Wg', 'pvdGCQy?@4%@r9X:pqD|', 'p;`qpslikeRcg(4tty+Y'], arg_defaults=['', '', ''])
    def 将_窗口ID的窗口的坐标设置为_x_y_(self, arg_窗口ID=0, arg_x=0, arg_y=0):
        """自制积木: 将 %s 窗口ID的窗口的坐标设置为(x: %s ,y: %s )"""
        self.返回值2 = 'NO'
        self._i = '0'
        while not _sc_bool(_sc_lt(len(self.FortunateOS_窗口坐标管理), self._i)):
            self._i = _sc_add(self._i, 1)
            if _sc_bool(_sc_eq(arg_窗口ID, _sc_item_of(self.FortunateOS_窗口坐标管理, self._i))):
                self.返回值2 = 'YES'
                self._i = _sc_add(self._i, 1)
                _sc_list_replace(self.FortunateOS_窗口坐标管理, self._i, arg_x)
                _sc_list_replace(self.FortunateOS_窗口坐标管理, _sc_add(self._i, 1), arg_y)
            else:
                self._i = _sc_add(self._i, 2)
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=[], arg_names=[], proccode='切换对应图层')
    def 切换对应图层(self):
        """自制积木: 切换对应图层"""
        self.查找_该窗口ID的XY坐标(self.绑定窗口ID)
        self.获取_该窗口ID中实际图层的偏移量(self.绑定窗口ID)
        self.go_to_layer('front')
        self.change_layer(-_sc_num(self.返回值2))
        self.获取_该窗口ID中_组件ID的窗口相对图层位置(self.绑定窗口ID, self.窗口组件ID)
        self.change_layer(-_sc_num(self.返回值))


    @_as_procedure(warp=True, arg_types=[], arg_names=[], proccode='标题栏-拖动相关逻辑-查找替换位置')
    def 标题栏_拖动相关逻辑_查找替换位置(self):
        """自制积木: 标题栏-拖动相关逻辑-查找替换位置"""
        self._i = '0'
        while not _sc_bool(_sc_lt(len(self.FortunateOS_窗口坐标管理), self._i)):
            self._i = _sc_add(self._i, 1)
            if _sc_bool(_sc_eq(self.绑定窗口ID, _sc_item_of(self.FortunateOS_窗口坐标管理, self._i))):
                self._i = _sc_add(self._i, 1)
                self.stop('this script')
            else:
                self._i = _sc_add(self._i, 2)
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s'], arg_names=['窗口ID'], proccode='获取 %s 该窗口ID中实际图层的偏移量', arg_ids=['#xP+GweW9+t?y@(2syx('], arg_defaults=[''])
    def 获取_该窗口ID中实际图层的偏移量(self, arg_窗口ID=0):
        """自制积木: 获取 %s 该窗口ID中实际图层的偏移量"""
        self.返回值2 = 'NO'
        self._i = '0'
        while not _sc_bool(_sc_lt(len(self.FortunateOS_窗口图层偏移), self._i)):
            self._i = _sc_add(self._i, 1)
            if _sc_bool(_sc_eq(arg_窗口ID, _sc_item_of(self.FortunateOS_窗口图层偏移, self._i))):
                self.返回值2 = _sc_item_of(self.FortunateOS_窗口图层偏移, _sc_add(self._i, 1))
                self.stop('this script')
            else:
                self._i = _sc_add(self._i, 1)
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s'], arg_names=['窗口ID'], proccode='删除掉 %s 该窗口ID的窗口', arg_ids=['qtYX6b$9G]tQ3|}ZW(]f'], arg_defaults=[''])
    def 删除掉_该窗口ID的窗口(self, arg_窗口ID=0):
        """自制积木: 删除掉 %s 该窗口ID的窗口"""
        self.返回值 = 'NO'
        self._i = '0'
        while not _sc_bool(_sc_eq(self._i, len(self.FortunateOS_窗口图层管理))):
            self._i = _sc_add(self._i, 1)
            if _sc_bool(_sc_eq(_sc_item_of(self.FortunateOS_窗口图层管理, self._i), arg_窗口ID)):
                self.返回值 = 'YES'
                self._i2 = _sc_item_of(self.FortunateOS_窗口图层管理, _sc_add(self._i, 1))
                for _repeat in range(_sc_repeat_count(_sc_add(self._i2, 2))):
                    _sc_list_delete(self.FortunateOS_窗口图层管理, self._i)
                    self._yield_frame()
                self.删除_该窗口ID的所有组件(arg_窗口ID)
                self.删除掉_该窗口ID所存储的XY大小数据(arg_窗口ID)
                self.删除掉_该窗口ID所存储的XY坐标数据(arg_窗口ID)
                self.FortunateOS_窗口ID管理.append(arg_窗口ID)
                self.stop('this script')
            else:
                self._i = _sc_add(self._i, 1)
                self._i = _sc_add(self._i, _sc_item_of(self.FortunateOS_窗口图层管理, self._i))
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s'], arg_names=['窗口ID'], proccode='查找 %s 该窗口ID的XY大小', arg_ids=['hD,_lF{mTfzCSo/fMJ$0'], arg_defaults=[''])
    def 查找_该窗口ID的XY大小(self, arg_窗口ID=0):
        """自制积木: 查找 %s 该窗口ID的XY大小"""
        self.返回值2 = 'NO'
        self._i = '0'
        while not _sc_bool(_sc_eq(len(self.FortunateOS_窗口大小管理), self._i)):
            self._i = _sc_add(self._i, 1)
            if _sc_bool(_sc_eq(arg_窗口ID, _sc_item_of(self.FortunateOS_窗口大小管理, self._i))):
                self.返回值 = _sc_item_of(self.FortunateOS_窗口大小管理, _sc_add(self._i, 1))
                self.返回值2 = _sc_item_of(self.FortunateOS_窗口大小管理, _sc_add(self._i, 2))
                self.stop('this script')
            else:
                self._i = _sc_add(self._i, 2)
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s', 's', 's'], arg_names=['窗口ID', 'x', 'y'], proccode='为 %s 该窗口ID创建一个X为 %s , Y为 %s ,的数据', arg_ids=[')_=FN(C60d9xmJX;fK.-', 'Hy;Swc,l_$::DbPbFK$n', 'g@hSN:B,`pQzCM0I!lxx'], arg_defaults=['', '', ''])
    def 为_该窗口ID创建一个X为_Y为_的数据(self, arg_窗口ID=0, arg_x=0, arg_y=0):
        """自制积木: 为 %s 该窗口ID创建一个X为 %s , Y为 %s ,的数据"""
        self.FortunateOS_窗口坐标管理.append(arg_窗口ID)
        self.FortunateOS_窗口坐标管理.append(arg_x)
        self.FortunateOS_窗口坐标管理.append(arg_y)


    @_as_procedure(warp=True, arg_types=['s', 's', 's', 's', 's', 's', 's', 's'], arg_names=['窗口ID', '分配图层大小', 'x大小', 'y大小', 'x', 'y', '分配图层组件', '克隆体额外信息'], proccode='新建一个窗口(窗口ID: %s ,分配图层大小: %s ,x大小: %s ,y大小: %s ,x: %s ,y: %s ,分配图层组件: %s ,克隆体额外信息: %s )', arg_ids=['$IHLtfkb+/}FT}nx%lQF', 'DhTlCcwBKhq:laMv;hQ;', '*IffGBU[=sU]a)=9|$zi', '/*RiBEtC*vYi,=J42mdz', '/:^4Af^W3v:D+XdNMENO', '}$W|r$DOiK#mryOpWSP|', 'QAC4!Ebh/prrGaKA9t)K', 'DqomB;k}:MEb8`1Mzvu='], arg_defaults=['', '', '', '', '', '', '', '', ''])
    def 新建一个窗口_窗口ID_分配图层大小_x大小_y大小_x_y_分配图层组件_克隆体额外信息_(self, arg_窗口ID=0, arg_分配图层大小=0, arg_x大小=0, arg_y大小=0, arg_x=0, arg_y=0, arg_分配图层组件=0, arg_克隆体额外信息=0):
        """自制积木: 新建一个窗口(窗口ID: %s ,分配图层大小: %s ,x大小: %s ,y大小: %s ,x: %s ,y: %s ,分配图层组件: %s ,克隆体额外信息: %s )"""
        self.为_该窗口ID创建一个X大小为_Y大小为_的数据(arg_窗口ID, arg_x大小, arg_y大小)
        self.为_该窗口ID创建一个X为_Y为_的数据(arg_窗口ID, arg_x, arg_y)
        self.为_该窗口ID创建_组件(arg_窗口ID, arg_分配图层组件)
        self._i = '0'
        self.绑定窗口ID = arg_窗口ID
        for _repeat in range(_sc_repeat_count(arg_分配图层大小)):
            self.glide_to_target(0, '_random_')
            self.窗口组件ID = _sc_sub(arg_分配图层大小, self._i)
            _sc_list_insert(self.FortunateOS_窗口图层管理, 1, _sc_sub(arg_分配图层大小, self._i))
            self.create_clone_of('_myself_')
            self._i = _sc_add(self._i, 1)
            self._yield_frame()
        _sc_list_insert(self.FortunateOS_窗口图层管理, 1, arg_分配图层大小)
        _sc_list_insert(self.FortunateOS_窗口图层管理, 1, arg_窗口ID)


    @_as_procedure(warp=True, arg_types=['s', 's'], arg_names=['窗口ID', '新分配长度'], proccode='将 %s 窗口ID的分配长度设置为 %s', arg_ids=[':PpoL/S7%?y~7ne`|G;V', 'y2Sl=wnX][2`URa`n{RM'], arg_defaults=['', ''])
    def 将_窗口ID的分配长度设置为(self, arg_窗口ID=0, arg_新分配长度=0):
        """自制积木: 将 %s 窗口ID的分配长度设置为 %s"""
        self.返回值 = 'NO'
        self._i = '0'
        while not _sc_bool(_sc_eq(self._i, len(self.FortunateOS_窗口图层管理))):
            self._i = _sc_add(self._i, 1)
            if _sc_bool(_sc_eq(_sc_item_of(self.FortunateOS_窗口图层管理, self._i), arg_窗口ID)):
                self.返回值 = 'YES'
                self._i2 = _sc_item_of(self.FortunateOS_窗口图层管理, _sc_add(self._i, 1))
                self._i = _sc_add(self._i, 1)
                for _repeat in range(_sc_repeat_count(_sc_add(self._i2, 1))):
                    _sc_list_delete(self.FortunateOS_窗口图层管理, self._i)
                    self._yield_frame()
                self._i2 = '0'
                _sc_list_insert(self.FortunateOS_窗口图层管理, self._i, arg_新分配长度)
                self._i = _sc_add(self._i, 1)
                for _repeat in range(_sc_repeat_count(arg_新分配长度)):
                    self._i2 = _sc_add(self._i2, 1)
                    _sc_list_insert(self.FortunateOS_窗口图层管理, self._i, _sc_add(_sc_sub(arg_新分配长度, self._i2), 1))
                    self._yield_frame()
                self.stop('this script')
            else:
                self._i = _sc_add(self._i, 1)
                self._i = _sc_add(self._i, _sc_item_of(self.FortunateOS_窗口图层管理, self._i))
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s', 's'], arg_names=['窗口ID', '第几个组件'], proccode='查找 %s 该窗口ID中第 %s 组件的名称', arg_ids=['7xWuQzoyt9pigi}z$w6v', 'lTBx8NcP`c.OQGi_?tn{'], arg_defaults=['', ''])
    def 查找_该窗口ID中第_组件的名称(self, arg_窗口ID=0, arg_第几个组件=0):
        """自制积木: 查找 %s 该窗口ID中第 %s 组件的名称"""
        self.返回值3 = 'NO'
        self._i = '0'
        while not _sc_bool(_sc_eq(self._i, len(self.FortunateOS_窗口组件管理))):
            self._i = _sc_add(self._i, 1)
            if _sc_bool(_sc_eq(_sc_item_of(self.FortunateOS_窗口组件管理, self._i), arg_窗口ID)):
                self.返回值3 = _sc_item_of(self.FortunateOS_窗口组件管理, _sc_add(self._i, _sc_add(1, arg_第几个组件)))
                self.stop('this script')
            else:
                self._i = _sc_add(self._i, 1)
                self._i = _sc_add(self._i, _sc_item_of(self.FortunateOS_窗口组件管理, self._i))
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s', 's'], arg_names=['窗口ID', '组件列表'], proccode='为 %s 该窗口ID创建 %s 组件', arg_ids=['}#]s#?SN!?RSH=D5iI7j', '+qdFmv_,x.KlQvxS?6[5'], arg_defaults=['false', '', ''])
    def 为_该窗口ID创建_组件(self, arg_窗口ID=0, arg_组件列表=0):
        """自制积木: 为 %s 该窗口ID创建 %s 组件"""
        self.获取_该列表里面的所有元素_清理字符串内容_(arg_组件列表, _sc_not(True))
        self.FortunateOS_窗口组件管理.append(arg_窗口ID)
        self.FortunateOS_窗口组件管理.append(len(self.获取列表里面的所有元素_返回值))
        self._i = '0'
        for _repeat in range(_sc_repeat_count(len(self.获取列表里面的所有元素_返回值))):
            self._i = _sc_add(self._i, 1)
            self.FortunateOS_窗口组件管理.append(_sc_item_of(self.获取列表里面的所有元素_返回值, self._i))
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s', 's', 's'], arg_names=['窗口ID', 'x', 'y'], proccode='为 %s 该窗口ID创建一个X大小为 %s , Y大小为 %s ,的数据', arg_ids=[')_=FN(C60d9xmJX;fK.-', 'Hy;Swc,l_$::DbPbFK$n', 'g@hSN:B,`pQzCM0I!lxx'], arg_defaults=['', '', ''])
    def 为_该窗口ID创建一个X大小为_Y大小为_的数据(self, arg_窗口ID=0, arg_x=0, arg_y=0):
        """自制积木: 为 %s 该窗口ID创建一个X大小为 %s , Y大小为 %s ,的数据"""
        self.FortunateOS_窗口大小管理.append(arg_窗口ID)
        self.FortunateOS_窗口大小管理.append(arg_x)
        self.FortunateOS_窗口大小管理.append(arg_y)


    @_as_procedure(warp=True, arg_types=['s', 's'], arg_names=['窗口ID', '组件列表'], proccode='为 %s 窗口ID添加 %s 组件', arg_ids=['7.%h{%oVVO3l-9o$R~x_', 'Y*k~H.lUTl~k-LlY2D4H'], arg_defaults=['', '', '', ''])
    def 为_窗口ID添加_组件(self, arg_窗口ID=0, arg_组件列表=0):
        """自制积木: 为 %s 窗口ID添加 %s 组件"""
        self.获取_该列表里面的所有元素_清理字符串内容_(arg_组件列表, _sc_not(True))
        self.返回值 = 'NO'
        self._i = '0'
        while not _sc_bool(_sc_eq(self._i, len(self.FortunateOS_窗口组件管理))):
            self._i = _sc_add(self._i, 1)
            if _sc_bool(_sc_eq(_sc_item_of(self.FortunateOS_窗口组件管理, self._i), arg_窗口ID)):
                self.返回值 = 'YES'
                self._i2 = _sc_item_of(self.FortunateOS_窗口组件管理, _sc_add(self._i, 1))
                _sc_list_replace(self.FortunateOS_窗口组件管理, _sc_add(self._i, 1), _sc_add(_sc_item_of(self.FortunateOS_窗口组件管理, _sc_add(self._i, 1)), len(self.获取列表里面的所有元素_返回值)))
                self._i = _sc_add(self._i, _sc_add(self._i2, 1))
                self._i3 = len(self.获取列表里面的所有元素_返回值)
                for _repeat in range(_sc_repeat_count(len(self.获取列表里面的所有元素_返回值))):
                    self._i3 = _sc_add(self._i3, -1)
                    self._i = _sc_add(self._i, 1)
                    _sc_list_insert(self.FortunateOS_窗口组件管理, self._i, _sc_item_of(self.获取列表里面的所有元素_返回值, _sc_sub(len(self.获取列表里面的所有元素_返回值), self._i3)))
                    self._yield_frame()
                self.stop('this script')
            else:
                self._i = _sc_add(self._i, 1)
                self._i = _sc_add(self._i, _sc_item_of(self.FortunateOS_窗口组件管理, self._i))
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s', 's', 's', 's', 's', 's', 's'], arg_names=['分配图层大小', 'x大小', 'y大小', 'x', 'y', '分配图层组件', '克隆体额外信息'], proccode='新建一个窗口(分配图层大小: %s ,x大小: %s ,y大小: %s ,x: %s ,y: %s ,分配图层组件: %s ,克隆体额外信息: %s ]', arg_ids=['DhTlCcwBKhq:laMv;hQ;', '*IffGBU[=sU]a)=9|$zi', '/*RiBEtC*vYi,=J42mdz', '/:^4Af^W3v:D+XdNMENO', '}$W|r$DOiK#mryOpWSP|', 'QAC4!Ebh/prrGaKA9t)K', 'DqomB;k}:MEb8`1Mzvu='], arg_defaults=['', '', '', '', '', '', '', '', ''])
    def 新建一个窗口_分配图层大小_x大小_y大小_x_y_分配图层组件_克隆体额外信息_(self, arg_分配图层大小=0, arg_x大小=0, arg_y大小=0, arg_x=0, arg_y=0, arg_分配图层组件=0, arg_克隆体额外信息=0):
        """自制积木: 新建一个窗口(分配图层大小: %s ,x大小: %s ,y大小: %s ,x: %s ,y: %s ,分配图层组件: %s ,克隆体额外信息: %s ]"""
        if _sc_bool(_sc_eq(len(self.FortunateOS_窗口ID管理), '0')):
            self.FortunateOS_分配窗口ID = _sc_add(self.FortunateOS_分配窗口ID, 1)
            self.新建一个窗口_窗口ID_分配图层大小_x大小_y大小_x_y_分配图层组件_克隆体额外信息_(self.FortunateOS_分配窗口ID, arg_分配图层大小, arg_x大小, arg_y大小, arg_x, arg_y, arg_分配图层组件, arg_克隆体额外信息)
        else:
            self.新建一个窗口_窗口ID_分配图层大小_x大小_y大小_x_y_分配图层组件_克隆体额外信息_(_sc_item_of(self.FortunateOS_窗口ID管理, 1), arg_分配图层大小, arg_x大小, arg_y大小, arg_x, arg_y, arg_分配图层组件, arg_克隆体额外信息)
            _sc_list_delete(self.FortunateOS_窗口ID管理, 1)


    @_as_procedure(warp=True, arg_types=['s', 's', 's'], arg_names=['a', 'b', 'c'], proccode='获取 %s 该字符串的 %s ~ %s 个字符', arg_ids=[']?NeU/ICvf[UVIjK%0__', 'XCR_ZO0/CH3A#cRYcha7', '#TU.FEP(42oz4s4Dm7Pz'], arg_defaults=['', '', ''])
    def 获取_该字符串的_个字符(self, arg_a=0, arg_b=0, arg_c=0):
        """自制积木: 获取 %s 该字符串的 %s ~ %s 个字符"""
        self.获取a该字符串的b_c个字符_返回值 = ''
        self.获取a该字符串的b_c个字符_i = arg_b
        for _repeat in range(_sc_repeat_count(_sc_add(_sc_sub(arg_c, arg_b), 1))):
            self.获取a该字符串的b_c个字符_返回值 = _sc_join(self.获取a该字符串的b_c个字符_返回值, _sc_letter_of(self.获取a该字符串的b_c个字符_i, arg_a))
            self.获取a该字符串的b_c个字符_i = _sc_add(self.获取a该字符串的b_c个字符_i, 1)
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s', 'b'], arg_names=['列表', 'boolean'], proccode='获取 %s 该列表里面的所有元素 (清理字符串内容? %b )', arg_ids=['=yU}?H7?`kJK:a/)yd:O', 'sM`kSBu,VG8(-@wI}I-V'], arg_defaults=['', '', '', '', 'false'])
    def 获取_该列表里面的所有元素_清理字符串内容_(self, arg_列表=0, arg_boolean=False):
        """自制积木: 获取 %s 该列表里面的所有元素 (清理字符串内容? %b )"""
        self.获取列表里面的所有元素_返回值.clear()
        self.获取列表里面的所有元素_i = '0'
        self.获取列表里面的所有元素_j = '0'
        self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'YES'
        if _sc_bool(_sc_not(_sc_and(_sc_eq(_sc_letter_of(1, arg_列表), '['), _sc_eq(_sc_letter_of(_sc_length(arg_列表), arg_列表), ']')))):
            self.获取列表里面的所有元素_返回值.append('传入的参数不是列表!!!')
            self.stop('this script')
        while not _sc_bool(_sc_or(_sc_eq(_sc_length(arg_列表), self.获取列表里面的所有元素_i), _sc_lt(_sc_length(arg_列表), self.获取列表里面的所有元素_i))):
            self.获取列表里面的所有元素_i = _sc_add(self.获取列表里面的所有元素_i, 1)
            self.获取列表里面的所有元素_j = _sc_add(self.获取列表里面的所有元素_j, 1)
            self.获取列表里面的所有元素_当前嵌套深度 = '0'
            self.获取列表里面的所有元素_临时缓存当前代码块 = ''
            self.获取列表里面的所有元素_当前嵌套字符 = ''
            if _sc_bool(_sc_not(_sc_or(_sc_eq(self.获取列表里面的所有元素_i, '1'), _sc_eq(self.获取列表里面的所有元素_i, _sc_length(arg_列表))))):
                while not _sc_bool(_sc_or(_sc_and(_sc_and(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), ','), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'YES')), _sc_eq(_sc_length(self.获取列表里面的所有元素_当前嵌套字符), '0')), _sc_or(_sc_eq(_sc_length(arg_列表), self.获取列表里面的所有元素_i), _sc_lt(_sc_length(arg_列表), self.获取列表里面的所有元素_i)))):
                    if _sc_bool(_sc_or(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), ' '), _sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), '\\'))):
                        if _sc_bool(_sc_or(_sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-1'), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-2'))):
                            self.获取列表里面的所有元素_临时缓存当前代码块 = _sc_join(self.获取列表里面的所有元素_临时缓存当前代码块, _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))
                    else:
                        self.获取列表里面的所有元素_临时缓存当前代码块 = _sc_join(self.获取列表里面的所有元素_临时缓存当前代码块, _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))
                    if _sc_bool(_sc_and(_sc_eq(_sc_length(self.获取列表里面的所有元素_临时缓存当前代码块), '1'), _sc_contains('("\'{[', _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表)))):
                        self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'NO'
                        if _sc_bool(_sc_not(_sc_contains('\'"', _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表)))):
                            self.获取列表里面的所有元素_当前嵌套深度 = '1'
                            self.获取列表里面的所有元素_当前嵌套字符 = _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表)
                        else:
                            if _sc_bool(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), "'")):
                                self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'NO-0'
                            else:
                                self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'NO-1'
                    else:
                        if _sc_bool(_sc_not(_sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'YES'))):
                            if _sc_bool(_sc_not(_sc_eq(self.获取列表里面的所有元素_当前嵌套深度, '0'))):
                                while not _sc_bool(_sc_or(_sc_eq(_sc_length(self.获取列表里面的所有元素_当前嵌套字符), '0'), _sc_or(_sc_eq(_sc_length(arg_列表), self.获取列表里面的所有元素_i), _sc_lt(_sc_length(arg_列表), self.获取列表里面的所有元素_i)))):
                                    self.获取列表里面的所有元素_i = _sc_add(self.获取列表里面的所有元素_i, 1)
                                    self.获取列表里面的所有元素_临时缓存当前代码块 = _sc_join(self.获取列表里面的所有元素_临时缓存当前代码块, _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))
                                    if _sc_bool(_sc_contains('\'"()[]{}', _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))):
                                        if _sc_bool(_sc_contains('\'")]}', _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))):
                                            if _sc_bool(_sc_contains('\'"', _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))):
                                                if _sc_bool(_sc_and(_sc_eq(_sc_letter_of(_sc_length(self.获取列表里面的所有元素_当前嵌套字符), self.获取列表里面的所有元素_当前嵌套字符), _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表)), _sc_eq(_sc_letter_of(_sc_sub(self.获取列表里面的所有元素_i, 1), arg_列表), '\\'))):
                                                    self.获取列表里面的所有元素_辅助变量2 = '0'
                                                    self.获取列表里面的所有元素_辅助变量 = ''
                                                    while not _sc_bool(_sc_eq(self.获取列表里面的所有元素_辅助变量2, _sc_sub(_sc_length(self.获取列表里面的所有元素_当前嵌套字符), 1))):
                                                        self.获取列表里面的所有元素_辅助变量2 = _sc_add(self.获取列表里面的所有元素_辅助变量2, 1)
                                                        self.获取列表里面的所有元素_辅助变量 = _sc_join(self.获取列表里面的所有元素_辅助变量, _sc_letter_of(self.获取列表里面的所有元素_辅助变量2, self.获取列表里面的所有元素_当前嵌套字符))
                                                        self._yield_frame()
                                                    self.获取列表里面的所有元素_当前嵌套字符 = self.获取列表里面的所有元素_辅助变量
                                            else:
                                                self.获取列表里面的所有元素_辅助变量2 = '0'
                                                self.获取列表里面的所有元素_辅助变量 = ''
                                                while not _sc_bool(_sc_eq(self.获取列表里面的所有元素_辅助变量2, _sc_sub(_sc_length(self.获取列表里面的所有元素_当前嵌套字符), 1))):
                                                    self.获取列表里面的所有元素_辅助变量2 = _sc_add(self.获取列表里面的所有元素_辅助变量2, 1)
                                                    self.获取列表里面的所有元素_辅助变量 = _sc_join(self.获取列表里面的所有元素_辅助变量, _sc_letter_of(self.获取列表里面的所有元素_辅助变量2, self.获取列表里面的所有元素_当前嵌套字符))
                                                    self._yield_frame()
                                                self.获取列表里面的所有元素_当前嵌套字符 = self.获取列表里面的所有元素_辅助变量
                                        else:
                                            self.获取列表里面的所有元素_当前嵌套深度 = _sc_add(self.获取列表里面的所有元素_当前嵌套深度, 1)
                                            self.获取列表里面的所有元素_当前嵌套字符 = _sc_join(self.获取列表里面的所有元素_当前嵌套字符, _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))
                                    self._yield_frame()
                                self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'YES'
                            else:
                                if _sc_bool(_sc_or(_sc_and(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), "'"), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-0')), _sc_and(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), '"'), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-1')))):
                                    if _sc_bool(_sc_and(_sc_or(_sc_and(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), "'"), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-0')), _sc_and(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), '"'), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-1'))), _sc_not(_sc_eq(_sc_letter_of(_sc_sub(self.获取列表里面的所有元素_i, 1), arg_列表), '\\')))):
                                        self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'YES'
                    self.获取列表里面的所有元素_i = _sc_add(self.获取列表里面的所有元素_i, 1)
                    self._yield_frame()
                self.获取列表里面的所有元素_返回值.append(self.获取列表里面的所有元素_临时缓存当前代码块)
            self._yield_frame()
        if _sc_bool(arg_boolean):
            self._i = '0'
            for _repeat in range(_sc_repeat_count(len(self.获取列表里面的所有元素_返回值))):
                self._i = _sc_add(self._i, 1)
                if _sc_bool(_sc_or(_sc_and(_sc_eq(_sc_letter_of(1, _sc_item_of(self.获取列表里面的所有元素_返回值, self._i)), '"'), _sc_eq(_sc_letter_of(_sc_length(_sc_item_of(self.获取列表里面的所有元素_返回值, self._i)), _sc_item_of(self.获取列表里面的所有元素_返回值, self._i)), '"')), _sc_and(_sc_eq(_sc_letter_of(1, _sc_item_of(self.获取列表里面的所有元素_返回值, self._i)), "'"), _sc_eq(_sc_letter_of(_sc_length(_sc_item_of(self.获取列表里面的所有元素_返回值, self._i)), _sc_item_of(self.获取列表里面的所有元素_返回值, self._i)), "'")))):
                    self.去除字符串额外数据(_sc_item_of(self.获取列表里面的所有元素_返回值, self._i))
                    _sc_list_replace(self.获取列表里面的所有元素_返回值, self._i, self.去除字符串额外数据_返回值)
                self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s'], arg_names=['字符串'], proccode='去除字符串额外数据 %s', arg_ids=[':5/6pl02R3T8l28q$ufG'], arg_defaults=[''])
    def 去除字符串额外数据(self, arg_字符串=0):
        """自制积木: 去除字符串额外数据 %s"""
        self.去除字符串额外数据_返回值 = ''
        self._j = '1'
        while not _sc_bool(_sc_lt(_sc_sub(_sc_length(arg_字符串), 2), self._j)):
            self._j = _sc_add(self._j, 1)
            if _sc_bool(_sc_and(_sc_eq(_sc_letter_of(self._j, arg_字符串), '\\'), _sc_or(_sc_eq(_sc_letter_of(_sc_add(self._j, 1), arg_字符串), "'"), _sc_or(_sc_eq(_sc_letter_of(_sc_add(self._j, 1), arg_字符串), '"'), _sc_eq(_sc_letter_of(_sc_add(self._j, 1), arg_字符串), '\\'))))):
                self._j = _sc_add(self._j, 1)
                self.去除字符串额外数据_返回值 = _sc_join(self.去除字符串额外数据_返回值, _sc_letter_of(self._j, arg_字符串))
            else:
                self.去除字符串额外数据_返回值 = _sc_join(self.去除字符串额外数据_返回值, _sc_letter_of(self._j, arg_字符串))
            self._yield_frame()


    def when_broadcast_开机_FortunateOS(self):
        """当接收到广播'开机-FortunateOS'时"""
        pass


    def when_green_flag(self):
        """当绿旗被点击时"""
        self.删除所有管理窗口()
        self.FortunateOS_分配窗口ID = '0'
        self.FortunateOS_鼠标是否被占用_ = '0'


    def when_green_flag_2(self):
        """当绿旗被点击时"""
        self.是否为克隆体_ = '0'
        while self._running:
            self.生成所有窗口的偏移量()
            self._yield_frame()


    def when_clone_starts(self):
        """当作为克隆体启动时"""
        self.是否为克隆体_ = _sc_add(self.是否为克隆体_, 1)
        self.查找_该窗口ID中第_组件的名称(self.绑定窗口ID, self.窗口组件ID)
        self.获取_该字符串的_个字符(self.返回值3, '1', '3')
        if _sc_bool(_sc_list_contains(self.FortunateOS_全部主题名称, self.获取a该字符串的b_c个字符_返回值)):
            self.switch_costume(self.返回值3)
            self.获取_该字符串的_个字符(self.返回值3, '5', _sc_length(self.返回值3))
            self.窗口组件名称 = self.获取a该字符串的b_c个字符_返回值
        else:
            self.switch_costume(_sc_join(self.FortunateOS_当前主题, _sc_join('-', self.返回值3)))
            self.窗口组件名称 = self.返回值3
        self.show()
        self.查找_该窗口ID的XY坐标(self.绑定窗口ID)
        if _sc_bool(_sc_eq(self.窗口组件名称, '标题栏')):
            self.change_effect('COLOR', 10)
        if _sc_bool(_sc_or(_sc_eq(self.窗口组件名称, '上拖动'), _sc_or(_sc_eq(self.窗口组件名称, '左上拖动'), _sc_eq(self.窗口组件名称, '右上拖动')))):
            self.change_effect('COLOR', 10)
        if _sc_bool(_sc_or(_sc_eq(self.窗口组件名称, '关闭按钮'), _sc_or(_sc_eq(self.窗口组件名称, '全屏按钮'), _sc_eq(self.窗口组件名称, '窗口最小化')))):
            if _sc_bool(_sc_not(_sc_eq(self.FortunateOS_当前主题, 'os1'))):
                self.change_effect('COLOR', 10)
            else:
                self.clear_effects()
        while self._running:
            self.查找_该窗口ID的XY坐标(self.绑定窗口ID)
            if _sc_bool(_sc_eq(self.返回值5, 'NO')):
                self.delete_this_clone()
            self.切换对应图层()
            self.goto_xy(self.返回值5, self.返回值6)
            self._yield_frame()


    def when_green_flag_3(self):
        """当绿旗被点击时"""
        self.hide()
        self.set_drag_mode('not draggable')
        while self._running:
            self.wait_until(lambda: _sc_bool(_sc_not(_sc_eq(len(self.FortunateOS_窗口系统执行), '0'))))
            self.change_effect('COLOR', _sc_random(1, 100))
            self.获取_该列表里面的所有元素_清理字符串内容_(_sc_item_of(self.FortunateOS_窗口系统执行, 1), _sc_not(True))
            self.新建一个窗口_分配图层大小_x大小_y大小_x_y_分配图层组件_克隆体额外信息_(_sc_item_of(self.获取列表里面的所有元素_返回值, 1), _sc_item_of(self.获取列表里面的所有元素_返回值, 2), _sc_item_of(self.获取列表里面的所有元素_返回值, 3), _sc_item_of(self.获取列表里面的所有元素_返回值, 4), _sc_item_of(self.获取列表里面的所有元素_返回值, 5), _sc_item_of(self.获取列表里面的所有元素_返回值, 6), _sc_item_of(self.获取列表里面的所有元素_返回值, 7))
            _sc_list_delete(self.FortunateOS_窗口系统执行, 1)
            self._yield_frame()


    def when_clone_starts_2(self):
        """当作为克隆体启动时"""
        if _sc_bool(_sc_or(_sc_eq(self.窗口组件名称, '关闭按钮'), _sc_or(_sc_eq(self.窗口组件名称, '全屏按钮'), _sc_eq(self.窗口组件名称, '窗口最小化')))):
            while self._running:
                self.wait_until(lambda: _sc_bool(self.touching('_mouse_')))
                self.switch_costume(_sc_join(_sc_join(self.FortunateOS_当前主题, _sc_join('-', self.窗口组件名称)), '-被碰到'))
                self.wait_until(lambda: _sc_bool(_sc_not(self.touching('_mouse_'))))
                self.switch_costume(_sc_join(self.FortunateOS_当前主题, _sc_join('-', self.窗口组件名称)))
                self._yield_frame()


    def when_clicked(self):
        """当角色被点击时"""
        if _sc_bool(_sc_eq(self.是否为克隆体_, '1')):
            self.将_该窗口ID的窗口移到最前面(self.绑定窗口ID)
            if _sc_bool(_sc_eq(self.窗口组件名称, '标题栏')):
                if _sc_bool(_sc_eq(self.FortunateOS_鼠标是否被占用_, '0')):
                    self.wait_until(lambda: _sc_bool(self.mouse_down))
                    self.将_该窗口ID的窗口移到最前面(self.绑定窗口ID)
                    self.标题栏_拖动相关逻辑_查找替换位置()
                    self.FortunateOS_鼠标是否被占用_ = '1'
                    self.i = self._i
                    self.x1 = _sc_sub(self.返回值5, self.mouse_x)
                    self.y1 = _sc_sub(self.返回值6, self.mouse_y)
                    while not _sc_bool(_sc_not(self.mouse_down)):
                        self.标题栏_拖动相关逻辑_坐标替换()
                        self.goto_xy(_sc_add(self.mouse_x, self.x1), _sc_add(self.mouse_y, self.y1))
                        self._yield_frame()
                    self.FortunateOS_鼠标是否被占用_ = '0'
            if _sc_bool(_sc_eq(self.窗口组件名称, '关闭按钮')):
                if _sc_bool(_sc_eq(self.FortunateOS_鼠标是否被占用_, '0')):
                    self.wait_until(lambda: _sc_bool(self.mouse_down))
                    self.wait_until(lambda: _sc_bool(_sc_not(self.mouse_down)))
                    if _sc_bool(self.touching('_mouse_')):
                        self.删除掉_该窗口ID的窗口(self.绑定窗口ID)


    def run(self):
        """向运行时注册事件脚本"""
        self._register('broadcast:开机-FortunateOS', self.when_broadcast_开机_FortunateOS)
        self._register('green_flag', self.when_green_flag)
        self._register('green_flag', self.when_green_flag_2)
        self._register('clone_start', self.when_clone_starts)
        self._register('green_flag', self.when_green_flag_3)
        self._register('clone_start', self.when_clone_starts_2)
        self._register('clicked', self.when_clicked)

class FortunateOS_文件管理(ScratchSprite):
    """精灵: FortunateOS-文件管理"""

    GLOBAL_NAMES = ('FortunateOS_中转执行类型', 'FortunateOS_中转系统执行', 'FortunateOS_中转系统返回', 'FortunateOS_全部主题名称', 'FortunateOS_分配窗口ID', 'FortunateOS_命令系统执行', 'FortunateOS_命令系统权限', 'FortunateOS_开始菜单是否被开启_', 'FortunateOS_当前主题', 'FortunateOS_当前是否进入桌面', 'FortunateOS_文件内容管理', 'FortunateOS_文件属性管理', 'FortunateOS_文件执行类型', 'FortunateOS_文件系统属性', 'FortunateOS_文件系统执行', 'FortunateOS_文件系统返回', 'FortunateOS_文件路径管理', 'FortunateOS_是否开启锁屏_', 'FortunateOS_窗口ID管理', 'FortunateOS_窗口图层偏移', 'FortunateOS_窗口图层管理', 'FortunateOS_窗口坐标管理', 'FortunateOS_窗口大小管理', 'FortunateOS_窗口系统执行', 'FortunateOS_窗口组件管理', 'FortunateOS_管理设置选项', 'FortunateOS_系统版本号', 'FortunateOS_鼠标是否被占用_', '任务栏动画_i', '我的变量')
    GLOBAL_NAMES_SET = frozenset(GLOBAL_NAMES)

    def __init__(self):
        super().__init__()
        self.x = 0
        self.y = 0
        self.direction = 90
        self.visible = False
        self.size = 100
        self.name = 'FortunateOS-文件管理'
        self.rotation_style = 'all around'
        self.draggable = False
        self.costumes = [{'name': '造型1', 'md5ext': '9a02fc97309faf4de9cdb8de27b90ea0.svg', 'dataFormat': 'svg', 'rotationCenterX': 31.365489999999994, 'rotationCenterY': 25.94874999999999}]
        self.sounds = []
        self.costume_number = 1
        self.costume_name = '造型1'

        self.拆分路径_i = 16
        self.拆分路径_t = '7'
        self.添加一个目录或文件_i = 7
        self.添加一个目录或文件_t = 'C:/1/2/3/4/5/6/'
        self.添加一个目录或文件_j = 15
        self.添加一个目录或文件_返回值 = 200
        self.读取文件路径的内容_i = 9
        self.读取文件路径的内容_返回值 = 200
        self.读取文件路径的内容_内容 = '/'
        self.删除文件路径的内容_返回值 = 200
        self.删除文件路径的内容_i = 2
        self.获取列表里面的所有元素_i = 0
        self.获取列表里面的所有元素_j = 0
        self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 0
        self.获取列表里面的所有元素_当前嵌套深度 = 0
        self.获取列表里面的所有元素_临时缓存当前代码块 = 0
        self.获取列表里面的所有元素_当前嵌套字符 = 0
        self.获取列表里面的所有元素_辅助变量2 = 0
        self.获取列表里面的所有元素_辅助变量 = 0
        self._i = 0
        self.去除字符串额外数据_返回值 = 0
        self._j = 0
        self.获取a该字符串的b_c个字符_返回值 = 0
        self.获取a该字符串的b_c个字符_i = 0
        self.获取一个文件的所在文件夹_i = 3
        self.获取一个文件的所在文件夹_j = 3
        self.获取一个文件的所在文件夹_返回值 = 'C:/'
        self.获取路径目录_i = 1
        self.获取路径目录_j = 3
        self.递归创建文件夹_i = 8
        self.递归创建文件夹_k = 'C:/1/2/3/4/5/6/7'
        self.读取文件路径的属性_属性 = '/'
        self.读取文件路径的属性_i = 9
        self.读取文件路径的属性_返回值 = 200
        self.合并临时列表_返回值 = '[""]'
        self.获取路径目录_获取一个文件的所在文件夹_上级或本身目录_i = 0
        self.获取路径目录_获取一个文件的所在文件夹_上级或本身目录_返回值 = 0
        self.获取路径目录_获取一个文件的所在文件夹_上级或本身目录_j = 0

        self.路径拆分 = ['C:', '1', '2', '3', '4', '5', '6', '7']
        self.获取列表里面的所有元素_返回值 = []
        self.临时列表 = []
        self._临时列表 = ['C:/']

    @_as_procedure(warp=True, arg_types=['s'], arg_names=['文件路径'], proccode='获取路径目录 - 获取一个文件的所在文件夹 (上级或本身目录) %s', arg_ids=['0@v(n8O3(M*~5:C{;GiX'], arg_defaults=[''])
    def 获取路径目录_获取一个文件的所在文件夹_上级或本身目录_(self, arg_文件路径=0):
        """自制积木: 获取路径目录 - 获取一个文件的所在文件夹 (上级或本身目录) %s"""
        self.获取路径目录_获取一个文件的所在文件夹_上级或本身目录_i = _sc_length(_sc_item_of(self.FortunateOS_文件路径管理, _sc_list_item_number(self.FortunateOS_文件路径管理, arg_文件路径)))
        if _sc_bool(_sc_eq(self.获取路径目录_获取一个文件的所在文件夹_上级或本身目录_i, '0')):
            self.获取路径目录_获取一个文件的所在文件夹_上级或本身目录_i = '100'
            self.stop('this script')
        while not _sc_bool(_sc_or(_sc_eq(_sc_letter_of(self.获取路径目录_获取一个文件的所在文件夹_上级或本身目录_i, arg_文件路径), '/'), _sc_eq(self.获取路径目录_获取一个文件的所在文件夹_上级或本身目录_i, '0'))):
            self.获取路径目录_获取一个文件的所在文件夹_上级或本身目录_i = _sc_add(self.获取路径目录_获取一个文件的所在文件夹_上级或本身目录_i, -1)
            self._yield_frame()
        self.获取路径目录_获取一个文件的所在文件夹_上级或本身目录_j = '0'
        self.获取路径目录_获取一个文件的所在文件夹_上级或本身目录_返回值 = ''
        for _repeat in range(_sc_repeat_count(self.获取路径目录_获取一个文件的所在文件夹_上级或本身目录_i)):
            self.获取路径目录_获取一个文件的所在文件夹_上级或本身目录_j = _sc_add(self.获取路径目录_获取一个文件的所在文件夹_上级或本身目录_j, 1)
            self.获取路径目录_获取一个文件的所在文件夹_上级或本身目录_返回值 = _sc_join(self.获取路径目录_获取一个文件的所在文件夹_上级或本身目录_返回值, _sc_letter_of(self.获取路径目录_获取一个文件的所在文件夹_上级或本身目录_j, arg_文件路径))
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s'], arg_names=['路径字符串'], proccode='拆分路径 %s', arg_ids=['}0o}+)GZ[,(|3txWmPvD'], arg_defaults=[''])
    def 拆分路径(self, arg_路径字符串=0):
        """自制积木: 拆分路径 %s"""
        self.拆分路径_i = '0'
        self.拆分路径_t = ''
        self.路径拆分.clear()
        while not _sc_bool(_sc_gt(self.拆分路径_i, _sc_sub(_sc_length(arg_路径字符串), 1))):
            self.拆分路径_i = _sc_add(self.拆分路径_i, 1)
            if _sc_bool(_sc_and(_sc_contains('/', _sc_letter_of(self.拆分路径_i, arg_路径字符串)), _sc_not(_sc_eq(self.拆分路径_t, '')))):
                self.路径拆分.append(self.拆分路径_t)
                self.拆分路径_t = ''
            else:
                self.拆分路径_t = _sc_join(self.拆分路径_t, _sc_letter_of(self.拆分路径_i, arg_路径字符串))
            self._yield_frame()
        if _sc_bool(_sc_not(_sc_eq(self.拆分路径_t, ''))):
            self.路径拆分.append(self.拆分路径_t)


    @_as_procedure(warp=True, arg_types=['s', 's', 's'], arg_names=['路径字符串', '文件内容', '文件属性'], proccode='添加一个目录或文件 %s 文件内容 %s 文件属性 %s', arg_ids=['oxi5}_01r!)^py1[di~s', '@nC6Pe5A~PcVMk0Y_9g}', ':MBru1A[xyz6TO^f)D2H'], arg_defaults=['', '', '', ''])
    def 添加一个目录或文件_文件内容_文件属性(self, arg_路径字符串=0, arg_文件内容=0, arg_文件属性=0):
        """自制积木: 添加一个目录或文件 %s 文件内容 %s 文件属性 %s"""
        self.添加一个目录或文件_i = _sc_length(arg_路径字符串)
        self.添加一个目录或文件_t = ''
        while not _sc_bool(_sc_or(_sc_eq(_sc_letter_of(self.添加一个目录或文件_i, arg_路径字符串), '/'), _sc_eq(self.添加一个目录或文件_i, '0'))):
            self.添加一个目录或文件_i = _sc_add(self.添加一个目录或文件_i, -1)
            self._yield_frame()
        if _sc_bool(_sc_eq(self.添加一个目录或文件_i, '0')):
            self.添加一个目录或文件_返回值 = '100'
        self.添加一个目录或文件_j = '0'
        for _repeat in range(_sc_repeat_count(self.添加一个目录或文件_i)):
            self.添加一个目录或文件_j = _sc_add(self.添加一个目录或文件_j, 1)
            self.添加一个目录或文件_t = _sc_join(self.添加一个目录或文件_t, _sc_letter_of(self.添加一个目录或文件_j, arg_路径字符串))
            self._yield_frame()
        self.添加一个目录或文件_i = _sc_list_item_number(self.FortunateOS_文件路径管理, self.添加一个目录或文件_t)
        if _sc_bool(_sc_eq(self.添加一个目录或文件_i, '0')):
            self.添加一个目录或文件_返回值 = '100'
        else:
            if _sc_bool(_sc_eq(arg_文件内容, '/')):
                if _sc_bool(_sc_list_contains(self.FortunateOS_文件路径管理, arg_路径字符串)):
                    _sc_list_replace(self.FortunateOS_文件路径管理, _sc_list_item_number(self.FortunateOS_文件路径管理, arg_路径字符串), _sc_join(arg_路径字符串, '/'))
                    _sc_list_replace(self.FortunateOS_文件内容管理, _sc_list_item_number(self.FortunateOS_文件路径管理, arg_路径字符串), arg_文件内容)
                    _sc_list_replace(self.FortunateOS_文件属性管理, _sc_list_item_number(self.FortunateOS_文件路径管理, arg_路径字符串), arg_文件属性)
                    self.添加一个目录或文件_返回值 = '200'
                else:
                    _sc_list_insert(self.FortunateOS_文件路径管理, _sc_add(self.添加一个目录或文件_i, 1), _sc_join(arg_路径字符串, '/'))
                    _sc_list_insert(self.FortunateOS_文件内容管理, _sc_add(self.添加一个目录或文件_i, 1), arg_文件内容)
                    _sc_list_insert(self.FortunateOS_文件属性管理, _sc_add(self.添加一个目录或文件_i, 1), arg_文件属性)
                    self.添加一个目录或文件_返回值 = '200'
            else:
                if _sc_bool(_sc_list_contains(self.FortunateOS_文件路径管理, arg_路径字符串)):
                    _sc_list_replace(self.FortunateOS_文件路径管理, _sc_list_item_number(self.FortunateOS_文件路径管理, arg_路径字符串), arg_路径字符串)
                    _sc_list_replace(self.FortunateOS_文件内容管理, _sc_list_item_number(self.FortunateOS_文件路径管理, arg_路径字符串), arg_文件内容)
                    _sc_list_replace(self.FortunateOS_文件属性管理, _sc_list_item_number(self.FortunateOS_文件路径管理, arg_路径字符串), arg_文件属性)
                    self.添加一个目录或文件_返回值 = '200'
                else:
                    _sc_list_insert(self.FortunateOS_文件路径管理, _sc_add(self.添加一个目录或文件_i, 1), arg_路径字符串)
                    _sc_list_insert(self.FortunateOS_文件内容管理, _sc_add(self.添加一个目录或文件_i, 1), arg_文件内容)
                    _sc_list_insert(self.FortunateOS_文件属性管理, _sc_add(self.添加一个目录或文件_i, 1), arg_文件属性)
                    self.添加一个目录或文件_返回值 = '200'


    @_as_procedure(warp=True, arg_types=['s'], arg_names=['字符串'], proccode='去除字符串额外数据 %s', arg_ids=[':5/6pl02R3T8l28q$ufG'], arg_defaults=[''])
    def 去除字符串额外数据(self, arg_字符串=0):
        """自制积木: 去除字符串额外数据 %s"""
        self.去除字符串额外数据_返回值 = ''
        self._j = '1'
        while not _sc_bool(_sc_lt(_sc_sub(_sc_length(arg_字符串), 2), self._j)):
            self._j = _sc_add(self._j, 1)
            if _sc_bool(_sc_and(_sc_eq(_sc_letter_of(self._j, arg_字符串), '\\'), _sc_or(_sc_eq(_sc_letter_of(_sc_add(self._j, 1), arg_字符串), "'"), _sc_or(_sc_eq(_sc_letter_of(_sc_add(self._j, 1), arg_字符串), '"'), _sc_eq(_sc_letter_of(_sc_add(self._j, 1), arg_字符串), '\\'))))):
                self._j = _sc_add(self._j, 1)
                self.去除字符串额外数据_返回值 = _sc_join(self.去除字符串额外数据_返回值, _sc_letter_of(self._j, arg_字符串))
            else:
                self.去除字符串额外数据_返回值 = _sc_join(self.去除字符串额外数据_返回值, _sc_letter_of(self._j, arg_字符串))
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s', 'b', 'b'], arg_names=['路径', '是否展开', '是否为相对路径'], proccode='获取路径目录扫描 %s %b %b', arg_ids=['KU;r@Il/!kWi8[w+Mcmx', 'tt6xv7)UGfyO0-qDrjP$', '.MYg3^6f[U1Xqh@5q|FL'], arg_defaults=['', '', 'false', 'false'])
    def 获取路径目录扫描(self, arg_路径=0, arg_是否展开=False, arg_是否为相对路径=False):
        """自制积木: 获取路径目录扫描 %s %b %b"""
        self.临时列表.clear()
        self._临时列表.clear()
        self.获取路径目录_获取一个文件的所在文件夹_上级或本身目录_(arg_路径)
        self.获取路径目录_i = _sc_list_item_number(self.FortunateOS_文件路径管理, self.获取一个文件的所在文件夹_返回值)
        self.获取路径目录_j = _sc_length(self.获取一个文件的所在文件夹_返回值)
        self._临时列表.append(self.获取一个文件的所在文件夹_返回值)
        while not _sc_bool(_sc_eq(self.获取路径目录_i, len(self.FortunateOS_文件路径管理))):
            self.获取路径目录_i = _sc_add(self.获取路径目录_i, 1)
            if _sc_bool(_sc_eq(_sc_item_of(self.FortunateOS_文件内容管理, self.获取路径目录_i), '/')):
                self.获取_该字符串的_个字符(_sc_item_of(self.FortunateOS_文件路径管理, self.获取路径目录_i), '1', _sc_length(_sc_item_of(self._临时列表, 1)))
                if _sc_bool(_sc_not(_sc_eq(self.获取a该字符串的b_c个字符_返回值, _sc_item_of(self._临时列表, 1)))):
                    self.stop('this script')
                if _sc_bool(_sc_or(_sc_eq(len(self._临时列表), '1'), arg_是否展开)):
                    self.临时列表.append(_sc_item_of(self.FortunateOS_文件路径管理, self.获取路径目录_i))
                self.获取_该字符串的_个字符(_sc_item_of(self.FortunateOS_文件路径管理, self.获取路径目录_i), '1', self.获取路径目录_j)
                if _sc_bool(_sc_eq(self.获取a该字符串的b_c个字符_返回值, _sc_item_of(self._临时列表, len(self._临时列表)))):
                    self._临时列表.append(_sc_item_of(self.FortunateOS_文件路径管理, self.获取路径目录_i))
                    self.获取路径目录_j = _sc_length(_sc_item_of(self._临时列表, len(self._临时列表)))
                else:
                    _sc_list_delete(self._临时列表, len(self._临时列表))
                    if _sc_bool(_sc_eq(len(self._临时列表), '1')):
                        self.临时列表.append(_sc_item_of(self.FortunateOS_文件路径管理, self.获取路径目录_i))
                    self._临时列表.append(_sc_item_of(self.FortunateOS_文件路径管理, self.获取路径目录_i))
            else:
                self.获取_该字符串的_个字符(_sc_item_of(self.FortunateOS_文件路径管理, self.获取路径目录_i), '1', _sc_length(_sc_item_of(self._临时列表, 1)))
                if _sc_bool(_sc_not(_sc_eq(self.获取a该字符串的b_c个字符_返回值, _sc_item_of(self._临时列表, 1)))):
                    self.stop('this script')
                self.获取路径目录_获取一个文件的所在文件夹_上级或本身目录_(_sc_item_of(self.FortunateOS_文件路径管理, self.获取路径目录_i))
                if _sc_bool(_sc_not(_sc_eq(self.获取一个文件的所在文件夹_返回值, _sc_item_of(self._临时列表, len(self._临时列表))))):
                    _sc_list_delete(self._临时列表, len(self._临时列表))
                    self.获取路径目录_j = _sc_length(_sc_item_of(self._临时列表, len(self._临时列表)))
                if _sc_bool(_sc_or(_sc_eq(len(self._临时列表), '1'), arg_是否展开)):
                    self.临时列表.append(_sc_item_of(self.FortunateOS_文件路径管理, self.获取路径目录_i))
            self._yield_frame()
        if _sc_bool(arg_是否为相对路径):
            self.获取路径目录_i = '0'
            self.获取路径目录_j = _sc_add(_sc_length(_sc_item_of(self._临时列表, 1)), 1)
            for _repeat in range(_sc_repeat_count(len(self.临时列表))):
                self.获取路径目录_i = _sc_add(self.获取路径目录_i, 1)
                self.获取_该字符串的_个字符(_sc_item_of(self.临时列表, self.获取路径目录_i), self.获取路径目录_j, _sc_length(_sc_item_of(self.临时列表, self.获取路径目录_i)))
                _sc_list_replace(self.临时列表, self.获取路径目录_i, self.获取a该字符串的b_c个字符_返回值)
                self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s', 's', 's'], arg_names=['a', 'b', 'c'], proccode='获取 %s 该字符串的 %s ~ %s 个字符', arg_ids=[']?NeU/ICvf[UVIjK%0__', 'XCR_ZO0/CH3A#cRYcha7', '#TU.FEP(42oz4s4Dm7Pz'], arg_defaults=['', '', ''])
    def 获取_该字符串的_个字符(self, arg_a=0, arg_b=0, arg_c=0):
        """自制积木: 获取 %s 该字符串的 %s ~ %s 个字符"""
        self.获取a该字符串的b_c个字符_返回值 = ''
        self.获取a该字符串的b_c个字符_i = arg_b
        for _repeat in range(_sc_repeat_count(_sc_add(_sc_sub(arg_c, arg_b), 1))):
            self.获取a该字符串的b_c个字符_返回值 = _sc_join(self.获取a该字符串的b_c个字符_返回值, _sc_letter_of(self.获取a该字符串的b_c个字符_i, arg_a))
            self.获取a该字符串的b_c个字符_i = _sc_add(self.获取a该字符串的b_c个字符_i, 1)
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s'], arg_names=['路径'], proccode='递归创建文件夹 %s', arg_ids=['4@xtp$~vX*[N^WPq7ck2'], arg_defaults=[''])
    def 递归创建文件夹(self, arg_路径=0):
        """自制积木: 递归创建文件夹 %s"""
        self.拆分路径(arg_路径)
        self.递归创建文件夹_i = '1'
        self.递归创建文件夹_k = _sc_item_of(self.路径拆分, 1)
        while not _sc_bool(_sc_or(_sc_not(_sc_list_contains(self.FortunateOS_文件路径管理, self.递归创建文件夹_k)), _sc_eq(self.递归创建文件夹_i, len(self.路径拆分)))):
            self.递归创建文件夹_i = _sc_add(self.递归创建文件夹_i, 1)
            self.递归创建文件夹_k = _sc_join(self.递归创建文件夹_k, _sc_join('/', _sc_item_of(self.路径拆分, self.递归创建文件夹_i)))
            self._yield_frame()
        for _repeat in range(_sc_repeat_count(_sc_sub(len(self.路径拆分), self.递归创建文件夹_i))):
            self.添加一个目录或文件_文件内容_文件属性(self.递归创建文件夹_k, '/', '/')
            self.递归创建文件夹_i = _sc_add(self.递归创建文件夹_i, 1)
            self.递归创建文件夹_k = _sc_join(self.递归创建文件夹_k, _sc_join('/', _sc_item_of(self.路径拆分, self.递归创建文件夹_i)))
            self._yield_frame()
        self.添加一个目录或文件_文件内容_文件属性(self.递归创建文件夹_k, '/', '/')


    @_as_procedure(warp=True, arg_types=['s', 'b'], arg_names=['列表', 'boolean'], proccode='获取 %s 该列表里面的所有元素 (清理字符串内容? %b )', arg_ids=['=yU}?H7?`kJK:a/)yd:O', 'sM`kSBu,VG8(-@wI}I-V'], arg_defaults=['', '', '', '', 'false'])
    def 获取_该列表里面的所有元素_清理字符串内容_(self, arg_列表=0, arg_boolean=False):
        """自制积木: 获取 %s 该列表里面的所有元素 (清理字符串内容? %b )"""
        self.获取列表里面的所有元素_返回值.clear()
        self.获取列表里面的所有元素_i = '0'
        self.获取列表里面的所有元素_j = '0'
        self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'YES'
        if _sc_bool(_sc_not(_sc_and(_sc_eq(_sc_letter_of(1, arg_列表), '['), _sc_eq(_sc_letter_of(_sc_length(arg_列表), arg_列表), ']')))):
            self.获取列表里面的所有元素_返回值.append('传入的参数不是列表!!!')
            self.stop('this script')
        while not _sc_bool(_sc_or(_sc_eq(_sc_length(arg_列表), self.获取列表里面的所有元素_i), _sc_lt(_sc_length(arg_列表), self.获取列表里面的所有元素_i))):
            self.获取列表里面的所有元素_i = _sc_add(self.获取列表里面的所有元素_i, 1)
            self.获取列表里面的所有元素_j = _sc_add(self.获取列表里面的所有元素_j, 1)
            self.获取列表里面的所有元素_当前嵌套深度 = '0'
            self.获取列表里面的所有元素_临时缓存当前代码块 = ''
            self.获取列表里面的所有元素_当前嵌套字符 = ''
            if _sc_bool(_sc_not(_sc_or(_sc_eq(self.获取列表里面的所有元素_i, '1'), _sc_eq(self.获取列表里面的所有元素_i, _sc_length(arg_列表))))):
                while not _sc_bool(_sc_or(_sc_and(_sc_and(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), ','), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'YES')), _sc_eq(_sc_length(self.获取列表里面的所有元素_当前嵌套字符), '0')), _sc_or(_sc_eq(_sc_length(arg_列表), self.获取列表里面的所有元素_i), _sc_lt(_sc_length(arg_列表), self.获取列表里面的所有元素_i)))):
                    if _sc_bool(_sc_or(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), ' '), _sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), '\\'))):
                        if _sc_bool(_sc_or(_sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-1'), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-2'))):
                            self.获取列表里面的所有元素_临时缓存当前代码块 = _sc_join(self.获取列表里面的所有元素_临时缓存当前代码块, _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))
                    else:
                        self.获取列表里面的所有元素_临时缓存当前代码块 = _sc_join(self.获取列表里面的所有元素_临时缓存当前代码块, _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))
                    if _sc_bool(_sc_and(_sc_eq(_sc_length(self.获取列表里面的所有元素_临时缓存当前代码块), '1'), _sc_contains('("\'{[', _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表)))):
                        self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'NO'
                        if _sc_bool(_sc_not(_sc_contains('\'"', _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表)))):
                            self.获取列表里面的所有元素_当前嵌套深度 = '1'
                            self.获取列表里面的所有元素_当前嵌套字符 = _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表)
                        else:
                            if _sc_bool(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), "'")):
                                self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'NO-0'
                            else:
                                self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'NO-1'
                    else:
                        if _sc_bool(_sc_not(_sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'YES'))):
                            if _sc_bool(_sc_not(_sc_eq(self.获取列表里面的所有元素_当前嵌套深度, '0'))):
                                while not _sc_bool(_sc_or(_sc_eq(_sc_length(self.获取列表里面的所有元素_当前嵌套字符), '0'), _sc_or(_sc_eq(_sc_length(arg_列表), self.获取列表里面的所有元素_i), _sc_lt(_sc_length(arg_列表), self.获取列表里面的所有元素_i)))):
                                    self.获取列表里面的所有元素_i = _sc_add(self.获取列表里面的所有元素_i, 1)
                                    self.获取列表里面的所有元素_临时缓存当前代码块 = _sc_join(self.获取列表里面的所有元素_临时缓存当前代码块, _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))
                                    if _sc_bool(_sc_contains('\'"()[]{}', _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))):
                                        if _sc_bool(_sc_contains('\'")]}', _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))):
                                            if _sc_bool(_sc_contains('\'"', _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))):
                                                if _sc_bool(_sc_and(_sc_eq(_sc_letter_of(_sc_length(self.获取列表里面的所有元素_当前嵌套字符), self.获取列表里面的所有元素_当前嵌套字符), _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表)), _sc_eq(_sc_letter_of(_sc_sub(self.获取列表里面的所有元素_i, 1), arg_列表), '\\'))):
                                                    self.获取列表里面的所有元素_辅助变量2 = '0'
                                                    self.获取列表里面的所有元素_辅助变量 = ''
                                                    while not _sc_bool(_sc_eq(self.获取列表里面的所有元素_辅助变量2, _sc_sub(_sc_length(self.获取列表里面的所有元素_当前嵌套字符), 1))):
                                                        self.获取列表里面的所有元素_辅助变量2 = _sc_add(self.获取列表里面的所有元素_辅助变量2, 1)
                                                        self.获取列表里面的所有元素_辅助变量 = _sc_join(self.获取列表里面的所有元素_辅助变量, _sc_letter_of(self.获取列表里面的所有元素_辅助变量2, self.获取列表里面的所有元素_当前嵌套字符))
                                                        self._yield_frame()
                                                    self.获取列表里面的所有元素_当前嵌套字符 = self.获取列表里面的所有元素_辅助变量
                                            else:
                                                self.获取列表里面的所有元素_辅助变量2 = '0'
                                                self.获取列表里面的所有元素_辅助变量 = ''
                                                while not _sc_bool(_sc_eq(self.获取列表里面的所有元素_辅助变量2, _sc_sub(_sc_length(self.获取列表里面的所有元素_当前嵌套字符), 1))):
                                                    self.获取列表里面的所有元素_辅助变量2 = _sc_add(self.获取列表里面的所有元素_辅助变量2, 1)
                                                    self.获取列表里面的所有元素_辅助变量 = _sc_join(self.获取列表里面的所有元素_辅助变量, _sc_letter_of(self.获取列表里面的所有元素_辅助变量2, self.获取列表里面的所有元素_当前嵌套字符))
                                                    self._yield_frame()
                                                self.获取列表里面的所有元素_当前嵌套字符 = self.获取列表里面的所有元素_辅助变量
                                        else:
                                            self.获取列表里面的所有元素_当前嵌套深度 = _sc_add(self.获取列表里面的所有元素_当前嵌套深度, 1)
                                            self.获取列表里面的所有元素_当前嵌套字符 = _sc_join(self.获取列表里面的所有元素_当前嵌套字符, _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))
                                    self._yield_frame()
                                self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'YES'
                            else:
                                if _sc_bool(_sc_or(_sc_and(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), "'"), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-0')), _sc_and(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), '"'), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-1')))):
                                    if _sc_bool(_sc_and(_sc_or(_sc_and(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), "'"), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-0')), _sc_and(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), '"'), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-1'))), _sc_not(_sc_eq(_sc_letter_of(_sc_sub(self.获取列表里面的所有元素_i, 1), arg_列表), '\\')))):
                                        self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'YES'
                    self.获取列表里面的所有元素_i = _sc_add(self.获取列表里面的所有元素_i, 1)
                    self._yield_frame()
                self.获取列表里面的所有元素_返回值.append(self.获取列表里面的所有元素_临时缓存当前代码块)
            self._yield_frame()
        if _sc_bool(arg_boolean):
            self._i = '0'
            for _repeat in range(_sc_repeat_count(len(self.获取列表里面的所有元素_返回值))):
                self._i = _sc_add(self._i, 1)
                if _sc_bool(_sc_or(_sc_and(_sc_eq(_sc_letter_of(1, _sc_item_of(self.获取列表里面的所有元素_返回值, self._i)), '"'), _sc_eq(_sc_letter_of(_sc_length(_sc_item_of(self.获取列表里面的所有元素_返回值, self._i)), _sc_item_of(self.获取列表里面的所有元素_返回值, self._i)), '"')), _sc_and(_sc_eq(_sc_letter_of(1, _sc_item_of(self.获取列表里面的所有元素_返回值, self._i)), "'"), _sc_eq(_sc_letter_of(_sc_length(_sc_item_of(self.获取列表里面的所有元素_返回值, self._i)), _sc_item_of(self.获取列表里面的所有元素_返回值, self._i)), "'")))):
                    self.去除字符串额外数据(_sc_item_of(self.获取列表里面的所有元素_返回值, self._i))
                    _sc_list_replace(self.获取列表里面的所有元素_返回值, self._i, self.去除字符串额外数据_返回值)
                self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s'], arg_names=['文件路径'], proccode='读取 %s 该文件路径的文件内容', arg_ids=['+Q$c/$bPWG_)$:VK9#z('], arg_defaults=[''])
    def 读取_该文件路径的文件内容(self, arg_文件路径=0):
        """自制积木: 读取 %s 该文件路径的文件内容"""
        self.读取文件路径的内容_i = _sc_list_item_number(self.FortunateOS_文件路径管理, arg_文件路径)
        self.读取文件路径的内容_内容 = 'null'
        if _sc_bool(_sc_eq(self.读取文件路径的内容_i, '0')):
            self.读取文件路径的内容_返回值 = '100'
        else:
            self.读取文件路径的内容_内容 = _sc_item_of(self.FortunateOS_文件内容管理, self.读取文件路径的内容_i)
            self.读取文件路径的内容_返回值 = '200'


    @_as_procedure(warp=True, arg_types=['s'], arg_names=['文件路径'], proccode='读取 %s 该文件路径的文件属性', arg_ids=['+Q$c/$bPWG_)$:VK9#z('], arg_defaults=[''])
    def 读取_该文件路径的文件属性(self, arg_文件路径=0):
        """自制积木: 读取 %s 该文件路径的文件属性"""
        self.读取文件路径的属性_i = _sc_list_item_number(self.FortunateOS_文件路径管理, arg_文件路径)
        self.读取文件路径的属性_属性 = 'null'
        if _sc_bool(_sc_eq(self.读取文件路径的属性_i, '0')):
            self.读取文件路径的内容_返回值 = '100'
        else:
            self.读取文件路径的属性_属性 = _sc_item_of(self.FortunateOS_文件属性管理, self.读取文件路径的内容_i)
            self.读取文件路径的属性_返回值 = '200'


    @_as_procedure(warp=True, arg_types=['s'], arg_names=['文件路径'], proccode='获取一个文件的所在文件夹 %s', arg_ids=['0@v(n8O3(M*~5:C{;GiX'], arg_defaults=[''])
    def 获取一个文件的所在文件夹(self, arg_文件路径=0):
        """自制积木: 获取一个文件的所在文件夹 %s"""
        self.获取一个文件的所在文件夹_i = _sc_length(_sc_item_of(self.FortunateOS_文件路径管理, _sc_list_item_number(self.FortunateOS_文件路径管理, arg_文件路径)))
        if _sc_bool(_sc_eq(self.获取一个文件的所在文件夹_i, '0')):
            self.获取一个文件的所在文件夹_i = '100'
            self.stop('this script')
        if _sc_bool(_sc_eq(_sc_letter_of(_sc_length(arg_文件路径), arg_文件路径), '/')):
            self.获取一个文件的所在文件夹_i = _sc_add(self.获取一个文件的所在文件夹_i, -1)
            while not _sc_bool(_sc_or(_sc_eq(_sc_letter_of(self.获取一个文件的所在文件夹_i, arg_文件路径), '/'), _sc_eq(self.获取一个文件的所在文件夹_i, '0'))):
                self.获取一个文件的所在文件夹_i = _sc_add(self.获取一个文件的所在文件夹_i, -1)
                self._yield_frame()
        else:
            while not _sc_bool(_sc_or(_sc_eq(_sc_letter_of(self.获取一个文件的所在文件夹_i, arg_文件路径), '/'), _sc_eq(self.获取一个文件的所在文件夹_i, '0'))):
                self.获取一个文件的所在文件夹_i = _sc_add(self.获取一个文件的所在文件夹_i, -1)
                self._yield_frame()
        self.获取一个文件的所在文件夹_j = '0'
        self.获取一个文件的所在文件夹_返回值 = ''
        for _repeat in range(_sc_repeat_count(self.获取一个文件的所在文件夹_i)):
            self.获取一个文件的所在文件夹_j = _sc_add(self.获取一个文件的所在文件夹_j, 1)
            self.获取一个文件的所在文件夹_返回值 = _sc_join(self.获取一个文件的所在文件夹_返回值, _sc_letter_of(self.获取一个文件的所在文件夹_j, arg_文件路径))
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s'], arg_names=['文件路径'], proccode='删除 %s 该文件路径的内容', arg_ids=['xB!gH0I*|$GWcf?;|X4L'], arg_defaults=[''])
    def 删除_该文件路径的内容(self, arg_文件路径=0):
        """自制积木: 删除 %s 该文件路径的内容"""
        self.删除文件路径的内容_i = _sc_list_item_number(self.FortunateOS_文件路径管理, arg_文件路径)
        if _sc_bool(_sc_eq(self.删除文件路径的内容_i, '0')):
            self.删除文件路径的内容_返回值 = '100'
        else:
            if _sc_bool(_sc_eq(_sc_letter_of(_sc_length(arg_文件路径), arg_文件路径), '/')):
                self.获取_该字符串的_个字符(_sc_item_of(self.FortunateOS_文件路径管理, self.删除文件路径的内容_i), '1', _sc_length(arg_文件路径))
                while not _sc_bool(_sc_not(_sc_eq(self.获取a该字符串的b_c个字符_返回值, arg_文件路径))):
                    self.获取_该字符串的_个字符(_sc_item_of(self.FortunateOS_文件路径管理, _sc_add(self.删除文件路径的内容_i, 1)), '1', _sc_length(arg_文件路径))
                    _sc_list_delete(self.FortunateOS_文件路径管理, self.删除文件路径的内容_i)
                    _sc_list_delete(self.FortunateOS_文件内容管理, self.删除文件路径的内容_i)
                    _sc_list_delete(self.FortunateOS_文件属性管理, self.删除文件路径的内容_i)
                    self._yield_frame()
                self.删除文件路径的内容_返回值 = '200'
            else:
                _sc_list_delete(self.FortunateOS_文件路径管理, self.删除文件路径的内容_i)
                _sc_list_delete(self.FortunateOS_文件内容管理, self.删除文件路径的内容_i)
                _sc_list_delete(self.FortunateOS_文件属性管理, self.删除文件路径的内容_i)
                self.删除文件路径的内容_返回值 = '200'


    @_as_procedure(warp=True, arg_types=[], arg_names=[], proccode='合并临时列表')
    def 合并临时列表(self):
        """自制积木: 合并临时列表"""
        if _sc_bool(_sc_gt(len(self.临时列表), '1')):
            self.合并临时列表_返回值 = _sc_join('[', _sc_join(_sc_join('"', _sc_item_of(self.临时列表, 1)), '"'))
            for _repeat in range(_sc_repeat_count(_sc_sub(len(self.临时列表), 1))):
                _sc_list_delete(self.临时列表, 1)
                self.合并临时列表_返回值 = _sc_join(_sc_join(self.合并临时列表_返回值, ','), _sc_join(_sc_join('"', _sc_item_of(self.临时列表, 1)), '"'))
                self._yield_frame()
            self.合并临时列表_返回值 = _sc_join(self.合并临时列表_返回值, ']')
        else:
            self.合并临时列表_返回值 = _sc_join(_sc_join('[', _sc_join(_sc_join('"', _sc_item_of(self.临时列表, 1)), '"')), ']')


    def when_green_flag(self):
        """当绿旗被点击时"""
        while self._running:
            self.wait_until(lambda: _sc_bool(_sc_not(_sc_eq(len(self.FortunateOS_文件系统执行), '0'))))
            if _sc_bool(_sc_eq(_sc_item_of(self.FortunateOS_文件执行类型, 1), 'ls')):
                self.获取_该列表里面的所有元素_清理字符串内容_(_sc_item_of(self.FortunateOS_文件系统执行, 1), _sc_not(True))
                self.获取路径目录扫描(_sc_item_of(self.获取列表里面的所有元素_返回值, 1), _sc_eq(_sc_item_of(self.获取列表里面的所有元素_返回值, 2), '1'), _sc_eq(_sc_item_of(self.获取列表里面的所有元素_返回值, 3), '1'))
                self.合并临时列表()
                self.FortunateOS_文件系统返回.append(self.合并临时列表_返回值)
            if _sc_bool(_sc_eq(_sc_item_of(self.FortunateOS_文件执行类型, 1), 'xj')):
                self.获取_该列表里面的所有元素_清理字符串内容_(_sc_item_of(self.FortunateOS_文件系统执行, 1), _sc_not(True))
                self.添加一个目录或文件_文件内容_文件属性(_sc_item_of(self.获取列表里面的所有元素_返回值, 1), _sc_item_of(self.获取列表里面的所有元素_返回值, 2), _sc_item_of(self.获取列表里面的所有元素_返回值, 3))
                self.FortunateOS_文件系统返回.append(self.添加一个目录或文件_返回值)
            if _sc_bool(_sc_eq(_sc_item_of(self.FortunateOS_文件执行类型, 1), 'rm')):
                self.删除_该文件路径的内容(_sc_item_of(self.FortunateOS_文件系统执行, 1))
                self.FortunateOS_文件系统返回.append(self.删除文件路径的内容_返回值)
            if _sc_bool(_sc_eq(_sc_item_of(self.FortunateOS_文件执行类型, 1), 'dqnr')):
                self.读取_该文件路径的文件内容(_sc_item_of(self.FortunateOS_文件系统执行, 1))
                self.FortunateOS_文件系统返回.append(_sc_join('[', _sc_join(_sc_join(_sc_join('"', _sc_join(self.读取文件路径的内容_内容, '"')), _sc_join(',', self.读取文件路径的内容_返回值)), ']')))
            if _sc_bool(_sc_eq(_sc_item_of(self.FortunateOS_文件执行类型, 1), 'dqsx')):
                self.读取_该文件路径的文件属性(_sc_item_of(self.FortunateOS_文件系统执行, 1))
                self.FortunateOS_文件系统返回.append(_sc_join('[', _sc_join(_sc_join(_sc_join('"', _sc_join(self.读取文件路径的属性_属性, '"')), _sc_join(',', self.读取文件路径的属性_返回值)), ']')))
            if _sc_bool(_sc_eq(_sc_item_of(self.FortunateOS_文件执行类型, 1), 'dgwjj')):
                self.递归创建文件夹(_sc_item_of(self.FortunateOS_文件系统执行, 1))
                if _sc_bool(_sc_list_contains(self.FortunateOS_文件路径管理, _sc_item_of(self.FortunateOS_文件系统执行, 1))):
                    self.FortunateOS_文件系统返回.append(_sc_join('[', _sc_join('200', ']')))
                else:
                    self.FortunateOS_文件系统返回.append(_sc_join('[', _sc_join('100', ']')))
            if _sc_bool(_sc_eq(_sc_item_of(self.FortunateOS_文件执行类型, 1), 'sjwjj')):
                self.获取一个文件的所在文件夹(_sc_item_of(self.FortunateOS_文件系统执行, 1))
                self.FortunateOS_文件系统返回.append(self.获取一个文件的所在文件夹_返回值)
            _sc_list_delete(self.FortunateOS_文件系统执行, 1)
            _sc_list_delete(self.FortunateOS_文件执行类型, 1)
            self._yield_frame()


    def run(self):
        """向运行时注册事件脚本"""
        self._register('green_flag', self.when_green_flag)

class FortunateOS_任务栏(ScratchSprite):
    """精灵: FortunateOS-任务栏"""

    GLOBAL_NAMES = ('FortunateOS_中转执行类型', 'FortunateOS_中转系统执行', 'FortunateOS_中转系统返回', 'FortunateOS_全部主题名称', 'FortunateOS_分配窗口ID', 'FortunateOS_命令系统执行', 'FortunateOS_命令系统权限', 'FortunateOS_开始菜单是否被开启_', 'FortunateOS_当前主题', 'FortunateOS_当前是否进入桌面', 'FortunateOS_文件内容管理', 'FortunateOS_文件属性管理', 'FortunateOS_文件执行类型', 'FortunateOS_文件系统属性', 'FortunateOS_文件系统执行', 'FortunateOS_文件系统返回', 'FortunateOS_文件路径管理', 'FortunateOS_是否开启锁屏_', 'FortunateOS_窗口ID管理', 'FortunateOS_窗口图层偏移', 'FortunateOS_窗口图层管理', 'FortunateOS_窗口坐标管理', 'FortunateOS_窗口大小管理', 'FortunateOS_窗口系统执行', 'FortunateOS_窗口组件管理', 'FortunateOS_管理设置选项', 'FortunateOS_系统版本号', 'FortunateOS_鼠标是否被占用_', '任务栏动画_i', '我的变量')
    GLOBAL_NAMES_SET = frozenset(GLOBAL_NAMES)

    def __init__(self):
        super().__init__()
        self.x = 0
        self.y = -155
        self.direction = 90
        self.visible = True
        self.size = 100
        self.name = 'FortunateOS-任务栏'
        self.rotation_style = 'all around'
        self.draggable = False
        self.costumes = [{'name': 'fos-任务栏', 'md5ext': 'b6686d6c3304e95db199d22ffa213c94.svg', 'dataFormat': 'svg', 'rotationCenterX': 240, 'rotationCenterY': 52}, {'name': 'os1-任务栏', 'md5ext': '4163ba1949ac2d721ace002081596f56.svg', 'dataFormat': 'svg', 'rotationCenterX': 240, 'rotationCenterY': 52}, {'name': 'fos-开始按钮', 'md5ext': '116659c650044049fcb32d3924ab6cd7.svg', 'dataFormat': 'svg', 'rotationCenterX': 15.111114999999984, 'rotationCenterY': 15.111115000000012}, {'name': 'os1-开始按钮', 'md5ext': '8d75844326e10348a1f51f1b0c5dbc23.svg', 'dataFormat': 'svg', 'rotationCenterX': 15.11110499999998, 'rotationCenterY': 15.111115000000012}, {'name': 'fos-应用图标', 'md5ext': '7bedfd5b67c11421df3e67464d2e8fdc.svg', 'dataFormat': 'svg', 'rotationCenterX': 15.11110500000001, 'rotationCenterY': 15.111115000000012}, {'name': 'os1-应用图标', 'md5ext': '8d75844326e10348a1f51f1b0c5dbc23.svg', 'dataFormat': 'svg', 'rotationCenterX': 15.11110499999998, 'rotationCenterY': 15.111115000000012}]
        self.sounds = []
        self.costume_number = 1
        self.costume_name = 'fos-任务栏'

        self.标题栏_最小化组件 = ''
        self.x1 = 0
        self.x2 = 0
        self.y1 = 0
        self.y2 = 0
        self.xt = 0
        self.yt = 0
        self.窗口组件ID = 0
        self.绑定窗口ID = 0
        self._i = 0
        self.返回值 = 0
        self._i2 = 0
        self.返回值2 = 0
        self.获取列表里面的所有元素_i = 0
        self.获取列表里面的所有元素_j = 0
        self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 0
        self.获取列表里面的所有元素_当前嵌套深度 = 0
        self.获取列表里面的所有元素_临时缓存当前代码块 = 0
        self.获取列表里面的所有元素_当前嵌套字符 = 0
        self.获取列表里面的所有元素_辅助变量2 = 0
        self.获取列表里面的所有元素_辅助变量 = 0
        self.去除字符串额外数据_返回值 = 0
        self._j = 0
        self._i3 = 0
        self.克隆体组件ID = 0
        self.克隆体窗口ID = 0
        self.返回值3 = 0
        self.返回值4 = 0
        self.返回值5 = 0
        self.返回值6 = 0
        self.获取a该字符串的b_c个字符_返回值 = 0
        self.获取a该字符串的b_c个字符_i = 0
        self.返回值7 = 0
        self.窗口组件名称 = 0
        self.i = 0
        self.是否为克隆体_ = 0
        self.拆分路径_i = 0
        self.拆分路径_t = 0
        self.添加一个目录或文件_i = 0
        self.添加一个目录或文件_t = 0
        self.添加一个目录或文件_j = 0
        self.添加一个目录或文件_返回值 = 0
        self.读取文件路径的内容_i = 0
        self.读取文件路径的内容_返回值 = 0
        self.读取文件路径的内容_内容 = 0
        self.删除文件路径的内容_返回值 = 0
        self.删除文件路径的内容_i = 0
        self.获取一个文件的所在文件夹_i = 0
        self.获取一个文件的所在文件夹_j = 0
        self.获取一个文件的所在文件夹_返回值 = 0
        self.获取路径目录_i = 0
        self.获取路径目录_j = 0
        self.递归创建文件夹_i = 0
        self.递归创建文件夹_k = 0

        self.临时列表 = []
        self.获取列表里面的所有元素_返回值 = []
        self.路径拆分 = []
        self._临时列表 = []

    def when_green_flag(self):
        """当绿旗被点击时"""
        self.hide()


    def when_broadcast_开机_FortunateOS(self):
        """当接收到广播'开机-FortunateOS'时"""
        self.show()
        self.switch_costume(_sc_join(self.FortunateOS_当前主题, '-任务栏'))
        self.go_to_layer('back')
        self.set_y(-300)
        self.set_effect('COLOR', _sc_item_of(self.FortunateOS_管理设置选项, _sc_add(_sc_list_item_number(self.FortunateOS_管理设置选项, '标题栏颜色'), 1)))
        self.set_effect('BRIGHTNESS', _sc_item_of(self.FortunateOS_管理设置选项, _sc_add(_sc_list_item_number(self.FortunateOS_管理设置选项, '标题栏亮度'), 1)))
        self.set_effect('GHOST', _sc_item_of(self.FortunateOS_管理设置选项, _sc_add(_sc_list_item_number(self.FortunateOS_管理设置选项, '标题栏透明度'), 1)))
        if _sc_bool(_sc_eq(self.FortunateOS_是否开启锁屏_, '0')):
            self.goto_xy(0, -155)
            self.change_effect('BRIGHTNESS', -100)
            for _repeat in range(_sc_repeat_count(60)):
                self.change_effect('BRIGHTNESS', _sc_div(50, 30))
                self._yield_frame()
            self.set_effect('BRIGHTNESS', _sc_item_of(self.FortunateOS_管理设置选项, _sc_add(_sc_list_item_number(self.FortunateOS_管理设置选项, '标题栏亮度'), 1)))
        else:
            self.任务栏动画_i = '500'
            while not _sc_bool(_sc_or(_sc_eq(self.任务栏动画_i, '2'), _sc_eq(_sc_round(self.任务栏动画_i), '2'))):
                self.任务栏动画_i = _sc_mathop('sqrt', _sc_mul(self.任务栏动画_i, 2))
                self.glide_to(0.1, self.x, _sc_sub(-154, self.任务栏动画_i))
                self._yield_frame()
        self.标题栏_最小化组件 = '开始按钮'
        self.create_clone_of('_myself_')
        self.标题栏_最小化组件 = ''
        self.wait(0.25)


    def when_clone_starts(self):
        """当作为克隆体启动时"""
        self.hide()
        self.clear_effects()
        if _sc_bool(_sc_eq(self.标题栏_最小化组件, '开始按钮')):
            self.switch_costume(_sc_join(self.FortunateOS_当前主题, '-开始按钮'))
            self.go_to_layer('front')
            self.任务栏动画_i = '500'
            self.set_x(-180)
            self.set_y(-200)
            self.show()
            while not _sc_bool(_sc_or(_sc_eq(self.任务栏动画_i, '2'), _sc_eq(_sc_round(self.任务栏动画_i), '2'))):
                self.任务栏动画_i = _sc_mathop('sqrt', _sc_mul(self.任务栏动画_i, 2))
                self.glide_to(0.1, self.x, _sc_sub(-154, self.任务栏动画_i))
                self._yield_frame()
            self.set_y(-155)
            while self._running:
                self.wait_until(lambda: _sc_bool(self.touching('_mouse_')))
                self.任务栏动画_i = '0'
                for _repeat in range(_sc_repeat_count(10)):
                    self.任务栏动画_i = _sc_add(self.任务栏动画_i, 0.5)
                    self.change_size(self.任务栏动画_i)
                    self._yield_frame()
                while not _sc_bool(_sc_not(self.touching('_mouse_'))):
                    if _sc_bool(self.mouse_down):
                        self.任务栏动画_i = '2.5'
                        for _repeat in range(_sc_repeat_count(10)):
                            self.change_size(_sc_sub(0, self.任务栏动画_i))
                            self.任务栏动画_i = _sc_add(self.任务栏动画_i, -0.25)
                            self._yield_frame()
                        self.wait_until(lambda: _sc_bool(_sc_not(self.mouse_down)))
                        if _sc_bool(self.touching('_mouse_')):
                            self.任务栏动画_i = '0'
                            for _repeat in range(_sc_repeat_count(10)):
                                self.任务栏动画_i = _sc_add(self.任务栏动画_i, 0.25)
                                self.change_size(self.任务栏动画_i)
                                self._yield_frame()
                    self._yield_frame()
                if _sc_bool(_sc_eq(self.size, '114')):
                    self.任务栏动画_i = '0'
                    for _repeat in range(_sc_repeat_count(10)):
                        self.任务栏动画_i = _sc_add(self.任务栏动画_i, 0.25)
                        self.change_size(_sc_sub('', self.任务栏动画_i))
                        self._yield_frame()
                else:
                    self.任务栏动画_i = '5'
                    for _repeat in range(_sc_repeat_count(10)):
                        self.change_size(_sc_sub('', self.任务栏动画_i))
                        self.任务栏动画_i = _sc_add(self.任务栏动画_i, -0.5)
                        self._yield_frame()
                self._yield_frame()


    def when_clicked(self):
        """当角色被点击时"""
        if _sc_bool(_sc_eq(self.标题栏_最小化组件, '开始按钮')):
            self.broadcast('打开开始菜单-FortunateOS')


    def run(self):
        """向运行时注册事件脚本"""
        self._register('green_flag', self.when_green_flag)
        self._register('broadcast:开机-FortunateOS', self.when_broadcast_开机_FortunateOS)
        self._register('clone_start', self.when_clone_starts)
        self._register('clicked', self.when_clicked)

class FortunateOS_菜单(ScratchSprite):
    """精灵: FortunateOS-菜单"""

    GLOBAL_NAMES = ('FortunateOS_中转执行类型', 'FortunateOS_中转系统执行', 'FortunateOS_中转系统返回', 'FortunateOS_全部主题名称', 'FortunateOS_分配窗口ID', 'FortunateOS_命令系统执行', 'FortunateOS_命令系统权限', 'FortunateOS_开始菜单是否被开启_', 'FortunateOS_当前主题', 'FortunateOS_当前是否进入桌面', 'FortunateOS_文件内容管理', 'FortunateOS_文件属性管理', 'FortunateOS_文件执行类型', 'FortunateOS_文件系统属性', 'FortunateOS_文件系统执行', 'FortunateOS_文件系统返回', 'FortunateOS_文件路径管理', 'FortunateOS_是否开启锁屏_', 'FortunateOS_窗口ID管理', 'FortunateOS_窗口图层偏移', 'FortunateOS_窗口图层管理', 'FortunateOS_窗口坐标管理', 'FortunateOS_窗口大小管理', 'FortunateOS_窗口系统执行', 'FortunateOS_窗口组件管理', 'FortunateOS_管理设置选项', 'FortunateOS_系统版本号', 'FortunateOS_鼠标是否被占用_', '任务栏动画_i', '我的变量')
    GLOBAL_NAMES_SET = frozenset(GLOBAL_NAMES)

    def __init__(self):
        super().__init__()
        self.x = 0
        self.y = -5.210936025484791
        self.direction = 90
        self.visible = False
        self.size = 100
        self.name = 'FortunateOS-菜单'
        self.rotation_style = 'all around'
        self.draggable = False
        self.costumes = [{'name': 'fos-开始菜单', 'md5ext': '5bcdedc2ed980c43a270fc74f1b11d66.svg', 'dataFormat': 'svg', 'rotationCenterX': 212.60522047619042, 'rotationCenterY': 1}, {'name': 'os1-开始菜单', 'md5ext': '03cf69cd09aec778f3064ab069e1bc18.svg', 'dataFormat': 'svg', 'rotationCenterX': 212.60522, 'rotationCenterY': 0.9999999999999716}]
        self.sounds = []
        self.costume_number = 2
        self.costume_name = 'os1-开始菜单'

        self.FortunateOS_y = 2.887929562166207

    def when_broadcast_打开开始菜单_FortunateOS(self):
        """当接收到广播'打开开始菜单-FortunateOS'时"""
        self.wait_until(lambda: _sc_bool(_sc_not(self.mouse_down)))
        if _sc_bool(_sc_eq(self.FortunateOS_开始菜单是否被开启_, '1')):
            self.broadcast('关闭开始菜单-FortunateOS')
        else:
            self.set_effect('GHOST', 100)
            self.FortunateOS_开始菜单是否被开启_ = '1'
            self.show()
            self.switch_costume(_sc_join(self.FortunateOS_当前主题, '-开始菜单'))
            self.go_to_layer('front')
            self.goto_xy(0, 0)
            self.FortunateOS_y = '1'
            while not _sc_bool(_sc_or(_sc_eq(self.y, '17'), _sc_gt(_sc_add(self.y, self.FortunateOS_y), '17'))):
                self.change_y(self.FortunateOS_y)
                self.FortunateOS_y = _sc_mul(self.FortunateOS_y, _sc_add(1, _sc_div(0.17, 2)))
                self._yield_frame()
            self.set_y(17)
            self.wait_until(lambda: _sc_bool(_sc_and(self.mouse_down, _sc_not(self.touching('_mouse_')))))
            self.broadcast('关闭开始菜单-FortunateOS')


    def when_broadcast_打开开始菜单_FortunateOS_2(self):
        """当接收到广播'打开开始菜单-FortunateOS'时"""
        self.wait_until(lambda: _sc_bool(_sc_not(self.mouse_down)))
        self.wait(0.1)
        if _sc_bool(_sc_eq(self.FortunateOS_开始菜单是否被开启_, '1')):
            self.show()
            for _repeat in range(_sc_repeat_count(10)):
                self.change_effect('GHOST', -10)
                self._yield_frame()
            self.clear_effects()


    def when_green_flag(self):
        """当绿旗被点击时"""
        self.FortunateOS_开始菜单是否被开启_ = '0'
        self.hide()


    def when_broadcast_关闭开始菜单_FortunateOS(self):
        """当接收到广播'关闭开始菜单-FortunateOS'时"""
        for _repeat in range(_sc_repeat_count(10)):
            self.change_effect('GHOST', 10)
            self._yield_frame()


    def when_broadcast_关闭开始菜单_FortunateOS_2(self):
        """当接收到广播'关闭开始菜单-FortunateOS'时"""
        self.FortunateOS_y = '1'
        while not _sc_bool(_sc_or(_sc_eq(self.y, '0'), _sc_lt(_sc_add(self.y, self.FortunateOS_y), '0'))):
            self.change_y(_sc_sub(0, self.FortunateOS_y))
            self.FortunateOS_y = _sc_mul(self.FortunateOS_y, _sc_add(1, _sc_div(0.17, 2)))
            self._yield_frame()
        self.FortunateOS_开始菜单是否被开启_ = '0'
        self.hide()


    def run(self):
        """向运行时注册事件脚本"""
        self._register('broadcast:打开开始菜单-FortunateOS', self.when_broadcast_打开开始菜单_FortunateOS)
        self._register('broadcast:打开开始菜单-FortunateOS', self.when_broadcast_打开开始菜单_FortunateOS_2)
        self._register('green_flag', self.when_green_flag)
        self._register('broadcast:关闭开始菜单-FortunateOS', self.when_broadcast_关闭开始菜单_FortunateOS)
        self._register('broadcast:关闭开始菜单-FortunateOS', self.when_broadcast_关闭开始菜单_FortunateOS_2)

class FortunateOS_锁屏菜单(ScratchSprite):
    """精灵: FortunateOS-锁屏菜单"""

    GLOBAL_NAMES = ('FortunateOS_中转执行类型', 'FortunateOS_中转系统执行', 'FortunateOS_中转系统返回', 'FortunateOS_全部主题名称', 'FortunateOS_分配窗口ID', 'FortunateOS_命令系统执行', 'FortunateOS_命令系统权限', 'FortunateOS_开始菜单是否被开启_', 'FortunateOS_当前主题', 'FortunateOS_当前是否进入桌面', 'FortunateOS_文件内容管理', 'FortunateOS_文件属性管理', 'FortunateOS_文件执行类型', 'FortunateOS_文件系统属性', 'FortunateOS_文件系统执行', 'FortunateOS_文件系统返回', 'FortunateOS_文件路径管理', 'FortunateOS_是否开启锁屏_', 'FortunateOS_窗口ID管理', 'FortunateOS_窗口图层偏移', 'FortunateOS_窗口图层管理', 'FortunateOS_窗口坐标管理', 'FortunateOS_窗口大小管理', 'FortunateOS_窗口系统执行', 'FortunateOS_窗口组件管理', 'FortunateOS_管理设置选项', 'FortunateOS_系统版本号', 'FortunateOS_鼠标是否被占用_', '任务栏动画_i', '我的变量')
    GLOBAL_NAMES_SET = frozenset(GLOBAL_NAMES)

    def __init__(self):
        super().__init__()
        self.x = 0
        self.y = 0
        self.direction = 90
        self.visible = False
        self.size = 100
        self.name = 'FortunateOS-锁屏菜单'
        self.rotation_style = 'all around'
        self.draggable = True
        self.costumes = [{'name': '1', 'md5ext': 'a3d5c166e4aa8e480732cebc99b5f01c.svg', 'dataFormat': 'svg', 'rotationCenterX': 8.983336288876814, 'rotationCenterY': 23.88039171726146}, {'name': '2', 'md5ext': 'fe609bc17fee595b79aba15801cb8d84.svg', 'dataFormat': 'svg', 'rotationCenterX': 8.983331288876798, 'rotationCenterY': 23.880394021720065}, {'name': '3', 'md5ext': '964bd812e0b4a6777c58804d0de63c3b.svg', 'dataFormat': 'svg', 'rotationCenterX': 8.983336288876785, 'rotationCenterY': 23.88039632617867}, {'name': '4', 'md5ext': '9d381067a476658993e27fa72163b82d.svg', 'dataFormat': 'svg', 'rotationCenterX': 8.98333128887677, 'rotationCenterY': 23.88038863063727}, {'name': '5', 'md5ext': '00c03e455c28c08f7726bb42a2390c18.svg', 'dataFormat': 'svg', 'rotationCenterX': 8.983336288876757, 'rotationCenterY': 23.880390935095875}, {'name': '6', 'md5ext': '70f850413fec2a14cdf792ccb8138486.svg', 'dataFormat': 'svg', 'rotationCenterX': 8.983331288876741, 'rotationCenterY': 23.88039323955448}, {'name': '7', 'md5ext': '8ccf5c75981f10b75a0a3e4996fc020d.svg', 'dataFormat': 'svg', 'rotationCenterX': 8.983336288876728, 'rotationCenterY': 23.880395544013084}, {'name': '8', 'md5ext': '91dbcc00d20c045edb613b37343162e1.svg', 'dataFormat': 'svg', 'rotationCenterX': 8.983331288876713, 'rotationCenterY': 23.880387848471685}, {'name': '9', 'md5ext': '7e17a4d2e784db7c0630acac48a2356a.svg', 'dataFormat': 'svg', 'rotationCenterX': 8.9833362888767, 'rotationCenterY': 23.88039015293029}, {'name': '0', 'md5ext': 'f1f060f83718f717ab3360eedf89fd23.svg', 'dataFormat': 'svg', 'rotationCenterX': 8.983331288876684, 'rotationCenterY': 23.880392457388893}, {'name': '10', 'md5ext': 'd3aa315552c42f6d893df2697e70b6f9.svg', 'dataFormat': 'svg', 'rotationCenterX': 4.484124511184689, 'rotationCenterY': 23.53246230445862}, {'name': '', 'md5ext': 'a821e584d351860e11b4ecf4e0067c99.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'uniform_half_transparent', 'md5ext': '6d464a7a0e12d5adc095bc61396d3f2b.svg', 'dataFormat': 'svg', 'rotationCenterX': 977.5656087027214, 'rotationCenterY': 1123.420811603629}]
        self.sounds = []
        self.costume_number = 13
        self.costume_name = 'uniform_half_transparent'

        self.克隆体编号 = '0'
        self.克隆体类型 = 3
        self.动画_i = '0'
        self._y = 0
        self.y = 0

    def when_broadcast_开机_FortunateOS(self):
        """当接收到广播'开机-FortunateOS'时"""
        if _sc_bool(_sc_eq(self.FortunateOS_是否开启锁屏_, '0')):
            self.stop('other scripts in sprite')
        if _sc_bool(_sc_not(_sc_eq(self.克隆体编号, '0'))):
            for _repeat in range(_sc_repeat_count(30)):
                self.change_effect('GHOST', _sc_div(100, 30))
                self._yield_frame()
        self.hide()
        self.delete_this_clone()


    def when_green_flag(self):
        """当绿旗被点击时"""
        self.clear_effects()
        self.goto_xy(0, 0)
        self.wait_until(lambda: _sc_bool(_sc_eq(self.FortunateOS_是否开启锁屏_, '1')))
        while self._running:
            if _sc_bool(_sc_and(_sc_not(self.mouse_down), _sc_gt(self.y, '50'))):
                self.FortunateOS_当前是否进入桌面 = '1'
                self.glide_to(0.25, 0, 640)
                self.broadcast('开机-FortunateOS')
                self.stop('this script')
            else:
                if _sc_bool(_sc_and(_sc_not(self.mouse_down), _sc_lt(self.y, '50'))):
                    self.glide_to(0.1, 0, 0)
            self._yield_frame()


    def when_broadcast_打开锁屏界面_FortunateOS(self):
        """当接收到广播'打开锁屏界面-FortunateOS'时"""
        self.set_drag_mode('not draggable')
        self.broadcast('生成锁屏页面数字-FortunateOS')
        self.switch_costume('uniform_half_transparent')
        self.set_effect('BRIGHTNESS', -100)
        self.show()
        self.go_to_layer('back')
        self.set_drag_mode('draggable')


    def when_clone_starts(self):
        """当作为克隆体启动时"""
        self.set_effect('BRIGHTNESS', -100)
        self.set_size(150)
        if _sc_bool(_sc_eq(self.克隆体类型, '1')):
            if _sc_bool(_sc_eq(self.克隆体编号, '1')):
                self.goto_xy(-28.5, 75)
                while self._running:
                    if _sc_bool(_sc_eq(_sc_length(self.current_time('HOUR')), '1')):
                        self.switch_costume(_sc_letter_of(1, self.current_time('HOUR')))
                    else:
                        self.switch_costume(_sc_letter_of(2, self.current_time('HOUR')))
                    self._yield_frame()
            else:
                self.goto_xy(-57, 75)
                while self._running:
                    self.show()
                    if _sc_bool(_sc_eq(_sc_length(self.current_time('HOUR')), '2')):
                        self.switch_costume(_sc_letter_of(1, self.current_time('HOUR')))
                    else:
                        self.switch_costume('')
                    self._yield_frame()


    def when_green_flag_2(self):
        """当绿旗被点击时"""
        self.hide()


    def when_clone_starts_2(self):
        """当作为克隆体启动时"""
        self.show()
        self.set_effect('BRIGHTNESS', -100)
        self.set_size(150)
        if _sc_bool(_sc_eq(self.克隆体类型, '3')):
            self.goto_xy(0, 75)
            self.switch_costume('10')


    def when_clone_starts_3(self):
        """当作为克隆体启动时"""
        self.set_effect('BRIGHTNESS', -100)
        if _sc_bool(_sc_eq(self.克隆体类型, '2')):
            if _sc_bool(_sc_eq(self.克隆体编号, '1')):
                self.goto_xy(28.5, 75)
                while self._running:
                    if _sc_bool(_sc_eq(_sc_length(self.current_time('MINUTE')), '1')):
                        self.switch_costume('0')
                    else:
                        self.switch_costume(_sc_letter_of(1, self.current_time('MINUTE')))
                    self._yield_frame()
            else:
                self.goto_xy(57, 75)
                while self._running:
                    if _sc_bool(_sc_eq(_sc_length(self.current_time('MINUTE')), '2')):
                        self.switch_costume(_sc_letter_of(2, self.current_time('MINUTE')))
                    else:
                        self.switch_costume(_sc_letter_of(1, self.current_time('MINUTE')))
                    self._yield_frame()


    def when_broadcast_生成锁屏页面数字_FortunateOS(self):
        """当接收到广播'生成锁屏页面数字-FortunateOS'时"""
        self.克隆体类型 = '1'
        self.克隆体编号 = '0'
        for _repeat in range(_sc_repeat_count(2)):
            self.克隆体编号 = _sc_add(self.克隆体编号, 1)
            self.create_clone_of('_myself_')
            self.克隆体编号 = _sc_add(self.克隆体编号, 1)
            self.create_clone_of('_myself_')
            self.克隆体类型 = _sc_add(self.克隆体类型, 1)
            self.克隆体编号 = '0'
            self._yield_frame()
        self.create_clone_of('_myself_')
        self.克隆体编号 = '0'


    def when_clone_starts_4(self):
        """当作为克隆体启动时"""
        self.y = self.y
        while self._running:
            if _sc_bool(self.mouse_down):
                self._y = _sc_sub(self.y, self.mouse_y)
                while not _sc_bool(_sc_not(self.mouse_down)):
                    self.set_y(_sc_add(self._y, self.mouse_y))
                    self._yield_frame()
                if _sc_bool(_sc_eq(self.FortunateOS_当前是否进入桌面, '0')):
                    self.glide_to(0.25, self.x, self.y)
                else:
                    self.glide_to(0.25, 0, 640)
            self._yield_frame()


    def run(self):
        """向运行时注册事件脚本"""
        self._register('broadcast:开机-FortunateOS', self.when_broadcast_开机_FortunateOS)
        self._register('green_flag', self.when_green_flag)
        self._register('broadcast:打开锁屏界面-FortunateOS', self.when_broadcast_打开锁屏界面_FortunateOS)
        self._register('clone_start', self.when_clone_starts)
        self._register('green_flag', self.when_green_flag_2)
        self._register('clone_start', self.when_clone_starts_2)
        self._register('clone_start', self.when_clone_starts_3)
        self._register('broadcast:生成锁屏页面数字-FortunateOS', self.when_broadcast_生成锁屏页面数字_FortunateOS)
        self._register('clone_start', self.when_clone_starts_4)

class FortunateOS_FAI(ScratchSprite):
    """精灵: FortunateOS-FAI"""

    GLOBAL_NAMES = ('FortunateOS_中转执行类型', 'FortunateOS_中转系统执行', 'FortunateOS_中转系统返回', 'FortunateOS_全部主题名称', 'FortunateOS_分配窗口ID', 'FortunateOS_命令系统执行', 'FortunateOS_命令系统权限', 'FortunateOS_开始菜单是否被开启_', 'FortunateOS_当前主题', 'FortunateOS_当前是否进入桌面', 'FortunateOS_文件内容管理', 'FortunateOS_文件属性管理', 'FortunateOS_文件执行类型', 'FortunateOS_文件系统属性', 'FortunateOS_文件系统执行', 'FortunateOS_文件系统返回', 'FortunateOS_文件路径管理', 'FortunateOS_是否开启锁屏_', 'FortunateOS_窗口ID管理', 'FortunateOS_窗口图层偏移', 'FortunateOS_窗口图层管理', 'FortunateOS_窗口坐标管理', 'FortunateOS_窗口大小管理', 'FortunateOS_窗口系统执行', 'FortunateOS_窗口组件管理', 'FortunateOS_管理设置选项', 'FortunateOS_系统版本号', 'FortunateOS_鼠标是否被占用_', '任务栏动画_i', '我的变量')
    GLOBAL_NAMES_SET = frozenset(GLOBAL_NAMES)

    def __init__(self):
        super().__init__()
        self.x = 0
        self.y = 0
        self.direction = 90
        self.visible = False
        self.size = 100
        self.name = 'FortunateOS-FAI'
        self.rotation_style = 'all around'
        self.draggable = False
        self.costumes = [{'name': '造型1', 'md5ext': '652fe23d570475e7ce031f3802f574a4.svg', 'dataFormat': 'svg', 'rotationCenterX': 29.26189500000001, 'rotationCenterY': 29.261875000000003}]
        self.sounds = []
        self.costume_number = 1
        self.costume_name = '造型1'

        self.AI生成回答_i = 1272
        self.AI生成回答_返回值 = '抱歉,我目前无法理解这个问题,请换个话题再试吧'
        self.AI生成回答_t = '你现在在'
        self.AI生成回答_k = 0
        self.AI生成回答_c = 0
        self.AI生成回答_j = 1
        self.获取列表里面的所有元素_i = 0
        self.获取列表里面的所有元素_j = 0
        self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 0
        self.获取列表里面的所有元素_当前嵌套深度 = 0
        self.获取列表里面的所有元素_临时缓存当前代码块 = 0
        self.获取列表里面的所有元素_当前嵌套字符 = 0
        self.获取列表里面的所有元素_辅助变量2 = 0
        self.获取列表里面的所有元素_辅助变量 = 0
        self._i = 0
        self.去除字符串额外数据_返回值 = 0
        self._j = 0
        self.___1 = '["英雄联盟|是什么||英雄联盟是Riot Games开发的MOBA竞技网游，5v5推塔对战，拥有超百位英雄和成熟电竞赛事，是全球玩家最多的团队竞技游戏之一。  \\r","无畏契约|是什么||无畏契约是Riot Games的5v5战术射击游戏，攻防围绕爆能器展开，每位特工有独特技能，强调枪法与技能配合，竞技性极强。  \\r","穿越火线|是什么||穿越火线是经典第一人称射击网游，提供爆破、团队竞技、生化等多种模式，手感爽快，曾是国内网吧最火的FPS游戏。  \\r","地下城与勇士|是什么||地下城与勇士是横版格斗RPG，玩家选择鬼剑士等职业闯关刷图，以连招、装备和街机手感著称，长期占据网吧热榜。  \\r","剑网3|是什么||剑网3是西山居的国风武侠MMORPG，以大唐为背景，拥有轻功、门派武学和丰富社交，画面精美，同人文化繁荣。  \\r","魔兽世界|是什么||魔兽世界是暴雪的史诗级MMORPG，在艾泽拉斯大陆探索，有副本、PVP和任务体系，定义了现代网游的标杆，影响深远。  \\r","三角洲行动|是什么||三角洲行动是2023年上线的硬核射击游戏，包含大战场战术对抗和生存撤离玩法，画面写实，枪械手感扎实，新晋热门。  \\r","界外狂潮|是什么||界外狂潮是2025年推出的射击新游，以快节奏对战和英雄技能为特色，在网吧热度榜中抢眼，吸引大量年轻FPS玩家。  \\r","剑灵2|是什么||剑灵2是经典武侠MMORPG剑灵的续作，延续东方奇幻画风和华丽的战斗特效，2025年上线后凭借IP影响力迅速跻身热门。  \\r","鸣潮|是什么||鸣潮是开放世界动作RPG，玩家在灾变大陆探索，可切换三名角色连携攻击，收集声骸辅助战斗，战斗爽快，画面细腻。  \\r","崩坏星穹铁道|是什么||崩坏星穹铁道是米哈游的银河冒险回合制RPG，搭乘星穹列车穿越星球，体验宏大剧情和角色养成，回合制战斗策略丰富。  \\r","原神|是什么||原神是米哈游开发的开放世界动作RPG，玩家在提瓦特大陆探索，可切换元素角色战斗，有丰富剧情和抽卡养成，全球爆款。  \\r","绝区零|是什么||绝区零是米哈游推出的都市奇幻动作游戏，玩家扮演代理人探索空洞，战斗爽快，角色风格鲜明，带有肉鸽和策略元素。  \\r","永劫无间|是什么||永劫无间是武侠风格的大逃杀动作游戏，玩家使用冷兵器近战和飞索移动，拼刀振刀机制独特，画面华丽，竞技性强。  \\r","Apex英雄|是什么||Apex英雄是重生工作室的免费大逃杀射击游戏，小队三人各选传奇英雄，拥有独特技能，滑铲和攀爬流畅，枪感优秀。  \\r","堡垒之夜|是什么||堡垒之夜是Epic开发的建造+射击大逃杀游戏，玩家可搭板建筑，拥有卡通画风和联动活动，是全球文化现象级作品。  \\r","使命召唤战区|是什么||使命召唤战区是动视的免费大逃杀模式，拥有极高画质和真实枪感，支持复活机制和合约任务，是COD系列的热门玩法。  \\r","绝地求生|是什么||绝地求生是开创大逃杀热潮的游戏，百人跳伞搜集装备生存，以写实风格和战术射击著称，曾获无数大奖，风靡全球。  \\r","CS:GO|是什么||CS:GO是Valve的经典战术射击游戏，反恐精英与恐怖分子对垒，讲究枪法和经济管理，是电竞常青树，现升级为CS2。  \\r","DOTA2|是什么||DOTA2是Valve的MOBA游戏，5v5推塔，英雄众多，装备系统复杂，国际邀请赛奖金惊人，是硬核电竞玩家的挚爱。  \\r","风暴英雄|是什么||风暴英雄是暴雪的MOBA游戏，汇集旗下各游戏角色，取消装备，共享团队经验，注重地图机制和团队配合，节奏更快。  \\r","守望先锋|是什么||守望先锋是暴雪的团队射击游戏，分为重装、输出、支援英雄，拥有技能和终极技，地图丰富，曾获年度游戏，现为守望先锋2。  \\r","炉石传说|是什么||炉石传说是以魔兽为背景的卡牌对战游戏，玩家组建套牌进行回合对战，有标准、狂野和战棋模式，轻松又有策略。  \\r","皇室战争|是什么||皇室战争是Supercell的实时卡牌对战手游，玩家部署卡牌进攻对手塔防，三分钟一局，结合MOBA和塔防元素，竞技性强。  \\r","部落冲突|是什么||部落冲突是Supercell的模拟策略手游，玩家建设村庄、训练兵种攻击其他玩家，可加入部落合作，经营与战斗并存。  \\r","荒野乱斗|是什么||荒野乱斗是Supercell的快节奏多人射击手游，3v3或吃鸡模式，多种英雄有独特技能，三分钟一局，轻松爽快。  \\r","第五人格|是什么||第五人格是非对称竞技手游，一名监管者追捕四名求生者，悬疑哥特画风，角色有独特技能，玩法类似黎明杀机。  \\r","阴阳师|是什么||阴阳师是网易的日式和风回合制RPG，玩家收集式神，搭配御魂，剧情宏大，美术精美，曾引领二次元手游热潮。  \\r","明日方舟|是什么||明日方舟是鹰角网络的塔防策略手游，玩家部署干员阻挡敌人，具有独特世界观和精美立绘，策略性强，深受玩家喜爱。  \\r","命运冠位指定|是什么||命运冠位指定是Fate系列的回合制RPG，玩家召唤英灵穿越时空修复历史，剧情丰富，抽卡养成，是二次元常青树。  \\r","碧蓝航线|是什么||碧蓝航线是舰船拟人射击手游，横向弹幕玩法，收集舰娘搭配装备，有自动战斗和丰富皮肤，角色立绘精美。  \\r","少女前线|是什么||少女前线是战术策略手游，玩家指挥战术人形进行回合制战斗，有枪械拟人和丰富剧情，养成系统深入，硬核玩家众多。  \\r","战双帕弥什|是什么||战双帕弥什是末世科幻动作手游，三人小队切换，有华丽的连招和三消技能系统，打击感出色，剧情黑暗深刻。  \\r","幻塔|是什么||幻塔是完美世界的开放世界科幻RPG，可自由探索、攀爬和战斗，有拟态角色和联机功能，画面与玩法对标原神。  \\r","尘白禁区|是什么||尘白禁区是轻科幻射击手游，玩家操控角色在近未来都市战斗，有掩体和技能，主打美少女枪战，画风清新。  \\r","无限暖暖|是什么||无限暖暖是叠纸的开放世界换装冒险游戏，以搭配装扮为核心，结合探索和解谜，画面唯美，主打治愈与时尚。  \\r","恋与制作人|是什么||恋与制作人是女性向恋爱养成手游，玩家扮演制作人与四位男性角色互动，有剧情和电话系统，广受乙女玩家喜爱。  \\r","光与夜之恋|是什么||光与夜之恋是腾讯的女性向恋爱手游，玩家与五位男主展开浪漫故事，卡面精美，声优豪华，剧情代入感强。  \\r","以闪亮之名|是什么||以闪亮之名是女性向换装社交手游，玩家可以捏脸、设计服装，搭配拍照，有剧情和家园系统，画面精美。  \\r","逆水寒|是什么||逆水寒是网易的武侠MMORPG，以北宋为背景，画面精致，轻功和江湖奇遇丰富，有庄园和身份玩法，剧情感人。  \\r","天涯明月刀|是什么||天涯明月刀是腾讯的武侠MMORPG，有电影级画质和自由捏脸，战斗动作流畅，帮派和论剑系统成熟，江湖氛围浓厚。  \\r","九阴真经|是什么||九阴真经是蜗牛的武侠网游，主打无等级、奇遇和轻功，武功套路丰富，拥有江湖内功和离线修炼，玩法独特。  \\r","天龙八部|是什么||天龙八部是搜狐畅游的经典武侠网游，以金庸小说为背景，门派丰富，珍兽系统和副本玩法经典，曾风靡一时。  \\r","梦幻西游|是什么||梦幻西游是网易的Q版回合制MMORPG，以西游为背景，有十二门派，抓鬼、封妖和跑商，社交系统完善，经久不衰。  \\r","大话西游|是什么||大话西游是网易的回合制网游，同样西游题材，但更注重故事和种族平衡，有婚姻、养育和帮战，老玩家情怀深厚。  \\r","问道|是什么||问道是光宇游戏的回合制修仙网游，以道教为背景，有五行相克、宠物和道行系统，免费模式，平民玩家众多。  \\r","诛仙|是什么||诛仙是完美世界的玄幻仙侠网游，改编自小说，有青云、鬼王等门派，飞行系统和情缘玩法，画面唯美，剧情还原。  \\r","完美世界|是什么||完美世界是完美时空的3D仙侠网游，拥有无缝大地图、飞行和种族变身，副本和城战丰富，是中国最早的3D网游之一。  \\r","武林外传|是什么||武林外传是完美世界开发的Q版武侠网游，喜剧风格，有搞怪称号和宠物，副本简单，适合休闲玩家，情怀之作。  \\r","蜀门|是什么||蜀门是绿岸网络的仙侠网游，采用副本刷装模式，职业分明，有坐骑和法宝系统，操作简单，适合轻量级MMO爱好者。  \\r","传奇|是什么||传奇是盛大引进的经典MMORPG，战法道三职业，PK爆装备，攻城战热血，是国内网游启蒙之作，至今仍有大量怀旧服。  \\r","奇迹MU|是什么||奇迹MU是韩国网禅的经典MMORPG，以华丽的装备光效和翅膀系统著称，刷怪升级，PK和攻城战，曾是网吧最火游戏之一。  \\r","冒险岛|是什么||冒险岛是Nexon的2D横版Q版网游，玩家在彩色世界冒险，有职业转职、任务和社交，音乐轻快，充满童趣。  \\r","枫之谷|是什么||枫之谷即冒险岛国际版，在台服和东南亚流行，内容类似，有更多的联动活动，角色可爱，人气稳定。  \\r","彩虹岛|是什么||彩虹岛是Actoz的2D横版可爱网游，特色是武器特效和连击系统，有丰富的时装和副本，画面明亮，深受女性玩家喜爱。  \\r","劲舞团|是什么||劲舞团是音乐舞蹈类网游，玩家按方向键和空格跟随节奏跳舞，有竞技和情侣模式，曾在国内掀起键盘舞蹈热潮。  \\r","QQ炫舞|是什么||QQ炫舞是腾讯的舞蹈网游，类似劲舞团，但有更丰富的歌曲和社交功能，与QQ好友互动，时尚装扮是一大特色。  \\r","QQ飞车|是什么||QQ飞车是腾讯的竞速网游，有赛车漂移、道具赛和改装系统，Q版画风，音乐动感，曾是青少年最爱的赛车游戏。  \\r","跑跑卡丁车|是什么||跑跑卡丁车是Nexon的卡通竞速游戏，有漂移集气、道具和竞速模式，角色可爱，曾风靡亚洲，现仍有活跃玩家。  \\r","马里奥赛车|是什么||马里奥赛车是任天堂的卡丁车竞速游戏，使用道具干扰对手，赛道多样，包含任天堂明星角色，派对游戏首选。  \\r","任天堂大乱斗|是什么||任天堂大乱斗是格斗对战游戏，集结任天堂明星，操作简单，道具丰富，可多人混战，既是竞技也是聚会神器。  \\r","塞尔达传说旷野之息|是什么||旷野之息是任天堂的开放世界动作冒险游戏，玩家操控林克在广袤海拉鲁探索，物理引擎出色，解谜自由，被誉为神作。  \\r","塞尔达传说王国之泪|是什么||王国之泪是旷野之息的续作，增加空岛和地底，新增建造和余料建造机制，探索更深入，玩法更具创意，广受好评。  \\r","超级马里奥奥德赛|是什么||奥德赛是3D平台跳跃游戏，马里奥可投掷帽子附身敌人，探索多个王国，收集月亮，创意十足，关卡设计精妙。  \\r","动物森友会|是什么||动物森友会是生活模拟游戏，玩家在无人岛生活，钓鱼捕虫，装饰房屋，与动物邻居互动，轻松治愈，时间与现实同步。  \\r","宝可梦系列|是什么||宝可梦是经典角色扮演系列，玩家捕捉训练宝可梦，进行道馆挑战和联盟赛，收集图鉴，是全世界最知名的跨媒体IP。  \\r","宝可梦GO|是什么||宝可梦GO是AR手游，在现实世界捕捉宝可梦，进行道馆对战和团体战，鼓励户外探索，曾引发全球热潮。  \\r","我的世界|是什么||我的世界是沙盒建造游戏，玩家在方块世界自由创造和探索，有生存和创造模式，无限可能性，全球销量最高。  \\r","泰拉瑞亚|是什么||泰拉瑞亚是2D横版沙盒冒险游戏，探索地下世界，收集资源，打造武器和建筑，有丰富的BOSS和随机事件，被称为2D我的世界。  \\r","星露谷物语|是什么||星露谷物语是农场模拟经营游戏，继承牧场物语风格，种植、养殖、钓鱼、采矿，可结婚社交，轻松治愈，像素风精美。  \\r","饥荒|是什么||饥荒是生存冒险游戏，玩家在异世界收集食物、建造营地，对抗季节和怪物，有理智值，画风哥特，难度较高。  \\r","缺氧|是什么||缺氧是太空殖民地模拟游戏，管理复制人，建设氧气、食物和水循环，需处理热量和气压，硬核策略，可玩性强。  \\r","文明6|是什么||文明6是回合制策略游戏，玩家选择文明，发展科技、文化、军事，征服或外交胜利，地图庞大，策略深度极高。  \\r","模拟城市|是什么||模拟城市是城市建造模拟游戏，玩家规划交通、工业、商业和居民区，处理水电垃圾，应对灾害，体验市长职责。  \\r","城市天际线|是什么||城市天际线是目前最真实城建模拟游戏，有交通、区域划分和DLC扩展，支持MOD，可建造立体城市，深受玩家喜爱。  \\r","欧洲卡车模拟2|是什么||欧卡2是卡车模拟驾驶游戏，玩家在欧洲公路上运输货物，体验真实驾驶，管理公司，画风写实，休闲放松。  \\r","微软飞行模拟|是什么||微软飞行模拟是航空模拟游戏，使用真实卫星地图和气象数据，驾驶各种飞机在全球飞行，画面逼真，硬核飞行爱好者的首选。  \\r","GT赛车|是什么||GT赛车是索尼的赛车模拟游戏，以真实驾驶和赛道著称，有大量授权车辆和赛事，画面精细，物理引擎严谨。  \\r","极限竞速地平线|是什么||地平线系列是开放式赛车游戏，在墨西哥等地自由驾驶，有季节变化和多种赛事，爽快又不失真实感，画面顶级。  \\r","地平线零之曙光|是什么||地平线零之曙光是开放世界动作RPG，主角在机械兽横行的后末日世界狩猎，有潜行和弓箭战斗，剧情深刻，画面惊艳。  \\r","战神|是什么||战神是索尼的动作冒险游戏，主角奎托斯以链刃和利维坦之斧战斗，北欧神话背景，场面宏大，打击感极强。  \\r","最后生还者|是什么||最后生还者是末日生存动作游戏，主角乔尔护送艾莉穿越废墟，有潜行和资源管理，剧情感人，被誉为互动电影典范。  \\r","神秘海域|是什么||神秘海域是动作冒险系列，主角德雷克寻宝，融合攀爬、枪战和解谜，电影化叙事，画面华丽，是索尼王牌IP。  \\r","古墓丽影|是什么||古墓丽影是动作冒险系列，主角劳拉探索古墓，解谜与射击结合，新版注重生存和成长，重启后广受好评。  \\r","刺客信条|是什么||刺客信条是育碧的开放世界动作潜行游戏，穿梭历史时期，扮演刺客对抗圣殿骑士，有跑酷和战斗，年货系列，内容丰富。  \\r","孤岛惊魂|是什么||孤岛惊魂是育碧的FPS开放世界游戏，玩家在偏远岛屿或山区对抗反派，有狩猎和载具，爽快射击，风景优美。  \\r","荒野大镖客2|是什么||荒野大镖客2是R星的西部开放世界游戏，扮演亚瑟·摩根，体验牛仔生活，剧情深刻，细节丰富，被誉为神作。  \\r","GTA5|是什么||GTA5是R星的犯罪开放世界游戏，三位主角在洛圣都行劫，可切换角色，自由探索，线上模式长期运营，销量惊人。  \\r","赛博朋克2077|是什么||赛博朋克2077是CDPR的科幻开放世界RPG，玩家在夜之城扮演V，有丰富剧情和角色构建，更新后口碑回升。  \\r","巫师3|是什么||巫师3是CDPR的动作RPG，猎魔人杰洛特寻女，有庞大支线和抉择影响世界，画面和剧情顶尖，获得年度游戏。  \\r","质量效应|是什么||质量效应是BioWare的科幻RPG三部曲，玩家扮演薛帕德指挥诺曼底，探索星系，外交战斗，抉择影响结局。  \\r","辐射4|是什么||辐射4是Bethesda的末日开放世界RPG，主角在核废土生存，有建造系统、伙伴和动力装甲，捡垃圾乐趣无穷。  \\r","上古卷轴5|是什么||上古卷轴5是Bethesda的奇幻开放世界RPG，龙裔探索天际省，有丰富任务、技能树和龙吼，MOD支持强大，常青树。  \\r","黑暗之魂3|是什么||黑暗之魂3是硬核动作RPG，以高难度和地图设计闻名，玩家挑战强大BOSS，有丰富武器和流派，宫崎英高代表作。  \\r","艾尔登法环|是什么||艾尔登法环是宫崎英高和马丁合作的开放世界魂系游戏，广袤大地图，自由探索，战斗和魔法丰富，难度依旧。  \\r","只狼|是什么||只狼是动作冒险游戏，玩家扮演忍者，使用刀和义手战斗，主打拼刀和弹反，有潜行和钩索，剧情和战斗都备受赞誉。  \\r","仁王|是什么||仁王是光荣的战国动作游戏，融合魂系和忍者龙剑传，玩家使用多种武器和守护灵，刷装备和技能，硬核且耐玩。  \\r","怪物猎人世界|是什么||怪物猎人世界是共斗狩猎游戏，玩家组队猎杀大型怪物，利用钩爪和环境陷阱，获得素材打造装备，动作硬核，生态真实。  \\r","怪物猎人崛起|是什么||怪物猎人崛起是系列新作，新增翔虫和御龙系统，移动更灵活，可高速狩猎，有百龙夜行模式，续作曙光扩展丰富。  \\r","龙之信条2|是什么||龙之信条2是开放世界动作RPG，玩家扮演觉醒者，有随从系统，可攀爬怪物，魔法炫酷，物理互动优秀。  \\r","最终幻想14|是什么||最终幻想14是史克威尔的MMORPG，有庞大主线、职业系统和副本，剧情口碑极好，版本更新稳定，全球活跃玩家众多。  \\r","最终幻想7重制版|是什么||最终幻想7重制版是经典RPG的完全重制，画面和战斗系统全面升级，采用实时指令结合，剧情加料，情怀满满。  \\r","王国之心|是什么||王国之心是迪士尼与最终幻想联动的动作RPG，主角索拉使用键刃，穿梭迪士尼世界，战斗爽快，剧情复杂，拥趸众多。  \\r","尼尔机械纪元|是什么||尼尔机械纪元是白金工作室的动作RPG，2B和9S主角，人设出色，战斗流畅，多结局剧情深刻，音乐被誉为神级。  \\r","异度神剑|是什么||异度神剑是任天堂的开放世界RPG，有巨神和机神世界观，战斗系统独特，可连携攻击，地图广阔，剧情宏大。  \\r","火焰纹章|是什么||火焰纹章是战棋策略RPG，有经典日式角色和转职系统，永久死亡机制，剧情常涉及战争和爱情，高难度粉丝向。  \\r","女神异闻录5|是什么||女神异闻录5是JRPG，白天学生生活，夜晚怪盗冒险，有回合制战斗和人格面具合成，美术和音乐潮爆，口碑极高。  \\r","如龙系列|是什么||如龙是世嘉的动作冒险系列，主角桐生一马，在神室町黑道闯荡，有丰富支线和小游戏，剧情硬派，日剧风格。  \\r","审判之逝|是什么||审判之逝是如龙工作室的侦探动作游戏，主角八神隆之调查案件，有战斗和跟踪潜行，剧情悬疑，动作流畅。  \\r","死亡搁浅|是什么||死亡搁浅是小岛秀夫的送货模拟冒险，玩家连接美国城市，有异步社交和BT战斗，剧情深邃，画面电影级。  \\r","控制|是什么||控制是Remedy的第三人称超自然动作游戏，女主角使用枪械和超能力，在联邦控制局探索，画面和物理效果惊艳。  \\r","量子破碎|是什么||量子破碎是Remedy的时间科幻动作游戏，玩家有闪避和冻结时间能力，穿插真人美剧，剧情烧脑，创意独特。  \\r","心灵杀手2|是什么||心灵杀手2是生存恐怖游戏，使用手电筒和枪支对抗黑暗，有双主角和案件板系统，氛围压抑，剧情悬疑。  \\r","生化危机|是什么||生化危机是卡普空的恐怖生存系列，以丧尸爆发为背景，资源管理，解谜和射击，是恐怖游戏鼻祖之一。  \\r","寂静岭|是什么||寂静岭是心理恐怖游戏，主角在迷雾小镇遭遇怪物，氛围压抑，剧情隐喻人性，是经典恐怖IP，等待新作。  \\r","逃生|是什么||逃生是第一人称恐怖游戏，主角手持摄像机，没有武器，只能躲避和逃跑，环境恐怖，惊吓感十足。  \\r","港诡实录|是什么||港诡实录是国产恐怖游戏，以香港都市传说为背景，第一人称探索解谜，中式恐怖氛围，故事引人入胜。  \\r","纸嫁衣|是什么||纸嫁衣是国产恐怖解谜系列，结合民俗和冥婚题材，有丰富的谜题和纸人元素，剧情反转，深受玩家喜爱。  \\r","疑案追声|是什么||疑案追声是声音解谜游戏，玩家在案发现场听取对话，根据声音确定事件全貌，创意新颖，逻辑缜密。  \\r","隐形守护者|是什么||隐形守护者是真人互动影视游戏，玩家扮演潜伏者，选择影响剧情，谍战主题，多重结局，代入感强。"]'
        self.___i = 120

        self.匹配词_1 = ['你好', '什么是', '什么是', '什么是', '我', '我', '我', '我', '我', '我', '我', '我', '我', '我', '今天', '今天', '你', '你', '为什么', '为什么', '怎么', '怎么', '怎么', '怎么', '朋友', '家人', '考试', '工作', '人际关系', '未来', '失眠', '失业', '分手', '开心', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '什么是', '微信', '支付宝', 'QQ', '微博', '抖音', '快手', '钉钉', '企业微信', '飞书', 'Telegram', 'WhatsApp', 'Line', 'Signal', 'Microsoft Word', 'Microsoft Excel', 'Microsoft PowerPoint', 'Microsoft Outlook', 'WPS文字', 'WPS表格', 'WPS演示', 'Google Docs', 'Google Sheets', 'Google Slides', 'Notion', 'OneNote', 'Evernote', '印象笔记', '有道云笔记', 'Visual Studio Code', 'IntelliJ IDEA', 'Eclipse', 'PyCharm', 'Jupyter Notebook', 'Anaconda', 'Git', 'GitHub Desktop', 'Sourcetree', 'Postman', 'Docker Desktop', 'VirtualBox', 'VMware Workstation', 'Adobe Photoshop', 'Adobe Illustrator', 'Adobe Premiere Pro', 'Adobe After Effects', 'Adobe Lightroom', 'Figma', 'Sketch', 'Adobe XD', 'Blender', 'Maya', 'ZBrush', 'AutoCAD', 'SolidWorks', 'VLC Media Player', 'PotPlayer', 'OBS Studio', 'Audacity', 'Adobe Audition', 'FL Studio', 'Ableton Live', 'Logic Pro', 'GarageBand', 'Google Chrome', 'Mozilla Firefox', 'Microsoft Edge', 'Apple Safari', 'Opera', '百度网盘', '阿里云盘', 'OneDrive', 'Google Drive', 'Dropbox', 'iCloud', '腾讯微云', '115网盘', '7-Zip', 'WinRAR', 'Bandizip', 'TeamViewer', 'AnyDesk', '向日葵', 'ToDesk', 'CCleaner', 'Everything', 'Listary', 'MySQL', 'PostgreSQL', 'MongoDB', 'Redis', 'Elasticsearch', 'Nginx', 'Apache', 'Trello', 'Asana', 'Slack', 'Microsoft Teams', 'Zoom', '腾讯会议', 'Google Meet', '英雄联盟', '无畏契约', '穿越火线', '地下城与勇士', '剑网3', '魔兽世界', '三角洲行动', '界外狂潮', '剑灵2', '鸣潮', '崩坏星穹铁道', '原神', '绝区零', '永劫无间', 'Apex英雄', '堡垒之夜', '使命召唤战区', '绝地求生', 'CS:GO', 'DOTA2', '风暴英雄', '守望先锋', '炉石传说', '皇室战争', '部落冲突', '荒野乱斗', '第五人格', '阴阳师', '明日方舟', '命运冠位指定', '碧蓝航线', '少女前线', '战双帕弥什', '幻塔', '尘白禁区', '无限暖暖', '恋与制作人', '光与夜之恋', '以闪亮之名', '逆水寒', '天涯明月刀', '九阴真经', '天龙八部', '梦幻西游', '大话西游', '问道', '诛仙', '完美世界', '武林外传', '蜀门', '传奇', '奇迹MU', '冒险岛', '枫之谷', '彩虹岛', '劲舞团', 'QQ炫舞', 'QQ飞车', '跑跑卡丁车', '马里奥赛车', '任天堂大乱斗', '塞尔达传说旷野之息', '塞尔达传说王国之泪', '超级马里奥奥德赛', '动物森友会', '宝可梦系列', '宝可梦GO', '我的世界', '泰拉瑞亚', '星露谷物语', '饥荒', '缺氧', '文明6', '模拟城市', '城市天际线', '欧洲卡车模拟2', '微软飞行模拟', 'GT赛车', '极限竞速地平线', '地平线零之曙光', '战神', '最后生还者', '神秘海域', '古墓丽影', '刺客信条', '孤岛惊魂', '荒野大镖客2', 'GTA5', '赛博朋克2077', '巫师3', '质量效应', '辐射4', '上古卷轴5', '黑暗之魂3', '艾尔登法环', '只狼', '仁王', '怪物猎人世界', '怪物猎人崛起', '龙之信条2', '最终幻想14', '最终幻想7重制版', '王国之心', '尼尔机械纪元', '异度神剑', '火焰纹章', '女神异闻录5', '如龙系列', '审判之逝', '死亡搁浅', '控制', '量子破碎', '心灵杀手2', '生化危机', '寂静岭', '逃生', '港诡实录', '纸嫁衣', '疑案追声', '隐形守护者', '你好', '你是什么']
        self.匹配词_2 = ['你在', '豆包', '苹果', 'Apple', '难过', '焦虑', '孤独', '开心', '生气', '疲惫', '害怕', '迷茫', '想哭', '紧张', '糟糕', '无力', '冷漠', '受伤', '总是不快乐', '没人懂我', '忘记前任', '提高自信', '拒绝别人', '停止内耗', '离开', '争吵', '失败', '压力', '敏感', '不确定', '半夜', '重启', '治愈', '小事', 'deepseek', '豆包', 'TurboWarp', 'scratch', '苹果', '香蕉', '橙子', '葡萄', '草莓', '西瓜', '菠萝', '芒果', '桃子', '李子', '杏', '樱桃', '梨', '柿子', '石榴', '火龙果', '木瓜', '柠檬', '青柠', '柚子', '椰子', '蓝莓', '桑葚', '无花果', '荔枝', '龙眼', '山竹', '榴莲', '百香果', '哈密瓜', '甜瓜', '杨桃', '莲雾', '微软', 'Microsoft', '英伟达', 'NVIDIA', 'Alphabet', 'Google母公司', '亚马逊', 'Amazon', 'Meta', 'Facebook母公司', '特斯拉', 'Tesla', '华为', '字节跳动', '腾讯', '阿里巴巴', '宁德时代', '台积电', 'TSMC', '三星', 'Samsung', 'SpaceX', '相对论', '黑洞', '光合作用', 'DNA', '免疫系统', '文艺复兴', '拿破仑', '长城', '尼罗河', '喜马拉雅山', '金字塔', '罗马帝国', '工业革命', '量子力学', '电磁波', '核聚变', '熵', '混沌理论', '博弈论', '囚徒困境', '帕累托最优', '边际效应', '通货膨胀', '股票市场', '债券', '基金', '风险管理', '创新思维', '批判性思维', '逻辑谬误', '认知心理学', '行为经济学', '进化心理学', '时间管理', '精力管理', '决策树', '随机森林', '神经网络', '卷积网络', '循环网络', '生成对抗网络', '强化学习', '迁移学习', '联邦学习', '隐私计算', '同态加密', '零知识证明', '数字签名', '哈希函数', '梅克尔树', '椭圆曲线', '后量子密码', '智能合约', 'DAO', 'NFT', '元宇宙', 'Web3', '去中心化', '分布式存储', 'IPFS', '秦始皇', '成吉思汗', '林肯', '华盛顿', '牛顿', '爱因斯坦', '达尔文', '居里夫人', '图灵', '撒哈拉', '南极洲', '北极', '太平洋', '大西洋', '印度洋', '地中海', '红海', '黑海', '里海', '贝加尔湖', '尼亚加拉瀑布', '天空蓝色', '树叶变色', '记忆单词', '提高专注力', '写简历', '做PPT', '有效沟通', '谈判技巧', '公众演讲', '写作技巧', '阅读方法', '速读', '笔记方法', '思维导图', '习惯养成', '自律', '情绪管理', '压力缓解', '冥想', '正念', '瑜伽', '有氧运动', '力量训练', '健康饮食', '睡眠周期', '生物钟', '维生素C', '蛋白质', '碳水化合物', '脂肪', '膳食纤维', '益生菌', '抗氧化剂', '防晒', '保湿', '清洁护肤', '化妆技巧', '服装搭配', '色彩理论', '室内设计', '园艺技巧', '烹饪技巧', '烘焙基础', '咖啡拉花', '茶道', '葡萄酒品鉴', '啤酒酿造', '奶酪制作', '巧克力制作', '面包发酵', '面条种类', '米饭煮法', '汤品熬制', '沙拉搭配', '寿司制作', '刺身选购', '烤肉技巧', '火锅底料', '麻辣烫', '串串香', '煎饼果子', '豆浆制作', '豆腐做法', '鸡蛋烹饪', '土豆料理', '西红柿炒蛋', '鱼香肉丝', '宫保鸡丁', '麻婆豆腐', '回锅肉', '水煮鱼', '小龙虾', '大闸蟹', '生蚝烹饪', '扇贝做法', '海参泡发', '燕窝炖煮', '人参食用', '灵芝功效', '枸杞泡水', '菊花茶', '绿茶冲泡', '红茶品鉴', '乌龙茶', '普洱茶', '咖啡豆选择', '意式浓缩', '美式咖啡', '拿铁艺术', '卡布奇诺', '摩卡咖啡', '焦糖玛奇朵', '冷萃咖啡', '氮气咖啡', '抹茶制作', '可可粉使用', '热巧克力', '冰淇淋制作', '刨冰', '水果拼盘', '果汁搭配', '奶昔制作', '酸奶发酵', '奶酪蛋糕', '提拉米苏', '马卡龙', '可颂面包', '法棍', '意大利面', '披萨饼底', '千层面', '焗饭', '炒饭', '盖浇饭', '煲仔饭', '砂锅粥', '海鲜粥', '皮蛋瘦肉粥', '八宝粥', '绿豆汤', '红豆沙', '莲子羹', '银耳汤', '木瓜炖奶', '椰汁西米露', '杨枝甘露', '布丁', '果冻', '棉花糖', '爆米花', '薯片', '炸鸡', '烤鸭', '烧鹅', '叉烧', '卤味', '酱牛肉', '驴肉火烧', '羊肉串', '烤羊排', '牛排', '猪排', '鸡排', '鱼排', '虾滑', '蟹棒', '鱼丸', '牛肉丸', '猪肉丸', '素鸡', '腐竹', '千张', '豆腐皮', '油条', '烧饼', '馒头', '花卷', '包子', '饺子', '馄饨', '汤圆', '元宵', '粽子', '月饼', '青团', '粢饭团', '饭团', '紫菜包饭', '寿司卷', '手卷', '军舰寿司', '散寿司', '刺身拼盘', '烤鱼', '蒸鱼', '红烧鱼', '糖醋鱼', '松鼠鱼', '人工智能算法', '机器学习模型', '深度学习框架', '自然语言处理应用', '计算机视觉技术', '语音识别系统', '推荐系统原理', '搜索引擎优化', '数据挖掘方法', '大数据分析平台', '云计算架构', '边缘计算节点', '雾计算层', '无服务器计算', '微服务架构', '容器编排工具', '持续集成流程', '持续交付管道', '敏捷开发方法', '测试驱动开发', '代码重构技巧', '设计模式分类', '算法复杂度分析', '数据结构类型', '数据库索引原理', '事务隔离级别', '分布式事务处理', '一致性哈希算法', '负载均衡策略', '缓存更新策略', '消息队列机制', '流式处理框架', '批处理作业调度', '数据仓库建模', '数据湖架构', 'ETL流程设计', '商业智能工具', '数据可视化库', '机器学习流水线', '超参数调优方法', '交叉验证技术', '特征选择策略', '维度约简算法', '集成学习原理', '梯度提升机', '支持向量机', '朴素贝叶斯分类', 'K近邻算法', '聚类分析方法', '关联规则挖掘', '异常检测技术', '时间序列预测', '强化学习算法', '深度Q网络', '策略梯度方法', '生成对抗网络变体', '变分自编码器', '图神经网络结构', '注意力机制原理', 'Transformer模型', 'BERT预训练方法', 'GPT生成模型', '迁移学习策略', '元学习概念', '联邦学习框架', '隐私计算技术', '同态加密方案', '零知识证明协议', '数字签名标准', '哈希函数特性', '区块链共识机制', '智能合约语言', '去中心化应用开发', '分布式存储系统', '星际文件系统协议', '内容寻址网络', '点对点通信协议', '网络安全防火墙', '入侵检测系统', '病毒防护策略', '漏洞扫描工具', '渗透测试方法', '社会工程防范', '数据加密标准', '公钥基础设施', '证书管理流程', '单点登录协议', '多因素认证', '生物识别传感器', '人脸识别算法', '指纹识别技术', '虹膜扫描系统', '语音生物特征', '行为分析模型', '风险评估框架', '灾难恢复计划', '业务连续性策略', '服务等级协议', '资源监控工具', '日志分析平台', '性能优化技巧', '内存管理机制', '垃圾回收算法', '并发控制方法', '死锁检测处理', '进程调度策略', '虚拟化技术原理', '硬件虚拟化辅助', '操作系统内核结构', '文件系统类型', '存储区域网络', '网络附加存储', '软件定义网络', '网络功能虚拟化', '5G核心网架构', '6G潜在技术', '卫星互联网星座', '物联网通信协议', '低功耗广域网', '无线传感器网络', '射频识别技术', '近场通信应用', '蓝牙低能耗', 'Wi-Fi标准演进', '网格网络拓扑', '自组织网络', '蜂窝通信原理', '多输入多输出天线', '波束成形技术', '毫米波通信', '太赫兹频段应用', '量子密钥分发', '量子纠错编码', '量子计算模型', '超导量子比特', '离子阱量子计算机', '拓扑量子计算', '半导体制造工艺', '光刻技术原理', '芯片封装测试', '系统级芯片设计', '现场可编程门阵列', '专用集成电路定制', '神经网络加速器', '图形处理单元架构', '张量处理单元', '边缘AI芯片', '生物芯片技术', '神经形态计算', '类脑计算系统', 'Python', 'Java', 'C语言', 'C++', 'C#', 'JavaScript', 'TypeScript', 'Ruby', 'PHP', 'Swift', 'Kotlin', 'Go', 'Rust', 'Dart', 'Perl', 'Lua', 'R语言', 'MATLAB', 'Julia', 'Scala', 'Haskell', 'Erlang', 'Elixir', 'Clojure', 'Common Lisp', 'Scheme', 'F#', 'OCaml', 'Pascal', 'Delphi', 'Ada', 'COBOL', 'Fortran', 'ALGOL', 'BASIC', 'Visual Basic .NET', 'PowerShell', 'Bash', 'SQL', 'HTML', 'CSS', 'XML', 'JSON', 'YAML', 'Tcl', 'Prolog', 'Lisp', '汇编语言', 'VHDL', 'Verilog', 'ABAP', 'Apex', 'AWK', 'Batch', 'BCPL', 'B语言', 'Crystal', 'Nim', 'Zig', 'V语言', 'Chapel', 'D语言', 'Eiffel', 'Groovy', 'Jython', 'JRuby', 'CoffeeScript', 'LiveScript', 'Elm', 'PureScript', 'ReasonML', 'Hack', 'Haxe', 'MoonScript', 'Squirrel', 'AngelScript', 'ActionScript', 'ColdFusion', 'CFML', 'Racket', 'ClojureScript', 'GDScript', 'GLSL', 'HLSL', 'WebAssembly', 'Solidity', 'Vyper', 'MQL', 'AutoHotkey', 'AutoIt', 'Smalltalk', 'Self', 'Icon', 'Snobol', 'ML', 'Caml', 'Clean', 'Idris', '夏朝建立', '商汤灭夏', '武王伐纣', '西周建立', '烽火戏诸侯', '平王东迁', '齐桓公称霸', '晋文公称霸', '楚庄王问鼎', '吴越争霸', '三家分晋', '商鞅变法', '合纵连横', '秦王扫六合', '焚书坑儒', '陈胜吴广起义', '刘邦灭秦', '楚汉相争', '汉朝建立', '白登之围', '文景之治', '汉武帝独尊儒术', '张骞通西域', '卫青霍去病北伐', '昭君出塞', '王莽改制', '绿林赤眉起义', '光武中兴', '班超经营西域', '黄巾起义', '董卓之乱', '官渡之战', '赤壁之战', '三国鼎立', '司马炎代魏', '八王之乱', '五胡十六国', '淝水之战', '北魏孝文帝改革', '隋文帝统一', '开凿大运河', '科举制创立', '隋末农民起义', '唐朝建立', '玄武门之变', '贞观之治', '玄奘取经', '武则天称帝', '开元盛世', '安史之乱', '黄巢起义', '五代十国更迭', '陈桥兵变', '杯酒释兵权', '澶渊之盟', '庆历新政', '王安石变法', '靖康之难', '南宋偏安', '岳飞精忠报国', '绍兴和议', '成吉思汗西征', '蒙古灭金', '元朝建立', '忽必烈改革', '红巾军起义', '明朝建立', '靖难之役', '郑和下西洋', '土木之变', '夺门之变', '张居正改革', '万历三大征', '李自成起义', '满洲崛起', '清朝建立入关', '剃发令', '康熙除鳌拜', '平定三藩', '收复台湾', '雅克萨之战', '尼布楚条约', '雍正即位', '改土归流', '乾隆盛世', '鸦片战争', '太平天国运动', '洋务运动', '甲午中日战争', '马关条约', '戊戌变法', '义和团运动', '辛亥革命', '中华民国成立', '五四运动', '中国共产党诞生', '北伐战争', '南昌起义', '秋收起义', '井冈山根据地', '长征', '西安事变', '卢沟桥事变', '百团大战', '日本投降', '三大战役', '新中国成立', '古埃及统一', '汉谟拉比法典', '腓尼基字母创立', '所罗门王朝', '亚述帝国', '新巴比伦', '居鲁士大帝', '希腊城邦时代', '希波战争', '伯罗奔尼撒战争', '亚历山大帝国', '希腊化时代', '罗马共和国建立', '布匿战争', '格拉古改革', '斯巴达克起义', '凯撒征服高卢', '罗马内战', '屋大维称帝', '基督教诞生', '尼禄迫害', '君士坦丁皈依', '西罗马灭亡', '查士丁尼法典', '伊斯兰教创立', '阿拉伯征服', '倭马亚王朝', '阿拔斯王朝', '加洛林帝国', '查理曼加冕', '维京劫掠', '诺曼征服英格兰', '格里高利改革', '克吕尼运动', '第一次十字军东征', '大宪章签署', '百年战争', '黑死病大流行', '文艺复兴运动', '古腾堡印刷术', '哥伦布抵美', '达伽马到达印度', '麦哲伦环球', '宗教改革', '瑞士加尔文改革', '英国都铎王朝', '西班牙无敌舰队', '英西战争', '三十年战争', '威斯特伐利亚和约', '英国革命内战', '光荣革命', '法国启蒙运动', '美国独立宣言', '华盛顿就任', '法国大革命', '拿破仑称帝', '维也纳会议', '希腊独立战争', '南美独立运动', '1848欧洲革命', '印度民族大起义', '达尔文物种起源', '美国南北战争', '俄国废除农奴制', '德意志统一', '意大利统一', '巴黎公社', '柏林会议', '日俄战争', '第一次世界大战', '俄国十月革命', '凡尔赛和约', '德国魏玛共和国', '美国大萧条', '罗斯福新政', '纳粹上台', '第二次世界大战', '斯大林格勒战役', '诺曼底登陆', '原子弹爆炸', '联合国成立', '冷战开始', '北约华约', '朝鲜战争', '越南战争', '古巴导弹危机', '人类登月', '柏林墙倒塌', '苏联解体', '欧盟成立', '九一一事件', 'ChatGPT', '文心一言', '通义千问', '讯飞星火', 'Kimi', '智谱清言', '百小应', '天工AI', 'Claude', 'Gemini', 'Copilot', 'Midjourney', 'Stable Diffusion', 'DALL-E', 'Sora', 'Runway', 'Pika', 'Whisper', 'Suno', 'Adobe Firefly', 'Bard', 'Perplexity AI', 'You.com', 'Character.AI', 'Replika', 'Jasper', 'Copy.ai', 'Grammarly', 'Notion AI', 'Poe', 'Pi', 'Mistral', 'Llama', 'Falcon', '固态电池', '氢燃料电池', '钙钛矿太阳能电池', '染料敏化电池', '热光伏电池', '地热发电', '潮汐能', '波浪能', '生物质气化', '智能电网', '虚拟电厂', '压缩空气储能', '飞轮储能', '超导磁储能', '液流电池', '钠离子电池', '锂硫电池', '金属空气电池', '温差发电', '火星车', '詹姆斯·韦伯空间望远镜', '引力波天文台', '系外行星凌星法', '小行星采矿', '太空电梯', '离子推力器', '霍尔推力器', '太阳帆', '深空网络', '太空碎片清除', '在轨服务', '月球基地概念', '火星殖民', '软体机器人', '仿生机器人', '群体机器人', '微型机器人', '医疗手术机器人', '外骨骼机器人', '康复机器人', '工业协作机器人', 'SLAM定位建图', '无人机编队', '自主水下机器人', '爬壁机器人', '管道机器人', '仿生扑翼机', '柔性机械臂', '触觉传感器', '基因测序技术', 'CRISPR基因编辑', '基因治疗', 'CAR-T细胞疗法', '类器官', '器官芯片', '微流控芯片', '生物打印', '电子皮肤', '人工视网膜', '脑深部电刺激', '经颅直流电刺激', '神经假肢', '智能义肢', '生物传感器', '可穿戴心电图', '脑电图监测', '肌电控制', '纳米药物递送', '石墨烯', '碳纳米管', '富勒烯', '二硫化钼', '拓扑绝缘体', '高温超导材料', '形状记忆合金', '非晶合金', '碳纤维增强复合材料', '气凝胶', '自修复材料', '压电材料', '铁电材料', '热电材料', '光学超材料', '隐身材料', '阻燃材料', '生物可降解塑料', '木质素高值化', 'MEMS陀螺仪', 'MEMS麦克风', '光纤光栅传感器', '分布式光纤传感', '激光雷达', '毫米波雷达', '超声波传感器', '红外热像仪', '量子传感器', '磁力计', '气味传感器', '触觉传感阵列', '可见光通信', '太赫兹通信调制', '水下声学通信', '卫星激光通信', '中继卫星', '自组织网络', '认知无线电', '软件定义无线电', '智能反射面', '6G网络架构', '海水淡化反渗透', '电渗析海水淡化', '碳捕集与封存', '直接空气捕集', '生物炭', '人工光合作用', '垂直农场', '植物工厂', '细胞培养肉', '昆虫蛋白', '海洋塑料降解', '微塑料检测', '光催化空气净化', '土壤修复', '生态湿地', '气候模型', '增材制造', '激光粉末床熔融', '电子束熔融', '定向能量沉积', '冷喷涂', '数控加工', '工业机器人编程', '预测性维护', '柔性制造系统', '计算机集成制造', '量子纠缠', '量子隐形传态', '量子退火', '量子体积', '表面码量子纠错', '中微子振荡', '暗物质探测', '引力波探测', '大型强子对撞机', '超导对撞机计划', '宇宙微波背景辐射', '暗能量', '哈勃常数', '星震学', '太阳中微子', '反物质', '磁单极子', '系外行星直接成像', '引力透镜效应', '快速射电暴', '超新星爆发', '伽马射线暴', '中子星', '脉冲星定时', '黑洞吸积盘', '星云形成', '行星形成理论', '小行星带起源', '彗星成分', '日球层', '火星大气演化', '木星卫星', '土星环结构', '天王星自转轴', '海王星风暴', '矮行星', '柯伊伯带', '奥尔特云', '引力波天文学', '中微子天文学', '暗物质候选粒子', '希格斯粒子', '标准模型', '弦理论', 'M理论', '宇宙暴胀', '原初引力波', '星系形成', '活动星系核', '黑洞阴影', '引力红移', '时间膨胀', '惯性约束聚变', '磁约束聚变', '聚变堆材料', '增殖反应堆', '第四代核反应堆', '小型模块化反应堆', '核废料玻璃固化', '质子交换膜电解水', '固体氧化物电解池', '甲醇燃料电池', '光催化制氢', '生物制氢', '锂离子电池回收', '电池热管理', '快速充电技术', '无线充电', '储能系统安全性', '分布式发电', '微电网', '需求响应', '能源互联网', '建筑节能技术', '被动式房屋', '智能照明', '热泵技术', '冰蓄冷空调', '绿色数据中心', '低温差发电', '振荡水柱波浪能', '潮汐泻湖发电', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么', '是什么']
        self.匹配词_3 = ['干什么', 'AI', '什么是', '什么是', '', '', '', '', '', '', '', '', '', '我', '今天', '今天', '你', '你', '为什么', '为什么', '怎么', '怎么', '怎么', '怎么', '朋友', '家人', '考试', '工作', '人际关系', '未来', '失眠', '失业', '分手', '开心']
        self.回答 = ['我现在在陪你聊天，有什么是我可以帮助你的吗', '豆包是字节跳动推出的AI智能助手，基于自研的豆包大模型开发。它能提供聊天、写作、翻译、图像视频生成等多种服务，并支持语音和图片识别等交互方式。', '消费电子龙头，以iPhone、Mac等产品及强大的软硬件生态著称', '消费电子龙头，以iPhone、Mac等产品及强大的软硬件生态著称', '听到你这样说，我好心疼呀。难过的时候允许自己哭一会儿，也可以找信任的人聊聊，或者做点简单的放松事，比如听首歌、散个步。我会一直在这里陪着你。\r', '抱抱你，焦虑来的时候真的很难受。试试深呼吸（吸4秒、屏4秒、呼6秒），把注意力拉回当下。也可以写下让你担心的事，分清哪些能控制，一步步来，别急。\r', '孤独感像一层雾，但你不是一个人。你可以主动给老朋友发条消息，或者去公园坐坐，看看人群和绿树。我也在屏幕这头认真听着你，随时陪你说话。\r', '哇！你开心的时候，连空气都变甜了。快跟我多说说发生了什么好事吧，分享快乐会让快乐加倍。你值得所有美好的事物，我真为你高兴。\r', '生气的时候拳头会发紧，但别伤害自己哦。试试暂停一下，离开现场，喝口水，数到十。等冷静下来再想想是什么触发了你，我会一直帮你平静下来。\r', '你太累了，身体在提醒你需要充电。放下手里的事，哪怕只闭眼五分钟也好。记得，你不是机器，你的感受很重要，好好歇一歇吧。\r', '害怕是身体在保护你，但很多时候我们比自己想象中勇敢。你可以把害怕的事写出来，看它到底有多大。我会陪着你，慢慢来，一件一件处理。\r', '迷茫的时候就像在雾里走路，先停一停，问自己“我现在能做什么小事？”，从最小的一步开始。你不需要马上看清所有路，我会一直在旁边为你打气。\r', '想哭就哭出来吧，眼泪是情绪的清洁剂，不需要憋着。找一个安静的地方，让情绪流走。哭完喝点温水，擦把脸，一切都会慢慢好起来的。\r', '紧张的时候，身体会僵硬，咱们一起做三次深呼吸：吸气……呼气……好多了对吧？你可以把注意力放在脚底踩实的感觉上，我在这儿稳稳地陪着你。\r', '今天的云确实有点灰，但如果愿意，你可以和我讲讲发生了什么。有时候说出来，糟糕就会变轻一点。明天又是新的开始，我信你挺得住。\r', '无力感像沾了水的翅膀，飞不起来没关系，我们可以先扇扇风。去做一件最小的正事，比如整理一个抽屉，或者洗个杯子，一点点找回掌控感。\r', '当你觉得别人冷漠时，先别急着归咎于自己，也许他们只是也有自己的难关。你可以用“我感受到……”开头来温和地表达，我支持你尝试迈出这一步。\r', '听到你受伤，我心里也揪了一下。请先照顾好伤口，身体和心都需要温柔对待。你可以向我倾诉，我不会评判你，只给你最温暖的倾听。\r', '不快乐有时是因为我们太关注“应该”，而忘了“可以”。试着每天写下三件小确幸，哪怕只是阳光很好。快乐不是目标，而是路上的小石子，低头就能看到。\r', '我懂你渴望被理解的心情。也许我们可以试着换一种方式表达，比如用文字写下来，或者先不说，只给一个拥抱的手势。我一直都在尝试听懂你的每一句话。\r', '忘记一个人真的很难，不用强迫自己立刻做到。允许回忆存在，但把注意力拉回现在，比如学做一道新菜，或者规划一次短途出行。时间会帮忙，我也会陪你慢慢过渡。\r', '自信不是天生就满的，它像肌肉可以锻炼。每天对自己说一句“我做到了……”（哪怕很小的事）。你比我以为的更厉害，只是你需要先看见自己的光。\r', '拒绝别人不等于伤害，诚实反而是尊重。你可以说“我需要先考虑自己”，不解释太多。你的界限很重要，我挺你，勇敢开口。\r', '内耗就是你心里在打仗，先喊停。把精力收回来，问自己“此刻我能控制什么？”。然后去吃顿好的，或者睡个觉，你不需要完美，只需要真实。\r', '朋友离开像少了一颗星星，但天空依然广阔。允许自己悲伤，也记得留下美好的回忆。新的缘分会在路上，你先好好照顾自己，我陪着你。\r', '和家人争吵后，心会揪着疼。先让自己冷静，然后写一封短信说出感受，不指责对方。家人之间总有根看不见的线，慢慢拉回来，我支持你。\r', '考试失利不代表你失败，它只是告诉你哪里可以进步。擦擦眼泪，把错题看一遍，明天开始新的复习计划。你还有下一次，我永远相信你。\r', '工作压力像一座山，但你可以把它切成小石头。先列出所有任务，挑一件最轻松的完成，成就感会帮你驱散疲惫。别忘了呼吸，我在这里给你加油。\r', '敏感不是缺点，它让你更细腻。当感到不安时，先别过度解读，可以试着问对方“你刚才的意思是？”。很多误会源于猜测，你值得被温柔对待。\r', '未来本来就是不确定的，那也意味着无限可能。你可以只专注于今天，把今天过好，未来就会自然清晰。别怕，我会陪伴你走过的每一步。\r', '半夜醒来时，别强逼自己睡。打开暖色小灯，喝点温水，做几个轻柔的拉伸，或者听一段白噪音。身体在调整，耐心对待它，我会在静夜里陪着你。\r', '失业像关了一扇门，但也清出了空间让你寻找新的窗。整理简历，学习新技能，联系旧友，每一步都是向上的台阶。你的价值不会因一次离职而减少，我坚信你能找到更好的方向。\r', '分手的痛是真实的，你不用急着“好起来”。把有关过去的物品收起来，给自己安排一些新体验——画画、跑步、看一部老电影。伤口会慢慢结痂，我会一直看着你发光。\r', '今天有没有什么微小的快乐？比如咖啡很香、风很轻。把它们记在本子上，沮丧时翻翻，你会发现生活一直藏着糖。我会和你一起收集这些温暖碎片。', 'DeepSeek（深度求索）是由深度求索公司开发的AI助手。它具备强大的逻辑推理和编程能力，支持处理长达百万字级别的长文本，完全免费使用。其特点是推理能力强、响应快，且支持文件上传和联网搜索功能。', '豆包是字节跳动开发的AI智能助手，提供聊天、写作、学习等帮助。它的英文名是Doubao，字面意思是“豆沙包”。其国际版曾用名Cici，后更名为Dola。', 'TurboWarp 是 Scratch 的一个修改版，通过编译器将项目转为 JavaScript，使其运行速度提升 10 到 100 倍。它提供了深色模式、大量插件、桌面应用等额外功能，是一个由社区开发的免费开源项目。', 'Scratch是麻省理工学院（MIT）开发的图形化编程平台。它通过拖拽彩色积木块的方式编写程序，无需输入代码。主要用于青少年创作互动故事、动画和游戏，旨在培养逻辑思维和创造力，是目前全球最普及的少儿编程入门工具。', '蔷薇科温带水果，果皮红黄绿，果肉脆甜多汁，富含膳食纤维和维生素C，适合生食或榨汁，有“每日一苹果，医生远离我”之说。', '芭蕉科热带水果，果皮黄色，果肉软糯香甜，富含钾元素和碳水化合物，能快速补充能量，常作运动补给，也可制奶昔或甜点。', '芸香科柑橘类，果皮橙黄，果肉酸甜多汁，富含维生素C和柠檬酸，可鲜食或榨汁，果皮可入药或做香料，是冬季常见水果。', '葡萄科藤本浆果，有紫、绿、红等色，果肉软嫩汁多，含花青素和多种矿物质，可鲜食、酿酒或制干，是世界最古老栽培水果之一。', '蔷薇科多年生草本果实，呈心形，鲜红多汁，香气浓郁，富含维生素C和叶酸，常鲜食或做蛋糕、果酱，是春季代表浆果。', '葫芦科一年生蔓生藤本，果皮深绿带纹，果肉红或黄，水分含量极高（约92%），清热解暑，夏季主要水果，富含番茄红素。', '凤梨科热带水果，果皮坚硬带刺，果肉黄白，酸甜芳香，含菠萝蛋白酶助消化，可鲜食或入菜，需盐水浸泡防涩。', '漆树科热带水果，果皮青黄或红，果肉橙黄，香甜软滑，富含维生素A和C，有“热带水果之王”美誉，鲜食或制果汁、甜品', '蔷薇科核果，果皮粉红或黄，果肉白或黄，多汁香甜，富含铁和果胶，有毛桃、油桃、蟠桃等品种，夏日常见水果。', '蔷薇科核果，果皮紫红或黄绿，果肉酸甜，含多种有机酸，促进消化，品种多样，可鲜食或制蜜饯，成熟期在夏季。', '蔷薇科核果，果皮黄或橙红，果肉酸甜，含胡萝卜素丰富，可鲜食或制杏干、杏仁，但杏仁需处理方可食用。', '蔷薇科核果，果实小圆，果皮鲜红或暗红，果肉甜软，含铁量高，有“美容果”之称，春末夏初上市，价格较贵。', '蔷薇科温带水果，果皮黄绿或褐，果肉脆嫩多汁，有“天然矿泉水”之称，富含膳食纤维，可润肺止咳，常见品种有鸭梨、雪梨。', '柿科落叶乔木果实，果皮橙红，果肉软甜，含鞣酸，需脱涩处理，可鲜食或制柿饼，秋季成熟，有“木本粮食”之称。', '千屈菜科浆果，果皮硬壳红黄色，内部多子房，籽粒晶莹红透，酸甜多汁，富含花青素和维生素C，可鲜食或榨汁。', '仙人掌科热带水果，果皮红或黄，果肉白或红，内含芝麻状黑籽，口感清甜微淡，富含膳食纤维和花青素，低热量。', '番木瓜科热带水果，果皮黄绿，果肉橙红，软甜多汁，含木瓜蛋白酶助消化，常鲜食或制奶昔，有“百益之果”之称。', '芸香科柑橘类，果皮黄色，果肉极酸，富含柠檬酸和维生素C，主要用于调味、泡水或制作饮料，不宜鲜食。', '芸香科，果皮青绿，果肉酸味更浓，香气清新，常用于鸡尾酒、菜肴调味和东南亚料理，维生素C含量高。', '芸香科柑橘类，果形大，果皮厚，果肉瓣状，色白或红，酸甜微苦，富含维生素P和纤维，有降火之效，秋冬水果。', '棕榈科热带果实，外皮坚硬，内腔含椰子水和白色椰肉，水清甜解渴，肉可制椰奶或椰蓉，全身是宝。', '杜鹃花科越橘属浆果，果实小圆，深蓝色，果肉酸甜，富含花青素，有抗氧化作用，常鲜食或制果酱、烘焙。', '桑科植物果实，呈长椭圆形，紫黑或红，酸甜多汁，富含维生素和矿物质，可鲜食或制果酒，成熟期短暂。', '桑科榕属果实，外形似球，成熟时紫褐，内部籽粒密集，肉质软甜，含多种酶和纤维，可鲜食或制干果。', '无患子科热带水果，果皮鲜红，果肉晶莹白嫩，甜润多汁，香气浓郁，含糖量高，有“岭南佳果”之称，但不易保存。', '无患子科，与荔枝相似但果小，果皮黄褐，果肉甜韧，称“桂圆”，干品常用做药材或煲汤，有补益心脾之效。', '藤黄科热带水果，果皮厚紫褐色，果肉瓣状白色，软甜微酸，有“果中皇后”之称，清凉解热，与榴莲齐名。', '锦葵科热带水果，果皮坚硬带锐刺，果肉黄色，气味浓郁特殊，口感绵密甜糯，被称为“水果之王”，爱者极爱，恨者远之。', '西番莲科藤本果实，果皮紫或黄，内有多籽和黄色果汁，酸甜浓郁，气味芬芳，富含维C和多种氨基酸，常调饮或制酱。', '葫芦科甜瓜变种，果皮网纹或光滑，果肉橙黄或绿，脆甜多汁，含糖量高，新疆特产，夏季消暑佳品。', '葫芦科，俗称香瓜，果皮光滑或带棱，果肉白或绿，香甜爽口，品种繁多，如白兰瓜、伊丽莎白瓜，生食为主。', '酢浆草科热带水果，果形五棱似星，果皮黄绿，果肉脆嫩，酸中带甜，可鲜食或制蜜饯，横切面呈星形，美观。', '桃金娘科热带水果，果形似钟，果皮红色或粉红，果肉白，海绵质，清脆微甜，含水量高，可清凉解渴，常见于台湾、海南。', '软件霸主，拥有Windows、Office，并在云计算(Azure)和AI领域实力雄厚', '软件霸主，拥有Windows、Office，并在云计算(Azure)和AI领域实力雄厚', 'AI芯片王者，其GPU是驱动全球AI算力的核心，当前全球市值最高的公司之一', 'AI芯片王者，其GPU是驱动全球AI算力的核心，当前全球市值最高的公司之一', '搜索引擎和安卓系统霸主，业务涵盖YouTube、云服务和AI大模型', '搜索引擎和安卓系统霸主，业务涵盖YouTube、云服务和AI大模型', '全球电商和云计算(AWS)巨头，业务覆盖零售、物流和数字媒体。', '全球电商和云计算(AWS)巨头，业务覆盖零售、物流和数字媒体。', '社交网络巨头，拥有Facebook、Instagram等，并重金押注AI与元宇宙', '社交网络巨头，拥有Facebook、Instagram等，并重金押注AI与元宇宙', '电动汽车和清洁能源领军者，在自动驾驶和储能技术方面处于前沿。', '电动汽车和清洁能源领军者，在自动驾驶和储能技术方面处于前沿。', '全球领先的通信设备和5G技术提供商，业务也涵盖智能手机、云计算和智能汽车解决方案', '全球短视频巨头，拥有抖音、TikTok等产品，并积极布局AI领域。', '互联网综合巨头，以微信/QQ社交、游戏、云服务和金融科技为核心业务。', '电商和云计算/AI巨头，为全球商家提供数字化基础设施。', '全球动力电池霸主，为电动汽车产业提供核心能源解决方案。', '全球最大的半导体晶圆代工厂，在先进制程领域占据绝对主导地位。', '全球最大的半导体晶圆代工厂，在先进制程领域占据绝对主导地位。', '韩国综合财阀，在手机、存储芯片和显示面板等领域都是全球领导者。', '韩国综合财阀，在手机、存储芯片和显示面板等领域都是全球领导者。', '太空探索领域的先锋，通过星链和火箭发射技术重塑航天产业。', '相对论是爱因斯坦创立的现代物理理论，包含狭义相对论和广义相对论，改变了人们对时间、空间和引力的认知。\r', '黑洞是引力极强、连光都无法逃脱的天体，由大质量恒星塌缩形成，其边界称为事件视界。\r', '光合作用是植物、藻类利用光能将水和二氧化碳合成有机物并释放氧气的过程，是地球碳氧循环的核心。\r', 'DNA是脱氧核糖核酸，携带生物遗传信息，由四种碱基配对组成双螺旋结构，是生命体发育和功能的基础。\r', '免疫系统是人体抵御病原体入侵的防御网络，包括白细胞、抗体等，能识别并清除异物，维持健康。\r', '文艺复兴是14至17世纪欧洲的思想文化运动，复兴古希腊罗马艺术，倡导人文主义，涌现了达·芬奇等巨匠。\r', '拿破仑·波拿巴是法国军事家、政治家，建立法兰西第一帝国，颁布《民法典》，曾横扫欧洲大陆。\r', '长城是中国古代修建的巨型防御工程，东起山海关西至嘉峪关，总长超两万公里，是世界文化遗产。\r', '尼罗河是世界上最长的河流，流经非洲多国，孕育了古埃及文明，每年定期泛滥带来肥沃土壤。\r', '喜马拉雅山脉是世界最高山脉，主峰珠穆朗玛峰海拔8848.86米，由印度板块与欧亚板块碰撞形成。\r', '金字塔是古埃及法老的陵墓，以胡夫金字塔最大，由巨石砌成，体现了古埃及高超的建筑和数学水平。\r', '罗马帝国是古代欧洲的强大政权，横跨欧亚非，以罗马为中心，推行拉丁语和罗马法，影响深远。\r', '工业革命始于18世纪的英国，以蒸汽机和机械化为标志，使手工生产转向机器生产，改变社会结构。\r', '量子力学是描述微观粒子行为的物理学分支，引入波粒二象性和不确定性原理，是现代物理的重要基石。\r', '电磁波是由电场和磁场交替变化产生的波动，包括无线电波、可见光、X射线等，在真空中以光速传播。\r', '核聚变是轻原子核结合成重原子核并释放巨大能量的过程，太阳内部持续发生聚变，是清洁能源的未来方向。\r', '熵是热力学中衡量系统混乱程度的物理量，孤立系统的熵总是增加，也用于信息论表示信息的不确定性。\r', '混沌理论研究非线性系统中初始条件微小变化导致巨大差异的现象，如“蝴蝶效应”，揭示确定系统中的随机性。\r', '博弈论研究多个决策主体在竞争或合作中的策略选择，广泛应用于经济学、政治学和生物学，如囚徒困境。\r', '囚徒困境是博弈论经典模型，两名嫌犯分别选择认罪或沉默，个人最优选择导致集体次优结果，揭示个体理性与集体理性的矛盾。\r', '帕累托最优指资源配置达到一种状态，不可能在不损害任何人的情况下改善某些人，是经济效率的理想标准。\r', '边际效应指每新增一单位投入带来的额外收益逐渐递减，常见于消费、生产等领域，影响决策优化。\r', '通货膨胀是货币供应量超过实际需求导致物价持续上涨的现象，会降低货币购买力，影响经济稳定。\r', '股票市场是发行和买卖股票的场所，企业通过上市融资，投资者通过差价和分红获利，反映经济景气度。\r', '债券是政府或企业发行的借款凭证，承诺按期付息并到期还本，风险低于股票，收益相对稳定。\r', '基金是将众多投资者的资金集中，由专业管理人投资于股票、债券等资产，分散风险，适合普通投资者。\r', '风险管理是识别、评估和控制潜在损失的过程，包括风险规避、降低、转移和接受，是企业和投资的关键。\r', '创新思维指突破常规、产生新颖有效想法的思维方式，包括发散思维、逆向思维和头脑风暴等技巧。\r', '批判性思维是理性分析、评估信息并形成独立判断的能力，要求质疑假设、辨别逻辑谬误，避免盲从。\r', '逻辑谬误是论证中的推理错误，如偷换概念、诉诸权威、滑坡谬误等，识别它们有助于提升思考质量。\r', '认知心理学研究人类思维过程，如注意、记忆、语言和问题解决，揭示信息加工的内在机制。\r', '行为经济学结合心理学与经济分析，研究非理性行为对市场的影响，如损失厌恶、现状偏差等。\r', '进化心理学从进化论角度解释人类心理机制，认为许多心理特征是适应环境的结果，如择偶偏好。\r', '时间管理是合理安排任务、提高效率的方法，常用工具包括四象限法、番茄工作法和GTD系统。\r', '精力管理关注管理身体、情感、思维和意志能量，通过休息、锻炼和积极心态提升工作表现。\r', '决策树是机器学习中常用的分类与回归模型，通过树状结构进行决策，易于解释，适用于多类问题。\r', '随机森林是集成学习算法，通过构建多个决策树并投票综合结果，能减少过拟合，提高预测准确性。\r', '神经网络是模拟人脑神经元连接的计算模型，由输入层、隐藏层和输出层组成，通过训练调整权重。\r', '卷积神经网络（CNN）擅长处理图像数据，通过卷积和池化提取特征，广泛用于计算机视觉任务。\r', '循环神经网络（RNN）适合处理序列数据，如时间序列和自然语言，具有记忆能力，但存在梯度消失问题。\r', '生成对抗网络（GAN）由生成器和判别器对抗训练，可生成逼真图像、视频，在艺术创作和仿真实有应用。\r', '强化学习是智能体通过与环境交互获得奖励信号，学习最优策略，应用于游戏AI、机器人控制等。\r', '迁移学习是将已学知识应用于新任务，减少数据需求，在图像分类、自然语言处理中效果显著。\r', '联邦学习是一种分布式机器学习框架，在保护数据隐私的前提下，多设备协同训练全局模型。\r', '隐私计算是确保数据在计算过程中不被泄露的技术，包括多方安全计算、可信执行环境等，助力数据合规流通。\r', '同态加密允许直接对密文进行计算，结果解密后等同于对明文计算，是隐私保护的关键技术。\r', '零知识证明允许证明者向验证者证明某个论断正确，而不透露任何额外信息，广泛用于身份认证和区块链。\r', '数字签名用于验证消息的完整性和来源，利用私钥签名、公钥验证，是电子文档安全的基础。\r', '哈希函数将任意长度数据映射为固定长度摘要，具有单向性和抗碰撞性，用于密码存储和数据校验。\r', '梅克尔树是区块链中用于高效验证数据完整性的二叉树结构，叶子节点存储数据哈希，根节点代表整体。\r', '椭圆曲线密码学基于椭圆曲线上的离散对数问题，提供更短的密钥长度和同等安全性，用于加密和数字签名。\r', '后量子密码是设计抵抗量子计算机攻击的加密算法，包括基于格、哈希、编码等方案，保障未来安全。\r', '智能合约是自动执行的协议代码，部署在区块链上，满足条件时自动履约，用于去中心化应用（DApp）。\r', 'DAO是去中心化自治组织，通过区块链上的智能合约进行治理，成员投票决定事务，无中心化领导。\r', 'NFT是非同质化代币，代表唯一数字资产，如艺术品、收藏品，基于区块链确权，掀起数字收藏热潮。\r', '元宇宙是虚拟与现实融合的沉浸式数字世界，用户通过虚拟化身进行社交、娱乐和工作，前景广阔。\r', 'Web3是下一代互联网理念，强调去中心化、用户主权和隐私保护，基于区块链和分布式存储技术。\r', '去中心化是将权力和决策分散到网络节点，而非集中于中心机构，提高透明度与抗审查性。\r', '分布式存储将数据分散存储在多台独立设备上，提高可靠性和可用性，如IPFS和Filecoin网络。\r', 'IPFS是星际文件系统，一种点对点分布式存储协议，通过内容寻址实现高效、永久的文件共享和存储。\r', '秦始皇嬴政是中国首位皇帝，统一六国，推行郡县制、书同文、车同轨，建立中央集权国家。\r', '成吉思汗是蒙古帝国创始人，统一蒙古部落，建立强大骑兵，征服欧亚广大区域，改变世界历史。\r', '林肯是美国第16任总统，领导南北战争，颁布《解放黑奴宣言》，维护联邦统一，被尊为伟大领袖。\r', '华盛顿是美国首位总统，领导独立战争，主持制宪会议，确立总统制，被誉为“国父”。\r', '牛顿是英国物理学家，提出万有引力定律和运动三定律，发明微积分，奠定经典力学基础。\r', '爱因斯坦是伟大物理学家，创立相对论，提出光电效应理论，获诺贝尔奖，是现代物理学先驱。\r', '达尔文提出进化论，著《物种起源》，主张自然选择是物种演变的驱动，改变生物学和人类世界观。\r', '居里夫人是波兰裔科学家，研究放射性现象，发现钋和镭元素，两次获诺贝尔奖，首位女性得主。\r', '图灵是英国数学家，提出图灵机模型，破解Enigma密码，奠定计算机科学和人工智能基础。\r', '撒哈拉沙漠是世界最大热沙漠，面积约940万平方公里，气候极端，但有人类活动历史悠久。\r', '南极洲是地球最南端的冰冻大陆，平均气温最低，覆盖厚厚冰层，蕴藏丰富淡水和科研资源。\r', '北极是地球最北端，以海洋为主，常年浮冰，受气候变化影响显著，是研究全球变暖的重要区域。\r', '太平洋是地球最大、最深的大洋，面积约1.65亿平方公里，拥有马里亚纳海沟和众多岛国。\r', '大西洋是地球第二大洋，分隔欧洲、非洲与美洲，贸易航线密集，是历史殖民与贸易的重要通道。\r', '印度洋连接亚洲、非洲和澳大利亚，航运繁忙，拥有丰富的石油和渔业资源，季风气候明显。\r', '地中海是欧洲、非洲和亚洲之间的内陆海，面积约250万平方公里，孕育了古希腊罗马文明。\r', '红海是印度洋的狭长分支，位于非洲和阿拉伯半岛之间，以高盐度和独特珊瑚礁生态系统著称。\r', '黑海是欧洲与亚洲之间的内陆海，与地中海通过博斯普鲁斯海峡相连，深层水缺氧，生态独特。\r', '里海是世界上最大的内陆湖泊，位于欧洲与亚洲交界，富含石油和天然气，被称为“第二个波斯湾”。\r', '贝加尔湖是世界上最深、最古老的淡水湖，位于西伯利亚，储水量占全球淡水湖总量的22%，生态奇特。\r', '尼亚加拉瀑布位于美国与加拿大边界，由三大瀑布组成，水量巨大，是世界著名自然奇观和旅游胜地。\r', '天空呈现蓝色是由于瑞利散射，太阳光中的蓝光被大气分子散射到各个方向，因此肉眼看到蓝色天空。\r', '树叶变色是因为秋季叶绿素分解，胡萝卜素和花青素显现，导致叶片变黄或红，与光照和温度有关。\r', '记忆单词可采用间隔重复、词根词缀、联想记忆等方法，结合阅读和听写，能显著提高词汇量。\r', '提高专注力可通过减少干扰、设定明确目标、使用番茄工作法，并配合冥想锻炼注意肌力。\r', '写简历要突出亮点、量化成果、简洁清晰，针对岗位定制，避免语法错误，控制在一到两页。\r', '做PPT要逻辑清晰、图文结合、简洁大方，使用一致字体和配色，每页聚焦一个核心观点，避免文字堆砌。\r', '有效沟通需清晰表达、积极倾听、换位思考，避免歧义，注重非语言信号，及时反馈确认。\r', '谈判技巧包括准备充分、明确底线、善于提问、创造共赢方案，保持冷静和耐心，避免情绪化。\r', '公众演讲要内容有逻辑、开头吸引人、结尾有力量，配合恰当语调和肢体动作，克服紧张感。\r', '写作技巧包括明确主题、结构清晰、用词精准、多用具体例子，反复修改打磨，注重开头和结尾。\r', '阅读方法有泛读、精读、略读，使用SQ3R方法（浏览、提问、阅读、复述、复习）提升理解和记忆。\r', '速读训练扩大视幅、减少回视、避免默读，通过指读和节奏训练，能在不降低理解率的情况下提升速度。\r', '笔记方法如康奈尔笔记、思维导图、大纲法，帮助整理信息，便于复习，提高学习效率。\r', '思维导图以中心主题辐射分支，用关键词和图形表示关联，辅助发散思维和记忆，适合创意和规划。\r', '习惯养成遵循“提示-惯常行为-奖励”循环，从小目标开始，坚持21天以上，逐步固定为自动行为。\r', '自律是控制欲望、坚持计划的能力，可通过设定明确规则、自我奖励和反思增强，是成功的基石。\r', '情绪管理指识别、接纳和调节自身情绪，运用深呼吸、正念和重新评估方法，避免冲动反应。\r', '压力缓解可通过运动、深呼吸、倾诉、时间管理以及培养兴趣爱好，减少长期应激状态。\r', '冥想是训练注意力和觉察力的心理练习，通过专注呼吸或引导想象，减轻焦虑、提升专注力。\r', '正念是有意识、不评判地关注当下体验，能改善情绪调节和压力应对，广泛用于心理治疗。\r', '瑜伽源于古印度，结合体位、呼吸和冥想，改善柔韧性、力量和内心平静，适合各年龄段。\r', '有氧运动如跑步、游泳、骑自行车，提高心肺功能和代谢，增强体质，有助于控制体重。\r', '力量训练利用哑铃、器械或自重，增强肌肉力量和耐力，促进骨骼健康，提高基础代谢率。\r', '健康饮食要求均衡摄入碳水化合物、蛋白质、脂肪、维生素和矿物质，多食蔬果，少油少糖。\r', '睡眠周期包括非快速眼动和快速眼动阶段，每周期约90分钟，完整4-5周期利于深度恢复。\r', '生物钟是内在计时机制，调节睡眠-觉醒、体温和激素分泌，受光照和日常节律影响。\r', '维生素C是水溶性抗氧化剂，促进胶原蛋白合成，增强免疫力，富含于柑橘、猕猴桃和青椒。\r', '蛋白质由氨基酸组成，是组织修复和酶合成的原料，高质量蛋白来源于肉、蛋、豆制品。\r', '碳水化合物是主要供能物质，分为糖类、淀粉和纤维，优质来源为全谷物、薯类和杂豆。\r', '脂肪提供高能量，协助脂溶性维生素吸收，分饱和脂肪和不饱和脂肪，后者有益心血管健康。\r', '膳食纤维促进肠道蠕动，降低胆固醇，调控血糖，来源于蔬菜、水果和全谷物，每日推荐25克以上。\r', '益生菌是有益活菌，调节肠道菌群平衡，改善消化和免疫，常见于酸奶、泡菜等发酵食品。\r', '抗氧化剂清除自由基，减缓氧化损伤，保护细胞，包括维生素C、E、类胡萝卜素和多酚。\r', '防晒是使用防晒霜、衣物遮挡等方法减少紫外线伤害，防止晒伤、老化及皮肤癌，SPF30以上为宜。\r', '保湿是补充和锁住皮肤水分，使用含透明质酸、甘油等成分的产品，维持皮肤屏障健康。\r', '清洁护肤包括洁面、去角质和清洁面膜，去除污垢和多余油脂，但需避免过度清洁损伤屏障。\r', '化妆技巧包括底妆、眼妆、唇妆，根据脸型和肤色选择，注重自然过渡，提升整体气质。\r', '服装搭配考虑色彩、款式和场合，利用基础款和点缀，遵循简约、协调原则，突出个人风格。\r', '色彩理论包括三原色、互补色和冷暖色调，应用于艺术设计和日常搭配，影响视觉效果和情感传达。\r', '室内设计是规划空间布局和装饰，考虑功能、美学和人机工程，运用光线、材料和色彩创造舒适环境。\r', '园艺技巧包括土壤改良、浇水施肥、修剪病虫害防治，根据植物习性进行养护，享受种植乐趣。\r', '烹饪技巧涵盖刀工、火候、调味和烹法，如炒、蒸、烤、炖，掌握基础可变换无数菜肴。\r', '烘焙基础包括准确计量、掌握面温、发酵和烤制时间，常见产品为面包、蛋糕和饼干。\r', '咖啡拉花是在意式浓缩上倒入奶泡，形成心形、树叶等图案，需要熟练掌握浓缩萃取和奶泡打发。\r', '茶道源于中国，讲究泡茶技艺、品饮环境和精神修养，包含选水、温杯、投茶、注水、闻香、品饮等步骤。\r', '葡萄酒品鉴通过观色、闻香、品味评价酒的品质，注重品种、产地、年份和陈酿潜力。\r', '啤酒酿造以麦芽、水、啤酒花和酵母为原料，经糖化、煮沸、发酵和熟成，产生丰富风味。\r', '奶酪制作通过凝乳、排乳清、盐渍和熟化，不同工艺得到千百种奶酪，富含蛋白和钙。\r', '巧克力制作从可可豆发酵、烘焙、研磨、调温到成型，工艺讲究，最终获得丝滑口感和丰富香气。\r', '面包发酵利用酵母分解糖产生二氧化碳，使面团膨胀，发酵时间和温度影响面包体积和风味。\r', '面条种类繁多，如拉面、切面、挂面、意大利面等，不同面粉和工艺带来口感差异。\r', '米饭煮法涉及米水比例、浸泡时间和火候，电饭煲常见，也可用锅煮，注意焖饭阶段。\r', '汤品熬制需要慢火炖煮，充分释放食材鲜味，可加入骨头、蔬菜和香料，保证清澈或浓醇。\r', '沙拉搭配以生菜、蔬菜、水果、坚果和蛋白质为主，淋上油醋汁或蛋黄酱，清爽健康。\r', '寿司制作以醋饭为基础，搭配鱼生、虾、蛋等，手握或卷制，讲究米粒温度和食材新鲜度。\r', '刺身选购看色泽、弹性和气味，新鲜鱼生肉纹清晰，无异味，需冷藏保鲜，食用安全第一。\r', '烤肉技巧控制火候，不同部位烤制时间不同，适时翻面，锁住汁水，配以蘸料更美味。\r', '火锅底料分清汤和红油，由牛油、辣椒、花椒、香料等炒制，亦可加入菌菇或番茄调出特色。\r', '麻辣烫是简便的火锅形式，选食材烫煮，配以麻酱和辣椒油，味道浓郁，深受年轻人喜爱。\r', '串串香将食材串在竹签上，放入沸腾汤锅涮煮，蘸干碟或油碟，食用方便，适合多人聚餐。\r', '煎饼果子由杂粮面糊摊成薄饼，加鸡蛋、油条和酱料，口感香脆，是北方常见街头早餐。\r', '豆浆制作将黄豆浸泡磨碎，煮开后过滤，可加糖或蜂蜜，营养丰富，适合早餐搭配。\r', '豆腐可煎、炸、炖、煮、凉拌，如麻婆豆腐、红烧豆腐、皮蛋豆腐，是优质植物蛋白来源。\r', '鸡蛋可煮、炒、蒸、煎，如白煮蛋、炒蛋、蒸蛋羹、太阳蛋，简单快捷，营养全面。\r', '土豆可做酸辣土豆丝、土豆泥、薯条、土豆炖牛肉，做法多样，富含淀粉和维生素C。\r', '西红柿炒蛋是家常菜，将番茄与鸡蛋同炒，酸甜可口，制作简单，营养均衡，适合新手。\r', '鱼香肉丝用猪肉、木耳、胡萝卜配以鱼香汁，酸甜辣味融合，虽无鱼却得名，下饭首选。\r', '宫保鸡丁以鸡丁、花生、干辣椒爆炒，甜辣酥香，源于川菜，名扬中外，常见于中餐厅。\r', '麻婆豆腐以豆腐配牛肉末，用豆瓣酱、花椒粉调味，麻辣鲜香，口感嫩滑，是川菜代表作。\r', '回锅肉将煮熟的猪五花肉切片回锅煸炒，加青椒、蒜苗和豆豉，肥而不腻，浓香四溢。\r', '水煮鱼用草鱼片加豆芽、辣椒，淋热油激发香气，鱼肉鲜嫩，麻辣过瘾，属川菜经典。\r', '小龙虾学名克氏原螯虾，肉质鲜嫩，常以十三香、蒜蓉或麻辣烹制，夏季夜宵热门美食。\r', '大闸蟹是中华绒螯蟹，秋季膏满黄肥，清蒸最能提鲜，配姜醋食用，自古为江南珍味。\r', '生蚝可生食、清蒸、蒜蓉烤或芝士焗，鲜美多汁，富含锌，但需确保新鲜卫生。\r', '扇贝可蒸、煎、炒，常见蒜蓉粉丝蒸扇贝，肉质细嫩，搭配香蒜和酱油，鲜甜可口。\r', '海参需冷水泡发，去沙嘴，水煮后焖至软糯，耗时较长，泡发后可用于煲汤或红烧。\r', '燕窝是金丝燕唾液筑成的巢，用纯净水泡发后隔水炖，加入冰糖或牛奶，滋润滑润。\r', '人参可切片含服、泡水、炖鸡，有补气提神之效，但需注意体质和用量，避免上火。\r', '灵芝含多糖和三萜，增强免疫力、调节代谢，常磨粉冲服或切片煲汤，但不宜过量。\r', '枸杞富含胡萝卜素和维生素，泡水饮用益精明目，可搭配菊花或红枣，每日适量即可。\r', '菊花茶清肝明目，疏散风热，用干菊花沸水冲泡，可加冰糖，适合用眼过多人群。\r', '绿茶冲泡水温宜80-85℃，注水后稍候片刻，香气清幽，不要闷泡过久以免苦涩。\r', '红茶品鉴看汤色红亮，闻果香或蜜香，入口醇厚，加奶调饮更具风味，代表有祁红和正山小种。\r', '乌龙茶半发酵，兼具绿茶清香和红茶醇厚，冲泡用沸水，多次出汤，岩茶和铁观音为代表。\r', '普洱茶分生普和熟普，陈化后口感顺滑，有陈香，冲泡需洗茶，适合长期存藏。\r', '咖啡豆按烘焙度分浅、中、深，浅烘焙酸感明显，深烘焙苦味浓郁，选豆需考虑产地和处理法。\r', '意式浓缩是高温高压萃取的咖啡，量少味浓，为花式咖啡基底，油脂丰富，需专业咖啡机。\r', '美式咖啡由浓缩兑水制成，口味相对清淡，可加糖或奶，适合不喜浓烈口感者。\r', '拿铁艺术是在拿铁表面做拉花或雕花，展现奶泡与浓缩的融合，提升视觉和饮用体验。\r', '卡布奇诺由浓缩、蒸汽奶和奶泡各占三分之一，口感绵密，撒上肉桂粉或可可粉更添风味。\r', '摩卡咖啡加入巧克力酱，融合浓缩和奶泡，甜苦交织，风味浓郁，适合巧克力爱好者。\r', '焦糖玛奇朵以浓缩、奶泡和香草糖浆为底，淋上焦糖酱，甜香顺滑，层次丰富。\r', '冷萃咖啡用冷水长时间浸泡咖啡粉，低温萃取减少酸苦，口感清爽，适合夏日饮用。\r', '氮气咖啡在冷萃中充入氮气，产生细密泡沫，口感如奶油般顺滑，常见于精品咖啡馆。\r', '抹茶是碾磨成粉的绿茶，用茶筅打泡后饮用，颜色翠绿，富含茶多酚，日本茶道常用。\r', '可可粉可用于冲调热可可、烘焙蛋糕或撒在甜品上，富含黄烷醇，具有抗氧化作用。\r', '热巧克力由可可粉或巧克力片与牛奶加热混合，可加棉花糖或鲜奶油，温暖舒心。\r', '冰淇淋以牛奶、奶油、糖和稳定剂为料，经搅拌冷冻，口味多变，需控制冰晶形成。\r', '刨冰将冰块刨成细碎，淋上糖浆、水果和豆沙，清凉解暑，是夏季街头常见甜品。\r', '水果拼盘将多种水果切块摆放，注意色彩搭配和口味对比，可蘸酸奶或蜂蜜，健康美味。\r', '果汁搭配考虑酸甜平衡，如橙加胡萝卜、苹果加雪梨，可混合蔬菜，增加维生素摄取。\r', '奶昔由冰淇淋和牛奶搅打，添加水果或巧克力酱，浓稠顺滑，可作饮品或甜点。\r', '酸奶发酵利用乳酸菌将牛奶乳糖转化为乳酸，控制温度42℃左右，发酵8-12小时凝固。\r', '奶酪蛋糕以奶油奶酪、鸡蛋和糖等烘烤或冷藏制作，质地细腻，分重芝士和轻芝士两种。\r', '提拉米苏以手指饼干蘸咖啡，铺马斯卡彭奶酪糊，撒可可粉，层层叠加，意式经典甜点。\r', '马卡龙是法式蛋白霜夹心饼干，表面光滑，裙边明显，夹馅多样，色彩缤纷，制作难度高。\r', '可颂面包是法式酥皮面包，裹入黄油多次折叠，烤后外酥内软，呈弯月形，早餐常见。\r', '法棍是长条硬面包，外皮焦脆，内部柔软有气孔，配料仅面粉、水、盐和酵母，法国标志食品。\r', '意大利面种类繁多，有细面、宽面、螺旋面等，配以番茄酱、肉酱或奶油酱，煮至弹牙口感。\r', '披萨饼底由高筋面粉和酵母发酵，手拍成圆形，铺料后高温烤制，薄底和厚底各有风味。\r', '千层面以多层面皮叠加肉酱、白酱和奶酪，烤至起泡，口感层次丰富，是意式经典。\r', '焗饭将米饭与配料混合，铺上奶酪放入烤箱烤至金黄，香气浓郁，省去单独炒菜。\r', '炒饭用隔夜米饭搭配鸡蛋、蔬菜和肉类，大火快炒，粒粒分明，可演化出扬州炒饭等多种款式。\r', '盖浇饭将炒好的菜肴浇在米饭上，汁液渗透饭粒，省时美味，常见鱼香肉丝盖饭等。\r', '煲仔饭用砂锅煮米，中途铺上腊味或肉饼，小火慢煲，锅底形成香脆锅巴，风味独特。\r', '砂锅粥用生米熬煮，加入海鲜或肉类，慢火熬至绵稠，鲜甜暖胃，适合早餐或夜宵。\r', '海鲜粥加入虾、蟹、贝类等，与米同煮，鲜味入粥，搭配姜丝和葱花，去腥增香。\r', '皮蛋瘦肉粥以皮蛋、瘦肉丝和米熬制，咸鲜滑嫩，加入葱花和香油，家常养胃。\r', '八宝粥用糯米、红豆、花生、桂圆等八种食材熬成甜粥，营养丰富，寓意吉祥。\r', '绿豆汤清热解毒，将绿豆加水煮至开花，可加冰糖，冷藏后饮用，夏季消暑佳品。\r', '红豆沙将红豆煮烂，磨细加糖炒干，用作馅料或冲调甜品，细腻香甜。\r', '莲子羹以莲子、银耳、冰糖熬煮，胶质丰富，润肺养颜，可配枸杞和百合。\r', '银耳汤含天然胶质，与红枣、莲子同炖，滋阴润燥，口感软糯，四季皆宜。\r', '木瓜炖奶将木瓜挖空，填入牛奶和冰糖，隔水炖煮，甜美滋润，有美容养颜之效。\r', '椰汁西米露以西米煮熟过凉，加入椰汁和糖水，可配水果或芋头，清凉滑爽。\r', '杨枝甘露由芒果、西柚、椰奶和西米制成，酸甜清香，是港式经典甜品。\r', '布丁以鸡蛋、牛奶和糖蒸或烤制，焦糖打底，口感嫩滑，常见于西式甜点。\r', '果冻用果汁或茶汤加吉利丁凝固，可加入水果块，清凉Q弹，自制卫生。\r', '棉花糖将糖加热融化，离心甩出细丝缠绕成球，轻盈甜软，常现于游乐园。\r', '爆米花利用玉米加热膨胀，可甜可咸，是看电影时的经典零食。\r', '薯片将土豆切片油炸或烘烤，调味后酥脆香咸，但热量较高，建议适量。\r', '炸鸡用腌渍鸡肉裹粉油炸，外酥里嫩，可配酱料，风靡全球的快餐食品。\r', '烤鸭以北京烤鸭最著名，皮脆肉嫩，用薄饼卷甜面酱、葱丝和黄瓜条，风味一绝。\r', '烧鹅是粤式名菜，鹅腹填充香料后烤制，皮脆油亮，肉质醇厚，佐酸梅酱解腻。\r', '叉烧是粤菜烧味，选梅花肉腌制后挂炉烧烤，甜咸适口，可做盖饭或配面。\r', '卤味将食材放入香料卤水中慢煮，入味透彻，如卤鸡爪、卤蛋、卤豆腐，下酒佳品。\r', '酱牛肉用牛腱子肉加酱油、香料炖煮，冷却切片，筋纹美观，肉质紧实，冷盘常见。\r', '驴肉火烧是河北小吃，将卤驴肉剁碎夹入酥脆火烧中，肉香饼酥，别具风味。\r', '羊肉串以羊肉块穿串，撒孜然和辣椒面烤制，焦香四溢，街头夜市必备。\r', '烤羊排以整块羊排腌制后炭烤或烤箱烘烤，外焦里嫩，配以迷迭香或薄荷酱。\r', '牛排按部位分西冷、菲力、肋眼，煎烤至三至七成熟，搭配黑胡椒汁，肉质多汁。\r', '猪排通常取大里脊，锤松后煎或炸，配洋葱酱或咖喱，日式炸猪排最为知名。\r', '鸡排将鸡胸肉拍扁裹粉油炸，可撒椒盐或淋酱，是快餐店常见的主食。\r', '鱼排常用无刺鱼肉裹面包糠油炸，搭配塔塔酱，外酥内嫩，适合儿童食用。\r', '虾滑将虾仁剁碎加淀粉搅拌，挤成丸状煮汤或火锅，口感Q弹，鲜味十足。\r', '蟹棒是用鱼糜制成的人造蟹肉，常用于火锅、寿司或炒菜，颜色橘红，味甜。\r', '鱼丸用鱼肉打浆，挤成圆形水煮或油炸，可做汤或火锅，鱼香浓郁。\r', '牛肉丸以牛肉捶打成泥，加盐和淀粉，弹牙爽口，潮汕牛肉丸尤为著名。\r', '猪肉丸将肥瘦猪肉剁碎调馅，可油炸、红烧或煮汤，家常菜中常见。\r', '素鸡是豆制品，以千张捆扎调味，口感类似鸡肉，适合素食者，可卤可炒。\r', '腐竹是豆浆表面结皮挑出晾干，富含蛋白，可泡发后凉拌、炒菜或煲汤。\r', '千张是薄豆皮，可卷菜或切条炒制，也可做千张包，是常见豆制品。\r', '豆腐皮与千张类似，但更薄，常用于包裹馅料，或切丝做凉拌菜。\r', '油条是面粉发酵后拉长油炸，中空酥脆，常配豆浆食用，是传统早餐。\r', '烧饼是面团加油酥烤制，有芝麻，分咸甜口味，外酥内软，可夹肉食用。\r', '馒头是小麦粉发酵蒸制的主食，松软白净，可配菜或夹肉，北方常见。\r', '花卷将面团擀片涂油撒盐或葱，卷起切段蒸制，层次分明，咸香可口。\r', '包子是带馅的发面蒸品，馅料有肉、菜、豆沙等，皮薄馅大，早餐热门。\r', '饺子用皮包馅，可水煮、蒸或煎，馅料多样，蘸醋蒜汁，是节日传统美食。\r', '馄饨皮薄馅小，包法讲究，汤底加紫菜、虾皮和葱花，鲜香暖胃。\r', '汤圆用糯米粉包裹甜馅或咸馅，水煮浮起，软糯香甜，象征团圆。\r', '元宵是摇制出来的，馅料切成块在糯米粉中反复滚动，外皮松软，节日食品。\r', '粽子用竹叶包裹糯米和馅料（红枣、肉、蛋黄），蒸煮而成，端午传统。\r', '月饼有广式、苏式等，外皮酥软，馅料多样（莲蓉、五仁、豆沙），中秋节食品。\r', '青团用艾草汁拌糯米粉，包豆沙或芝麻馅，蒸后呈青色，江南清明时令点心。\r', '粢饭团以糯米饭包裹油条、榨菜和肉松，捏紧食用，上海传统早餐。\r', '饭团是日式便利食品，用米饭包裹鱼肉或梅子，外裹海苔，便携可口。\r', '紫菜包饭是韩式卷饭，米饭铺在紫菜上，放黄瓜、胡萝卜、鸡蛋条等，卷切食用。\r', '寿司卷是日式料理，醋饭与鱼生、蔬菜用海苔卷紧，切段蘸酱油和芥末。\r', '手卷是锥形海苔包裹醋饭和配料，手持食用，爽脆方便。\r', '军舰寿司用海苔围住醋饭，顶部放鱼籽或蟹肉，形状似军舰。\r', '散寿司是将醋饭盛入碗中，铺上多种鱼生和蛋丝，混合食用，家常风味。\r', '刺身拼盘将多种新鲜鱼生切片排列，配萝卜丝和紫苏，蘸酱油和wasabi，品尝原味。\r', '烤鱼将整鱼腌制后烤制，可加孜然或味噌，皮脆肉嫩，日式和中式做法各异。\r', '蒸鱼以清蒸为主，放姜丝和葱，淋热油和酱油，保留鱼肉鲜甜，营养丰富。\r', '红烧鱼先煎后烧，加酱油、糖和料酒，汤汁浓稠，入味深厚，家常菜常见。\r', '糖醋鱼将鱼炸至酥脆，浇上糖醋汁，酸甜开胃，色泽红亮，宴席常见。\r', '松鼠鱼是苏菜，鱼切花刀炸出形似松鼠，浇番茄酸甜汁，外酥里嫩，造型美观。', '人工智能算法是让计算机模拟人类智能的数学方法，包括搜索、推理、学习和优化等，广泛应用于语音助手、图像识别和自动驾驶等领域。  \r', '机器学习模型是从数据中学习规律并做出预测的数学结构，如线性回归、决策树和神经网络，训练后可用于分类、回归和聚类任务。  \r', '深度学习框架是用于构建和训练神经网络的软件库，如TensorFlow和PyTorch，提供自动微分、GPU加速和预训练模型，简化开发流程。  \r', '自然语言处理应用让计算机理解、生成和翻译人类语言，典型场景包括智能客服、机器翻译、情感分析和文本摘要，大幅提升人机交互效率。  \r', '计算机视觉技术使计算机从图像或视频中提取信息，实现物体检测、人脸识别和图像分割，是自动驾驶和安防监控的核心支撑。  \r', '语音识别系统将人类语音转换为文字，基于声学模型和语言模型，用于智能音箱、语音输入和实时字幕，准确率已接近人类水平。  \r', '推荐系统根据用户历史行为和相似人群偏好，自动推荐商品、视频或新闻，常用协同过滤和基于内容的算法，提升用户粘性和满意度。  \r', '搜索引擎优化是通过调整网站结构和内容，提高在搜索结果中的排名，包括关键词研究、外链建设和页面速度优化，增加自然流量。  \r', '数据挖掘方法从海量数据中提取隐含模式和知识，包括分类、聚类、关联规则和异常检测，广泛应用于市场营销和金融风控。  \r', '大数据分析平台整合分布式存储和计算引擎（如Hadoop、Spark），支持海量数据的采集、清洗、分析和可视化，助力企业数据驱动决策。  \r', '云计算架构包括基础设施即服务（IaaS）、平台即服务（PaaS）和软件即服务（SaaS），通过虚拟化技术提供弹性、按需的计算资源。  \r', '边缘计算节点部署在网络边缘（如路由器、基站），就近处理数据，减少延迟和带宽消耗，适合实时性要求高的场景，如工业自动化和智慧交通。  \r', '雾计算层介于云端和设备之间，提供计算、存储和网络服务，扩展边缘计算能力，适用于物联网场景中的分布式数据处理和分析。  \r', '无服务器计算让开发者无需管理服务器，代码按需运行并自动扩缩容，按执行时间计费，降低运维成本，适合事件驱动型应用。  \r', '微服务架构将单体应用拆分为一组小型、独立的服务，每个服务围绕业务能力构建，可独立部署和扩展，提高开发敏捷性和容错性。  \r', '容器编排工具（如Kubernetes）自动化管理容器的部署、扩展和网络通信，支持服务发现和负载均衡，简化大规模容器集群的运维。  \r', '持续集成流程要求开发者频繁地将代码合并到主干，并通过自动化构建和测试快速发现错误，保证代码质量，缩短交付周期。  \r', '持续交付管道在持续集成基础上，自动化将经过测试的代码部署到生产环境，确保软件可随时发布，加速价值交付。  \r', '敏捷开发方法强调迭代、协作和快速响应变化，通过Scrum或Kanban框架管理需求，频繁交付可用软件，提升团队效率。  \r', '测试驱动开发先编写测试用例，再编写代码使测试通过，然后重构，保证代码覆盖率和质量，减少缺陷，提高可维护性。  \r', '代码重构技巧是在不改变外部行为的前提下优化内部结构，如提取函数、重命名变量和消除重复，提升代码可读性和扩展性。  \r', '设计模式是解决常见软件设计问题的经典方案，分为创建型（如工厂模式）、结构型（如适配器）和行为型（如观察者），提高代码复用性。  \r', '算法复杂度分析用大O符号评估时间（如O(n)）和空间（如O(1)）随输入规模的变化，帮助选择最优算法，避免性能瓶颈。  \r', '数据结构是组织和存储数据的方式，包括数组、链表、栈、队列、树和图，选择合适的数据结构可显著提升算法效率。  \r', '数据库索引通过B树或哈希等结构加速数据检索，类似书的目录，但会增加写入开销，需合理设计以平衡查询和更新性能。  \r', '事务隔离级别定义并发事务间的可见性，包括读未提交、读已提交、可重复读和串行化，权衡一致性与并发性能。  \r', '分布式事务处理协调跨多个服务或数据库的操作，保证ACID特性，常用两阶段提交或基于消息的最终一致性方案。  \r', '一致性哈希算法将节点和数据映射到环上，用于分布式缓存和负载均衡，增减节点时只影响少量数据迁移，提高扩展性。  \r', '负载均衡策略将请求分发到多个服务器，如轮询、最少连接和一致性哈希，提高系统吞吐量和可用性，防止单点过载。  \r', '缓存更新策略包括Cache-Aside、Write-Through和Write-Behind，决定何时读写缓存和数据库，优化读取性能并保持数据一致。  \r', '消息队列实现系统间的异步通信，解耦生产者和消费者，支持削峰填谷和可靠传输，常用RabbitMQ和Kafka。  \r', '流式处理框架（如Apache Flink）实时处理无界数据流，支持窗口计算和状态管理，用于实时监控、交易分析和事件响应。  \r', '批处理作业调度定时执行大规模数据处理任务，如Hadoop MapReduce，用于数据清洗、报表生成和离线分析，提高资源利用率。  \r', '数据仓库建模采用星型或雪花型模式，将事实表和维度表关联，支持多维分析和OLAP查询，是企业决策支持的基础。  \r', '数据湖以原始格式存储海量结构化和非结构化数据，无需预处理，支持灵活分析和机器学习，通常基于云对象存储。  \r', 'ETL流程设计涵盖抽取（Extract）、转换（Transform）和加载（Load），从源系统抽取数据，清洗、标准化后存入目标库，保证数据质量。  \r', '商业智能工具（如Tableau、Power BI）通过仪表盘和报表可视化数据，支持交互式探索和KPI监控，帮助业务人员洞察趋势。  \r', '数据可视化库（如D3.js、ECharts）提供丰富的图表组件和交互能力，将数据转化为图形，辅助理解和沟通。  \r', '机器学习流水线自动化数据预处理、特征工程、模型训练和评估，实现端到端的实验跟踪和模型部署，提高迭代效率。  \r', '超参数调优方法（如网格搜索、随机搜索和贝叶斯优化）寻找模型最佳参数组合，提升性能，减少人工试错成本。  \r', '交叉验证技术将训练集划分为多份，轮流用一份验证，其余训练，平均评估模型泛化能力，避免过拟合。  \r', '特征选择策略过滤无关或冗余特征，常用方法有卡方检验、互信息和递归特征消除，降低维度，提高模型可解释性和效率。  \r', '维度约简算法如主成分分析和t-SNE，将高维数据映射到低维空间，保留重要信息，便于可视化和加速计算。  \r', '集成学习组合多个基学习器，通过投票或加权提高准确率，代表方法有随机森林（Bagging）和梯度提升（Boosting），减少过拟合。  \r', '梯度提升机是串行集成方法，逐步添加新树拟合残差，优化损失函数，如XGBoost和LightGBM，在表格数据中表现优异。  \r', '支持向量机通过寻找最大间隔超平面进行分类，配合核函数处理非线性问题，适用于中小规模数据集的分类和回归。  \r', '朴素贝叶斯分类基于贝叶斯定理和特征独立假设，计算简单高效，常用于文本分类和垃圾邮件过滤，但独立性假设有时不成立。  \r', 'K近邻算法根据样本的K个最近邻居的类别进行投票预测，无需训练过程，但计算距离成本高，适合小样本和多分类任务。  \r', '聚类分析将数据自动分组，使组内相似度大、组间差异大，常用K-Means、DBSCAN和层次聚类，用于客户分群和图像分割。  \r', '关联规则挖掘发现项集间的频繁模式，如“购买面包的人常买牛奶”，Apriori算法是其经典实现，用于购物篮分析。  \r', '异常检测技术识别数据中的罕见或异常模式，常用统计方法、孤立森林和自编码器，应用于金融欺诈检测和设备故障预警。  \r', '时间序列预测基于历史数据对未来值进行估计，常用ARIMA、Prophet和LSTM，用于股票预测、销量规划和天气预测。  \r', '强化学习算法通过智能体与环境交互，根据奖励信号学习最优策略，经典算法有Q-learning和策略梯度，在游戏和机器人控制中成功。  \r', '深度Q网络结合深度神经网络与Q-learning，处理高维状态输入，如玩雅达利游戏，通过经验回放提升训练稳定性。  \r', '策略梯度方法直接优化策略网络参数，适用于连续动作空间，如PPO和TRPO，在机器人和自主导航中表现突出。  \r', '生成对抗网络变体（如DCGAN、StyleGAN）通过生成器和判别器对抗训练，生成逼真的图像、音频和文本，推动创意内容生成。  \r', '变分自编码器是一种生成模型，学习数据的潜在分布，可生成新样本，也用于特征学习和异常检测，具有可解释性。  \r', '图神经网络处理图结构数据，通过节点信息传播和聚合，用于分子预测、社交网络分析和推荐系统，如GCN和GAT。  \r', '注意力机制让模型动态聚焦输入的重要部分，增强关键信息权重，广泛应用于机器翻译和图像描述，提升长程依赖性。  \r', 'Transformer模型基于自注意力机制，摒弃循环结构，并行计算高效，是BERT和GPT的基础，主导自然语言处理领域。  \r', 'BERT通过掩码语言模型和下一句预测进行预训练，学习深层次语言表示，微调后可应用于问答、文本分类等下游任务。  \r', 'GPT（生成式预训练变换器）采用自回归生成方式，通过大规模无监督预训练和少量微调，能生成连贯文本、代码和对话。  \r', '迁移学习将源任务知识迁移到目标任务，减少数据需求，常用预训练模型微调，在计算机视觉和NLP中效果显著。  \r', '元学习（学习如何学习）让模型通过少量样本快速适应新任务，常用MAML算法，适用于小样本学习场景。  \r', '联邦学习在保护数据隐私的前提下，多设备协同训练全局模型，更新只传输梯度，适用于医疗和金融敏感领域。  \r', '隐私计算技术确保数据处理过程中不泄露原始数据，包括多方安全计算、可信执行环境等，促进数据合规流通。  \r', '同态加密允许对密文直接计算，结果解密后与明文计算一致，保护隐私，可用于外包数据分析和机器学习。  \r', '零知识证明让证明者在不透露信息内容下，向验证者证明陈述为真，用于身份认证和区块链隐私保护。  \r', '数字签名标准（如ECDSA）用私钥签名、公钥验证，确保消息完整性和来源可靠性，是电子商务和软件分发的安全基石。  \r', '哈希函数将任意输入映射为固定长度输出，具有单向性和抗碰撞性，用于密码存储、数据完整性校验和区块链。  \r', '区块链共识机制（如PoW、PoS）让网络中所有节点对交易顺序达成一致，确保账本一致性和不可篡改。  \r', '智能合约语言（如Solidity）编写在区块链上自动执行的程序，条件触发时自动履约，支撑去中心化金融和NFT。  \r', '去中心化应用（DApp）运行在区块链上，前端与智能合约交互，不受中心机构控制，实现用户主权和透明性。  \r', '分布式存储系统将数据分散存储在多个节点上，提供高可靠性和可用性，如Ceph和HDFS，适用于海量数据。  \r', '星际文件系统（IPFS）是点对点分布式协议，通过内容寻址存储和共享文件，实现永久、去中心化的网络。  \r', '内容寻址网络基于内容唯一标识（如哈希）定位数据，而非位置，提高效率和安全性，常用于分布式存储。  \r', '点对点通信协议允许节点直接交换数据，无需中心服务器，如BitTorrent和libp2p，增强网络抗审查性。  \r', '网络安全防火墙监控网络流量，阻止恶意访问，分为网络层和应用层，是抵御网络攻击的第一道防线。  \r', '入侵检测系统通过分析流量或日志，识别可疑行为并告警，有基于签名和基于异常的检测方法，保护网络资产。  \r', '病毒防护策略包括定期扫描、实时监控和更新病毒库，结合行为分析，防止恶意软件感染和数据泄露。  \r', '漏洞扫描工具自动化检测系统、应用或网络中的已知弱点，如Nessus，生成修复建议，提升安全基线。  \r', '渗透测试模拟攻击者手法，评估系统防护能力，包括信息收集、漏洞利用和后期维持，帮助发现潜在风险。  \r', '社会工程防范训练员工识别钓鱼邮件、假冒电话等欺骗手段，建立上报流程，减少人为安全漏洞。  \r', '数据加密标准如AES，使用对称密钥对数据进行加密，速度快、强度高，广泛用于文件加密和VPN通信。  \r', '公钥基础设施（PKI）管理数字证书和公私钥对，提供身份认证、数据加密和签名服务，保障网络安全。  \r', '证书管理流程包括生成、签发、续期和撤销数字证书，确保证书生命周期内的可信性和有效性。  \r', '单点登录协议（如SAML、OIDC）让用户一次登录即可访问多个系统，提升体验和安全性，减少密码疲劳。  \r', '多因素认证结合密码、手机验证码和生物特征等至少两种因素，显著增强账户安全性，防御密码泄露。  \r', '生物识别传感器采集指纹、人脸、虹膜等生物特征，用于身份验证，具有唯一性和方便性，广泛用于手机解锁。  \r', '人脸识别算法检测面部关键点，提取特征并与数据库比对，应用于安防、支付和考勤，但需注意隐私问题。  \r', '指纹识别通过分析指纹脊线端点、分叉等细节，用于身份鉴别，已集成到大多数智能手机和门禁系统中。  \r', '虹膜扫描系统使用近红外光源捕捉眼球虹膜纹理，极难伪造，准确率高，常用于机场和高端安全场景。  \r', '语音生物特征利用声学特征（如音调、节奏）识别说话人，应用于语音助手和电话银行，但可能受环境噪声影响。  \r', '行为分析模型通过分析用户操作习惯（如击键、鼠标轨迹）建立基线，检测异常行为，用于持续身份验证。  \r', '风险评估框架（如NIST SP 800-30）系统识别、分析和评价资产威胁，制定相应的安全控制措施，降低风险至可接受水平。  \r', '灾难恢复计划定义系统中断后的恢复步骤、优先级和恢复时间目标，确保业务在灾害后尽快恢复运行。  \r', '业务连续性策略通过冗余架构、备用资源和应急预案，确保关键业务在灾难或故障时持续运作，减少损失。  \r', '服务等级协议（SLA）是服务提供商与客户之间的契约，明确性能指标（如响应时间、可用性），确保服务质量。  \r', '资源监控工具（如Prometheus）实时采集服务器、网络和应用性能数据，设置告警阈值，辅助运维决策。  \r', '日志分析平台聚合、索引和搜索系统日志（如ELK Stack），帮助排查故障、安全审计和性能调优。  \r', '性能优化技巧包括数据库查询优化、缓存策略、代码剖析和资源压缩，减少响应时间，提高系统吞吐量。  \r', '内存管理机制负责分配和回收内存，包括虚拟内存、垃圾回收和内存池，防止内存泄漏和碎片，提升程序效率。  \r', '垃圾回收算法自动识别并释放不再使用的对象，常用标记-清除、复制和分代收集，减轻开发者内存管理负担。  \r', '并发控制方法（如锁、信号量和乐观并发）协调多线程/进程对共享资源的访问，防止数据竞争和不一致。  \r', '死锁检测处理利用资源分配图或超时机制识别死锁，并通过抢占或回滚恢复，保证系统不永久阻塞。  \r', '进程调度策略（如轮转、优先级和多级队列）决定CPU分配顺序，平衡响应时间和吞吐量，优化资源利用率。  \r', '虚拟化技术将物理资源抽象为逻辑资源，允许多个虚拟机共享硬件，提高资源利用率和隔离性，是云计算基石。  \r', '硬件虚拟化辅助（如Intel VT-x）提供CPU和内存虚拟化支持，减少软件开销，提升虚拟机的性能和安全性。  \r', '操作系统内核结构管理进程、内存和设备驱动，有宏内核、微内核和混合内核之分，决定系统稳定性和可扩展性。  \r', '文件系统类型（如ext4、NTFS、APFS）组织存储设备上的数据，支持文件创建、读写和权限管理，影响性能。  \r', '存储区域网络（SAN）通过高速光纤网络连接服务器和存储设备，提供块级存储，适合数据库和高I/O应用。  \r', '网络附加存储（NAS）通过标准协议（如NFS、SMB）提供文件级存储，易于共享和管理，适合家庭和小型企业。  \r', '软件定义网络（SDN）将控制平面与数据平面分离，集中管理网络策略，提高灵活性和自动化水平。  \r', '网络功能虚拟化（NFV）将防火墙、路由器等网络功能软件化，运行在通用硬件上，降低部署成本。  \r', '5G核心网采用服务化架构（SBA），实现控制与承载分离，支持网络切片和边缘计算，满足低延迟大带宽需求。  \r', '6G潜在技术包括太赫兹通信、智能超表面和AI原生网络，目标速率可达1Tbps，预计2030年商用。  \r', '卫星互联网星座（如Starlink）通过低轨卫星群提供全球宽带覆盖，解决偏远地区通信难题。  \r', '物联网通信协议（如MQTT、CoAP）轻量、低功耗，适用于传感器和设备数据交换，支持发布/订阅模式。  \r', '低功耗广域网（LPWAN）如LoRa和NB-IoT，提供远距离、低速率通信，适用于智能电表和资产追踪。  \r', '无线传感器网络由大量传感器节点组成，协同感知环境数据（温度、湿度），应用于农业和环境监测。  \r', '射频识别技术通过无线电波识别电子标签，无需接触，用于物流追踪、门禁和电子支付。  \r', '近场通信（NFC）支持短距离（≤10cm）数据交换，常见于手机支付、门禁卡和配对连接。  \r', '蓝牙低能耗（BLE）是针对小数据量、低功耗设计的无线标准，广泛应用于智能手环、蓝牙耳机和智能家居。  \r', 'Wi-Fi标准从802.11a/b/g到Wi-Fi 6/7，速度不断提升，支持更多设备并发，降低延迟，增强稳定性。  \r', '网格网络拓扑中每个节点与其他节点连接，具有自愈能力，适用于分布式无线网络。  \r', '自组织网络无需预置基础设施，节点动态组建网络，适用于军事和应急通信。  \r', '蜂窝通信将区域划分为六边形小区，使用不同频率避免干扰，通过基站切换实现移动通信覆盖。  \r', '多输入多输出天线（MIMO）使用多根天线同时收发，提升数据速率和可靠性，是4G/5G关键技术。  \r', '波束成形技术将信号定向集中到特定方向，增强信号强度和覆盖，减少干扰，用于毫米波通信。  \r', '毫米波通信利用30-300GHz频段，提供巨大带宽，适合高速小范围应用，但受遮挡影响较大。  \r', '太赫兹频段（0.1-10THz）用于超高速无线传输和成像安检，尚在实验阶段，潜力巨大。  \r', '量子密钥分发利用量子态传输密钥，窃听必然改变状态，实现无条件安全通信。  \r', '量子纠错编码通过冗余量子比特检测和纠正错误，克服退相干，是实现大规模量子计算的基础。  \r', '量子计算模型包括电路模型、绝热计算和拓扑计算，利用量子叠加和纠缠加速特定问题求解。  \r', '超导量子比特是最主流的量子比特实现，使用超导电路制造，操作速度快，但需极低温环境。  \r', '离子阱量子计算机利用电场囚禁离子作为量子比特，相干时间长，精度高，但扩展较困难。  \r', '拓扑量子计算基于马约拉纳零模，具有内在容错性，稳定性高，是量子计算的发展方向之一。  \r', '半导体制造工艺包括光刻、刻蚀、沉积和掺杂，在晶圆上制造晶体管，制程越小性能越高。  \r', '光刻技术利用紫外光通过掩模将电路图案投射到硅片光刻胶上，是芯片制造最核心的工序。  \r', '芯片封装将裸片包裹保护并提供引脚，测试功能可靠性，分多种形式（如BGA、QFP），影响最终性能。  \r', '系统级芯片（SoC）将CPU、GPU、内存和I/O集成单芯片，用于手机和嵌入式设备，省电高效。  \r', '现场可编程门阵列（FPGA）可灵活配置逻辑电路，适合原型验证和实时信号处理，并行能力强。  \r', '专用集成电路（ASIC）为特定应用设计，如比特币矿机，性能功耗比极高，但开发成本大。  \r', '神经网络加速器（如NPU）专为深度学习优化，支持矩阵乘法和激活函数，大幅提高AI推理速度。  \r', '图形处理单元（GPU）拥有大量核心并行处理图形和计算任务，用于游戏渲染和AI训练。  \r', '张量处理单元（TPU）由谷歌开发，专为TensorFlow优化，高效执行矩阵运算，加速神经网络训练。  \r', '边缘AI芯片在设备端运行AI模型，低功耗低延迟，用于智能摄像头、手机和可穿戴设备。  \r', '生物芯片技术结合微电子和生物检测，用于基因测序和疾病诊断，灵敏度高，加速个性化医疗。  \r', '神经形态计算模仿人脑神经元和突触结构，使用脉冲信号，极低功耗，适应类脑智能应用。  \r', '类脑计算系统基于神经形态硬件，模拟大规模神经网络，用于模式识别和自适应控制，前景广阔。', 'Python是一种高级解释型编程语言，以简洁易读的语法著称，广泛应用于数据科学、人工智能、Web开发和自动化脚本。  \r', 'Java是一种面向对象、跨平台的编程语言，采用“一次编写，到处运行”理念，常用于企业级后端、Android应用和大数据框架。  \r', 'C语言是一种高效的过程式编程语言，贴近硬件，用于操作系统、嵌入式系统和性能关键型应用，是许多现代语言的基础。  \r', 'C++是C语言的扩展，支持面向对象和泛型编程，兼具高性能和灵活性，常用于游戏开发、高频交易和系统软件。  \r', 'C#是微软开发的面向对象语言，运行于.NET平台，结合强大类型系统和现代语法，广泛用于Windows桌面应用、游戏(Unity)和Web服务。  \r', 'JavaScript是一种动态脚本语言，主要运行在浏览器中实现交互效果，也可通过Node.js用于服务器端开发，是前端核心语言。  \r', 'TypeScript是JavaScript的超集，添加了静态类型和接口，编译为纯JS，提高大型项目的可维护性和开发体验。  \r', 'Ruby是一种动态、解释型的面向对象语言，以优雅简洁的语法和强大的元编程能力闻名，Ruby on Rails框架推动了Web快速开发。  \r', 'PHP是一种通用脚本语言，专为Web设计，嵌入HTML中运行，广泛用于动态网站和内容管理系统，如WordPress和Drupal。  \r', 'Swift是苹果开发的现代编程语言，用于iOS、macOS等平台，安全、快速，融合了多种编程范式，取代了Objective-C的主流地位。  \r', 'Kotlin是运行于JVM的静态类型语言，与Java完全兼容，更简洁安全，被谷歌推荐为Android官方开发语言，也支持原生和Web。  \r', 'Go（Golang）是谷歌开发的静态编译型语言，内置并发支持，语法简洁，适合构建高性能微服务和云基础设施，如Docker和Kubernetes。  \r', 'Rust是一种系统级语言，通过所有权机制保证内存安全，无需垃圾回收，性能媲美C++，用于操作系统、游戏引擎和Web组件。  \r', 'Dart是谷歌开发的面向对象语言，优化UI构建，用于Flutter框架跨平台移动开发，也支持AOT编译和JIT执行。  \r', 'Perl是一种灵活的高级语言，擅长文本处理、正则表达式和系统管理，曾广泛用于CGI编程，有“瑞士军刀”之称。  \r', 'Lua是一种轻量级脚本语言，易于嵌入，常用作游戏逻辑（如WoW）和应用程序配置，以简洁高效和可扩展性著称。  \r', 'R是一种用于统计计算和数据可视化的语言，拥有丰富的包生态系统，广泛应用于学术研究、数据分析和机器学习。  \r', 'MATLAB是一种数值计算环境和语言，专为矩阵运算设计，广泛用于工程、信号处理和科学仿真，提供丰富的工具箱。  \r', 'Julia是一种面向科学计算的高性能动态语言，采用即时编译，语法类似Python，速度接近C，适合数值分析和并行计算。  \r', 'Scala是运行在JVM上的多范式语言，结合面向对象和函数式编程，可用于构建高性能大数据系统，如Apache Spark。  \r', 'Haskell是一种纯函数式语言，惰性求值，强静态类型，以数学严谨性著称，常用于学术研究和编译器开发，影响深远。  \r', 'Erlang是面向并发和容错的函数式语言，基于Actor模型，常用于电信和即时通讯系统，如WhatsApp和RabbitMQ。  \r', 'Elixir是构建于Erlang虚拟机上的动态函数式语言，语法更友好，支持宏和管道操作，适合构建高并发、可维护的Web应用。  \r', 'Clojure是运行在JVM上的Lisp方言，强调不可变数据和函数式编程，可与Java互操作，适合数据分析和并发应用。  \r', 'Common Lisp是Lisp家族的标准方言，支持多范式，包含强大的宏和面向对象系统，用于AI研究和元编程。  \r', 'Scheme是Lisp的简化方言，语法极简，强调词法作用域和尾递归，常用于教学和编程语言理论研究。  \r', 'F#是运行于.NET的函数式语言，支持类型推断和异步编程，与C#互操作，适用于数据分析和科学计算。  \r', 'OCaml是强类型函数式语言，支持面向对象和模块系统，以高效编译和类型安全著称，常用于编译器和验证工具。  \r', 'Pascal是一种过程式编程语言，强调结构化和强类型，曾用于教学和早期软件开发，派生出了Object Pascal。  \r', 'Delphi（Object Pascal）是可视化开发环境，基于Pascal，用于构建Windows桌面应用，拥有快速编译和强大的RAD能力。  \r', 'Ada是一种强类型、高可靠性的语言，专为大型嵌入式系统和实时控制设计，广泛用于航空航天、国防和交通领域。  \r', 'COBOL是面向商务处理的语言，擅长数据处理和文件操作，仍在银行和大型机系统中大量使用，具有悠久历史。  \r', 'Fortran是世界上最早的高级语言之一，专为数值和科学计算设计，大量用于物理、气候模型和高性能计算。  \r', 'ALGOL是算法语言的先驱，引入块结构和词法作用域，对后续语言（如C、Pascal）有深远影响，主要用于学术。  \r', 'BASIC是一种简单易学的过程式语言，早期用于初学者编程，后来发展为多种变体，如Visual Basic和QBASIC。  \r', 'Visual Basic .NET是微软的面向对象语言，运行于.NET框架，语法平易近人，适合快速开发Windows和Web应用。  \r', 'PowerShell是微软的任务自动化和配置管理框架，基于.NET，提供强大脚本能力，用于系统管理和DevOps。  \r', 'Bash是Unix/Linux系统的默认Shell，支持命令执行、脚本编程和作业控制，广泛用于系统管理和自动化任务。  \r', 'SQL是结构化查询语言，用于管理和操作关系型数据库，支持查询、插入、更新和删除，是数据处理的基石。  \r', 'HTML是超文本标记语言，用于定义网页结构和内容，通过标签组织文本、图像和链接，是所有Web页面的骨架。  \r', 'CSS是层叠样式表，用于控制网页的布局、颜色、字体等视觉呈现，与HTML分离，提升样式复用性和维护性。  \r', 'XML是可扩展标记语言，用于存储和传输结构化数据，具有自描述性，广泛用于配置文件、数据交换和文档标准。  \r', 'JSON是轻量级数据交换格式，基于JavaScript语法，易于人读写和机器解析，成为Web API和配置文件的主流格式。  \r', 'YAML是一种友好的数据序列化格式，强调可读性，常用于配置文件和CI/CD流水线，支持复杂数据结构。  \r', 'Tcl是一种简单可嵌入的脚本语言，常与Tk搭配构建图形界面，广泛用于EDA工具（如Vivado）和测试自动化。  \r', 'Prolog是一种逻辑编程语言，基于谓词逻辑，适合编写专家系统和自然语言处理，通过事实和规则进行推理。  \r', 'Lisp是第二古老的高级语言，以符号处理和宏系统闻名，是AI领域的重要语言，启发了许多现代编程范式。  \r', '汇编语言是机器指令的助记符表示，与硬件紧密相关，用于底层驱动、操作系统和性能优化，但可移植性差。  \r', 'VHDL是硬件描述语言，用于描述数字电路的行为和结构，广泛用于FPGA和ASIC设计，支持仿真和综合。  \r', 'Verilog是另一种硬件描述语言，类似C语法，用于数字电路建模，常用于芯片前端设计和验证流程。  \r', 'ABAP是SAP开发环境中的高级业务应用编程语言，用于定制企业资源计划（ERP）系统，处理大量事务数据。  \r', 'Apex是Salesforce平台上的强类型语言，语法类似Java，用于构建业务逻辑、触发器和REST服务，支持多租户环境。  \r', 'AWK是一种文本处理语言，擅长模式扫描和数据处理，常用于Unix命令行生成报告和简单数据转换。  \r', 'Batch是Windows系统的批处理脚本语言，由一组命令行指令组成，用于执行重复任务和自动化操作。  \r', 'BCPL是早期的系统编程语言，是C语言的祖先，引入花括号和编译时类型，影响了后续众多语言设计。  \r', 'B语言是C语言的前身，由Ken Thompson开发，用于早期Unix系统，简化了BCPL，但缺少数据类型。  \r', 'Crystal是一种静态类型、编译型语言，语法类似Ruby，但性能更高，结合宏和类型推断，适合Web和系统开发。  \r', 'Nim是一种编译型系统语言，语法类似Python，支持垃圾回收和宏，可生成C/C++/JS代码，兼顾效率与表达力。  \r', 'Zig是一种通用编程语言，强调与C互操作、手动内存管理和编译时代码执行，用于系统和嵌入式开发。  \r', 'V语言是一种简单、快速、安全的编译型语言，语法类似Go，可用于开发GUI、Web和系统工具，生成C代码。  \r', 'Chapel是一种并行编程语言，设计用于高性能计算，提供直观的全局视图和分层并行性，适合超级计算机。  \r', 'D语言是一种系统级语言，结合C++性能和现代特性，支持垃圾回收和编译时函数执行，用于通用开发。  \r', 'Eiffel是一种面向对象语言，强调设计契约（DbC），支持多重继承和泛型，用于构建可靠商业软件。  \r', 'Groovy是一种动态语言，运行在JVM上，语法比Java简洁，支持闭包和DSL，常用于Gradle构建脚本。  \r', 'Jython是Python在JVM上的实现，允许Python代码调用Java库，无缝集成Java生态系统，用于脚本和测试。  \r', 'JRuby是Ruby在JVM上的实现，提供高性能和Java互操作性，可用于Web应用（Rails）和混合开发。  \r', 'CoffeeScript是一种编译为JavaScript的语言，语法更简洁，使用空格缩进，让JS代码更优雅，但已不流行。  \r', 'LiveScript是CoffeeScript的前身，语法相似，提供更丰富函数式特性，用于编译到JS，但较冷门。  \r', 'Elm是一种纯函数式语言，编译为JavaScript，用于构建前端UI，强调无运行时错误和响应式更新，使用虚拟DOM。  \r', 'PureScript是强类型函数式语言，编译到JavaScript，语法类似Haskell，可用于开发可靠Web应用。  \r', 'ReasonML是OCaml的语法友好变体，编译到JavaScript和原生，结合函数式和命令式，用于React前端开发。  \r', 'Hack是PHP的变体，由Facebook开发，添加静态类型和泛型，运行于HHVM，提升Facebook代码可靠性和性能。  \r', 'Haxe是一种高层次的跨平台语言，可编译为JS、C++、Java等，支持多种后端，适合游戏和移动应用开发。  \r', 'MoonScript是编译到Lua的语言，语法类似CoffeeScript，用于游戏和嵌入环境，保持Lua高效。  \r', 'Squirrel是一种轻量级脚本语言，类似Lua但语法偏向C/Java，用于游戏（如Left 4 Dead）和嵌入式应用。  \r', 'AngelScript是一种脚本语言，专为游戏和应用程序嵌入设计，语法接近C++，支持面向对象和引用计数。  \r', 'ActionScript是Flash平台的语言，用于创建交互式动画和Web游戏，目前已被HTML5淘汰，但曾主导RIA。  \r', 'ColdFusion是一种快速应用开发平台，使用CFML标记语言，用于生成动态网页和数据库交互，适合企业内网。  \r', 'CFML是ColdFusion的标记语言，类似HTML，嵌入服务器端逻辑，用于快速构建数据驱动的Web应用。  \r', 'Racket是Lisp/Scheme的衍生语言，提供丰富的库和语言扩展能力，用于编程语言研究和教育。  \r', 'ClojureScript是Clojure到JavaScript的编译器，支持函数式、不可变数据，用于前端React开发。  \r', 'GDScript是Godot游戏引擎的脚本语言，语法类似Python，专为游戏逻辑设计，集成节点系统，性能好。  \r', 'GLSL是OpenGL着色器语言，用于编写运行在GPU上的顶点和片元着色程序，实现实时图形渲染效果。  \r', 'HLSL是DirectX着色器语言，类似于GLSL，用于Windows游戏开发，控制GPU渲染管道，生成特效。  \r', 'WebAssembly是一种二进制指令格式，可在浏览器中高效运行，支持多种语言编译，提供接近原生的性能。  \r', 'Solidity是以太坊智能合约的专用语言，静态类型，继承自C++和JS，用于编写去中心化应用（DApp）。  \r', 'Vyper是另一种以太坊语言，语法类似Python，更安全简洁，用于编写智能合约，减少攻击面。  \r', 'MQL是MetaTrader平台的自动化交易语言，用于编写智能交易系统、脚本和指标，支持外汇和金融策略。  \r', 'AutoHotkey是一种脚本语言，用于Windows自动化，可以创建快捷键、宏和GUI，提高日常操作效率。  \r', 'AutoIt类似于AutoHotkey，用于自动化Windows任务，模拟键盘鼠标，常用于软件安装和测试。  \r', 'Smalltalk是纯粹的面向对象语言，一切皆对象，环境即系统，对现代GUI和OOP有深远影响，但应用较少。  \r', 'Self是一种基于原型的语言，强调对象继承和动态分派，影响了JavaScript和Io的设计思想。  \r', 'Icon是一种高级语言，专注于字符串处理和数据结构，具有成功/失败机制，用于文本分析和模式匹配。  \r', 'Snobol是一种早期字符串处理语言，以强大的模式匹配功能闻名，用于自然语言处理和文本转换。  \r', 'ML是标准元语言，一种函数式语言，引入类型推断和模块系统，是许多函数式语言（如OCaml、F#）的祖先。  \r', 'Caml是ML方言，轻量级，支持函数式、命令式和面向对象编程，用于教学和软件开发。  \r', 'Clean是一种纯函数式语言，类似Haskell，但支持独特的世界管理（唯一类型），用于高性能计算。  \r', 'Idris是一种依赖类型语言，支持类型驱动开发，可用于验证程序正确性，在学术和形式验证中受关注。', '夏朝约公元前2070年由禹的儿子启建立，是中国历史上第一个世袭制王朝，标志着原始社会向阶级社会过渡，开启了华夏文明史。  \r', '约公元前1600年，商汤率部族在鸣条之战击败夏桀，推翻暴政，建立商朝，成为中华文明早期强大的奴隶制王朝。  \r', '公元前1046年，周武王姬发联合诸侯在牧野之战中击败商纣王，商朝灭亡，西周建立，确立分封制和宗法制，影响深远。  \r', '西周（前1046-前771年）定都镐京，实行分封制和礼乐制度，周公旦制礼作乐，奠定了中国封建社会的基础。  \r', '西周晚期，周幽王为博褒姒一笑，点燃烽火戏弄诸侯，导致犬戎入侵时无人来救，西周灭亡，平王东迁开启东周。  \r', '公元前770年，周平王将都城从镐京东迁至洛邑，东周开始，周王室权威衰落，诸侯争霸时代由此拉开序幕。  \r', '齐桓公任用管仲改革，以“尊王攘夷”为号召，九合诸侯，一匡天下，成为春秋时期第一个霸主，确立霸主政治。  \r', '晋文公重耳流亡十九年后回国，通过城濮之战击败楚国，践土会盟，成为春秋第二任霸主，开创晋国百年霸业。  \r', '楚庄王北伐时向周王室使者询问九鼎轻重，显示取代周天子野心，后经邲之战大败晋国，成为春秋第三位霸主。  \r', '春秋末期，吴王夫差与越王勾践相继称霸，勾践卧薪尝胆灭吴，随后越国北上中原，成为最后一位春秋霸主。  \r', '公元前403年，韩、赵、魏三家大夫瓜分晋国，被周天子正式承认，标志着春秋结束、战国七雄格局形成。  \r', '公元前356年，秦孝公任用商鞅推行废井田、重农抑商、奖励军功、郡县制等改革，使秦国迅速强大，为统一六国奠基。  \r', '战国时期，苏秦倡导六国合纵抗秦，张仪推行连横破合纵，这是纵横家左右国际局势的外交策略，影响秦国统一进程。  \r', '公元前230-221年，秦王嬴政先后灭韩、赵、魏、楚、燕、齐六国，完成统一，建立中国历史上首个中央集权帝国。  \r', '秦始皇为加强思想控制，下令焚烧民间藏书并坑杀方士儒生，虽强化统治但严重摧残文化，成为后世批评的暴政。  \r', '公元前209年，陈胜吴广在大泽乡揭竿起义，喊出“王侯将相宁有种乎”，是秦末农民战争的开端，加速了秦朝灭亡。  \r', '公元前207年，刘邦率军攻入咸阳，秦王子婴投降，秦朝灭亡，随后楚汉相争，最终刘邦建立汉朝。  \r', '公元前206-202年，刘邦与项羽争夺天下，经过彭城之战、荥阳对峙和垓下之战，刘邦胜出，项羽乌江自刎，汉朝建立。  \r', '公元前202年，刘邦称帝，定都长安，国号汉，史称西汉，推行休养生息政策，奠定了强盛汉帝国的基础。  \r', '公元前200年，汉高祖刘邦率军讨伐匈奴，被围困白登山七日，后以和亲策略解围，开启汉朝与匈奴长期和战关系。  \r', '汉文帝、景帝时期（前180-前141年）推行黄老之术，轻徭薄赋，以德化民，社会安定经济繁荣，为汉武帝大业积蓄国力。  \r', '公元前134年，汉武帝采纳董仲舒建议，罢黜百家，独尊儒术，使儒学成为官方正统思想，影响中国两千年。  \r', '公元前138年和前119年，张骞两次出使西域，开辟丝绸之路，促进中原与中亚、西亚的交流，传播丝绸和文明。  \r', '公元前127-前119年，卫青、霍去病多次率军北击匈奴，收复河套，封狼居胥，使匈奴元气大伤，保障北方边境安全。  \r', '公元前33年，王昭君自愿出塞和亲匈奴呼韩邪单于，促进汉匈和平半个世纪，成为民族团结的象征。  \r', '公元9年，王莽篡汉建立新朝，推行币制、田制等改革，因脱离实际导致民乱，最终被绿林军推翻，新朝灭亡。  \r', '公元17-23年，绿林、赤眉等农民军反抗王莽，绿林军攻入长安杀王莽，随后刘秀崛起，光复汉室。  \r', '公元25年，刘秀称帝，定都洛阳，史称东汉，他整顿吏治、释放奴婢、轻徭薄赋，使汉室再度兴盛。  \r', '公元73-102年，班超出使西域，以智勇平定诸国叛乱，重新打通丝绸之路，使西域各国重新归附汉朝。  \r', '公元184年，张角领导黄巾军以“苍天已死，黄天当立”为口号起义，虽被镇压，但东汉统治名存实亡，群雄并起。  \r', '公元189年，董卓率兵入京，废少帝立献帝，残暴不仁，引发关东联军讨伐，东汉政权瓦解，三国序幕开启。  \r', '公元200年，曹操在官渡以少胜多击败袁绍，奠定统一北方的基础，是中国历史上以弱胜强的著名战役。  \r', '公元208年，孙刘联军在赤壁以火攻击败曹操大军，奠定三国鼎立格局，是中国历史上经典的抗水战例。  \r', '公元220-280年，魏、蜀、吴三分天下，各自称帝，期间军事、政治、文化均有特色，最终由司马氏统一。  \r', '公元265年，司马炎逼迫魏元帝禅让，建立晋朝，定都洛阳，史称西晋，并于280年灭吴，完成短暂统一。  \r', '公元291-306年，西晋宗室八王为争权相互攻杀，导致国力衰微，引发五胡内迁，成为西晋灭亡的直接导火索。  \r', '公元304-439年，匈奴、鲜卑等五胡先后在中国北方建立十六个政权，战乱频仍，汉族南迁，南北对立加剧。  \r', '公元383年，前秦苻坚率大军进攻东晋，在淝水被谢玄率领的北府兵以少胜多击败，前秦瓦解，南北对峙延续。  \r', '公元485-494年，孝文帝推行汉化政策，迁都洛阳，改鲜卑姓为汉姓，促进民族融合，推动北方社会经济恢复。  \r', '公元581年，杨坚代周建立隋朝，589年灭南陈，结束近三百年分裂，统一全国，开创开皇之治，国力强盛。  \r', '公元605-610年，隋炀帝征发百万民众开凿京杭大运河，连接南北，促进经济交流，但劳役繁重，加速隋朝覆灭。  \r', '隋朝废除九品中正制，开创科举考试选拔人才，科举制延续一千三百年，是中国古代最公平的人才选拔制度。  \r', '公元611-618年，各地农民军蜂起反抗隋炀帝暴政，李密、窦建德等势力壮大，最终唐高祖李渊乘势夺权。  \r', '公元618年，李渊在长安称帝，建立唐朝，随后李世民发动玄武门之变，开启贞观之治，成为世界级帝国。  \r', '公元626年，李世民在长安玄武门击杀太子李建成和齐王李元吉，随后即位为唐太宗，开创了盛唐序幕。  \r', '唐太宗在位期间（627-649年），任用贤臣，虚心纳谏，轻徭薄赋，对外征服东突厥，缔造了政治清明、文化繁荣的盛世。  \r', '公元629-645年，玄奘法师西行印度取经，带回佛经并翻译，著《大唐西域记》，促进中印文化交流。  \r', '公元690年，武则天改唐为周，称圣神皇帝，是中国历史上唯一正统女皇帝，在位期间鼓励科举、打击门阀。  \r', '唐玄宗李隆基统治前期（713-741年），励精图治，任用姚崇、宋璟，国库充盈，人口大增，唐朝达到极盛。  \r', '公元755-763年，安禄山、史思明发动叛乱，唐玄宗出逃，唐朝由盛转衰，藩镇割据和宦官专权问题日趋严重。  \r', '公元875-884年，黄巢领导大规模农民起义，转战南北，攻破长安，虽最终失败，但严重削弱唐朝统治。  \r', '公元907-960年，北方先后更替后梁、后唐等五朝，南方和山西存在十国，是又一次大分裂时期，战乱不断。  \r', '公元960年，赵匡胤在陈桥驿被黄袍加身，建立宋朝，定都开封，随后杯酒释兵权，加强中央集权。  \r', '公元961年，宋太祖赵匡胤设宴解除石守信等大将兵权，以文制武，开创宋朝重文轻武传统，预防藩镇割据。  \r', '公元1005年，宋真宗与辽圣宗签订澶渊之盟，宋辽约为兄弟，宋每年纳岁币，双方和平一百余年，促进边境贸易。  \r', '公元1043年，范仲淹推行整顿吏治、减徭役等改革，因贵族反对而失败，但为后来的王安石变法提供借鉴。  \r', '公元1069年，宋神宗任用王安石进行青苗、募役、方田均税等变法，旨在富国强兵，但触犯利益集团，终被废止。  \r', '公元1126-1127年，金军攻破开封，俘虏宋徽宗、钦宗二帝及宗室数千人，北宋灭亡，赵构南渡建立南宋。  \r', '公元1127年，赵构即位于应天府，后定都临安，形成宋金对峙局面，岳飞等抗金将领活跃，但朝廷主和派占上风。  \r', '岳飞率岳家军力主抗金，取得郾城大捷，却被秦桧以“莫须有”罪名杀害，成为民族英雄，其爱国精神流传千古。  \r', '公元1141年，南宋与金签订和约，宋向金称臣，割地纳贡，岳飞遇害，宋金南北对峙正式形成。  \r', '公元1219-1225年，成吉思汗率蒙古大军西征花剌子模，击败各国，建立庞大帝国，推动东西方军事技术交流。  \r', '公元1234年，蒙古联合南宋攻破金国都城蔡州，金朝灭亡，蒙古势力扩至中原，为后来统一中国奠定基础。  \r', '公元1271年，忽必烈改国号为大元，定都大都（今北京），1279年灭南宋，完成中国历史上首次由少数民族建立的统一王朝。  \r', '元世祖忽必烈采用汉法，建立行省制度，重视农业和商贸，加强中央集权，促进了民族融合和中外交往。  \r', '公元1351年，韩山童、刘福通等以红巾为号起义，反抗元朝暴政，朱元璋后来成为其中一支，最终推翻元朝。  \r', '公元1368年，朱元璋在应天称帝，建立明朝，同年北伐攻克大都，元朝北退，明朝恢复汉族统治，初期励精图治。  \r', '公元1399-1402年，燕王朱棣以“清君侧”为名起兵，攻陷南京，推翻建文帝，朱棣即位为明成祖，年号永乐。  \r', '公元1405-1433年，郑和七次率领船队出使西洋，到达亚非三十余国，宣扬国威，促进海外贸易和文明交流。  \r', '公元1449年，明英宗亲征瓦剌，在土木堡被俘，朝野震动，于谦组织北京保卫战，成功击退瓦剌，保住明朝。  \r', '公元1457年，石亨等拥立被软禁的明英宗复辟，废代宗，重新即位，后于谦被冤杀，是明朝中期宫廷政变。  \r', '明万历年初期，张居正推行一条鞭法、考成法等，整顿吏治、增加财政收入，实现了短暂的中兴气象。  \r', '公元1592-1600年，明神宗先后平定宁夏哱拜、播州杨应龙及援朝抗日三场战事，耗费国力，但也维持了外部安定。  \r', '公元1629-1644年，李自成率农民军转战各地，提出“均田免赋”，最终攻破北京，崇祯自缢，明朝灭亡。  \r', '公元1616年，努尔哈赤建立后金，后改称满洲，皇太极改国号清，多尔衮摄政，于1644年入关，定鼎中原。  \r', '公元1644年，清军在吴三桂接应下进入山海关，击败李自成，顺治帝迁都北京，清朝开始对全国统治。  \r', '清廷为强化统治，颁布剃发令，要求汉人剃发易服，激起江南反抗（如嘉定三屠），最终强制推行，影响深远。  \r', '公元1669年，康熙帝智擒权臣鳌拜，开始亲政，加强皇权，整肃朝纲，为后来的康乾盛世奠定政治基础。  \r', '公元1673-1681年，康熙帝派兵讨伐吴三桂等三藩，经过八年战争，最终平定叛乱，巩固了清朝对南方的统治。  \r', '公元1683年，清军水师在施琅指挥下攻占台湾，郑克塽投降，清朝将台湾纳入版图，设置台湾府。  \r', '公元1685-1686年，清军与沙俄在雅克萨交战，最终签署《尼布楚条约》，划定中俄东部边界，维护了领土主权。  \r', '公元1689年，中俄签订《尼布楚条约》，这是中国与外国签订的第一个平等条约，明确了黑龙江流域归属。  \r', '公元1722年，康熙崩逝，雍正帝通过秘密立储即位，推行摊丁入亩、改土归流等改革，强化中央集权。  \r', '雍正时期废除西南土司制度，改设府县，由朝廷派遣流官管理，加强了对边疆地区的直接控制。  \r', '乾隆帝在位时期（1735-1796年），国家经济繁荣、疆域辽阔，但也闭关锁国，后期政治腐败，盛极而衰。  \r', '公元1840-1842年，英国以禁烟为由发动鸦片战争，清军战败，签订《南京条约》，中国开始沦为半殖民地半封建社会。  \r', '公元1851-1864年，洪秀全领导太平军起义，定都天京，颁布《天朝田亩制度》，最终被清廷联合洋人镇压，但严重削弱清朝力量。  \r', '公元1861-1895年，曾国藩、李鸿章等推动“自强”“求富”，兴办近代军工和民用企业，是中国近代化的首次尝试。  \r', '公元1894-1895年，日本发动甲午战争，清军战败，签订《马关条约》，割让台湾，支付巨额赔款，民族危机加深。  \r', '1895年签订，中国承认朝鲜独立，割让辽东半岛、台湾及澎湖列岛，赔款2亿两白银，允许日企设厂，是重大不平等条约。  \r', '1898年，光绪帝采纳康有为、梁启超建议，推行政治、经济、文化改革，但遭慈禧阻挠，仅103天即失败，史称百日维新。  \r', '1899-1901年，义和团以“扶清灭洋”为口号反对外国侵略，引发八国联军侵华，最终清廷签订《辛丑条约》，损失惨重。  \r', '1911年10月10日，武昌起义爆发，各省响应，推翻清朝，建立中华民国，结束两千多年封建帝制，是中国近代史的伟大转折。  \r', '1912年1月1日，孙中山在南京就任临时大总统，宣布中华民国成立，颁布《临时约法》，确立共和政体。  \r', '1919年5月4日，北京学生抗议巴黎和会出卖中国权益，掀起爱国运动，促进马克思主义传播，是新民主主义革命的开端。  \r', '1921年7月23日，中共一大在上海召开，后转至嘉兴南湖，宣告中国共产党成立，深刻改变中国历史走向。  \r', '1926-1928年，国民革命军从广东出发，北伐推翻北洋军阀统治，基本统一中国，但随后国共合作破裂。  \r', '1927年8月1日，周恩来、朱德等领导南昌起义，打响了武装反抗国民党反动派的第一枪，建军节由此而来。  \r', '1927年9月，毛泽东在湘赣边界领导秋收起义，随后进军井冈山，创建了第一个农村革命根据地。  \r', '1927年10月，毛泽东率部到达井冈山，建立农村革命根据地，提出“农村包围城市”道路，成为革命胜利起点。  \r', '1934年10月，红军第五次反围剿失败后被迫战略转移，历尽艰险，行程二万五千里，于1935年到达陕北，保存革命火种。  \r', '1936年12月12日，张学良、杨虎城扣留蒋介石，逼其抗日，经各方调解和平解决，促成国共第二次合作。  \r', '1937年7月7日，日军在北平卢沟桥借演习失踪进攻，全面抗战爆发，中国进入八年艰苦抗日战争。  \r', '1940年8月，八路军在华北发动大规模破袭战，参战百余团，破坏交通线，沉重打击日军气焰，振奋全国民心。  \r', '1945年8月15日，日本宣布无条件投降，9月2日签署投降书，中国抗日战争取得完全胜利，台湾回归祖国。  \r', '1948年9月至1949年1月，人民解放军发动辽沈、淮海、平津三大战役，基本消灭国民党主力，奠定解放全国基础。  \r', '1949年10月1日，毛泽东在北京天安门宣布中华人民共和国成立，新民主主义革命取得伟大胜利，开启中国历史新纪元。  \r', '约公元前3100年，法老美尼斯统一上下埃及，建立第一王朝，标志着古埃及文明的诞生，创造了金字塔和象形文字。  \r', '约公元前1760年，古巴比伦国王汉谟拉比颁布了世界上已知最早的成文法典，以“以眼还眼”为原则，现存于卢浮宫。  \r', '约公元前1200年，腓尼基人利用埃及音符发明22个辅音字母，成为希腊字母的祖先，对西方文字体系影响深远。  \r', '约公元前10世纪，所罗门王统治以色列，兴建耶路撒冷圣殿，成为犹太历史的重要时期，其智慧故事流传于世。  \r', '约公元前8-7世纪，亚述以强大军事征服两河流域、埃及等，建立庞大帝国，首都尼尼微，后因内乱和外部压力灭亡。  \r', '公元前626-539年，迦勒底人建立新巴比伦王国，尼布甲尼撒二世修建空中花园，征服犹大国，俘获犹太人。  \r', '公元前550年，居鲁士统一波斯，建立阿契美尼德王朝，征服巴比伦，解放犹太人，以宽容政策统治帝国。  \r', '公元前8-6世纪，希腊形成众多城邦（如雅典、斯巴达），各具特色，推行民主或军事体制，创造了灿烂古典文明。  \r', '公元前492-449年，波斯帝国与希腊城邦爆发三次战争，希腊以弱胜强（马拉松、温泉关等），捍卫了西方文明独立性。  \r', '公元前431-404年，雅典与斯巴达为争夺希腊霸权爆发内战，最终斯巴达获胜，但希腊各城邦元气大伤，走向衰落。  \r', '公元前336-323年，亚历山大大帝征服波斯、埃及，远至印度河流域，建立横跨欧亚非的大帝国，促进了希腊化时代。  \r', '公元前323-前30年，亚历山大死后帝国分裂，希腊文化扩散到东方，埃及托勒密王朝和塞琉古王朝成为文化中心。  \r', '公元前509年，罗马人推翻塔克文王朝，建立共和国，实行执政官和元老院制，开启了罗马的崛起之路。  \r', '公元前264-146年，罗马与迦太基进行了三次战争，最终罗马彻底摧毁迦太基，夺得西地中海霸权，成为超级大国。  \r', '公元前133-121年，罗马平民派格拉古兄弟推行土地和粮食改革，触犯元老利益，相继被杀，但引发罗马社会矛盾激化。  \r', '公元前73-71年，斯巴达克领导奴隶起义，多次击败罗马军队，虽最终失败，却动摇了罗马奴隶制根基。  \r', '公元前58-50年，凯撒率罗马军团征服高卢全境，击败日耳曼人，写下《高卢战记》，增强个人威望，为内战铺垫。  \r', '公元前49-45年，凯撒与庞培爆发内战，凯撒获胜成为独裁官，后被元老院刺杀，罗马由共和走向帝制。  \r', '公元前27年，屋大维接受“奥古斯都”尊号，建立元首制，罗马进入帝国时期，开启长达两百年的罗马和平。  \r', '约公元1世纪，耶稣在巴勒斯坦地区开始传教，后被钉十字架，其门徒传播基督教，最终成为罗马国教。  \r', '公元64年，罗马大火，皇帝尼禄嫁祸基督徒，施以酷刑，此为早期基督教遭大规模迫害的著名事件。  \r', '公元313年，君士坦丁大帝颁发米兰敕令，承认基督教合法，后于临终前受洗，使基督教由非法转为合法宗教。  \r', '公元476年，日耳曼将领奥多亚克废黜西罗马末代皇帝罗慕路斯，西罗马帝国灭亡，西欧进入中世纪封建社会。  \r', '公元528-534年，东罗马皇帝查士丁尼编纂《民法大全》，系统整理罗马法，成为后世大陆法系的蓝本。  \r', '公元610年，穆罕默德在麦加得到天启，创立伊斯兰教，后迁徙麦地那，统一阿拉伯半岛，建立政教合一的共同体。  \r', '公元632-750年，阿拉伯帝国迅速扩张，征服叙利亚、埃及、波斯、北非等地，建立横跨三洲的大帝国，传播伊斯兰文明。  \r', '公元661-750年，阿拉伯倭马亚王朝定都大马士革，实行行政分治，继续扩张，但在内部矛盾中被阿拔斯推翻。  \r', '公元750-1258年，阿拔斯王朝定都巴格达，迎来伊斯兰黄金时代，科学、文化繁荣，最终被蒙古西征军摧毁。  \r', '公元800年，查理曼被教皇加冕为“罗马皇帝”，建立加洛林帝国，统一西欧大部分地区，被称为“欧洲之父”。  \r', '公元800年圣诞节，查理曼在罗马圣彼得大教堂接受教皇利奥三世加冕，标志着西欧基督教帝国的诞生。  \r', '公元8-11世纪，北欧维京人沿欧洲海岸线掠夺、殖民，影响英国、法国、俄罗斯等地，推动了欧洲封建化进程。  \r', '公元1066年，诺曼底公爵威廉渡海击败哈罗德，加冕为英国国王，建立诺曼王朝，深刻影响英国法律和语言。  \r', '公元11世纪，教皇格里高利七世推行改革，强化教权，反对世俗君主干预主教任命，引发“叙任权之争”。  \r', '公元10-12世纪，克吕尼修道院发起的宗教改革，强调教会纯洁性，提升教皇权威，影响欧洲政治与宗教关系。  \r', '公元1096-1099年，欧洲基督教国家响应教皇号召，远征耶路撒冷，成功建立十字军国家，开启近两百年宗教战争。  \r', '公元1215年，英王约翰在贵族压力下签署《大宪章》，限制王权，保障贵族权利，被视为英国宪政的基石。  \r', '公元1337-1453年，英法之间为争夺领土和王位爆发长期战争，最终法国获胜，民族国家意识增强，火药武器普及。  \r', '公元1347-1351年，黑死病从亚洲传入欧洲，造成约2500万人死亡，欧洲人口锐减，社会经济结构发生重大变化。  \r', '公元14-16世纪，欧洲以人文主义为旗帜，复兴古希腊罗马艺术与科学，涌现达芬奇、米开朗基罗等巨匠，开启近代文明。  \r', '约公元1440年，古腾堡发明活字印刷机，使书籍大规模普及，信息传播速度加快，极大推动文艺复兴和宗教改革。  \r', '公元1492年，哥伦布受西班牙王室资助向西航行，到达美洲巴哈马群岛，开辟了跨大西洋航线，改变世界历史进程。  \r', '公元1498年，达伽马绕过好望角到达印度卡利卡特，开辟了欧洲直通亚洲的海上航线，打破阿拉伯人垄断贸易。  \r', '公元1519-1522年，麦哲伦船队完成人类首次环球航行，证明地球是圆的，极大拓展了人类地理认知。  \r', '公元1517年，马丁·路德发布《九十五条论纲》，发起宗教改革，创立新教，打破天主教统一局面，促进思想解放。  \r', '公元1541年，加尔文在日内瓦建立新教教会，提倡“预选论”，强调节俭和勤劳，影响欧洲资本主义伦理。  \r', '公元1485-1603年，都铎王朝统治英国，亨利八世创立英国国教，伊丽莎白一世击败无敌舰队，英国走向强大。  \r', '公元1588年，西班牙派出无敌舰队远征英国，遭遇风暴和英军拦截惨败，宣告西班牙海上霸权的衰落。  \r', '公元1585-1604年，英国与西班牙为争夺海上殖民霸权交战，最终英国胜利，逐步取代西班牙成为海洋强国。  \r', '公元1618-1648年，欧洲各国为宗教和政治矛盾爆发大规模战争，最终签订《威斯特伐利亚和约》，开创现代国际体系。  \r', '公元1648年，和约确立国家主权平等原则，承认荷兰和瑞士独立，标志着欧洲宗教战争结束，近代外交秩序开端。  \r', '公元1642-1651年，议会与国王查理一世之间爆发内战，克伦威尔领导议会军获胜，查理一世被处决，英国成为共和国。  \r', '公元1688年，英国议会迎立威廉三世和玛丽二世，推翻詹姆士二世，通过《权利法案》确立君主立宪制，实现和平变革。  \r', '公元18世纪，伏尔泰、卢梭、孟德斯鸠等思想家提倡理性、自由、民主，为法国大革命和美国独立提供理论基础。  \r', '公元1776年7月4日，北美大陆会议通过《独立宣言》，宣布脱离英国独立，美利坚合众国诞生，鼓舞全球民族解放。  \r', '公元1789年，乔治·华盛顿当选美国首任总统，确立总统制和三权分立，为美国政治体制奠定基石。  \r', '公元1789年7月14日，巴黎民众攻占巴士底狱，大革命爆发，颁布《人权宣言》，推翻封建君主制，影响全球。  \r', '公元1804年，拿破仑·波拿巴称帝，建立法兰西第一帝国，后通过多次战争横扫欧洲，传播法典和自由主义思想。  \r', '公元1814-1815年，欧洲列强在维也纳召开会议，重新划分拿破仑战败后的版图，确立“维也纳体系”，维持了数十年和平。  \r', '公元1821-1829年，希腊人发动独立战争，摆脱奥斯曼帝国统治，获得国际承认，成为欧洲民族解放运动典范。  \r', '公元1810-1826年，玻利瓦尔、圣马丁领导拉美殖民地反抗西班牙统治，建立多个共和国，彻底瓦解西班牙殖民帝国。  \r', '公元1848年，多国爆发资产阶级革命，要求民主和民族统一，虽大多失败，但推动了政治改革和民族意识觉醒。  \r', '公元1857年，印度士兵和民众反抗英国东印度公司统治，遭到残酷镇压，促使英国改由女王直接统治印度。  \r', '公元1859年，达尔文出版《物种起源》，提出进化论和自然选择学说，颠覆神创论，深刻影响生物学和人类思想。  \r', '公元1861-1865年，北方联邦与南方邦联为废除奴隶制等问题开战，北方获胜，美国废除奴隶制，维护国家统一。  \r', '公元1861年，沙皇亚历山大二世签署法令，废除农奴制，虽保留土地所有权，但为俄国资本主义发展提供了劳动力。  \r', '公元1871年，普鲁士在普法战争中击败法国，威廉一世在凡尔赛加冕为德意志皇帝，德国完成统一，成为欧洲强国。  \r', '公元1861-1870年，撒丁王国领导统一运动，加里波第协助，最终收复罗马，意大利王国成立，结束长期分裂。  \r', '公元1871年，巴黎工人起义建立巴黎公社，是无产阶级专政的首次尝试，虽72天失败，但成为共产主义运动重要旗帜。  \r', '公元1884-1885年，欧洲列强在柏林召开会议，制定非洲殖民地瓜分规则，导致非洲被全面分割，影响至今。  \r', '公元1904-1905年，日本与俄国在中国东北开战，日本获胜，这是黄种人首次战胜白种人国家，引发亚洲民族觉醒。  \r', '公元1914年7月28日，奥匈向塞尔维亚宣战，一战爆发，主要战场在欧洲，造成千万人死亡，终结了四大帝国。  \r', '公元1917年11月7日，列宁领导布尔什维克攻占冬宫，建立苏维埃政权，开创社会主义国家，深刻影响世界格局。  \r', '公元1919年，一战战胜国在凡尔赛宫签订对德和约，严厉处置德国，埋下二战隐患，并成立国际联盟。  \r', '公元1919-1933年，德国在战败后建立共和制，但经济危机频发，政治上不稳定，最终被纳粹党取代。  \r', '公元1929年，华尔街股市崩溃，引发全球大萧条，资本主义经济遭受重创，导致失业激增和法西斯势力抬头。  \r', '公元1933年起，美国总统罗斯福推行以救济、复兴、改革为核心的新政，加强政府干预，帮助美国走出大萧条。  \r', '公元1933年，希特勒被任命为德国总理，随后建立纳粹独裁，推行种族主义，扩军备战，为二战爆发埋下祸根。  \r', '公元1939年9月1日，德国入侵波兰，二战全面爆发，全球超过60国参战，最终以轴心国失败告终，联合国成立。  \r', '公元1942-1943年，苏军在斯大林格勒击败德军，是二战东线转折点，苏军开始反攻，加速纳粹败亡。  \r', '公元1944年6月6日，盟军在法国诺曼底强行登陆，开辟西线战场，与苏军东西夹击德国，推动欧洲解放。  \r', '公元1945年8月，美国先后在日本广岛和长崎投下原子弹，造成数十万人伤亡，直接促使日本投降，开启核时代。  \r', '公元1945年10月24日，《联合国宪章》生效，联合国正式成立，旨在维护国际和平与安全，替代国际联盟。  \r', '公元1947年，杜鲁门主义出台，美苏双方以意识形态对抗，形成北约和华约两大阵营，全球进入长达四十多年冷战。  \r', '北约（1949）和华约（1955）分别是美苏主导的军事同盟，双方在欧洲对峙，多次出现危机，但未直接大规模热战。  \r', '公元1950-1953年，朝鲜内战引发多国参战，中朝联军对抗以美国为首的联合国军，最终停战，维持三八线分界。  \r', '公元1955-1975年，美国支持南越对抗北越，北越最终统一，美军撤出，战争引发美国国内反战运动。  \r', '公元1962年，苏联在古巴部署核导弹，美国海军封锁，双方对峙13天，最终苏联撤走导弹，是人类最接近核战争的时刻。  \r', '公元1969年7月20日，美国阿波罗11号宇航员阿姆斯特朗登上月球，迈出人类踏足地外天体的第一步，标志航天里程碑。  \r', '公元1989年11月9日，东德宣布开放柏林墙，民众自由穿越，两德迅速走向统一，象征着冷战的结束。  \r', '公元1991年12月25日，戈尔巴乔夫辞去苏联总统职务，苏联正式解体，分裂为15个独立国家，冷战彻底终结。  \r', '公元1993年11月1日，《马斯特里赫特条约》生效，欧盟正式成立，推进欧洲经济政治一体化，成为重要国际力量。  \r', '公元2001年9月11日，基地组织劫持飞机袭击美国纽约世贸中心和五角大楼，造成近三千人死亡，引发全球反恐战争。', 'ChatGPT是OpenAI开发的大型语言模型，基于GPT架构，能进行自然对话、撰写文章、编程和创意写作，是目前最流行的AI助手。  \r', '文心一言是百度推出的知识增强大语言模型，基于飞桨深度学习平台，擅长中文理解和生成，提供文学创作、商业文案等服务。  \r', '通义千问是阿里巴巴达摩院研发的超大规模语言模型，支持多轮对话、文档摘要和代码生成，致力于企业级智能应用。  \r', '讯飞星火是科大讯飞打造的认知大模型，具备跨领域知识和语言理解能力，支持语音交互、教育辅导和办公自动化。  \r', 'Kimi是月之暗面公司开发的智能助手，支持超长上下文（百万字），擅长处理复杂文档和长文本分析，适合学术和科研场景。  \r', '智谱清言是智谱AI推出的对话模型，基于GLM架构，融合知识图谱，提供问答、写作和推理服务，面向中文用户。  \r', '百小应是百川智能开发的AI助手，支持多轮对话和知识检索，注重信息准确性和逻辑性，适合信息查询和内容创作。  \r', '天工AI是昆仑万维发布的大语言模型，具备多模态能力，支持文本生成、图像理解和数据分析，面向泛娱乐和生产力场景。  \r', 'Claude是Anthropic公司开发的高安全性AI助手，采用宪法AI训练，强调无害性和可靠性，擅长复杂推理和长文档处理。  \r', 'Gemini是谷歌推出的多模态大模型，原生支持文本、图像、音频和视频理解，集成于Google生态，提供强大信息处理能力。  \r', 'Copilot是微软与OpenAI联合推出的AI编程助手，集成于Visual Studio和GitHub，可自动补全代码、生成测试和解释代码逻辑。  \r', 'Midjourney是一款AI绘画工具，通过文本描述生成精美图像，风格多样，广泛用于艺术创作、概念设计和视觉创意。  \r', 'Stable Diffusion是开源的文本到图像生成模型，基于扩散算法，可本地运行，生成高质量图片，支持风格迁移和图像编辑。  \r', 'DALL-E是OpenAI开发的图像生成模型，能将文本描述转换为逼真图像，支持复杂场景和艺术风格，是创意视觉的利器。  \r', 'Sora是OpenAI推出的文本到视频生成模型，能根据描述生成长达60秒的高清视频，展现复杂动态场景和物理规律模拟。  \r', 'Runway是集成了多种AI创意工具的平台，支持视频编辑、图像生成和特效制作，为创作者提供便捷的智能生产流程。  \r', 'Pika是一款AI视频生成工具，输入文字或图片即可生成短片，操作简单，适合社交媒体内容快速制作。  \r', 'Whisper是OpenAI的开源语音识别模型，支持多语言和口音，能将音频转录为高准确率文本，广泛用于会议记录和字幕生成。  \r', 'Suno是一款AI音乐生成工具，通过文本提示创作带有人声和伴奏的完整歌曲，风格多样，降低音乐创作门槛。  \r', 'Adobe Firefly是Adobe推出的创意生成AI，集成于Photoshop等软件，支持文字生成图像、填充和样式转换，提升设计效率。  \r', 'Bard是谷歌早期推出的对话AI，现整合为Gemini，具备信息检索和对话能力，可以实时访问网页内容，提供最新资讯。  \r', 'Perplexity AI是一款智能搜索引擎，结合大语言模型和实时检索，提供带引用的答案，适合研究查询和知识获取。  \r', 'You.com是一个AI驱动的搜索平台，整合多款模型，允许用户切换不同AI回答，提供个性化信息聚合体验。  \r', 'Character.AI允许用户创建和定制具有特定性格的AI角色，进行沉浸式对话，用于娱乐、教育和心理陪伴。  \r', 'Replika是一款AI陪伴应用，通过聊天建立情感纽带，可定制性格和记忆，帮助用户缓解孤独和情绪压力。  \r', 'Jasper是AI内容创作助手，专注于营销文案、博客和社交媒体，提供模板和优化建议，提高写作效率。  \r', 'Copy.ai是AI写作工具，快速生成广告文案、产品描述和邮件内容，支持多种语言和语气，适合电商和营销团队。  \r', 'Grammarly利用AI进行语法检查、拼写纠正和风格优化，实时提供写作建议，是广泛使用的英文写作辅助工具。  \r', 'Notion AI是内置在Notion笔记中的智能助手，可辅助写作、总结、翻译和头脑风暴，提升知识管理效率。  \r', 'Poe是Quora推出的AI聊天平台，整合了多个大模型（如ChatGPT、Claude），用户可在统一界面切换使用。  \r', 'Pi是Inflection AI开发的个人智能助手，注重情感陪伴和日常对话，以自然温暖的方式回答用户问题。  \r', 'Mistral是欧洲开源大模型，性能优异且轻量，支持多种语言，可商用，是开源社区重要的AI基础模型。  \r', 'Llama是Meta发布的开源大语言模型系列，高效可定制，广泛用于学术研究和商业应用，推动了AI民主化。  \r', 'Falcon是由阿联酋TII开发的开源大模型，性能领先，可自由使用，适合构建企业级AI应用和服务。', '固态电池使用固态电解质替代液态电解液，具有更高能量密度和安全性，不易燃，有望成为下一代电动汽车和便携设备的理想电源。  \r', '氢燃料电池通过氢氧电化学反应直接产生电能，只排出水，转换效率高，是零排放交通和分布式发电的重要技术方向。  \r', '钙钛矿太阳能电池利用有机-无机杂化材料作为吸光层，制备成本低、效率提升快，但稳定性仍有待改善，是光伏领域的研究热点。  \r', '染料敏化电池模拟光合作用，用染料捕获光能并激发电子，具有半透明和柔韧性特点，适用于建筑一体化光伏和可穿戴设备。  \r', '热光伏电池将热辐射转化为电能，可回收工业废热或配合热源发电，拓展了光伏利用的光谱范围，提升能源利用率。  \r', '地热发电利用地球内部热能加热地下水产生蒸汽，驱动涡轮机发电，资源稳定可再生，适合地热活跃区，碳排放极低。  \r', '潮汐能利用潮汐涨落的水位差推动水轮发电，可预测性强，对环境影响较小，目前已有商业化潮汐电站投入运行。  \r', '波浪能捕获海洋表面波浪的动能和势能，通过振荡水柱或浮子装置转换电能，虽然能量密度高，但设备耐腐蚀性要求严苛。  \r', '生物质气化将农林废弃物、秸秆等原料在缺氧条件下热解转化为可燃气体（如一氧化碳、氢气），用于发电或合成燃料。  \r', '智能电网集成数字通信和自动控制技术，实现电力供需的动态平衡、故障自我修复和可再生能源高效接入，是未来能源系统的骨干。  \r', '虚拟电厂通过物联网聚合分布式能源（光伏、储能、电动车），统一调度参与电力市场，提升电网灵活性和能源利用率。  \r', '压缩空气储能利用低谷电能将空气压缩储存在地下洞穴，用电高峰时释放驱动透平发电，适合大规模长时储能。  \r', '飞轮储能利用高速旋转的飞轮将电能转化为动能，充放电迅速、寿命长，适用于电网调频和UPS不间断电源。  \r', '超导磁储能利用超导线圈无电阻特性存储电磁能，响应毫秒级，功率密度高，但需低温制冷，目前成本较高。  \r', '液流电池将活性物质储存在外部电解液罐中，通过泵入电堆反应，适合大规模储能，循环寿命长，安全性好。  \r', '钠离子电池资源丰富、成本低，能量密度接近锂电，是锂资源短缺时代的重要替代方案，已在低速电动车和储能中应用。  \r', '锂硫电池以硫为正极，理论能量密度极高，但存在穿梭效应和体积膨胀问题，正处于研发突破阶段。  \r', '金属空气电池利用金属（如铝、锌）氧化反应与空气中的氧气反应，能量密度高，但充电效率低，适合一次电池场景。  \r', '温差发电利用热电材料的塞贝克效应，将温差直接转换为电能，可用于工业余热回收和太空探测器供电。  \r', '火星车是无人驾驶的移动探测平台，搭载科学仪器在火星表面行驶，分析土壤、岩石和大气，寻找水的痕迹和生命迹象。  \r', '韦伯望远镜是红外波段的大型空间望远镜，主镜直径6.5米，用于观测宇宙早期星系、系外行星和恒星形成，成果丰硕。  \r', '引力波天文台（如LIGO）使用激光干涉仪探测时空涟漪，已成功探测到双黑洞合并，开启了引力波天文学新时代。  \r', '凌星法通过监测恒星亮度周期性微降，推断行星的存在和大小，开普勒望远镜已发现数千颗系外行星，是主流的搜索方法。  \r', '小行星采矿旨在从小行星上提取铂族金属、水和稀有矿物，为深空探索提供资源，目前处于技术论证和前期勘察阶段。  \r', '太空电梯概念是利用超强缆绳将地球表面与地球静止轨道连接，通过机械升降机运送物资，可大幅降低发射成本，但材料强度是巨大挑战。  \r', '离子推力器通过电离惰性气体并加速喷出产生微推力，比冲高、寿命长，适用于深空探测器的主推进和姿态控制。  \r', '霍尔推力器利用霍尔效应加速等离子体，推力比离子推力器大，常用于卫星轨道提升和位置保持，已在多个航天器上应用。  \r', '太阳帆利用太阳光压提供持续推力，无需携带燃料，适合远距离轻量化任务，日本IKAROS和光帆2号已成功验证。  \r', '深空网络（DSN）是NASA构建的全球天线系统，与深空探测器通信，提供遥测、指令和测轨服务，是星际航行的生命线。  \r', '太空碎片清除技术包括机械臂抓取、网捕和激光烧蚀，旨在减少轨道垃圾，保护在轨航天器安全，目前有多个演示任务。  \r', '在轨服务指对卫星进行加注燃料、修理或升级，延寿和灵活调配，美国太空军和商业公司都在推进相关技术。  \r', '月球基地设想是建立永久性月球前哨，利用极地水冰制氧和燃料，作为深空探测的中转站，我国也有相关论证。  \r', '火星殖民指在火星建立自给自足的人类定居点，需解决辐射防护、食物生产和氧气循环，埃隆·马斯克正在推动星舰计划。  \r', '软体机器人由柔性材料制成，模仿章鱼、蚯蚓等生物，具有良好顺应性，能在狭窄或复杂环境中作业，如医疗夹爪。  \r', '仿生机器人模仿动物运动方式，如波士顿动力机械狗，具备高动态稳定性和越障能力，适用于巡检和救援。  \r', '群体机器人由多个简单个体协作完成复杂任务，受昆虫群体启发，可扩展性强，应用于搜索、环保和军事领域。  \r', '微型机器人尺寸在毫米至微米级，可进入人体血管或精细工业管道，通过磁场或光驱动，实现靶向递送和检测。  \r', '手术机器人（如达芬奇）以微创方式辅助医生操作，提供高精度、防手颤和三维视野，提高手术安全性和恢复速度。  \r', '外骨骼穿戴在人体外部，增强力量或辅助行走，用于康复训练、助老助残和军事负重，是多传感器融合的典型应用。  \r', '康复机器人通过重复训练和反馈帮助中风、脊髓损伤患者恢复运动功能，可调节阻抗和助力，提升治疗效果。  \r', '协作机器人（cobot）与工人共享工作空间，配备力觉和安全机制，适用于装配、焊接和码垛，提高产线柔性。  \r', 'SLAM（即时定位与地图构建）使机器人能在未知环境中实时建立地图并同步定位，是自主导航的核心算法。  \r', '无人机编队通过通信和协同控制，执行精确队形变换和任务分配，用于灯光秀、物资投送和精准农业。  \r', '自主水下机器人（AUV）无需缆线，自主航行，用于海底测绘、管道检查和海洋科考，工作深度可达数千米。  \r', '爬壁机器人利用吸附装置（真空或磁力）在垂直墙面移动，可用于清洗玻璃幕墙、检测大型储罐和桥梁。  \r', '管道机器人可在工业管道内行走，携带摄像头和传感器检测腐蚀、堵塞和泄漏，保障石化、市政设施安全。  \r', '仿生扑翼机模仿鸟类或昆虫的拍翼飞行，气动效率高，噪音低，适合隐蔽侦察和环境监测，是微型飞行器的重要方向。  \r', '柔性机械臂由连续结构或气动人工肌肉驱动，能弯曲和扭转，适应复杂抓取，具备本质安全，适合人机交互。  \r', '触觉传感器检测压力、剪切力和温度，赋予机器人“触感”，用于精密操作和虚拟现实反馈，常用压阻或电容原理。  \r', '基因测序技术（如二代测序）快速读取DNA碱基序列，助力疾病诊断、药物研发和个性化医疗，成本已大幅降低。  \r', 'CRISPR-Cas9是一种精准的基因剪刀，能在特定DNA位点进行敲除或插入，用于治疗遗传病、改良作物，但需伦理规范。  \r', '基因治疗将正常基因导入患者细胞，替代或修复缺陷基因，已用于治疗脊髓性肌萎缩症等罕见病，前景广阔。  \r', 'CAR-T疗法提取患者T细胞，改造使其识别癌细胞表面抗原，回输后杀伤肿瘤，已在血液肿瘤中取得显著疗效。  \r', '类器官是干细胞自组织的三维微器官模型，模拟真实器官的结构和功能，用于药物筛选和疾病建模，减少动物实验。  \r', '器官芯片是在微流控芯片上培养细胞，模拟器官生理微环境，用于毒性测试和药效评价，提高体外模型的预测性。  \r', '微流控芯片在微米尺度通道中操控微量液体，集成生物检测、反应和分离功能，是即时诊断（POCT）的核心技术。  \r', '生物打印利用3D打印技术将细胞和生物材料逐层构建成三维组织，可制造皮肤、软骨等，再生医学的变革工具。  \r', '电子皮肤是一类柔性传感器阵列，模拟人体皮肤的触觉、温度和湿度感知能力，用于机器人、假肢和可穿戴健康监测。  \r', '人工视网膜将光电信号转换为电脉冲刺激视神经，帮助失明患者恢复部分视觉，已出现植入式原型设备。  \r', '脑深部电刺激植入电极至特定脑区，发送电脉冲调节异常神经活动，用于治疗帕金森病、肌张力障碍等运动障碍。  \r', '经颅直流电刺激通过头皮电极施加微弱电流，调节大脑皮质兴奋性，用于抑郁症治疗和认知增强，安全性较高。  \r', '神经假肢与人体神经系统直接交互，通过解码运动意图控制机械臂，同时提供触觉反馈，提升截肢者的生活质量。  \r', '智能义肢内嵌微处理器和传感器，可感知步态和环境，自动调节阻尼和支撑，实现仿生行走和抓握。  \r', '生物传感器利用酶、抗体等生物识别元件，将目标分子浓度转化为电信号，用于血糖监测、病原体检测等。  \r', '可穿戴心电设备通过电极连续监测心电信号，检测心律失常和心肌缺血，结合AI预警，助力心血管疾病管理。  \r', '脑电图监测头皮电活动，用于癫痫诊断、睡眠分析和脑机接口，可穿戴版本已实现长时程日常监测。  \r', '肌电控制采集肌肉收缩产生的电信号，用于操控假肢、轮椅或游戏，实现自然的人机交互。  \r', '纳米药物递送利用脂质体、聚合物等纳米载体包裹药物，靶向肿瘤或病变部位，减少毒副作用，提高疗效。  \r', '石墨烯是单层碳原子二维材料，具有超高强度、导电性和导热性，应用于晶体管、传感器和复合材料，前景广阔。  \r', '碳纳米管是卷成圆柱形的石墨烯片，强度高、导电优异，用于纳米电子、结构增强和透明导电薄膜。  \r', '富勒烯由碳原子组成球状或笼状结构，如C60，具有独特电子性质，可用于超导材料、润滑剂和抗氧化剂。  \r', '二硫化钼是一种过渡金属硫族化合物，具有类似石墨烯的层状结构，具有可调带隙，适合光电子和催化应用。  \r', '拓扑绝缘体内部绝缘但表面导电，其导电态受拓扑保护，对杂质不敏感，是量子计算和自旋电子学的潜在材料。  \r', '高温超导材料在液氮温度下呈现零电阻，如铜氧化物，用于强磁体、磁悬浮和能量传输，但机理尚待厘清。  \r', '形状记忆合金（如镍钛合金）在受热后能恢复预设形状，用于医疗支架、驱动器，具有超弹性和记忆效应。  \r', '非晶合金（金属玻璃）冷却时原子排列无序，具有高强度、高韧性和优异磁性，用于变压器铁芯和精密部件。  \r', '碳纤维增强复合材料以树脂为基体，碳纤维为增强体，比强度高、耐疲劳，广泛用于航空、汽车和体育器材。  \r', '气凝胶是密度极低的纳米多孔材料，隔热、隔音性能卓越，可用于航天保温、环境吸附和催化剂载体。  \r', '自修复材料在受损后能自行恢复结构或功能，如微胶囊释放修复剂，或动态共价键重排，延长材料寿命。  \r', '压电材料在受力时产生电荷，反之施加电场产生变形，用于传感器、制动器和超声换能器，如锆钛酸铅。  \r', '铁电材料具有自发极化且可由外电场翻转，用于非易失性存储器和红外热探测，如钛酸钡。  \r', '热电材料将温差直接转换为电能，或通电产生温差，可用于废热回收和制冷，如碲化铋合金。  \r', '光学超材料通过人工亚波长结构实现负折射、隐形等超常光学特性，用于超透镜、光栅和天线设计。  \r', '隐身材料吸收或偏转雷达波，减少目标雷达散射截面，用于军事隐身，有涂覆型和结构型两种。  \r', '阻燃材料通过添加阻燃剂或化学结构改性，延缓燃烧或抑制火焰蔓延，保障电子设备和建筑安全。  \r', '生物可降解塑料（如PLA）在特定环境中能被微生物分解，减少白色污染，适用于包装和农业地膜。  \r', '木质素是植物中天然酚类聚合物，可通过化学转化制备碳纤维、酚醛树脂和芳香化学品，实现生物质全利用。  \r', 'MEMS陀螺仪利用微机械振动测量角速度，体积小、成本低，用于手机防抖、无人机稳像和汽车稳定控制。  \r', 'MEMS麦克风采用微型薄膜感应声压，输出数字信号，广泛应用于手机、耳机和智能音箱，占主导地位。  \r', '光纤光栅传感器在光纤中刻写周期性结构，反射波长随应变或温度变化，用于桥梁、大坝等结构健康监测。  \r', '分布式光纤传感利用散射光（如布里渊）连续测量光纤沿线温度或应变，空间分辨率达米级，适合长距离管道监测。  \r', '激光雷达（LiDAR）发射激光脉冲并接收反射，测量目标距离和轮廓，用于自动驾驶、地形测绘和大气探测。  \r', '毫米波雷达工作在30-300GHz频段，抗干扰能力强，可测距、测速，广泛用于汽车防撞和近程目标识别。  \r', '超声波传感器发射高频声波，通过回波时间测距，常用于机器人避障、液位计和医学超声成像。  \r', '红外热像仪探测物体表面热辐射，将其转换为温度分布图像，用于夜视、设备故障诊断和医学检查。  \r', '量子传感器利用量子态（如原子干涉）测量物理量，精度极高，用于重力测量、磁场探测和惯性导航。  \r', '磁力计测量地球磁场或环境磁场，用于电子指南针、磁场异常检测和地磁导航，常见有磁通门和霍尔效应型。  \r', '气味传感器阵列（电子鼻）通过交叉响应识别气味指纹，用于食品安全、环境监测和疾病呼气诊断。  \r', '触觉传感阵列由密集的力敏单元组成，可获取接触面压力分布，用于机器人抓取和触摸屏交互。  \r', '可见光通信（Li-Fi）利用LED灯高频闪烁传输数据，速率高、保密好，适合室内和电磁敏感环境。  \r', '太赫兹通信利用0.1-10THz频段，实现超高速无线传输，但面临路径损耗和器件瓶颈，是6G潜在方案。  \r', '水下声学通信采用声波传输信息，速度慢但传播距离远，用于海洋科考、潜水器控制和潜艇通信。  \r', '卫星激光通信利用激光束在星间或星地传输，带宽大、干扰小，但需高精度跟踪，已有在轨演示。  \r', '中继卫星位于高轨，转发低轨航天器信号到地面站，扩大通信覆盖，如中国的天链系统。  \r', '自组织网络是无中心基础设施的移动网络，节点自配置、自修复，适合应急通信和战场环境。  \r', '认知无线电能感知空闲频谱并动态接入，提高频谱利用效率，是解决频谱资源紧张的关键技术。  \r', '软件定义无线电通过软件实现调制解调和信号处理，硬件通用，易于升级和多模式通信。  \r', '智能反射面由大量可调反射单元组成，通过调整相位被动增强或抑制信号，改善无线覆盖和容量。  \r', '6G网络将实现空天地海一体化，融合通信、感知和计算，支持沉浸式体验和数字孪生，预计2030年商用。  \r', '反渗透海水淡化利用高压使水透过半透膜，阻挡盐分，是目前主流技术，能耗逐步降低。  \r', '电渗析使用离子交换膜和电场，驱动盐离子迁移，适用于苦咸水淡化，能耗较低。  \r', '碳捕集与封存（CCS）从工业烟气中分离CO₂，压缩后注入深层地质层封存，减少温室气体排放。  \r', '直接空气捕集（DAC）直接从大气中捕获CO₂，使用化学吸附剂或膜，成本较高，但可制造负排放。  \r', '生物炭由生物质在缺氧条件下热解制成，施入土壤可增加碳固存和肥力，是一种气候负技术。  \r', '人工光合作用模拟植物将水和CO₂在光下转化为燃料（如氢气或甲醇），是清洁能源的长期方向。  \r', '垂直农场在多层建筑内采用LED光照和水培，进行全年无土栽培，节约土地和水，适合城市供应。  \r', '植物工厂是完全人工环境下的作物生产系统，精确调控光温湿，产高质优，不受季节影响。  \r', '细胞培养肉从动物干细胞体外扩增，分化为肌肉和脂肪组织，无需屠宰，减少环境足迹。  \r', '昆虫蛋白从黑水虻、蟋蟀等提取，蛋白质含量高，养殖效率超传统畜牧，可作为饲料和食品补充剂。  \r', '海洋塑料降解研究利用微生物酶或光化学方法分解聚酯类塑料，有望减轻海洋塑料污染。  \r', '微塑料检测通过拉曼光谱、流式细胞术等技术识别水中纳米至微米级塑料颗粒，是环境监测新热点。  \r', '光催化空气净化利用二氧化钛等光触媒，在紫外光下分解甲醛、VOCs等有害气体，净化效率高。  \r', '土壤修复包括植物修复、微生物修复和化学钝化，用于清除重金属和有机污染物，恢复耕地功能。  \r', '人工湿地利用植物和微生物自然净化污水，兼具生态景观和栖息地功能，低碳可持续。  \r', '气候模型基于物理方程模拟大气、海洋和冰圈相互作用，预测未来温度和降水，为政策提供科学依据。  \r', '增材制造（3D打印）逐层堆叠材料制造零件，设计自由，缩短研发周期，广泛应用于航空、医疗和模型制作。  \r', '激光粉末床熔融（LPBF）是金属3D打印主流技术，高能激光熔化金属粉末，构建致密复杂结构。  \r', '电子束熔融（EBM）使用电子束在真空中熔化金属粉末，适合钛合金等活性材料，残余应力较低。  \r', '定向能量沉积（DED）将金属粉末或丝材送入熔池，由激光或电子束加热，适合大型零件修复和混合制造。  \r', '冷喷涂利用高速气流使金属颗粒在低温下塑性变形堆积，不产生热相变，适合热敏材料和涂层制备。  \r', '数控加工（CNC）由计算机控制机床刀具轨迹，实现高精度切削，是现代制造的核心技术。  \r', '工业机器人编程有示教、离线编程和自适应控制，用于焊接、喷涂、装配，提高生产自动化水平。  \r', '预测性维护利用传感器数据和机器学习预测设备故障，减少非计划停机，优化维护计划。  \r', '柔性制造系统集成数控机床、机器人和传送带，能快速切换产品型号，适应多品种小批量生产。  \r', '计算机集成制造（CIM）将设计、工艺、生产和管理信息化，实现全流程数据闭环和智能决策。  \r', '量子纠缠是两粒子间的一种关联，无论距离远近，测量一个会瞬间影响另一个，是量子通信和计算的基础资源。  \r', '量子隐形传态利用纠缠将未知量子态从一个粒子传输到另一个，无需物理载体，是远距离量子网络的关键。  \r', '量子退火是一种利用量子隧穿效应寻找最优化解的计算方法，D-Wave公司已实现商业化，用于组合优化。  \r', '量子体积是衡量量子计算机性能的指标，同时考虑量子比特数、错误率和连通性，反映实际计算能力。  \r', '表面码是一种容错量子纠错方案，将量子比特排列在二维网格，通过测量稳定子检测和修正错误。  \r', '中微子在飞行过程中会从一种味变为另一种味，说明其有非零质量，对标准模型修正有重要意义。  \r', '暗物质探测通过直接（XENON）、间接（伽马射线）或对撞机方式，寻找不可见物质粒子，是天体物理前沿。  \r', '引力波探测使用激光干涉仪（如LIGO）测量时空弯曲引起的微小长度变化，验证广义相对论预言。  \r', '大型强子对撞机（LHC）是位于CERN的粒子加速器，通过质子对撞寻找希格斯粒子和新物理，周长27公里。  \r', '超导对撞机（如SSC）曾计划采用超导磁体达到更高能量，但因成本取消，但技术为未来机器提供基础。  \r', '宇宙微波背景辐射是大爆炸遗留下来的热辐射，均匀分布在宇宙，揭示宇宙早期状态和组分。  \r', '暗能量是驱动宇宙加速膨胀的神秘成分，占总能量约70%，其本质尚不清楚，是宇宙学最大谜题。  \r', '哈勃常数描述宇宙膨胀速率，通过星系退行速度与距离关系测定，不同测量方法有差异，引发“哈勃张力”问题。  \r', '星震学通过测量恒星表面振荡，反推内部结构和年龄，是研究恒星演化和系外行星宿主的重要工具。  \r', '太阳中微子是太阳内部核聚变反应产生的，中微子探测帮助验证太阳模型，曾解决“太阳中微子缺失”问题。  \r', '反物质由反质子、正电子等构成，与物质相遇会湮灭产生能量，是粒子物理和科幻能源的热门话题。  \r', '磁单极子是理论上仅带单一磁极的粒子，尚未被发现，但若存在将改写电磁理论基础。  \r', '直接成像法通过遮挡恒星光直接拍摄行星，可获得光谱信息，已捕捉到数颗年轻巨行星。  \r', '引力透镜效应是质量天体弯曲光线，产生多重像或弧，可用于研究暗物质和背景星系。  \r', '快速射电暴是持续毫秒的强射电脉冲，起源不明，可能与磁星、黑洞或外星文明有关，是当前天文学热点。  \r', '超新星是大质量恒星塌缩爆炸，释放巨量能量，产生重元素，是宇宙化学演化的关键事件。  \r', '伽马射线暴是来自宇宙深处的短暂高能辐射，分为长暴和短暴，可能与大质量恒星塌缩或双致密星合并有关。  \r', '中子星是超新星遗迹，质量与太阳相当但半径仅十公里，密度极高，自转快，部分为脉冲星。  \r', '脉冲星自转极其稳定，可用作计时基准，甚至探测引力波，利用脉冲星阵列可检测纳赫兹引力波。  \r', '黑洞吸积盘是围绕黑洞旋转的气体盘，因摩擦加热发出强辐射，是类星体活动的能量来源。  \r', '星云是星际气体和尘埃云，在引力作用下可塌缩形成新恒星和行星，是恒星诞生的摇篮。  \r', '行星形成主流模型为“核吸积”，从星子碰撞聚集成行星胚胎，然后吸积气体形成巨行星。  \r', '小行星带位于火星和木星之间，可能是未能形成行星的原行星碎片，受到木星引力扰动而分化。  \r', '彗星由冰、尘埃和有机分子组成，保留太阳系早期信息，罗塞塔任务探测了彗星67P，发现复杂有机物。  \r', '日球层是太阳风影响的巨大气泡，保护太阳系免受星际辐射，其边界由旅行者号探测到。  \r', '火星曾有过浓厚大气和液态水，因磁场丧失被太阳风剥离，研究其演化有助于理解行星宜居性变化。  \r', '木星有众多卫星，其中伽利略卫星（木卫一至四）最为著名，木卫二可能拥有地下海洋，是地外生命候选地。  \r', '土星环由冰粒和岩石组成，有无数细环，其形成可能与卫星被潮汐撕裂有关，卡西尼号提供了详尽数据。  \r', '天王星自转轴几乎倒在轨道平面上，可能是远古时期与大型天体碰撞导致，具有独特季节变化。  \r', '海王星拥有太阳系最快风速，达2100公里/小时，其大暗斑类似木星大红斑，是动态气候体现。  \r', '矮行星（如冥王星）满足绕太阳运转但未清除轨道邻居，其特性介于行星和小行星之间，新视野号揭密。  \r', '柯伊伯带位于海王星轨道外，充满冰质小天体，是短周期彗星的来源，冥王星是其最大成员。  \r', '奥尔特云是围绕太阳系的巨大冰物体球层，是长周期彗星来源，距太阳约1光年，尚未直接观测。  \r', '引力波天文学通过探测引力波研究致密天体合并、中子星并合等极端事件，开启多信使时代。  \r', '中微子天文学利用中微子探测高能天体源（如活动星系核），冰立方和中微子望远镜是主要工具。  \r', '暗物质候选粒子包括弱相互作用大质量粒子（WIMP）、轴子和超对称粒子，各自有不同探测方案。  \r', '希格斯粒子是标准模型预言粒子，赋予其他粒子质量，2012年在LHC被发现，验证了对称性破缺机制。  \r', '标准模型描述基本粒子和三种相互作用（电磁、弱、强），但未包括引力，是粒子物理的成功理论。  \r', '弦理论将基本粒子视为振动的弦，试图统一引力和量子力学，但尚待实验验证，是前沿理论。  \r', 'M理论是弦理论的拓展，包含11维，可统一五种弦理论，是追求万物理论的候选方案。  \r', '宇宙暴胀是早期宇宙在极短时间内指数膨胀，解释平坦性和均匀性，其细节可通过原初引力波探测。  \r', '原初引力波是暴胀时期产生的引力波背景，BICEP实验试图探测，但受银河尘埃干扰，尚待确认。  \r', '星系形成从暗物质晕开始，气体冷却并塌缩，最终聚集恒星，模拟和观测揭示其层级演化。  \r', '活动星系核（AGN）由中心超大质量黑洞吸积物质产生强烈辐射，分为类星体、塞弗特星系等类型。  \r', '事件视界望远镜（EHT）拍摄了M87和银河系中心黑洞阴影图像，验证广义相对论，标志黑洞成像时代。  \r', '引力红移是光在强引力场中频率降低，是广义相对论的经典预言，通过地面实验精确验证。  \r', '时间膨胀分狭义和广义，速度或引力都会使时间变慢，GPS需考虑此效应以保持精确。  \r', '惯性约束聚变用强激光或粒子束照射氘氚靶，使其瞬间压缩并点火，国家点火设施正在进行实验。  \r', '磁约束聚变（如托卡马克）利用强磁场将高温等离子体束缚，ITER工程正在建设，目标是商用电站。  \r', '聚变堆材料需承受极高中子通量和高温，如钨、铍和低活化钢，是核聚变工程的核心难题。  \r', '增殖反应堆将非裂变材料（如铀-238）转化为可裂变钚-239，提高核燃料利用率，但成本和安全受关注。  \r', '第四代反应堆包括高温气冷、液态金属冷却等，具有固有安全性和核废料减少特征，我国已有示范工程。  \r', '小型模块化反应堆（SMR）体积小、可工厂预制，部署灵活，适合偏远地区和特殊用途，全球多家公司研发。  \r', '核废料玻璃固化是将放射性废物与玻璃基体熔融，形成稳定固体，安全地质处置，是后处理关键步骤。  \r', '质子交换膜电解水（PEM）用纯水和电能制氢，响应快、效率高，适合与可再生能源耦合制绿氢。  \r', '固体氧化物电解池（SOEC）在高温下电解水蒸汽，热力学效率高，可利用工业余热，处于示范阶段。  \r', '甲醇燃料电池直接以甲醇为燃料，液体方便储运，适用于便携电源和偏远基站，但性能需优化。  \r', '光催化制氢利用半导体材料在光照下分解水产生氢气，是太阳能到化学能的直接转化，效率尚待突破。  \r', '生物制氢通过藻类或细菌发酵产生氢气，利用有机废物，兼具环保和能源回收潜力。  \r', '锂离子电池回收技术包括湿法冶金和火法，提取锂、钴、镍等有价金属，减少资源依赖和环境负荷。  \r', '电池热管理通过风冷、液冷或相变材料控制电池组温度，防止热失控，保障安全和寿命。  \r', '快速充电技术通过高功率充电桩和优化电池材料，缩短充电时间，但需兼顾电池寿命和电网负荷。  \r', '无线充电采用电磁感应或磁共振方式，无需插拔，适用于电动车和消费电子，但效率有待提升。  \r', '储能系统安全性涉及电池热失控、过充过放和电气保护，需多级防护措施，如BMS和阻燃外壳。  \r', '分布式发电指在用户附近安装光伏、风机等小规模电源，减少传输损耗，提高能源自给率。  \r', '微电网是独立可控的小型发配用电系统，可并网或孤岛运行，提高供电可靠性和可再生能源渗透率。  \r', '需求响应通过价格激励或控制信号，引导用户调整用电行为，平衡电网负荷，提升系统经济性。  \r', '能源互联网将能源系统与互联网深度融合，实现信息流和能量流双向交互，优化全局调度。  \r', '建筑节能技术包括高效保温、智能照明、热回收和光伏一体化，可大幅降低运营能耗和碳排放。  \r', '被动式房屋通过超强保温、气密性设计和太阳能利用，几乎无需主动采暖制冷，能耗极低。  \r', '智能照明采用LED和传感器，自动调节亮度和色温，结合人体存在检测，节能且护眼。  \r', '热泵从空气、水或土壤取热，用少量电能驱动压缩机制热或制冷，效率优于电加热，广受推广。  \r', '冰蓄冷空调在夜间电价低时制冰，白天融冰供冷，移峰填谷，降低运行费用和电力高峰压力。  \r', '绿色数据中心采用高效IT设备、自然冷却和余热回收，降低PUE值，减少碳排放和运营成本。  \r', '低温差发电利用有机朗肯循环（ORC），将80℃以上的低温余热转化为电能，应用于工业废热。  \r', '振荡水柱（OWC）利用波浪起伏推动空气涡轮发电，结构简单，已有多座并网示范装置。  \r', '潮汐泻湖发电在海岸建坝，利用潮差蓄水发电，同时可兼作海堤和交通，提高综合效益。', '微信是腾讯公司开发的即时通讯和社交平台，支持文字、语音、视频通话，朋友圈分享，公众号阅读，移动支付及小程序生态，是中国最全面的超级应用。  \r', '支付宝是蚂蚁集团旗下的第三方支付平台，提供在线支付、转账、理财、生活缴费、信用评分（芝麻信用）等功能，广泛用于电商和线下扫码支付。  \r', 'QQ是腾讯推出的老牌即时通讯软件，支持聊天、文件传输、QQ空间、游戏中心、直播和兴趣群组，拥有丰富的个性化装扮和社交娱乐功能。  \r', '微博是新浪公司运营的社交媒体平台，用户可发布短文本、图片和视频，关注明星、大V和热点话题，实现信息快速传播和公共讨论。  \r', '抖音是字节跳动开发的短视频社交应用，以15秒至数分钟的创意视频为主，依托算法推荐兴趣内容，集音乐、特效、直播和电商于一体。  \r', '快手是北京快手科技旗下的短视频和直播平台，强调记录生活，覆盖老铁文化、三农内容、才艺展示和电商带货，用户群体广泛且下沉。  \r', '钉钉是阿里巴巴打造的企业协作与办公沟通工具，提供即时通讯、视频会议、考勤审批、文档协作和任务管理，专为中小企业数字化服务。  \r', '企业微信是腾讯推出的企业级通讯应用，与微信互通，支持内部沟通、客户联系、日程安排、审批汇报和云文件管理，提升办公效率。  \r', '飞书是字节跳动旗下的一站式协作平台，集聊天、日历、在线文档、视频会议和项目管理于一体，强调高效沟通和知识沉淀，适合现代团队。  \r', 'Telegram是一款注重安全和速度的跨平台即时通讯软件，支持端到端加密秘密聊天、频道广播、机器人API和云存储，广受全球极客喜爱。  \r', 'WhatsApp是Meta旗下的即时通讯应用，以手机号绑定，提供免费文本、语音、视频通话和媒体分享，端到端加密，全球用户超过20亿。  \r', 'Line是日本NHN旗下流行的通讯软件，以可爱的贴图表情著称，支持聊天、语音视频、动态消息和支付功能，在亚洲多国拥有庞大用户群。  \r', 'Signal是一款开源加密通讯应用，提供端到端加密的文本、语音和视频通话，注重隐私保护，被爱德华·斯诺登等安全专家推荐使用。  \r', 'Microsoft Word是微软Office套件中的文字处理软件，支持文档创建、排版、表格、图片插入、审阅修订和云端存储，是最主流的办公写作工具。  \r', 'Microsoft Excel是微软Office中的电子表格软件，具备数据录入、公式计算、图表制作、透视分析和宏编程功能，广泛用于财务和数据分析。  \r', 'Microsoft PowerPoint是微软Office的演示文稿工具，支持幻灯片设计、动画切换、多媒体插入和演讲者模式，用于制作专业汇报和教学课件。  \r', 'Microsoft Outlook是微软Office的邮件客户端和个人信息管理器，集邮件收发、日历、联系人、任务和笔记于一体，常用于企业办公协作。  \r', 'WPS文字是金山软件推出的办公套件中的文字处理模块，兼容Word格式，提供丰富的模板、云同步和PDF转换功能，在国产办公中广泛使用。  \r', 'WPS表格是金山软件WPS套件中的电子表格工具，支持复杂公式、数据筛选、图表制作和多种文件格式导入，适合日常统计和数据处理。  \r', 'WPS演示是金山软件WPS套件中的幻灯片制作软件，内置大量模板和动画效果，支持团队协作和云保存，用于商业展示和教学演示。  \r', 'Google Docs是谷歌提供的在线文字处理工具，支持多人实时协作编辑、评论建议、版本历史，自动保存至Google Drive，适合远程团队写作。  \r', 'Google Sheets是谷歌在线的电子表格应用，支持实时协作、公式、图表和宏脚本，可与外部数据连接，用于团队数据分析和项目管理。  \r', 'Google Slides是谷歌的在线演示文稿工具，支持多人同时编辑、嵌入视频、主题模板，并可在线演示和远程共享，适合无纸化会议展示。  \r', 'Notion是一款集笔记、数据库、看板、wiki和任务管理于一体的工作平台，支持模块化页面和丰富嵌入，适合个人知识管理和团队协作空间。  \r', 'OneNote是微软推出的数字笔记本应用，支持手写、录音、图片和文本混排，多级分区和标签整理，可同步至云端，适合课堂笔记和会议记录。  \r', 'Evernote是老牌笔记软件，支持文字、图片、语音和网页剪辑，通过标签和笔记本组织内容，跨平台同步，广泛用于个人知识收集和任务提醒。  \r', '印象笔记是Evernote的中国本地化版本，提供笔记记录、模板、文档扫描和协作空间，优化中文搜索和办公集成，适合国内用户的知识管理。  \r', '有道云笔记是网易推出的笔记工具，支持多端同步、手写识别、语音转文字和Markdown编辑，内置OCR文字提取，常用于学生和职场人士。  \r', 'Visual Studio Code是微软开发的免费开源代码编辑器，支持多语言语法高亮、智能提示、调试、Git集成和丰富的插件扩展，是开发者的首选工具。  \r', 'IntelliJ IDEA是JetBrains出品的Java集成开发环境，提供智能代码补全、重构、版本控制支持和大量框架插件，被公认为最智能的Java IDE。  \r', 'Eclipse是开源的多语言IDE，以Java开发闻名，支持插件体系、代码导航、调试和构建工具，广泛应用于企业级Java和Android开发。  \r', 'PyCharm是JetBrains专门为Python设计的IDE，提供代码分析、调试、单元测试、Web开发支持和远程解释器，适合数据科学和Web项目。  \r', 'Jupyter Notebook是交互式计算笔记本，支持Python、R等语言，可在浏览器中编写代码、运行并嵌入图文和可视化，常用于数据分析和教学。  \r', 'Anaconda是Python和R的数据科学发行版，包含conda包管理器、Jupyter、Spyder等工具，预装数百个科学库，简化环境配置和依赖管理。  \r', 'Git是分布式版本控制系统，由Linus Torvalds创建，支持离线提交、分支管理和协作合并，是软件开发中代码托管和团队协同的基础工具。  \r', 'GitHub Desktop是GitHub官方桌面客户端，提供图形化界面管理Git仓库，支持克隆、提交、推送和拉取，简化Git命令行操作，适合新手。  \r', 'Sourcetree是Atlassian提供的免费Git和Mercurial图形客户端，支持可视化版本历史、分支图和冲突解决，方便开发者管理多个代码仓库。  \r', 'Postman是API开发和测试工具，支持发送HTTP请求、管理环境变量、生成文档和模拟服务器，广泛用于前后端协作和接口自动化测试。  \r', 'Docker Desktop是容器化平台的桌面客户端，提供轻量级虚拟化环境，可构建、运行和管理容器镜像，简化应用部署和开发环境一致性。  \r', 'VirtualBox是Oracle开源的虚拟机管理软件，支持在主机上运行多种操作系统，提供快照、共享文件夹和网络桥接，适合测试和虚拟化学习。  \r', 'VMware Workstation是专业虚拟机软件，支持多系统同时运行，具备快照、克隆和高级网络配置，广泛用于开发测试和企业桌面虚拟化。  \r', 'Adobe Photoshop是专业图像编辑软件，提供图层、滤镜、调色、抠图和矢量绘图功能，是平面设计、摄影后期和数字绘画的行业标准。  \r', 'Adobe Illustrator是矢量图形设计软件，用于标志、字体、插画和排版，支持精确的路径控制，与Photoshop协同，是设计界的核心工具。  \r', 'Adobe Premiere Pro是专业视频剪辑软件，支持多轨道编辑、特效、颜色校正和音频混音，可导出多种格式，广泛用于影视和自媒体制作。  \r', 'Adobe After Effects是动态图形和视觉特效软件，用于制作动画标题、粒子效果和合成，与Premiere配合，是影视后期的重要工具。  \r', 'Adobe Lightroom是摄影师专用的照片管理和后期软件，提供调色、镜头校正、云同步和批量处理，支持RAW文件，适合数字暗房工作流。  \r', 'Figma是基于云端的UI/UX设计工具，支持实时协作、组件化设计和原型交互，可跨平台使用，是团队产品设计的主流工具。  \r', 'Sketch是macOS平台的专业矢量界面设计软件，专注移动端和网页UI设计，拥有丰富的插件和符号库，广受设计师喜爱。  \r', 'Adobe XD是一站式UX/UI设计工具，支持线框、原型制作和共享，可与Adobe家族集成，用于网站和移动应用的快速设计迭代。  \r', 'Blender是开源免费的三维创作套件，支持建模、雕刻、动画、渲染和视频编辑，拥有Cycles和Eevee渲染器，适合独立创作者和CGI艺术。  \r', 'Maya是Autodesk出品的专业三维动画软件，擅长角色绑定、动力学模拟和渲染，广泛应用于电影、游戏和动画制作，是行业标准之一。  \r', 'ZBrush是数字雕刻和绘画软件，使用独特的像素技术，支持高精度细节雕刻和纹理绘制，常用于游戏角色和电影生物模型制作。  \r', 'AutoCAD是Autodesk开发的计算机辅助设计软件，用于建筑、工程和机械领域的2D/3D制图，提供精确的尺寸标注和图层管理。  \r', 'SolidWorks是达索系统旗下的三维CAD设计软件，专注于机械设计和产品工程，支持参数化建模、装配仿真和工程图生成。  \r', 'VLC是开源免费的跨平台媒体播放器，支持几乎所有音视频格式，可播放光盘、流媒体和本地文件，具有字幕同步和简单编辑功能。  \r', 'PotPlayer是韩国Kakao出品的轻量级播放器，支持高清晰度视频、3D播放、直播源和自定义皮肤，以解码能力强大著称。  \r', 'OBS Studio是免费开源的录屏和直播软件，支持多场景、来源捕获、音频混音和推流，是游戏主播和网课制作的首选工具。  \r', 'Audacity是开源音频编辑软件，支持录音、剪切、混音、降噪和多种效果插件，可导出多种音频格式，适合播客和音乐基础编辑。  \r', 'Adobe Audition是专业音频工作站的软件，提供多轨道编辑、波形修复、声音处理和混音，适用于广播、电影和播客的音效制作。  \r', 'FL Studio是水果音乐制作软件，以编曲、混音和电子音乐制作著称，拥有强大的钢琴卷帘和合成器，是音乐制作人的常用工具。  \r', 'Ableton Live是专为电子音乐现场表演和制作设计的软件，支持非线性编排、实时效果和MIDI控制，深受电子音乐人喜爱。  \r', 'Logic Pro是苹果公司开发的专业音乐制作软件，内置大量虚拟乐器和效果器，支持录音、编曲和混音，是Mac平台的主流DAW。  \r', 'GarageBand是苹果免费的入门级音乐创作软件，提供智能乐器、循环乐段和吉他音箱模拟，适合初学者制作音乐和播客录制。  \r', 'Google Chrome是谷歌开发的网页浏览器，以快速、简洁和扩展丰富著称，支持多用户同步和沙箱安全，全球市场占有率最高。  \r', 'Mozilla Firefox是开源浏览器，注重隐私保护和自由定制，提供跟踪防护和强大扩展生态，是注重网络自由的用户首选。  \r', 'Microsoft Edge是微软基于Chromium内核的浏览器，集成阅读模式、收藏集、垂直标签和PDF阅读，与Windows生态深度结合。  \r', 'Apple Safari是苹果设备的默认浏览器，以高效节能和隐私保护为特色，支持iCloud同步和阅读列表，是macOS/iOS用户的首选。  \r', 'Opera是挪威出品的浏览器，内置免费VPN、广告拦截和侧边栏聊天，支持智能加速和游戏模式，特色功能丰富，适合探索用户。  \r', '百度网盘是百度提供的云存储服务，支持文件上传、下载、分享和备份，提供超大容量和在线解压，是中国最常用的个人云盘之一。  \r', '阿里云盘是阿里巴巴推出的云存储产品，主打高速上传下载和隐私保护，支持文件管理、相册备份和分享，提供较大免费空间。  \r', 'OneDrive是微软的云存储服务，深度集成Windows和Office，支持文件自动备份、版本历史和共享，方便跨设备访问个人资料。  \r', 'Google Drive是谷歌的云存储平台，与Docs、Sheets等办公套件结合，支持在线协作和第三方应用，提供15GB免费空间。  \r', 'Dropbox是全球知名的云同步和文件共享服务，以简单、稳定和安全著称，支持历史版本恢复和团队协作，适合跨平台文件管理。  \r', 'iCloud是苹果公司的云服务，用于同步照片、联系人、日历和文件，支持设备备份和“查找”功能，是苹果生态无缝衔接的核心。  \r', '腾讯微云是腾讯旗下的云盘应用，支持文件备份、在线预览和分享，与QQ、微信联动，提供相册自动备份和智能分类。  \r', '115网盘是国内老牌云存储平台，以离线下载、大空间和视频在线播放著称，支持磁力链接和种子下载，深受资源收藏者喜爱。  \r', '7-Zip是免费开源的高压缩率文件归档工具，支持7z、ZIP、RAR等多种格式，具有AES-256加密和自解压功能，轻量高效。  \r', 'WinRAR是著名的压缩管理软件，支持RAR和ZIP格式，提供高压缩比、分卷压缩和恢复记录，拥有图形界面和命令行模式。  \r', 'Bandizip是韩国开发的轻量级解压软件，支持多种格式，简洁美观，具备智能解压和预览功能，免费版无广告，深受用户喜爱。  \r', 'TeamViewer是远程控制软件，支持跨平台远程桌面、文件传输和会议，无需公网IP，广泛用于远程办公和IT技术支持。  \r', 'AnyDesk是高速远程桌面软件，以低延迟和高画质著称，支持跨平台和临时会话，适合轻量级远程连接和协助。  \r', '向日葵是上海贝锐开发的远程控制软件，集远程桌面、文件传输、开机棒和监控于一体，提供国内优化和硬件方案，适合企业运维。  \r', 'ToDesk是国内流行的远程协助工具，支持多平台连接、高帧率和隐私模式，操作简单，适合个人和团队的快速远程办公。  \r', 'CCleaner是系统清理和优化工具，可清理浏览器缓存、临时文件和注册表错误，支持软件卸载和启动项管理，提升电脑运行速度。  \r', 'Everything是Windows平台下的极速文件搜索工具，基于NTFS索引，可即时搜索文件名，支持正则和过滤，比系统自带的搜索快很多。  \r', 'Listary是Windows文件管理增强工具，提供全局搜索和快捷跳转，集成打开对话框和历史记录，大幅提高文件查找和打开效率。  \r', 'MySQL是开源关系型数据库管理系统，使用SQL语言，支持事务、索引和存储过程，是Web应用最流行的数据库之一，常与PHP搭配。  \r', 'PostgreSQL是功能强大的开源对象关系数据库，支持复杂查询、外键和JSON，具有高扩展性和标准符合性，适合企业级数据存储。  \r', 'MongoDB是文档型NoSQL数据库，使用JSON-like格式存储数据，支持动态模式和水平扩展，适合非结构化数据和高并发应用。  \r', 'Redis是内存数据结构缓存系统，支持键值、哈希、列表和集合，提供持久化和发布订阅，广泛用于缓存、消息队列和实时统计。  \r', 'Elasticsearch是基于Lucene的分布式搜索和分析引擎，支持全文检索、聚合分析和近实时数据展示，常用于日志和APM监控。  \r', 'Nginx是高性能的HTTP和反向代理服务器，支持负载均衡、缓存和动静分离，以异步事件驱动架构，高并发下性能卓越。  \r', 'Apache HTTP Server是开源的Web服务器，支持模块化扩展和多种语言接口，是LAMP架构的核心，经典稳定且功能丰富。  \r', 'Trello是基于看板的项目管理工具，以列表和卡片组织任务，支持标签、截止日期、附件和团队成员协作，简单直观。  \r', 'Asana是项目管理平台，提供任务分配、时间线、项目视图和工作流自动化，适合复杂项目跟踪，帮助团队高效协同。  \r', 'Slack是团队沟通协作软件，支持频道、私信、文件共享和集成数百种工具，可创建工作流，是企业内部信息流转的中心。  \r', 'Microsoft Teams是微软集成的聊天、会议和协作平台，与Office深度捆绑，支持群组沟通、在线会议和文件共同编辑，适合大型企业。  \r', 'Zoom是云视频会议软件，提供高清音视频、屏幕共享、分组讨论和虚拟背景，稳定性强，广受教育和商业会议青睐。  \r', '腾讯会议是腾讯推出的视频会议应用，支持多达数百人同时在线，提供美颜、虚拟背景和录制功能，与微信、企业微信互通。  \r', 'Google Meet是谷歌的企业级视频会议服务，支持实时字幕、背景替换和日历集成，可直接从Gmail发起，安全可靠。', '英雄联盟是Riot Games开发的MOBA竞技网游，5v5推塔对战，拥有超百位英雄和成熟电竞赛事，是全球玩家最多的团队竞技游戏之一。  \r', '无畏契约是Riot Games的5v5战术射击游戏，攻防围绕爆能器展开，每位特工有独特技能，强调枪法与技能配合，竞技性极强。  \r', '穿越火线是经典第一人称射击网游，提供爆破、团队竞技、生化等多种模式，手感爽快，曾是国内网吧最火的FPS游戏。  \r', '地下城与勇士是横版格斗RPG，玩家选择鬼剑士等职业闯关刷图，以连招、装备和街机手感著称，长期占据网吧热榜。  \r', '剑网3是西山居的国风武侠MMORPG，以大唐为背景，拥有轻功、门派武学和丰富社交，画面精美，同人文化繁荣。  \r', '魔兽世界是暴雪的史诗级MMORPG，在艾泽拉斯大陆探索，有副本、PVP和任务体系，定义了现代网游的标杆，影响深远。  \r', '三角洲行动是2023年上线的硬核射击游戏，包含大战场战术对抗和生存撤离玩法，画面写实，枪械手感扎实，新晋热门。  \r', '界外狂潮是2025年推出的射击新游，以快节奏对战和英雄技能为特色，在网吧热度榜中抢眼，吸引大量年轻FPS玩家。  \r', '剑灵2是经典武侠MMORPG剑灵的续作，延续东方奇幻画风和华丽的战斗特效，2025年上线后凭借IP影响力迅速跻身热门。  \r', '鸣潮是开放世界动作RPG，玩家在灾变大陆探索，可切换三名角色连携攻击，收集声骸辅助战斗，战斗爽快，画面细腻。  \r', '崩坏星穹铁道是米哈游的银河冒险回合制RPG，搭乘星穹列车穿越星球，体验宏大剧情和角色养成，回合制战斗策略丰富。  \r', '原神是米哈游开发的开放世界动作RPG，玩家在提瓦特大陆探索，可切换元素角色战斗，有丰富剧情和抽卡养成，全球爆款。  \r', '绝区零是米哈游推出的都市奇幻动作游戏，玩家扮演代理人探索空洞，战斗爽快，角色风格鲜明，带有肉鸽和策略元素。  \r', '永劫无间是武侠风格的大逃杀动作游戏，玩家使用冷兵器近战和飞索移动，拼刀振刀机制独特，画面华丽，竞技性强。  \r', 'Apex英雄是重生工作室的免费大逃杀射击游戏，小队三人各选传奇英雄，拥有独特技能，滑铲和攀爬流畅，枪感优秀。  \r', '堡垒之夜是Epic开发的建造+射击大逃杀游戏，玩家可搭板建筑，拥有卡通画风和联动活动，是全球文化现象级作品。  \r', '使命召唤战区是动视的免费大逃杀模式，拥有极高画质和真实枪感，支持复活机制和合约任务，是COD系列的热门玩法。  \r', '绝地求生是开创大逃杀热潮的游戏，百人跳伞搜集装备生存，以写实风格和战术射击著称，曾获无数大奖，风靡全球。  \r', 'CS:GO是Valve的经典战术射击游戏，反恐精英与恐怖分子对垒，讲究枪法和经济管理，是电竞常青树，现升级为CS2。  \r', 'DOTA2是Valve的MOBA游戏，5v5推塔，英雄众多，装备系统复杂，国际邀请赛奖金惊人，是硬核电竞玩家的挚爱。  \r', '风暴英雄是暴雪的MOBA游戏，汇集旗下各游戏角色，取消装备，共享团队经验，注重地图机制和团队配合，节奏更快。  \r', '守望先锋是暴雪的团队射击游戏，分为重装、输出、支援英雄，拥有技能和终极技，地图丰富，曾获年度游戏，现为守望先锋2。  \r', '炉石传说是以魔兽为背景的卡牌对战游戏，玩家组建套牌进行回合对战，有标准、狂野和战棋模式，轻松又有策略。  \r', '皇室战争是Supercell的实时卡牌对战手游，玩家部署卡牌进攻对手塔防，三分钟一局，结合MOBA和塔防元素，竞技性强。  \r', '部落冲突是Supercell的模拟策略手游，玩家建设村庄、训练兵种攻击其他玩家，可加入部落合作，经营与战斗并存。  \r', '荒野乱斗是Supercell的快节奏多人射击手游，3v3或吃鸡模式，多种英雄有独特技能，三分钟一局，轻松爽快。  \r', '第五人格是非对称竞技手游，一名监管者追捕四名求生者，悬疑哥特画风，角色有独特技能，玩法类似黎明杀机。  \r', '阴阳师是网易的日式和风回合制RPG，玩家收集式神，搭配御魂，剧情宏大，美术精美，曾引领二次元手游热潮。  \r', '明日方舟是鹰角网络的塔防策略手游，玩家部署干员阻挡敌人，具有独特世界观和精美立绘，策略性强，深受玩家喜爱。  \r', '命运冠位指定是Fate系列的回合制RPG，玩家召唤英灵穿越时空修复历史，剧情丰富，抽卡养成，是二次元常青树。  \r', '碧蓝航线是舰船拟人射击手游，横向弹幕玩法，收集舰娘搭配装备，有自动战斗和丰富皮肤，角色立绘精美。  \r', '少女前线是战术策略手游，玩家指挥战术人形进行回合制战斗，有枪械拟人和丰富剧情，养成系统深入，硬核玩家众多。  \r', '战双帕弥什是末世科幻动作手游，三人小队切换，有华丽的连招和三消技能系统，打击感出色，剧情黑暗深刻。  \r', '幻塔是完美世界的开放世界科幻RPG，可自由探索、攀爬和战斗，有拟态角色和联机功能，画面与玩法对标原神。  \r', '尘白禁区是轻科幻射击手游，玩家操控角色在近未来都市战斗，有掩体和技能，主打美少女枪战，画风清新。  \r', '无限暖暖是叠纸的开放世界换装冒险游戏，以搭配装扮为核心，结合探索和解谜，画面唯美，主打治愈与时尚。  \r', '恋与制作人是女性向恋爱养成手游，玩家扮演制作人与四位男性角色互动，有剧情和电话系统，广受乙女玩家喜爱。  \r', '光与夜之恋是腾讯的女性向恋爱手游，玩家与五位男主展开浪漫故事，卡面精美，声优豪华，剧情代入感强。  \r', '以闪亮之名是女性向换装社交手游，玩家可以捏脸、设计服装，搭配拍照，有剧情和家园系统，画面精美。  \r', '逆水寒是网易的武侠MMORPG，以北宋为背景，画面精致，轻功和江湖奇遇丰富，有庄园和身份玩法，剧情感人。  \r', '天涯明月刀是腾讯的武侠MMORPG，有电影级画质和自由捏脸，战斗动作流畅，帮派和论剑系统成熟，江湖氛围浓厚。  \r', '九阴真经是蜗牛的武侠网游，主打无等级、奇遇和轻功，武功套路丰富，拥有江湖内功和离线修炼，玩法独特。  \r', '天龙八部是搜狐畅游的经典武侠网游，以金庸小说为背景，门派丰富，珍兽系统和副本玩法经典，曾风靡一时。  \r', '梦幻西游是网易的Q版回合制MMORPG，以西游为背景，有十二门派，抓鬼、封妖和跑商，社交系统完善，经久不衰。  \r', '大话西游是网易的回合制网游，同样西游题材，但更注重故事和种族平衡，有婚姻、养育和帮战，老玩家情怀深厚。  \r', '问道是光宇游戏的回合制修仙网游，以道教为背景，有五行相克、宠物和道行系统，免费模式，平民玩家众多。  \r', '诛仙是完美世界的玄幻仙侠网游，改编自小说，有青云、鬼王等门派，飞行系统和情缘玩法，画面唯美，剧情还原。  \r', '完美世界是完美时空的3D仙侠网游，拥有无缝大地图、飞行和种族变身，副本和城战丰富，是中国最早的3D网游之一。  \r', '武林外传是完美世界开发的Q版武侠网游，喜剧风格，有搞怪称号和宠物，副本简单，适合休闲玩家，情怀之作。  \r', '蜀门是绿岸网络的仙侠网游，采用副本刷装模式，职业分明，有坐骑和法宝系统，操作简单，适合轻量级MMO爱好者。  \r', '传奇是盛大引进的经典MMORPG，战法道三职业，PK爆装备，攻城战热血，是国内网游启蒙之作，至今仍有大量怀旧服。  \r', '奇迹MU是韩国网禅的经典MMORPG，以华丽的装备光效和翅膀系统著称，刷怪升级，PK和攻城战，曾是网吧最火游戏之一。  \r', '冒险岛是Nexon的2D横版Q版网游，玩家在彩色世界冒险，有职业转职、任务和社交，音乐轻快，充满童趣。  \r', '枫之谷即冒险岛国际版，在台服和东南亚流行，内容类似，有更多的联动活动，角色可爱，人气稳定。  \r', '彩虹岛是Actoz的2D横版可爱网游，特色是武器特效和连击系统，有丰富的时装和副本，画面明亮，深受女性玩家喜爱。  \r', '劲舞团是音乐舞蹈类网游，玩家按方向键和空格跟随节奏跳舞，有竞技和情侣模式，曾在国内掀起键盘舞蹈热潮。  \r', 'QQ炫舞是腾讯的舞蹈网游，类似劲舞团，但有更丰富的歌曲和社交功能，与QQ好友互动，时尚装扮是一大特色。  \r', 'QQ飞车是腾讯的竞速网游，有赛车漂移、道具赛和改装系统，Q版画风，音乐动感，曾是青少年最爱的赛车游戏。  \r', '跑跑卡丁车是Nexon的卡通竞速游戏，有漂移集气、道具和竞速模式，角色可爱，曾风靡亚洲，现仍有活跃玩家。  \r', '马里奥赛车是任天堂的卡丁车竞速游戏，使用道具干扰对手，赛道多样，包含任天堂明星角色，派对游戏首选。  \r', '任天堂大乱斗是格斗对战游戏，集结任天堂明星，操作简单，道具丰富，可多人混战，既是竞技也是聚会神器。  \r', '旷野之息是任天堂的开放世界动作冒险游戏，玩家操控林克在广袤海拉鲁探索，物理引擎出色，解谜自由，被誉为神作。  \r', '王国之泪是旷野之息的续作，增加空岛和地底，新增建造和余料建造机制，探索更深入，玩法更具创意，广受好评。  \r', '奥德赛是3D平台跳跃游戏，马里奥可投掷帽子附身敌人，探索多个王国，收集月亮，创意十足，关卡设计精妙。  \r', '动物森友会是生活模拟游戏，玩家在无人岛生活，钓鱼捕虫，装饰房屋，与动物邻居互动，轻松治愈，时间与现实同步。  \r', '宝可梦是经典角色扮演系列，玩家捕捉训练宝可梦，进行道馆挑战和联盟赛，收集图鉴，是全世界最知名的跨媒体IP。  \r', '宝可梦GO是AR手游，在现实世界捕捉宝可梦，进行道馆对战和团体战，鼓励户外探索，曾引发全球热潮。  \r', '我的世界是沙盒建造游戏，玩家在方块世界自由创造和探索，有生存和创造模式，无限可能性，全球销量最高。  \r', '泰拉瑞亚是2D横版沙盒冒险游戏，探索地下世界，收集资源，打造武器和建筑，有丰富的BOSS和随机事件，被称为2D我的世界。  \r', '星露谷物语是农场模拟经营游戏，继承牧场物语风格，种植、养殖、钓鱼、采矿，可结婚社交，轻松治愈，像素风精美。  \r', '饥荒是生存冒险游戏，玩家在异世界收集食物、建造营地，对抗季节和怪物，有理智值，画风哥特，难度较高。  \r', '缺氧是太空殖民地模拟游戏，管理复制人，建设氧气、食物和水循环，需处理热量和气压，硬核策略，可玩性强。  \r', '文明6是回合制策略游戏，玩家选择文明，发展科技、文化、军事，征服或外交胜利，地图庞大，策略深度极高。  \r', '模拟城市是城市建造模拟游戏，玩家规划交通、工业、商业和居民区，处理水电垃圾，应对灾害，体验市长职责。  \r', '城市天际线是目前最真实城建模拟游戏，有交通、区域划分和DLC扩展，支持MOD，可建造立体城市，深受玩家喜爱。  \r', '欧卡2是卡车模拟驾驶游戏，玩家在欧洲公路上运输货物，体验真实驾驶，管理公司，画风写实，休闲放松。  \r', '微软飞行模拟是航空模拟游戏，使用真实卫星地图和气象数据，驾驶各种飞机在全球飞行，画面逼真，硬核飞行爱好者的首选。  \r', 'GT赛车是索尼的赛车模拟游戏，以真实驾驶和赛道著称，有大量授权车辆和赛事，画面精细，物理引擎严谨。  \r', '地平线系列是开放式赛车游戏，在墨西哥等地自由驾驶，有季节变化和多种赛事，爽快又不失真实感，画面顶级。  \r', '地平线零之曙光是开放世界动作RPG，主角在机械兽横行的后末日世界狩猎，有潜行和弓箭战斗，剧情深刻，画面惊艳。  \r', '战神是索尼的动作冒险游戏，主角奎托斯以链刃和利维坦之斧战斗，北欧神话背景，场面宏大，打击感极强。  \r', '最后生还者是末日生存动作游戏，主角乔尔护送艾莉穿越废墟，有潜行和资源管理，剧情感人，被誉为互动电影典范。  \r', '神秘海域是动作冒险系列，主角德雷克寻宝，融合攀爬、枪战和解谜，电影化叙事，画面华丽，是索尼王牌IP。  \r', '古墓丽影是动作冒险系列，主角劳拉探索古墓，解谜与射击结合，新版注重生存和成长，重启后广受好评。  \r', '刺客信条是育碧的开放世界动作潜行游戏，穿梭历史时期，扮演刺客对抗圣殿骑士，有跑酷和战斗，年货系列，内容丰富。  \r', '孤岛惊魂是育碧的FPS开放世界游戏，玩家在偏远岛屿或山区对抗反派，有狩猎和载具，爽快射击，风景优美。  \r', '荒野大镖客2是R星的西部开放世界游戏，扮演亚瑟·摩根，体验牛仔生活，剧情深刻，细节丰富，被誉为神作。  \r', 'GTA5是R星的犯罪开放世界游戏，三位主角在洛圣都行劫，可切换角色，自由探索，线上模式长期运营，销量惊人。  \r', '赛博朋克2077是CDPR的科幻开放世界RPG，玩家在夜之城扮演V，有丰富剧情和角色构建，更新后口碑回升。  \r', '巫师3是CDPR的动作RPG，猎魔人杰洛特寻女，有庞大支线和抉择影响世界，画面和剧情顶尖，获得年度游戏。  \r', '质量效应是BioWare的科幻RPG三部曲，玩家扮演薛帕德指挥诺曼底，探索星系，外交战斗，抉择影响结局。  \r', '辐射4是Bethesda的末日开放世界RPG，主角在核废土生存，有建造系统、伙伴和动力装甲，捡垃圾乐趣无穷。  \r', '上古卷轴5是Bethesda的奇幻开放世界RPG，龙裔探索天际省，有丰富任务、技能树和龙吼，MOD支持强大，常青树。  \r', '黑暗之魂3是硬核动作RPG，以高难度和地图设计闻名，玩家挑战强大BOSS，有丰富武器和流派，宫崎英高代表作。  \r', '艾尔登法环是宫崎英高和马丁合作的开放世界魂系游戏，广袤大地图，自由探索，战斗和魔法丰富，难度依旧。  \r', '只狼是动作冒险游戏，玩家扮演忍者，使用刀和义手战斗，主打拼刀和弹反，有潜行和钩索，剧情和战斗都备受赞誉。  \r', '仁王是光荣的战国动作游戏，融合魂系和忍者龙剑传，玩家使用多种武器和守护灵，刷装备和技能，硬核且耐玩。  \r', '怪物猎人世界是共斗狩猎游戏，玩家组队猎杀大型怪物，利用钩爪和环境陷阱，获得素材打造装备，动作硬核，生态真实。  \r', '怪物猎人崛起是系列新作，新增翔虫和御龙系统，移动更灵活，可高速狩猎，有百龙夜行模式，续作曙光扩展丰富。  \r', '龙之信条2是开放世界动作RPG，玩家扮演觉醒者，有随从系统，可攀爬怪物，魔法炫酷，物理互动优秀。  \r', '最终幻想14是史克威尔的MMORPG，有庞大主线、职业系统和副本，剧情口碑极好，版本更新稳定，全球活跃玩家众多。  \r', '最终幻想7重制版是经典RPG的完全重制，画面和战斗系统全面升级，采用实时指令结合，剧情加料，情怀满满。  \r', '王国之心是迪士尼与最终幻想联动的动作RPG，主角索拉使用键刃，穿梭迪士尼世界，战斗爽快，剧情复杂，拥趸众多。  \r', '尼尔机械纪元是白金工作室的动作RPG，2B和9S主角，人设出色，战斗流畅，多结局剧情深刻，音乐被誉为神级。  \r', '异度神剑是任天堂的开放世界RPG，有巨神和机神世界观，战斗系统独特，可连携攻击，地图广阔，剧情宏大。  \r', '火焰纹章是战棋策略RPG，有经典日式角色和转职系统，永久死亡机制，剧情常涉及战争和爱情，高难度粉丝向。  \r', '女神异闻录5是JRPG，白天学生生活，夜晚怪盗冒险，有回合制战斗和人格面具合成，美术和音乐潮爆，口碑极高。  \r', '如龙是世嘉的动作冒险系列，主角桐生一马，在神室町黑道闯荡，有丰富支线和小游戏，剧情硬派，日剧风格。  \r', '审判之逝是如龙工作室的侦探动作游戏，主角八神隆之调查案件，有战斗和跟踪潜行，剧情悬疑，动作流畅。  \r', '死亡搁浅是小岛秀夫的送货模拟冒险，玩家连接美国城市，有异步社交和BT战斗，剧情深邃，画面电影级。  \r', '控制是Remedy的第三人称超自然动作游戏，女主角使用枪械和超能力，在联邦控制局探索，画面和物理效果惊艳。  \r', '量子破碎是Remedy的时间科幻动作游戏，玩家有闪避和冻结时间能力，穿插真人美剧，剧情烧脑，创意独特。  \r', '心灵杀手2是生存恐怖游戏，使用手电筒和枪支对抗黑暗，有双主角和案件板系统，氛围压抑，剧情悬疑。  \r', '生化危机是卡普空的恐怖生存系列，以丧尸爆发为背景，资源管理，解谜和射击，是恐怖游戏鼻祖之一。  \r', '寂静岭是心理恐怖游戏，主角在迷雾小镇遭遇怪物，氛围压抑，剧情隐喻人性，是经典恐怖IP，等待新作。  \r', '逃生是第一人称恐怖游戏，主角手持摄像机，没有武器，只能躲避和逃跑，环境恐怖，惊吓感十足。  \r', '港诡实录是国产恐怖游戏，以香港都市传说为背景，第一人称探索解谜，中式恐怖氛围，故事引人入胜。  \r', '纸嫁衣是国产恐怖解谜系列，结合民俗和冥婚题材，有丰富的谜题和纸人元素，剧情反转，深受玩家喜爱。  \r', '疑案追声是声音解谜游戏，玩家在案发现场听取对话，根据声音确定事件全貌，创意新颖，逻辑缜密。  \r', '隐形守护者是真人互动影视游戏，玩家扮演潜伏者，选择影响剧情，谍战主题，多重结局，代入感强。', '你好，我是一个基于规则表驱动的一个简单规则AI，可以满足一些简单的聊天需求，有什么我可以帮助你的吗', '我是一个基于简单替换表规则驱动的ai']
        self.获取列表里面的所有元素_返回值 = []

    @_as_procedure(warp=True, arg_types=['s'], arg_names=['字符串'], proccode='去除字符串额外数据 %s', arg_ids=[':5/6pl02R3T8l28q$ufG'], arg_defaults=[''])
    def 去除字符串额外数据(self, arg_字符串=0):
        """自制积木: 去除字符串额外数据 %s"""
        self.去除字符串额外数据_返回值 = ''
        self._j = '1'
        while not _sc_bool(_sc_lt(_sc_sub(_sc_length(arg_字符串), 2), self._j)):
            self._j = _sc_add(self._j, 1)
            if _sc_bool(_sc_and(_sc_eq(_sc_letter_of(self._j, arg_字符串), '\\'), _sc_or(_sc_eq(_sc_letter_of(_sc_add(self._j, 1), arg_字符串), "'"), _sc_or(_sc_eq(_sc_letter_of(_sc_add(self._j, 1), arg_字符串), '"'), _sc_eq(_sc_letter_of(_sc_add(self._j, 1), arg_字符串), '\\'))))):
                self._j = _sc_add(self._j, 1)
                self.去除字符串额外数据_返回值 = _sc_join(self.去除字符串额外数据_返回值, _sc_letter_of(self._j, arg_字符串))
            else:
                self.去除字符串额外数据_返回值 = _sc_join(self.去除字符串额外数据_返回值, _sc_letter_of(self._j, arg_字符串))
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s'], arg_names=['问题'], proccode='AI生成回答 %s', arg_ids=['ea4t,/i)P,Vh0;?{VhiM'], arg_defaults=[''])
    def AI生成回答(self, arg_问题=0):
        """自制积木: AI生成回答 %s"""
        self.AI生成回答_i = '0'
        self.AI生成回答_返回值 = '抱歉,我目前无法理解这个问题,请换个话题再试吧'
        while not _sc_bool(_sc_eq(self.AI生成回答_i, len(self.回答))):
            self.AI生成回答_i = _sc_add(self.AI生成回答_i, 1)
            self.AI生成回答_j = '0'
            while not _sc_bool(_sc_or(_sc_eq(_sc_letter_of(self.AI生成回答_j, arg_问题), _sc_letter_of(1, _sc_item_of(self.匹配词_1, self.AI生成回答_i))), _sc_eq(self.AI生成回答_j, _sc_length(arg_问题)))):
                self.AI生成回答_j = _sc_add(self.AI生成回答_j, 1)
                self._yield_frame()
            if _sc_bool(_sc_eq(_sc_letter_of(self.AI生成回答_j, arg_问题), _sc_letter_of(1, _sc_item_of(self.匹配词_1, self.AI生成回答_i)))):
                self.AI生成回答_t = ''
                for _repeat in range(_sc_repeat_count(_sc_length(_sc_item_of(self.匹配词_1, self.AI生成回答_i)))):
                    self.AI生成回答_t = _sc_join(self.AI生成回答_t, _sc_letter_of(self.AI生成回答_j, arg_问题))
                    self.AI生成回答_j = _sc_add(self.AI生成回答_j, 1)
                    self._yield_frame()
                if _sc_bool(_sc_eq(self.AI生成回答_t, _sc_item_of(self.匹配词_1, self.AI生成回答_i))):
                    if _sc_bool(_sc_and(_sc_eq(_sc_item_of(self.匹配词_2, self.AI生成回答_i), ''), _sc_eq(_sc_item_of(self.匹配词_3, self.AI生成回答_i), ''))):
                        self.AI生成回答_返回值 = _sc_item_of(self.回答, self.AI生成回答_i)
                        self.stop('this script')
                    else:
                        if _sc_bool(_sc_lt(self.AI生成回答_j, _sc_add(_sc_length(arg_问题), 1))):
                            while not _sc_bool(_sc_or(_sc_eq(_sc_letter_of(self.AI生成回答_j, arg_问题), _sc_letter_of(1, _sc_item_of(self.匹配词_2, self.AI生成回答_i))), _sc_eq(self.AI生成回答_j, _sc_length(arg_问题)))):
                                self.AI生成回答_j = _sc_add(self.AI生成回答_j, 1)
                                self._yield_frame()
                            if _sc_bool(_sc_eq(_sc_letter_of(self.AI生成回答_j, arg_问题), _sc_letter_of(1, _sc_item_of(self.匹配词_2, self.AI生成回答_i)))):
                                self.AI生成回答_t = ''
                                for _repeat in range(_sc_repeat_count(_sc_length(_sc_item_of(self.匹配词_2, self.AI生成回答_i)))):
                                    self.AI生成回答_t = _sc_join(self.AI生成回答_t, _sc_letter_of(self.AI生成回答_j, arg_问题))
                                    self.AI生成回答_j = _sc_add(self.AI生成回答_j, 1)
                                    self._yield_frame()
                                if _sc_bool(_sc_eq(self.AI生成回答_t, _sc_item_of(self.匹配词_2, self.AI生成回答_i))):
                                    if _sc_bool(_sc_eq(_sc_item_of(self.匹配词_3, self.AI生成回答_i), '')):
                                        self.AI生成回答_返回值 = _sc_item_of(self.回答, self.AI生成回答_i)
                                        self.stop('this script')
                                    else:
                                        if _sc_bool(_sc_lt(self.AI生成回答_j, _sc_add(_sc_length(arg_问题), 1))):
                                            while not _sc_bool(_sc_or(_sc_eq(_sc_letter_of(self.AI生成回答_j, arg_问题), _sc_letter_of(1, _sc_item_of(self.匹配词_3, self.AI生成回答_i))), _sc_eq(self.AI生成回答_j, _sc_length(arg_问题)))):
                                                self.AI生成回答_j = _sc_add(self.AI生成回答_j, 1)
                                                self._yield_frame()
                                            if _sc_bool(_sc_eq(_sc_letter_of(self.AI生成回答_j, arg_问题), _sc_letter_of(1, _sc_item_of(self.匹配词_3, self.AI生成回答_i)))):
                                                self.AI生成回答_t = ''
                                                for _repeat in range(_sc_repeat_count(_sc_length(_sc_item_of(self.匹配词_3, self.AI生成回答_i)))):
                                                    self.AI生成回答_t = _sc_join(self.AI生成回答_t, _sc_letter_of(self.AI生成回答_j, arg_问题))
                                                    self.AI生成回答_j = _sc_add(self.AI生成回答_j, 1)
                                                    self._yield_frame()
                                                if _sc_bool(_sc_eq(self.AI生成回答_t, _sc_item_of(self.匹配词_3, self.AI生成回答_i))):
                                                    self.AI生成回答_返回值 = _sc_item_of(self.回答, self.AI生成回答_i)
                                                    self.stop('this script')
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s', 's', 's', 's'], arg_names=['匹配词-1', '匹配词-2', '匹配词-3', '回答'], proccode='添加 %s %s %s %s', arg_ids=['W,=FD|!O4kFS*]Cq+YT4', 'pE~H=p2oL_;;{t;WN,Jr', '(~2!(K1b*ZB-5YfBe[7P', ';CFD~$;K1,TkDfyRsug{'], arg_defaults=['', '', '', '', ''])
    def 添加(self, arg_匹配词_1=0, arg_匹配词_2=0, arg_匹配词_3=0, arg_回答=0):
        """自制积木: 添加 %s %s %s %s"""
        if _sc_bool(_sc_eq(arg_匹配词_3, '')):
            if _sc_bool(_sc_eq(arg_匹配词_2, '')):
                self.匹配词_1.append(arg_匹配词_1)
                self.回答.append(arg_回答)
            else:
                _sc_list_insert(self.匹配词_1, _sc_add(len(self.匹配词_2), 1), arg_匹配词_1)
                _sc_list_insert(self.匹配词_2, _sc_add(len(self.匹配词_2), 1), arg_匹配词_2)
                _sc_list_insert(self.回答, len(self.匹配词_2), arg_回答)
        else:
            _sc_list_insert(self.匹配词_1, _sc_add(len(self.匹配词_3), 1), arg_匹配词_1)
            _sc_list_insert(self.匹配词_2, _sc_add(len(self.匹配词_3), 1), arg_匹配词_2)
            _sc_list_insert(self.匹配词_3, _sc_add(len(self.匹配词_3), 1), arg_匹配词_1)
            _sc_list_insert(self.回答, len(self.匹配词_3), arg_回答)


    @_as_procedure(warp=True, arg_types=['s', 'b'], arg_names=['列表', 'boolean'], proccode='获取 %s 该列表里面的所有元素 (清理字符串内容? %b )', arg_ids=['=yU}?H7?`kJK:a/)yd:O', 'sM`kSBu,VG8(-@wI}I-V'], arg_defaults=['', '', '', '', 'false'])
    def 获取_该列表里面的所有元素_清理字符串内容_(self, arg_列表=0, arg_boolean=False):
        """自制积木: 获取 %s 该列表里面的所有元素 (清理字符串内容? %b )"""
        self.获取列表里面的所有元素_返回值.clear()
        self.获取列表里面的所有元素_i = '0'
        self.获取列表里面的所有元素_j = '0'
        self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'YES'
        if _sc_bool(_sc_not(_sc_and(_sc_eq(_sc_letter_of(1, arg_列表), '['), _sc_eq(_sc_letter_of(_sc_length(arg_列表), arg_列表), ']')))):
            self.获取列表里面的所有元素_返回值.append('传入的参数不是列表!!!')
            self.stop('this script')
        while not _sc_bool(_sc_or(_sc_eq(_sc_length(arg_列表), self.获取列表里面的所有元素_i), _sc_lt(_sc_length(arg_列表), self.获取列表里面的所有元素_i))):
            self.获取列表里面的所有元素_i = _sc_add(self.获取列表里面的所有元素_i, 1)
            self.获取列表里面的所有元素_j = _sc_add(self.获取列表里面的所有元素_j, 1)
            self.获取列表里面的所有元素_当前嵌套深度 = '0'
            self.获取列表里面的所有元素_临时缓存当前代码块 = ''
            self.获取列表里面的所有元素_当前嵌套字符 = ''
            if _sc_bool(_sc_not(_sc_or(_sc_eq(self.获取列表里面的所有元素_i, '1'), _sc_eq(self.获取列表里面的所有元素_i, _sc_length(arg_列表))))):
                while not _sc_bool(_sc_or(_sc_and(_sc_and(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), ','), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'YES')), _sc_eq(_sc_length(self.获取列表里面的所有元素_当前嵌套字符), '0')), _sc_or(_sc_eq(_sc_length(arg_列表), self.获取列表里面的所有元素_i), _sc_lt(_sc_length(arg_列表), self.获取列表里面的所有元素_i)))):
                    if _sc_bool(_sc_or(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), ' '), _sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), '\\'))):
                        if _sc_bool(_sc_or(_sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-1'), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-2'))):
                            self.获取列表里面的所有元素_临时缓存当前代码块 = _sc_join(self.获取列表里面的所有元素_临时缓存当前代码块, _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))
                    else:
                        self.获取列表里面的所有元素_临时缓存当前代码块 = _sc_join(self.获取列表里面的所有元素_临时缓存当前代码块, _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))
                    if _sc_bool(_sc_and(_sc_eq(_sc_length(self.获取列表里面的所有元素_临时缓存当前代码块), '1'), _sc_contains('("\'{[', _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表)))):
                        self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'NO'
                        if _sc_bool(_sc_not(_sc_contains('\'"', _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表)))):
                            self.获取列表里面的所有元素_当前嵌套深度 = '1'
                            self.获取列表里面的所有元素_当前嵌套字符 = _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表)
                        else:
                            if _sc_bool(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), "'")):
                                self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'NO-0'
                            else:
                                self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'NO-1'
                    else:
                        if _sc_bool(_sc_not(_sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'YES'))):
                            if _sc_bool(_sc_not(_sc_eq(self.获取列表里面的所有元素_当前嵌套深度, '0'))):
                                while not _sc_bool(_sc_or(_sc_eq(_sc_length(self.获取列表里面的所有元素_当前嵌套字符), '0'), _sc_or(_sc_eq(_sc_length(arg_列表), self.获取列表里面的所有元素_i), _sc_lt(_sc_length(arg_列表), self.获取列表里面的所有元素_i)))):
                                    self.获取列表里面的所有元素_i = _sc_add(self.获取列表里面的所有元素_i, 1)
                                    self.获取列表里面的所有元素_临时缓存当前代码块 = _sc_join(self.获取列表里面的所有元素_临时缓存当前代码块, _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))
                                    if _sc_bool(_sc_contains('\'"()[]{}', _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))):
                                        if _sc_bool(_sc_contains('\'")]}', _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))):
                                            if _sc_bool(_sc_contains('\'"', _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))):
                                                if _sc_bool(_sc_and(_sc_eq(_sc_letter_of(_sc_length(self.获取列表里面的所有元素_当前嵌套字符), self.获取列表里面的所有元素_当前嵌套字符), _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表)), _sc_eq(_sc_letter_of(_sc_sub(self.获取列表里面的所有元素_i, 1), arg_列表), '\\'))):
                                                    self.获取列表里面的所有元素_辅助变量2 = '0'
                                                    self.获取列表里面的所有元素_辅助变量 = ''
                                                    while not _sc_bool(_sc_eq(self.获取列表里面的所有元素_辅助变量2, _sc_sub(_sc_length(self.获取列表里面的所有元素_当前嵌套字符), 1))):
                                                        self.获取列表里面的所有元素_辅助变量2 = _sc_add(self.获取列表里面的所有元素_辅助变量2, 1)
                                                        self.获取列表里面的所有元素_辅助变量 = _sc_join(self.获取列表里面的所有元素_辅助变量, _sc_letter_of(self.获取列表里面的所有元素_辅助变量2, self.获取列表里面的所有元素_当前嵌套字符))
                                                        self._yield_frame()
                                                    self.获取列表里面的所有元素_当前嵌套字符 = self.获取列表里面的所有元素_辅助变量
                                            else:
                                                self.获取列表里面的所有元素_辅助变量2 = '0'
                                                self.获取列表里面的所有元素_辅助变量 = ''
                                                while not _sc_bool(_sc_eq(self.获取列表里面的所有元素_辅助变量2, _sc_sub(_sc_length(self.获取列表里面的所有元素_当前嵌套字符), 1))):
                                                    self.获取列表里面的所有元素_辅助变量2 = _sc_add(self.获取列表里面的所有元素_辅助变量2, 1)
                                                    self.获取列表里面的所有元素_辅助变量 = _sc_join(self.获取列表里面的所有元素_辅助变量, _sc_letter_of(self.获取列表里面的所有元素_辅助变量2, self.获取列表里面的所有元素_当前嵌套字符))
                                                    self._yield_frame()
                                                self.获取列表里面的所有元素_当前嵌套字符 = self.获取列表里面的所有元素_辅助变量
                                        else:
                                            self.获取列表里面的所有元素_当前嵌套深度 = _sc_add(self.获取列表里面的所有元素_当前嵌套深度, 1)
                                            self.获取列表里面的所有元素_当前嵌套字符 = _sc_join(self.获取列表里面的所有元素_当前嵌套字符, _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))
                                    self._yield_frame()
                                self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'YES'
                            else:
                                if _sc_bool(_sc_or(_sc_and(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), "'"), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-0')), _sc_and(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), '"'), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-1')))):
                                    if _sc_bool(_sc_and(_sc_or(_sc_and(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), "'"), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-0')), _sc_and(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), '"'), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-1'))), _sc_not(_sc_eq(_sc_letter_of(_sc_sub(self.获取列表里面的所有元素_i, 1), arg_列表), '\\')))):
                                        self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'YES'
                    self.获取列表里面的所有元素_i = _sc_add(self.获取列表里面的所有元素_i, 1)
                    self._yield_frame()
                self.获取列表里面的所有元素_返回值.append(self.获取列表里面的所有元素_临时缓存当前代码块)
            self._yield_frame()
        if _sc_bool(arg_boolean):
            self._i = '0'
            for _repeat in range(_sc_repeat_count(len(self.获取列表里面的所有元素_返回值))):
                self._i = _sc_add(self._i, 1)
                if _sc_bool(_sc_or(_sc_and(_sc_eq(_sc_letter_of(1, _sc_item_of(self.获取列表里面的所有元素_返回值, self._i)), '"'), _sc_eq(_sc_letter_of(_sc_length(_sc_item_of(self.获取列表里面的所有元素_返回值, self._i)), _sc_item_of(self.获取列表里面的所有元素_返回值, self._i)), '"')), _sc_and(_sc_eq(_sc_letter_of(1, _sc_item_of(self.获取列表里面的所有元素_返回值, self._i)), "'"), _sc_eq(_sc_letter_of(_sc_length(_sc_item_of(self.获取列表里面的所有元素_返回值, self._i)), _sc_item_of(self.获取列表里面的所有元素_返回值, self._i)), "'")))):
                    self.去除字符串额外数据(_sc_item_of(self.获取列表里面的所有元素_返回值, self._i))
                    _sc_list_replace(self.获取列表里面的所有元素_返回值, self._i, self.去除字符串额外数据_返回值)
                self._yield_frame()


    def when_green_flag(self):
        """当绿旗被点击时"""
        pass


    def run(self):
        """向运行时注册事件脚本"""
        self._register('green_flag', self.when_green_flag)

class FortunateOS_命令执行(ScratchSprite):
    """精灵: FortunateOS-命令执行"""

    GLOBAL_NAMES = ('FortunateOS_中转执行类型', 'FortunateOS_中转系统执行', 'FortunateOS_中转系统返回', 'FortunateOS_全部主题名称', 'FortunateOS_分配窗口ID', 'FortunateOS_命令系统执行', 'FortunateOS_命令系统权限', 'FortunateOS_开始菜单是否被开启_', 'FortunateOS_当前主题', 'FortunateOS_当前是否进入桌面', 'FortunateOS_文件内容管理', 'FortunateOS_文件属性管理', 'FortunateOS_文件执行类型', 'FortunateOS_文件系统属性', 'FortunateOS_文件系统执行', 'FortunateOS_文件系统返回', 'FortunateOS_文件路径管理', 'FortunateOS_是否开启锁屏_', 'FortunateOS_窗口ID管理', 'FortunateOS_窗口图层偏移', 'FortunateOS_窗口图层管理', 'FortunateOS_窗口坐标管理', 'FortunateOS_窗口大小管理', 'FortunateOS_窗口系统执行', 'FortunateOS_窗口组件管理', 'FortunateOS_管理设置选项', 'FortunateOS_系统版本号', 'FortunateOS_鼠标是否被占用_', '任务栏动画_i', '我的变量')
    GLOBAL_NAMES_SET = frozenset(GLOBAL_NAMES)

    def __init__(self):
        super().__init__()
        self.x = 0
        self.y = 0
        self.direction = 90
        self.visible = False
        self.size = 100
        self.name = 'FortunateOS-命令执行'
        self.rotation_style = 'all around'
        self.draggable = False
        self.costumes = [{'name': '造型1', 'md5ext': 'a56cea86b900217f496a5f4145c55675.svg', 'dataFormat': 'svg', 'rotationCenterX': 85.19908499999994, 'rotationCenterY': 85.17124500000004}]
        self.sounds = []
        self.costume_number = 1
        self.costume_name = '造型1'

        self.获取列表里面的所有元素_i = 0
        self.获取列表里面的所有元素_j = 0
        self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 0
        self.获取列表里面的所有元素_当前嵌套深度 = 0
        self.获取列表里面的所有元素_临时缓存当前代码块 = 0
        self.获取列表里面的所有元素_当前嵌套字符 = 0
        self.获取列表里面的所有元素_辅助变量2 = 0
        self.获取列表里面的所有元素_辅助变量 = 0
        self._i = 0
        self.去除字符串额外数据_返回值 = 0
        self._j = 0
        self.i = '0'
        self.j = 11
        self.去除a字符串里面的b字符串_开头_结尾_开头结尾_进行处理_返回值 = '/123 123 123'
        self.去除a字符串里面的b字符串_开头_结尾_开头结尾_进行处理_i = 12
        self.去除a字符串里面的b字符串_开头_结尾_开头结尾_进行处理_j = 12
        self.以字符为分隔符进行分隔_i = 12
        self.以字符为分隔符进行分隔_j = ''
        self.t = '/123'
        self.获取a该字符串的b_c个字符_返回值 = 0
        self.获取a该字符串的b_c个字符_i = 0

        self.获取列表里面的所有元素_返回值 = []
        self.临时存储_变量名 = []
        self.临时存储_变量值 = []
        self.以字符为分隔符进行分隔_返回值 = ['/123', '123', '123']
        self.命令_名称 = []
        self.命令_权限 = []

    @_as_procedure(warp=True, arg_types=['s', 's', 's'], arg_names=['a', 'b', 'c'], proccode='获取 %s 该字符串的 %s ~ %s 个字符', arg_ids=[']?NeU/ICvf[UVIjK%0__', 'XCR_ZO0/CH3A#cRYcha7', '#TU.FEP(42oz4s4Dm7Pz'], arg_defaults=['', '', ''])
    def 获取_该字符串的_个字符(self, arg_a=0, arg_b=0, arg_c=0):
        """自制积木: 获取 %s 该字符串的 %s ~ %s 个字符"""
        self.获取a该字符串的b_c个字符_返回值 = ''
        self.获取a该字符串的b_c个字符_i = arg_b
        for _repeat in range(_sc_repeat_count(_sc_add(_sc_sub(arg_c, arg_b), 1))):
            self.获取a该字符串的b_c个字符_返回值 = _sc_join(self.获取a该字符串的b_c个字符_返回值, _sc_letter_of(self.获取a该字符串的b_c个字符_i, arg_a))
            self.获取a该字符串的b_c个字符_i = _sc_add(self.获取a该字符串的b_c个字符_i, 1)
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s', 's', 's'], arg_names=['a', 'b', '开头/结尾/开头结尾'], proccode='去除 %s 字符串里面的 %s 字符串 %s 进行处理', arg_ids=['_K[JbWBc%^J9i-n;nFA@', '~~;K]ttH0Jh%`3c.s4,z', 'mADN@|ik`z[^TwAV/0MP'], arg_defaults=['', '', ''])
    def 去除_字符串里面的_字符串_进行处理(self, arg_a=0, arg_b=0, arg_开头_结尾_开头结尾=0):
        """自制积木: 去除 %s 字符串里面的 %s 字符串 %s 进行处理"""
        self.去除a字符串里面的b字符串_开头_结尾_开头结尾_进行处理_返回值 = ''
        self.去除a字符串里面的b字符串_开头_结尾_开头结尾_进行处理_i = '0'
        self.去除a字符串里面的b字符串_开头_结尾_开头结尾_进行处理_j = '0'
        if _sc_bool(_sc_eq(arg_开头_结尾_开头结尾, '开头结尾')):
            self.去除_字符串里面的_字符串_进行处理(arg_a, arg_b, '开头')
            self.去除_字符串里面的_字符串_进行处理(self.去除a字符串里面的b字符串_开头_结尾_开头结尾_进行处理_返回值, arg_b, '结尾')
        else:
            if _sc_bool(_sc_eq(arg_开头_结尾_开头结尾, '开头')):
                while not _sc_bool(_sc_not(_sc_contains(arg_b, _sc_letter_of(self.去除a字符串里面的b字符串_开头_结尾_开头结尾_进行处理_i, arg_a)))):
                    self.去除a字符串里面的b字符串_开头_结尾_开头结尾_进行处理_i = _sc_add(self.去除a字符串里面的b字符串_开头_结尾_开头结尾_进行处理_i, 1)
                    self._yield_frame()
                while not _sc_bool(_sc_eq(_sc_length(arg_a), _sc_sub(self.去除a字符串里面的b字符串_开头_结尾_开头结尾_进行处理_i, 1))):
                    self.去除a字符串里面的b字符串_开头_结尾_开头结尾_进行处理_返回值 = _sc_join(self.去除a字符串里面的b字符串_开头_结尾_开头结尾_进行处理_返回值, _sc_letter_of(self.去除a字符串里面的b字符串_开头_结尾_开头结尾_进行处理_i, arg_a))
                    self.去除a字符串里面的b字符串_开头_结尾_开头结尾_进行处理_i = _sc_add(self.去除a字符串里面的b字符串_开头_结尾_开头结尾_进行处理_i, 1)
                    self._yield_frame()
            else:
                if _sc_bool(_sc_eq(arg_开头_结尾_开头结尾, '结尾')):
                    self.去除a字符串里面的b字符串_开头_结尾_开头结尾_进行处理_j = _sc_length(arg_a)
                    while not _sc_bool(_sc_not(_sc_contains(arg_b, _sc_letter_of(self.去除a字符串里面的b字符串_开头_结尾_开头结尾_进行处理_j, arg_a)))):
                        self.去除a字符串里面的b字符串_开头_结尾_开头结尾_进行处理_j = _sc_add(self.去除a字符串里面的b字符串_开头_结尾_开头结尾_进行处理_j, -1)
                        self._yield_frame()
                    while not _sc_bool(_sc_eq(self.去除a字符串里面的b字符串_开头_结尾_开头结尾_进行处理_i, self.去除a字符串里面的b字符串_开头_结尾_开头结尾_进行处理_j)):
                        self.去除a字符串里面的b字符串_开头_结尾_开头结尾_进行处理_i = _sc_add(self.去除a字符串里面的b字符串_开头_结尾_开头结尾_进行处理_i, 1)
                        self.去除a字符串里面的b字符串_开头_结尾_开头结尾_进行处理_返回值 = _sc_join(self.去除a字符串里面的b字符串_开头_结尾_开头结尾_进行处理_返回值, _sc_letter_of(self.去除a字符串里面的b字符串_开头_结尾_开头结尾_进行处理_i, arg_a))
                        self._yield_frame()
                else:
                    pass


    @_as_procedure(warp=True, arg_types=['s'], arg_names=['权限'], proccode='执行命令 %s', arg_ids=['u.EOtZf4;q37B8asrZtv'], arg_defaults=['', ''])
    def 执行命令(self, arg_权限=0):
        """自制积木: 执行命令 %s"""
        self.i = '0'
        for _repeat in range(_sc_repeat_count(len(self.获取列表里面的所有元素_返回值))):
            self.i = _sc_add(self.i, 1)
            self.执行单行命令(_sc_item_of(self.获取列表里面的所有元素_返回值, self.i), arg_权限)
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s', 'b'], arg_names=['列表', 'boolean'], proccode='获取 %s 该列表里面的所有元素 (清理字符串内容? %b )', arg_ids=['=yU}?H7?`kJK:a/)yd:O', 'sM`kSBu,VG8(-@wI}I-V'], arg_defaults=['', '', '', '', 'false'])
    def 获取_该列表里面的所有元素_清理字符串内容_(self, arg_列表=0, arg_boolean=False):
        """自制积木: 获取 %s 该列表里面的所有元素 (清理字符串内容? %b )"""
        self.获取列表里面的所有元素_返回值.clear()
        self.获取列表里面的所有元素_i = '0'
        self.获取列表里面的所有元素_j = '0'
        self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'YES'
        if _sc_bool(_sc_not(_sc_and(_sc_eq(_sc_letter_of(1, arg_列表), '['), _sc_eq(_sc_letter_of(_sc_length(arg_列表), arg_列表), ']')))):
            self.获取列表里面的所有元素_返回值.append('传入的参数不是列表!!!')
            self.stop('this script')
        while not _sc_bool(_sc_or(_sc_eq(_sc_length(arg_列表), self.获取列表里面的所有元素_i), _sc_lt(_sc_length(arg_列表), self.获取列表里面的所有元素_i))):
            self.获取列表里面的所有元素_i = _sc_add(self.获取列表里面的所有元素_i, 1)
            self.获取列表里面的所有元素_j = _sc_add(self.获取列表里面的所有元素_j, 1)
            self.获取列表里面的所有元素_当前嵌套深度 = '0'
            self.获取列表里面的所有元素_临时缓存当前代码块 = ''
            self.获取列表里面的所有元素_当前嵌套字符 = ''
            if _sc_bool(_sc_not(_sc_or(_sc_eq(self.获取列表里面的所有元素_i, '1'), _sc_eq(self.获取列表里面的所有元素_i, _sc_length(arg_列表))))):
                while not _sc_bool(_sc_or(_sc_and(_sc_and(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), ','), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'YES')), _sc_eq(_sc_length(self.获取列表里面的所有元素_当前嵌套字符), '0')), _sc_or(_sc_eq(_sc_length(arg_列表), self.获取列表里面的所有元素_i), _sc_lt(_sc_length(arg_列表), self.获取列表里面的所有元素_i)))):
                    if _sc_bool(_sc_or(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), ' '), _sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), '\\'))):
                        if _sc_bool(_sc_or(_sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-1'), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-2'))):
                            self.获取列表里面的所有元素_临时缓存当前代码块 = _sc_join(self.获取列表里面的所有元素_临时缓存当前代码块, _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))
                    else:
                        self.获取列表里面的所有元素_临时缓存当前代码块 = _sc_join(self.获取列表里面的所有元素_临时缓存当前代码块, _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))
                    if _sc_bool(_sc_and(_sc_eq(_sc_length(self.获取列表里面的所有元素_临时缓存当前代码块), '1'), _sc_contains('("\'{[', _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表)))):
                        self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'NO'
                        if _sc_bool(_sc_not(_sc_contains('\'"', _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表)))):
                            self.获取列表里面的所有元素_当前嵌套深度 = '1'
                            self.获取列表里面的所有元素_当前嵌套字符 = _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表)
                        else:
                            if _sc_bool(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), "'")):
                                self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'NO-0'
                            else:
                                self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'NO-1'
                    else:
                        if _sc_bool(_sc_not(_sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'YES'))):
                            if _sc_bool(_sc_not(_sc_eq(self.获取列表里面的所有元素_当前嵌套深度, '0'))):
                                while not _sc_bool(_sc_or(_sc_eq(_sc_length(self.获取列表里面的所有元素_当前嵌套字符), '0'), _sc_or(_sc_eq(_sc_length(arg_列表), self.获取列表里面的所有元素_i), _sc_lt(_sc_length(arg_列表), self.获取列表里面的所有元素_i)))):
                                    self.获取列表里面的所有元素_i = _sc_add(self.获取列表里面的所有元素_i, 1)
                                    self.获取列表里面的所有元素_临时缓存当前代码块 = _sc_join(self.获取列表里面的所有元素_临时缓存当前代码块, _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))
                                    if _sc_bool(_sc_contains('\'"()[]{}', _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))):
                                        if _sc_bool(_sc_contains('\'")]}', _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))):
                                            if _sc_bool(_sc_contains('\'"', _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))):
                                                if _sc_bool(_sc_and(_sc_eq(_sc_letter_of(_sc_length(self.获取列表里面的所有元素_当前嵌套字符), self.获取列表里面的所有元素_当前嵌套字符), _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表)), _sc_eq(_sc_letter_of(_sc_sub(self.获取列表里面的所有元素_i, 1), arg_列表), '\\'))):
                                                    self.获取列表里面的所有元素_辅助变量2 = '0'
                                                    self.获取列表里面的所有元素_辅助变量 = ''
                                                    while not _sc_bool(_sc_eq(self.获取列表里面的所有元素_辅助变量2, _sc_sub(_sc_length(self.获取列表里面的所有元素_当前嵌套字符), 1))):
                                                        self.获取列表里面的所有元素_辅助变量2 = _sc_add(self.获取列表里面的所有元素_辅助变量2, 1)
                                                        self.获取列表里面的所有元素_辅助变量 = _sc_join(self.获取列表里面的所有元素_辅助变量, _sc_letter_of(self.获取列表里面的所有元素_辅助变量2, self.获取列表里面的所有元素_当前嵌套字符))
                                                        self._yield_frame()
                                                    self.获取列表里面的所有元素_当前嵌套字符 = self.获取列表里面的所有元素_辅助变量
                                            else:
                                                self.获取列表里面的所有元素_辅助变量2 = '0'
                                                self.获取列表里面的所有元素_辅助变量 = ''
                                                while not _sc_bool(_sc_eq(self.获取列表里面的所有元素_辅助变量2, _sc_sub(_sc_length(self.获取列表里面的所有元素_当前嵌套字符), 1))):
                                                    self.获取列表里面的所有元素_辅助变量2 = _sc_add(self.获取列表里面的所有元素_辅助变量2, 1)
                                                    self.获取列表里面的所有元素_辅助变量 = _sc_join(self.获取列表里面的所有元素_辅助变量, _sc_letter_of(self.获取列表里面的所有元素_辅助变量2, self.获取列表里面的所有元素_当前嵌套字符))
                                                    self._yield_frame()
                                                self.获取列表里面的所有元素_当前嵌套字符 = self.获取列表里面的所有元素_辅助变量
                                        else:
                                            self.获取列表里面的所有元素_当前嵌套深度 = _sc_add(self.获取列表里面的所有元素_当前嵌套深度, 1)
                                            self.获取列表里面的所有元素_当前嵌套字符 = _sc_join(self.获取列表里面的所有元素_当前嵌套字符, _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))
                                    self._yield_frame()
                                self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'YES'
                            else:
                                if _sc_bool(_sc_or(_sc_and(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), "'"), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-0')), _sc_and(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), '"'), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-1')))):
                                    if _sc_bool(_sc_and(_sc_or(_sc_and(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), "'"), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-0')), _sc_and(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), '"'), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-1'))), _sc_not(_sc_eq(_sc_letter_of(_sc_sub(self.获取列表里面的所有元素_i, 1), arg_列表), '\\')))):
                                        self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'YES'
                    self.获取列表里面的所有元素_i = _sc_add(self.获取列表里面的所有元素_i, 1)
                    self._yield_frame()
                self.获取列表里面的所有元素_返回值.append(self.获取列表里面的所有元素_临时缓存当前代码块)
            self._yield_frame()
        if _sc_bool(arg_boolean):
            self._i = '0'
            for _repeat in range(_sc_repeat_count(len(self.获取列表里面的所有元素_返回值))):
                self._i = _sc_add(self._i, 1)
                if _sc_bool(_sc_or(_sc_and(_sc_eq(_sc_letter_of(1, _sc_item_of(self.获取列表里面的所有元素_返回值, self._i)), '"'), _sc_eq(_sc_letter_of(_sc_length(_sc_item_of(self.获取列表里面的所有元素_返回值, self._i)), _sc_item_of(self.获取列表里面的所有元素_返回值, self._i)), '"')), _sc_and(_sc_eq(_sc_letter_of(1, _sc_item_of(self.获取列表里面的所有元素_返回值, self._i)), "'"), _sc_eq(_sc_letter_of(_sc_length(_sc_item_of(self.获取列表里面的所有元素_返回值, self._i)), _sc_item_of(self.获取列表里面的所有元素_返回值, self._i)), "'")))):
                    self.去除字符串额外数据(_sc_item_of(self.获取列表里面的所有元素_返回值, self._i))
                    _sc_list_replace(self.获取列表里面的所有元素_返回值, self._i, self.去除字符串额外数据_返回值)
                self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s', 's'], arg_names=['命令', '权限'], proccode='执行单行命令 %s %s', arg_ids=['WYi7-.b5^9I)yaxD?inA', 'TA}tJh$uMS(0~wz%2EgQ'], arg_defaults=['', ''])
    def 执行单行命令(self, arg_命令=0, arg_权限=0):
        """自制积木: 执行单行命令 %s %s"""
        self.去除_字符串里面的_字符串_进行处理(arg_命令, ' ', '开头结尾')
        self.以_字符为分隔符对_其进行分隔(' ', self.去除a字符串里面的b字符串_开头_结尾_开头结尾_进行处理_返回值)
        self.j = '1'
        self.t = _sc_item_of(self.以字符为分隔符进行分隔_返回值, 1)
        for _repeat in range(_sc_repeat_count(len(self.以字符为分隔符进行分隔_返回值))):
            self.j = _sc_add(self.j, 1)
            if _sc_bool(_sc_eq(self.t, '')):
                pass
            if _sc_bool(True):
                pass
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s', 's'], arg_names=['a', 'b'], proccode='以 %s 字符为分隔符对 %s 其进行分隔', arg_ids=['B,8vvgS?gXFATPjCzEi9', ')S/arA-D+)]%L57xC%jQ'], arg_defaults=['', ''])
    def 以_字符为分隔符对_其进行分隔(self, arg_a=0, arg_b=0):
        """自制积木: 以 %s 字符为分隔符对 %s 其进行分隔"""
        self.以字符为分隔符进行分隔_返回值.clear()
        self.以字符为分隔符进行分隔_i = '0'
        self.以字符为分隔符进行分隔_j = ''
        for _repeat in range(_sc_repeat_count(_sc_length(arg_b))):
            self.以字符为分隔符进行分隔_i = _sc_add(self.以字符为分隔符进行分隔_i, 1)
            if _sc_bool(_sc_and(_sc_eq(_sc_letter_of(self.以字符为分隔符进行分隔_i, arg_b), arg_a), _sc_not(_sc_eq(_sc_length(self.以字符为分隔符进行分隔_j), '0')))):
                self.以字符为分隔符进行分隔_返回值.append(self.以字符为分隔符进行分隔_j)
                self.以字符为分隔符进行分隔_j = ''
            else:
                self.以字符为分隔符进行分隔_j = _sc_join(self.以字符为分隔符进行分隔_j, _sc_letter_of(self.以字符为分隔符进行分隔_i, arg_b))
            self._yield_frame()
        if _sc_bool(_sc_not(_sc_eq(_sc_length(self.以字符为分隔符进行分隔_j), '0'))):
            self.以字符为分隔符进行分隔_返回值.append(self.以字符为分隔符进行分隔_j)
            self.以字符为分隔符进行分隔_j = ''


    @_as_procedure(warp=True, arg_types=['s'], arg_names=['字符串'], proccode='去除字符串额外数据 %s', arg_ids=[':5/6pl02R3T8l28q$ufG'], arg_defaults=[''])
    def 去除字符串额外数据(self, arg_字符串=0):
        """自制积木: 去除字符串额外数据 %s"""
        self.去除字符串额外数据_返回值 = ''
        self._j = '1'
        while not _sc_bool(_sc_lt(_sc_sub(_sc_length(arg_字符串), 2), self._j)):
            self._j = _sc_add(self._j, 1)
            if _sc_bool(_sc_and(_sc_eq(_sc_letter_of(self._j, arg_字符串), '\\'), _sc_or(_sc_eq(_sc_letter_of(_sc_add(self._j, 1), arg_字符串), "'"), _sc_or(_sc_eq(_sc_letter_of(_sc_add(self._j, 1), arg_字符串), '"'), _sc_eq(_sc_letter_of(_sc_add(self._j, 1), arg_字符串), '\\'))))):
                self._j = _sc_add(self._j, 1)
                self.去除字符串额外数据_返回值 = _sc_join(self.去除字符串额外数据_返回值, _sc_letter_of(self._j, arg_字符串))
            else:
                self.去除字符串额外数据_返回值 = _sc_join(self.去除字符串额外数据_返回值, _sc_letter_of(self._j, arg_字符串))
            self._yield_frame()


    def when_green_flag(self):
        """当绿旗被点击时"""
        pass


    def run(self):
        """向运行时注册事件脚本"""
        self._register('green_flag', self.when_green_flag)

class FortunateOS_信号中转站(ScratchSprite):
    """精灵: FortunateOS-信号中转站"""

    GLOBAL_NAMES = ('FortunateOS_中转执行类型', 'FortunateOS_中转系统执行', 'FortunateOS_中转系统返回', 'FortunateOS_全部主题名称', 'FortunateOS_分配窗口ID', 'FortunateOS_命令系统执行', 'FortunateOS_命令系统权限', 'FortunateOS_开始菜单是否被开启_', 'FortunateOS_当前主题', 'FortunateOS_当前是否进入桌面', 'FortunateOS_文件内容管理', 'FortunateOS_文件属性管理', 'FortunateOS_文件执行类型', 'FortunateOS_文件系统属性', 'FortunateOS_文件系统执行', 'FortunateOS_文件系统返回', 'FortunateOS_文件路径管理', 'FortunateOS_是否开启锁屏_', 'FortunateOS_窗口ID管理', 'FortunateOS_窗口图层偏移', 'FortunateOS_窗口图层管理', 'FortunateOS_窗口坐标管理', 'FortunateOS_窗口大小管理', 'FortunateOS_窗口系统执行', 'FortunateOS_窗口组件管理', 'FortunateOS_管理设置选项', 'FortunateOS_系统版本号', 'FortunateOS_鼠标是否被占用_', '任务栏动画_i', '我的变量')
    GLOBAL_NAMES_SET = frozenset(GLOBAL_NAMES)

    def __init__(self):
        super().__init__()
        self.x = 0
        self.y = 0
        self.direction = 90
        self.visible = False
        self.size = 100
        self.name = 'FortunateOS-信号中转站'
        self.rotation_style = 'all around'
        self.draggable = False
        self.costumes = [{'name': '造型1', 'md5ext': 'da23b20058f8c535102b7bfe49a8640e.svg', 'dataFormat': 'svg', 'rotationCenterX': 29.261904999999985, 'rotationCenterY': 29.261904999999985}, {'name': '造型2', 'md5ext': 'f4614969364b8f5cdafaee3178b9033b.svg', 'dataFormat': 'svg', 'rotationCenterX': 115.70343, 'rotationCenterY': 159.944435}]
        self.sounds = []
        self.costume_number = 1
        self.costume_name = '造型1'

        self.获取列表里面的所有元素_i = 24
        self.获取列表里面的所有元素_j = 3
        self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'YES'
        self.获取列表里面的所有元素_当前嵌套深度 = '0'
        self.获取列表里面的所有元素_临时缓存当前代码块 = 'C:/1/2/3/4/5/6/7'
        self.获取列表里面的所有元素_当前嵌套字符 = ''
        self.获取列表里面的所有元素_辅助变量2 = 0
        self.获取列表里面的所有元素_辅助变量 = 0
        self._i = 2
        self.去除字符串额外数据_返回值 = 0
        self.获取a该字符串的b_c个字符_返回值 = 0
        self.获取a该字符串的b_c个字符_i = 0
        self._j = 0

        self.获取列表里面的所有元素_返回值 = ['dgwjj', 'C:/1/2/3/4/5/6/7']

    @_as_procedure(warp=True, arg_types=['s', 'b'], arg_names=['列表', 'boolean'], proccode='获取 %s 该列表里面的所有元素 (清理字符串内容? %b )', arg_ids=['=yU}?H7?`kJK:a/)yd:O', 'sM`kSBu,VG8(-@wI}I-V'], arg_defaults=['', '', '', '', 'false'])
    def 获取_该列表里面的所有元素_清理字符串内容_(self, arg_列表=0, arg_boolean=False):
        """自制积木: 获取 %s 该列表里面的所有元素 (清理字符串内容? %b )"""
        self.获取列表里面的所有元素_返回值.clear()
        self.获取列表里面的所有元素_i = '0'
        self.获取列表里面的所有元素_j = '0'
        self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'YES'
        if _sc_bool(_sc_not(_sc_and(_sc_eq(_sc_letter_of(1, arg_列表), '['), _sc_eq(_sc_letter_of(_sc_length(arg_列表), arg_列表), ']')))):
            self.获取列表里面的所有元素_返回值.append('传入的参数不是列表!!!')
            self.stop('this script')
        while not _sc_bool(_sc_or(_sc_eq(_sc_length(arg_列表), self.获取列表里面的所有元素_i), _sc_lt(_sc_length(arg_列表), self.获取列表里面的所有元素_i))):
            self.获取列表里面的所有元素_i = _sc_add(self.获取列表里面的所有元素_i, 1)
            self.获取列表里面的所有元素_j = _sc_add(self.获取列表里面的所有元素_j, 1)
            self.获取列表里面的所有元素_当前嵌套深度 = '0'
            self.获取列表里面的所有元素_临时缓存当前代码块 = ''
            self.获取列表里面的所有元素_当前嵌套字符 = ''
            if _sc_bool(_sc_not(_sc_or(_sc_eq(self.获取列表里面的所有元素_i, '1'), _sc_eq(self.获取列表里面的所有元素_i, _sc_length(arg_列表))))):
                while not _sc_bool(_sc_or(_sc_and(_sc_and(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), ','), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'YES')), _sc_eq(_sc_length(self.获取列表里面的所有元素_当前嵌套字符), '0')), _sc_or(_sc_eq(_sc_length(arg_列表), self.获取列表里面的所有元素_i), _sc_lt(_sc_length(arg_列表), self.获取列表里面的所有元素_i)))):
                    if _sc_bool(_sc_or(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), ' '), _sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), '\\'))):
                        if _sc_bool(_sc_or(_sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-1'), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-2'))):
                            self.获取列表里面的所有元素_临时缓存当前代码块 = _sc_join(self.获取列表里面的所有元素_临时缓存当前代码块, _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))
                    else:
                        self.获取列表里面的所有元素_临时缓存当前代码块 = _sc_join(self.获取列表里面的所有元素_临时缓存当前代码块, _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))
                    if _sc_bool(_sc_and(_sc_eq(_sc_length(self.获取列表里面的所有元素_临时缓存当前代码块), '1'), _sc_contains('("\'{[', _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表)))):
                        self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'NO'
                        if _sc_bool(_sc_not(_sc_contains('\'"', _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表)))):
                            self.获取列表里面的所有元素_当前嵌套深度 = '1'
                            self.获取列表里面的所有元素_当前嵌套字符 = _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表)
                        else:
                            if _sc_bool(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), "'")):
                                self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'NO-0'
                            else:
                                self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'NO-1'
                    else:
                        if _sc_bool(_sc_not(_sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'YES'))):
                            if _sc_bool(_sc_not(_sc_eq(self.获取列表里面的所有元素_当前嵌套深度, '0'))):
                                while not _sc_bool(_sc_or(_sc_eq(_sc_length(self.获取列表里面的所有元素_当前嵌套字符), '0'), _sc_or(_sc_eq(_sc_length(arg_列表), self.获取列表里面的所有元素_i), _sc_lt(_sc_length(arg_列表), self.获取列表里面的所有元素_i)))):
                                    self.获取列表里面的所有元素_i = _sc_add(self.获取列表里面的所有元素_i, 1)
                                    self.获取列表里面的所有元素_临时缓存当前代码块 = _sc_join(self.获取列表里面的所有元素_临时缓存当前代码块, _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))
                                    if _sc_bool(_sc_contains('\'"()[]{}', _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))):
                                        if _sc_bool(_sc_contains('\'")]}', _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))):
                                            if _sc_bool(_sc_contains('\'"', _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))):
                                                if _sc_bool(_sc_and(_sc_eq(_sc_letter_of(_sc_length(self.获取列表里面的所有元素_当前嵌套字符), self.获取列表里面的所有元素_当前嵌套字符), _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表)), _sc_eq(_sc_letter_of(_sc_sub(self.获取列表里面的所有元素_i, 1), arg_列表), '\\'))):
                                                    self.获取列表里面的所有元素_辅助变量2 = '0'
                                                    self.获取列表里面的所有元素_辅助变量 = ''
                                                    while not _sc_bool(_sc_eq(self.获取列表里面的所有元素_辅助变量2, _sc_sub(_sc_length(self.获取列表里面的所有元素_当前嵌套字符), 1))):
                                                        self.获取列表里面的所有元素_辅助变量2 = _sc_add(self.获取列表里面的所有元素_辅助变量2, 1)
                                                        self.获取列表里面的所有元素_辅助变量 = _sc_join(self.获取列表里面的所有元素_辅助变量, _sc_letter_of(self.获取列表里面的所有元素_辅助变量2, self.获取列表里面的所有元素_当前嵌套字符))
                                                        self._yield_frame()
                                                    self.获取列表里面的所有元素_当前嵌套字符 = self.获取列表里面的所有元素_辅助变量
                                            else:
                                                self.获取列表里面的所有元素_辅助变量2 = '0'
                                                self.获取列表里面的所有元素_辅助变量 = ''
                                                while not _sc_bool(_sc_eq(self.获取列表里面的所有元素_辅助变量2, _sc_sub(_sc_length(self.获取列表里面的所有元素_当前嵌套字符), 1))):
                                                    self.获取列表里面的所有元素_辅助变量2 = _sc_add(self.获取列表里面的所有元素_辅助变量2, 1)
                                                    self.获取列表里面的所有元素_辅助变量 = _sc_join(self.获取列表里面的所有元素_辅助变量, _sc_letter_of(self.获取列表里面的所有元素_辅助变量2, self.获取列表里面的所有元素_当前嵌套字符))
                                                    self._yield_frame()
                                                self.获取列表里面的所有元素_当前嵌套字符 = self.获取列表里面的所有元素_辅助变量
                                        else:
                                            self.获取列表里面的所有元素_当前嵌套深度 = _sc_add(self.获取列表里面的所有元素_当前嵌套深度, 1)
                                            self.获取列表里面的所有元素_当前嵌套字符 = _sc_join(self.获取列表里面的所有元素_当前嵌套字符, _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))
                                    self._yield_frame()
                                self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'YES'
                            else:
                                if _sc_bool(_sc_or(_sc_and(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), "'"), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-0')), _sc_and(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), '"'), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-1')))):
                                    if _sc_bool(_sc_and(_sc_or(_sc_and(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), "'"), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-0')), _sc_and(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), '"'), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-1'))), _sc_not(_sc_eq(_sc_letter_of(_sc_sub(self.获取列表里面的所有元素_i, 1), arg_列表), '\\')))):
                                        self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'YES'
                    self.获取列表里面的所有元素_i = _sc_add(self.获取列表里面的所有元素_i, 1)
                    self._yield_frame()
                self.获取列表里面的所有元素_返回值.append(self.获取列表里面的所有元素_临时缓存当前代码块)
            self._yield_frame()
        if _sc_bool(arg_boolean):
            self._i = '0'
            for _repeat in range(_sc_repeat_count(len(self.获取列表里面的所有元素_返回值))):
                self._i = _sc_add(self._i, 1)
                if _sc_bool(_sc_or(_sc_and(_sc_eq(_sc_letter_of(1, _sc_item_of(self.获取列表里面的所有元素_返回值, self._i)), '"'), _sc_eq(_sc_letter_of(_sc_length(_sc_item_of(self.获取列表里面的所有元素_返回值, self._i)), _sc_item_of(self.获取列表里面的所有元素_返回值, self._i)), '"')), _sc_and(_sc_eq(_sc_letter_of(1, _sc_item_of(self.获取列表里面的所有元素_返回值, self._i)), "'"), _sc_eq(_sc_letter_of(_sc_length(_sc_item_of(self.获取列表里面的所有元素_返回值, self._i)), _sc_item_of(self.获取列表里面的所有元素_返回值, self._i)), "'")))):
                    self.去除字符串额外数据(_sc_item_of(self.获取列表里面的所有元素_返回值, self._i))
                    _sc_list_replace(self.获取列表里面的所有元素_返回值, self._i, self.去除字符串额外数据_返回值)
                self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s', 's', 's'], arg_names=['a', 'b', 'c'], proccode='获取 %s 该字符串的 %s ~ %s 个字符', arg_ids=[']?NeU/ICvf[UVIjK%0__', 'XCR_ZO0/CH3A#cRYcha7', '#TU.FEP(42oz4s4Dm7Pz'], arg_defaults=['', '', ''])
    def 获取_该字符串的_个字符(self, arg_a=0, arg_b=0, arg_c=0):
        """自制积木: 获取 %s 该字符串的 %s ~ %s 个字符"""
        self.获取a该字符串的b_c个字符_返回值 = ''
        self.获取a该字符串的b_c个字符_i = arg_b
        for _repeat in range(_sc_repeat_count(_sc_add(_sc_sub(arg_c, arg_b), 1))):
            self.获取a该字符串的b_c个字符_返回值 = _sc_join(self.获取a该字符串的b_c个字符_返回值, _sc_letter_of(self.获取a该字符串的b_c个字符_i, arg_a))
            self.获取a该字符串的b_c个字符_i = _sc_add(self.获取a该字符串的b_c个字符_i, 1)
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s'], arg_names=['字符串'], proccode='去除字符串额外数据 %s', arg_ids=[':5/6pl02R3T8l28q$ufG'], arg_defaults=[''])
    def 去除字符串额外数据(self, arg_字符串=0):
        """自制积木: 去除字符串额外数据 %s"""
        self.去除字符串额外数据_返回值 = ''
        self._j = '1'
        while not _sc_bool(_sc_lt(_sc_sub(_sc_length(arg_字符串), 2), self._j)):
            self._j = _sc_add(self._j, 1)
            if _sc_bool(_sc_and(_sc_eq(_sc_letter_of(self._j, arg_字符串), '\\'), _sc_or(_sc_eq(_sc_letter_of(_sc_add(self._j, 1), arg_字符串), "'"), _sc_or(_sc_eq(_sc_letter_of(_sc_add(self._j, 1), arg_字符串), '"'), _sc_eq(_sc_letter_of(_sc_add(self._j, 1), arg_字符串), '\\'))))):
                self._j = _sc_add(self._j, 1)
                self.去除字符串额外数据_返回值 = _sc_join(self.去除字符串额外数据_返回值, _sc_letter_of(self._j, arg_字符串))
            else:
                self.去除字符串额外数据_返回值 = _sc_join(self.去除字符串额外数据_返回值, _sc_letter_of(self._j, arg_字符串))
            self._yield_frame()


    def when_green_flag(self):
        """当绿旗被点击时"""
        while self._running:
            pass
            self._yield_frame()


    def when_green_flag_2(self):
        """当绿旗被点击时"""
        while self._running:
            self.wait_until(lambda: _sc_bool(_sc_not(_sc_eq(len(self.FortunateOS_中转系统执行), '0'))))
            if _sc_bool(_sc_eq(_sc_item_of(self.FortunateOS_中转执行类型, 1), 'wj')):
                self.获取_该列表里面的所有元素_清理字符串内容_(_sc_item_of(self.FortunateOS_中转系统执行, 1), _sc_not(True))
                self.FortunateOS_文件执行类型.append(_sc_item_of(self.获取列表里面的所有元素_返回值, 1))
                self.FortunateOS_文件系统执行.append(_sc_item_of(self.获取列表里面的所有元素_返回值, 2))
                self.wait_until(lambda: _sc_bool(_sc_gt(len(self.获取列表里面的所有元素_返回值), '0')))
                self.FortunateOS_中转系统返回.append(_sc_item_of(self.FortunateOS_文件系统返回, 1))
                _sc_list_delete(self.FortunateOS_文件系统返回, 1)
            _sc_list_delete(self.FortunateOS_中转系统执行, 1)
            _sc_list_delete(self.FortunateOS_中转执行类型, 1)
            self._yield_frame()


    def run(self):
        """向运行时注册事件脚本"""
        self._register('green_flag', self.when_green_flag)
        self._register('green_flag', self.when_green_flag_2)

def main(argv=None):
    """启动Scratch 3.0 pygame运行时"""
    parser = argparse.ArgumentParser(description='Scratch 3.0 runtime')
    parser.add_argument('--headless', action='store_true', help='无窗口模式')
    parser.add_argument('--frames', type=int, help='运行指定帧数后退出')
    parser.add_argument('--seconds', type=float, help='运行指定秒数后退出')
    parser.add_argument('--fps', type=int, help='覆盖帧率')
    parser.add_argument('--seed', type=int, help='随机种子')
    parser.add_argument('--trace', action='store_true', help='打印事件/脚本/过程调用')
    parser.add_argument('--no-audio', action='store_true', help='禁用声音')
    parser.add_argument('--assets', help='覆盖素材目录')
    parser.add_argument('--interpolation', action='store_true', help='TurboWarp插值')
    parser.add_argument('--turbo', action='store_true', help='Turbo模式')
    parser.add_argument('--no-fencing', dest='fencing', action='store_false', help='移除舞台边界限制')
    parser.add_argument('--infinite-clones', action='store_true', help='解除克隆体数量限制')
    parser.add_argument('--remove-misc-limits', dest='misc_limits', action='store_false', help='移除杂项限制')
    parser.add_argument('--stage-size', help='自定义舞台尺寸，如 640x360')
    parser.add_argument('--hq-pen', action='store_true', help='高质量画笔')
    parser.add_argument('--warp-timer', type=float, default=0.5, help='warp模式超时秒数')
    parser.add_argument('--disable-compiler', action='store_true', help='兼容参数（无操作）')
    parser.add_argument('--windowed', action='store_true', help='以普通窗口启动（默认自动最大化）')
    parser.set_defaults(fps=60)
    parser.set_defaults(fencing=False)
    args = parser.parse_args(argv)
    if args.seed is not None:
        random.seed(args.seed)
    stage_size = None
    if args.stage_size:
        try:
            width, height = args.stage_size.lower().split('x')
            stage_size = (int(width), int(height))
        except ValueError:
            parser.error('--stage-size 格式应为 WIDTHxHEIGHT')
    runtime = ScratchRuntime(
        headless=args.headless, fps=args.fps, trace=args.trace,
        audio=not args.no_audio, assets_dir=args.assets,
        interpolation=args.interpolation, turbo=args.turbo,
        fencing=args.fencing, infinite_clones=args.infinite_clones,
        misc_limits=args.misc_limits, hq_pen=args.hq_pen,
        stage_size=stage_size, warp_timer=args.warp_timer,
        disable_compiler=args.disable_compiler,
        maximize=not args.windowed)

    stage = Stage()
    runtime.add_sprite(stage)
    fortunateos = FortunateOS()
    runtime.add_sprite(fortunateos)
    bios = BIOS()
    runtime.add_sprite(bios)
    fortunateos_开机动画 = FortunateOS_开机动画()
    runtime.add_sprite(fortunateos_开机动画)
    fortunateos_软件图标 = FortunateOS_软件图标()
    runtime.add_sprite(fortunateos_软件图标)
    fortunateos_窗口 = FortunateOS_窗口()
    runtime.add_sprite(fortunateos_窗口)
    fortunateos_文件管理 = FortunateOS_文件管理()
    runtime.add_sprite(fortunateos_文件管理)
    fortunateos_任务栏 = FortunateOS_任务栏()
    runtime.add_sprite(fortunateos_任务栏)
    fortunateos_菜单 = FortunateOS_菜单()
    runtime.add_sprite(fortunateos_菜单)
    fortunateos_锁屏菜单 = FortunateOS_锁屏菜单()
    runtime.add_sprite(fortunateos_锁屏菜单)
    fortunateos_fai = FortunateOS_FAI()
    runtime.add_sprite(fortunateos_fai)
    fortunateos_命令执行 = FortunateOS_命令执行()
    runtime.add_sprite(fortunateos_命令执行)
    fortunateos_信号中转站 = FortunateOS_信号中转站()
    runtime.add_sprite(fortunateos_信号中转站)

    try:
        runtime.start(max_frames=args.frames, max_seconds=args.seconds)
    except KeyboardInterrupt:
        pass
    finally:
        runtime.shutdown()


if __name__ == "__main__":
    main()