# -*- coding: utf-8 -*-
"""扩展积木处理器模板（pen / runtimeoptions / music / text2speech / stretch / text / JSON）"""

EXTENSIONS = r'''
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


def _extension_text2speech(runtime, sprite, opcode, inputs, fields):
    """text2speech扩展：朗读并等待、切换嗓音/语言"""
    key = str(opcode).lower().replace('_', '')
    if 'speak' in key:
        text = _sc_str(_ext_input(inputs, fields, 'WORDS', 'TEXT', 'words', 'text',
                                  default=''))
        runtime.speak(text, sprite)
    elif 'setvoice' in key:
        runtime.tts_voice = _sc_str(
            _ext_input(inputs, fields, 'VOICE', 'voice', default='alto')).lower()
    elif 'setlanguage' in key:
        runtime.tts_language = _sc_str(
            _ext_input(inputs, fields, 'LANGUAGE', 'language', default='English'))
    return 0


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


def _json_reject_constant(value):
    raise ValueError('invalid JSON constant')


def _json_load(text):
    try:
        return True, json.loads(_sc_str(text), parse_constant=_json_reject_constant)
    except Exception:
        return False, None


def _json_norm(value):
    if isinstance(value, float) and math.isfinite(value) and value == int(value):
        return int(value)
    if isinstance(value, list):
        return [_json_norm(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_norm(item) for key, item in value.items()}
    return value


def _json_dumps(value):
    try:
        return json.dumps(_json_norm(value), ensure_ascii=False,
                          separators=(',', ':'), allow_nan=False)
    except Exception:
        return ''


def _json_bracketed(value):
    if not isinstance(value, str):
        return False
    return ((value.startswith('[') and value.endswith(']'))
            or (value.startswith('{') and value.endswith('}')))


def _json_valid(value):
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    if not _json_bracketed(stripped):
        return False
    ok, _parsed = _json_load(stripped)
    return ok


def _json_valid_return(value):
    if not isinstance(value, str) or not _json_bracketed(value):
        return value
    ok, parsed = _json_load(value)
    if not ok:
        return value
    return '' if parsed is None else parsed


def _json_fix(value):
    if isinstance(value, float):
        if math.isnan(value):
            return 'NaN'
        if math.isinf(value):
            return 'Infinity' if value > 0 else '-Infinity'
    if value is None:
        return ''
    return value


def _json_strict_eq(first, second):
    if isinstance(first, bool) or isinstance(second, bool):
        return isinstance(first, bool) and isinstance(second, bool) and first == second
    if isinstance(first, (dict, list)) or isinstance(second, (dict, list)):
        return first is second
    if isinstance(first, (int, float)) and isinstance(second, (int, float)):
        return first == second
    if isinstance(first, str) and isinstance(second, str):
        return first == second
    if first is None or second is None:
        return first is None and second is None
    return False


def _json_member(container, key):
    """返回 (是否存在, 值)，兼容对象键、数组下标和数组的 length"""
    if isinstance(container, dict):
        text = _sc_str(key)
        return (text in container), container.get(text)
    if isinstance(container, list):
        text = _sc_str(key)
        if text == 'length':
            return True, len(container)
        number = _sc_num(key)
        if isinstance(number, float) and not number.is_integer():
            return False, None
        index = int(number)
        if 0 <= index < len(container):
            return True, container[index]
        return False, None
    return False, None


def _json_index(array, index):
    """Scratch 风格下标：1 是首项，-1 是末项，0 无效"""
    number = _sc_num(index)
    if isinstance(number, float) and not number.is_integer():
        return None
    index = int(number)
    if index == 0:
        return None
    if index > 0:
        index -= 1
    else:
        index += len(array)
    if index < 0 or index >= len(array):
        return None
    return index


def _json_key_text(key):
    return _sc_str(_json_fix(_json_valid_return(key)))


def _json_compare(first, second):
    return _sc_compare(first, second)


def _json_join_item(value):
    if value is None:
        return ''
    if isinstance(value, dict):
        return '[object Object]'
    if isinstance(value, list):
        return ','.join(_json_join_item(item) for item in value)
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return _sc_str(value)


def _json_spread(value):
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, list):
        return {str(index): item for index, item in enumerate(value)}
    return {}


def _json_flatten(value, depth):
    result = []
    for item in value:
        if isinstance(item, list) and depth > 0:
            result.extend(_json_flatten(item, depth - 1))
        else:
            result.append(item)
    return result


def _json_analysis(values, analysis):
    numbers = [_sc_num(item) for item in values]
    total = len(numbers)
    if analysis == 'maximum':
        if not numbers:
            return -math.inf
        best = -math.inf
        for number in numbers:
            if number > best:
                best = number
        return best
    if analysis == 'minimum':
        if not numbers:
            return math.inf
        best = math.inf
        for number in numbers:
            if number < best:
                best = number
        return best
    if analysis == 'sum':
        return math.fsum(numbers)
    if analysis == 'average':
        if not total:
            return math.nan
        return math.fsum(numbers) / total
    if analysis == 'median':
        if not total:
            return math.nan
        ordered = sorted(numbers)
        middle = total // 2
        if total % 2 == 0:
            return (ordered[middle - 1] + ordered[middle]) / 2.0
        return ordered[middle]
    if analysis == 'mode':
        counts = {}
        best, best_count = 0, 0
        for number in numbers:
            counts[number] = counts.get(number, 0) + 1
            if counts[number] > best_count:
                best, best_count = number, counts[number]
        return best
    if analysis == 'variance':
        if not total:
            return math.nan
        average = math.fsum(numbers) / total
        return math.fsum((number - average) ** 2 for number in numbers) / total
    return 0


def _extension_skyhigh_json(runtime, sprite, opcode, inputs, fields):
    """TurboWarp JSON 扩展（skyhigh173JSON）"""
    key = str(opcode).lower().replace('_', '')

    def arg(*names, default=''):
        return _ext_input(inputs, fields, *names, default=default)

    if key.endswith('jsonisvalid'):
        return _json_valid(arg('json'))

    if key.endswith('jsonerrmsg'):
        text = _sc_str(arg('json'))
        ok, _parsed = _json_load(text)
        if not ok:
            try:
                json.loads(text)
            except Exception as error:
                return str(error)
            return 'JSON must be an object or array'
        return ''

    if key.endswith('jsonis'):
        types = _sc_str(arg('types', default='Object'))
        ok, parsed = _json_load(arg('json'))
        if not ok:
            return False
        if types == 'Object':
            return isinstance(parsed, dict)
        if types == 'Array':
            return isinstance(parsed, list)
        return False

    if key.endswith('jsongetall'):
        ok, parsed = _json_load(arg('json'))
        if not ok:
            return ''
        kind = _sc_str(arg('Stype', default='keys'))
        if isinstance(parsed, list):
            keys = [str(index) for index in range(len(parsed))]
            values = list(parsed)
        elif isinstance(parsed, dict):
            keys = list(parsed.keys())
            values = list(parsed.values())
        else:
            return ''
        if kind == 'keys':
            return _json_dumps(keys)
        if kind == 'values':
            return _json_dumps([_json_fix(item) for item in values])
        if kind == 'datas':
            return _json_dumps([[_json_fix(key_item), _json_fix(value)]
                                for key_item, value in zip(keys, values)])
        return ''

    if key.endswith('jsonnew'):
        kind = _sc_str(arg('json', default='Object'))
        if kind == 'Object':
            return '{}'
        if kind == 'Array':
            return '[]'
        return ''

    if key.endswith('jsonhaskey'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, (dict, list)):
            return False
        text = _json_key_text(arg('key'))
        if isinstance(parsed, list) and text == 'length':
            return False
        found, _value = _json_member(parsed, text)
        return found

    if key.endswith('jsonhasvalue'):
        ok, parsed = _json_load(arg('json'))
        if not ok:
            return False
        wanted = _json_valid_return(arg('value'))
        if isinstance(parsed, list):
            return any(_json_strict_eq(item, wanted) for item in parsed)
        if isinstance(parsed, str):
            return _sc_str(wanted) in parsed
        return False

    if key.endswith('jsonequal'):
        ok1, first = _json_load(arg('json1'))
        ok2, second = _json_load(arg('json2'))
        if not ok1 or not ok2:
            return False
        left = _json_spread(first)
        right = _json_spread(second)
        same = len(left) == len(right) and all(
            _json_strict_eq(value, right.get(name))
            for name, value in left.items())
        operator = _sc_str(arg('equal', default='='))
        if operator == '=':
            return same
        if operator == '≠':
            return not same
        return False

    if key.endswith('jsonminify'):
        ok, parsed = _json_load(arg('json'))
        return _json_dumps(parsed) if ok else ''

    if key.endswith('jsonflip'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, dict):
            return ''
        result = {}
        for name, value in parsed.items():
            targets = value if isinstance(value, list) else [value]
            for target in targets:
                if isinstance(target, (dict, list)) or target is None:
                    continue
                target = _sc_str(target)
                if target in result:
                    if isinstance(result[target], list):
                        result[target].append(name)
                    else:
                        result[target] = [result[target], name]
                else:
                    result[target] = name
        return _json_dumps(result)

    if key.endswith('jsongetpath'):
        ok, path = _json_load(arg('path'))
        if not ok or not isinstance(path, list):
            return ''
        ok, parsed = _json_load(arg('json'))
        if not ok:
            return ''
        current = parsed
        for step in path:
            if isinstance(current, list):
                index = _json_index(current, step)
                if index is None:
                    return ''
                current = current[index]
            elif isinstance(current, dict):
                name = _sc_str(step)
                if name not in current:
                    return ''
                current = current[name]
            else:
                return ''
        if current is None:
            return ''
        if isinstance(current, (dict, list)):
            return _json_dumps(current)
        return _json_fix(current)

    if key.endswith('jsonsetpath'):
        ok, path = _json_load(arg('path'))
        if not ok or not isinstance(path, list) or not path:
            return ''
        ok, parsed = _json_load(arg('json'))
        if not ok:
            return ''
        data = _json_fix(_json_valid_return(arg('data')))
        current = parsed
        for position, step in enumerate(path):
            last = position == len(path) - 1
            if isinstance(current, list):
                index = _json_index(current, step)
                if index is None:
                    return ''
                if last:
                    current[index] = data
                else:
                    current = current[index]
            elif isinstance(current, dict):
                name = _sc_str(step)
                if last:
                    current[name] = data
                elif name in current:
                    current = current[name]
                else:
                    return ''
            else:
                return ''
        return _json_dumps(parsed)

    if key.endswith('jsonjlength') or key.endswith('jsonlength'):
        ok, parsed = _json_load(arg('json'))
        if not ok or parsed is None:
            return ' '
        if isinstance(parsed, (dict, list, str)):
            return len(parsed)
        return 0

    if key.endswith('jsonget'):
        ok, parsed = _json_load(arg('json'))
        if not ok:
            return ''
        found, value = _json_member(parsed, arg('item'))
        if not found:
            return ''
        value = _json_fix(value)
        return _json_dumps(value) if isinstance(value, (dict, list)) else value

    if key.endswith('jsonset'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, (dict, list)):
            return ''
        value = _json_fix(_json_valid_return(arg('value')))
        item = arg('item')
        if isinstance(parsed, list):
            number = _sc_num(item)
            if isinstance(number, float) and not number.is_integer():
                return _json_dumps(parsed)
            index = int(number)
            if index < 0:
                return _json_dumps(parsed)
            if index >= len(parsed):
                parsed.extend([None] * (index + 1 - len(parsed)))
            parsed[index] = value
        else:
            parsed[_sc_str(item)] = value
        return _json_dumps(parsed)

    if key.endswith('jsondelete'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, (dict, list)):
            return ''
        item = arg('item')
        if isinstance(parsed, list):
            number = _sc_num(item)
            if isinstance(number, float) and not number.is_integer():
                return _json_dumps(parsed)
            index = int(number)
            if 0 <= index < len(parsed):
                parsed[index] = None
        else:
            parsed.pop(_sc_str(item), None)
        return _json_dumps(parsed)

    if key.endswith('jsonarrayget'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, list):
            return ''
        index = _json_index(parsed, arg('item'))
        if index is None:
            return ''
        value = _json_fix(parsed[index])
        return _json_dumps(value) if isinstance(value, (dict, list)) else value

    if key.endswith('jsonarrayitemh'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, list):
            return ''
        wanted = _json_fix(_json_valid_return(arg('item')))
        for index, value in enumerate(parsed):
            if _json_strict_eq(value, wanted):
                return index + 1
        return 0

    if key.endswith('jsonarrayfromto'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, list):
            return ''
        start = int(_sc_num(arg('item'))) - 1
        end = int(_sc_num(arg('item2')))
        if start < 0:
            start = max(0, len(parsed) + start)
        if end < 0:
            end = max(0, len(parsed) + end)
        return _json_dumps(parsed[start:end])

    if key.endswith('jsonarrayfrom'):
        return _json_dumps(list(_sc_str(arg('json'))))

    if key.endswith('jsonarrayconcat'):
        ok1, first = _json_load(arg('json'))
        ok2, second = _json_load(arg('json2'))
        if not ok1 or not ok2:
            return ''
        if isinstance(first, list):
            if isinstance(second, list):
                return _json_dumps(first + second)
            return _json_dumps(first + [second])
        if isinstance(first, str) and isinstance(second, str):
            return first + second
        return ''

    if key.endswith('jsonarraypush'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, list):
            return ''
        parsed.append(_json_fix(_json_valid_return(arg('item'))))
        return _json_dumps(parsed)

    if key.endswith('jsonarrayinsert'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, list):
            return ''
        index = int(_sc_num(arg('pos'))) - 1
        if index < 0:
            index = max(0, len(parsed) + index)
        if index > len(parsed):
            index = len(parsed)
        parsed.insert(index, _json_fix(_json_valid_return(arg('item'))))
        return _json_dumps(parsed)

    if key.endswith('jsonarraysetlen'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, list):
            return ''
        length = int(_sc_num(arg('len', default=0)))
        if length < 0:
            return ''
        if length > len(parsed):
            parsed.extend([None] * (length - len(parsed)))
        else:
            del parsed[length:]
        return _json_dumps(parsed)

    if key.endswith('jsonarrayset'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, list):
            return ''
        index = int(_sc_num(arg('pos'))) - 1
        if index < 0:
            return _json_dumps(parsed)
        if index >= len(parsed):
            parsed.extend([None] * (index + 1 - len(parsed)))
        parsed[index] = _json_fix(_json_valid_return(arg('item')))
        return _json_dumps(parsed)

    if key.endswith('jsonarraydelete'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, list):
            return ''
        index = int(_sc_num(arg('item'))) - 1
        if index < 0:
            index = max(0, len(parsed) + index)
        if index < len(parsed):
            del parsed[index]
        return _json_dumps(parsed)

    if key.endswith('jsonarrayremoveall'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, list):
            return ''
        wanted = _json_fix(_json_valid_return(arg('item')))
        parsed[:] = [value for value in parsed
                     if not _json_strict_eq(value, wanted)]
        return _json_dumps(parsed)

    if key.endswith('jsonarrayreverse'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, list):
            return ''
        return _json_dumps(list(reversed(parsed)))

    if key.endswith('jsonarrayflat'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, list):
            return ''
        depth = _sc_num(arg('depth', default=2))
        if isinstance(depth, float) and math.isinf(depth):
            depth = 9999
        return _json_dumps(_json_flatten(parsed, int(depth)))

    if key.endswith('jsonarraycreate'):
        text = _sc_str(arg('text'))
        delimiter = _sc_str(arg('d'))
        return _json_dumps(list(text) if delimiter == '' else text.split(delimiter))

    if key.endswith('jsonarrayjoin'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, list):
            return ''
        return _sc_str(arg('d')).join(_json_join_item(item) for item in parsed)

    if key.endswith('jsonarrayfilter'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, list):
            return ''
        name = _sc_str(arg('key'))
        result = []
        for item in parsed:
            found, value = _json_member(item, name)
            result.append(_json_fix(value) if found else None)
        return _json_dumps(result)

    if key.endswith('jsonarraytextfilter'):
        ok, parsed = _json_load(arg('list'))
        if not ok:
            return ''
        option = _sc_str(arg('options', default='includes'))
        text = _sc_str(arg('text'))
        output = _sc_str(arg('type', default='Object'))
        if isinstance(parsed, list):
            entries = [(str(index), value) for index, value in enumerate(parsed)]
            was_array = True
        elif isinstance(parsed, dict):
            entries = list(parsed.items())
            was_array = False
        else:
            return ''
        kept = []
        for name, value in entries:
            if not isinstance(value, str):
                continue
            if option == 'starts with':
                matched = value.startswith(text)
            elif option == 'ends with':
                matched = value.endswith(text)
            else:
                matched = text in value
            if matched:
                kept.append((name, value))
        if output == 'Array':
            return _json_dumps([value for _name, value in kept])
        if was_array and output == 'Object':
            return _json_dumps({str(int(name) + 1): value for name, value in kept})
        return _json_dumps(dict(kept))

    if key.endswith('jsonarraysort'):
        ok, parsed = _json_load(arg('list'))
        if not ok or not isinstance(parsed, list):
            return ''
        ordered = sorted(parsed, key=functools.cmp_to_key(_json_compare))
        if _sc_str(arg('order', default='ascending')) == 'descending':
            ordered.reverse()
        return _json_dumps(ordered)

    if key.endswith('jsonmerge'):
        ok1, first = _json_load(arg('json1'))
        ok2, second = _json_load(arg('json2'))
        if not ok1 or not ok2:
            return ''
        if isinstance(first, list) and isinstance(second, list):
            return _json_dumps(first + second)
        merged = _json_spread(first)
        merged.update(_json_spread(second))
        return _json_dumps(merged)

    if key.endswith('jsonarrayanalysis'):
        ok, parsed = _json_load(arg('list'))
        if not ok or not isinstance(parsed, list):
            return 0
        return _json_analysis(parsed, _sc_str(arg('analysis', default='sum')))

    if key.endswith('jsonvmgetlist') or key.endswith('jsonvmsetlist'):
        target, name = runtime._find_list(sprite, arg('list'))
        if key.endswith('jsonvmgetlist'):
            return _json_dumps(list(target[name])) if target is not None else ''
        ok, parsed = _json_load(arg('json'))
        if target is None or not ok or not isinstance(parsed, list):
            return ''
        values = [_json_dumps(item) if isinstance(item, (dict, list))
                  else _json_fix(item) for item in parsed]
        target[name] = values
        return ''

    if key.endswith('jsonvmexportvar'):
        result = {}
        for name, value in GLOBALS.items():
            if isinstance(value, (str, int, float, bool)):
                result[name] = value
        for name, value in getattr(sprite, '__dict__', {}).items():
            if name.startswith('_') or name in runtime.JSON_BUILTIN_ATTRS:
                continue
            if isinstance(value, (str, int, float, bool)):
                result[name] = value
        return _json_dumps(result)

    if key.endswith('jsonvmimportvar'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, dict):
            return ''
        for name, value in parsed.items():
            attr = _sc_ident(name, 'var')
            if attr in GLOBALS:
                GLOBALS[attr] = value
            elif hasattr(sprite, name):
                setattr(sprite, name, value)
            elif hasattr(sprite, attr):
                setattr(sprite, attr, value)
        return ''

    return 0


# ===================== 通用扩展辅助 =====================

def _ext_target(runtime, name):
    """按扩展菜单里的角色名找目标（支持 _stage_）"""
    text = _sc_str(name)
    if text == '_stage_':
        return runtime.stage_sprite
    return runtime.find_sprite(text)


def _ext_family(runtime, sprite):
    """同一角色名下的全部目标（本体+克隆体）"""
    if sprite is None:
        return []
    if getattr(sprite, 'is_stage', False):
        return [sprite]
    return [item for item in runtime.sprites if item.name == sprite.name]


def _ext_origin(runtime, sprite):
    """返回角色本体（没有克隆标记的那个）"""
    for item in _ext_family(runtime, sprite):
        if not getattr(item, '_is_clone', False):
            return item
    return sprite


def _ext_var_attr(sprite, name):
    text = _sc_str(name)
    return getattr(type(sprite), 'VAR_ATTRS', {}).get(text) \
        or _sc_ident(text, 'var')


def _ext_var_get(sprite, name, default=''):
    if not _sc_str(name):
        return default
    attr = _ext_var_attr(sprite, name)
    if attr in getattr(type(sprite), 'GLOBAL_NAMES_SET', ()):
        return GLOBALS.get(attr, default)
    return getattr(sprite, attr, default)


def _ext_var_set(sprite, name, value):
    if not _sc_str(name):
        return
    attr = _ext_var_attr(sprite, name)
    if attr in getattr(type(sprite), 'GLOBAL_NAMES_SET', ()):
        GLOBALS[attr] = value
    else:
        setattr(sprite, attr, value)


def _ext_thing(target, prop):
    """Clones+ 的 [属性] of clone 积木"""
    if target is None:
        return ''
    prop = _sc_str(prop)
    if prop == 'x position':
        return target.x
    if prop == 'y position':
        return target.y
    if prop == 'direction':
        return target.direction
    if prop == 'costume num':
        return target.costume_number
    if prop == 'costume name':
        return target.costume_name
    if prop == 'size':
        return target.size
    if prop == 'volume':
        return target.volume
    return ''


def _ext_key_down(runtime, key):
    text = _sc_str(key).lower()
    if text in ('any', 'anything'):
        return bool(runtime.keys)
    if text == 'shift':
        return 'left shift' in runtime.keys or 'right shift' in runtime.keys
    if text == 'control':
        return 'left ctrl' in runtime.keys or 'right ctrl' in runtime.keys
    return text in runtime.keys


def _ext_stop_target(runtime, sprite, target):
    """停止指定目标的脚本；如果目标就是自己，按Scratch语义结束当前脚本"""
    if target is None:
        return
    runtime.stop_scripts_of(target)
    context = getattr(sprite._local, 'context', None)
    if context is not None and context.sprite is target:
        raise StopIteration('stop scripts')


def _ext_touching_targets(runtime, sprite, targets):
    """角色是否碰到给定目标列表中的任意一个（按像素遮罩判定）"""
    rect = runtime._sprite_rect(sprite)
    first = None
    for other in list(targets):
        if other is sprite or not other.visible:
            continue
        other_rect = runtime._sprite_rect(other)
        if not rect.colliderect(other_rect):
            continue
        if first is None:
            first = runtime._sprite_mask(sprite)
        second = runtime._sprite_mask(other)
        if first is None or second is None:
            return True
        offset = (other_rect.x - rect.x, other_rect.y - rect.y)
        if first.overlap(second, offset) is not None:
            return True
    return False


def _ext_hat_input(entry, name, default=None):
    inputs = entry.get('inputs') or {}
    for key in (name, name.upper(), name.lower()):
        if key in inputs:
            value = inputs[key]
            try:
                return value() if callable(value) else value
            except Exception:
                return default
    return default


def _ext_hat_alive(entry):
    thread = entry.get('thread')
    return thread is not None and thread.is_alive()


def _ext_frame_hat_action(runtime, sprite, entry):
    """返回 'start' / 'stop' / None，由运行时逐帧调用"""
    opcode = str(entry.get('opcode') or '').lower()
    short = opcode.split('_', 1)[-1]

    if short == 'whenclonestartswithvar':
        if not getattr(sprite, '_is_clone', False):
            return None
        name = _ext_hat_input(entry, 'INPUTA', '')
        expected = _ext_hat_input(entry, 'INPUTB', '')
        now = _sc_compare(_ext_var_get(sprite, name), expected) == 0
        previous = entry.get('state')
        entry['state'] = now
        if now and previous is not True:
            return 'start'
        return None

    if short == 'forever':
        return None if _ext_hat_alive(entry) else 'start'

    if short == 'whentruefalse':
        state = _sc_str(_ext_hat_input(entry, 'STATE', 'true')).lower() == 'true'
        condition = _sc_bool(_ext_hat_input(entry, 'CONDITION', False))
        now = condition if state else not condition
        previous = entry.get('state')
        entry['state'] = now
        if now and previous is not True:
            return 'start'
        return None

    if short == 'whiletruefalse':
        state = _sc_str(_ext_hat_input(entry, 'STATE', 'true')).lower() == 'true'
        condition = _sc_bool(_ext_hat_input(entry, 'CONDITION', False))
        now = condition if state else not condition
        if now:
            return None if _ext_hat_alive(entry) else 'start'
        return 'stop' if _ext_hat_alive(entry) else None

    if short == 'whenvaluechanged':
        current = _sc_str(_ext_hat_input(entry, 'INPUT', ''))
        previous = entry.get('state')
        # 与原扩展一致：上一值为空（假值）时只记录，不触发
        if not previous:
            entry['state'] = current
            return None
        if previous == current:
            return None
        entry['state'] = current
        return 'start'

    if short == 'everyduration':
        steps = _sc_round(_ext_hat_input(entry, 'DURATION', 3))
        if not isinstance(steps, int) or steps <= 0:
            return None
        if (runtime.frame + 1) % steps != 0:
            return None
        return None if _ext_hat_alive(entry) else 'start'

    if short == 'whenkeyaction':
        key = _ext_hat_input(entry, 'KEY_OPTION', 'space')
        action = _sc_str(_ext_hat_input(entry, 'ACTION', 'hit')).lower()
        down = _ext_key_down(runtime, key)
        now = (not down) if action == 'released' else down
        previous = entry.get('state')
        entry['state'] = now
        if now and previous is not True:
            return 'start'
        return None

    if short == 'whilekeypressed':
        down = _ext_key_down(runtime, _ext_hat_input(entry, 'KEY_OPTION', 'space'))
        if down:
            return None if _ext_hat_alive(entry) else 'start'
        return 'stop' if _ext_hat_alive(entry) else None

    return None


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


# ===================== Clones+ 克隆+ =====================

def _extension_clones_plus(runtime, sprite, opcode, inputs, fields):
    """lmsclonesplus：带变量值的克隆管理"""
    key = str(opcode).lower().replace('_', '')
    var_a = _ext_input(inputs, fields, 'INPUTA', 'inputa', 'INPUT', 'input',
                       default='')
    var_b = _ext_input(inputs, fields, 'INPUTB', 'inputb', default=1)
    var_c = _ext_input(inputs, fields, 'INPUTC', 'inputc', default='')
    value_d = _ext_input(inputs, fields, 'INPUTD', 'inputd', default=1)

    if key.endswith('whenclonestartswithvar'):
        return 0

    if key.endswith('createcloneofmyselfwithvar'):
        sprite._make_clone({var_a: var_b})
        return 0

    if key.endswith('createclonewithvar'):
        _ext_origin(runtime, sprite)._make_clone({var_a: var_b})
        return 0

    if key.endswith('touchingclonewithvar'):
        clones = [item for item in _ext_family(runtime, sprite)
                  if getattr(item, '_is_clone', False)
                  and _sc_compare(_ext_var_get(item, var_a), var_b) == 0]
        return _ext_touching_targets(runtime, sprite, clones)

    if key.endswith('touchingmainsprite'):
        if not getattr(sprite, '_is_clone', False):
            return False
        origin = _ext_origin(runtime, sprite)
        return _ext_touching_targets(runtime, sprite, [origin])

    if key.endswith('setvariableofclone'):
        for item in _ext_family(runtime, sprite):
            if not getattr(item, '_is_clone', False):
                continue
            if _sc_compare(_ext_var_get(item, var_c), value_d) == 0:
                _ext_var_set(item, var_a, var_b)
        return 0

    if key.endswith('getvariableofclone'):
        # 该积木的匹配值是 INPUTC，没有 INPUTD
        match = _ext_input(inputs, fields, 'INPUTC', 'inputc', default=1)
        for item in _ext_family(runtime, sprite):
            if not getattr(item, '_is_clone', False):
                continue
            if _sc_compare(_ext_var_get(item, var_b), match) == 0:
                return _ext_var_get(item, var_a)
        return ''

    if key.endswith('setvariableofmainsprite'):
        _ext_var_set(_ext_origin(runtime, sprite), var_a, var_b)
        return 0

    if key.endswith('getvariableofmainsprite'):
        return _ext_var_get(_ext_origin(runtime, sprite), var_a)

    if key.endswith('cloneexists'):
        for item in _ext_family(runtime, sprite):
            if getattr(item, '_is_clone', False) \
                    and _sc_compare(_ext_var_get(item, var_a), var_b) == 0:
                return True
        return False

    if key.endswith('getthingofclone'):
        match = _ext_input(inputs, fields, 'INPUTC', 'inputc', default=1)
        for item in _ext_family(runtime, sprite):
            if not getattr(item, '_is_clone', False):
                continue
            if _sc_compare(_ext_var_get(item, var_b), match) == 0:
                return _ext_thing(item, var_a)
        return ''

    if key.endswith('getthingofmainsprite'):
        return _ext_thing(_ext_origin(runtime, sprite), var_a)

    if key.endswith('stopscriptsinclone'):
        for item in _ext_family(runtime, sprite):
            if getattr(item, '_is_clone', False) \
                    and _sc_compare(_ext_var_get(item, var_a), var_b) == 0:
                _ext_stop_target(runtime, sprite, item)
        return 0

    if key.endswith('stopscriptsinmainsprite'):
        _ext_stop_target(runtime, sprite, _ext_origin(runtime, sprite))
        return 0

    if key.endswith('stopscriptsinsprite'):
        _ext_stop_target(runtime, sprite, _ext_target(runtime, var_a))
        return 0

    if key.endswith('deleteclonesinsprite'):
        target = _ext_target(runtime, var_a)
        disposed_self = False
        if target is not None:
            for item in list(_ext_family(runtime, target)):
                if getattr(item, '_is_clone', False):
                    disposed_self = disposed_self or item is sprite
                    runtime.dispose_clone(item)
        if disposed_self:
            raise StopIteration('Clone deleted')
        return 0

    if key.endswith('deleteclonewithvar'):
        disposed_self = False
        for item in list(_ext_family(runtime, sprite)):
            if getattr(item, '_is_clone', False) \
                    and _sc_compare(_ext_var_get(item, var_a), var_b) == 0:
                disposed_self = disposed_self or item is sprite
                runtime.dispose_clone(item)
        if disposed_self:
            raise StopIteration('Clone deleted')
        return 0

    if key.endswith('isclone'):
        return bool(getattr(sprite, '_is_clone', False))

    if key.endswith('spriteclonecount'):
        target = _ext_target(runtime, var_a)
        if target is None:
            return 0
        return sum(1 for item in _ext_family(runtime, target)
                   if getattr(item, '_is_clone', False))

    if key.endswith('clonecount'):
        return sum(1 for item in runtime.sprites
                   if getattr(item, '_is_clone', False))

    return 0


# ===================== Looks+ 外观+ =====================

def _ext_costume_index(sprite, value):
    count = len(getattr(sprite, 'costumes', ()) or ())
    if not count:
        return 0
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        index = int(_sc_round(value)) - 1
        return index % count
    text = _sc_str(value)
    for index, costume in enumerate(sprite.costumes):
        if costume.get('name') == text:
            return index
    number = _sc_number_or_nan(text)
    if not math.isnan(number):
        return (int(_sc_round(number)) - 1) % count
    return 0


def _ext_costume_image(runtime, sprite, index):
    costumes = getattr(sprite, 'costumes', ()) or ()
    if not costumes:
        return None
    costume = costumes[index % len(costumes)]
    return runtime.get_sprite_image(
        costume.get('md5ext') or costume.get('name'))


def _ext_costume_format(costume):
    text = _sc_str(costume.get('dataFormat') or '').lower()
    if text:
        return text
    name = _sc_str(costume.get('md5ext') or costume.get('name')).lower()
    if name.endswith('.svg'):
        return 'svg'
    if '.' in name:
        return name.rsplit('.', 1)[-1]
    return 'unknown'


def _ext_apply_costume_svg(runtime, sprite, index, text):
    """把SVG文本写回造型：有cairosvg时重新渲染，否则只保存文本"""
    costumes = getattr(sprite, 'costumes', ()) or ()
    if not costumes:
        return
    costume = costumes[index % len(costumes)]
    key = costume.get('md5ext') or costume.get('name')
    try:
        import cairosvg
        png = cairosvg.svg2png(bytestring=text.encode('utf-8'))
        image = pygame.image.load(io.BytesIO(png))
        runtime.costume_cache[key] = image.convert_alpha()
    except Exception:
        pass


def _extension_looks_plus(runtime, sprite, opcode, inputs, fields):
    """lmsLooksPlus：跨角色显示/图层/特效/造型信息"""
    key = str(opcode).lower().replace('_', '')
    target_name = _ext_input(inputs, fields, 'TARGET', 'target', default='')
    target = _ext_target(runtime, target_name)

    if key.endswith('showsprite'):
        if target is not None:
            target.visible = True
        return 0

    if key.endswith('hidesprite'):
        if target is not None:
            target.visible = False
        return 0

    if key.endswith('spritevisible'):
        return bool(target.visible) if target is not None else False

    if key.endswith('setlayerto'):
        if target is None:
            return 0
        layer = _sc_num(_ext_input(inputs, fields, 'LAYER', 'layer', default=1))
        if math.isnan(layer) or math.isinf(layer):
            return 0
        ordered = [item for item in runtime.sprites
                   if not getattr(item, 'is_stage', False)]
        if target not in ordered:
            return 0
        ordered.remove(target)
        index = max(0, min(len(ordered), int(layer) - 1))
        ordered.insert(index, target)
        stage = runtime.stage_sprite
        runtime.sprites = ([stage] if stage is not None else []) + ordered
        return 0

    if key.endswith('spritelayernumber'):
        ordered = [item for item in runtime.sprites
                   if not getattr(item, 'is_stage', False)]
        if target in ordered:
            return ordered.index(target) + 1
        return 0

    if key.endswith('effectvalue'):
        if target is None:
            return 0
        effect = _sc_str(_ext_input(inputs, fields, 'EFFECT', 'effect',
                                    default='color')).lower()
        return _sc_num(target._effects.get(effect, 0))

    if key.endswith('targetcostumenumber'):
        return len(getattr(target, 'costumes', ()) or ()) if target else 0

    if key.endswith('costumeattribute'):
        # 该积木没有 TARGET，操作的是当前角色的造型
        costume_value = _ext_input(inputs, fields, 'COSTUME', 'costume',
                                   default=1)
        index = _ext_costume_index(sprite, costume_value)
        costumes = sprite.costumes
        if not costumes:
            return 0
        costume = costumes[index]
        attribute = _sc_str(_ext_input(inputs, fields, 'ATTRIBUTE',
                                       'attribute', default='width'))
        if attribute == 'width':
            image = _ext_costume_image(runtime, sprite, index)
            return image.get_width() if image is not None else 0
        if attribute == 'height':
            image = _ext_costume_image(runtime, sprite, index)
            return image.get_height() if image is not None else 0
        if attribute == 'format':
            return _ext_costume_format(costume)
        if attribute == 'rotationCenterX':
            return _sc_num(costume.get('rotationCenterX', 0))
        if attribute == 'rotationCenterY':
            return _sc_num(costume.get('rotationCenterY', 0))
        return ''

    if key.endswith('snapshotstage'):
        return runtime.snapshot_data_uri()

    if key.endswith('replacecostumecontentnew') \
            or key.endswith('replacecostumecontent'):
        costume_value = _ext_input(inputs, fields, 'COSTUME', 'costume',
                                   default=1)
        index = _ext_costume_index(sprite, costume_value)
        content = _sc_str(_ext_input(inputs, fields, 'CONTENT', 'content',
                                     default='<svg />'))
        costumes = getattr(sprite, 'costumes', ()) or ()
        if costumes:
            costume = costumes[index % len(costumes)]
            runtime.costume_text_overrides[
                costume.get('md5ext') or costume.get('name')] = content
        _ext_apply_costume_svg(runtime, sprite, index, content)
        return 0

    if key.endswith('restorecostumecontent'):
        costume_value = _ext_input(inputs, fields, 'COSTUME', 'costume',
                                   default=1)
        index = _ext_costume_index(sprite, costume_value)
        costumes = getattr(sprite, 'costumes', ()) or ()
        if costumes:
            costume = costumes[index % len(costumes)]
            runtime.costume_text_overrides.pop(
                costume.get('md5ext') or costume.get('name'), None)
            raw = runtime.asset_bytes(costume.get('md5ext')
                                      or costume.get('name'))
            if raw is not None:
                _ext_apply_costume_svg(
                    runtime, sprite, index, raw.decode('utf-8', 'replace'))
        return 0

    if key.endswith('costumecontent'):
        if target is None:
            return ''
        costume_number = _sc_num(_ext_input(inputs, fields, 'COSTUME',
                                            'costume', default=1))
        costumes = getattr(target, 'costumes', ()) or ()
        if not costumes:
            return ''
        index = (int(_sc_round(costume_number)) - 1) % len(costumes)
        costume = costumes[index]
        content_type = _sc_str(_ext_input(inputs, fields, 'CONTENT',
                                          'content', default='content'))
        override = runtime.costume_text_overrides.get(
            costume.get('md5ext') or costume.get('name'))
        if override is not None:
            raw = override.encode('utf-8')
        else:
            raw = runtime.asset_bytes(costume.get('md5ext')
                                      or costume.get('name'))
        if raw is None:
            return ''
        if content_type == 'dataURI':
            mime = 'image/svg+xml' \
                if _ext_costume_format(costume) == 'svg' else 'image/png'
            return 'data:%s;base64,%s' % (
                mime, base64.b64encode(raw).decode('ascii'))
        return raw.decode('utf-8', 'replace')

    if key.endswith('replacecolors'):
        svg = _sc_str(_ext_input(inputs, fields, 'SVG', 'svg',
                                 default='<svg />'))
        first = _sc_str(_ext_input(inputs, fields, 'COLOR1', 'color1',
                                   default='#FCB1E3'))
        second = _sc_str(_ext_input(inputs, fields, 'COLOR2', 'color2',
                                    default='#8ECAFF'))
        try:
            return re.sub(re.escape(first), second, svg, flags=re.IGNORECASE)
        except re.error:
            return svg

    if key.endswith('colorhex'):
        return _ext_input(inputs, fields, 'COLOR', 'color',
                          default='#FFD983')

    return 0


# ===================== More Events 更多事件 =====================

def _ext_received_data(sprite):
    context = getattr(sprite._local, 'context', None)
    data = getattr(context, 'received_data', None) if context else None
    return data if data else ''


def _ext_wait_threads(sprite, runtime, threads):
    context = getattr(sprite._local, 'context', None)
    while any(thread.is_alive() for thread in threads):
        if not runtime.running or (context is not None and not context.running):
            return
        sprite._yield_frame()


def _extension_more_events(runtime, sprite, opcode, inputs, fields):
    """lmsMoreEvents：广播传数据等命令积木"""
    key = str(opcode).lower().replace('_', '')

    if key.endswith('receiveddata'):
        return _ext_received_data(sprite)

    message = _sc_str(_ext_input(inputs, fields, 'BROADCAST_OPTION',
                                 'broadcast_option', default=''))
    data = _ext_input(inputs, fields, 'DATA', 'data', default=None)
    target_name = _ext_input(inputs, fields, 'TARGET', 'target', default='')

    if key.endswith('broadcastdatatotargetandwait') \
            or key.endswith('broadcastdatatotarget'):
        if not message:
            return 0
        target = _ext_target(runtime, target_name)
        if target is None:
            return 0
        targets = _ext_family(runtime, target)
        threads = runtime.broadcast_to(message, targets, data)
        if key.endswith('andwait'):
            _ext_wait_threads(sprite, runtime, threads)
        return 0

    if key.endswith('broadcasttotargetandwait') \
            or key.endswith('broadcasttotarget'):
        if not message:
            return 0
        target = _ext_target(runtime, target_name)
        if target is None:
            return 0
        threads = runtime.broadcast_to(
            message, _ext_family(runtime, target), data)
        if key.endswith('andwait'):
            _ext_wait_threads(sprite, runtime, threads)
        return 0

    if key.endswith('broadcastdataandwait') or key.endswith('broadcastdata'):
        if not message:
            return 0
        threads = runtime.broadcast(message, data)
        if key.endswith('andwait'):
            _ext_wait_threads(sprite, runtime, threads)
        return 0

    return 0


# ===================== Temporary Variables 临时变量 =====================

def _ext_thread_vars(sprite):
    store = getattr(sprite._local, 'ext_thread_vars', None)
    if store is None:
        store = {}
        sprite._local.ext_thread_vars = store
    return store


def _extension_temp_vars(runtime, sprite, opcode, inputs, fields):
    """lmsTempVars2 / lmstempvars：线程变量与运行时变量"""
    key = str(opcode).lower().replace('_', '')
    name = _ext_input(inputs, fields, 'VAR', 'var', 'INPUT', 'input',
                      'INPUTA', 'inputa', default='')

    if key.endswith('setthreadvariable'):
        _ext_thread_vars(sprite)[_sc_str(name)] = \
            _ext_input(inputs, fields, 'STRING', 'string', default=0)
        return 0
    if key.endswith('changethreadvariable'):
        store = _ext_thread_vars(sprite)
        text = _sc_str(name)
        previous = _sc_num(store.get(text, 0))
        store[text] = previous + _sc_num(
            _ext_input(inputs, fields, 'NUM', 'num', default=1))
        return 0
    if key.endswith('getthreadvariable'):
        return _ext_thread_vars(sprite).get(_sc_str(name), '')
    if key.endswith('threadvariableexists'):
        return _sc_str(name) in _ext_thread_vars(sprite)
    if key.endswith('listthreadvariables'):
        return ','.join(_ext_thread_vars(sprite).keys())
    if key.endswith('foreachthreadvariable'):
        return 0

    if key.endswith('setruntimevariable'):
        runtime.ext_runtime_vars[_sc_str(name)] = \
            _ext_input(inputs, fields, 'STRING', 'string', default=0)
        return 0
    if key.endswith('changeruntimevariable'):
        text = _sc_str(name)
        previous = _sc_num(runtime.ext_runtime_vars.get(text, 0))
        runtime.ext_runtime_vars[text] = previous + _sc_num(
            _ext_input(inputs, fields, 'NUM', 'num', default=1))
        return 0
    if key.endswith('getruntimevariable'):
        return runtime.ext_runtime_vars.get(_sc_str(name), '')
    if key.endswith('runtimevariableexists'):
        return _sc_str(name) in runtime.ext_runtime_vars
    if key.endswith('deleteruntimevariable'):
        runtime.ext_runtime_vars.pop(_sc_str(name), None)
        return 0
    if key.endswith('deleteallruntimevariables'):
        runtime.ext_runtime_vars = {}
        return 0
    if key.endswith('listruntimevariables'):
        return ','.join(runtime.ext_runtime_vars.keys())

    # 旧版临时变量扩展：模块级字典，直到显式删除才清空
    if key.endswith('setvariableto'):
        runtime.ext_legacy_vars[_sc_str(name)] = \
            _ext_input(inputs, fields, 'INPUTB', 'inputb', default=0)
        return 0
    if key.endswith('changevariableby'):
        text = _sc_str(name)
        previous = _sc_num(runtime.ext_legacy_vars.get(text, 0))
        runtime.ext_legacy_vars[text] = previous + _sc_num(
            _ext_input(inputs, fields, 'INPUTB', 'inputb', default=1))
        return 0
    if key.endswith('getvariable'):
        return runtime.ext_legacy_vars.get(_sc_str(name), '')
    if key.endswith('deletevariable'):
        runtime.ext_legacy_vars.pop(_sc_str(name), None)
        return 0
    if key.endswith('deleteallvariables'):
        runtime.ext_legacy_vars = {}
        return 0
    if key.endswith('listvariables'):
        return ','.join(runtime.ext_legacy_vars.keys())

    return 0'''
