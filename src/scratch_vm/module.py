# -*- coding: utf-8 -*-
"""运行时命名空间与动态角色类。

复用 ``python_generator`` 的字符串模板：把 ``runtime_code`` 中的
helpers / extensions / runtime / sprite 基类 exec 到一个独立命名空间，
再为每个 ``SpriteIR`` 生成一个 ``ScratchSprite`` 子类。

这样解释器可以直接使用现有的渲染、画笔、克隆、扩展、音频与询问框实现，
而不用重新实现一套 pygame 栈。
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from ir import ProjectIR, SpriteIR, sanitize_name
from python_generator import PythonGenerator, _json_literal


class RuntimeModule:
    """一个项目对应的一份运行时命名空间"""

    def __init__(self, project: ProjectIR, assets_dir: str,
                 namespace: Dict[str, Any],
                 sprite_classes: List[type]):
        self.project = project
        self.assets_dir = assets_dir
        self.namespace = namespace
        self.Runtime = namespace["ScratchRuntime"]
        self.SpriteBase = namespace["ScratchSprite"]
        self.sprite_classes = sprite_classes

    def create_runtime(self, **options) -> Any:
        """实例化 ScratchRuntime"""
        return self.Runtime(**options)

    def create_sprites(self, runtime) -> List[Any]:
        """实例化所有角色（含舞台）并加入运行时"""
        sprites = []
        for sprite_class in self.sprite_classes:
            sprite = sprite_class()
            runtime.add_sprite(sprite)
            sprites.append(sprite)
        return sprites


def _sprite_class_source(sprite: SpriteIR, index: int,
                         global_names: set) -> str:
    """生成单个角色的类定义源码（只含状态初始化，不含脚本）"""
    class_name = (f"VM_Sprite_{index}_"
                  f"{sanitize_name(sprite.name, 'sprite')}")
    lines = [
        f"class {class_name}(ScratchSprite):",
        f'    """角色: {sprite.name}"""',
        "",
    ]

    local_names = {
        sprite.variable_attrs.get(name) or sanitize_name(name, "var")
        for name in sprite.variables
    }
    local_names |= {
        sprite.list_attrs.get(name) or sanitize_name(name, "lst")
        for name in sprite.lists
    }
    if sprite.is_stage:
        # 舞台声明的是全局变量/列表，必须全部走共享 GLOBALS
        names = tuple(sorted(global_names))
    else:
        names = tuple(sorted(set(global_names) - local_names))
    lines.append(f"    GLOBAL_NAMES = {names!r}")
    lines.append("    GLOBAL_NAMES_SET = frozenset(GLOBAL_NAMES)")

    variable_attrs = {
        str(name): (sprite.variable_attrs.get(name)
                    or sanitize_name(name, "var"))
        for name in sprite.variables
    }
    list_attrs = {
        str(name): (sprite.list_attrs.get(name)
                    or sanitize_name(name, "lst"))
        for name in sprite.lists
    }
    lines.append(f"    VAR_ATTRS = {variable_attrs!r}")
    lines.append(f"    LIST_ATTRS = {list_attrs!r}")
    lines.append("")

    lines.append("    def __init__(self):")
    lines.append("        super().__init__()")
    lines.append(f"        self.x = {sprite.x!r}")
    lines.append(f"        self.y = {sprite.y!r}")
    lines.append(f"        self.direction = {sprite.direction!r}")
    lines.append(f"        self.visible = {sprite.visible!r}")
    lines.append(f"        self.size = {sprite.size!r}")
    lines.append(f"        self.name = {sprite.name!r}")
    if sprite.is_stage:
        lines.append("        self.is_stage = True")
    lines.append(f"        self.rotation_style = {sprite.rotation_style!r}")
    lines.append(f"        self.draggable = {bool(sprite.draggable)!r}")

    costumes = [
        {
            "name": costume.get("name", ""),
            "md5ext": costume.get("md5ext", ""),
            "dataFormat": costume.get("dataFormat", ""),
            "rotationCenterX": costume.get("rotationCenterX"),
            "rotationCenterY": costume.get("rotationCenterY"),
        }
        for costume in sprite.costumes
    ]
    sounds = [
        {"name": sound.get("name", ""), "md5ext": sound.get("md5ext", "")}
        for sound in sprite.sounds
    ]
    lines.append(f"        self.costumes = {costumes!r}")
    lines.append(f"        self.sounds = {sounds!r}")
    lines.append(f"        self.costume_number = {sprite.current_costume + 1}")
    if costumes:
        current = sprite.current_costume % len(costumes)
        lines.append(f"        self.costume_name = {costumes[current]['name']!r}")
    lines.append("")

    if not sprite.is_stage:
        for name, value in sprite.variables.items():
            attr = sprite.variable_attrs.get(name) \
                or sanitize_name(name, "var")
            lines.append(f"        self.{attr} = {_json_literal(value)}")
        if sprite.variables:
            lines.append("")
        for name, items in sprite.lists.items():
            attr = sprite.list_attrs.get(name) \
                or sanitize_name(name, "lst")
            lines.append(f"        self.{attr} = {_json_literal(list(items))}")
        if sprite.lists:
            lines.append("")

    return "\n".join(lines) + "\n"


def build_module(project: ProjectIR, assets_dir: str) -> RuntimeModule:
    """构建运行时命名空间与角色类"""
    gen = PythonGenerator()
    gen._prepare_globals(project)
    gen._prepare_extensions(project)

    lines = list(gen._module_imports())
    lines.extend(gen._generate_runtime_helpers())
    lines.append("")
    lines.extend(gen._generate_runtime_constants(project))
    lines.extend(gen._generate_runtime_class())
    lines.append("")
    lines.extend(gen._generate_base_class())
    lines.append("")

    source = "\n".join(lines)
    # 让模板里的 ASSETS_DIR 指向真实资源目录
    filename = os.path.join(assets_dir, "scratch_vm_runtime.py")
    namespace: Dict[str, Any] = {
        "__name__": "scratch_vm_runtime",
        "__file__": filename,
    }
    exec(compile(source, filename, "exec"), namespace)

    sprite_classes = []
    for index, sprite in enumerate(project.sprites):
        class_source = _sprite_class_source(sprite, index, gen.global_names)
        filename = os.path.join(
            assets_dir, f"scratch_vm_sprite_{index}.py")
        exec(compile(class_source, filename, "exec"), namespace)
        class_name = (f"VM_Sprite_{index}_"
                      f"{sanitize_name(sprite.name, 'sprite')}")
        sprite_classes.append(namespace[class_name])

    return RuntimeModule(project, assets_dir, namespace, sprite_classes)
