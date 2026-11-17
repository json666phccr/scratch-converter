# -*- coding: utf-8 -*-
"""jeremygamerTweening 补间"""

# ===================== Tween 补间扩展 =====================

def _tween_sine(x, direction):
    if direction == 'in':
        return 1 - math.cos((x * math.pi) / 2)
    if direction == 'out':
        return math.sin((x * math.pi) / 2)
    if direction == 'in out':
        return -(math.cos(math.pi * x) - 1) / 2
    return 0


def _tween_quad(x, direction):
    if direction == 'in':
        return x * x
    if direction == 'out':
        return 1 - (1 - x) * (1 - x)
    if direction == 'in out':
        return 2 * x * x if x < 0.5 else 1 - math.pow(-2 * x + 2, 2) / 2
    return 0


def _tween_cubic(x, direction):
    if direction == 'in':
        return x * x * x
    if direction == 'out':
        return 1 - math.pow(1 - x, 3)
    if direction == 'in out':
        return 4 * x * x * x if x < 0.5 \
            else 1 - math.pow(-2 * x + 2, 3) / 2
    return 0


def _tween_quart(x, direction):
    if direction == 'in':
        return x * x * x * x
    if direction == 'out':
        return 1 - math.pow(1 - x, 4)
    if direction == 'in out':
        return 8 * x * x * x * x if x < 0.5 \
            else 1 - math.pow(-2 * x + 2, 4) / 2
    return 0


def _tween_quint(x, direction):
    if direction == 'in':
        return x * x * x * x * x
    if direction == 'out':
        return 1 - math.pow(1 - x, 5)
    if direction == 'in out':
        return 16 * x * x * x * x * x if x < 0.5 \
            else 1 - math.pow(-2 * x + 2, 5) / 2
    return 0


def _tween_expo(x, direction):
    if direction == 'in':
        return 0 if x == 0 else math.pow(2, 10 * x - 10)
    if direction == 'out':
        return 1 if x == 1 else 1 - math.pow(2, -10 * x)
    if direction == 'in out':
        if x == 0:
            return 0
        if x == 1:
            return 1
        if x < 0.5:
            return math.pow(2, 20 * x - 10) / 2
        return (2 - math.pow(2, -20 * x + 10)) / 2
    return 0


def _tween_circ(x, direction):
    if direction == 'in':
        return 1 - math.sqrt(1 - math.pow(x, 2))
    if direction == 'out':
        return math.sqrt(1 - math.pow(x - 1, 2))
    if direction == 'in out':
        if x < 0.5:
            return (1 - math.sqrt(1 - math.pow(2 * x, 2))) / 2
        return (math.sqrt(1 - math.pow(-2 * x + 2, 2)) + 1) / 2
    return 0


def _tween_back(x, direction):
    if direction == 'in':
        return 2.70158 * x * x * x - 1.70158 * x * x
    if direction == 'out':
        return (1 + 2.70158 * math.pow(x - 1, 3)
                + 1.70158 * math.pow(x - 1, 2))
    if direction == 'in out':
        factor = 2.5949095
        if x < 0.5:
            return math.pow(2 * x, 2) * ((factor + 1) * 2 * x - factor) / 2
        return (math.pow(2 * x - 2, 2)
                * ((factor + 1) * (x * 2 - 2) + factor) + 2) / 2
    return 0


def _tween_elastic(x, direction):
    if direction == 'in':
        if x == 0:
            return 0
        if x == 1:
            return 1
        angle = 2 * math.pi / 3
        return -math.pow(2, 10 * x - 10) * math.sin((x * 10 - 10.75) * angle)
    if direction == 'out':
        if x == 0:
            return 0
        if x == 1:
            return 1
        angle = 2 * math.pi / 3
        return (math.pow(2, -10 * x) * math.sin((x * 10 - 0.75) * angle)
                + 1)
    if direction == 'in out':
        if x == 0:
            return 0
        if x == 1:
            return 1
        angle = 2 * math.pi / 4.5
        if x < 0.5:
            return (-math.pow(2, 20 * x - 10)
                    * math.sin((20 * x - 11.125) * angle)) / 2
        return (math.pow(2, -20 * x + 10)
                * math.sin((20 * x - 11.125) * angle)) / 2 + 1
    return 0


def _tween_bounce_out(x):
    if x < 1 / 2.75:
        return 7.5625 * x * x
    if x < 2 / 2.75:
        x -= 1.5 / 2.75
        return 7.5625 * x * x + 0.75
    if x < 2.5 / 2.75:
        x -= 2.25 / 2.75
        return 7.5625 * x * x + 0.9375
    x -= 2.625 / 2.75
    return 7.5625 * x * x + 0.984375


def _tween_bounce(x, direction):
    if direction == 'in':
        return 1 - _tween_bounce_out(1 - x)
    if direction == 'out':
        return _tween_bounce_out(x)
    if direction == 'in out':
        if x < 0.5:
            return (1 - _tween_bounce_out(1 - 2 * x)) / 2
        return (1 + _tween_bounce_out(2 * x - 1)) / 2
    return 0


_TWEEN_EASINGS = {
    'linear': lambda x, direction: x,
    'sine': _tween_sine,
    'quad': _tween_quad,
    'cubic': _tween_cubic,
    'quart': _tween_quart,
    'quint': _tween_quint,
    'expo': _tween_expo,
    'circ': _tween_circ,
    'back': _tween_back,
    'elastic': _tween_elastic,
    'bounce': _tween_bounce,
}


def _tween_ease(mode, direction, progress):
    easing = _TWEEN_EASINGS.get(_sc_str(mode).lower())
    if easing is None:
        easing = _TWEEN_EASINGS['linear']
    try:
        return easing(progress, _sc_str(direction).lower())
    except (ValueError, OverflowError):
        return progress


def _tween_interpolate(progress, start, end):
    return progress * (end - start) + start


def _tween_progress(sprite, seconds):
    """按帧产出0..1的进度；脚本停止或运行时结束时提前结束"""
    seconds = max(0.0, _sc_num(seconds))
    context = getattr(sprite._local, 'context', None)

    def alive():
        if context is not None and not context.running:
            return False
        runtime = getattr(sprite, '_runtime', None)
        return runtime is None or runtime.running

    if seconds <= 0:
        yield 1.0
        return
    started = time.time()
    while alive():
        progress = min(1.0, (time.time() - started) / seconds)
        yield progress
        if progress >= 1.0:
            return
        sprite._yield_frame()
        runtime = getattr(sprite, '_runtime', None)
        warp = getattr(sprite._local, 'warp_depth', 0) > 0 \
            or (runtime is not None and getattr(runtime, 'turbo', False))
        if warp:
            time.sleep(0.002)


def _extension_tween(runtime, sprite, opcode, inputs, fields):
    """jeremygamerTweening：缓动/补间"""
    key = str(opcode).lower().replace('_', '')
    mode = _ext_input(inputs, fields, 'MODE', 'mode', default='linear')
    direction = _ext_input(inputs, fields, 'DIRECTION', 'direction',
                           default='in')

    if key.endswith('tweenvalue'):
        start = _sc_num(_ext_input(inputs, fields, 'START', 'start', default=0))
        end = _sc_num(_ext_input(inputs, fields, 'END', 'end', default=100))
        amount = _sc_num(_ext_input(inputs, fields, 'AMOUNT', 'amount',
                                    default=50)) / 100.0
        return _tween_interpolate(_tween_ease(mode, direction, amount),
                                  start, end)

    seconds = _sc_num(_ext_input(inputs, fields, 'SEC', 'sec', default=1))

    if key.endswith('tweenvariable'):
        name = _ext_input(inputs, fields, 'VAR', 'var', default='')
        end = _sc_num(_ext_input(inputs, fields, 'VALUE', 'value', default=100))
        start = _sc_num(_ext_var_get(sprite, name, 0))
        for progress in _tween_progress(sprite, seconds):
            value = _tween_interpolate(
                _tween_ease(mode, direction, progress), start, end)
            _ext_var_set(sprite, name, value)
        return 0

    if key.endswith('tweenxy'):
        target_x = _sc_num(_ext_input(inputs, fields, 'X', 'x', default=100))
        target_y = _sc_num(_ext_input(inputs, fields, 'Y', 'y', default=100))
        start_x, start_y = _sc_num(sprite.x), _sc_num(sprite.y)
        for progress in _tween_progress(sprite, seconds):
            factor = _tween_ease(mode, direction, progress)
            sprite.goto_xy(_tween_interpolate(factor, start_x, target_x),
                           _tween_interpolate(factor, start_y, target_y))
        return 0

    if key.endswith('tweenproperty'):
        prop = _sc_str(_ext_input(inputs, fields, 'PROPERTY', 'property',
                                  default='x position'))
        end = _sc_num(_ext_input(inputs, fields, 'VALUE', 'value', default=100))
        if prop == 'x position':
            start = _sc_num(sprite.x)
            getter_setter = lambda value: sprite.goto_xy(value, sprite.y)
        elif prop == 'y position':
            start = _sc_num(sprite.y)
            getter_setter = lambda value: sprite.goto_xy(sprite.x, value)
        elif prop == 'direction':
            start = _sc_num(sprite.direction)
            getter_setter = lambda value: sprite.point_in_direction(value)
        elif prop == 'size':
            start = _sc_num(sprite.size)
            getter_setter = lambda value: sprite.set_size(value)
        else:
            return 0
        for progress in _tween_progress(sprite, seconds):
            getter_setter(_tween_interpolate(
                _tween_ease(mode, direction, progress), start, end))
        return 0

    return 0
