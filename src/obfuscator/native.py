# -*- coding: utf-8 -*-
"""Tier 2 原生编译管线（P6）。

把多态壳 loader 用 Cython 编译为平台扩展（Windows .pyd / Linux .so），
分发形态::

    <name>_native/
      main.py            纯 Python 壳（import core）
      core.cpXXX-xxx.pyd 原生扩展：解密 + 许可证绑定 + exec 全在原生代码里

字节码级工具（marshal dump / pycdc / exec hook）对原生扩展失效；
反编译主 init 函数有实际摩擦。但 native 不等于加密：Cython 压缩字符串
表、片段编码、运行期 import 后的内存状态都是可提取的数据（见
docs/obfuscator-hardening.md §15）。数据保密需配合 --license-file
（机器指纹不出分发物）或服务端授权。

注意：native 模式下 loader 的调用栈指纹校验被禁用（Cython 代码的
co_filename 是编译期 .pyx 路径，指纹语义不适用）；loader 整体收进
单一入口函数，模块命名空间在启动后不再暴露片段/分段表/字符串表。
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
import shutil
import sys

from setuptools import Extension, setup
from Cython.Build import cythonize

macros = []
if sys.maxsize > 2 ** 32:
    macros.append(('MS_WIN64', None))
    macros.append(('SIZEOF_VOID_P', '8'))

# F2/D2：不生成调试信息，避免 DWARF 泄露加载器变量词汇表
extra = ['-g0'] if shutil.which('gcc') else []

ext = Extension('core', ['core.pyx'], define_macros=macros,
                language='c', extra_compile_args=extra)
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
                src_file = os.path.join(workdir, name)
                # F2/D2：strip 兜底（-g0 已禁止生成调试段）
                strip = shutil.which('strip')
                if strip:
                    try:
                        subprocess.run([strip, '--strip-debug', src_file],
                                       capture_output=True, timeout=60)
                    except (OSError, subprocess.TimeoutExpired):
                        pass
                shutil.copy2(src_file, os.path.join(output_dir, name))
                copied.append(name)
        if not copied:
            raise ObfuscationError("编译完成但未找到 core 扩展产物")
        main_path = os.path.join(output_dir, 'main.py')
        with open(main_path, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(_MAIN_STUB)
        return output_dir
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
