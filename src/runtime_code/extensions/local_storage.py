# -*- coding: utf-8 -*-
"""localstorage 本地存储"""

# ===================== Local Storage (localstorage) =====================

def _localstorage_path(runtime):
    namespace = getattr(runtime, 'localstorage_namespace', '') or \
        os.path.splitext(os.path.basename(__file__))[0]
    safe = ''.join(ch if ch.isalnum() or ch in '._-' else '_'
                   for ch in _sc_str(namespace))[:80] or 'project'
    folder = os.path.join(os.path.expanduser('~'), '.scratch-converter',
                          'localstorage')
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError:
        pass
    return os.path.join(folder, safe + '.json')


def _localstorage_load(runtime):
    if getattr(runtime, '_localstorage_cache', None) is not None:
        return runtime._localstorage_cache
    data = {}
    try:
        with open(_localstorage_path(runtime), 'r', encoding='utf-8') as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            data = loaded
    except (OSError, ValueError):
        pass
    runtime._localstorage_cache = data
    return data


def _localstorage_save(runtime):
    path = _localstorage_path(runtime)
    temp = path + '.tmp'
    try:
        with open(temp, 'w', encoding='utf-8') as handle:
            json.dump(getattr(runtime, '_localstorage_cache', {}), handle,
                      ensure_ascii=False)
        os.replace(temp, path)
    except OSError:
        pass


def _extension_local_storage(runtime, sprite, opcode, inputs, fields):
    """localstorage：持久化键值存储"""
    key = str(opcode).lower().replace('_', '')
    if key.endswith('setprojectid'):
        namespace = _sc_str(_ext_input(inputs, fields, 'ID', 'id', default=''))
        runtime.localstorage_namespace = namespace
        runtime._localstorage_cache = None
        return 0
    data = _localstorage_load(runtime)
    name = _sc_str(_ext_input(inputs, fields, 'KEY', 'key', default=''))
    if key.endswith('get'):
        return data.get(name, '')
    if key.endswith('set'):
        data[name] = _ext_input(inputs, fields, 'VALUE', 'value', default='')
        _localstorage_save(runtime)
        return 0
    if key.endswith('remove'):
        data.pop(name, None)
        _localstorage_save(runtime)
        return 0
    if key.endswith('removeall'):
        data.clear()
        _localstorage_save(runtime)
        return 0
    if key.endswith('keycount'):
        return len(data)
    if key.endswith('itemofkey'):
        index = _sc_round(_sc_num(
            _ext_input(inputs, fields, 'NUM', 'num', default=1)))
        keys = list(data.keys())
        if 1 <= index <= len(keys):
            return keys[index - 1]
        return ''
    return 0
