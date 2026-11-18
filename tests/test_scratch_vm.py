# -*- coding: utf-8 -*-
"""Scratch VM（src/scratch_vm）测试：加载、解释执行、调试器。"""

import json
import os
import sys
import tempfile
import threading
import time
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import *  # noqa: F401,F403

from scratch_vm import load_project, build_module
from scratch_vm.debugger import DebugController
from scratch_vm.interpreter import VMInterpreter


# ===================== 构造工具 =====================

def vm_project(blocks, variables=None, lists=None, stage_vars=None,
               stage_lists=None, name="Sprite1"):
    """构造带舞台与一个角色的最小项目"""
    stage = {
        "isStage": True,
        "name": "Stage",
        "variables": stage_vars or {},
        "lists": stage_lists or {},
        "broadcasts": {},
        "blocks": {},
        "comments": {},
        "currentCostume": 0,
        "costumes": [],
        "sounds": [],
        "volume": 100,
        "layerOrder": 0,
        "tempo": 60,
        "videoTransparency": 50,
        "videoState": "on",
        "textToSpeechLanguage": None,
    }
    sprite = {
        "isStage": False,
        "name": name,
        "variables": variables or {},
        "lists": lists or {},
        "broadcasts": {},
        "blocks": blocks,
        "comments": {},
        "currentCostume": 0,
        "costumes": [],
        "sounds": [],
        "volume": 100,
        "layerOrder": 1,
        "x": 0,
        "y": 0,
        "direction": 90,
        "visible": True,
        "size": 100,
        "draggable": False,
        "rotationStyle": "all around",
    }
    return {
        "targets": [stage, sprite],
        "monitors": [],
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "0.2.0", "agent": "test"},
    }


def build_vm(project_json, assets_dir=None, debug=True):
    """返回 (runtime, interpreter, controller, sprites)"""
    folder = assets_dir or tempfile.mkdtemp(prefix="vm_test_")
    project = parse_scratch_project(project_json)
    module = build_module(project, folder)
    runtime = module.create_runtime(headless=True, audio=False, maximize=False)
    interpreter = VMInterpreter(project, module, runtime, debug=None)
    controller = DebugController(interpreter, runtime, project)
    controller.interactive = bool(debug)
    interpreter.debug = controller
    sprites = module.create_sprites(runtime)
    return runtime, interpreter, controller, sprites


def run_vm(runtime, controller, frames=30, settle=0.2):
    """运行若干帧，再给脚本线程一点收尾时间"""
    try:
        runtime.start(max_frames=frames)
        time.sleep(settle)
    finally:
        controller.shutdown()
        runtime.shutdown()


def find_sprite(sprites, name):
    return next(sprite for sprite in sprites if getattr(sprite, "name", "") == name)


# ===================== 测试 =====================

def test_vm_loader_json_and_sb3():
    """VM-1 loader：json / sb3 读取与资源解压"""
    print("[测试89] VM loader")

    project_json = vm_project({
        "hat": block("event_whenflagclicked", None, None, top_level=True),
    })
    with tempfile.TemporaryDirectory() as folder:
        json_path = os.path.join(folder, "demo.json")
        with open(json_path, "w", encoding="utf-8") as handle:
            json.dump(project_json, handle, ensure_ascii=False)

        with load_project(json_path) as loaded:
            assert loaded.name == "demo"
            assert loaded.temp_dir is None
            assert len(loaded.project.sprites) == 2
            assert loaded.assets_dir == os.path.abspath(folder)

        sb3_path = os.path.join(folder, "demo.sb3")
        with zipfile.ZipFile(sb3_path, "w") as archive:
            archive.writestr("project.json", json.dumps(project_json))
            archive.writestr("asset.svg", b"<svg/>")
        loaded = load_project(sb3_path)
        try:
            assert loaded.temp_dir is not None
            assert os.path.exists(os.path.join(loaded.assets_dir, "asset.svg"))
        finally:
            temp_dir = loaded.temp_dir
            loaded.close()
            assert not os.path.exists(temp_dir)

    print("  [PASS] VM loader 通过")
    return True


def test_vm_green_flag_loop_and_global():
    """VM-2 绿旗、循环、全局变量与本地变量"""
    print("[测试90] VM 绿旗与循环")

    blocks = {
        "hat": block("event_whenflagclicked", "set", None, top_level=True),
        "set": block("data_setvariableto", "repeat", "hat",
                     {"VALUE": [1, [4, "0"]]},
                     {"VARIABLE": ["计数", "v1"]}),
        "repeat": block("control_repeat", "say", "set",
                        {"TIMES": [1, [4, "5"]], "SUBSTACK": [2, "add"]}),
        "add": block("data_changevariableby", None, "repeat",
                     {"VALUE": [1, [4, "2"]]},
                     {"VARIABLE": ["全局", "g1"]}),
        "say": block("looks_say", None, "repeat",
                     {"MESSAGE": [1, [10, "done"]]}),
    }
    project_json = vm_project(
        blocks,
        variables={"v1": ["计数", 99]},
        stage_vars={"g1": ["全局", 0]},
    )
    runtime, interpreter, controller, sprites = build_vm(project_json)
    try:
        run_vm(runtime, controller, frames=20)
        sprite = find_sprite(sprites, "Sprite1")
        stage = find_sprite(sprites, "Stage")
        assert sprite.计数 == 0
        assert stage.全局 == 10, stage.全局
        assert sprite._say_text == "done"
    finally:
        if runtime.running:
            runtime.shutdown()

    print("  [PASS] VM 绿旗与循环通过")
    return True


def test_vm_procedure_recursion():
    """VM-3 自制积木：参数、递归、if 与 warp"""
    print("[测试91] VM 自制积木递归")

    blocks = {
        "hat": block("event_whenflagclicked", "call", None, top_level=True),
        "call": block(
            "procedures_call", None, "hat",
            {"arg1": [1, [4, "5"]]},
            mutation={
                "tagName": "mutation",
                "children": [],
                "proccode": "countdown %s",
                "argumentids": json.dumps(["arg1"]),
                "warp": "false",
            }),
        "def": block("procedures_definition", "ifblock", None,
                     {"custom_block": [1, "proto"]}, top_level=True),
        "proto": block(
            "procedures_prototype", None, "def",
            {"arg1": [1, [4, ""]]},
            mutation={
                "tagName": "mutation",
                "children": [],
                "proccode": "countdown %s",
                "argumentids": json.dumps(["arg1"]),
                "argumentnames": json.dumps(["n"]),
                "argumentdefaults": json.dumps([""]),
                "warp": "true",
            }),
        "ifblock": block("control_if", None, "def",
                         {"CONDITION": [2, "gt"], "SUBSTACK": [2, "add"]}),
        "gt": block("operator_gt", None, "ifblock", {
            "OPERAND1": [3, "arg", [4, "0"]],
            "OPERAND2": [1, [4, "0"]],
        }),
        "arg": block("argument_reporter_string_number", None, "gt", {},
                     {"VALUE": ["n", None]}),
        "add": block("data_changevariableby", "recursive", "ifblock",
                     {"VALUE": [3, "arg2", [4, "0"]]},
                     {"VARIABLE": ["结果", "v1"]}),
        "arg2": block("argument_reporter_string_number", None, "add", {},
                      {"VALUE": ["n", None]}),
        "recursive": block(
            "procedures_call", None, "add",
            {"arg1": [3, "sub", [4, ""]]},
            mutation={
                "tagName": "mutation",
                "children": [],
                "proccode": "countdown %s",
                "argumentids": json.dumps(["arg1"]),
                "warp": "false",
            }),
        "sub": block("operator_subtract", None, "recursive", {
            "NUM1": [3, "arg3", [4, "0"]],
            "NUM2": [1, [4, "1"]],
        }),
        "arg3": block("argument_reporter_string_number", None, "sub", {},
                      {"VALUE": ["n", None]}),
    }
    project_json = vm_project(
        blocks, variables={"v1": ["结果", 0]}, name="Recur")
    runtime, interpreter, controller, sprites = build_vm(project_json)
    try:
        run_vm(runtime, controller, frames=30)
        sprite = find_sprite(sprites, "Recur")
        assert sprite.结果 == 15, sprite.结果
    finally:
        if runtime.running:
            runtime.shutdown()

    print("  [PASS] VM 自制积木递归通过")
    return True


def test_vm_broadcast_and_clone():
    """VM-4 广播、广播等待、克隆与删除克隆体"""
    print("[测试92] VM 广播与克隆")

    blocks = {
        # 绿旗：广播并等待；克隆自己
        "hat": block("event_whenflagclicked", "bcast", None, top_level=True),
        "bcast": block("event_broadcastandwait", "clone", "hat", {},
                       {"BROADCAST_OPTION": ["go", None]}),
        "clone": block("control_create_clone_of", None, "bcast", {},
                       {"CLONE_OPTION": ["_myself_", None]}),
        # 接收广播：全局 +1
        "recv": block("event_whenbroadcastreceived", "inc", None,
                      fields={"BROADCAST_OPTION": ["go", "bc1"]},
                      top_level=True),
        "inc": block("data_changevariableby", None, "recv",
                     {"VALUE": [1, [4, "1"]]},
                     {"VARIABLE": ["全局", "g1"]}),
        # 克隆体启动：全局 +10，然后删除自己
        "clone_hat": block("control_start_as_clone", "inc10", None,
                           top_level=True),
        "inc10": block("data_changevariableby", "del", "clone_hat",
                       {"VALUE": [1, [4, "10"]]},
                       {"VARIABLE": ["全局", "g1"]}),
        "del": block("control_delete_this_clone", None, "inc10"),
    }
    project_json = vm_project(
        blocks, stage_vars={"g1": ["全局", 0]}, name="Clone")
    runtime, interpreter, controller, sprites = build_vm(project_json)
    try:
        run_vm(runtime, controller, frames=40, settle=0.3)
        stage = find_sprite(sprites, "Stage")
        assert stage.全局 == 11, stage.全局
        clones = [sprite for sprite in runtime.sprites
                  if getattr(sprite, "_is_clone", False)]
        assert not clones, "克隆体应在执行 delete this clone 后被删除"
    finally:
        if runtime.running:
            runtime.shutdown()

    print("  [PASS] VM 广播与克隆通过")
    return True


def test_vm_debugger_breakpoint_step_trace():
    """VM-5 调试器：断点、单步、trace、变量与统计"""
    print("[测试93] VM 调试器")

    blocks = {
        "hat": block("event_whenflagclicked", "set", None, top_level=True),
        "set": block("data_changevariableby", "after", "hat",
                     {"VALUE": [1, [4, "1"]]},
                     {"VARIABLE": ["分数", "v1"]}),
        "after": block("data_setvariableto", None, "set",
                       {"VALUE": [1, [4, "2"]]},
                       {"VARIABLE": ["标记", "v2"]}),
    }
    project_json = vm_project(
        blocks, variables={"v1": ["分数", 0], "v2": ["标记", 0]},
        name="Debug")
    runtime, interpreter, controller, sprites = build_vm(project_json)
    controller.interactive = True
    controller.add_breakpoint("opcode", "data_changevariableby")

    thread = threading.Thread(
        target=lambda: runtime.start(max_frames=300), daemon=True)
    sprite = find_sprite(sprites, "Debug")
    try:
        thread.start()
        deadline = time.time() + 5.0
        while time.time() < deadline and not controller.paused:
            time.sleep(0.01)
        assert controller.paused, "断点未命中"
        assert controller.last_stmt is not None
        assert controller.last_stmt.extra.get("opcode") == "data_changevariableby"
        assert sprite.分数 == 0, "断点应在语句执行前暂停"

        assert controller.recent_trace(5), "trace 不应为空"
        report = controller.stats_report()
        assert report["total_steps"] >= 1
        entries = controller.dump_variables("Debug")
        assert entries and entries[0]["variables"]["分数"] == 0

        controller.step_block()
        time.sleep(0.1)
        assert sprite.分数 == 1, "单步应执行当前积木"

        controller.resume()
        deadline = time.time() + 5.0
        while time.time() < deadline and sprite.标记 != 2:
            time.sleep(0.01)
        assert sprite.标记 == 2, "继续运行后应执行后续积木"
        assert controller.errors == controller.errors  # 仅确认可访问
    finally:
        controller.shutdown()
        runtime.running = False
        runtime.stop_all_scripts()
        thread.join(timeout=3.0)
        runtime.shutdown()

    print("  [PASS] VM 调试器通过")
    return True


def test_vm_overlay_headless():
    """VM-6 可视化面板在 headless 下禁用且不报错"""
    print("[测试94] VM overlay headless")

    from scratch_vm.overlay import DebugOverlay

    blocks = {
        "hat": block("event_whenflagclicked", None, None, top_level=True),
    }
    project_json = vm_project(blocks)
    runtime, interpreter, controller, sprites = build_vm(project_json)
    try:
        overlay = DebugOverlay(runtime, controller, enabled=True)
        assert overlay.enabled is False
        assert overlay.toggle() is False
        text = overlay.draw_once()
        assert "[VM]" in text
    finally:
        controller.shutdown()
        runtime.shutdown()

    print("  [PASS] VM overlay headless 通过")
    return True


TESTS = [
    test_vm_loader_json_and_sb3,
    test_vm_green_flag_loop_and_global,
    test_vm_procedure_recursion,
    test_vm_broadcast_and_clone,
    test_vm_debugger_breakpoint_step_trace,
    test_vm_overlay_headless,
]
