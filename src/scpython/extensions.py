# -*- coding: utf-8 -*-
"""ScPython 扩展支持。

两类扩展：

1. 内置常用扩展的函数式封装（pen / music），直接生成对应的 Scratch 扩展块；
2. 工程根目录 ``extensions.json`` 声明的自定义扩展：

```json
{
  "myext": {
    "jump": {
      "opcode": "myext_jump",
      "inputs": ["HEIGHT"],
      "fields": {"MODE": "MODE"}
    },
    "speed": {"opcode": "myext_getSpeed", "expr": true}
  }
}
```

角色代码里用 ``myext.jump(10, MODE="fast")`` 调用。
"""

from __future__ import annotations

import ast
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from .errors import ScPythonError


class ExtensionBlock:
    """一个扩展积木的声明"""

    def __init__(self, namespace: str, name: str, opcode: str,
                 inputs: List[str], fields: Dict[str, str],
                 hat: bool = False, expr: bool = False):
        self.namespace = namespace
        self.name = name
        self.opcode = opcode
        self.inputs = list(inputs)
        self.fields = dict(fields)
        self.hat = bool(hat)
        self.expr = bool(expr)


class ExtensionRegistry:
    """自定义扩展清单"""

    def __init__(self, project_root: str):
        self.project_root = project_root
        self.blocks: Dict[str, Dict[str, ExtensionBlock]] = {}
        self.manifest_path = os.path.join(project_root, 'extensions.json')
        self._load()

    def _load(self) -> None:
        if not os.path.isfile(self.manifest_path):
            return
        try:
            with open(self.manifest_path, 'r', encoding='utf-8') as handle:
                data = json.load(handle)
        except (OSError, ValueError) as error:
            raise ScPythonError(
                f"读取 extensions.json 失败: {error}",
                path=self.manifest_path) from error
        if not isinstance(data, dict):
            raise ScPythonError(
                "extensions.json 顶层必须是对象", path=self.manifest_path)

        for namespace, blocks in data.items():
            if not isinstance(blocks, dict):
                raise ScPythonError(
                    f"扩展 {namespace} 的声明必须是对象",
                    path=self.manifest_path)
            namespace_blocks = self.blocks.setdefault(str(namespace), {})
            for name, spec in blocks.items():
                if not isinstance(spec, dict):
                    raise ScPythonError(
                        f"扩展积木 {namespace}.{name} 的声明必须是对象",
                        path=self.manifest_path)
                namespace_blocks[str(name)] = ExtensionBlock(
                    str(namespace),
                    str(name),
                    str(spec.get('opcode') or f"{namespace}_{name}"),
                    list(spec.get('inputs') or []),
                    dict(spec.get('fields') or {}),
                    hat=bool(spec.get('hat')),
                    expr=bool(spec.get('expr')),
                )

    def resolve(self, namespace: str, name: str) -> Optional[ExtensionBlock]:
        return self.blocks.get(namespace, {}).get(name)

    def namespaces(self) -> set:
        return set(self.blocks)


# 内置扩展：函数名 -> (namespace, opcode, 输入槽顺序)
_BUILTIN_EXTENSIONS: Dict[str, Tuple[str, str, List[str]]] = {
    # 画笔
    'pen_clear': ('pen', 'pen_clear', []),
    'pen_down': ('pen', 'pen_down', []),
    'pen_up': ('pen', 'pen_up', []),
    'pen_stamp': ('pen', 'pen_stamp', []),
    'set_pen_color': ('pen', 'pen_setPenColorToColor', ['COLOR']),
    'set_pen_size': ('pen', 'pen_setPenSizeTo', ['SIZE']),
    'change_pen_size': ('pen', 'pen_changePenSizeBy', ['SIZE']),
    'set_pen_param': ('pen', 'pen_setPenColorParamTo',
                      ['COLOR_PARAM', 'VALUE']),
    'change_pen_param': ('pen', 'pen_changePenColorParamBy',
                         ['COLOR_PARAM', 'VALUE']),
    # 音乐
    'play_note': ('music', 'music_playNoteForBeats', ['NOTE', 'BEATS']),
    'play_drum': ('music', 'music_playDrumForBeats', ['DRUM', 'BEATS']),
    'set_tempo': ('music', 'music_setTempo', ['TEMPO']),
    'rest': ('music', 'music_restForBeats', ['BEATS']),
    'set_instrument': ('music', 'music_setInstrument', ['INSTRUMENT']),
}


def builtin_extension(name: str):
    return _BUILTIN_EXTENSIONS.get(name)


def bind_extension_args(block: ExtensionBlock,
                        args: List[ast.AST],
                        keywords: List[ast.keyword],
                        expr_to_ir,
                        eval_constant,
                        source_path: str) -> Tuple[list, dict]:
    """把调用参数绑定到扩展声明的 inputs / fields。

    Returns:
        (inputs, fields)：inputs 是 [(槽名, Expr)]，fields 是 {字段名: 字符串}
    """
    values: Dict[str, ast.AST] = {}
    for index, arg in enumerate(args):
        if index >= len(block.inputs):
            raise ScPythonError(
                f"扩展块 {block.namespace}.{block.name} 只接受 "
                f"{len(block.inputs)} 个位置参数", path=source_path)
        values[block.inputs[index]] = arg

    fields = {}
    for keyword in keywords:
        if keyword.arg is None:
            raise ScPythonError("扩展调用不支持 **kwargs", path=source_path)
        key = keyword.arg
        if key in block.fields:
            value = eval_constant(keyword.value)
            fields[block.fields[key]] = str(value)
        else:
            values[key] = keyword.value

    inputs = []
    for name in block.inputs:
        if name in values:
            inputs.append((name, expr_to_ir(values[name])))
    # 未声明但传入的关键字也作为输入（方便扩展作者少写声明）
    declared = set(block.inputs)
    for key, value in values.items():
        if key not in declared:
            inputs.append((key, expr_to_ir(value)))
    return inputs, fields
