# -*- coding: utf-8 -*-
"""pen 画笔扩展"""

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
        sprite._pen_cap = True
        sprite._pen_last = (float(_sc_num(sprite.x)), float(_sc_num(sprite.y)))
    elif key.endswith('penup'):
        sprite._pen_down = False
        sprite._pen_cap = True
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
