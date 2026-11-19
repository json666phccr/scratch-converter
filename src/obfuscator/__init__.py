# -*- coding: utf-8 -*-
"""SB3 -> 混淆 Python 单向转换器。

流程：

1. 读取 SB3 与资产；
2. IR 常量折叠（可选）；
3. 生成常规 Python；
4. AST 混淆（重命名、属性派发表、字符串加密表、垃圾代码、函数簇拆分）；
5. 编译成 code object；
6. 与资产一起 marshal -> zlib -> 分段 HMAC-SHA256 -> 密钥流异或 -> base85；
7. 生成极小加载器：密钥分裂 + 反调试探针 + 函数簇懒加载 +
   虚拟资产文件系统（内嵌模式不落盘）。

注意：任何纯 Python 本地混淆都无法做到“不可破解”。本工具的目标是显著提高
阅读、搜索与直接复用源码的成本，同时保持项目可正常运行。终极强度请配合
原生编译（Cython/Nuitka）与许可证体系（见 docs/obfuscator-hardening.md）。
"""

from __future__ import annotations

import ast
import hashlib
import os
import random
from dataclasses import dataclass
from typing import Dict, Optional, Set

from ir import ProjectIR
from python_generator import PythonGenerator
from scratch_vm import load_project

from .ast_obf import obfuscate_module
from .folding import fold_project
from .payload import build_payload, compile_module, loader_source

__version__ = "2.0.0"


class ObfuscationError(Exception):
    """混淆导出失败"""


@dataclass
class ObfuscationResult:
    output: str
    asset_count: int
    embedded_assets: bool
    size: int
    folded: bool
    clusters: int
    strings: int


def _asset_names(project: ProjectIR) -> Set[str]:
    names = set()
    for sprite in project.sprites:
        for costume in sprite.costumes or ():
            name = costume.get('md5ext')
            if name:
                names.add(os.path.basename(name))
        for sound in sprite.sounds or ():
            name = sound.get('md5ext')
            if name:
                names.add(os.path.basename(name))
    return names


def _read_assets(assets_dir: str, names: Set[str]) -> Dict[str, bytes]:
    assets = {}
    for name in sorted(names):
        path = os.path.join(assets_dir, name)
        if not os.path.isfile(path):
            raise ObfuscationError(f"缺少资产文件: {name}")
        with open(path, 'rb') as handle:
            assets[name] = handle.read()
    return assets


def _rename_assets(project: ProjectIR, assets: Dict[str, bytes],
                   seed) -> Dict[str, bytes]:
    """把 md5ext 资产名替换为 a_<hex>.<ext>，抹除资产身份"""
    rng = random.Random(seed)
    mapping: Dict[str, str] = {}
    renamed: Dict[str, bytes] = {}
    used = set()
    for old in sorted(assets):
        extension = old.rsplit('.', 1)[-1]
        while True:
            new = f"a_{rng.randrange(16 ** 10):010x}.{extension}"
            if new not in used:
                used.add(new)
                break
        mapping[old] = new
        renamed[new] = assets[old]
    if mapping:
        for sprite in project.sprites:
            for costume in sprite.costumes or ():
                old = costume.get('md5ext')
                if old in mapping:
                    costume['md5ext'] = mapping[old]
                    costume['assetId'] = mapping[old].rsplit('.', 1)[0]
            for sound in sprite.sounds or ():
                old = sound.get('md5ext')
                if old in mapping:
                    sound['md5ext'] = mapping[old]
                    sound['assetId'] = mapping[old].rsplit('.', 1)[0]
    return renamed


def _scrub_runtime_labels(code: str) -> str:
    """只替换运行时自己的标识，不碰用户字符串"""
    replacements = (
        ('Scratch 3.0 Runtime ', 'Studio Runtime '),
        ('[runtime] Scratch 3 运行时 v', '[runtime] 运行时 v'),
        ("'Scratch 3.0 runtime'", "'runtime'"),
        ('Scratch 3.0 / TurboWarp -> Python 转换代码', ''),
        ('由 scratch-converter 自动生成', ''),
        ('TurboWarp高级选项', '高级选项'),
    )
    for old, new in replacements:
        code = code.replace(old, new)
    # 混淆版不提供 --trace，避免运行时打印原始脚本/自制积木名
    code = code.replace(
        "    parser.add_argument('--trace', action='store_true', "
        "help='打印事件/脚本/过程调用')\n", "")
    code = code.replace("trace=args.trace", "trace=False")
    return code


def obfuscate_sb3(input_path: str,
                  output_path: Optional[str] = None,
                  embed_assets: bool = True,
                  fold: bool = True,
                  seed: Optional[int] = None) -> ObfuscationResult:
    """把 .sb3 转换为混淆后的单文件 Python。

    Args:
        input_path: .sb3/.json 输入
        output_path: 输出 .py；默认 <输入名>_obf.py
        embed_assets: True 时资产写入加密载荷，运行时通过虚拟文件系统
            按需解密（不落盘）；False 时导出到 <输出名>_assets/
        fold: 是否进行常量折叠与恒定条件简化
        seed: 混淆随机种子（None 表示每次不同）

    Returns:
        ObfuscationResult
    """
    input_path = os.path.abspath(input_path)
    if not os.path.exists(input_path):
        raise ObfuscationError(f"输入文件不存在: {input_path}")
    if output_path is None:
        stem = os.path.splitext(os.path.basename(input_path))[0]
        output_path = os.path.join(os.path.dirname(input_path),
                                   stem + '_obf.py')
    output_path = os.path.abspath(output_path)

    loaded = load_project(input_path)
    try:
        project = loaded.project
        if fold:
            fold_project(project)

        names = _asset_names(project)
        raw_assets = _read_assets(loaded.assets_dir, names)
        if embed_assets:
            payload_assets = _rename_assets(project, raw_assets, seed)
        else:
            payload_assets = {}

        code = PythonGenerator().generate_project(project)
        code = _scrub_runtime_labels(code)
        try:
            tree = ast.parse(code, filename='<generated>')
        except SyntaxError as error:
            raise ObfuscationError(f"生成代码语法错误: {error}") from error

        result = obfuscate_module(tree, seed)
        stage1_code = compile_module(result.tree, seed)

        spec = build_payload(
            stage1_code, result.clusters, result.str_entries,
            payload_assets, seed)
        asset_dir_name = (
            os.path.splitext(os.path.basename(output_path))[0] + '_assets')
        source = loader_source(
            spec,
            main_name=result.main_name,
            strtable_name=result.strtable_name,
            cluster_helper=result.cluster_helper,
            asset_helper='__al__',
            embed_assets=embed_assets,
            asset_dir=asset_dir_name,
            seed=seed)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(source)

        if not embed_assets and raw_assets:
            target_dir = os.path.join(os.path.dirname(output_path),
                                      asset_dir_name)
            os.makedirs(target_dir, exist_ok=True)
            for name, content in raw_assets.items():
                with open(os.path.join(target_dir, name), 'wb') as handle:
                    handle.write(content)

        return ObfuscationResult(
            output=output_path,
            asset_count=len(names),
            embedded_assets=embed_assets and bool(raw_assets),
            size=os.path.getsize(output_path),
            folded=fold,
            clusters=len(result.clusters),
            strings=len(result.str_entries),
        )
    finally:
        loaded.close()


__all__ = [
    "obfuscate_sb3",
    "ObfuscationResult",
    "ObfuscationError",
    "__version__",
]
