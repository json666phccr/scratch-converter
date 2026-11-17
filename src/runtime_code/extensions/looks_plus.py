# -*- coding: utf-8 -*-
"""lmsLooksPlus 外观+"""

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
        # 与当前窗口渲染倍率保持一致，避免替换造型后尺寸变小
        scale = max(1.0, getattr(runtime, 'render_scale', 1.0))
        png = cairosvg.svg2png(bytestring=text.encode('utf-8'), scale=scale)
        image = pygame.image.load(io.BytesIO(png))
        runtime.costume_cache[key] = image.convert_alpha()
        runtime.costume_image_scales[key] = scale
        runtime.costume_cache_scales[(key, scale)] = runtime.costume_cache[key]
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
            if image is None:
                return 0
            scale = runtime.get_sprite_image_scale(
                costume.get('md5ext') or costume.get('name'))
            return int(round(image.get_width() / max(1e-6, scale)))
        if attribute == 'height':
            image = _ext_costume_image(runtime, sprite, index)
            if image is None:
                return 0
            scale = runtime.get_sprite_image_scale(
                costume.get('md5ext') or costume.get('name'))
            return int(round(image.get_height() / max(1e-6, scale)))
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
