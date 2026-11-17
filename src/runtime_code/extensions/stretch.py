# -*- coding: utf-8 -*-
"""stretch 角色拉伸"""

def _extension_stretch(runtime, sprite, opcode, inputs, fields):
    """TurboWarp 角色拉伸（Stretch）扩展"""
    key = str(opcode).lower().replace('_', '')
    if key.endswith('setstretchx'):
        sprite._stretch_x = _sc_num(_ext_input(inputs, fields, 'X', 'x', default=100))
    elif key.endswith('setstretchy'):
        sprite._stretch_y = _sc_num(_ext_input(inputs, fields, 'Y', 'y', default=100))
    elif key.endswith('changestretchx'):
        sprite._stretch_x += _sc_num(_ext_input(inputs, fields, 'DX', 'dx', default=0))
    elif key.endswith('changestretchy'):
        sprite._stretch_y += _sc_num(_ext_input(inputs, fields, 'DY', 'dy', default=0))
    elif key.endswith('setstretch'):
        sprite._stretch_x = _sc_num(_ext_input(inputs, fields, 'X', 'x', default=100))
        sprite._stretch_y = _sc_num(_ext_input(inputs, fields, 'Y', 'y', default=100))
    elif key.endswith('changestretch'):
        sprite._stretch_x += _sc_num(_ext_input(inputs, fields, 'DX', 'dx', default=0))
        sprite._stretch_y += _sc_num(_ext_input(inputs, fields, 'DY', 'dy', default=0))
    elif key.endswith('getx'):
        return sprite._stretch_x
    elif key.endswith('gety'):
        return sprite._stretch_y
    return 0
