# -*- coding: utf-8 -*-
"""动态收集外部对象的方法名，防止类方法重命名撞名。

构建时导入 pygame 与标准库，收集其模块与常用类的全部公开属性名。
这些名字一律不参与类方法重命名，避免 `rect.move()`、`mixer.pause()`、
`cond.wait()` 这类外部对象调用被改名后崩溃。
"""

from __future__ import annotations

import re
from typing import Set

_IDENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def collect_foreign_method_names() -> Set[str]:
    names: Set[str] = set()

    def absorb(obj) -> None:
        try:
            attrs = dir(obj)
        except Exception:
            return
        for attr in attrs:
            if not attr.startswith('_') and _IDENT.match(attr):
                names.add(attr)

    # 标准库模块与关键类
    modules = [
        'os', 'os.path', 'sys', 're', 'math', 'random', 'time', 'json',
        'io', 'base64', 'argparse', 'threading', 'functools', 'heapq',
        'decimal', 'array', 'hashlib', 'hmac', 'zlib', 'shutil',
        'tempfile', 'atexit', 'builtins', 'collections', 'types',
        'traceback', 'contextlib', 'operator', 'string', 'struct',
        'itertools', 'subprocess', 'socket', 'ssl', 'platform',
    ]
    for mod_name in modules:
        try:
            absorb(__import__(mod_name, fromlist=['*']))
        except Exception:
            pass

    classes = [
        # 标准库对象
        'threading.Thread', 'threading.Condition', 'threading.Event',
        'threading.Lock', 'threading.RLock', 'threading.Timer',
        'threading.local', 're.Pattern', 're.Match',
        'io.BytesIO', 'io.StringIO', 'io.IOBase', 'io.FileIO',
        'os.PathLike', 'argparse.ArgumentParser',
        'collections.deque', 'collections.OrderedDict',
        'decimal.Decimal', 'array.array',
        # pygame 模块与其常用类
        'pygame', 'pygame.mixer', 'pygame.mixer.music', 'pygame.display',
        'pygame.event', 'pygame.key', 'pygame.mouse', 'pygame.joystick',
        'pygame.draw', 'pygame.image', 'pygame.transform', 'pygame.scrap',
        'pygame.time', 'pygame.font', 'pygame.rect', 'pygame.surface',
        'pygame.cursors', 'pygame.midi', 'pygame.touch', 'pygame.freetype',
        'pygame.Rect', 'pygame.Surface', 'pygame.font.Font',
        'pygame.time.Clock', 'pygame.mixer.Sound', 'pygame.mixer.Channel',
        'pygame.joystick.Joystick', 'pygame.event.Event',
        'pygame.sprite.Sprite', 'pygame.sprite.Group',
        'pygame.freetype.Font', 'pygame.math.Vector2',
    ]
    for path in classes:
        try:
            obj = __import__(path, fromlist=['*'])
            absorb(obj)
            # pygame.mixer.music 这类子模块顺便收集
            for sub in ('music', 'Sound', 'Channel', 'Font', 'Clock',
                        'Rect', 'Surface', 'Event', 'Vector2'):
                try:
                    absorb(getattr(obj, sub))
                except Exception:
                    pass
        except Exception:
            pass

    return names
