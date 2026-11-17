# -*- coding: utf-8 -*-
"""扩展共享辅助函数"""

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


# ===================== Clipping & Blending 渲染辅助 =====================

def _clipbox_rect(runtime, clipbox):
    """把 Scratch 坐标的裁剪框换算成舞台像素矩形"""
    if not clipbox or runtime is None:
        return None
    scale = runtime.render_scale
    width = runtime.stage_width
    height = runtime.stage_height
    x1 = int(round((width / 2 + _sc_num(clipbox.get('x_min', 0))) * scale))
    y1 = int(round((height / 2 - _sc_num(clipbox.get('y_max', 0))) * scale))
    x2 = int(round((width / 2 + _sc_num(clipbox.get('x_max', 0))) * scale))
    y2 = int(round((height / 2 - _sc_num(clipbox.get('y_min', 0))) * scale))
    return pygame.Rect(x1, y1, max(0, x2 - x1), max(0, y2 - y1))


def _clipbox_apply(screen, runtime, sprite):
    """给屏幕设置角色的裁剪框，返回 (是否设置, 原裁剪区)"""
    box = getattr(sprite, '_clipbox', None)
    if box is None:
        return False, None
    rect = _clipbox_rect(runtime, box)
    if rect is None:
        return False, None
    previous = screen.get_clip()
    if previous is not None:
        rect = previous.clip(rect)
    screen.set_clip(rect)
    return True, previous


def _blend_blit(dest, src, rect, mode):
    """按 Clipping & Blending 的混合模式把 src 画到 dest 上"""
    mode = _sc_str(mode or 'default').strip().lower()
    if mode in ('', 'default'):
        dest.blit(src, rect)
        return
    flags = {
        'additive': pygame.BLEND_RGB_ADD,
        'additive with alpha': pygame.BLEND_RGBA_ADD,
        'additive legacy': pygame.BLEND_RGBA_ADD,
        'subtract': pygame.BLEND_RGB_SUB,
        'subtract with alpha': pygame.BLEND_RGBA_SUB,
        'subtract legacy': pygame.BLEND_RGBA_SUB,
        'multiply': pygame.BLEND_RGB_MULT,
    }.get(mode)
    if flags is not None:
        dest.blit(src, rect, special_flags=flags)
        return
    _blend_blit_numpy(dest, src, rect, mode)


def _blend_blit_numpy(dest, src, rect, mode):
    """behind/invert/mask/erase 需要逐像素运算，有 numpy 时精确实现"""
    try:
        import numpy
    except Exception:
        return
    area = dest.get_rect().clip(rect)
    if area.width <= 0 or area.height <= 0:
        return
    src_part = src.subsurface(pygame.Rect(
        area.x - rect.x, area.y - rect.y, area.width, area.height))
    try:
        # array3d/array_alpha 返回拷贝，不锁 Surface；结果用 blit_array 写回
        source_rgb = pygame.surfarray.array3d(src_part).astype(numpy.float32)
        if src_part.get_flags() & pygame.SRCALPHA:
            source_a = pygame.surfarray.array_alpha(src_part).astype(
                numpy.float32) / 255.0
        else:
            source_a = numpy.ones(source_rgb.shape[:2], dtype=numpy.float32)
        dst_part = dest.subsurface(area)
        has_alpha = bool(dest.get_flags() & pygame.SRCALPHA)
        target_view = None
        alpha_view = None
        try:
            target_view = pygame.surfarray.pixels3d(dst_part)
            target_n = target_view.astype(numpy.float32) / 255.0
            if has_alpha:
                alpha_view = pygame.surfarray.pixels_alpha(dst_part)
                alpha = alpha_view.astype(numpy.float32) / 255.0
            else:
                alpha = numpy.ones(target_n.shape[:2], dtype=numpy.float32)
            source = source_rgb / 255.0
            if mode == 'default behind':
                result = (source * source_a[..., None]
                          * (1.0 - alpha[..., None]) + target_n)
                out_alpha = source_a * (1.0 - alpha) + alpha
            elif mode == 'invert':
                result = source * (1.0 - target_n) + target_n * (1.0 - source)
                out_alpha = alpha
            elif mode == 'mask':
                result = target_n * source_a[..., None]
                out_alpha = alpha * source_a
            elif mode == 'erase':
                result = target_n * (1.0 - source_a[..., None])
                out_alpha = alpha * (1.0 - source_a)
            else:
                return
            target_view[...] = numpy.clip(
                result * 255.0, 0, 255).astype(numpy.uint8)
            if alpha_view is not None:
                alpha_view[...] = numpy.clip(
                    out_alpha * 255.0, 0, 255).astype(numpy.uint8)
        finally:
            # 必须显式删除视图解锁 Surface，否则后续 blit 会报“画面已锁定”
            if target_view is not None:
                del target_view
            if alpha_view is not None:
                del alpha_view
    except Exception:
        return


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
