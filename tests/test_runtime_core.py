# -*- coding: utf-8 -*-
"""由 test_all.py 拆分出的测试模块"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import *


def test_scratch_runtime_semantics():
    """生成的辅助函数必须复刻Scratch类型转换与边界行为"""
    print("[测试19] Scratch运行时语义")

    scratch_json = make_project({
        "b1": block("event_whenflagclicked", None, None, top_level=True),
    }, name="Sem")
    code = generate_python(parse_scratch_project(scratch_json))
    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)

    eq = namespace["_sc_eq"]
    lt = namespace["_sc_lt"]
    num = namespace["_sc_num"]
    to_str = namespace["_sc_str"]
    to_bool = namespace["_sc_bool"]
    rnd = namespace["_sc_round"]
    div = namespace["_sc_div"]
    mod = namespace["_sc_mod"]
    mathop = namespace["_sc_mathop"]
    letter = namespace["_sc_letter_of"]
    item_of = namespace["_sc_item_of"]
    list_num = namespace["_sc_list_item_number"]
    contents = namespace["_sc_list_contents"]
    repeat_count = namespace["_sc_repeat_count"]

    # 比较：数字优先；否则忽略大小写
    assert eq("ABC", "abc") is True
    assert eq("123", 123) is True
    assert eq("1. ", "1") is True
    assert lt("A", "b") is True
    assert eq("", " ") is False  # 空白字符串按字符串比较
    # 数字/布尔/字符串转换
    assert num("0x10") == 16
    assert num("cat") == 0
    assert num("Infinity") == float("inf")
    assert to_str(3.0) == "3"
    assert to_str(True) == "true"
    assert to_bool("false") is False
    assert to_bool("0") is False
    assert to_bool("") is False
    assert to_bool("0.0") is True
    # 空字符串参与运算
    assert namespace["_sc_add"]("", 5) == 5
    assert namespace["_sc_join"]("", 5) == "5"
    # 运算边界
    assert rnd(2.5) == 3 and rnd(-2.5) == -2
    assert div(1, 0) == float("inf")
    assert div(0, 0) != div(0, 0)  # NaN
    assert mod(-7, 3) == 2
    assert round(mathop("sin", 90), 6) == 1
    assert mathop("tan", 90) == float("inf")
    assert letter(99, "abc") == ""
    assert letter(0.5, "abc") == "", "小于1的小数下标按越界处理"
    assert letter(1.9, "abc") == "a", "小数下标按 charAt 截断"
    assert letter(2.5, "abc") == "b"
    # 列表语义
    items = ["a", "b"]
    assert item_of(items, "last") == "b"
    assert item_of(items, "all") == ""
    assert item_of(items, 99) == ""
    assert list_num([4, 7, "123"], "123") == 3
    assert contents(["a", "b"]) == "ab"
    assert contents(["ab", "c"]) == "ab c"
    # repeat/wait
    assert repeat_count(2.5) == 3
    assert repeat_count(-3) == 0

    print("  [PASS] Scratch运行时语义通过")
    return True


def test_procedure_missing_args_default_empty():
    """自制积木调用没传参数时取空字符串（与原版Scratch一致）"""
    print("[测试20] 自制积木缺省参数")

    code = '''class X(ScratchSprite):
    def add(self, arg_a, arg_b):
        self.n = _sc_add(arg_a, arg_b)

    def when_green_flag(self):
        self.add(1)
'''
    sprite = parse_python_code(code, "X")
    data = write_scratch_project(python_to_project(sprite))
    blocks = get_sprite(data["targets"])["blocks"]

    call = next(b for b in blocks.values() if b.get("opcode") == "procedures_call")
    defn = next(b for b in blocks.values()
                if b.get("opcode") == "procedures_prototype")

    arg_ids = json.loads(call["mutation"]["argumentids"])
    assert len(arg_ids) == 2, "调用参数数量应与定义一致"
    assert call["inputs"][arg_ids[0]][1] == [4, "1"]
    assert call["inputs"][arg_ids[1]][1] == [10, ""], "缺少的参数应为空字符串"

    defaults = json.loads(defn["mutation"]["argumentdefaults"])
    assert defaults == ["", ""], "参数默认值应为空字符串"

    generated = generate_python(parse_scratch_project(data))
    assert "def add(self, arg_a='', arg_b='')" in generated, \
        "生成的Python参数默认值应为空字符串"

    # 运行时：没填的参数当成文本使用时必须为空，而不是 "0"
    runtime_project = make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("procedures_call", None, "b1",
                    {"argid1": [1, [10, "first"]]},
                    mutation={"proccode": "echo %s %s",
                              "argumentids": '["argid1", "argid2"]',
                              "warp": "false"}),
        "p1": block("procedures_definition", "p2", None,
                    {"custom_block": [1, "proto"]}, top_level=True),
        "proto": {
            "opcode": "procedures_prototype", "next": None, "parent": "p1",
            "inputs": {}, "fields": {}, "shadow": True, "topLevel": False,
            "mutation": {"proccode": "echo %s %s",
                         "argumentids": '["argid1", "argid2"]',
                         "argumentnames": '["a", "b"]',
                         "argumentdefaults": '["", ""]', "warp": "false"},
        },
        "p2": block("looks_say", None, "p1", {"MESSAGE": [3, "arg_b", [10, ""]]}),
        "arg_b": block("argument_reporter_string_number", None, "p2", {},
                       {"VALUE": ["b", None]}),
    }, name="DefaultArg")

    import time
    runtime_code = generate_python(parse_scratch_project(runtime_project))
    namespace = {}
    exec(compile(runtime_code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite_obj = namespace["DefaultArg"]()
    runtime.add_sprite(sprite_obj)
    try:
        runtime.start(max_frames=2)
        time.sleep(0.1)
        assert sprite_obj._say_text == "", \
            f"缺省参数用于说话时应为空: {sprite_obj._say_text!r}"
    finally:
        runtime.shutdown()

    print("  [PASS] 自制积木缺省参数通过")
    return True


def test_empty_string_argument_preserved():
    """显式空字符串参数应保持为 ""，不能变成0"""
    print("[测试21] 空字符串参数")

    scratch_json = make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("procedures_call", None, "b1",
                    {"argid1": [1, [10, ""]]},
                    mutation={"proccode": "echo %s",
                              "argumentids": '["argid1"]', "warp": "false"}),
        "p1": block("procedures_definition", "p2", None,
                    {"custom_block": [1, "proto"]}, top_level=True),
        "proto": {
            "opcode": "procedures_prototype", "next": None, "parent": "p1",
            "inputs": {}, "fields": {}, "shadow": True, "topLevel": False,
            "mutation": {"proccode": "echo %s", "argumentids": '["argid1"]',
                         "argumentnames": '["x"]', "argumentdefaults": '[""]',
                         "warp": "false"},
        },
        "p2": block("looks_say", None, "p1", {"MESSAGE": [3, "arg", [10, ""]]}),
        "arg": block("argument_reporter_string_number", None, "p2", {},
                     {"VALUE": ["x", None]}),
    }, name="EmptyArg")

    code = generate_python(parse_scratch_project(scratch_json))
    assert "self.echo('')" in code, "空字符串参数不能被替换成0"

    data = write_scratch_project(python_to_project(parse_python_code(code, "EmptyArg")))
    call = next(b for b in get_sprite(data["targets"])["blocks"].values()
                if b.get("opcode") == "procedures_call")
    arg_id = json.loads(call["mutation"]["argumentids"])[0]
    assert call["inputs"][arg_id] == [1, [10, ""]]

    print("  [PASS] 空字符串参数通过")
    return True


def test_pygame_runtime_runs_generated_script():
    """生成的脚本应能在pygame无头模式下真正执行"""
    print("[测试22] pygame运行时执行")

    import time

    blocks = {
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("data_setvariableto", "b3", "b1",
                    {"VALUE": [1, [4, "0"]]},
                    {"VARIABLE": ["count", "v1"]}),
        "b3": block("control_repeat", "b4", "b2",
                    {"TIMES": [1, [4, "2"]], "SUBSTACK": [2, "c1"]}),
        "c1": block("data_changevariableby", "c2", "b3",
                    {"VALUE": [1, [4, "1"]]},
                    {"VARIABLE": ["count", "v1"]}),
        "c2": block("looks_say", None, "c1",
                    {"MESSAGE": [3, "j1", [10, ""]]}),
        "j1": block("operator_join", None, "c2",
                    {"STRING1": [1, [10, "n="]], "STRING2": [3, "v1"]}),
        "v1": block("data_variable", None, "j1", {},
                    {"VARIABLE": ["count", "v1"]}),
        "b4": block("motion_movesteps", None, "b3", {"STEPS": [1, [4, "10"]]}),
    }
    project = make_project(blocks, name="PyRun")
    project["targets"][0]["variables"] = {"v1": ["count", 0]}

    code = generate_python(parse_scratch_project(project))
    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)

    runtime = namespace["ScratchRuntime"](headless=True)
    sprite = namespace["PyRun"]()
    runtime.add_sprite(sprite)
    try:
        runtime.start(max_frames=8)
        time.sleep(0.2)
        assert abs(sprite.x - 10) < 1e-6, "move(10)在方向90下应向右移动"
        assert abs(sprite.y) < 1e-6
        assert sprite.count == 2
        assert sprite._say_text == "n=2"
    finally:
        runtime.shutdown()

    print("  [PASS] pygame运行时执行通过")
    return True


def test_generated_cli_mixed_arguments():
    """生成脚本应支持 --headless/--frames/--seconds/--trace 等混合参数"""
    print("[测试23] 生成脚本调试参数")

    import subprocess
    import tempfile

    scratch_json = make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("motion_movesteps", None, "b1", {"STEPS": [1, [4, "5"]]}),
    }, name="Cli")
    code = generate_python(parse_scratch_project(scratch_json))

    with tempfile.TemporaryDirectory() as folder:
        script = os.path.join(folder, "cli_run.py")
        with open(script, "w", encoding="utf-8") as f:
            f.write(code)

        result = subprocess.run(
            [sys.executable, script, "--headless", "--frames", "3",
             "--no-audio", "--seed", "7", "--trace"],
            capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stderr
        assert "[trace] green flag" in result.stdout
        assert "Traceback" not in result.stderr

        result2 = subprocess.run(
            [sys.executable, script, "--headless", "--seconds", "0.2",
             "--no-audio"],
            capture_output=True, text=True, timeout=60)
        assert result2.returncode == 0, result2.stderr

    print("  [PASS] 生成脚本调试参数通过")
    return True


def test_sb3_assets_extracted():
    """.sb3里的造型资源应自动解压到脚本旁的assets目录"""
    print("[测试24] sb3素材自动提取")

    import base64
    import tempfile
    import zipfile
    from converter import ScratchConverter

    # 1x1 PNG
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")

    project = make_project({
        "b1": block("event_whenflagclicked", None, None, top_level=True),
    }, name="AssetSprite")
    project["targets"][0]["costumes"] = [{
        "name": "dot.png", "dataFormat": "png", "assetId": "dotasset",
        "md5ext": "dotasset.png", "rotationCenterX": 0, "rotationCenterY": 0,
    }]

    with tempfile.TemporaryDirectory() as folder:
        sb3 = os.path.join(folder, "sample.sb3")
        with zipfile.ZipFile(sb3, "w") as zf:
            zf.writestr("project.json", json.dumps(project, ensure_ascii=False))
            zf.writestr("dotasset.png", png)

        output = os.path.join(folder, "sample.py")
        ScratchConverter().scratch_to_python(sb3, output)

        asset_path = os.path.join(folder, "assets", "dotasset.png")
        assert os.path.exists(asset_path), "造型资源应导出到脚本旁的assets目录"
        code = open(output, encoding="utf-8").read()
        assert "dotasset.png" in code

    print("  [PASS] sb3素材自动提取通过")
    return True


TESTS = [
    test_scratch_runtime_semantics,
    test_procedure_missing_args_default_empty,
    test_empty_string_argument_preserved,
    test_pygame_runtime_runs_generated_script,
    test_generated_cli_mixed_arguments,
    test_sb3_assets_extracted,
]
