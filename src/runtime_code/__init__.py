# -*- coding: utf-8 -*-
"""生成脚本使用的运行时模板。

拆分成多个模块，避免 python_generator.py 单文件过大；
这些都只是字符串模板，生成时原样写入输出脚本。
"""

from .helpers import HELPERS as RUNTIME_HELPERS
from .extensions import EXTENSIONS as RUNTIME_EXTENSIONS
from .runtime_class import RUNTIME_CLASS
from .sprite_base import SPRITE_BASE

__all__ = [
    "RUNTIME_HELPERS",
    "RUNTIME_EXTENSIONS",
    "RUNTIME_CLASS",
    "SPRITE_BASE",
]
