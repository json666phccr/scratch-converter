# -*- coding: utf-8 -*-
"""由 test_all.py 拆分出的测试模块"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import *


def test_turbowarp_warp_procedure_fidelity():
    """TurboWarp自制积木：proccode/argumentids/argumentdefaults/warp 全保真"""
    print("[测试25] TurboWarp warp自制积木保真")

    mutation = {
        "tagName": "mutation",
        "children": [],
        "proccode": "spin %n %b",
        "argumentids": json.dumps(["arg_n", "arg_b"]),
        "argumentnames": json.dumps(["n", "flag"]),
        "argumentdefaults": json.dumps(["7", "false"]),
        "warp": "true",
    }
    blocks = {
        "d1": block("procedures_definition", "d2", None, top_level=True),
        "p1": block("procedures_prototype", None, "d1", {}, mutation=mutation),
        "d2": block("motion_changexby", "d3", "d1",
                    {"DX": [3, "a1", [4, "1"]]}),
        "a1": block("argument_reporter_string_number", None, "d2", {},
                    {"VALUE": ["n", None]}),
        "d3": block("control_repeat", None, "d2",
                    {"TIMES": [1, [4, "2"]], "SUBSTACK": [2, "f1"]}),
        "f1": block("motion_changeyby", None, "d3",
                    {"DY": [3, "a2", [4, "1"]]}),
        "a2": block("argument_reporter_boolean", None, "f1", {},
                    {"VALUE": ["flag", None]}),
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("procedures_call", None, "b1",
                    {"arg_n": [1, [4, "3"]], "arg_b": [1, [10, "true"]]},
                    mutation=dict(mutation, proccode="spin %n %b")),
    }
    # 让definition的custom_block指向prototype
    blocks["d1"]["inputs"]["custom_block"] = [1, "p1"]

    project = make_project(blocks, name="WarpSprite")
    ir = parse_scratch_project(project)
    sprite = ir.sprites[0]
    definition = next(s for s in sprite.statements
                      if s.type == BlockType.PROCEDURE_DEFINE)
    assert definition.extra.get('warp') is True, "warp应按原文保留"
    assert definition.extra.get('proccode') == "spin %n %b"
    assert definition.extra.get('argumentids') == ["arg_n", "arg_b"]
    assert definition.extra.get('argumentdefaults') == ["7", "false"], \
        "argumentdefaults 应按Scratch原文保留字符串"
    assert definition.extra.get('arg_types') == ['n', 'b']

    code = generate_python(ir)
    assert "@_as_procedure(warp=True" in code, "warp参数应传给过程装饰器"
    assert "proccode='spin %n %b'" in code

    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    sprite_obj = namespace["WarpSprite"]()
    sprite_obj._runtime = None
    sprite_obj.spin(3, True)
    assert abs(sprite_obj.x - 3) < 1e-6, "warp过程应正常执行参数"

    written = write_scratch_project(parse_scratch_project(project))
    prototypes = [b for b in written["targets"][1]["blocks"].values()
                  if b.get("opcode") == "procedures_prototype"]
    assert prototypes, "应写回procedures_prototype"
    written_mutation = prototypes[0]["mutation"]
    assert written_mutation["proccode"] == "spin %n %b"
    assert json.loads(written_mutation["argumentids"]) == ["arg_n", "arg_b"]
    assert json.loads(written_mutation["argumentdefaults"]) == ["7", "false"]
    assert written_mutation["warp"] == "true"

    print("  [PASS] TurboWarp warp自制积木保真通过")
    return True


def test_turbowarp_custom_reporter():
    """TurboWarp自定义reporter：procedures_return + 表达式调用"""
    print("[测试26] TurboWarp自定义reporter")

    mutation = {
        "tagName": "mutation",
        "children": [],
        "proccode": "double %n",
        "argumentids": json.dumps(["arg_n"]),
        "argumentnames": json.dumps(["n"]),
        "argumentdefaults": json.dumps(["0"]),
        "warp": "false",
    }
    blocks = {
        "d1": block("procedures_definition", "d2", None, top_level=True),
        "p1": block("procedures_prototype", None, "d1", {}, mutation=mutation),
        "d2": block("procedures_return", None, "d1",
                    {"VALUE": [3, "sum", [4, "0"]]}),
        "sum": block("operator_add", None, "d2",
                     {"NUM1": [3, "a1", [4, "0"]], "NUM2": [3, "a1", [4, "0"]]}),
        "a1": block("argument_reporter_string_number", None, "sum", {},
                    {"VALUE": ["n", None]}),
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("looks_say", None, "b1",
                    {"MESSAGE": [3, "c1", [10, ""]]}),
        "c1": block("procedures_call", None, "b2",
                    {"arg_n": [1, [4, "21"]]},
                    mutation=dict(mutation)),
    }
    blocks["d1"]["inputs"]["custom_block"] = [1, "p1"]

    project = make_project(blocks, name="ReporterSprite")
    ir = parse_scratch_project(project)
    code = generate_python(ir)
    assert "self.double(" in code, "reporter调用应生成Python表达式"

    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](headless=True)
    sprite = namespace["ReporterSprite"]()
    runtime.add_sprite(sprite)
    try:
        assert sprite.double(21) == 42
        assert "_ProcedureReturn" in code
    finally:
        runtime.shutdown()

    # 反向：procedures_return 应写回
    written = write_scratch_project(parse_scratch_project(project))
    opcodes = [b.get("opcode") for b in written["targets"][1]["blocks"].values()]
    assert "procedures_return" in opcodes

    print("  [PASS] TurboWarp自定义reporter通过")
    return True


def test_turbowarp_pen_extension_runtime():
    """TurboWarp画笔扩展：转换后能真正在画布上画线"""
    print("[测试27] TurboWarp画笔扩展")

    blocks = {
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("pen_clear", "b3", "b1"),
        "b3": block("pen_setPenColorToColor", "b4", "b2",
                    {"COLOR": [1, [9, "#ff0000"]]}),
        "b4": block("pen_penDown", "b5", "b3"),
        "b5": block("control_repeat", "b6", "b4",
                    {"TIMES": [1, [4, "10"]], "SUBSTACK": [2, "r1"]}),
        "r1": block("motion_movesteps", None, "b5", {"STEPS": [1, [4, "10"]]}),
        "b6": block("pen_penUp", None, "b5"),
    }
    project = make_project(blocks, name="PenSprite")
    project["extensions"] = ["pen"]

    code = generate_python(parse_scratch_project(project))
    assert "pen_clear" in code and "pen_setPenColorToColor" in code

    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](headless=True)
    sprite = namespace["PenSprite"]()
    runtime.add_sprite(sprite)
    try:
        sprite.run()
        runtime.green_flag()
        import time
        for _ in range(40):
            runtime.step()
            time.sleep(0.004)
        y = runtime.stage_height // 2
        drawn = [runtime.pen_layer.get_at((runtime.stage_width // 2 + offset, y))
                 for offset in range(5, 100, 5)]
        drawn = [pixel for pixel in drawn if pixel.a > 0]
        assert drawn, "画笔应在画布上留下轨迹"
        assert drawn[0].r > 200 and drawn[0].g < 80, "画笔颜色应为红色"
    finally:
        runtime.running = False
        runtime.shutdown()

    print("  [PASS] TurboWarp画笔扩展通过")
    return True


def test_turbowarp_runtime_options_extension():
    """TurboWarp运行时选项扩展：帧率/插值/除雾/舞台尺寸/克隆限制"""
    print("[测试28] TurboWarp运行时选项扩展")

    project = make_project({
        "b1": block("event_whenflagclicked", None, None, top_level=True),
    }, name="OptionsSprite")
    project["extensions"] = ["runtimeoptions", "pen"]
    code = generate_python(parse_scratch_project(project))
    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)

    runtime = namespace["ScratchRuntime"](headless=True)
    sprite = namespace["OptionsSprite"]()
    runtime.add_sprite(sprite)
    try:
        sprite.extension('runtimeoptions', 'runtimeoptions_setFramerate',
                         {'VALUE': 60}, {})
        assert runtime.fps == 60

        sprite.extension('runtimeoptions', 'runtimeoptions_setInterpolation',
                         {'VALUE': 'on'}, {})
        assert runtime.interpolation is True

        sprite.extension('runtimeoptions', 'runtimeoptions_setTurboMode',
                         {'VALUE': 'off'}, {})
        assert runtime.turbo is False

        sprite.extension('runtimeoptions', 'runtimeoptions_setFencing',
                         {'VALUE': 'off'}, {})
        assert runtime.fencing is False

        sprite.extension('runtimeoptions', 'runtimeoptions_setCloneLimit',
                         {'VALUE': 500}, {})
        assert runtime.clone_limit == 500

        sprite.extension('runtimeoptions', 'runtimeoptions_setStageSize',
                         {'WIDTH': 640, 'HEIGHT': 360}, {})
        assert (runtime.stage_width, runtime.stage_height) == (640, 360)
        assert runtime.pen_layer.get_width() == 640

        sprite.extension('pen', 'pen_setPenColorToColor',
                         {'COLOR': '#00ff00'}, {})
        assert sprite._pen_hsv[1] > 99 and sprite._pen_hsv[2] > 99
        sprite.extension('pen', 'pen_setPenColorParamTo',
                         {'COLOR_PARAM': 'color', 'VALUE': 50}, {})
        assert abs(sprite._pen_hsv[0] - 50) < 1e-6
        sprite.extension('pen', 'pen_setPenSizeTo', {'SIZE': 5}, {})
        assert sprite._pen_size == 5
    finally:
        runtime.shutdown()

    print("  [PASS] TurboWarp运行时选项扩展通过")
    return True


def test_turbowarp_extension_roundtrip_and_cli():
    """扩展调用反向转换 + TurboWarp高级选项CLI参数"""
    print("[测试29] TurboWarp扩展往返与高级选项")

    import subprocess
    import tempfile

    source = '''
class PenSprite(ScratchSprite):
    def __init__(self):
        super().__init__()
        self.name = 'PenSprite'

    def when_green_flag(self):
        self.extension('pen', 'pen_clear', {}, {})
        self.extension('pen', 'pen_penDown', {}, {})
        self.extension('runtimeoptions', 'runtimeoptions_setFramerate', {'VALUE': 60}, {})
'''
    sprite = parse_python_code(source, "PenSprite")
    project = python_to_project(sprite)
    written = write_scratch_project(project)
    opcodes = [b.get("opcode") for b in written["targets"][1]["blocks"].values()]
    assert 'pen_clear' in opcodes
    assert 'pen_penDown' in opcodes
    assert 'runtimeoptions_setFramerate' in opcodes
    assert 'pen' in written["extensions"]
    assert 'runtimeoptions' in written["extensions"]

    # 扩展表达式（reporter）也要能反向转换
    expr_sprite = parse_python_code('''
class ExprExt(ScratchSprite):
    def when_green_flag(self):
        self.say(self.extension('pen', 'pen_penDown', {}, {}))
''', "ExprExt")
    expr_written = write_scratch_project(python_to_project(expr_sprite))
    expr_opcodes = [b.get("opcode")
                    for b in expr_written["targets"][1]["blocks"].values()]
    assert 'pen_penDown' in expr_opcodes, "扩展表达式应写回为输入积木"

    # 高级选项CLI
    code = generate_python(parse_scratch_project(make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("motion_movesteps", None, "b1", {"STEPS": [1, [4, "5"]]}),
    }, name="Options")))
    with tempfile.TemporaryDirectory() as folder:
        script = os.path.join(folder, "turbo_options.py")
        with open(script, "w", encoding="utf-8") as f:
            f.write(code)
        result = subprocess.run(
            [sys.executable, script, "--headless", "--frames", "3",
             "--no-audio", "--interpolation", "--turbo", "--no-fencing",
             "--infinite-clones", "--remove-misc-limits",
             "--stage-size", "640x360", "--hq-pen",
             "--warp-timer", "0.05", "--disable-compiler"],
            capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stderr
        assert "Traceback" not in result.stderr

    print("  [PASS] TurboWarp扩展往返与高级选项通过")
    return True


TESTS = [
    test_turbowarp_warp_procedure_fidelity,
    test_turbowarp_custom_reporter,
    test_turbowarp_pen_extension_runtime,
    test_turbowarp_runtime_options_extension,
    test_turbowarp_extension_roundtrip_and_cli,
]
