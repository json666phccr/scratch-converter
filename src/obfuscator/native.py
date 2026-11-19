# -*- coding: utf-8 -*-
"""Tier 2 原生编译管线（P6）。

把多态壳 loader 用 Cython 编译为平台扩展（Windows .pyd / Linux .so），
分发形态::

    <name>_native/
      main.py            纯 Python 壳（import core）
      core.cpXXX-xxx.pyd 原生扩展：解密 + 许可证绑定 + exec 全在原生代码里

字节码级工具（marshal dump / pycdc / exec hook）对原生扩展完全失效，
只能上 IDA/Ghidra 级逆向。构建失败给出清晰提示并建议回退 Tier 1。

注意：native 模式下 loader 的调用栈指纹校验被禁用（Cython 代码的
co_filename 是编译期 .pyx 路径，指纹语义不适用）——原生编译本身
提供更强的保护。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

from . import ObfuscationError

_MAIN_STUB = '''\
# -*- coding: utf-8 -*-
"""Tier 2 原生产物入口：全部解密与执行逻辑在原生扩展内。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core
'''

_SETUP_STUB = '''\
# -*- coding: utf-8 -*-
import os
import sys

from setuptools import Extension, setup
from Cython.Build import cythonize

macros = []
if sys.maxsize > 2 ** 32:
    macros.append(('MS_WIN64', None))
    macros.append(('SIZEOF_VOID_P', '8'))

ext = Extension('core', ['core.pyx'], define_macros=macros,
                language='c')
setup(ext_modules=cythonize(ext, language_level=3))
'''


def _pick_compiler() -> list:
    """构建命令参数：Windows 优先 MinGW gcc，否则走默认（MSVC）"""
    if sys.platform == 'win32' and shutil.which('gcc'):
        return ['--compiler=mingw32']
    return []


def build_native(loader_source_text: str, output_dir: str,
                 seed=None) -> str:
    """把 loader 源码编译为原生扩展，输出到 output_dir。

    返回构建目录路径。编译器/Cython 缺失时抛 ObfuscationError。
    """
    try:
        import Cython  # noqa: F401
    except ImportError as exc:
        raise ObfuscationError(
            "native 模式需要 Cython：pip install cython"
            "（或改用纯 Python 模式）") from exc

    if os.path.exists(output_dir) and os.listdir(output_dir):
        raise ObfuscationError(f"输出目录已存在且非空: {output_dir}")
    os.makedirs(output_dir, exist_ok=True)

    workdir = tempfile.mkdtemp(prefix='obf_native_')
    try:
        pyx_path = os.path.join(workdir, 'core.pyx')
        with open(pyx_path, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write('# cython: language_level=3\n'
                         '# cython: binding=False\n')
            handle.write(loader_source_text)
        setup_path = os.path.join(workdir, 'setup.py')
        with open(setup_path, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(_SETUP_STUB)

        cmd = [sys.executable, setup_path, 'build_ext', '--inplace']
        cmd += _pick_compiler()
        proc = subprocess.run(cmd, cwd=workdir, capture_output=True,
                              text=True, timeout=600)
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or '')[-1500:]
            raise ObfuscationError(
                f"原生编译失败（检查 C 编译器是否可用）:\n{detail}")

        # 拷贝产物：core*.pyd/.so + main.py 壳
        copied = []
        for name in os.listdir(workdir):
            if name.startswith('core.') and name.endswith(('.pyd', '.so')):
                shutil.copy2(os.path.join(workdir, name),
                             os.path.join(output_dir, name))
                copied.append(name)
        if not copied:
            raise ObfuscationError("编译完成但未找到 core 扩展产物")
        main_path = os.path.join(output_dir, 'main.py')
        with open(main_path, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(_MAIN_STUB)
        return output_dir
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
