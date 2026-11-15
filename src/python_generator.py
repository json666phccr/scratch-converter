#!/usr/bin/env python3
"""
Python 代码生成器
将中间表示 (IR) 转换为 Python 源代码

生成的Python代码使用一种特殊DSL，与Scratch块一一对应：
- 每个Scratch块 -> 一个Python函数调用
- Scratch循环 -> Python for/while循环
- Scratch变量 -> Python变量
- Scratch自制积木 -> Python函数
- Scratch事件 -> 装饰器标记的函数
"""

import math
from typing import Dict, List, Optional, Set
from ir import (
    BlockType, ExprType, Expr, Statement, SpriteIR, ProjectIR,
    sanitize_name, key_to_identifier, set_procedure_name_resolver,
)
from runtime_code import (
    RUNTIME_HELPERS, RUNTIME_EXTENSIONS, RUNTIME_CLASS, SPRITE_BASE,
)


class PythonGenerator:
    """将ProjectIR转换为Python源代码"""

    # 运行时模板位于 runtime_code 包，按模块拆分，便于阅读和维护
    RUNTIME_HELPERS = RUNTIME_HELPERS
    RUNTIME_EXTENSIONS = RUNTIME_EXTENSIONS
    RUNTIME_CLASS = RUNTIME_CLASS
    SPRITE_BASE = SPRITE_BASE

    def __init__(self):
        self.imports: Set[str] = set()
        self.indent_level = 0
        self.current_sprite: Optional[SpriteIR] = None
        self.procedure_names: Dict[str, str] = {}
        self.stage_globals: Dict[str, object] = {}
        self.global_names: Set[str] = set()

    def _prepare_globals(self, project: ProjectIR):
        """收集舞台上的全局变量/列表（单文件与多文件输出共用）"""
        self.imports = {"import math", "import time", "import random"}

        # Scratch全局变量/列表存放在舞台上；生成后放进共享的GLOBALS字典，
        # 所有角色通过 __getattr__/__setattr__ 读写同一份数据。
        self.stage_globals = {}
        if project.stage is not None:
            for name, value in project.stage.variables.items():
                self.stage_globals[sanitize_name(name, 'var')] = value
            for name, items in project.stage.lists.items():
                self.stage_globals[sanitize_name(name, 'lst')] = list(items)
        self.global_names = set(self.stage_globals)

    def generate_project(self, project: ProjectIR) -> str:
        """生成整个项目的Python代码"""
        self._prepare_globals(project)

        lines = []
        lines.append("# -*- coding: utf-8 -*-")
        lines.append('"""')
        lines.append("Scratch 3.0 / TurboWarp -> Python 转换代码")
        lines.append("由 scratch-converter 自动生成")
        lines.append('"""')
        lines.append("")
        if project.warnings:
            summary = ', '.join(f"{opcode} x{count}"
                                for opcode, count in sorted(project.warnings.items()))
            lines.append(f"# 转换报告: 以下积木暂未支持，已从脚本中忽略: {summary}")
            lines.append("")
        lines.append("import math")
        lines.append("import time")
        lines.append("import random")
        lines.append("import re")
        lines.append("import array")
        lines.append("import decimal")
        lines.append("import os")
        lines.append("import io")
        lines.append("import base64")
        lines.append("import argparse")
        lines.append("import threading")
        lines.append("import json")
        lines.append("import functools")
        lines.append("")
        lines.append("try:")
        lines.append("    import pygame")
        lines.append("except ImportError:")
        lines.append("    pygame = None")
        lines.append("")

        lines.extend(self._generate_runtime_helpers())
        lines.append("")

        lines.extend(self._generate_runtime_constants(project))
        lines.extend(self._generate_runtime_class())
        lines.append("")

        lines.extend(self._generate_base_class())
        lines.append("")

        for sprite in project.sprites:
            lines.extend(self._generate_sprite_class(sprite))
            lines.append("")

        lines.extend(self._generate_main(project))
        set_procedure_name_resolver(None)
        return "\n".join(lines)

    def generate_modules(self, project: ProjectIR, prefix: str = 'scratch'):
        """生成模块化多文件输出

        返回 (入口代码, {附加文件名: 代码})：
        - <prefix>_runtime.py   运行时与辅助函数（所有角色共享）
        - <prefix>_sprite_NN_*.py  每个角色一个模块
        """
        self._prepare_globals(project)
        prefix = sanitize_name(prefix, 'scratch') or 'scratch'
        header = [
            "# -*- coding: utf-8 -*-",
            '"""由 scratch-converter 自动生成，请勿手动修改"""',
            "",
        ]
        runtime_module = f"{prefix}_runtime"
        runtime_lines = list(header)
        runtime_lines.extend(self._module_imports())
        runtime_lines.extend(self._generate_runtime_helpers())
        runtime_lines.append("")
        runtime_lines.extend(self._generate_runtime_constants(project))
        runtime_lines.extend(self._generate_runtime_class())
        runtime_lines.append("")
        runtime_lines.extend(self._generate_base_class())
        files = {runtime_module + ".py": "\n".join(runtime_lines)}

        sprite_modules = []
        for index, sprite in enumerate(project.sprites, 1):
            class_name = sanitize_name(sprite.name, "Sprite")
            module_name = (f"{prefix}_sprite_{index:02d}_"
                           f"{sanitize_name(sprite.name, 'sprite')}")
            lines = list(header)
            lines.append(f'"""角色: {sprite.name}"""')
            lines.extend(self._bootstrap_runtime(runtime_module))
            lines.append("")
            lines.extend(self._generate_sprite_class(sprite))
            files[module_name + ".py"] = "\n".join(lines)
            sprite_modules.append((module_name, class_name))

        entry_lines = list(header)
        entry_lines.append("import os")
        entry_lines.append("import sys")
        entry_lines.append("import random")
        entry_lines.append("import argparse")
        entry_lines.append("")
        entry_lines.append("_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))")
        entry_lines.append("if _SCRIPT_DIR not in sys.path:")
        entry_lines.append("    sys.path.insert(0, _SCRIPT_DIR)")
        entry_lines.append("")
        entry_lines.append(f"from {runtime_module} import ScratchRuntime")
        for module_name, class_name in sprite_modules:
            entry_lines.append(f"from {module_name} import {class_name}")
        entry_lines.append("")
        entry_lines.extend(self._generate_main(project))
        return "\n".join(entry_lines), files

    @staticmethod
    def _module_imports() -> List[str]:
        """运行时模块需要的导入（与单文件版本保持一致）"""
        return [
            "import math", "import time", "import random", "import re",
            "import array", "import decimal", "import os", "import io",
            "import base64",
            "import threading", "import json", "import functools",
            "",
            "try:",
            "    import pygame",
            "except ImportError:",
            "    pygame = None",
            "",
        ]

    @staticmethod
    def _bootstrap_runtime(runtime_module: str) -> List[str]:
        """角色模块把运行时模块的公开/下划线名字全部导入当前命名空间"""
        return [
            "import os",
            "import sys",
            "",
            "_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))",
            "if _SCRIPT_DIR not in sys.path:",
            "    sys.path.insert(0, _SCRIPT_DIR)",
            "",
            f"import {runtime_module} as _scratch_runtime",
            "",
            "for _name in dir(_scratch_runtime):",
            "    if not _name.startswith('__'):",
            "        globals()[_name] = getattr(_scratch_runtime, _name)",
            "del _name",
            "",
        ]

    def _generate_runtime_helpers(self) -> List[str]:
        """生成复刻Scratch类型转换与运算语义的模块级辅助函数"""
        lines = self.RUNTIME_HELPERS.strip('\n').splitlines()
        lines.append("")
        lines.extend(self.RUNTIME_EXTENSIONS.strip('\n').splitlines())
        return lines

    def _generate_runtime_constants(self, project: ProjectIR) -> List[str]:
        """生成资源目录、全局变量与监视器常量"""
        lines = []
        lines.append("try:")
        lines.append("    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))")
        lines.append("except NameError:")
        lines.append("    _SCRIPT_DIR = os.getcwd()")
        lines.append("ASSETS_DIR = _SCRIPT_DIR")

        stage_costume = ''
        backdrops = []
        if project.stage is not None and project.stage.costumes:
            stage_costume = (project.stage.costumes[0].get('md5ext') or
                             project.stage.costumes[0].get('name') or '')
            backdrops = [
                (costume.get('name', ''),
                 costume.get('md5ext') or costume.get('name', ''))
                for costume in project.stage.costumes
            ]
        lines.append(f"STAGE_COSTUME = {stage_costume!r}")
        lines.append(f"BACKDROPS = {backdrops!r}")
        lines.append(f"GLOBALS = {self.stage_globals!r}")
        lines.append("")

        monitors = []
        for monitor in project.monitors:
            if not monitor.get('visible'):
                continue
            owner = monitor.get('spriteName')
            params = monitor.get('params', {})
            if monitor.get('mode') == 'list' or monitor.get('opcode') == 'data_listcontents':
                name = str(params.get('LIST', ''))
                monitors.append({
                    'kind': 'list', 'name': name,
                    'sprite': owner,
                    # 局部列表按Scratch习惯加角色名前缀
                    'label': name if not owner or name.startswith(owner + ':')
                             else f"{owner}: {name}",
                    'attr': sanitize_name(name, 'lst'),
                    'x': monitor.get('x', 0), 'y': monitor.get('y', 0),
                    'width': monitor.get('width') or 200,
                    'height': monitor.get('height') or 150,
                })
            else:
                name = str(params.get('VARIABLE', ''))
                monitors.append({
                    'kind': 'var', 'name': name,
                    'sprite': owner,
                    # 局部变量按Scratch习惯加角色名前缀
                    'label': name if not owner or name.startswith(owner + ':')
                             else f"{owner}: {name}",
                    'attr': sanitize_name(name, 'var'),
                    'x': monitor.get('x', 0), 'y': monitor.get('y', 0),
                    'width': monitor.get('width') or 120,
                    'height': monitor.get('height') or 20,
                })
        lines.append(f"MONITORS = {monitors!r}")
        lines.append("")
        return lines

    def _generate_runtime_class(self) -> List[str]:
        """生成pygame运行时类"""
        return self.RUNTIME_CLASS.strip('\n').splitlines()

    def _generate_base_class(self) -> List[str]:
        """生成精灵基类"""
        return self.SPRITE_BASE.strip('\n').splitlines()

    # ===================== 自制积木命名 =====================

    def _build_procedure_names(self, sprite: SpriteIR):
        """为每个自制积木生成唯一方法名，并建立proccode -> 方法名映射"""
        self.procedure_names = {}
        used = set()
        for stmt in sprite.statements:
            if stmt.type != BlockType.PROCEDURE_DEFINE:
                continue
            key = stmt.extra.get('proccode') or stmt.extra.get('name') or 'procedure'
            base = sanitize_name(stmt.extra.get('name') or 'procedure', 'proc')
            name = base
            index = 2
            while name in used:
                name = f"{base}_{index}"
                index += 1
            used.add(name)
            self.procedure_names[key] = name
            stmt.extra['python_name'] = name

        mapping = dict(self.procedure_names)

        def resolver(proccode, fallback):
            return mapping.get(proccode, fallback)

        set_procedure_name_resolver(resolver)

    def _procedure_name(self, stmt: Statement) -> str:
        proccode = stmt.extra.get('proccode')
        if proccode and proccode in self.procedure_names:
            return self.procedure_names[proccode]
        return (stmt.extra.get('python_name') or
                sanitize_name(stmt.extra.get('name') or 'procedure', 'proc'))

    # ===================== 事件 =====================

    def _event_info(self, stmt: Statement):
        """返回 (方法名, docstring, 运行时事件key)"""
        if stmt.type == BlockType.WHEN_FLAG_CLICKED:
            return 'when_green_flag', '当绿旗被点击时', 'green_flag'
        if stmt.type == BlockType.WHEN_KEY_PRESSED:
            key = stmt.extra.get('key') or 'space'
            name = f"when_key_pressed_{key_to_identifier(key)}"
            return name, f'当按下{key}键时', f'key:{key}'
        if stmt.type == BlockType.WHEN_THIS_SPRITE_CLICKED:
            return 'when_clicked', '当角色被点击时', 'clicked'
        if stmt.type == BlockType.START_AS_CLONE:
            return 'when_clone_starts', '当作为克隆体启动时', 'clone_start'
        if stmt.type == BlockType.WHEN_BROADCAST_RECEIVED:
            msg = stmt.value.to_scratch_value() if stmt.value is not None else ''
            msg = str(msg)
            name = f"when_broadcast_{sanitize_name(msg, 'msg')}"
            # 反向解析依赖这句docstring恢复含空格的广播名
            return name, f"当接收到广播'{msg}'时", f'broadcast:{msg}'
        if stmt.type == BlockType.WHEN_BACKDROP_SWITCHES:
            backdrop = stmt.extra.get('backdrop') or 'backdrop1'
            name = f"when_backdrop_{sanitize_name(backdrop, 'backdrop')}"
            return name, f"当背景换成'{backdrop}'时", f'backdrop:{backdrop}'
        if stmt.type == BlockType.WHEN_GREATER_THAN:
            menu = str(stmt.extra.get('menu') or 'TIMER').lower()
            if menu == 'loudness':
                return ('when_loudness_greater_than', '当响度大于设定值时',
                        'greater_than:loudness')
            return ('when_timer_greater_than', '当计时器大于设定值时',
                    'greater_than:timer')
        if stmt.type == BlockType.EXTENSION_HAT:
            opcode = str(stmt.extra.get('opcode') or '')
            short = opcode.lower().split('_', 1)[-1]
            names = {
                'whenclonestartswithvar': ('when_clone_starts_with_var',
                                           '当克隆体带着指定变量值启动时'),
                'whenstopclicked': ('when_stop_clicked', '当停止按钮被点击时'),
                'forever': ('when_forever', 'More Events: 一直重复'),
                'whentruefalse': ('when_condition_becomes',
                                  'More Events: 当条件变为指定状态时'),
                'whiletruefalse': ('while_condition_is',
                                   'More Events: 当条件保持指定状态时'),
                'whenvaluechanged': ('when_value_changed',
                                     'More Events: 当值改变时'),
                'everyduration': ('every_frames', 'More Events: 每隔若干帧'),
                'whenkeyaction': ('when_key_action',
                                  'More Events: 当按键按下/松开时'),
                'whilekeypressed': ('while_key_pressed',
                                    'More Events: 按键保持按下时'),
                'beforesave': ('before_project_saves',
                               'More Events: 项目保存前'),
                'aftersave': ('after_project_saves',
                              'More Events: 项目保存后'),
            }
            name, doc = names.get(
                short, ('when_' + sanitize_name(short, 'event'), '扩展帽子事件'))
            return name, doc, 'extension_hat:' + opcode.lower()
        return None, None, None

    def _generate_event_handler(self, stmt: Statement,
                                name: Optional[str] = None,
                                doc: Optional[str] = None) -> List[str]:
        if name is None or doc is None:
            name, doc, _event = self._event_info(stmt)
        lines = [f"    def {name}(self):", f'        """{doc}"""']
        body = self._emit_chain(stmt.next, 2)
        if body:
            lines.extend(body)
        else:
            lines.append("        pass")
        lines.append("")
        return lines

    def _emit_chain(self, stmt: Optional[Statement], indent: int) -> List[str]:
        lines = []
        seen = set()
        while stmt is not None and id(stmt) not in seen:
            seen.add(id(stmt))
            lines.extend(self._generate_statement(stmt, indent))
            stmt = stmt.next
        return lines

    def _emit_body(self, body: List[Statement], indent: int) -> List[str]:
        lines = []
        for child in body:
            lines.extend(self._generate_statement(child, indent))
        return lines

    # ===================== 自制积木定义 =====================

    def _generate_procedure(self, stmt: Statement) -> List[str]:
        name = self._procedure_name(stmt)
        args = list(stmt.extra.get('args') or [])
        arg_types = list(stmt.extra.get('arg_types') or [])
        while len(arg_types) < len(args):
            arg_types.append('s')
        if len(arg_types) > len(args):
            arg_types = arg_types[:len(args)]

        python_args = []
        used = set()
        for index, arg in enumerate(args):
            base = f"arg_{sanitize_name(str(arg), 'arg')}"
            candidate = base
            suffix = 2
            while candidate in used:
                candidate = f"{base}_{suffix}"
                suffix += 1
            used.add(candidate)
            python_args.append(candidate)

        meta = [f"warp={bool(stmt.extra.get('warp'))}",
                f"arg_types={arg_types!r}", f"arg_names={args!r}"]
        proccode = stmt.extra.get('proccode')
        if proccode:
            meta.append(f"proccode={proccode!r}")
        arg_ids = stmt.extra.get('argumentids')
        if arg_ids:
            meta.append(f"arg_ids={list(arg_ids)!r}")
        arg_defaults = list(stmt.extra.get('argumentdefaults') or [])
        if arg_defaults:
            meta.append(f"arg_defaults={arg_defaults!r}")

        lines = [f"    @_as_procedure({', '.join(meta)})"]
        signature = ["self"]
        for index, python_arg in enumerate(python_args):
            # 与 Scratch 一致：未填参数取 definition 的 argumentdefaults，
            # 新建积木的默认值是空字符串（布尔为 False）。
            if index < len(arg_defaults):
                default = repr(arg_defaults[index])
            else:
                default = repr(False if arg_types[index] == 'b' else '')
            signature.append(f"{python_arg}={default}")
        lines.append(f"    def {name}({', '.join(signature)}):")
        title = proccode or stmt.extra.get('name') or 'procedure'
        lines.append(f'        """自制积木: {title}"""')
        body = self._emit_body(stmt.body, 2)
        if body:
            lines.extend(body)
        else:
            lines.append("        pass")
        lines.append("")
        return lines

    # ===================== 精灵类 =====================

    def _generate_sprite_class(self, sprite: SpriteIR) -> List[str]:
        """生成单个精灵的Python类"""
        self.current_sprite = sprite
        self._build_procedure_names(sprite)
        lines = []

        class_name = sanitize_name(sprite.name, "Sprite")
        lines.append(f"class {class_name}(ScratchSprite):")
        lines.append(f'    """精灵: {sprite.name}"""')
        lines.append("")

        local_names = {sanitize_name(name, 'var') for name in sprite.variables}
        local_names |= {sanitize_name(name, 'lst') for name in sprite.lists}
        if sprite.is_stage:
            # 舞台声明的是Scratch全局变量/列表，必须全部走共享GLOBALS
            global_names = tuple(sorted(self.global_names))
        else:
            global_names = tuple(sorted(self.global_names - local_names))
        lines.append(f"    GLOBAL_NAMES = {global_names!r}")
        lines.append("    GLOBAL_NAMES_SET = frozenset(GLOBAL_NAMES)")
        # 扩展积木按“变量名”访问变量时，需要名字到Python属性的映射
        variable_attrs = {
            str(name): sanitize_name(name, 'var')
            for name in sprite.variables
        }
        lines.append(f"    VAR_ATTRS = {variable_attrs!r}")
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
                'name': costume.get('name', ''),
                'md5ext': costume.get('md5ext', ''),
                'dataFormat': costume.get('dataFormat', ''),
                'rotationCenterX': costume.get('rotationCenterX'),
                'rotationCenterY': costume.get('rotationCenterY'),
            }
            for costume in sprite.costumes
        ]
        lines.append(f"        self.costumes = {costumes!r}")
        sounds = [
            {'name': sound.get('name', ''), 'md5ext': sound.get('md5ext', '')}
            for sound in sprite.sounds
        ]
        lines.append(f"        self.sounds = {sounds!r}")
        lines.append(f"        self.costume_number = {sprite.current_costume + 1}")
        if costumes:
            index = sprite.current_costume % len(costumes)
            lines.append(f"        self.costume_name = {costumes[index]['name']!r}")
        lines.append("")

        if not sprite.is_stage:
            for name, value in sprite.variables.items():
                lines.append(f"        self.{sanitize_name(name, 'var')} = {value!r}")
            if sprite.variables:
                lines.append("")

            for name, items in sprite.lists.items():
                lines.append(f"        self.{sanitize_name(name, 'lst')} = {list(items)!r}")
            if sprite.lists:
                lines.append("")

        for stmt in sprite.statements:
            if stmt.type == BlockType.PROCEDURE_DEFINE:
                lines.extend(self._generate_procedure(stmt))
                lines.append("")

        # 同一帽子事件可以有多个并列脚本，必须各自生成独立方法并全部注册
        event_entries = self._collect_event_entries(sprite)
        for stmt, name, doc, _event in event_entries:
            lines.extend(self._generate_event_handler(stmt, name, doc))
            lines.append("")

        lines.extend(self._generate_run_method(event_entries))
        return lines

    def _collect_event_entries(self, sprite: SpriteIR):
        """为每个事件脚本分配唯一方法名（重复帽子事件加 _2/_3 后缀）"""
        entries = []
        used = set()
        for stmt in sprite.statements:
            base, doc, event = self._event_info(stmt)
            if not base or not event:
                continue
            name = base
            index = 2
            while name in used:
                name = f"{base}_{index}"
                index += 1
            used.add(name)
            entries.append((stmt, name, doc, event))
        return entries

    def _generate_run_method(self, event_entries) -> List[str]:
        lines = ["    def run(self):", '        """向运行时注册事件脚本"""']
        if not event_entries:
            lines.append("        pass")
            return lines
        for stmt, name, _doc, event in event_entries:
            if stmt.type == BlockType.EXTENSION_HAT:
                values = {}
                for key, expr in stmt.extra.get('inputs', []):
                    values[key] = expr.to_python_source()
                for key, value in (stmt.extra.get('fields') or {}).items():
                    values.setdefault(key, repr(value))
                inputs = ', '.join(
                    f"{key!r}: (lambda: {source})"
                    for key, source in values.items())
                lines.append(
                    f"        self._register_extension_hat("
                    f"{stmt.extra.get('namespace', '')!r}, "
                    f"{stmt.extra.get('opcode', '')!r}, "
                    f"{{{inputs}}}, self.{name})")
                continue
            if stmt.type == BlockType.WHEN_GREATER_THAN:
                menu = str(stmt.extra.get('menu') or 'TIMER').lower()
                value = (stmt.value.to_python_source()
                         if stmt.value is not None else '10')
                lines.append(
                    f"        self._register_greater_than({menu!r}, lambda: {value}, "
                    f"self.{name})")
                continue
            lines.append(f"        self._register({event!r}, self.{name})")
        return lines

    # ===================== 语句 =====================

    def _generate_statement(self, stmt: Statement, indent: int) -> List[str]:
        spaces = "    " * indent

        if stmt.type == BlockType.MOVE_STEPS:
            value = stmt.value.to_python_source() if stmt.value else "10"
            return [f"{spaces}self.move({value})"]

        if stmt.type == BlockType.TURN_RIGHT:
            value = stmt.value.to_python_source() if stmt.value else "15"
            return [f"{spaces}self.turn_right({value})"]

        if stmt.type == BlockType.TURN_LEFT:
            value = stmt.value.to_python_source() if stmt.value else "15"
            return [f"{spaces}self.turn_left({value})"]

        if stmt.type == BlockType.GO_TO_XY:
            x = stmt.extra.get('x', Expr(ExprType.NUMBER, 0)).to_python_source()
            y = stmt.extra.get('y', Expr(ExprType.NUMBER, 0)).to_python_source()
            return [f"{spaces}self.goto_xy({x}, {y})"]

        if stmt.type == BlockType.GO_TO_RANDOM:
            target = stmt.extra.get('target', '_random_')
            return [f"{spaces}self.goto_target({target!r})"]

        if stmt.type == BlockType.GLIDE_TO:
            secs = stmt.value.to_python_source() if stmt.value else "1"
            target = stmt.extra.get('target', '_random_')
            return [f"{spaces}self.glide_to_target({secs}, {target!r})"]

        if stmt.type == BlockType.POINT_IN_DIRECTION:
            value = stmt.value.to_python_source() if stmt.value else "90"
            return [f"{spaces}self.point_in_direction({value})"]

        if stmt.type == BlockType.POINT_TOWARDS:
            target = stmt.extra.get('target', '_mouse_')
            return [f"{spaces}self.point_towards({target!r})"]

        if stmt.type == BlockType.SET_ROTATION_STYLE:
            style = stmt.extra.get('style', 'all around')
            return [f"{spaces}self.set_rotation_style({style!r})"]

        if stmt.type == BlockType.GLIDE_SECS_TO:
            secs = stmt.value.to_python_source() if stmt.value else "1"
            x = stmt.extra.get('x', Expr(ExprType.NUMBER, 0)).to_python_source()
            y = stmt.extra.get('y', Expr(ExprType.NUMBER, 0)).to_python_source()
            return [f"{spaces}self.glide_to({secs}, {x}, {y})"]

        if stmt.type == BlockType.SET_X:
            value = stmt.value.to_python_source() if stmt.value else "0"
            return [f"{spaces}self.set_x({value})"]

        if stmt.type == BlockType.SET_Y:
            value = stmt.value.to_python_source() if stmt.value else "0"
            return [f"{spaces}self.set_y({value})"]

        if stmt.type == BlockType.CHANGE_X:
            value = stmt.value.to_python_source() if stmt.value else "10"
            return [f"{spaces}self.change_x({value})"]

        if stmt.type == BlockType.CHANGE_Y:
            value = stmt.value.to_python_source() if stmt.value else "10"
            return [f"{spaces}self.change_y({value})"]

        if stmt.type == BlockType.IF_ON_EDGE_BOUNCE:
            return [f"{spaces}self.if_on_edge_bounce()"]

        if stmt.type == BlockType.SAY:
            value = stmt.value.to_python_source() if stmt.value else "''"
            return [f"{spaces}self.say({value})"]

        if stmt.type == BlockType.SAY_FOR_SECS:
            message = stmt.extra.get('message', Expr(ExprType.STRING, '')).to_python_source()
            secs = stmt.value.to_python_source() if stmt.value else "1"
            return [f"{spaces}self.say_for({message}, {secs})"]

        if stmt.type == BlockType.THINK:
            value = stmt.value.to_python_source() if stmt.value else "''"
            return [f"{spaces}self.think({value})"]

        if stmt.type == BlockType.THINK_FOR_SECS:
            message = stmt.extra.get('message', Expr(ExprType.STRING, '')).to_python_source()
            secs = stmt.value.to_python_source() if stmt.value else "1"
            return [f"{spaces}self.think_for({message}, {secs})"]

        if stmt.type == BlockType.SHOW:
            return [f"{spaces}self.show()"]

        if stmt.type == BlockType.HIDE:
            return [f"{spaces}self.hide()"]

        if stmt.type == BlockType.SWITCH_COSTUME:
            value = stmt.value.to_python_source() if stmt.value else "'costume1'"
            return [f"{spaces}self.switch_costume({value})"]

        if stmt.type == BlockType.NEXT_COSTUME:
            return [f"{spaces}self.next_costume()"]

        if stmt.type == BlockType.CHANGE_SIZE:
            value = stmt.value.to_python_source() if stmt.value else "10"
            return [f"{spaces}self.change_size({value})"]

        if stmt.type == BlockType.SET_SIZE:
            value = stmt.value.to_python_source() if stmt.value else "100"
            return [f"{spaces}self.set_size({value})"]

        if stmt.type == BlockType.CHANGE_EFFECT:
            effect = stmt.extra.get('effect', 'color')
            value = stmt.value.to_python_source() if stmt.value else "25"
            return [f"{spaces}self.change_effect({effect!r}, {value})"]

        if stmt.type == BlockType.SET_EFFECT:
            effect = stmt.extra.get('effect', 'color')
            value = stmt.value.to_python_source() if stmt.value else "100"
            return [f"{spaces}self.set_effect({effect!r}, {value})"]

        if stmt.type == BlockType.CLEAR_EFFECTS:
            return [f"{spaces}self.clear_effects()"]

        if stmt.type == BlockType.PLAY_SOUND:
            value = stmt.value.to_python_source() if stmt.value else "'sound1'"
            return [f"{spaces}self.play_sound({value})"]

        if stmt.type == BlockType.PLAY_SOUND_UNTIL_DONE:
            value = stmt.value.to_python_source() if stmt.value else "'sound1'"
            return [f"{spaces}self.play_sound({value}, wait=True)"]

        if stmt.type == BlockType.STOP_ALL_SOUNDS:
            return [f"{spaces}self.stop_all_sounds()"]

        if stmt.type == BlockType.CHANGE_VOLUME:
            value = stmt.value.to_python_source() if stmt.value else "10"
            return [f"{spaces}self.change_volume({value})"]

        if stmt.type == BlockType.SET_VOLUME:
            value = stmt.value.to_python_source() if stmt.value else "100"
            return [f"{spaces}self.set_volume({value})"]

        if stmt.type == BlockType.WAIT:
            value = stmt.value.to_python_source() if stmt.value else "1"
            return [f"{spaces}self.wait({value})"]

        if stmt.type == BlockType.REPEAT:
            times = stmt.value.to_python_source() if stmt.value else "10"
            lines = [f"{spaces}for _repeat in range(_sc_repeat_count({times})):"]
            body = self._emit_body(stmt.body, indent + 1)
            lines.extend(body if body else [f"{spaces}    pass"])
            lines.append(f"{spaces}    self._yield_frame()")
            return lines

        if stmt.type == BlockType.FOREVER:
            lines = [f"{spaces}while self._running:"]
            body = self._emit_body(stmt.body, indent + 1)
            lines.extend(body if body else [f"{spaces}    pass"])
            lines.append(f"{spaces}    self._yield_frame()")
            return lines

        if stmt.type == BlockType.IF:
            condition = stmt.condition.to_python_source() if stmt.condition else "True"
            lines = [f"{spaces}if _sc_bool({condition}):"]
            body = self._emit_body(stmt.body, indent + 1)
            lines.extend(body if body else [f"{spaces}    pass"])
            return lines

        if stmt.type == BlockType.IF_ELSE:
            condition = stmt.condition.to_python_source() if stmt.condition else "True"
            lines = [f"{spaces}if _sc_bool({condition}):"]
            body = self._emit_body(stmt.body, indent + 1)
            lines.extend(body if body else [f"{spaces}    pass"])
            lines.append(f"{spaces}else:")
            else_body = self._emit_body(stmt.else_body, indent + 1)
            lines.extend(else_body if else_body else [f"{spaces}    pass"])
            return lines

        if stmt.type == BlockType.WAIT_UNTIL:
            condition = stmt.condition.to_python_source() if stmt.condition else "True"
            return [f"{spaces}self.wait_until(lambda: _sc_bool({condition}))"]

        if stmt.type == BlockType.REPEAT_UNTIL:
            condition = stmt.condition.to_python_source() if stmt.condition else "False"
            lines = [f"{spaces}while not _sc_bool({condition}):"]
            body = self._emit_body(stmt.body, indent + 1)
            lines.extend(body if body else [f"{spaces}    pass"])
            lines.append(f"{spaces}    self._yield_frame()")
            return lines

        if stmt.type == BlockType.STOP:
            option = stmt.extra.get('option', 'all')
            return [f"{spaces}self.stop({option!r})"]

        if stmt.type == BlockType.CREATE_CLONE_OF:
            value = stmt.value.to_python_source() if stmt.value else "'_myself_'"
            return [f"{spaces}self.create_clone_of({value})"]

        if stmt.type == BlockType.DELETE_THIS_CLONE:
            return [f"{spaces}self.delete_this_clone()"]

        if stmt.type == BlockType.ASK_AND_WAIT:
            value = stmt.value.to_python_source() if stmt.value else "''"
            return [f"{spaces}self.ask_and_wait({value})"]

        if stmt.type == BlockType.RESET_TIMER:
            return [f"{spaces}self.reset_timer()"]

        if stmt.type == BlockType.SET_VARIABLE:
            name = sanitize_name(stmt.extra.get('name') or 'var', 'var')
            value = stmt.value.to_python_source() if stmt.value else "0"
            return [f"{spaces}self.{name} = {value}"]

        if stmt.type == BlockType.CHANGE_VARIABLE:
            name = sanitize_name(stmt.extra.get('name') or 'var', 'var')
            value = stmt.value.to_python_source() if stmt.value else "1"
            return [f"{spaces}self.{name} = _sc_add(self.{name}, {value})"]

        if stmt.type == BlockType.ADD_TO_LIST:
            name = sanitize_name(stmt.extra.get('name') or 'list', 'lst')
            item = stmt.value.to_python_source() if stmt.value else "''"
            return [f"{spaces}self.{name}.append({item})"]

        if stmt.type == BlockType.DELETE_FROM_LIST:
            name = sanitize_name(stmt.extra.get('name') or 'list', 'lst')
            index = stmt.value.to_python_source() if stmt.value else "1"
            return [f"{spaces}_sc_list_delete(self.{name}, {index})"]

        if stmt.type == BlockType.DELETE_ALL_FROM_LIST:
            name = sanitize_name(stmt.extra.get('name') or 'list', 'lst')
            return [f"{spaces}self.{name}.clear()"]

        if stmt.type == BlockType.INSERT_IN_LIST:
            name = sanitize_name(stmt.extra.get('name') or 'list', 'lst')
            item = stmt.extra.get('item', Expr(ExprType.STRING, '')).to_python_source()
            index = stmt.value.to_python_source() if stmt.value else "1"
            return [f"{spaces}_sc_list_insert(self.{name}, {index}, {item})"]

        if stmt.type == BlockType.REPLACE_IN_LIST:
            name = sanitize_name(stmt.extra.get('name') or 'list', 'lst')
            item = stmt.extra.get('item', Expr(ExprType.STRING, '')).to_python_source()
            index = stmt.value.to_python_source() if stmt.value else "1"
            return [f"{spaces}_sc_list_replace(self.{name}, {index}, {item})"]

        if stmt.type == BlockType.SHOW_VARIABLE:
            return [f"{spaces}self.show_variable({str(stmt.extra.get('name', 'var'))!r})"]

        if stmt.type == BlockType.HIDE_VARIABLE:
            return [f"{spaces}self.hide_variable({str(stmt.extra.get('name', 'var'))!r})"]

        if stmt.type == BlockType.SHOW_LIST:
            return [f"{spaces}self.show_list({str(stmt.extra.get('name', 'list'))!r})"]

        if stmt.type == BlockType.HIDE_LIST:
            return [f"{spaces}self.hide_list({str(stmt.extra.get('name', 'list'))!r})"]

        if stmt.type == BlockType.BROADCAST:
            value = stmt.value.to_python_source() if stmt.value else "''"
            return [f"{spaces}self.broadcast({value})"]

        if stmt.type == BlockType.BROADCAST_AND_WAIT:
            value = stmt.value.to_python_source() if stmt.value else "''"
            return [f"{spaces}self.broadcast_and_wait({value})"]

        if stmt.type == BlockType.PROCEDURE_CALL:
            name = self._procedure_name(stmt)
            call_args = stmt.extra.get('args', [])
            args_str = ", ".join(a.to_python_source() for a in call_args)
            return [f"{spaces}self.{name}({args_str})"]

        if stmt.type == BlockType.PROCEDURE_RETURN:
            if stmt.value is not None:
                return [f"{spaces}return {stmt.value.to_python_source()}"]
            return [f"{spaces}return"]

        if stmt.type == BlockType.EXTENSION:
            opcode = str(stmt.extra.get('opcode') or '')
            if opcode.lower().endswith('foreachthreadvariable'):
                # 临时变量扩展的循环块：把变量依次设为1..N，每次执行子栈
                input_map = dict(stmt.extra.get('inputs', []))
                variable = input_map.get(
                    'VAR', Expr(ExprType.STRING, 'variable')).to_python_source()
                count = input_map.get(
                    'NUM', Expr(ExprType.NUMBER, 10)).to_python_source()
                lines = [
                    f"{spaces}for _ext_temp_index in range("
                    f"max(0, int(_sc_num({count})))):",
                    f"{spaces}    self.extension("
                    f"{stmt.extra.get('namespace', '')!r}, "
                    f"'setThreadVariable', "
                    f"{{'VAR': {variable}, "
                    f"'STRING': _ext_temp_index + 1}}, {{}})",
                ]
                body = self._emit_body(stmt.body, indent + 1)
                lines.extend(body if body else [f"{spaces}    pass"])
                lines.append(f"{spaces}    self._yield_frame()")
                return lines
            inputs = ', '.join(
                f"{key!r}: {value.to_python_source()}"
                for key, value in stmt.extra.get('inputs', []))
            lines = [f"{spaces}self.extension("
                     f"{stmt.extra.get('namespace', '')!r}, "
                     f"{stmt.extra.get('opcode', '')!r}, "
                     f"{{{inputs}}}, {stmt.extra.get('fields', {})!r})"]
            lines.extend(self._emit_body(stmt.body, indent))
            return lines

        if stmt.type == BlockType.COMMENT:
            return [f"{spaces}# {stmt.extra.get('text', '')}"]

        if stmt.type == BlockType.SWITCH_BACKDROP:
            value = stmt.value.to_python_source() if stmt.value else "'backdrop1'"
            return [f"{spaces}self.set_backdrop({value})"]

        if stmt.type == BlockType.SWITCH_BACKDROP_AND_WAIT:
            value = stmt.value.to_python_source() if stmt.value else "'backdrop1'"
            return [f"{spaces}self.set_backdrop_and_wait({value})"]

        if stmt.type == BlockType.NEXT_BACKDROP:
            return [f"{spaces}self.next_backdrop()"]

        if stmt.type in (BlockType.GO_TO_FRONT, BlockType.GO_TO_BACK):
            where = stmt.extra.get('where', 'front')
            return [f"{spaces}self.go_to_layer({where!r})"]

        if stmt.type in (BlockType.GO_FORWARD_LAYERS, BlockType.GO_BACKWARD_LAYERS):
            direction = stmt.extra.get('direction', 'forward')
            value = stmt.value.to_python_source() if stmt.value else "1"
            sign = "-" if str(direction).lower().startswith('back') else ""
            return [f"{spaces}self.change_layer({sign}_sc_num({value}))"]

        if stmt.type == BlockType.SET_DRAG_MODE:
            mode = stmt.extra.get('mode', 'draggable')
            return [f"{spaces}self.set_drag_mode({mode!r})"]

        if stmt.type in (BlockType.SET_SOUND_EFFECT,
                         BlockType.CHANGE_SOUND_EFFECT):
            effect = stmt.extra.get('effect', 'PITCH')
            value = stmt.value.to_python_source() if stmt.value else "10"
            method = ('set_sound_effect' if stmt.type == BlockType.SET_SOUND_EFFECT
                      else 'change_sound_effect')
            return [f"{spaces}self.{method}({effect!r}, {value})"]

        if stmt.type == BlockType.CLEAR_SOUND_EFFECTS:
            return [f"{spaces}self.clear_sound_effects()"]

        if stmt.type == BlockType.FOR_EACH:
            name = sanitize_name(stmt.extra.get('name') or 'item', 'var')
            items = stmt.value.to_python_source() if stmt.value else "[]"
            lines = [f"{spaces}for _each in _sc_list_values({items}):",
                     f"{spaces}    self.{name} = _each"]
            body = self._emit_body(stmt.body, indent + 1)
            lines.extend(body if body else [f"{spaces}    pass"])
            lines.append(f"{spaces}    self._yield_frame()")
            return lines

        if stmt.type == BlockType.ALL_AT_ONCE:
            return self._emit_body(stmt.body, indent)

        if stmt.type == BlockType.INCR_COUNTER:
            return [f"{spaces}self.incr_counter()"]

        if stmt.type == BlockType.CLEAR_COUNTER:
            return [f"{spaces}self.clear_counter()"]

        return [f"{spaces}# TODO: {stmt.type.name}"]

    # ===================== main =====================

    def _generate_main(self, project: ProjectIR) -> List[str]:
        """生成主函数：启动pygame运行时，支持多种调试参数"""
        lines = []
        lines.append("def main(argv=None):")
        lines.append('    """启动Scratch 3.0 pygame运行时"""')
        lines.append("    parser = argparse.ArgumentParser(description='Scratch 3.0 runtime')")
        lines.append("    parser.add_argument('--headless', action='store_true', help='无窗口模式')")
        lines.append("    parser.add_argument('--frames', type=int, help='运行指定帧数后退出')")
        lines.append("    parser.add_argument('--seconds', type=float, help='运行指定秒数后退出')")
        lines.append("    parser.add_argument('--fps', type=int, help='覆盖帧率')")
        lines.append("    parser.add_argument('--seed', type=int, help='随机种子')")
        lines.append("    parser.add_argument('--trace', action='store_true', help='打印事件/脚本/过程调用')")
        lines.append("    parser.add_argument('--no-audio', action='store_true', help='禁用声音')")
        lines.append("    parser.add_argument('--assets', help='覆盖素材目录')")
        lines.append("    parser.add_argument('--interpolation', action='store_true', help='TurboWarp插值')")
        lines.append("    parser.add_argument('--turbo', action='store_true', help='Turbo模式')")
        lines.append("    parser.add_argument('--no-fencing', dest='fencing', action='store_false', help='移除舞台边界限制')")
        lines.append("    parser.add_argument('--infinite-clones', action='store_true', help='解除克隆体数量限制')")
        lines.append("    parser.add_argument('--remove-misc-limits', dest='misc_limits', action='store_false', help='移除杂项限制')")
        lines.append("    parser.add_argument('--stage-size', help='自定义舞台尺寸，如 640x360')")
        lines.append("    parser.add_argument('--hq-pen', action='store_true', help='高质量画笔')")
        lines.append("    parser.add_argument('--warp-timer', type=float, default=0.5, help='warp模式超时秒数')")
        lines.append("    parser.add_argument('--disable-compiler', action='store_true', help='兼容参数（无操作）')")
        lines.append("    parser.add_argument('--windowed', action='store_true', help='以普通窗口启动（默认自动最大化）')")
        # TurboWarp把高级选项保存在 project.json 的 _twconfig_ 注释里
        options = project.runtime_options or {}
        runtime_options = options.get('runtimeOptions') or {}

        def tw_value(name, default=None):
            if name in options:
                return options[name]
            return runtime_options.get(name, default)

        framerate = tw_value('framerate', tw_value('fps'))
        if framerate:
            lines.append(f"    parser.set_defaults(fps={int(float(framerate))})")
        if tw_value('fencing', True) is False:
            lines.append("    parser.set_defaults(fencing=False)")
        if tw_value('miscLimits', True) is False:
            lines.append("    parser.set_defaults(misc_limits=False)")
        if tw_value('interpolation', False):
            lines.append("    parser.set_defaults(interpolation=True)")
        if tw_value('turbo', False):
            lines.append("    parser.set_defaults(turbo=True)")
        if tw_value('hqPen', False) or tw_value('hq', False):
            lines.append("    parser.set_defaults(hq_pen=True)")
        if tw_value('compiler', True) is False:
            lines.append("    parser.set_defaults(disable_compiler=True)")
        clone_limit = tw_value('cloneLimit')
        if clone_limit is None:
            clone_limit = tw_value('maxClones')
        if clone_limit is not None:
            try:
                if clone_limit == float('inf') or int(clone_limit) <= 0:
                    lines.append("    parser.set_defaults(infinite_clones=True)")
            except (TypeError, ValueError, OverflowError):
                pass
        warp_timer = tw_value('warpTimer')
        if warp_timer is not None:
            lines.append(f"    parser.set_defaults(warp_timer={float(warp_timer)!r})")
        stage_width = tw_value('stageWidth') or tw_value('width')
        stage_height = tw_value('stageHeight') or tw_value('height')
        if stage_width:
            try:
                width = int(float(stage_width))
                if stage_height:
                    height = int(float(stage_height))
                else:
                    # TurboWarp 只保存改动过的字段；高度未给出时保持默认 360
                    height = 360
                lines.append(
                    f"    parser.set_defaults(stage_size='{width}x{height}')")
            except (TypeError, ValueError):
                pass
        lines.append("    args = parser.parse_args(argv)")
        lines.append("    if args.seed is not None:")
        lines.append("        random.seed(args.seed)")
        lines.append("    stage_size = None")
        lines.append("    if args.stage_size:")
        lines.append("        try:")
        lines.append("            width, height = args.stage_size.lower().split('x')")
        lines.append("            stage_size = (int(width), int(height))")
        lines.append("        except ValueError:")
        lines.append("            parser.error('--stage-size 格式应为 WIDTHxHEIGHT')")
        lines.append("    runtime = ScratchRuntime(")
        lines.append("        headless=args.headless, fps=args.fps, trace=args.trace,")
        lines.append("        audio=not args.no_audio, assets_dir=args.assets,")
        lines.append("        interpolation=args.interpolation, turbo=args.turbo,")
        lines.append("        fencing=args.fencing, infinite_clones=args.infinite_clones,")
        lines.append("        misc_limits=args.misc_limits, hq_pen=args.hq_pen,")
        lines.append("        stage_size=stage_size, warp_timer=args.warp_timer,")
        lines.append("        disable_compiler=args.disable_compiler,")
        lines.append("        maximize=not args.windowed)")
        lines.append("")

        # 实例名必须避开类名和 main() 里的局部变量名。
        # 中文/无大小写的角色名（如“角色1”）lower() 后与类名相同，
        # 直接写 `角色1 = 角色1()` 会触发 UnboundLocalError。
        reserved_names = {'parser', 'args', 'runtime', 'stage_size',
                          'width', 'height'}
        class_names = {sanitize_name(item.name, "Sprite")
                       for item in project.sprites}
        used_instances = set()
        for sprite in project.sprites:
            safe_class = sanitize_name(sprite.name, "Sprite")
            instance = sanitize_name(sprite.name.lower(), "inst")
            if instance == safe_class or instance in class_names \
                    or instance in reserved_names:
                instance = f'inst_{instance}'
            while instance in used_instances or instance in class_names \
                    or instance in reserved_names:
                instance = f'{instance}_'
            used_instances.add(instance)
            lines.append(f"    {instance} = {safe_class}()")
            lines.append(f"    runtime.add_sprite({instance})")

        lines.append("")
        lines.append("    try:")
        lines.append("        runtime.start(max_frames=args.frames, max_seconds=args.seconds)")
        lines.append("    except KeyboardInterrupt:")
        lines.append("        pass")
        lines.append("    finally:")
        lines.append("        runtime.shutdown()")
        lines.append("")
        lines.append("")
        lines.append('if __name__ == "__main__":')
        lines.append("    main()")
        return lines


def generate_python(project: ProjectIR) -> str:
    """便捷函数：生成Python代码"""
    gen = PythonGenerator()
    return gen.generate_project(project)


def generate_modules(project: ProjectIR, prefix: str = 'scratch'):
    """便捷函数：生成模块化多文件（入口代码, {附加文件名: 代码}）"""
    gen = PythonGenerator()
    return gen.generate_modules(project, prefix)


def save_python(project: ProjectIR, file_path: str):
    """将Python代码保存到文件"""
    code = generate_python(project)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(code)
