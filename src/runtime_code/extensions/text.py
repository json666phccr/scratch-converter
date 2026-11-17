# -*- coding: utf-8 -*-
"""text 艺术字"""

def _extension_text(runtime, sprite, opcode, inputs, fields):
    """TurboWarp 艺术字（Animated Text）扩展"""
    key = str(opcode).lower().replace('_', '')
    if key.endswith('animatetextinput') or key.endswith('animatetext'):
        sprite._text_animate(
            _sc_str(_ext_input(inputs, fields, 'ANIMATE', 'animate', default='rainbow')),
            _sc_str(_ext_input(inputs, fields, 'TEXT', 'text', default='')))
    elif key.endswith('settext'):
        sprite._text_set(_sc_str(_ext_input(inputs, fields, 'TEXT', 'text', default='')))
    elif key.endswith('cleartext'):
        sprite._text_clear()
    elif key.endswith('setfontinput') or key.endswith('setfont'):
        sprite._text_set_font(
            _sc_str(_ext_input(inputs, fields, 'FONT', 'font', default='Handwriting')))
    elif key.endswith('setcolor'):
        sprite._text_set_color(
            _sc_str(_ext_input(inputs, fields, 'COLOR', 'color', default='#575e75')))
    elif key.endswith('setwidthvalue'):
        sprite._text_set_width(_sc_num(_ext_input(inputs, fields, 'WIDTH', 'width', default=200)))
    elif key.endswith('setwidthinput') or key.endswith('setwidth'):
        sprite._text_set_width(
            _sc_num(_ext_input(inputs, fields, 'WIDTH', 'width', default=200)),
            _sc_str(_ext_input(inputs, fields, 'ALIGN', 'align', default='center')))
    elif key.endswith('setoutlinewidth'):
        sprite._text_set_outline_width(
            _sc_num(_ext_input(inputs, fields, 'WIDTH', 'width', default=3)))
    elif key.endswith('setoutlinecolor'):
        sprite._text_set_outline_color(
            _sc_str(_ext_input(inputs, fields, 'COLOR', 'color', default='#000000')))
    elif key.endswith('addline'):
        sprite._text_add_line(
            _sc_str(_ext_input(inputs, fields, 'TEXT', 'text', default='')))
    elif key.endswith('getlinesv2'):
        with_wrap = _sc_str(_ext_input(inputs, fields, 'WITH_WORD_WRAP', default='with word wrap'))
        return sprite._text_count_lines('without' not in with_wrap.lower())
    elif key.endswith('getlines'):
        return sprite._text_count_lines(False)
    elif key.endswith('setalignment'):
        sprite._text_set_align(
            _sc_str(_ext_input(inputs, fields, 'ALIGN', 'align', default='center')))
    elif key.endswith('resetwidth'):
        sprite._text_set_width(runtime.stage_width)
    elif key.endswith('resetanimateduration'):
        sprite._text_reset_duration(
            _sc_str(_ext_input(inputs, fields, 'ANIMATE', 'animate', default='rainbow')))
    elif key.endswith('getanimateduration'):
        return sprite._text_animation_duration(
            _sc_str(_ext_input(inputs, fields, 'ANIMATE', 'animate', default='rainbow')))
    elif key.endswith('setanimateduration'):
        sprite._text_set_duration(
            _sc_str(_ext_input(inputs, fields, 'ANIMATE', 'animate', default='rainbow')),
            _sc_num(_ext_input(inputs, fields, 'NUM', 'num', default=3)))
    elif key.endswith('animateuntildone'):
        animation = _sc_str(
            _ext_input(inputs, fields, 'ANIMATE', 'animate', default='rainbow'))
        duration = sprite._text_start_animation(animation)
        if duration > 0:
            sprite.wait(duration)
    elif key.endswith('startanimate'):
        sprite._text_start_animation(
            _sc_str(_ext_input(inputs, fields, 'ANIMATE', 'animate', default='rainbow')))
    elif key.endswith('isanimating'):
        return sprite._text_is_animating()
    elif key.endswith('setshakeintensity'):
        sprite._text_ensure()['shake_intensity'] = _sc_num(
            _ext_input(inputs, fields, 'NUM', 'num', default=100))
    elif key.endswith('resettypedelay'):
        sprite._text_ensure()['type_delay'] = 1.0 / 15.0
    elif key.endswith('gettypedelay'):
        return sprite._text_ensure().get('type_delay', 1.0 / 15.0)
    elif key.endswith('settypedelay'):
        sprite._text_ensure()['type_delay'] = _sc_num(
            _ext_input(inputs, fields, 'NUM', 'num', default=0.1))
    elif key.endswith('textactive'):
        return sprite._text_active()
    elif key.endswith('getdisplayedtext'):
        return sprite._text_displayed()
    elif key.endswith('gettextattribute'):
        return sprite._text_attribute(
            _sc_str(_ext_input(inputs, fields, 'ATTRIBUTE', 'attribute', default='font')))
    return 0
