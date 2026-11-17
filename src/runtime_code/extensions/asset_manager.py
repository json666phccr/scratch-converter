# -*- coding: utf-8 -*-
"""lmsAssets 资源管理扩展（简单实现）

支持造型/声音的添加、删除、改名、排序与查询；
需要完整 Scratch VM 的积木（添加角色、打开作品、加载扩展、作品 JSON/导出）
保持空操作或返回空字符串。
"""

_ASSET_MIME = {
    'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
    'bmp': 'image/bmp', 'gif': 'image/gif', 'webp': 'image/webp',
    'svg': 'image/svg+xml',
    'wav': 'audio/wav', 'mp3': 'audio/mpeg', 'ogg': 'audio/ogg',
    'm4a': 'audio/mp4', 'flac': 'audio/flac',
}

_ASSET_MIME_TO_FORMAT = {
    'image/png': 'png', 'image/jpeg': 'jpg', 'image/jpg': 'jpg',
    'image/bmp': 'bmp', 'image/gif': 'gif', 'image/webp': 'webp',
    'image/svg+xml': 'svg',
    'audio/wav': 'wav', 'audio/x-wav': 'wav', 'audio/wave': 'wav',
    'audio/mpeg': 'mp3', 'audio/mp3': 'mp3', 'audio/ogg': 'ogg',
    'audio/mp4': 'm4a', 'audio/flac': 'flac',
}


def _asset_family(runtime, sprite):
    """同一角色的本体与克隆体（Scratch 中它们共享造型/声音列表）"""
    if getattr(sprite, 'is_stage', False):
        return [sprite]
    return [item for item in runtime.sprites if type(item) is type(sprite)]


def _asset_origin(runtime, sprite):
    for item in _asset_family(runtime, sprite):
        if not getattr(item, '_is_clone', False):
            return item
    return sprite


def _asset_target(runtime, sprite, name):
    """解析资源管理菜单里的角色名（含 myself）"""
    text = _sc_str(name)
    if text in ('_myself_', 'myself', ''):
        return _asset_origin(runtime, sprite)
    if text == '_stage_':
        return runtime.stage_sprite
    return runtime.find_sprite(text)


def _asset_fetch(url):
    """读取 URL，返回 (字节, MIME)；失败返回 (None, '')"""
    text = _sc_str(url)
    if text.lower().startswith('data:'):
        header, _, payload = text[5:].partition(',')
        mime = header.split(';', 1)[0].strip().lower()
        try:
            if ';base64' in header.lower():
                import base64
                return base64.b64decode(payload), mime
            from urllib.parse import unquote_to_bytes
            return unquote_to_bytes(payload), mime
        except Exception:
            return None, ''
    try:
        import urllib.request
        with urllib.request.urlopen(text, timeout=20) as response:
            mime = response.headers.get('Content-Type', '')
            return response.read(), mime.split(';', 1)[0].strip().lower()
    except Exception:
        return None, ''


def _asset_guess_format(data, mime, url, kind):
    """按 MIME、URL 后缀、文件头推断资源格式"""
    fmt = _ASSET_MIME_TO_FORMAT.get((mime or '').lower())
    if fmt:
        return fmt
    path = _sc_str(url).split('?', 1)[0].split('#', 1)[0]
    ext = path.rsplit('.', 1)[-1].lower() if '.' in path else ''
    if kind == 'costume':
        if ext in ('png', 'jpg', 'jpeg', 'bmp', 'gif', 'webp', 'svg'):
            return 'jpg' if ext == 'jpeg' else ext
        if data[:8] == b'\x89PNG\r\n\x1a\n':
            return 'png'
        if data[:2] == b'\xff\xd8':
            return 'jpg'
        if data[:4] == b'GIF8':
            return 'gif'
        if data[:2] == b'BM':
            return 'bmp'
        if b'<svg' in data[:4096].lower():
            return 'svg'
        return 'png'
    if ext in ('mp3', 'wav', 'ogg', 'm4a', 'flac'):
        return ext
    if data[:4] == b'RIFF' and data[8:12] == b'WAVE':
        return 'wav'
    if data[:4] == b'OggS':
        return 'ogg'
    return 'mp3'


def _asset_store(runtime, data, fmt):
    """按内容哈希写入素材目录，返回 md5.ext 文件名"""
    import hashlib
    import os
    digest = hashlib.md5(data).hexdigest()
    filename = '%s.%s' % (digest, fmt)
    try:
        os.makedirs(runtime.assets_dir, exist_ok=True)
        path = os.path.join(runtime.assets_dir, filename)
        if not os.path.exists(path):
            with open(path, 'wb') as handle:
                handle.write(data)
    except OSError:
        return ''
    # 新增素材后清掉同名缓存，后续绘制/播放会重新加载
    runtime._asset_path_cache.pop(filename, None)
    runtime._costume_kind.pop(filename, None)
    runtime._costume_scale_caps.pop(filename, None)
    runtime.costume_cache.pop(filename, None)
    for key in [item for item in runtime.costume_cache_scales
                if item[0] == filename]:
        runtime.costume_cache_scales.pop(key, None)
    return filename


def _asset_valid_costume(data, fmt):
    if fmt == 'svg':
        return b'<svg' in data[:4096].lower()
    try:
        image = pygame.image.load(io.BytesIO(data))
        return image is not None
    except Exception:
        return False


def _asset_refresh_backdrops(runtime, sprite):
    """舞台造型变化后同步背景菜单（BACKDROPS）"""
    if not getattr(sprite, 'is_stage', False):
        return
    stage = runtime.stage_sprite
    if stage is None:
        return
    global BACKDROPS
    BACKDROPS[:] = [
        (costume.get('name', ''),
         costume.get('md5ext') or costume.get('name', ''))
        for costume in stage.costumes
    ]


def _asset_clamp_costume(sprite):
    count = len(sprite.costumes)
    if count <= 0:
        sprite.costume_number = 1
        sprite.costume_name = ''
        return
    number = int(_sc_num(getattr(sprite, 'costume_number', 1))) or 1
    number = max(1, min(count, number))
    sprite.costume_number = number
    sprite.costume_name = sprite.costumes[number - 1].get('name', '')


def _asset_costume_index(sprite, name):
    text = _sc_str(name)
    for index, costume in enumerate(sprite.costumes):
        if costume.get('name') == text:
            return index
    return -1


def _asset_sound_index(sprite, name):
    text = _sc_str(name)
    for index, sound in enumerate(sprite.sounds):
        if sound.get('name') == text:
            return index
    return -1


def _asset_file_format(filename):
    name = _sc_str(filename)
    return name.rsplit('.', 1)[-1].lower() if '.' in name else ''


def _asset_header(filename):
    return _ASSET_MIME.get(_asset_file_format(filename),
                           'application/octet-stream')


def _asset_id(filename):
    name = _sc_str(filename)
    return name.rsplit('.', 1)[0] if '.' in name else name


def _asset_data_uri(runtime, filename):
    data = runtime.asset_bytes(filename)
    if data is None:
        return ''
    import base64
    return ('data:%s;base64,%s'
            % (_asset_header(filename),
               base64.b64encode(data).decode('ascii')))


def _asset_add_costume(runtime, sprite, url, name):
    data, mime = _asset_fetch(url)
    if not data:
        return 0
    fmt = _asset_guess_format(data, mime, url, 'costume')
    if not _asset_valid_costume(data, fmt):
        return 0
    filename = _asset_store(runtime, data, fmt)
    if not filename:
        return 0
    costume = {
        'name': _sc_str(name) or 'costume1',
        'md5ext': filename, 'dataFormat': fmt,
        'rotationCenterX': None, 'rotationCenterY': None,
    }
    for item in _asset_family(runtime, sprite):
        item.costumes.append(dict(costume))
    _asset_refresh_backdrops(runtime, sprite)
    return 0


def _asset_add_sound(runtime, sprite, url, name):
    data, mime = _asset_fetch(url)
    if not data:
        return 0
    fmt = _asset_guess_format(data, mime, url, 'sound')
    filename = _asset_store(runtime, data, fmt)
    if not filename:
        return 0
    sound = {'name': _sc_str(name) or 'sound1', 'md5ext': filename}
    for item in _asset_family(runtime, sprite):
        item.sounds.append(dict(sound))
    return 0


def _asset_reorder(items, index1, index2):
    if index1 < 0 or index2 < 0:
        return False
    if index1 >= len(items) or index2 >= len(items):
        return False
    items.insert(index2, items.pop(index1))
    return True


def _asset_get_costume_data(runtime, sprite, attribute, name):
    index = _asset_costume_index(sprite, name)
    if index < 0:
        return ''
    costume = sprite.costumes[index]
    filename = costume.get('md5ext') or ''
    prop = _sc_str(attribute).strip().lower()
    if prop == 'index':
        return index + 1
    if prop == 'datauri':
        return _asset_data_uri(runtime, filename)
    if prop == 'format':
        return _asset_file_format(filename)
    if prop == 'header':
        return _asset_header(filename)
    if prop == 'asset id':
        return _asset_id(filename)
    return ''


def _asset_get_sound_data(runtime, sprite, attribute, name):
    index = _asset_sound_index(sprite, name)
    if index < 0:
        return ''
    sound = sprite.sounds[index]
    filename = sound.get('md5ext') or ''
    prop = _sc_str(attribute).strip().lower()
    if prop == 'index':
        return index + 1
    if prop == 'datauri':
        return _asset_data_uri(runtime, filename)
    if prop == 'format':
        return _asset_file_format(filename)
    if prop == 'header':
        return _asset_header(filename)
    if prop == 'asset id':
        return _asset_id(filename)
    return ''


def _extension_asset_manager(runtime, sprite, opcode, inputs, fields):
    """lmsAssets：造型/声音等资源管理"""
    key = str(opcode).lower().replace('_', '')
    if key.endswith('addsprite'):
        # 简单实现：运行时创建角色需要完整 VM，保留空操作
        return 0
    if key.endswith('addcostume'):
        return _asset_add_costume(
            runtime, sprite,
            _ext_input(inputs, fields, 'URL', 'url', default=''),
            _ext_input(inputs, fields, 'NAME', 'name', default='costume1'))
    if key.endswith('addsound'):
        return _asset_add_sound(
            runtime, sprite,
            _ext_input(inputs, fields, 'URL', 'url', default=''),
            _ext_input(inputs, fields, 'NAME', 'name', default='sound1'))
    if key.endswith('renamesprite'):
        target = _asset_target(
            runtime, sprite,
            _ext_input(inputs, fields, 'TARGET', 'target', default='_myself_'))
        if target is None or getattr(target, 'is_stage', False):
            return 0
        name = _sc_str(_ext_input(inputs, fields, 'NAME', 'name', default=''))
        for item in _asset_family(runtime, target):
            item.name = name
        return 0
    if key.endswith('renamecostume'):
        index = _asset_costume_index(
            sprite, _ext_input(inputs, fields, 'COSTUME', 'costume', default=''))
        if index < 0:
            return 0
        old = _sc_str(_ext_input(
            inputs, fields, 'COSTUME', 'costume', default=''))
        name = _sc_str(_ext_input(inputs, fields, 'NAME', 'name', default=''))
        for item in _asset_family(runtime, sprite):
            if index < len(item.costumes):
                item.costumes[index]['name'] = name
                if _sc_str(item.costume_name) == old:
                    item.costume_name = name
        _asset_refresh_backdrops(runtime, sprite)
        return 0
    if key.endswith('renamesound'):
        index = _asset_sound_index(
            sprite, _ext_input(inputs, fields, 'SOUND', 'sound', default=''))
        if index < 0:
            return 0
        name = _sc_str(_ext_input(inputs, fields, 'NAME', 'name', default=''))
        for item in _asset_family(runtime, sprite):
            if index < len(item.sounds):
                item.sounds[index]['name'] = name
        return 0
    if key.endswith('deletesprite'):
        target = _asset_target(
            runtime, sprite,
            _ext_input(inputs, fields, 'TARGET', 'target', default='_myself_'))
        if target is None or getattr(target, 'is_stage', False):
            return 0
        for item in _asset_family(runtime, target):
            runtime.stop_scripts_of(item)
            runtime.remove_sprite(item)
        runtime.mask_cache.clear()
        return 0
    if key.endswith('deletecostume'):
        index = _asset_costume_index(
            sprite, _ext_input(inputs, fields, 'COSTUME', 'costume', default=''))
        if index < 0:
            return 0
        for item in _asset_family(runtime, sprite):
            if index < len(item.costumes):
                item.costumes.pop(index)
                _asset_clamp_costume(item)
        _asset_refresh_backdrops(runtime, sprite)
        return 0
    if key.endswith('deletesound'):
        index = _asset_sound_index(
            sprite, _ext_input(inputs, fields, 'SOUND', 'sound', default=''))
        if index < 0:
            return 0
        for item in _asset_family(runtime, sprite):
            if index < len(item.sounds):
                item.sounds.pop(index)
        return 0
    if key.endswith('getallsprites'):
        import json
        names = [getattr(item, 'name', '')
                 for item in runtime.sprites
                 if not getattr(item, 'is_stage', False)
                 and not getattr(item, '_is_clone', False)]
        return json.dumps(names)
    if key.endswith('getallcostumes'):
        import json
        return json.dumps([item.get('name', '') for item in sprite.costumes])
    if key.endswith('getallsounds'):
        import json
        return json.dumps([item.get('name', '') for item in sprite.sounds])
    if key.endswith('getspritevalue2'):
        target = _asset_target(
            runtime, sprite,
            _ext_input(inputs, fields, 'TARGET', 'target', default='_myself_'))
        if target is None or getattr(target, 'is_stage', False):
            return ''
        export = _sc_str(
            _ext_input(inputs, fields, 'EXPORT', 'export', default='name'))
        if export == 'dataURI':
            # 简单实现：不导出整个角色（需要重新打包 sb3）
            return ''
        return getattr(target, 'name', '')
    if key.endswith('getspritevalue'):
        export = _sc_str(
            _ext_input(inputs, fields, 'EXPORT', 'export', default='name'))
        if export == 'dataURI':
            return ''
        return getattr(sprite, 'name', '')
    if key.endswith('getspritename'):
        return getattr(sprite, 'name', '')
    if key.endswith('reordercostume'):
        index1 = int(_sc_num(_ext_input(
            inputs, fields, 'INDEX1', 'index1', default=1))) - 1
        index2 = int(_sc_num(_ext_input(
            inputs, fields, 'INDEX2', 'index2', default=1))) - 1
        for item in _asset_family(runtime, sprite):
            current = _sc_str(item.costume_name)
            if _asset_reorder(item.costumes, index1, index2):
                for idx, costume in enumerate(item.costumes):
                    if costume.get('name') == current:
                        item.costume_number = idx + 1
                        break
        _asset_refresh_backdrops(runtime, sprite)
        return 0
    if key.endswith('reordersound'):
        index1 = int(_sc_num(_ext_input(
            inputs, fields, 'INDEX1', 'index1', default=1))) - 1
        index2 = int(_sc_num(_ext_input(
            inputs, fields, 'INDEX2', 'index2', default=1))) - 1
        for item in _asset_family(runtime, sprite):
            _asset_reorder(item.sounds, index1, index2)
        return 0
    if key.endswith('getsounddata'):
        return _asset_get_sound_data(
            runtime, sprite,
            _ext_input(inputs, fields, 'ATTRIBUTE', 'attribute',
                       default='index'),
            _ext_input(inputs, fields, 'SOUND', 'sound', default=''))
    if key.endswith('getcostumedata'):
        return _asset_get_costume_data(
            runtime, sprite,
            _ext_input(inputs, fields, 'ATTRIBUTE', 'attribute',
                       default='index'),
            _ext_input(inputs, fields, 'COSTUME', 'costume', default=''))
    if key.endswith('getcostumeatindex'):
        index = int(_sc_num(_ext_input(
            inputs, fields, 'INDEX', 'index', default=1))) - 1
        if 0 <= index < len(sprite.costumes):
            return sprite.costumes[index].get('name', '')
        return ''
    if key.endswith('getsoundatindex'):
        index = int(_sc_num(_ext_input(
            inputs, fields, 'INDEX', 'index', default=1))) - 1
        if 0 <= index < len(sprite.sounds):
            return sprite.sounds[index].get('name', '')
        return ''
    if key.endswith('getloadedextensions'):
        import json
        try:
            names = sorted({str(item).lower()
                            for item in _BUILTIN_EXTENSIONS})
        except NameError:
            names = []
        return json.dumps(names)
    # open project / project JSON / load extension：需要完整 VM，简单实现为空操作
    return 0
