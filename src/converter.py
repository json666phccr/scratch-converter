#!/usr/bin/env python3
"""
Scratch 3.0 <-> 高级语言 双向转换器

支持：
1. Scratch (.sb3) -> Python (.py)
2. Python (.py) -> Scratch (.sb3)
3. Scratch JSON -> IR -> Python
4. Python -> IR -> Scratch JSON

用法:
    python converter.py scratch2py input.sb3 output.py
    python converter.py py2scratch input.py output.sb3
    python converter.py demo
"""

import json
import sys
import os
import zipfile
import tempfile
from typing import Optional

from ir import ProjectIR, SpriteIR
from scratch_parser import load_scratch_file, parse_scratch_project
from scratch_writer import write_scratch_project, save_scratch_file
from python_generator import generate_python, save_python, generate_modules
from python_parser import (parse_python_code, parse_python_file,
                           python_to_project, PythonParser)
from general_python import parse_general_project
from convert_log import LOG

__version__ = "0.13.0"


def _count_statements(project: ProjectIR) -> int:
    """统计 IR 中的语句总数（含嵌套子栈），用于日志中的中间状态"""
    total = 0
    stack = []
    for sprite in project.sprites:
        stack.extend(sprite.statements)
    while stack:
        stmt = stack.pop()
        total += 1
        stack.extend(stmt.body)
        stack.extend(stmt.else_body)
        if stmt.next is not None:
            stack.append(stmt.next)
    return total


def _log_project(project: ProjectIR):
    """输出项目 IR 的摘要，便于定位转换中间状态"""
    LOG.debug('精灵: %d 个（舞台: %s）'
              % (len(project.sprites),
                 project.stage.name if project.stage else '无'))
    LOG.debug('语句: %d 条，转换告警: %d 种，监视器: %d 个'
              % (_count_statements(project), len(project.warnings),
                 len(project.monitors)))
    if project.extensions:
        LOG.debug('扩展: %s' % ', '.join(sorted(project.extensions)))
    for sprite in project.sprites:
        LOG.debug('  - %s: 变量 %d，列表 %d，顶层脚本 %d'
                  % (sprite.name, len(sprite.variables), len(sprite.lists),
                     len(sprite.statements)))



class ScratchConverter:
    """Scratch 3.0 双向转换器"""

    def scratch_to_python(self, sb3_path: str, py_path: Optional[str] = None,
                          split: bool = False, bundle: bool = False) -> str:
        """
        将Scratch项目(.sb3)转换为Python代码

        Args:
            sb3_path: .sb3文件路径
            py_path: 输出.py文件路径(可选)
            split: 是否生成模块化多文件（入口 + 运行时 + 每个角色一个模块）
            bundle: 是否生成独立项目文件夹（<项目名>/<项目名>.py + assets），
                    避免同一目录下多个项目的素材互相覆盖

        Returns:
            生成的Python代码字符串（split 时为入口文件内容）
        """
        print(f"[Scratch -> Python] 正在转换: {sb3_path}")
        LOG.debug('输入文件: %s' % os.path.abspath(sb3_path))

        output_path = py_path
        project_dir = None
        if py_path and bundle:
            project_dir, output_path = self._bundle_paths(py_path)

        # 1. 读取sb3文件（ZIP格式）
        with LOG.stage('读取项目'):
            project_data = self._read_sb3(sb3_path)
        LOG.debug('project.json: targets=%d, monitors=%d, extensions=%d'
                  % (len(project_data.get('targets') or []),
                     len(project_data.get('monitors') or []),
                     len(project_data.get('extensions') or [])))

        # 2. 解析为IR
        with LOG.stage('解析为 IR'):
            ir = parse_scratch_project(project_data)
            _log_project(ir)
        print(f"  解析完成: {len(ir.sprites)} 个精灵")
        if ir.warnings:
            print("  [转换报告] 暂未支持的积木:")
            for opcode, count in sorted(ir.warnings.items()):
                print(f"    {opcode} x{count}")
        if ir.runtime_options:
            print(f"  TurboWarp高级选项: {ir.runtime_options}")

        # 3. 生成Python代码
        with LOG.stage('生成 Python'):
            if split:
                stem = (os.path.splitext(os.path.basename(output_path))[0]
                        if output_path else 'scratch')
                python_code, extra_files = generate_modules(ir, stem)
                LOG.debug('模块: %s'
                          % ', '.join(sorted(extra_files)))
            else:
                python_code = generate_python(ir)
        LOG.debug('生成代码: %d 行' % len(python_code.splitlines()))

        # 4. 保存到文件
        if output_path:
            if project_dir:
                os.makedirs(project_dir, exist_ok=True)
            with LOG.stage('写入输出'):
                if split:
                    base_dir = os.path.dirname(os.path.abspath(output_path))
                    for name, code in extra_files.items():
                        with open(os.path.join(base_dir, name), 'w',
                                  encoding='utf-8') as f:
                            f.write(code)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(python_code)
            print(f"  Python代码已保存: {output_path}")
            if project_dir:
                print(f"  项目文件夹: {project_dir}")
            if split:
                print(f"  模块化输出: 另生成 {len(extra_files)} 个模块文件（运行时 + 角色）")
            # 提取造型/声音资源，供pygame运行时加载
            with LOG.stage('导出素材'):
                self._extract_assets(sb3_path, output_path)

        total_lines = len(python_code.splitlines())
        if split:
            total_lines += sum(len(code.splitlines()) for code in extra_files.values())
        print(f"[转换完成] Python代码共 {total_lines} 行")
        if not split and total_lines > 3000:
            print("  [提示] 代码较长，可使用 --split 生成模块化多文件，便于阅读和调试")
        return python_code

    @staticmethod
    def _bundle_paths(py_path: str):
        """返回 (项目文件夹, 入口脚本路径)

        例如 out/game.py -> out/game/game.py；
        如果输出已经在 out/game/game.py，则沿用该文件夹，避免重复嵌套。
        """
        parent = os.path.dirname(os.path.abspath(py_path))
        stem = os.path.splitext(os.path.basename(py_path))[0] or 'scratch'
        if os.path.basename(parent) == stem:
            project_dir = parent
        else:
            project_dir = os.path.join(parent, stem)
        return project_dir, os.path.join(project_dir, stem + '.py')

    @staticmethod
    def _parse_dsl_project(code: str):
        """DSL 模式：解析文件中所有 ScratchSprite 子类，保留多精灵项目"""
        import ast as _ast
        class_names = []
        try:
            tree = _ast.parse(code)
            for node in tree.body:
                if isinstance(node, _ast.ClassDef) and any(
                        isinstance(base, _ast.Name) and base.id == 'ScratchSprite'
                        for base in node.bases):
                    class_names.append(node.name)
        except SyntaxError:
            class_names = []

        project = ProjectIR()
        if not class_names:
            project.add_sprite(parse_python_code(code, 'Sprite'))
            return project
        for name in class_names:
            parser = PythonParser()
            sprite = parser.parse_code(code, name)
            if name == 'Stage':
                sprite.is_stage = True
                sprite.variables.pop('is_stage', None)
                # 舞台全局变量/列表只在模块级 GLOBALS 中出现，
                # 这里把它们补回舞台，角色侧只保留引用关系。
                for global_name, global_value in sprite.global_values.items():
                    if isinstance(global_value, list):
                        sprite.lists.setdefault(
                            global_name, list(global_value))
                    else:
                        sprite.variables.setdefault(
                            global_name, global_value)
            project.add_sprite(sprite)
        return project

    @staticmethod
    def _detect_python_mode(code: str) -> str:
        """判断输入是转换器DSL还是普通Python脚本"""
        markers = ('ScratchSprite', '@_as_procedure', 'when_green_flag',
                   'when_clicked', 'when_clone_starts', 'def when_')
        if any(marker in code for marker in markers):
            return 'dsl'
        return 'general'

    def python_to_scratch(self, py_path: str, sb3_path: Optional[str] = None,
                          mode: str = 'auto') -> dict:
        """
        将Python代码转换为Scratch项目

        Args:
            py_path: .py文件路径
            sb3_path: 输出.sb3文件路径(可选)
            mode: 'auto' | 'dsl' | 'general'
                - dsl: 本转换器生成的Scratch DSL（默认自动识别，准确率最高）
                - general: 通用Python脚本（支持常见语法，复杂特性会记录到转换报告）

        Returns:
            Scratch项目JSON字典
        """
        print(f"[Python -> Scratch] 正在转换: {py_path}")
        LOG.debug('输入文件: %s' % os.path.abspath(py_path))

        with LOG.stage('读取 Python'):
            with open(py_path, 'r', encoding='utf-8') as f:
                code = f.read()
        if mode == 'auto':
            mode = self._detect_python_mode(code)
        if mode not in ('dsl', 'general'):
            raise ValueError(f"未知转换模式: {mode}")
        LOG.debug('输入 %d 行，模式: %s' % (len(code.splitlines()), mode))

        # 1. 解析Python代码为IR
        with LOG.stage('解析 Python'):
            if mode == 'general':
                sprite_name = os.path.splitext(os.path.basename(py_path))[0] or 'Python'
                project = parse_general_project(code, sprite_name)
                print(f"  解析模式: 通用Python（实验性）")
            else:
                project = self._parse_dsl_project(code)
                print(f"  解析模式: Scratch DSL")
            _log_project(project)
        sprite = next((item for item in project.sprites if not item.is_stage),
                      project.sprites[0])
        print(f"  解析完成: 精灵 '{sprite.name}'")
        if project.warnings:
            summary = ', '.join(f"{name}×{count}"
                                for name, count in project.warnings.items())
            print(f"  转换报告（以下特性未完整支持）: {summary}")

        # 2. 转换为Scratch JSON
        with LOG.stage('生成 Scratch 项目'):
            scratch_json = write_scratch_project(project)
        LOG.debug('targets=%d, blocks=%d'
                  % (len(scratch_json.get('targets') or []),
                     sum(len(target.get('blocks') or {})
                         for target in scratch_json.get('targets') or [])))

        # 3. 保存到文件
        if sb3_path:
            with LOG.stage('写入 sb3'):
                self._write_sb3(scratch_json, sb3_path, project.assets)
            print(f"  Scratch项目已保存: {sb3_path}")

        print(f"[转换完成] Scratch项目（{mode} 模式）")
        return scratch_json

    def scratch_json_to_python(self, json_data: dict) -> str:
        """从Scratch JSON字典生成Python代码"""
        ir = parse_scratch_project(json_data)
        return generate_python(ir)

    def python_code_to_scratch_json(self, code: str, sprite_name: str = "Sprite",
                                    mode: str = 'auto') -> dict:
        """从Python代码字符串生成Scratch JSON"""
        if mode == 'auto':
            mode = self._detect_python_mode(code)
        if mode == 'general':
            project = parse_general_project(code, sprite_name)
        else:
            project = self._parse_dsl_project(code)
        return write_scratch_project(project)

    def roundtrip_scratch(self, sb3_path: str, output_sb3_path: str) -> dict:
        """
        Scratch -> Python -> Scratch 往返转换
        用于验证转换的保真度
        """
        print(f"[往返测试] {sb3_path}")

        # 读取原始项目
        original_data = self._read_sb3(sb3_path)
        original_ir = parse_scratch_project(original_data)

        # 生成Python
        python_code = generate_python(original_ir)

        # 从Python恢复IR
        restored_sprites = []
        for sprite in original_ir.sprites:
            if sprite.is_stage:
                continue
            restored = parse_python_code(python_code, sprite.name)
            restored_sprites.append(restored)

        # 创建恢复的项目（舞台不参与Python生成，但必须原样保留）
        restored_project = ProjectIR()
        if original_ir.stage is not None:
            restored_project.add_sprite(original_ir.stage)
        for s in restored_sprites:
            restored_project.add_sprite(s)

        # 转换回Scratch JSON
        restored_json = write_scratch_project(restored_project)

        # 保存
        if output_sb3_path:
            self._write_sb3(restored_json, output_sb3_path)
            print(f"  往返转换完成: {output_sb3_path}")

        return restored_json

    def roundtrip_python(self, py_path: str, output_py_path: str):
        """
        Python -> Scratch -> Python 往返转换
        用于验证转换的保真度
        """
        print(f"[往返测试] {py_path}")

        # 解析原始Python
        sprite = parse_python_file(py_path)

        # 转换为Scratch JSON
        project = python_to_project(sprite)
        scratch_json = write_scratch_project(project)

        # 从Scratch JSON恢复IR
        restored_ir = parse_scratch_project(scratch_json)

        # 生成Python
        restored_python = generate_python(restored_ir)

        # 保存
        if output_py_path:
            with open(output_py_path, 'w', encoding='utf-8') as f:
                f.write(restored_python)
            print(f"  往返转换完成: {output_py_path}")

        return restored_python

    def _extract_assets(self, sb3_path: str, py_path: str):
        """把.sb3里的造型/声音资源解压到Python脚本旁的assets目录"""
        if not sb3_path.lower().endswith('.sb3'):
            return
        try:
            assets_dir = os.path.join(os.path.dirname(os.path.abspath(py_path)), 'assets')
            os.makedirs(assets_dir, exist_ok=True)
            with zipfile.ZipFile(sb3_path, 'r') as zf:
                for name in zf.namelist():
                    if name.endswith('/') or name == 'project.json':
                        continue
                    filename = os.path.basename(name)
                    if not filename:
                        continue
                    with open(os.path.join(assets_dir, filename), 'wb') as f:
                        f.write(zf.read(name))
            print(f"  资源已导出到: {assets_dir}")
        except (OSError, zipfile.BadZipFile) as error:
            print(f"  [警告] 资源提取失败: {error}")

    def _read_sb3(self, sb3_path: str) -> dict:
        """读取.sb3文件（ZIP格式，内含project.json）"""
        if sb3_path.endswith('.json'):
            with open(sb3_path, 'r', encoding='utf-8') as f:
                return json.load(f)

        with zipfile.ZipFile(sb3_path, 'r') as zf:
            if 'project.json' in zf.namelist():
                with zf.open('project.json') as f:
                    return json.load(f)
            else:
                # 尝试找任何.json文件
                for name in zf.namelist():
                    if name.endswith('.json'):
                        with zf.open(name) as f:
                            return json.load(f)
                raise ValueError(f"在 {sb3_path} 中找不到 project.json")

    def _write_sb3(self, scratch_json: dict, sb3_path: str, assets=None):
        """写入.sb3文件（JSON 输出无法携带资源，仅写 project.json）"""
        if sb3_path.endswith('.json'):
            with open(sb3_path, 'w', encoding='utf-8') as f:
                json.dump(scratch_json, f, indent=2, ensure_ascii=False)
            if assets:
                print("  [提示] .json 输出不包含造型资源，请改用 .sb3")
            return

        with zipfile.ZipFile(sb3_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('project.json', json.dumps(scratch_json, ensure_ascii=False))
            for name, data in (assets or {}).items():
                zf.writestr(name, data)


def _extract_log_args(args):
    """从命令行参数中提取日志选项，返回 (剩余参数, 级别, 日志文件)"""
    level = None
    log_file = None
    rest = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in ('--log-level', '--log-file', '--log') and index + 1 < len(args):
            if arg == '--log-level':
                level = args[index + 1]
            else:
                log_file = args[index + 1]
            index += 2
            continue
        if arg.startswith('--log-level='):
            level = arg.split('=', 1)[1]
        elif arg.startswith('--log-file=') or arg.startswith('--log='):
            log_file = arg.split('=', 1)[1]
        elif arg in ('-v', '--verbose'):
            level = 'debug'
        elif arg == '--quiet':
            level = 'quiet'
        else:
            rest.append(arg)
        index += 1
    return rest, level, log_file


def main():
    """命令行入口"""
    converter = ScratchConverter()
    args, log_level, log_file = _extract_log_args(sys.argv[1:])
    try:
        LOG.configure(level=log_level, path=log_file,
                      timestamps=bool(log_file))
    except ValueError as error:
        print(error)
        sys.exit(1)

    try:
        _dispatch(converter, args)
    except KeyboardInterrupt:
        raise
    except Exception as error:
        LOG.exception(error, '转换失败: %s: %s'
                      % (type(error).__name__, error))
        if not LOG.debug_enabled:
            LOG.error('可加 -v 查看完整调用栈')
        sys.exit(2)
    finally:
        LOG.close()


def _dispatch(converter, args):
    """按子命令执行转换"""
    if not args:
        print("Scratch 3.0 <-> Python 双向转换器")
        print()
        print("用法:")
        print("  python converter.py scratch2py <input.sb3> [output.py] [--split] [--no-bundle]")
        print("  python converter.py py2scratch <input.py> [output.sb3] [--mode dsl|general|auto]")
        print("  python converter.py scpy2scratch <工程目录> [output.sb3]")
        print("  python converter.py sb3obf <input.sb3> [output.py] [--no-embed-assets] [--no-fold] [--seed N]")
        print("  python converter.py roundtrip-sb3 <input.sb3> [output.sb3]")
        print("  python converter.py roundtrip-py <input.py> [output.py]")
        print("  python converter.py demo")
        print()
        print("日志选项（可放在任意位置）:")
        print("  -v, --verbose        输出详细转换日志")
        print("  --quiet              只输出错误")
        print("  --log-level LEVEL    debug/info/warning/error/quiet")
        print("  --log-file FILE      把日志写入文件（含时间戳）")
        sys.exit(1)

    command = args[0]

    if command == 'scratch2py':
        args = args[1:]
        split = '--split' in args
        bundle = '--no-bundle' not in args
        args = [item for item in args
                if item not in ('--split', '--bundle', '--no-bundle')]
        if not args:
            print("用法: python converter.py scratch2py <input.sb3> [output.py] "
                  "[--split] [--no-bundle]")
            sys.exit(1)
        input_path = args[0]
        output_path = args[1] if len(args) > 1 else input_path.replace('.sb3', '.py').replace('.json', '.py')
        converter.scratch_to_python(input_path, output_path, split=split,
                                    bundle=bundle)

    elif command == 'py2scratch':
        args = args[1:]
        mode = 'auto'
        if '--mode' in args:
            index = args.index('--mode')
            mode = args[index + 1] if index + 1 < len(args) else 'auto'
            del args[index:index + 2]
        if not args:
            print("用法: python converter.py py2scratch <input.py> [output.sb3] "
                  "[--mode dsl|general|auto]")
            sys.exit(1)
        input_path = args[0]
        output_path = args[1] if len(args) > 1 else input_path.replace('.py', '.sb3')
        converter.python_to_scratch(input_path, output_path, mode)

    elif command == 'scpy2scratch':
        args = args[1:]
        if not args:
            print("用法: python converter.py scpy2scratch <工程目录> [output.sb3]")
            sys.exit(1)
        from scpython import export_project
        folder = args[0]
        output_path = args[1] if len(args) > 1 else (
            os.path.abspath(folder.rstrip('\\/')) + '.sb3')
        path = export_project(folder, output_path)
        print(f"  ScPython 工程已导出: {path}")

    elif command == 'sb3obf':
        args = args[1:]
        embed_assets = '--no-embed-assets' not in args
        fold = '--no-fold' not in args
        seed = None
        if '--seed' in args:
            index = args.index('--seed')
            if index + 1 < len(args):
                seed = int(args[index + 1])
                del args[index:index + 2]
        args = [item for item in args if item not in (
            '--no-embed-assets', '--no-fold')]
        if not args:
            print("用法: python converter.py sb3obf <input.sb3> [output.py] "
                  "[--no-embed-assets] [--no-fold] [--seed N]")
            sys.exit(1)
        from obfuscator import obfuscate_sb3
        result = obfuscate_sb3(
            args[0], args[1] if len(args) > 1 else None,
            embed_assets=embed_assets, fold=fold, seed=seed)
        print(f"  混淆 Python 已生成: {result.output}")
        print(f"  大小: {result.size} 字节；资产 {result.asset_count} 个")

    elif command == 'roundtrip-sb3':
        if len(args) < 2:
            print("用法: python converter.py roundtrip-sb3 <input.sb3> [output.sb3]")
            sys.exit(1)
        input_path = args[1]
        output_path = args[2] if len(args) > 2 else input_path.replace('.sb3', '_roundtrip.sb3')
        converter.roundtrip_scratch(input_path, output_path)

    elif command == 'roundtrip-py':
        if len(args) < 2:
            print("用法: python converter.py roundtrip-py <input.py> [output.py]")
            sys.exit(1)
        input_path = args[1]
        output_path = args[2] if len(args) > 2 else input_path.replace('.py', '_roundtrip.py')
        converter.roundtrip_python(input_path, output_path)

    elif command == 'demo':
        run_demo(converter)

    else:
        print(f"未知命令: {command}")
        sys.exit(1)


def run_demo(converter: ScratchConverter):
    """运行演示"""
    print("=" * 60)
    print("Scratch 3.0 <-> Python 双向转换器 演示")
    print("=" * 60)

    # 创建一个示例Scratch项目
    scratch_json = {
        "targets": [
            {
                "isStage": True,
                "name": "Stage",
                "variables": {},
                "lists": {},
                "broadcasts": {},
                "blocks": {},
                "comments": {},
                "currentCostume": 0,
                "costumes": [{"name": "backdrop1", "dataFormat": "svg", "assetId": "", "md5ext": ""}],
                "sounds": [],
                "volume": 100,
                "layerOrder": 0,
                "tempo": 60,
                "videoTransparency": 50,
                "videoState": "on",
                "textToSpeechLanguage": None
            },
            {
                "isStage": False,
                "name": "Cat",
                "variables": {"var_counter": ["counter", 0]},
                "lists": {"list_items": ["items", ["apple", "banana", "cherry"]]},
                "broadcasts": {},
                "blocks": {
                    "block1": {
                        "opcode": "event_whenflagclicked",
                        "next": "block2",
                        "parent": None,
                        "inputs": {},
                        "fields": {},
                        "shadow": False,
                        "topLevel": True,
                        "x": 100,
                        "y": 100
                    },
                    "block2": {
                        "opcode": "data_setvariableto",
                        "next": "block3",
                        "parent": "block1",
                        "inputs": {"VALUE": [1, "0"]},
                        "fields": {"VARIABLE": ["counter", "var_counter"]},
                        "shadow": False,
                        "topLevel": False
                    },
                    "block3": {
                        "opcode": "control_repeat",
                        "next": "block6",
                        "parent": "block2",
                        "inputs": {
                            "TIMES": [1, "5"],
                            "SUBSTACK": [2, "block4"]
                        },
                        "fields": {},
                        "shadow": False,
                        "topLevel": False
                    },
                    "block4": {
                        "opcode": "data_changevariableby",
                        "next": "block5",
                        "parent": "block3",
                        "inputs": {"VALUE": [1, "1"]},
                        "fields": {"VARIABLE": ["counter", "var_counter"]},
                        "shadow": False,
                        "topLevel": False
                    },
                    "block5": {
                        "opcode": "looks_say",
                        "next": None,
                        "parent": "block4",
                        "inputs": {"MESSAGE": [1, ["10", "Hello!"]]},
                        "fields": {},
                        "shadow": False,
                        "topLevel": False
                    },
                    "block6": {
                        "opcode": "motion_movesteps",
                        "next": None,
                        "parent": "block3",
                        "inputs": {"STEPS": [1, "10"]},
                        "fields": {},
                        "shadow": False,
                        "topLevel": False
                    }
                },
                "comments": {},
                "currentCostume": 0,
                "costumes": [{"name": "costume1", "dataFormat": "svg", "assetId": "", "md5ext": ""}],
                "sounds": [],
                "visible": True,
                "x": 0,
                "y": 0,
                "size": 100,
                "direction": 90,
                "draggable": False,
                "rotationStyle": "all around",
                "volume": 100,
                "layerOrder": 1
            }
        ],
        "monitors": [],
        "extensions": [],
        "meta": {
            "semver": "3.0.0",
            "vm": "0.2.0",
            "agent": ""
        }
    }

    # 1. Scratch -> Python
    print("\n[1] Scratch -> Python")
    print("-" * 40)
    ir = parse_scratch_project(scratch_json)
    python_code = generate_python(ir)
    print(python_code)

    # 2. Python -> Scratch
    print("\n[2] Python -> Scratch")
    print("-" * 40)
    restored_json = converter.python_code_to_scratch_json(python_code, "Cat")
    print(json.dumps(restored_json, indent=2, ensure_ascii=False)[:2000] + "...")

    # 3. 从恢复的JSON再生成Python
    print("\n[3] 恢复的 JSON -> Python")
    print("-" * 40)
    ir2 = parse_scratch_project(restored_json)
    python_code2 = generate_python(ir2)
    print(python_code2)

    print("\n" + "=" * 60)
    print("演示完成!")
    print("=" * 60)


if __name__ == '__main__':
    main()
