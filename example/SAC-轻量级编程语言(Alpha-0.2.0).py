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
STAGE_COSTUME = 'cd21514d0531fdffb22204e0ec5ed84a.svg'
BACKDROPS = [('背景1', 'cd21514d0531fdffb22204e0ec5ed84a.svg')]
GLOBALS = {}

MONITORS = [{'kind': 'list', 'name': '输入代码', 'sprite': 'SAC-轻量级编程语言', 'label': 'SAC-轻量级编程语言: 输入代码', 'attr': '输入代码', 'x': 1, 'y': 0, 'width': 252, 'height': 250}, {'kind': 'list', 'name': 'Token', 'sprite': 'SAC-轻量级编程语言', 'label': 'SAC-轻量级编程语言: Token', 'attr': 'Token', 'x': 255, 'y': 0, 'width': 231, 'height': 250}, {'kind': 'list', 'name': '语法分析器-状态栈', 'sprite': 'SAC-轻量级编程语言', 'label': 'SAC-轻量级编程语言: 语法分析器-状态栈', 'attr': '语法分析器_状态栈', 'x': 380, 'y': 160, 'width': 200, 'height': 150}, {'kind': 'list', 'name': '语法分析器-嵌套栈', 'sprite': 'SAC-轻量级编程语言', 'label': 'SAC-轻量级编程语言: 语法分析器-嵌套栈', 'attr': '语法分析器_嵌套栈', 'x': 380, 'y': 160, 'width': 200, 'height': 150}, {'kind': 'list', 'name': '语法分析器-操作符栈', 'sprite': 'SAC-轻量级编程语言', 'label': 'SAC-轻量级编程语言: 语法分析器-操作符栈', 'attr': '语法分析器_操作符栈', 'x': 5, 'y': 263, 'width': 200, 'height': 150}, {'kind': 'list', 'name': '语法分析器:操作数栈', 'sprite': 'SAC-轻量级编程语言', 'label': 'SAC-轻量级编程语言: 语法分析器:操作数栈', 'attr': '语法分析器_操作数栈', 'x': 155, 'y': 263, 'width': 200, 'height': 150}, {'kind': 'list', 'name': '语法分析器:当前操作', 'sprite': 'SAC-轻量级编程语言', 'label': 'SAC-轻量级编程语言: 语法分析器:当前操作', 'attr': '语法分析器_当前操作', 'x': 80, 'y': 160, 'width': 200, 'height': 150}, {'kind': 'list', 'name': '语法分析器-解析表达式:结束type', 'sprite': 'SAC-轻量级编程语言', 'label': 'SAC-轻量级编程语言: 语法分析器-解析表达式:结束type', 'attr': '语法分析器_解析表达式_结束type', 'x': 174, 'y': 219, 'width': 200, 'height': 150}, {'kind': 'list', 'name': '语法分析器-解析表达式:结束token', 'sprite': 'SAC-轻量级编程语言', 'label': 'SAC-轻量级编程语言: 语法分析器-解析表达式:结束token', 'attr': '语法分析器_解析表达式_结束token', 'x': 155, 'y': 123, 'width': 200, 'height': 150}, {'kind': 'var', 'name': '语法分析器-解析表达式-查看当前是否应该终止:返回值', 'sprite': 'SAC-轻量级编程语言', 'label': 'SAC-轻量级编程语言: 语法分析器-解析表达式-查看当前是否应该终止:返回值', 'attr': '语法分析器_解析表达式_查看当前是否应该终止_返回值', 'x': 84, 'y': 223, 'width': 120, 'height': 20}, {'kind': 'var', 'name': '语法分析器-解析表达式-查看当前是否应该终止:i', 'sprite': 'SAC-轻量级编程语言', 'label': 'SAC-轻量级编程语言: 语法分析器-解析表达式-查看当前是否应该终止:i', 'attr': '语法分析器_解析表达式_查看当前是否应该终止_i', 'x': 58, 'y': 142, 'width': 120, 'height': 20}, {'kind': 'list', 'name': '语法分析器-解析表达式:临时列表', 'sprite': 'SAC-轻量级编程语言', 'label': 'SAC-轻量级编程语言: 语法分析器-解析表达式:临时列表', 'attr': '语法分析器_解析表达式_临时列表', 'x': 160, 'y': 10, 'width': 200, 'height': 150}, {'kind': 'var', 'name': '语法分析器-解析表达式-获取优先级:返回值', 'sprite': 'SAC-轻量级编程语言', 'label': 'SAC-轻量级编程语言: 语法分析器-解析表达式-获取优先级:返回值', 'attr': '语法分析器_解析表达式_获取优先级_返回值', 'x': 150, 'y': 255, 'width': 120, 'height': 20}, {'kind': 'var', 'name': '语法分析器-解析表达式-获取优先级:临时存储', 'sprite': 'SAC-轻量级编程语言', 'label': 'SAC-轻量级编程语言: 语法分析器-解析表达式-获取优先级:临时存储', 'attr': '语法分析器_解析表达式_获取优先级_临时存储', 'x': 135, 'y': 31, 'width': 120, 'height': 20}, {'kind': 'var', 'name': '语法分析器-解析表达式-弹栈并构建BinOp:运算符节点', 'sprite': 'SAC-轻量级编程语言', 'label': 'SAC-轻量级编程语言: 语法分析器-解析表达式-弹栈并构建BinOp:运算符节点', 'attr': '语法分析器_解析表达式_弹栈并构建BinOp_运算符节点', 'x': 1, 'y': 153, 'width': 120, 'height': 20}, {'kind': 'var', 'name': '语法分析器-解析表达式-弹栈并构建UnaryOp:运算符节点', 'sprite': 'SAC-轻量级编程语言', 'label': 'SAC-轻量级编程语言: 语法分析器-解析表达式-弹栈并构建UnaryOp:运算符节点', 'attr': '语法分析器_解析表达式_弹栈并构建UnaryOp_运算符节点', 'x': 148, 'y': 231, 'width': 120, 'height': 20}, {'kind': 'var', 'name': '语法分析器-解析表达式-保存当前状态:i', 'sprite': 'SAC-轻量级编程语言', 'label': 'SAC-轻量级编程语言: 语法分析器-解析表达式-保存当前状态:i', 'attr': '语法分析器_解析表达式_保存当前状态_i', 'x': 137, 'y': 196, 'width': 120, 'height': 20}, {'kind': 'var', 'name': '语法分析器-解析表达式:当前临时指向的根节点?', 'sprite': 'SAC-轻量级编程语言', 'label': 'SAC-轻量级编程语言: 语法分析器-解析表达式:当前临时指向的根节点?', 'attr': '语法分析器_解析表达式_当前临时指向的根节点_', 'x': 11, 'y': 116, 'width': 120, 'height': 20}]

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
        self.stage_sprite = None
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
            if ghost > 0:
                background = background.copy()
                background.set_alpha(int(255 * (1 - ghost / 100.0)))
        if background is not None:
            if ghost > 0:
                # 半透明背景需要先铺底色，避免叠到上一帧画面
                self.stage_surface.fill((255, 255, 255))
            self.stage_surface.blit(background, (0, 0))
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

    GLOBAL_NAMES = ()
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
        self.costumes = [{'name': '背景1', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 240, 'rotationCenterY': 180}]
        self.sounds = []
        self.costume_number = 1
        self.costume_name = '背景1'

    def run(self):
        """向运行时注册事件脚本"""
        pass

class SAC_轻量级编程语言(ScratchSprite):
    """精灵: SAC-轻量级编程语言"""

    GLOBAL_NAMES = ()
    GLOBAL_NAMES_SET = frozenset(GLOBAL_NAMES)

    def __init__(self):
        super().__init__()
        self.x = -30
        self.y = 10
        self.direction = 90
        self.visible = False
        self.size = 100
        self.name = 'SAC-轻量级编程语言'
        self.rotation_style = 'all around'
        self.draggable = False
        self.costumes = [{'name': 'a', 'md5ext': '78f1c8994065bafc771e04e2af4f7453.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'b', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'c', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'd', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'e', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'f', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'g', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'h', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'i', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'j', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'k', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'l', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'n', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'm', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'o', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'p', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'q', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'r', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 's', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 't', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'u', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'v', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'w', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'x', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'y', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'z', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'A', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'B', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'C', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'D', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'E', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'F', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'G', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'H', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'I', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'J', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'K', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'L', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'N', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'M', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'O', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'P', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'Q', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'R', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'S', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'T', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'U', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'V', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'W', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'X', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'Y', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}, {'name': 'Z', 'md5ext': 'cd21514d0531fdffb22204e0ec5ed84a.svg', 'dataFormat': 'svg', 'rotationCenterX': 0, 'rotationCenterY': 0}]
        self.sounds = []
        self.costume_number = 20
        self.costume_name = 't'

        self.判断a字符串在b字符串第一次出现的索引位置_返回值 = 0
        self.判断a字符串在b字符串第一次出现的索引位置_i = 0
        self.判断a字符串在b字符串第一次出现的索引位置_j = 0
        self.判断a字符串在b字符串第一次出现的索引位置_w = 0
        self.判断a字符串在b字符串出现几次_返回值 = 0
        self.判断a字符串在b字符串出现几次_i = 11
        self.判断a字符串在b字符串出现几次_j = 1
        self.判断a字符串在b字符串出现几次_w = 'r'
        self.判断a字符串是否只由b字符串组成_返回值 = 'YES'
        self.判断a字符串是否只由b字符串组成_i = 1
        self.去除a字符串里面的b字符串_开头_结尾_开头结尾_进行处理_返回值 = ''
        self.去除a字符串里面的b字符串_开头_结尾_开头结尾_进行处理_i = 0
        self.获取列表里面的所有元素_i = 0
        self.获取列表里面的所有元素_j = 0
        self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'YES'
        self.获取列表里面的所有元素_当前嵌套深度 = 0
        self.获取列表里面的所有元素_临时缓存当前代码块 = 'Integer'
        self.获取列表里面的所有元素_当前嵌套字符 = ''
        self.获取列表里面的所有元素_辅助变量2 = 0
        self.获取列表里面的所有元素_辅助变量 = ''
        self.对字符串进行转义处理_返回值 = '0'
        self.对字符串进行转义处理_i = 0
        self.去除a字符串里面的b字符串_开头_结尾_开头结尾_进行处理_j = 0
        self.获取a该字符串的b_c个字符_i = 0
        self.获取a该字符串的b_c个字符_返回值 = ''
        self.获取a该字符串的b_c以外的字符_返回值 = '17'
        self.获取a该字符串的b_c以外的字符_i = 15
        self.词法分析器_i = 1
        self.词法分析器_j = 15
        self.词法分析器_Type = 'Note'
        self.词法分析器_当前是否是转义模式 = 'NO'
        self.词法分析器_Token = ''
        self.词法分析器_代码嵌套 = ''
        self.词法分析器_判断是否能跳出嵌套_ = 0
        self.词法分析器_表达式嵌套层数 = 0
        self.获取列表里面的所有元素_当前是否是转义模式 = 'NO'
        self.判断两个字符串是否相等_返回值 = 'YES'
        self.判断两个字符串是否相等_i = 5
        self.判断两个字符串是否相等_v = 20
        self.词法分析器_k = 0
        self.词法分析器_ki = 1
        self.词法分析器_kj = 6
        self.构建语法树_层次 = -3
        self.构建语法树_节点 = 6
        self.构建语法树_处理语句结束_w = '-'
        self.构建语法树_处理语句结束_k = 'BinOp'
        self.语法分析器_i = 197880625
        self.语法分析器_Token = ''
        self.语法分析器_Type = ''
        self.语法分析器_row = ''
        self.语法分析器_保存当前状态_临时变量 = '[传入的参数不是列表!!!,197880625,,,,[]]]]'
        self.语法分析器_当前选择分支 = '传入的参数不是列表!!!'
        self.语法分析器_保存当前状态_i = 1
        self.语法分析器_回退最近的状态_i = 1
        self.语法分析器_临时存储 = '$a'
        self.语法分析器_line = 1
        self.语法分析器_解析表达式_查看当前是否应该终止_返回值 = 'NO'
        self.语法分析器_解析表达式_查看当前是否应该终止_i = 2
        self.语法分析器_解析表达式_获取优先级_返回值 = 0
        self.语法分析器_解析表达式_获取优先级_临时存储 = 0
        self.语法分析器_解析表达式_弹栈并构建BinOp_运算符节点 = 2
        self.语法分析器_解析表达式_弹栈并构建UnaryOp_运算符节点 = 0
        self.语法分析器_解析表达式_保存当前状态_i = 0
        self.语法分析器_解析表达式_当前临时指向的根节点_ = 0

        self.获取列表里面的所有元素_返回值 = []
        self.输出结果 = []
        self.输入代码 = ['$a = "114514"']
        self.语法树 = [0, 'Call', 'input', 0, 0, 1, 'Assignment', '$a', 0, 0, 2, 'BinOp', '', 0, 0, 3, '', '', '', 0, 4, '', '', '', 0, 5, '', '', 2, 0]
        self.Token = ['[0,1,line]', '[1,$a,Variable]', '[4,=,Assignment]', '[6,"114514",String-2]', '[0,Null,EOF]']
        self.词法分析器_判断层数 = []
        self.运算符组合列表 = ['+=', '-=', '*=', '/=', '//', '**', '==', '<=', '>=', '>>', '<<', '!=']
        self.关键字 = ['while', 'for', 'in', 'range', 'len', 'list', 'dist', 'int', 'str', 'float', 'bool', 'True', 'False', 'print', 'input', 'if', 'elif', 'else', 'return', 'class', 'def', 'pass', 'not', 'or', 'and', 'try', 'except', 'as']
        self.Token_平铺 = [0, 1, 'line', 1, '$a', 'Variable', 4, '=', 'Assignment', 6, '"114514"', 'String-2', 0, 'Null', 'EOF']
        self.构建语法树_自定义 = []
        self.报错_详细信息 = []
        self.Keywords_关键字 = ['if', 'elif', 'else', 'while', 'for', 'class', 'def', 'try', 'except']
        self.Built_in_function_关键字 = ['print', 'input', 'int', 'list', 'dict', 'len', 'float', 'bool', 'True', 'False']
        self.Operator_关键字 = ['or', 'and', 'not', 'as']
        self.报错 = []
        self.语法分析器_状态栈 = []
        self.语法分析器_嵌套栈 = ['传入的参数不是列表!!!']
        self.语法分析器_回退最近的状态_临时列表 = ['传入的参数不是列表!!!']
        self.语法分析器_操作符栈 = []
        self.语法分析器_操作数栈 = []
        self.语法分析器_当前操作 = []
        self.语法分析器_解析表达式_结束type = ['', '']
        self.语法分析器_解析表达式_结束token = ['传入的参数不是列表!!!', '传入的参数不是列表!!!']
        self.语法分析器_解析表达式_临时列表 = []
        self.语法分析器_操作数栈_类型 = []

    @_as_procedure(warp=True, arg_types=[], arg_names=[], proccode='语法分析器-解析表达式-保存当前状态')
    def 语法分析器_解析表达式_保存当前状态(self):
        """自制积木: 语法分析器-解析表达式-保存当前状态"""
        self.语法分析器_保存当前状态_临时变量 = _sc_join('[', _sc_join(self.语法分析器_当前选择分支, _sc_join(',', _sc_join(self.语法分析器_i, _sc_join(',', _sc_join(self.语法分析器_row, _sc_join(',', _sc_join(self.语法分析器_Token, _sc_join(',', _sc_join(self.语法分析器_Type, ',['))))))))))
        self.语法分析器_保存当前状态_i = '1'
        self.语法分析器_保存当前状态_临时变量 = _sc_join(self.语法分析器_保存当前状态_临时变量, _sc_item_of(self.语法分析器_操作数栈, self.语法分析器_i))
        for _repeat in range(_sc_repeat_count(len(self.语法分析器_操作数栈))):
            self.语法分析器_保存当前状态_i = _sc_add(self.语法分析器_保存当前状态_i, 1)
            self.语法分析器_保存当前状态_临时变量 = _sc_join(self.语法分析器_保存当前状态_临时变量, _sc_join(',', _sc_item_of(self.语法分析器_操作数栈, self.语法分析器_i)))
            self._yield_frame()
        self.语法分析器_保存当前状态_临时变量 = _sc_join(self.语法分析器_保存当前状态_临时变量, ']],[')
        self.语法分析器_保存当前状态_i = '1'
        self.语法分析器_保存当前状态_临时变量 = _sc_join(self.语法分析器_保存当前状态_临时变量, _sc_item_of(self.语法分析器_操作数栈_类型, self.语法分析器_i))
        for _repeat in range(_sc_repeat_count(len(self.语法分析器_操作数栈_类型))):
            self.语法分析器_保存当前状态_i = _sc_add(self.语法分析器_保存当前状态_i, 1)
            self.语法分析器_保存当前状态_临时变量 = _sc_join(self.语法分析器_保存当前状态_临时变量, _sc_join(',', _sc_item_of(self.语法分析器_操作数栈_类型, self.语法分析器_i)))
            self._yield_frame()
        self.语法分析器_保存当前状态_临时变量 = _sc_join(self.语法分析器_保存当前状态_临时变量, ']],[')
        self.语法分析器_保存当前状态_临时变量 = _sc_join(self.语法分析器_保存当前状态_临时变量, _sc_item_of(self.语法分析器_操作符栈, self.语法分析器_i))
        for _repeat in range(_sc_repeat_count(len(self.语法分析器_操作符栈))):
            self.语法分析器_保存当前状态_i = _sc_add(self.语法分析器_保存当前状态_i, 1)
            self.语法分析器_保存当前状态_临时变量 = _sc_join(self.语法分析器_保存当前状态_临时变量, _sc_join(',', _sc_item_of(self.语法分析器_操作符栈, self.语法分析器_i)))
            self._yield_frame()
        self.语法分析器_保存当前状态_临时变量 = _sc_join(self.语法分析器_保存当前状态_临时变量, ']]')
        self.语法分析器_状态栈.append(self.语法分析器_保存当前状态_临时变量)


    @_as_procedure(warp=True, arg_types=[], arg_names=[], proccode='语法分析器-保存当前状态')
    def 语法分析器_保存当前状态(self):
        """自制积木: 语法分析器-保存当前状态"""
        self.语法分析器_保存当前状态_临时变量 = _sc_join('[', _sc_join(self.语法分析器_当前选择分支, _sc_join(',', _sc_join(self.语法分析器_i, _sc_join(',', _sc_join(self.语法分析器_row, _sc_join(',', _sc_join(self.语法分析器_Token, _sc_join(',', _sc_join(self.语法分析器_Type, ',['))))))))))
        self.语法分析器_保存当前状态_i = '1'
        self.语法分析器_保存当前状态_临时变量 = _sc_join(self.语法分析器_保存当前状态_临时变量, _sc_item_of(self.语法分析器_嵌套栈, self.语法分析器_i))
        for _repeat in range(_sc_repeat_count(len(self.语法分析器_嵌套栈))):
            self.语法分析器_保存当前状态_i = _sc_add(self.语法分析器_保存当前状态_i, 1)
            self.语法分析器_保存当前状态_临时变量 = _sc_join(self.语法分析器_保存当前状态_临时变量, _sc_join(',', _sc_item_of(self.语法分析器_嵌套栈, self.语法分析器_i)))
            self._yield_frame()
        self.语法分析器_保存当前状态_临时变量 = _sc_join(self.语法分析器_保存当前状态_临时变量, ']]')
        self.语法分析器_状态栈.append(self.语法分析器_保存当前状态_临时变量)


    @_as_procedure(warp=False, arg_types=[], arg_names=[], proccode='词法分析器')
    def 词法分析器(self):
        """自制积木: 词法分析器"""
        self.proc_unnamed_7bc0ee('初始化')
        self.词法分析器_i = '0'
        self.词法分析器_代码嵌套 = ''
        self.词法分析器_当前是否是转义模式 = 'NO'
        self.词法分析器_判断是否能跳出嵌套_ = '0'
        self.词法分析器_Type = 'Note'
        self.词法分析器_Token = ''
        self.Token.clear()
        self.Token_平铺.clear()
        self.词法分析器_判断层数.clear()
        while not _sc_bool(_sc_or(_sc_eq(len(self.输入代码), self.词法分析器_i), _sc_lt(len(self.输入代码), self.词法分析器_i))):
            self.proc_unnamed_7bc0ee('保存行标记')
            self.词法分析器_i = _sc_add(self.词法分析器_i, 1)
            self.词法分析器_Token = self.词法分析器_i
            self.词法分析器_Type = 'line'
            self.词法分析器_保存token()
            self.proc_unnamed_7bc0ee('每一行的初始化')
            self.词法分析器_j = '1'
            self.词法分析器_k = '0'
            self.词法分析器_ki = '0'
            self.词法分析器_kj = '0'
            while not _sc_bool(_sc_or(_sc_eq(_sc_length(_sc_item_of(self.输入代码, self.词法分析器_i)), _sc_sub(self.词法分析器_j, 1)), _sc_lt(_sc_length(_sc_item_of(self.输入代码, self.词法分析器_i)), _sc_sub(self.词法分析器_j, 1)))):
                self.proc_unnamed_7bc0ee('判断当前是什么模式')
                if _sc_bool(_sc_and(_sc_and(_sc_not(_sc_eq(self.词法分析器_Token, 'Note')), _sc_not(_sc_and(_sc_eq(self.词法分析器_i, self.词法分析器_ki), _sc_eq(self.词法分析器_j, self.词法分析器_kj)))), _sc_eq(self.词法分析器_k, '0'))):
                    self.proc_unnamed_7bc0ee('设置每个token的起始列')
                    self.词法分析器_k = self.词法分析器_j
                    self.词法分析器_ki = self.词法分析器_i
                    self.词法分析器_kj = self.词法分析器_j
                if _sc_bool(_sc_not(_sc_and(_sc_eq(self.词法分析器_Type, 'Note'), _sc_eq(_sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)), ' ')))):
                    if _sc_bool(_sc_eq(self.词法分析器_Type, 'Note')):
                        self.proc_unnamed_7bc0ee('判断单行注释')
                        if _sc_bool(_sc_and(_sc_eq(_sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)), '\\'), _sc_eq(_sc_letter_of(_sc_add(self.词法分析器_j, 1), _sc_item_of(self.输入代码, self.词法分析器_i)), '\\'))):
                            self.词法分析器_j = _sc_length(_sc_item_of(self.输入代码, self.词法分析器_i))
                        else:
                            self.proc_unnamed_7bc0ee('判断多行注释')
                            if _sc_bool(_sc_and(_sc_eq(_sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)), '\\'), _sc_eq(_sc_letter_of(_sc_add(self.词法分析器_j, 1), _sc_item_of(self.输入代码, self.词法分析器_i)), '*'))):
                                self.词法分析器_Type = 'Annotation'
                            else:
                                self.proc_unnamed_7bc0ee('如果都不是则判定为Code')
                                self.词法分析器_Type = 'Code'
                    else:
                        self.proc_unnamed_7bc0ee('如果是注释模式(Annotation)则一直匹配到下一个注释结束为止')
                        if _sc_bool(_sc_eq(self.词法分析器_Type, 'Annotation')):
                            self.词法分析器_j = _sc_add(self.词法分析器_j, 1)
                            if _sc_bool(_sc_and(_sc_eq(_sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)), '*'), _sc_eq(_sc_letter_of(_sc_add(self.词法分析器_j, 1), _sc_item_of(self.输入代码, self.词法分析器_i)), '\\'))):
                                self.词法分析器_Type = 'Note'
                                self.词法分析器_j = _sc_add(self.词法分析器_j, 2)
                        else:
                            self.proc_unnamed_7bc0ee('代码模式(Code)的进一步判定')
                            if _sc_bool(_sc_and(_sc_eq(self.词法分析器_Type, 'Code'), _sc_not(_sc_eq(self.词法分析器_Type, '')))):
                                self.词法分析器_初步判断token类型()
                            else:
                                self.proc_unnamed_7bc0ee('进一步分析,并尝试拆解成token')
                                self.词法分析器_进一步进行拆解()
                if _sc_bool(_sc_eq(self.词法分析器_Type, 'Note')):
                    self.proc_unnamed_7bc0ee('跳过没用空格')
                    while not _sc_bool(_sc_not(_sc_eq(_sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)), ' '))):
                        self.词法分析器_j = _sc_add(self.词法分析器_j, 1)
                        self._yield_frame()
                else:
                    if _sc_bool(_sc_eq(self.词法分析器_Type, 'Error')):
                        self.词法分析器_Token = 'Error'
                        self.词法分析器_保存token()
                        self.stop('this script')
                self._yield_frame()
            self.proc_unnamed_7bc0ee('检查是否有没有保存的token，如果有则保存')
            if _sc_bool(_sc_not(_sc_eq(self.词法分析器_Type, 'Note'))):
                self.词法分析器_保存token()
            self._yield_frame()
        self.词法分析器_Token = 'Null'
        self.词法分析器_Type = 'EOF'
        self.词法分析器_保存token()


    @_as_procedure(warp=True, arg_types=[], arg_names=[], proccode='语法分析器-解析表达式-回退最近的状态')
    def 语法分析器_解析表达式_回退最近的状态(self):
        """自制积木: 语法分析器-解析表达式-回退最近的状态"""
        self.语法分析器_回退最近的状态_临时列表.clear()
        self.获取_该列表里面的所有元素_额外选项_是否允许像扩展的那样不需要包含双引号的额外信息_请输入yes或no_默认是no_(_sc_item_of(self.语法分析器_状态栈, len(self.语法分析器_状态栈)), '')
        self.语法分析器_row = _sc_item_of(self.获取列表里面的所有元素_返回值, 3)
        self.语法分析器_Token = _sc_item_of(self.获取列表里面的所有元素_返回值, 4)
        self.语法分析器_Type = _sc_item_of(self.获取列表里面的所有元素_返回值, 5)
        self.语法分析器_嵌套栈.clear()
        self.语法分析器_回退最近的状态_i = '0'
        for _repeat in range(_sc_repeat_count(len(self.获取列表里面的所有元素_返回值))):
            self.语法分析器_回退最近的状态_i = _sc_add(self.语法分析器_回退最近的状态_i, 1)
            self.语法分析器_回退最近的状态_临时列表.append(_sc_item_of(self.获取列表里面的所有元素_返回值, self.语法分析器_回退最近的状态_i))
            self._yield_frame()
        self.获取_该列表里面的所有元素_额外选项_是否允许像扩展的那样不需要包含双引号的额外信息_请输入yes或no_默认是no_(_sc_item_of(self.语法分析器_回退最近的状态_临时列表, 6), '')
        self.语法分析器_回退最近的状态_i = '0'
        for _repeat in range(_sc_repeat_count(len(self.获取列表里面的所有元素_返回值))):
            self.语法分析器_回退最近的状态_i = _sc_add(self.语法分析器_回退最近的状态_i, 1)
            self.语法分析器_操作数栈.append(_sc_item_of(self.获取列表里面的所有元素_返回值, self.语法分析器_回退最近的状态_i))
            self._yield_frame()
        self.获取_该列表里面的所有元素_额外选项_是否允许像扩展的那样不需要包含双引号的额外信息_请输入yes或no_默认是no_(_sc_item_of(self.语法分析器_回退最近的状态_临时列表, 7), '')
        self.语法分析器_回退最近的状态_i = '0'
        for _repeat in range(_sc_repeat_count(len(self.获取列表里面的所有元素_返回值))):
            self.语法分析器_回退最近的状态_i = _sc_add(self.语法分析器_回退最近的状态_i, 1)
            self.语法分析器_操作数栈_类型.append(_sc_item_of(self.获取列表里面的所有元素_返回值, self.语法分析器_回退最近的状态_i))
            self._yield_frame()
        self.获取_该列表里面的所有元素_额外选项_是否允许像扩展的那样不需要包含双引号的额外信息_请输入yes或no_默认是no_(_sc_item_of(self.语法分析器_回退最近的状态_临时列表, 8), '')
        self.语法分析器_回退最近的状态_i = '0'
        for _repeat in range(_sc_repeat_count(len(self.获取列表里面的所有元素_返回值))):
            self.语法分析器_回退最近的状态_i = _sc_add(self.语法分析器_回退最近的状态_i, 1)
            self.语法分析器_操作符栈.append(_sc_item_of(self.获取列表里面的所有元素_返回值, self.语法分析器_回退最近的状态_i))
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s', 's'], arg_names=['a', 'b'], proccode='判断 %s 字符串在 %s 出现几次', arg_ids=['_K[JbWBc%^J9i-n;nFA@', '~~;K]ttH0Jh%`3c.s4,z'], arg_defaults=['', ''])
    def 判断_字符串在_出现几次(self, arg_a=0, arg_b=0):
        """自制积木: 判断 %s 字符串在 %s 出现几次"""
        self.判断a字符串在b字符串出现几次_返回值 = '0'
        self.判断a字符串在b字符串出现几次_i = '0'
        for _repeat in range(_sc_repeat_count(_sc_length(arg_a))):
            self.判断a字符串在b字符串出现几次_j = '0'
            self.判断a字符串在b字符串出现几次_w = ''
            for _repeat in range(_sc_repeat_count(_sc_length(arg_b))):
                self.判断a字符串在b字符串出现几次_j = _sc_add(self.判断a字符串在b字符串出现几次_j, 1)
                self.判断a字符串在b字符串出现几次_w = _sc_join(self.判断a字符串在b字符串出现几次_w, _sc_letter_of(_sc_add(self.判断a字符串在b字符串出现几次_i, self.判断a字符串在b字符串出现几次_j), arg_a))
                self._yield_frame()
            if _sc_bool(_sc_eq(self.判断a字符串在b字符串出现几次_w, arg_b)):
                self.判断a字符串在b字符串出现几次_返回值 = _sc_add(self.判断a字符串在b字符串出现几次_返回值, 1)
            self.判断a字符串在b字符串出现几次_i = _sc_add(self.判断a字符串在b字符串出现几次_i, 1)
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s', 's', 's', 's'], arg_names=['行', '列', '原因', '报错信息'], proccode='添加报错(行: %s ,列: %s ,原因: %s ,报错信息: %s )', arg_ids=['~3Yq@H*+Ps~-:m1P{h:K', 'a*3mU_QCn6o9/tyS:|Yx', '~#5V_}yZ#*xV8!)QYSEz', 'mCEti2bXV1ak1t!EY*Y{'], arg_defaults=['', '', '', ''])
    def 添加报错_行_列_原因_报错信息_(self, arg_行=0, arg_列=0, arg_原因=0, arg_报错信息=0):
        """自制积木: 添加报错(行: %s ,列: %s ,原因: %s ,报错信息: %s )"""
        self.报错_详细信息.append(_sc_join(_sc_join('ASC-Error:\\n', '在行:'), _sc_join(arg_行, _sc_join(',列:', _sc_join(arg_列, _sc_join('中,', _sc_join(arg_原因, _sc_join(':', arg_报错信息))))))))
        self.报错.append(arg_报错信息)


    @_as_procedure(warp=True, arg_types=['s'], arg_names=['字符串'], proccode='对 %s 该字符串进行转义处理', arg_ids=['@I-oS*BqR0PPAmG#[u;^'], arg_defaults=[''])
    def 对_该字符串进行转义处理(self, arg_字符串=0):
        """自制积木: 对 %s 该字符串进行转义处理"""
        self.对字符串进行转义处理_返回值 = ''
        self.对字符串进行转义处理_i = '0'
        while not _sc_bool(_sc_eq(_sc_length(arg_字符串), self.对字符串进行转义处理_i)):
            self.对字符串进行转义处理_i = _sc_add(self.对字符串进行转义处理_i, 1)
            if _sc_bool(_sc_eq(_sc_letter_of(self.对字符串进行转义处理_i, arg_字符串), '"')):
                self.对字符串进行转义处理_返回值 = _sc_join(self.对字符串进行转义处理_返回值, '\\"')
            else:
                self.对字符串进行转义处理_返回值 = _sc_join(self.对字符串进行转义处理_返回值, _sc_letter_of(self.对字符串进行转义处理_i, arg_字符串))
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s', 's', 's'], arg_names=['a', 'b', 'c'], proccode='获取 %s 该字符串的 %s ~ %s 以外的字符', arg_ids=[']?NeU/ICvf[UVIjK%0__', 'XCR_ZO0/CH3A#cRYcha7', '#TU.FEP(42oz4s4Dm7Pz'], arg_defaults=['', '', ''])
    def 获取_该字符串的_以外的字符(self, arg_a=0, arg_b=0, arg_c=0):
        """自制积木: 获取 %s 该字符串的 %s ~ %s 以外的字符"""
        self.获取a该字符串的b_c以外的字符_返回值 = ''
        self.获取a该字符串的b_c以外的字符_i = '0'
        for _repeat in range(_sc_repeat_count(_sc_sub(arg_b, 1))):
            self.获取a该字符串的b_c以外的字符_i = _sc_add(self.获取a该字符串的b_c以外的字符_i, 1)
            self.获取a该字符串的b_c以外的字符_返回值 = _sc_join(self.获取a该字符串的b_c以外的字符_返回值, _sc_letter_of(self.获取a该字符串的b_c以外的字符_i, arg_a))
            self._yield_frame()
        self.获取a该字符串的b_c以外的字符_i = _sc_add(self.获取a该字符串的b_c以外的字符_i, arg_c)
        for _repeat in range(_sc_repeat_count(_sc_add(_sc_sub(_sc_length(arg_a), self.获取a该字符串的b_c个字符_i), 1))):
            self.获取a该字符串的b_c以外的字符_返回值 = _sc_join(self.获取a该字符串的b_c以外的字符_返回值, _sc_letter_of(self.获取a该字符串的b_c以外的字符_i, arg_a))
            self.获取a该字符串的b_c以外的字符_i = _sc_add(self.获取a该字符串的b_c以外的字符_i, 1)
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=[], arg_names=[], proccode='词法分析器:保存token', arg_defaults=[''])
    def 词法分析器_保存token(self):
        """自制积木: 词法分析器:保存token"""
        if _sc_bool(_sc_eq(self.词法分析器_Type, 'Float')):
            if _sc_bool(_sc_or(_sc_eq(_sc_letter_of(1, self.词法分析器_Token), '.'), _sc_eq(_sc_letter_of(_sc_length(self.词法分析器_Token), self.词法分析器_Token), '.'))):
                self.词法分析器_Token = 'Float-Error'
                self.词法分析器_Type = 'Error'
            self.判断_字符串在_出现几次(self.词法分析器_Token, '.')
            if _sc_bool(_sc_gt(self.判断a字符串在b字符串出现几次_返回值, '1')):
                self.词法分析器_Token = 'Float-Error'
                self.词法分析器_Type = 'Error'
        if _sc_bool(_sc_eq(self.词法分析器_Token, '=')):
            self.词法分析器_Type = 'Assignment'
        if _sc_bool(_sc_eq(self.词法分析器_Type, 'Function')):
            if _sc_bool(_sc_list_contains(self.关键字, self.词法分析器_Token)):
                self.proc_unnamed_11ecdd(_sc_item_of(self.关键字, _sc_list_item_number(self.关键字, self.词法分析器_Token)), self.词法分析器_Token)
                if _sc_bool(_sc_eq(self.判断两个字符串是否相等_返回值, 'YES')):
                    if _sc_bool(_sc_list_contains(self.Operator_关键字, self.词法分析器_Token)):
                        self.词法分析器_Type = 'Operator'
                    else:
                        if _sc_bool(_sc_list_contains(self.Keywords_关键字, self.词法分析器_Token)):
                            self.词法分析器_Type = 'Keywords'
                        else:
                            self.词法分析器_Type = 'Built-in_function'
        if _sc_bool(_sc_and(_sc_eq(self.词法分析器_Type, 'Variable'), _sc_not(_sc_eq(_sc_letter_of(1, self.词法分析器_Token), '$')))):
            self.词法分析器_Token = _sc_join('$', self.词法分析器_Token)
        self.Token.append(_sc_join(_sc_join('[', _sc_join(self.词法分析器_k, _sc_join(',', self.词法分析器_Token))), _sc_join(_sc_join(',', self.词法分析器_Type), ']')))
        self.Token_平铺.append(self.词法分析器_k)
        self.Token_平铺.append(self.词法分析器_Token)
        self.Token_平铺.append(self.词法分析器_Type)
        self.词法分析器_k = '0'
        self.词法分析器_Token = ''
        self.词法分析器_Type = 'Note'
        self.词法分析器_j = _sc_add(self.词法分析器_j, 1)


    @_as_procedure(warp=True, arg_types=['s', 's'], arg_names=['A', 'B'], proccode='%s === %s ?', arg_ids=['|K+PDtdjxF!zwCMYmwG^', 'R(qI=VPa/TOKjHHK?}*t'], arg_defaults=['', ''])
    def proc_unnamed_11ecdd(self, arg_A=0, arg_B=0):
        """自制积木: %s === %s ?"""
        self.判断两个字符串是否相等_返回值 = 'NO'
        if _sc_bool(_sc_eq(_sc_length(arg_A), _sc_length(arg_B))):
            self.判断两个字符串是否相等_i = '0'
            for _repeat in range(_sc_repeat_count(_sc_length(arg_A))):
                self.判断两个字符串是否相等_i = _sc_add(self.判断两个字符串是否相等_i, 1)
                if _sc_bool(_sc_eq(arg_A, arg_B)):
                    if _sc_bool(_sc_contains('abcdefghijklnmopqrstuvwxyz', _sc_letter_of(self.判断两个字符串是否相等_i, arg_A))):
                        self.switch_costume(_sc_letter_of(self.判断两个字符串是否相等_i, arg_A))
                        self.判断两个字符串是否相等_v = self.costume_number
                        self.switch_costume(_sc_letter_of(self.判断两个字符串是否相等_i, arg_B))
                        if _sc_bool(_sc_not(_sc_eq(self.判断两个字符串是否相等_v, self.costume_number))):
                            self.stop('this script')
                else:
                    self.stop('this script')
                self._yield_frame()
            self.判断两个字符串是否相等_返回值 = 'YES'


    @_as_procedure(warp=True, arg_types=['s', 's', 's', 's', 's'], arg_names=['节点ID', '节点类型', ' 值', '父节点ID', '层级'], proccode='构建语法树-添加节点 (节点ID: %s ,节点类型: %s ,值: %s ,父节点ID: %s ,层级: %s )', arg_ids=['Lu1IMXfk+dc/g}O#P(+4', '*+YA|zHKs7z_{NVG[r~V', 'u]j|vV{)v=hee0JuOSV9', 'at^o2o:=#8i(_I=B_fDh', 'JQ1yn?;3Ok[R/Xy%+18P'], arg_defaults=['', '', '', '', '', ''])
    def 构建语法树_添加节点_节点ID_节点类型_值_父节点ID_层级_(self, arg_节点ID=0, arg_节点类型=0, arg__值=0, arg_父节点ID=0, arg_层级=0):
        """自制积木: 构建语法树-添加节点 (节点ID: %s ,节点类型: %s ,值: %s ,父节点ID: %s ,层级: %s )"""
        self.语法树.append(arg_节点ID)
        self.语法树.append(arg_节点类型)
        self.语法树.append(arg__值)
        self.语法树.append(arg_父节点ID)
        self.语法树.append(arg_层级)
        self.构建语法树_节点 = _sc_add(self.构建语法树_节点, 1)


    @_as_procedure(warp=True, arg_types=[], arg_names=[], proccode='语法分析器-回退最近的状态')
    def 语法分析器_回退最近的状态(self):
        """自制积木: 语法分析器-回退最近的状态"""
        self.语法分析器_回退最近的状态_临时列表.clear()
        self.获取_该列表里面的所有元素_额外选项_是否允许像扩展的那样不需要包含双引号的额外信息_请输入yes或no_默认是no_(_sc_item_of(self.语法分析器_状态栈, len(self.语法分析器_状态栈)), '')
        self.语法分析器_回退最近的状态_i = '0'
        for _repeat in range(_sc_repeat_count(len(self.获取列表里面的所有元素_返回值))):
            self.语法分析器_回退最近的状态_i = _sc_add(self.语法分析器_回退最近的状态_i, 1)
            self.语法分析器_回退最近的状态_临时列表.append(_sc_item_of(self.获取列表里面的所有元素_返回值, self.语法分析器_回退最近的状态_i))
            self._yield_frame()
        self.语法分析器_当前选择分支 = _sc_item_of(self.获取列表里面的所有元素_返回值, 1)
        self.语法分析器_row = _sc_item_of(self.获取列表里面的所有元素_返回值, 3)
        self.语法分析器_Token = _sc_item_of(self.获取列表里面的所有元素_返回值, 4)
        self.语法分析器_Type = _sc_item_of(self.获取列表里面的所有元素_返回值, 5)
        self.语法分析器_嵌套栈.clear()
        self.语法分析器_回退最近的状态_i = '0'
        self.获取_该列表里面的所有元素_额外选项_是否允许像扩展的那样不需要包含双引号的额外信息_请输入yes或no_默认是no_(_sc_item_of(self.语法分析器_回退最近的状态_临时列表, 6), '')
        for _repeat in range(_sc_repeat_count(len(self.获取列表里面的所有元素_返回值))):
            self.语法分析器_回退最近的状态_i = _sc_add(self.语法分析器_回退最近的状态_i, 1)
            self.语法分析器_嵌套栈.append(_sc_item_of(self.获取列表里面的所有元素_返回值, self.语法分析器_回退最近的状态_i))
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s'], arg_names=['这只是一个注释块'], proccode='// %s', arg_ids=['@TfQpFtZ}CL.sUMK8n@]'], arg_defaults=[''])
    def proc_unnamed_7bc0ee(self, arg_这只是一个注释块=0):
        """自制积木: // %s"""
        pass


    @_as_procedure(warp=True, arg_types=[], arg_names=[], proccode='语法分析器')
    def 语法分析器(self):
        """自制积木: 语法分析器"""
        self.语法分析器_状态栈.clear()
        self.语法分析器_嵌套栈.clear()
        self.语法分析器_当前操作.clear()
        self.语法树.clear()
        self.语法分析器_i = '1'
        self.语法分析器_当前选择分支 = '1'
        while not _sc_bool(_sc_eq(self.语法分析器_Type, 'EOF')):
            self.语法分析器_查看当前token()
            if _sc_bool(_sc_eq(self.语法分析器_Type, 'line')):
                self.语法分析器_line = self.语法分析器_Token
                self.语法分析器_推进token指针()
            if _sc_bool(_sc_eq(self.语法分析器_Type, 'Variable')):
                self.语法分析器_临时存储 = self.语法分析器_Token
                self.语法分析器_当前操作.append(self.语法分析器_Token)
                self.语法分析器_推进并查看token()
                if _sc_bool(_sc_eq(self.语法分析器_Type, 'Assignment')):
                    self.语法分析器_推进并查看token()
                    if _sc_bool(_sc_eq(self.语法分析器_Type, 'Built-in_function')):
                        self.语法分析器_当前操作.append(self.语法分析器_Token)
                        self.语法分析器_推进并查看token()
                        if _sc_bool(_sc_and(_sc_eq(self.语法分析器_Type, 'Parameter'), _sc_eq(self.语法分析器_Token, 'Start'))):
                            self.语法分析器_推进并查看token()
                            if _sc_bool(_sc_eq(self.语法分析器_Type, 'String-2')):
                                self.语法分析器_推进并查看token()
                                if _sc_bool(_sc_and(_sc_eq(self.语法分析器_Type, 'Parameter'), _sc_eq(self.语法分析器_Token, 'End'))):
                                    self.语法分析器_推进并查看token()
                else:
                    pass
            self._yield_frame()
        self.构建语法树_节点 = '0'
        self.构建语法树_添加节点_节点ID_节点类型_值_父节点ID_层级_(self.构建语法树_节点, 'Call', _sc_item_of(self.语法分析器_当前操作, len(self.语法分析器_当前操作)), '0', '0')
        _sc_list_delete(self.语法分析器_当前操作, len(self.语法分析器_当前操作))
        self.构建语法树_添加节点_节点ID_节点类型_值_父节点ID_层级_(self.构建语法树_节点, 'Assignment', _sc_item_of(self.语法分析器_当前操作, len(self.语法分析器_当前操作)), '0', '0')
        _sc_list_delete(self.语法分析器_当前操作, len(self.语法分析器_当前操作))


    @_as_procedure(warp=True, arg_types=[], arg_names=[], proccode='语法分析器:推进并查看token')
    def 语法分析器_推进并查看token(self):
        """自制积木: 语法分析器:推进并查看token"""
        self.语法分析器_推进token指针()
        self.语法分析器_查看当前token()


    @_as_procedure(warp=True, arg_types=['s', 's', 's'], arg_names=['节点ID', '新父节点', '新层级'], proccode='构建语法树-更改节点(节点ID: %s ,新父节点: %s ,新层级: %s )', arg_ids=['Izjm.M^nNZB(.*:/m1o^', 'P|3zjkx{:Cpb3|SFRUPa', 'hBx-5#XmhNR/kUp%%=JZ'], arg_defaults=['', '', ''])
    def 构建语法树_更改节点_节点ID_新父节点_新层级_(self, arg_节点ID=0, arg_新父节点=0, arg_新层级=0):
        """自制积木: 构建语法树-更改节点(节点ID: %s ,新父节点: %s ,新层级: %s )"""
        _sc_list_replace(self.语法树, _sc_add(_sc_mul(arg_节点ID, 5), 4), arg_新父节点)
        _sc_list_replace(self.语法树, _sc_add(_sc_mul(arg_节点ID, 5), 5), arg_新层级)


    @_as_procedure(warp=True, arg_types=['s', 's', 's'], arg_names=['a', 'b', 'c'], proccode='获取 %s 该字符串的 %s ~ %s 个字符', arg_ids=[']?NeU/ICvf[UVIjK%0__', 'XCR_ZO0/CH3A#cRYcha7', '#TU.FEP(42oz4s4Dm7Pz'], arg_defaults=['', '', ''])
    def 获取_该字符串的_个字符(self, arg_a=0, arg_b=0, arg_c=0):
        """自制积木: 获取 %s 该字符串的 %s ~ %s 个字符"""
        self.获取a该字符串的b_c个字符_返回值 = ''
        self.获取a该字符串的b_c个字符_i = _sc_sub(arg_b, 1)
        for _repeat in range(_sc_repeat_count(_sc_add(_sc_sub(arg_c, arg_b), 1))):
            self.获取a该字符串的b_c个字符_i = _sc_add(self.获取a该字符串的b_c个字符_i, 1)
            self.获取a该字符串的b_c个字符_返回值 = _sc_join(self.获取a该字符串的b_c个字符_返回值, _sc_letter_of(self.获取a该字符串的b_c个字符_i, arg_a))
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=[], arg_names=[], proccode='词法分析器:初步判断token类型')
    def 词法分析器_初步判断token类型(self):
        """自制积木: 词法分析器:初步判断token类型"""
        if _sc_bool(_sc_contains('abcdefghijklnmopqrstuvwxyz_', _sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)))):
            self.词法分析器_j = _sc_add(self.词法分析器_j, -1)
            self.词法分析器_Type = 'Function'
            self.stop('this script')
        if _sc_bool(_sc_contains('1234567890', _sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)))):
            self.词法分析器_j = _sc_add(self.词法分析器_j, -1)
            self.词法分析器_Type = 'Number'
            self.stop('this script')
        if _sc_bool(_sc_eq(_sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)), '.')):
            self.词法分析器_Type = 'Dotted'
            self.词法分析器_Token = 'Dotted'
            self.词法分析器_保存token()
        if _sc_bool(_sc_eq(_sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)), '$')):
            self.词法分析器_Type = 'Variable'
            self.stop('this script')
        if _sc_bool(_sc_contains('\'"', _sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)))):
            if _sc_bool(_sc_eq(_sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)), '1')):
                self.词法分析器_Type = 'String-1'
            else:
                self.词法分析器_Type = 'String-2'
            self.stop('this script')
        if _sc_bool(_sc_contains('[]', _sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)))):
            if _sc_bool(_sc_eq(_sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)), '[')):
                self.词法分析器_Type = 'List'
                self.词法分析器_Token = 'Start'
                self.词法分析器_保存token()
            else:
                self.词法分析器_Type = 'List'
                self.词法分析器_Token = 'End'
                self.词法分析器_保存token()
            self.stop('this script')
        if _sc_bool(_sc_eq(_sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)), ';')):
            self.词法分析器_Type = 'Separate'
            self.词法分析器_Token = ';'
            self.词法分析器_k = self.词法分析器_j
            self.词法分析器_保存token()
            self.stop('this script')
        if _sc_bool(_sc_and(_sc_contains('+-*/=><!', _sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i))), _sc_not(_sc_eq(_sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)), '')))):
            if _sc_bool(_sc_list_contains(self.运算符组合列表, _sc_join(_sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)), _sc_letter_of(_sc_add(self.词法分析器_j, 1), _sc_item_of(self.输入代码, self.词法分析器_i))))):
                self.词法分析器_Token = _sc_join(_sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)), _sc_letter_of(_sc_add(self.词法分析器_j, 1), _sc_item_of(self.输入代码, self.词法分析器_i)))
                self.词法分析器_Type = 'Operator'
                self.词法分析器_j = _sc_add(self.词法分析器_j, 1)
                self.词法分析器_保存token()
            else:
                self.词法分析器_Token = _sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i))
                self.词法分析器_Type = 'Operator'
                self.词法分析器_保存token()
            self.stop('this script')
        if _sc_bool(_sc_and(_sc_contains('{}', _sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i))), _sc_not(_sc_eq(_sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)), '')))):
            if _sc_bool(_sc_eq(_sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)), '{')):
                self.获取_该列表里面的所有元素_额外选项_是否允许像扩展的那样不需要包含双引号的额外信息_请输入yes或no_默认是no_(_sc_item_of(self.Token, len(self.Token)), '')
                if _sc_bool(_sc_or(_sc_and(_sc_eq(_sc_item_of(self.获取列表里面的所有元素_返回值, 2), 'End'), _sc_eq(_sc_item_of(self.获取列表里面的所有元素_返回值, 3), 'Parameter')), _sc_or(_sc_and(_sc_eq(_sc_item_of(self.获取列表里面的所有元素_返回值, 2), 'else'), _sc_eq(_sc_item_of(self.获取列表里面的所有元素_返回值, 3), 'Keywords')), _sc_or(_sc_and(_sc_eq(_sc_item_of(self.获取列表里面的所有元素_返回值, 2), 'try'), _sc_eq(_sc_item_of(self.获取列表里面的所有元素_返回值, 3), 'Keywords')), _sc_and(_sc_eq(_sc_item_of(self.获取列表里面的所有元素_返回值, 2), 'except'), _sc_eq(_sc_item_of(self.获取列表里面的所有元素_返回值, 3), 'Keywords')))))):
                    self.词法分析器_Type = 'Code_block'
                    self.词法分析器_Token = 'Start'
                    self.词法分析器_代码嵌套 = _sc_join(self.词法分析器_代码嵌套, '~')
                else:
                    if _sc_bool(_sc_eq(self.词法分析器_k, 'Assignment')):
                        self.词法分析器_Type = 'Dictionary'
                        self.词法分析器_Token = 'Start'
                        self.词法分析器_代码嵌套 = _sc_join(self.词法分析器_代码嵌套, '{')
                self.词法分析器_保存token()
                self.stop('this script')
            else:
                if _sc_bool(_sc_contains('~{', _sc_letter_of(_sc_length(self.词法分析器_代码嵌套), self.词法分析器_代码嵌套))):
                    if _sc_bool(_sc_eq(_sc_letter_of(_sc_length(self.词法分析器_代码嵌套), self.词法分析器_代码嵌套), '~')):
                        self.词法分析器_Type = 'Code_block'
                        self.词法分析器_Token = 'End'
                        self.词法分析器_保存token()
                    else:
                        self.词法分析器_Type = 'Dictionary'
                        self.词法分析器_Token = 'End'
                        self.词法分析器_保存token()
                        self.获取_该字符串的_个字符(self.词法分析器_代码嵌套, '1', _sc_sub(_sc_length(self.词法分析器_代码嵌套), 1))
                        self.词法分析器_代码嵌套 = self.获取a该字符串的b_c个字符_返回值
                else:
                    self.词法分析器_Type = 'Error'
                self.stop('this script')
        if _sc_bool(_sc_and(_sc_contains('()', _sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i))), _sc_not(_sc_eq(_sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)), '')))):
            self.获取_该列表里面的所有元素_额外选项_是否允许像扩展的那样不需要包含双引号的额外信息_请输入yes或no_默认是no_(_sc_item_of(self.Token, len(self.Token)), '')
            if _sc_bool(_sc_or(_sc_eq(_sc_item_of(self.获取列表里面的所有元素_返回值, 3), 'Built-in_function'), _sc_eq(_sc_item_of(self.获取列表里面的所有元素_返回值, 3), 'Keywords'))):
                self.词法分析器_Token = 'Start'
                self.词法分析器_Type = 'Parameter'
                self.词法分析器_k = _sc_sub(self.词法分析器_j, 1)
                self.词法分析器_保存token()
                self.词法分析器_判断层数.append('Parameter')
                self.词法分析器_判断层数.append('Start')
            else:
                if _sc_bool(_sc_or(_sc_eq(_sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)), '('), _sc_and(_sc_eq(_sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)), ')'), _sc_not(_sc_eq(self.词法分析器_表达式嵌套层数, '0'))))):
                    self.词法分析器_j = _sc_add(self.词法分析器_j, -1)
                    self.词法分析器_Type = 'Expression'
                else:
                    if _sc_bool(_sc_eq(_sc_item_of(self.词法分析器_判断层数, _sc_sub(len(self.词法分析器_判断层数), 1)), 'Parameter')):
                        if _sc_bool(_sc_and(_sc_eq(_sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)), ')'), _sc_and(_sc_eq(self.词法分析器_表达式嵌套层数, '0'), _sc_eq(self.词法分析器_Type, 'Code')))):
                            _sc_list_delete(self.词法分析器_判断层数, len(self.词法分析器_判断层数))
                            _sc_list_delete(self.词法分析器_判断层数, len(self.词法分析器_判断层数))
                            self.词法分析器_Token = 'End'
                            self.词法分析器_Type = 'Parameter'
                            self.词法分析器_k = self.词法分析器_j
                            self.词法分析器_保存token()
                        else:
                            pass
            self.stop('this script')
        if _sc_bool(_sc_and(_sc_eq(_sc_item_of(self.词法分析器_判断层数, _sc_sub(len(self.词法分析器_判断层数), 1)), 'Parameter'), _sc_eq(_sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)), ','))):
            self.词法分析器_Token = 'Parameter Separation'
            self.词法分析器_Type = 'Parameter Separation'
            self.词法分析器_k = self.词法分析器_j
            self.词法分析器_保存token()
            self.stop('this script')
        else:
            self.proc_unnamed_7bc0ee('后续根据需要扩展')
            self.词法分析器_Type = 'Error'


    @_as_procedure(warp=True, arg_types=['s', 's'], arg_names=['a', 'b'], proccode='判断 %s 字符串在 %s 字符串第一次出现的索引位置', arg_ids=['_K[JbWBc%^J9i-n;nFA@', '~~;K]ttH0Jh%`3c.s4,z'], arg_defaults=['', ''])
    def 判断_字符串在_字符串第一次出现的索引位置(self, arg_a=0, arg_b=0):
        """自制积木: 判断 %s 字符串在 %s 字符串第一次出现的索引位置"""
        self.判断a字符串在b字符串第一次出现的索引位置_返回值 = '0'
        self.判断a字符串在b字符串第一次出现的索引位置_i = '0'
        for _repeat in range(_sc_repeat_count(_sc_length(arg_a))):
            self.判断a字符串在b字符串第一次出现的索引位置_j = '0'
            self.判断a字符串在b字符串第一次出现的索引位置_w = ''
            for _repeat in range(_sc_repeat_count(_sc_length(arg_b))):
                self.判断a字符串在b字符串第一次出现的索引位置_j = _sc_add(self.判断a字符串在b字符串第一次出现的索引位置_j, 1)
                self.判断a字符串在b字符串第一次出现的索引位置_w = _sc_join(self.判断a字符串在b字符串第一次出现的索引位置_w, _sc_letter_of(_sc_add(self.判断a字符串在b字符串第一次出现的索引位置_i, self.判断a字符串在b字符串第一次出现的索引位置_j), arg_a))
                self._yield_frame()
            self.判断a字符串在b字符串第一次出现的索引位置_i = _sc_add(self.判断a字符串在b字符串第一次出现的索引位置_i, 1)
            if _sc_bool(_sc_eq(self.判断a字符串在b字符串第一次出现的索引位置_w, arg_b)):
                self.判断a字符串在b字符串第一次出现的索引位置_返回值 = self.判断a字符串在b字符串第一次出现的索引位置_i
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s'], arg_names=['终止token'], proccode='语法分析器-解析表达式 %s', arg_ids=['@Si(-Y|^x?l_;w;B;r[#'], arg_defaults=[''])
    def 语法分析器_解析表达式(self, arg_终止token=0):
        """自制积木: 语法分析器-解析表达式 %s"""
        self.语法分析器_解析表达式_查看当前是否应该终止_返回值 = 'NO'
        self.语法分析器_解析表达式_临时列表.clear()
        self.语法分析器_操作数栈_类型.clear()
        self.语法分析器_操作符栈.clear()
        self.语法分析器_操作数栈.clear()
        self.获取_该列表里面的所有元素_额外选项_是否允许像扩展的那样不需要包含双引号的额外信息_请输入yes或no_默认是no_(arg_终止token, '')
        for _repeat in range(_sc_repeat_count(len(self.获取列表里面的所有元素_返回值))):
            self.语法分析器_解析表达式_结束token.append(_sc_item_of(self.获取列表里面的所有元素_返回值, 1))
            self.语法分析器_解析表达式_结束type.append(_sc_item_of(self.获取列表里面的所有元素_返回值, 2))
            _sc_list_delete(self.获取列表里面的所有元素_返回值, 1)
            _sc_list_delete(self.获取列表里面的所有元素_返回值, 1)
            self._yield_frame()
        while not _sc_bool(_sc_eq(self.语法分析器_解析表达式_查看当前是否应该终止_返回值, 'YES')):
            self.语法分析器_查看当前token()
            self.语法分析器_解析表达式_查看当前是否应该终止()
            if _sc_bool(_sc_eq(self.词法分析器_Type, 'Expression')):
                if _sc_bool(_sc_eq(self.词法分析器_Token, 'Start')):
                    self.语法分析器_操作符栈.append('(')
                else:
                    while not _sc_bool(_sc_or(_sc_eq(_sc_item_of(self.语法分析器_操作符栈, len(self.语法分析器_操作符栈)), '('), _sc_eq(len(self.语法分析器_操作符栈), '0'))):
                        self.语法分析器_解析表达式_弹栈并构建UnaryOp()
                        self._yield_frame()
            if _sc_bool(_sc_eq(self.词法分析器_Type, 'Operator')):
                if _sc_bool(_sc_or(_sc_eq(len(self.语法分析器_操作符栈), '0'), _sc_eq(_sc_item_of(self.语法分析器_操作符栈, len(self.语法分析器_操作符栈)), '('))):
                    self.语法分析器_操作符栈.append(self.词法分析器_Token)
                else:
                    self.语法分析器_解析表达式_获取优先级(_sc_item_of(self.语法分析器_操作符栈, len(self.语法分析器_操作符栈)))
                    self.语法分析器_解析表达式_获取优先级_临时存储 = self.语法分析器_解析表达式_获取优先级_返回值
                    self.语法分析器_解析表达式_获取优先级(self.词法分析器_Token)
                    if _sc_bool(_sc_eq(_sc_item_of(self.语法分析器_操作符栈, len(self.语法分析器_操作符栈)), '**')):
                        if _sc_bool(_sc_lt(self.语法分析器_解析表达式_获取优先级_临时存储, self.语法分析器_解析表达式_获取优先级_返回值)):
                            self.语法分析器_解析表达式_弹栈并构建UnaryOp()
                    else:
                        if _sc_bool(_sc_or(_sc_eq(self.语法分析器_解析表达式_获取优先级_返回值, self.语法分析器_解析表达式_获取优先级_临时存储), _sc_gt(self.语法分析器_解析表达式_获取优先级_临时存储, self.语法分析器_解析表达式_获取优先级_返回值))):
                            self.语法分析器_解析表达式_弹栈并构建UnaryOp()
            if _sc_bool(_sc_or(_sc_or(_sc_eq(self.词法分析器_Type, 'Integer'), _sc_eq(self.词法分析器_Type, 'Float')), _sc_or(_sc_eq(self.词法分析器_Type, 'Srting-1'), _sc_eq(self.词法分析器_Type, 'Srting-2')))):
                self.语法分析器_操作数栈.append(self.词法分析器_Token)
                self.语法分析器_操作数栈_类型.append(self.词法分析器_Type)
            self.语法分析器_推进token指针()
            self._yield_frame()
        while not _sc_bool(_sc_eq(len(self.语法分析器_操作符栈), '0')):
            self.语法分析器_解析表达式_弹栈并构建UnaryOp()
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=[], arg_names=[], proccode='语法分析器-解析表达式-查看当前是否应该终止')
    def 语法分析器_解析表达式_查看当前是否应该终止(self):
        """自制积木: 语法分析器-解析表达式-查看当前是否应该终止"""
        self.语法分析器_解析表达式_查看当前是否应该终止_返回值 = 'NO'
        self.语法分析器_解析表达式_查看当前是否应该终止_i = '0'
        for _repeat in range(_sc_repeat_count(len(self.语法分析器_解析表达式_结束type))):
            self.语法分析器_解析表达式_查看当前是否应该终止_i = _sc_add(self.语法分析器_解析表达式_查看当前是否应该终止_i, 1)
            if _sc_bool(_sc_and(_sc_eq(self.语法分析器_Token, _sc_item_of(self.语法分析器_解析表达式_结束token, self.语法分析器_解析表达式_查看当前是否应该终止_i)), _sc_eq(self.语法分析器_Type, _sc_item_of(self.语法分析器_解析表达式_结束type, self.语法分析器_解析表达式_查看当前是否应该终止_i)))):
                self.语法分析器_解析表达式_查看当前是否应该终止_返回值 = 'YES'
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=['s'], arg_names=['指针'], proccode='语法分析器:强制将token指针移到 %s 的位置', arg_ids=['YtA9^F8mR+kNwAAYHc^A'], arg_defaults=[''])
    def 语法分析器_强制将token指针移到_的位置(self, arg_指针=0):
        """自制积木: 语法分析器:强制将token指针移到 %s 的位置"""
        self.语法分析器_i = arg_指针


    @_as_procedure(warp=True, arg_types=[], arg_names=[], proccode='语法分析器:推进token指针')
    def 语法分析器_推进token指针(self):
        """自制积木: 语法分析器:推进token指针"""
        self.语法分析器_i = _sc_add(self.语法分析器_i, 1)


    @_as_procedure(warp=True, arg_types=['s', 's'], arg_names=['a', 'b'], proccode='判断 %s 字符串是否只由 %s 字符串组成', arg_ids=['_K[JbWBc%^J9i-n;nFA@', '~~;K]ttH0Jh%`3c.s4,z'], arg_defaults=['', ''])
    def 判断_字符串是否只由_字符串组成(self, arg_a=0, arg_b=0):
        """自制积木: 判断 %s 字符串是否只由 %s 字符串组成"""
        self.判断a字符串是否只由b字符串组成_返回值 = 'YES'
        self.判断a字符串是否只由b字符串组成_i = '0'
        for _repeat in range(_sc_repeat_count(_sc_length(arg_a))):
            self.判断a字符串是否只由b字符串组成_i = _sc_add(self.判断a字符串是否只由b字符串组成_i, 1)
            if _sc_bool(_sc_not(_sc_contains(arg_b, _sc_letter_of(self.判断a字符串是否只由b字符串组成_i, arg_a)))):
                self.判断a字符串是否只由b字符串组成_返回值 = 'NO'
                self.stop('this script')
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=[], arg_names=[], proccode='语法分析器:查看当前token')
    def 语法分析器_查看当前token(self):
        """自制积木: 语法分析器:查看当前token"""
        self.语法分析器_row = _sc_item_of(self.Token_平铺, _sc_add(_sc_mul(_sc_sub(self.语法分析器_i, 1), 3), 1))
        self.语法分析器_Token = _sc_item_of(self.Token_平铺, _sc_add(_sc_mul(_sc_sub(self.语法分析器_i, 1), 3), 2))
        self.语法分析器_Type = _sc_item_of(self.Token_平铺, _sc_add(_sc_mul(_sc_sub(self.语法分析器_i, 1), 3), 3))


    @_as_procedure(warp=True, arg_types=[], arg_names=[], proccode='语法分析器-跳过当前行')
    def 语法分析器_跳过当前行(self):
        """自制积木: 语法分析器-跳过当前行"""
        self.语法分析器_查看后_几个token数据('1')
        if _sc_bool(_sc_or(_sc_eq(self.语法分析器_Type, 'line'), _sc_eq(self.语法分析器_Type, 'EOF'))):
            self.语法分析器_推进token指针()
            self.stop('this script')
        while not _sc_bool(_sc_or(_sc_eq(self.语法分析器_Type, 'line'), _sc_eq(self.语法分析器_Type, 'EOF'))):
            self.语法分析器_推进token指针()
            self.语法分析器_查看后_几个token数据('1')
            self._yield_frame()


    @_as_procedure(warp=True, arg_types=[], arg_names=[], proccode='词法分析器-进一步进行拆解')
    def 词法分析器_进一步进行拆解(self):
        """自制积木: 词法分析器-进一步进行拆解"""
        self.词法分析器_j = _sc_add(self.词法分析器_j, 1)
        if _sc_bool(_sc_or(_sc_eq(self.词法分析器_Type, 'String-1'), _sc_eq(self.词法分析器_Type, 'String-2'))):
            if _sc_bool(_sc_eq(self.词法分析器_当前是否是转义模式, 'NO')):
                if _sc_bool(_sc_eq(_sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)), '\\')):
                    self.词法分析器_当前是否是转义模式 = 'YES'
                    self.词法分析器_Token = _sc_join(self.词法分析器_Token, _sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)))
                else:
                    if _sc_bool(_sc_or(_sc_and(_sc_eq(self.词法分析器_Type, 'String-1'), _sc_eq(_sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)), "'")), _sc_and(_sc_eq(self.词法分析器_Type, 'String-2'), _sc_eq(_sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)), '"')))):
                        self.词法分析器_Token = _sc_join('"', _sc_join(self.词法分析器_Token, '"'))
                        self.词法分析器_保存token()
                    else:
                        self.词法分析器_Token = _sc_join(self.词法分析器_Token, _sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)))
            else:
                self.词法分析器_Token = _sc_join(self.词法分析器_Token, _sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)))
                self.词法分析器_当前是否是转义模式 = 'NO'
        else:
            if _sc_bool(_sc_eq(self.词法分析器_Type, 'Error')):
                self.词法分析器_Token = 'Error'
                self.词法分析器_保存token()
                self.stop('this script')
            else:
                if _sc_bool(_sc_not(_sc_eq(_sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)), ' '))):
                    if _sc_bool(_sc_or(_sc_eq(self.词法分析器_Type, 'Number'), _sc_or(_sc_eq(self.词法分析器_Type, 'Integer'), _sc_eq(self.词法分析器_Type, 'Float')))):
                        self.判断_字符串是否只由_字符串组成(_sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)), '1234567890')
                        if _sc_bool(_sc_and(_sc_eq(self.判断a字符串是否只由b字符串组成_返回值, 'YES'), _sc_or(_sc_eq(self.词法分析器_Type, 'Number'), _sc_eq(self.词法分析器_Type, 'Integer')))):
                            self.词法分析器_Type = 'Integer'
                        else:
                            self.词法分析器_Type = 'Float'
                        self.词法分析器_Token = _sc_join(self.词法分析器_Token, _sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)))
                        if _sc_bool(_sc_not(_sc_contains('1234567890.', _sc_letter_of(_sc_add(self.词法分析器_j, 1), _sc_item_of(self.输入代码, self.词法分析器_i))))):
                            self.词法分析器_保存token()
                    else:
                        if _sc_bool(_sc_eq(self.词法分析器_Type, 'Expression')):
                            if _sc_bool(_sc_eq(_sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)), '(')):
                                self.词法分析器_表达式嵌套层数 = _sc_add(self.词法分析器_表达式嵌套层数, 1)
                                self.词法分析器_Token = 'Start'
                                self.词法分析器_保存token()
                            else:
                                self.词法分析器_表达式嵌套层数 = _sc_add(self.词法分析器_表达式嵌套层数, -1)
                                self.词法分析器_Token = 'End'
                                self.词法分析器_保存token()
                        else:
                            if _sc_bool(_sc_eq(self.词法分析器_Type, 'Function')):
                                self.判断_字符串是否只由_字符串组成(_sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)), '1234567890abcdefghijklnmopqrstuvwxyz_')
                                if _sc_bool(_sc_eq(self.判断a字符串是否只由b字符串组成_返回值, 'YES')):
                                    self.词法分析器_Token = _sc_join(self.词法分析器_Token, _sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)))
                                else:
                                    self.词法分析器_保存token()
                                    self.词法分析器_j = _sc_add(self.词法分析器_j, -1)
                            else:
                                if _sc_bool(_sc_eq(self.词法分析器_Type, 'Variable')):
                                    self.判断_字符串是否只由_字符串组成(_sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)), '1234567890abcdefghijklnmopqrstuvwxyz_')
                                    if _sc_bool(_sc_eq(self.判断a字符串是否只由b字符串组成_返回值, 'YES')):
                                        self.词法分析器_Token = _sc_join(self.词法分析器_Token, _sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)))
                                    else:
                                        if _sc_bool(_sc_not(_sc_eq(_sc_letter_of(self.词法分析器_j, _sc_item_of(self.输入代码, self.词法分析器_i)), ' '))):
                                            self.词法分析器_Token = _sc_join('$', self.词法分析器_Token)
                                            self.词法分析器_保存token()
                                            self.词法分析器_j = _sc_add(self.词法分析器_j, -1)
                                else:
                                    if _sc_bool(_sc_eq(self.词法分析器_Type, 'Error')):
                                        self.词法分析器_Token = 'Error'
                                        self.词法分析器_保存token()
                                        self.stop('this script')
                                    else:
                                        pass
                else:
                    self.词法分析器_保存token()


    @_as_procedure(warp=True, arg_types=['s'], arg_names=['运算符'], proccode='语法分析器-解析表达式-获取优先级 %s', arg_ids=['H90w~46AU5t^Vh{n#.1='], arg_defaults=[''])
    def 语法分析器_解析表达式_获取优先级(self, arg_运算符=0):
        """自制积木: 语法分析器-解析表达式-获取优先级 %s"""
        self.语法分析器_解析表达式_获取优先级_返回值 = '0'
        if _sc_bool(_sc_contains('+-', arg_运算符)):
            self.语法分析器_解析表达式_获取优先级_返回值 = '1'
        if _sc_bool(_sc_contains('*/', arg_运算符)):
            self.语法分析器_解析表达式_获取优先级_返回值 = '2'
        if _sc_bool(_sc_eq(arg_运算符, '**')):
            self.语法分析器_解析表达式_获取优先级_返回值 = '3'


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


    @_as_procedure(warp=True, arg_types=[], arg_names=[], proccode='语法分析器-解析表达式-弹栈并构建UnaryOp')
    def 语法分析器_解析表达式_弹栈并构建UnaryOp(self):
        """自制积木: 语法分析器-解析表达式-弹栈并构建UnaryOp"""
        self.语法分析器_解析表达式_弹栈并构建BinOp_运算符节点 = '0'
        self.构建语法树_添加节点_节点ID_节点类型_值_父节点ID_层级_(self.构建语法树_节点, 'UnaryOp', self.语法分析器_Token, '0', '0')
        self.语法分析器_解析表达式_弹栈并构建UnaryOp_运算符节点 = _sc_sub(self.构建语法树_节点, 1)
        if _sc_bool(_sc_or(_sc_eq(_sc_item_of(self.语法分析器_操作数栈_类型, len(self.语法分析器_操作数栈_类型)), 'BinOp'), _sc_eq(_sc_item_of(self.语法分析器_操作数栈_类型, len(self.语法分析器_操作数栈_类型)), 'UnaryOp'))):
            self.构建语法树_更改节点_节点ID_新父节点_新层级_(_sc_item_of(self.语法分析器_操作数栈, len(self.语法分析器_操作数栈)), self.语法分析器_解析表达式_弹栈并构建UnaryOp_运算符节点, '0')
        else:
            self.构建语法树_添加节点_节点ID_节点类型_值_父节点ID_层级_(self.构建语法树_节点, _sc_item_of(self.语法分析器_操作数栈_类型, len(self.语法分析器_操作数栈_类型)), _sc_item_of(self.语法分析器_操作数栈, len(self.语法分析器_操作数栈)), self.语法分析器_解析表达式_弹栈并构建UnaryOp_运算符节点, '0')
            _sc_list_delete(self.语法分析器_操作数栈, len(self.语法分析器_操作数栈))
            _sc_list_delete(self.语法分析器_操作数栈_类型, len(self.语法分析器_操作数栈_类型))
        _sc_list_delete(self.语法分析器_操作符栈, len(self.语法分析器_操作符栈))
        self.语法分析器_操作数栈.append(self.语法分析器_解析表达式_弹栈并构建UnaryOp_运算符节点)
        self.语法分析器_操作数栈_类型.append('UnaryOp')


    @_as_procedure(warp=True, arg_types=['s'], arg_names=['后几个'], proccode='语法分析器:查看后 %s 几个token数据', arg_ids=['}jU?#Wd(g{`)@Z4_?seE'], arg_defaults=[''])
    def 语法分析器_查看后_几个token数据(self, arg_后几个=0):
        """自制积木: 语法分析器:查看后 %s 几个token数据"""
        self.语法分析器_row = _sc_item_of(self.Token_平铺, _sc_add(_sc_mul(_sc_sub(_sc_add(self.词法分析器_i, arg_后几个), 1), 3), 1))
        self.语法分析器_Token = _sc_item_of(self.Token_平铺, _sc_add(_sc_mul(_sc_sub(_sc_add(self.词法分析器_i, arg_后几个), 1), 3), 2))
        self.语法分析器_Type = _sc_item_of(self.Token_平铺, _sc_add(_sc_mul(_sc_sub(_sc_add(self.词法分析器_i, arg_后几个), 1), 3), 3))


    @_as_procedure(warp=True, arg_types=[], arg_names=[], proccode='语法分析器-解析表达式-弹栈并构建BinOp')
    def 语法分析器_解析表达式_弹栈并构建BinOp(self):
        """自制积木: 语法分析器-解析表达式-弹栈并构建BinOp"""
        self.语法分析器_解析表达式_弹栈并构建BinOp_运算符节点 = '0'
        self.构建语法树_添加节点_节点ID_节点类型_值_父节点ID_层级_(self.构建语法树_节点, 'BinOp', _sc_item_of(self.语法分析器_操作符栈, len(self.语法分析器_操作符栈)), '0', '0')
        self.语法分析器_解析表达式_弹栈并构建BinOp_运算符节点 = _sc_sub(self.构建语法树_节点, 1)
        for _repeat in range(_sc_repeat_count(2)):
            if _sc_bool(_sc_or(_sc_eq(_sc_item_of(self.语法分析器_操作数栈_类型, len(self.语法分析器_操作数栈_类型)), 'BinOp'), _sc_eq(_sc_item_of(self.语法分析器_操作数栈_类型, len(self.语法分析器_操作数栈_类型)), 'UnaryOp'))):
                self.构建语法树_更改节点_节点ID_新父节点_新层级_(_sc_item_of(self.语法分析器_操作数栈, len(self.语法分析器_操作数栈)), self.语法分析器_解析表达式_弹栈并构建BinOp_运算符节点, '0')
            else:
                self.构建语法树_添加节点_节点ID_节点类型_值_父节点ID_层级_(self.构建语法树_节点, _sc_item_of(self.语法分析器_操作数栈_类型, len(self.语法分析器_操作数栈_类型)), _sc_item_of(self.语法分析器_操作数栈, len(self.语法分析器_操作数栈)), self.语法分析器_解析表达式_弹栈并构建BinOp_运算符节点, '0')
                _sc_list_delete(self.语法分析器_操作数栈, len(self.语法分析器_操作数栈))
                _sc_list_delete(self.语法分析器_操作数栈_类型, len(self.语法分析器_操作数栈_类型))
            self._yield_frame()
        self.语法分析器_操作数栈.append(self.语法分析器_解析表达式_弹栈并构建BinOp_运算符节点)
        self.语法分析器_操作数栈_类型.append('BinOp')
        self.语法分析器_操作符栈.append(self.语法分析器_Token)


    @_as_procedure(warp=True, arg_types=['s', 's'], arg_names=['列表', '是否允许像扩展的那样不需要包含双引号的额外信息'], proccode='获取 %s 该列表里面的所有元素,额外选项:(是否允许像扩展的那样不需要包含双引号的额外信息(请输入yes或no,默认是no): %s', arg_ids=['=yU}?H7?`kJK:a/)yd:O', 'BZVL.A9BqesvJYeQ6Zmb'], arg_defaults=['', '', ''])
    def 获取_该列表里面的所有元素_额外选项_是否允许像扩展的那样不需要包含双引号的额外信息_请输入yes或no_默认是no_(self, arg_列表=0, arg_是否允许像扩展的那样不需要包含双引号的额外信息=0):
        """自制积木: 获取 %s 该列表里面的所有元素,额外选项:(是否允许像扩展的那样不需要包含双引号的额外信息(请输入yes或no,默认是no): %s"""
        self.获取列表里面的所有元素_返回值.clear()
        self.获取列表里面的所有元素_i = '0'
        self.获取列表里面的所有元素_j = '0'
        self.获取列表里面的所有元素_当前是否是转义模式 = 'NO'
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
                        if _sc_bool(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), '\\')):
                            if _sc_bool(_sc_or(_sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-1'), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-2'))):
                                if _sc_bool(_sc_eq(self.获取列表里面的所有元素_当前是否是转义模式, 'YES')):
                                    self.获取列表里面的所有元素_当前是否是转义模式 = 'NO'
                                    self.获取列表里面的所有元素_临时缓存当前代码块 = _sc_join(self.获取列表里面的所有元素_临时缓存当前代码块, _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))
                                else:
                                    self.词法分析器_当前是否是转义模式 = 'YES'
                                if _sc_bool(_sc_and(_sc_or(_sc_eq(arg_是否允许像扩展的那样不需要包含双引号的额外信息, ''), _sc_eq(arg_是否允许像扩展的那样不需要包含双引号的额外信息, 'no')), _sc_not(_sc_eq(_sc_letter_of(_sc_sub(self.获取列表里面的所有元素_i, 1), arg_列表), '\\')))):
                                    self.获取列表里面的所有元素_临时缓存当前代码块 = _sc_join(self.获取列表里面的所有元素_临时缓存当前代码块, _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))
                                else:
                                    if _sc_bool(_sc_eq(self.获取列表里面的所有元素_当前是否是转义模式, 'YES')):
                                        self.获取列表里面的所有元素_临时缓存当前代码块 = _sc_join(self.获取列表里面的所有元素_临时缓存当前代码块, _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))
                        else:
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
                            if _sc_bool(_sc_not(_sc_or(_sc_eq(arg_是否允许像扩展的那样不需要包含双引号的额外信息, ''), _sc_eq(arg_是否允许像扩展的那样不需要包含双引号的额外信息, 'no')))):
                                self.获取列表里面的所有元素_临时缓存当前代码块 = ''
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
                                if _sc_bool(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), '\\')):
                                    if _sc_bool(_sc_not(_sc_or(_sc_eq(arg_是否允许像扩展的那样不需要包含双引号的额外信息, ''), _sc_eq(arg_是否允许像扩展的那样不需要包含双引号的额外信息, 'no')))):
                                        self.对字符串进行转义处理_i = _sc_add(self.对字符串进行转义处理_i, 1)
                                        self.获取列表里面的所有元素_临时缓存当前代码块 = _sc_join(self.获取列表里面的所有元素_临时缓存当前代码块, _sc_letter_of(self.获取列表里面的所有元素_i, arg_列表))
                                else:
                                    if _sc_bool(_sc_or(_sc_and(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), "'"), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-0')), _sc_and(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), '"'), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-1')))):
                                        if _sc_bool(_sc_and(_sc_or(_sc_and(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), "'"), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-0')), _sc_and(_sc_eq(_sc_letter_of(self.获取列表里面的所有元素_i, arg_列表), '"'), _sc_eq(self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_, 'NO-1'))), _sc_not(_sc_eq(_sc_letter_of(_sc_sub(self.获取列表里面的所有元素_i, 1), arg_列表), '\\')))):
                                            self.获取列表里面的所有元素_列表参数当前是否为可直接分段参数_ = 'YES'
                                            if _sc_bool(_sc_not(_sc_or(_sc_eq(arg_是否允许像扩展的那样不需要包含双引号的额外信息, ''), _sc_eq(arg_是否允许像扩展的那样不需要包含双引号的额外信息, 'no')))):
                                                self.获取列表里面的所有元素_辅助变量2 = '0'
                                                self.获取列表里面的所有元素_辅助变量 = ''
                                                while not _sc_bool(_sc_eq(self.获取列表里面的所有元素_辅助变量2, _sc_sub(_sc_length(self.获取列表里面的所有元素_临时缓存当前代码块), 1))):
                                                    self.获取列表里面的所有元素_辅助变量2 = _sc_add(self.获取列表里面的所有元素_辅助变量2, 1)
                                                    self.获取列表里面的所有元素_辅助变量 = _sc_join(self.获取列表里面的所有元素_辅助变量, _sc_letter_of(self.获取列表里面的所有元素_辅助变量2, self.获取列表里面的所有元素_临时缓存当前代码块))
                                                    self._yield_frame()
                                                self.获取列表里面的所有元素_临时缓存当前代码块 = self.获取列表里面的所有元素_辅助变量
                                        else:
                                            pass
                    self.获取列表里面的所有元素_i = _sc_add(self.获取列表里面的所有元素_i, 1)
                    self._yield_frame()
                self.获取列表里面的所有元素_返回值.append(self.获取列表里面的所有元素_临时缓存当前代码块)
            self._yield_frame()


    def when_green_flag(self):
        """当绿旗被点击时"""
        self.词法分析器()


    def run(self):
        """向运行时注册事件脚本"""
        self._register('green_flag', self.when_green_flag)

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
    sac_轻量级编程语言 = SAC_轻量级编程语言()
    runtime.add_sprite(sac_轻量级编程语言)

    try:
        runtime.start(max_frames=args.frames, max_seconds=args.seconds)
    except KeyboardInterrupt:
        pass
    finally:
        runtime.shutdown()


if __name__ == "__main__":
    main()