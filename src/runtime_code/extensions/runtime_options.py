# -*- coding: utf-8 -*-
"""runtimeoptions 运行时选项"""

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
