# -*- coding: utf-8 -*-
"""SB3 项目加载器。

负责把 .sb3 / .zip / .json 变成：

- ``project_json``：原始字典（调试器读取 block id / opcode 用）
- ``project``：``ProjectIR``（解释器执行用）
- ``assets_dir``：造型/声音所在目录（.sb3 会解压到临时目录）

用法::

    with load_project("game.sb3") as loaded:
        ...
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from typing import Optional

from ir import ProjectIR
from scratch_parser import parse_scratch_project


class LoadError(Exception):
    """项目加载失败（带文件路径与原因）"""

    def __init__(self, path: str, message: str):
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message}")


@dataclass
class LoadedProject:
    """加载后的项目及其资源目录"""

    path: str
    project_json: dict
    project: ProjectIR
    assets_dir: str
    temp_dir: Optional[str] = None

    @property
    def name(self) -> str:
        """项目名：文件名去掉扩展名"""
        return os.path.splitext(os.path.basename(self.path))[0]

    def close(self) -> None:
        """清理临时解压目录"""
        if self.temp_dir and os.path.isdir(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.temp_dir = None

    def __enter__(self) -> "LoadedProject":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()


def _read_json_file(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except OSError as error:
        raise LoadError(path, f"无法读取文件: {error}") from error
    except ValueError as error:
        raise LoadError(path, f"JSON 解析失败: {error}") from error
    if not isinstance(data, dict):
        raise LoadError(path, "project.json 顶层必须是对象")
    return data


def _read_zip(path: str):
    """从 ZIP 中读取 project.json，并返回 (数据, zip 对象)"""
    try:
        archive = zipfile.ZipFile(path, "r")
    except (OSError, zipfile.BadZipFile) as error:
        raise LoadError(path, f"不是有效的 sb3/zip 文件: {error}") from error

    names = archive.namelist()
    candidate = None
    if "project.json" in names:
        candidate = "project.json"
    else:
        for name in names:
            if name.lower().endswith(".json") and not name.endswith("/"):
                candidate = name
                break
    if candidate is None:
        archive.close()
        raise LoadError(path, "压缩包中找不到 project.json")

    try:
        with archive.open(candidate) as handle:
            data = json.load(handle)
    except (OSError, ValueError) as error:
        archive.close()
        raise LoadError(path, f"读取 {candidate} 失败: {error}") from error
    if not isinstance(data, dict):
        archive.close()
        raise LoadError(path, f"{candidate} 顶层必须是对象")
    return data, archive


def _extract_assets(archive: zipfile.ZipFile, target_dir: str) -> None:
    """解压所有非 project.json 资源；只取 basename，拒绝路径穿越"""
    os.makedirs(target_dir, exist_ok=True)
    for info in archive.infolist():
        if info.is_dir():
            continue
        name = os.path.basename(info.filename)
        if not name or name == "project.json":
            continue
        # basename 已去掉目录；再防御一次纯 ".." 之类的名字
        if name in (".", ".."):
            continue
        destination = os.path.join(target_dir, name)
        try:
            with archive.open(info) as source, open(destination, "wb") as output:
                shutil.copyfileobj(source, output)
        except (OSError, RuntimeError) as error:
            raise LoadError(
                info.filename, f"解压资源失败: {error}") from error


def load_project(path: str, extract_assets: bool = True) -> LoadedProject:
    """读取 .sb3/.zip/.json 项目。

    Args:
        path: 项目文件路径
        extract_assets: 是否解压 .sb3 内的资源（测试可关闭以加速）

    Raises:
        LoadError: 文件不存在、格式错误、缺少 project.json 等
    """
    if not os.path.isfile(path):
        raise LoadError(path, "文件不存在")

    lower = path.lower()
    if lower.endswith(".json"):
        data = _read_json_file(path)
        assets_dir = os.path.dirname(os.path.abspath(path))
        temp_dir = None
    else:
        data, archive = _read_zip(path)
        temp_dir = None
        assets_dir = os.path.dirname(os.path.abspath(path))
        try:
            if extract_assets:
                temp_dir = tempfile.mkdtemp(prefix="scratch_vm_")
                _extract_assets(archive, temp_dir)
                assets_dir = temp_dir
        finally:
            archive.close()

    targets = data.get("targets")
    if not isinstance(targets, list) or not targets:
        raise LoadError(path, "project.json 缺少 targets 或为空")

    try:
        project = parse_scratch_project(data)
    except Exception as error:  # 解析器内部错误统一转成 LoadError
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise LoadError(path, f"解析项目失败: {error}") from error

    return LoadedProject(
        path=os.path.abspath(path),
        project_json=data,
        project=project,
        assets_dir=assets_dir,
        temp_dir=temp_dir,
    )
