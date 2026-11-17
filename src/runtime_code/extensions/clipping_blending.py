# -*- coding: utf-8 -*-
"""xeltallivclipblend 裁剪与颜色混合扩展

状态保存在角色上：
- sprite._clipbox: None 或 {'x_min','y_min','x_max','y_max'}（Scratch 坐标）
- sprite._blend_mode: 'default' / 'additive' / 'mask' 等
实际渲染由 shared.py 的 _clipbox_rect / _blend_blit 完成。
"""

_CLIPBLEND_MODES = {
    'default', 'default behind',
    'additive', 'additive with alpha', 'additive legacy',
    'subtract', 'subtract with alpha', 'subtract legacy',
    'multiply', 'invert', 'invert legacy',
    'mask', 'erase',
}

_CLIPBLEND_LEGACY = {
    'additive': 'additive legacy',
    'subtract': 'subtract legacy',
    'invert': 'invert legacy',
    'default': 'default',
    'multiply': 'multiply',
}


def _clipblend_report_mode(sprite):
    """getBlend：旧版混合名归一化为菜单里的名字"""
    mode = getattr(sprite, '_blend_mode', 'default') or 'default'
    if mode == 'additive legacy':
        return 'additive'
    if mode == 'subtract legacy':
        return 'subtract'
    if mode == 'invert legacy':
        return 'invert'
    return mode


def _extension_clipping_blending(runtime, sprite, opcode, inputs, fields):
    """Clipping & Blending：角色的裁剪框与混合模式"""
    key = str(opcode).lower().replace('_', '')
    if key.endswith('setclipbox'):
        if getattr(sprite, 'is_stage', False):
            return 0
        x1 = _sc_num(_ext_input(inputs, fields, 'X1', 'x1', default=0))
        y1 = _sc_num(_ext_input(inputs, fields, 'Y1', 'y1', default=0))
        x2 = _sc_num(_ext_input(inputs, fields, 'X2', 'x2', default=100))
        y2 = _sc_num(_ext_input(inputs, fields, 'Y2', 'y2', default=100))
        sprite._clipbox = {
            'x_min': min(x1, x2), 'y_min': min(y1, y2),
            'x_max': max(x1, x2), 'y_max': max(y1, y2),
        }
        return 0
    if key.endswith('clearclipbox'):
        sprite._clipbox = None
        return 0
    if key.endswith('getclipbox'):
        box = getattr(sprite, '_clipbox', None)
        if not box:
            return ''
        prop = _sc_str(
            _ext_input(inputs, fields, 'PROP', 'prop', default='width'))
        if prop == 'width':
            return _sc_sub_safe(box['x_max'], box['x_min'])
        if prop == 'height':
            return _sc_sub_safe(box['y_max'], box['y_min'])
        if prop == 'min x':
            return box['x_min']
        if prop == 'min y':
            return box['y_min']
        if prop == 'max x':
            return box['x_max']
        if prop == 'max y':
            return box['y_max']
        return ''
    if key.endswith('setblend2'):
        mode = _sc_str(
            _ext_input(inputs, fields, 'BLENDMODE', 'blendMode', 'blendmode',
                       default='default'))
        if mode in _CLIPBLEND_MODES:
            sprite._blend_mode = mode
        return 0
    if key.endswith('setblend'):
        # 旧版积木：additive/subtract/invert 会落到 legacy 参数组合
        mode = _sc_str(
            _ext_input(inputs, fields, 'BLENDMODE', 'blendMode', 'blendmode',
                       default='default'))
        mapped = _CLIPBLEND_LEGACY.get(mode)
        if mapped is not None:
            sprite._blend_mode = mapped
        return 0
    if key.endswith('getblend'):
        return _clipblend_report_mode(sprite)
    if key.endswith('setadditiveblend'):
        state = _ext_bool(
            _ext_input(inputs, fields, 'STATE', 'state', default='on'))
        sprite._blend_mode = 'additive legacy' if state else 'default'
        return 0
    if key.endswith('getadditiveblend'):
        return getattr(sprite, '_blend_mode', 'default') in (
            'additive', 'additive legacy', 'additive with alpha')
    return 0


def _sc_sub_safe(a, b):
    """裁剪框宽高保持数值类型（整型输入不变成浮点）"""
    result = _sc_num(a) - _sc_num(b)
    if isinstance(a, int) and isinstance(b, int):
        return int(result)
    return result
