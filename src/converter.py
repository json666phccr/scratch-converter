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
from python_generator import generate_python, save_python
from python_parser import parse_python_code, parse_python_file, python_to_project

__version__ = "0.4.3"


class ScratchConverter:
    """Scratch 3.0 双向转换器"""

    def scratch_to_python(self, sb3_path: str, py_path: Optional[str] = None) -> str:
        """
        将Scratch项目(.sb3)转换为Python代码

        Args:
            sb3_path: .sb3文件路径
            py_path: 输出.py文件路径(可选)

        Returns:
            生成的Python代码字符串
        """
        print(f"[Scratch -> Python] 正在转换: {sb3_path}")

        # 1. 读取sb3文件（ZIP格式）
        project_data = self._read_sb3(sb3_path)

        # 2. 解析为IR
        ir = parse_scratch_project(project_data)
        print(f"  解析完成: {len(ir.sprites)} 个精灵")
        if ir.warnings:
            print("  [转换报告] 暂未支持的积木:")
            for opcode, count in sorted(ir.warnings.items()):
                print(f"    {opcode} x{count}")
        if ir.runtime_options:
            print(f"  TurboWarp高级选项: {ir.runtime_options}")

        # 3. 生成Python代码
        python_code = generate_python(ir)

        # 4. 保存到文件
        if py_path:
            with open(py_path, 'w', encoding='utf-8') as f:
                f.write(python_code)
            print(f"  Python代码已保存: {py_path}")
            # 提取造型/声音资源，供pygame运行时加载
            self._extract_assets(sb3_path, py_path)

        print(f"[转换完成] Python代码共 {len(python_code.splitlines())} 行")
        return python_code

    def python_to_scratch(self, py_path: str, sb3_path: Optional[str] = None) -> dict:
        """
        将Python代码转换为Scratch项目

        Args:
            py_path: .py文件路径
            sb3_path: 输出.sb3文件路径(可选)

        Returns:
            Scratch项目JSON字典
        """
        print(f"[Python -> Scratch] 正在转换: {py_path}")

        # 1. 解析Python代码为IR
        sprite = parse_python_file(py_path)
        project = python_to_project(sprite)
        print(f"  解析完成: 精灵 '{sprite.name}'")

        # 2. 转换为Scratch JSON
        scratch_json = write_scratch_project(project)

        # 3. 保存到文件
        if sb3_path:
            self._write_sb3(scratch_json, sb3_path)
            print(f"  Scratch项目已保存: {sb3_path}")

        print(f"[转换完成] Scratch项目")
        return scratch_json

    def scratch_json_to_python(self, json_data: dict) -> str:
        """从Scratch JSON字典生成Python代码"""
        ir = parse_scratch_project(json_data)
        return generate_python(ir)

    def python_code_to_scratch_json(self, code: str, sprite_name: str = "Sprite") -> dict:
        """从Python代码字符串生成Scratch JSON"""
        sprite = parse_python_code(code, sprite_name)
        project = python_to_project(sprite)
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

    def _write_sb3(self, scratch_json: dict, sb3_path: str):
        """写入.sb3文件"""
        if sb3_path.endswith('.json'):
            with open(sb3_path, 'w', encoding='utf-8') as f:
                json.dump(scratch_json, f, indent=2, ensure_ascii=False)
            return

        with zipfile.ZipFile(sb3_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('project.json', json.dumps(scratch_json, ensure_ascii=False))


def main():
    """命令行入口"""
    converter = ScratchConverter()

    if len(sys.argv) < 2:
        print("Scratch 3.0 <-> Python 双向转换器")
        print()
        print("用法:")
        print("  python converter.py scratch2py <input.sb3> [output.py]")
        print("  python converter.py py2scratch <input.py> [output.sb3]")
        print("  python converter.py roundtrip-sb3 <input.sb3> [output.sb3]")
        print("  python converter.py roundtrip-py <input.py> [output.py]")
        print("  python converter.py demo")
        sys.exit(1)

    command = sys.argv[1]

    if command == 'scratch2py':
        if len(sys.argv) < 3:
            print("用法: python converter.py scratch2py <input.sb3> [output.py]")
            sys.exit(1)
        input_path = sys.argv[2]
        output_path = sys.argv[3] if len(sys.argv) > 3 else input_path.replace('.sb3', '.py').replace('.json', '.py')
        converter.scratch_to_python(input_path, output_path)

    elif command == 'py2scratch':
        if len(sys.argv) < 3:
            print("用法: python converter.py py2scratch <input.py> [output.sb3]")
            sys.exit(1)
        input_path = sys.argv[2]
        output_path = sys.argv[3] if len(sys.argv) > 3 else input_path.replace('.py', '.sb3')
        converter.python_to_scratch(input_path, output_path)

    elif command == 'roundtrip-sb3':
        if len(sys.argv) < 3:
            print("用法: python converter.py roundtrip-sb3 <input.sb3> [output.sb3]")
            sys.exit(1)
        input_path = sys.argv[2]
        output_path = sys.argv[3] if len(sys.argv) > 3 else input_path.replace('.sb3', '_roundtrip.sb3')
        converter.roundtrip_scratch(input_path, output_path)

    elif command == 'roundtrip-py':
        if len(sys.argv) < 3:
            print("用法: python converter.py roundtrip-py <input.py> [output.py]")
            sys.exit(1)
        input_path = sys.argv[2]
        output_path = sys.argv[3] if len(sys.argv) > 3 else input_path.replace('.py', '_roundtrip.py')
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
