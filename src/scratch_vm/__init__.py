# -*- coding: utf-8 -*-
"""Scratch VM：读取 sb3、解释执行、命令行与可视化调试。

基本用法::

    from scratch_vm import run_project
    result = run_project("game.sb3", headless=True, max_frames=60)
    print(result["variables"])

命令行::

    python -m scratch_vm game.sb3 --debug
"""

from __future__ import annotations

from typing import Optional

from .debugger import DebugController
from .interpreter import VMInterpreter
from .loader import LoadedProject, LoadError, load_project
from .module import RuntimeModule, build_module

__version__ = "0.14.2"

__all__ = [
    "run_project",
    "load_project",
    "build_module",
    "VMInterpreter",
    "DebugController",
    "LoadedProject",
    "LoadError",
    "RuntimeModule",
    "__version__",
]


def run_project(path: str,
                headless: bool = True,
                max_frames: Optional[int] = None,
                max_seconds: Optional[float] = None,
                debug: bool = False,
                overlay: bool = False,
                **options) -> dict:
    """加载并运行项目，返回运行快照。

    Args:
        path: .sb3/.zip/.json
        headless: 无窗口模式
        max_frames: 运行帧数上限
        max_seconds: 运行秒数上限
        debug: 是否启用交互调试（断点命中时暂停）
        overlay: 是否启用窗口内调试面板（headless 下自动关闭）
        **options: 透传给 ``ScratchRuntime`` 的选项

    Returns:
        ``{"frames", "elapsed", "stats", "variables", "errors"}``
    """
    with load_project(path) as loaded:
        module = build_module(loaded.project, loaded.assets_dir)
        runtime = module.create_runtime(
            headless=headless, assets_dir=loaded.assets_dir, **options)
        interpreter = VMInterpreter(
            loaded.project, module, runtime, debug=None)
        controller = DebugController(
            interpreter, runtime, loaded.project, trace_size=2000)
        controller.interactive = bool(debug)
        interpreter.debug = controller

        if overlay and not headless:
            from .overlay import DebugOverlay
            DebugOverlay(runtime, controller, enabled=True)

        module.create_sprites(runtime)
        try:
            runtime.start(max_frames=max_frames, max_seconds=max_seconds)
        finally:
            controller.shutdown()
            runtime.shutdown()
        return {
            "frames": runtime.frame,
            "elapsed": runtime.elapsed(),
            "stats": controller.stats_report(),
            "variables": controller.dump_variables(),
            "errors": list(controller.errors),
        }
