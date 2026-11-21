# -*- coding: utf-8 -*-
"""运行时底层辅助函数模板（运行时原样写入生成脚本）"""

HELPERS = r'''
_SCRATCH_LIST_LIMIT = 200000
_RUNTIME_VERSION = '0.13.9'


class _FairLock:
    """FIFO公平锁：避免某个脚本一直抢到执行权导致其他脚本饿死"""

    def __init__(self):
        self._lock = threading.Lock()
        self._owner = None
        # 按脚本注册顺序排队，既公平又保证同一帧内的执行顺序稳定
        self._waiters = []
        self._wait_seq = 0
        # 每个线程复用一个Event，避免每帧大量创建/销毁对象
        self._local = threading.local()

    def acquire(self, order=0):
        waiter = getattr(self._local, 'event', None)
        if waiter is None:
            waiter = threading.Event()
            self._local.event = waiter
        with self._lock:
            if self._owner is None:
                self._owner = threading.get_ident()
                return True
            waiter.clear()
            self._wait_seq += 1
            heapq.heappush(self._waiters,
                           (order, self._wait_seq, waiter))
        waiter.wait()
        with self._lock:
            self._owner = threading.get_ident()
        return True

    def release(self):
        with self._lock:
            if self._waiters:
                # 直接把所有权移交给序最小的脚本，避免新线程插队
                _, _, waiter = heapq.heappop(self._waiters)
                waiter.set()
            else:
                self._owner = None

    def locked(self):
        with self._lock:
            return self._owner is not None


class _ScriptThread:
    """轻量脚本线程：start()不等待线程真正启动

    threading.Thread.start() 会阻塞到新线程执行 bootstrap，
    大量克隆同时启动时容易互相拖慢；这里直接用 _thread 接口。
    """

    _counter = 0

    def __init__(self, target):
        self._target = target
        self._alive = False
        _ScriptThread._counter += 1
        self.name = "runner-%d" % _ScriptThread._counter
        self.ident = None
        self._scratch_context = None

    def start(self):
        self._alive = True
        try:
            _thread.start_new_thread(self._bootstrap, ())
        except Exception:
            self._alive = False
            raise

    def _bootstrap(self):
        try:
            self._target()
        finally:
            self._alive = False

    def is_alive(self):
        return self._alive

    def join(self, timeout=None):
        if timeout is None:
            while self._alive:
                time.sleep(0.001)
            return
        deadline = time.time() + timeout
        while self._alive and time.time() < deadline:
            time.sleep(0.001)


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
    text = re.sub(r'[^\w\u4e00-\u9fff]+', '_', _sc_str(name))
    if not text.strip('_'):
        import hashlib
        digest = hashlib.md5(_sc_str(name).encode('utf-8')).hexdigest()[:6]
        text = f"{prefix}_unnamed_{digest}"
    if text[0].isdigit():
        text = prefix + text
    # 与 ir.sanitize_name 保持一致：双下划线开头会被类作用域改名
    if text.startswith('__'):
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


def _svg_parse_attrs(text):
    """一次扫描解析标签属性，避免对超大的 base64 属性反复 search"""
    return dict(re.findall(r'([\w:-]+)\s*=\s*"([^"]*)"', text or ''))


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
    """解析SVG颜色，返回 (r, g, b, a)

    支持 #rgb/#rgba/#rrggbb/#rrggbbaa、rgb()/rgba()、transparent、
    常见颜色名与 Scratch 的整数颜色。
    """
    if value is None or value == '' or value == 'none':
        return None
    text = _sc_str(value).strip().lower()
    if text == 'transparent':
        return (0, 0, 0, 0)
    if text.startswith('#'):
        digits = text[1:]
        try:
            if len(digits) == 3:
                return tuple(int(ch * 2, 16) for ch in digits) + (255,)
            if len(digits) == 4:
                return tuple(int(ch * 2, 16) for ch in digits)
            if len(digits) == 6:
                return (int(digits[0:2], 16), int(digits[2:4], 16),
                        int(digits[4:6], 16), 255)
            if len(digits) == 8:
                return (int(digits[0:2], 16), int(digits[2:4], 16),
                        int(digits[4:6], 16), int(digits[6:8], 16))
        except ValueError:
            return default
        return default
    if text.startswith('rgb') or text.startswith('rgba'):
        body = text[text.find('(') + 1:text.rfind(')')] if '(' in text else ''
        parts = [part.strip() for part in body.replace('/', ',').split(',')
                 if part.strip()]
        if len(parts) >= 3:
            channels = []
            try:
                for part in parts[:3]:
                    if part.endswith('%'):
                        channels.append(int(round(float(part[:-1]) * 2.55)))
                    else:
                        channels.append(int(round(float(part))))
                alpha = 255
                if len(parts) >= 4:
                    part = parts[3]
                    value_alpha = float(part[:-1]) / 100.0 \
                        if part.endswith('%') else float(part)
                    alpha = int(round(max(0.0, min(1.0, value_alpha)) * 255))
                return (max(0, min(255, channels[0])),
                        max(0, min(255, channels[1])),
                        max(0, min(255, channels[2])),
                        max(0, min(255, alpha)))
            except ValueError:
                return default
    named = {
        'white': (255, 255, 255, 255), 'black': (0, 0, 0, 255),
        'red': (255, 0, 0, 255), 'green': (0, 128, 0, 255),
        'lime': (0, 255, 0, 255), 'blue': (0, 0, 255, 255),
        'yellow': (255, 255, 0, 255), 'orange': (255, 165, 0, 255),
        'purple': (128, 0, 128, 255), 'pink': (255, 192, 203, 255),
        'brown': (165, 42, 42, 255), 'cyan': (0, 255, 255, 255),
        'magenta': (255, 0, 255, 255), 'gray': (128, 128, 128, 255),
        'grey': (128, 128, 128, 255), 'silver': (192, 192, 192, 255),
        'navy': (0, 0, 128, 255), 'teal': (0, 128, 128, 255),
        'olive': (128, 128, 0, 255), 'maroon': (128, 0, 0, 255),
        'gold': (255, 215, 0, 255), 'violet': (238, 130, 238, 255),
        'indigo': (75, 0, 130, 255),
    }
    if text in named:
        return named[text]
    try:
        number = int(_sc_num(text))
    except (ValueError, TypeError):
        return default
    return ((number >> 16) & 255, (number >> 8) & 255, number & 255, 255)


def _svg_style_value(style_text, name, default=None):
    """从 style="fill:#fff;opacity:0.5" 中取值"""
    if not style_text:
        return default
    for part in style_text.split(';'):
        if ':' not in part:
            continue
        key, value = part.split(':', 1)
        if key.strip() == name:
            return value.strip()
    return default


def _svg_prop(attrs, name, default=None):
    """优先读元素属性，其次读 style 内联样式"""
    value = _svg_attr(attrs, name, None)
    if value is None:
        value = _svg_style_value(_svg_attr(attrs, 'style', ''), name, None)
    return default if value is None else value


def _svg_get(attrs, name, default=None):
    """元素属性读取：支持已解析的 dict 或原始标签字符串"""
    if isinstance(attrs, dict):
        value = attrs.get(name)
        if value is None:
            value = _svg_style_value(attrs.get('style'), name, None)
        return default if value is None else value
    return _svg_prop(attrs, name, default)


def _svg_opacity(value, default=1.0):
    """解析透明度：0~1 或百分比"""
    if value is None or value == '':
        return default
    text = _sc_str(value).strip()
    try:
        number = float(text[:-1]) / 100.0 if text.endswith('%') \
            else float(text)
    except (ValueError, TypeError):
        return default
    return max(0.0, min(1.0, number))


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
    def __init__(self, order=0):
        self.running = True
        self.sprite = None
        self.func = None
        self.order = order
        self.thread = None
        self.gate_index = None
        self.first_turn_done = False
        # More Events 的“广播并传数据”把数据挂在接收线程上
        self.received_data = None


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

    return decorate(func) if func is not None else decorate'''
