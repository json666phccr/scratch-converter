# -*- coding: utf-8 -*-
"""ScPython：Python 风格、Scratch 语义的 .scpy 语言。

工程目录示例::

    my_project/
    ├── stage.scpy          # 舞台
    ├── Cat.scpy            # 角色（文件名即角色名）
    ├── macros.scpy         # 可选宏函数
    ├── extensions.json     # 可选自定义扩展声明
    └── assets/
        ├── cat.svg
        └── meow.wav

导出::

    python -m scpython export my_project -o game.sb3
"""

from __future__ import annotations

import os
from typing import Optional

from ir import ProjectIR

from .compiler import (
    FunctionInfo, ModuleAnalyzer, ModuleInfo, ProjectCompiler, analyze_macros,
    validate_sb3_json,
)
from .errors import ScPythonError, ScPythonSyntaxError
from .importer import import_sb3
from .lint import LintIssue, lint_project

__version__ = "0.2.0"

__all__ = [
    "export_project",
    "check_project",
    "import_sb3",
    "lint_project",
    "LintIssue",
    "ProjectCompiler",
    "validate_sb3_json",
    "ModuleAnalyzer",
    "analyze_macros",
    "ModuleInfo",
    "FunctionInfo",
    "ScPythonError",
    "ScPythonSyntaxError",
    "__version__",
]


def _default_output(folder: str) -> str:
    folder = os.path.abspath(folder)
    name = os.path.basename(folder.rstrip('\\/')) or 'project'
    return os.path.join(os.path.dirname(folder), name + '.sb3')


def export_project(folder: str, output: Optional[str] = None,
                   verbose: bool = False) -> str:
    """把 ScPython 工程目录导出为 .sb3（或 .json）"""
    output = output or _default_output(folder)
    compiler = ProjectCompiler(folder, verbose=verbose)
    return compiler.export(output)


def check_project(folder: str, verbose: bool = False) -> ProjectIR:
    """只编译不导出，用于语法检查"""
    compiler = ProjectCompiler(folder, verbose=verbose)
    return compiler.compile()


def sb3_to_scpython(input_path: str, output_folder: str,
                    split_macros: bool = True) -> str:
    """把 .sb3 / project.json 转成 ScPython 工程目录。"""
    return import_sb3(input_path, output_folder, split_macros=split_macros)
