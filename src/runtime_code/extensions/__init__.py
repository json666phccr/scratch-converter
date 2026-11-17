# -*- coding: utf-8 -*-
"""运行时扩展源码包

各个扩展按文件放在本目录下（.py 里是可直接拼接到生成脚本的源码），
由 config.json 描述扩展 ID、处理器函数、别名、依赖文件与额外根节点。
生成脚本时只拼装项目实际用到的扩展及其依赖函数。
"""

import json
import os

_DIR = os.path.dirname(os.path.abspath(__file__))
_CONFIG_PATH = os.path.join(_DIR, 'config.json')

with open(_CONFIG_PATH, encoding='utf-8') as _fp:
    _CONFIG = json.load(_fp)

CORE_FILES = tuple(_CONFIG.get('core') or ())
CORE_ROOTS = tuple(_CONFIG.get('core_roots') or ())
EXTENSION_CONFIG = _CONFIG.get('extensions') or {}

EXTRA_ROOTS = {
    name: tuple(spec.get('extra_roots') or ())
    for name, spec in EXTENSION_CONFIG.items()
}

HANDLER_GROUPS = {
    name: (spec['handler'], tuple(spec.get('aliases') or [name]))
    for name, spec in EXTENSION_CONFIG.items()
}

_FILE_CACHE = {}


def read_source(filename):
    """读取子文件源码（带缓存）"""
    if filename not in _FILE_CACHE:
        path = os.path.join(_DIR, filename)
        with open(path, encoding='utf-8') as handle:
            _FILE_CACHE[filename] = handle.read().rstrip('\n')
    return _FILE_CACHE[filename]


def _assemble_all():
    names = list(CORE_FILES)
    for spec in EXTENSION_CONFIG.values():
        for filename in spec.get('files') or ():
            if filename not in names:
                names.append(filename)
    return '\n\n\n'.join(read_source(name) for name in names)


EXTENSIONS = _assemble_all()
