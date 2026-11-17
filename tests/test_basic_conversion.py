# -*- coding: utf-8 -*-
"""由 test_all.py 拆分出的测试模块"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import *


def test_basic_scratch_to_python():
    """测试基本的Scratch到Python转换"""
    print("[测试1] 基本Scratch -> Python转换")
    
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
                "variables": {"v1": ["score", 0]},
                "lists": {},
                "broadcasts": {},
                "blocks": {
                    "b1": {
                        "opcode": "event_whenflagclicked",
                        "next": "b2",
                        "parent": None,
                        "inputs": {},
                        "fields": {},
                        "shadow": False,
                        "topLevel": True,
                        "x": 100,
                        "y": 100
                    },
                    "b2": {
                        "opcode": "motion_movesteps",
                        "next": "b3",
                        "parent": "b1",
                        "inputs": {"STEPS": [1, "10"]},
                        "fields": {},
                        "shadow": False,
                        "topLevel": False
                    },
                    "b3": {
                        "opcode": "looks_say",
                        "next": None,
                        "parent": "b2",
                        "inputs": {"MESSAGE": [1, ["10", "Hello!"]]},
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
        "meta": {"semver": "3.0.0", "vm": "0.2.0", "agent": ""}
    }
    
    ir = parse_scratch_project(scratch_json)
    python_code = generate_python(ir)
    
    assert "class Cat(ScratchSprite):" in python_code, "应该生成Cat类"
    assert "def when_green_flag(self):" in python_code, "应该生成when_green_flag方法"
    assert "self.move(10)" in python_code, "应该生成move(10)调用"
    assert "self.say(" in python_code, "应该生成say调用"
    
    print("  [PASS] 基本Scratch -> Python转换通过")
    return True


def test_scratch_loop_to_python():
    """测试Scratch循环到Python的转换"""
    print("[测试2] Scratch循环 -> Python转换")
    
    scratch_json = {
        "targets": [{
            "isStage": False,
            "name": "Loop",
            "variables": {},
            "lists": {},
            "broadcasts": {},
            "blocks": {
                "b1": {
                    "opcode": "event_whenflagclicked",
                    "next": "b2",
                    "parent": None,
                    "inputs": {},
                    "fields": {},
                    "shadow": False,
                    "topLevel": True,
                    "x": 100,
                    "y": 100
                },
                "b2": {
                    "opcode": "control_repeat",
                    "next": "b4",
                    "parent": "b1",
                    "inputs": {
                        "TIMES": [1, "3"],
                        "SUBSTACK": [2, "b3"]
                    },
                    "fields": {},
                    "shadow": False,
                    "topLevel": False
                },
                "b3": {
                    "opcode": "motion_movesteps",
                    "next": None,
                    "parent": "b2",
                    "inputs": {"STEPS": [1, "5"]},
                    "fields": {},
                    "shadow": False,
                    "topLevel": False
                },
                "b4": {
                    "opcode": "control_forever",
                    "next": None,
                    "parent": "b2",
                    "inputs": {"SUBSTACK": [2, "b5"]},
                    "fields": {},
                    "shadow": False,
                    "topLevel": False
                },
                "b5": {
                    "opcode": "motion_ifonedgebounce",
                    "next": None,
                    "parent": "b4",
                    "inputs": {},
                    "fields": {},
                    "shadow": False,
                    "topLevel": False
                }
            },
            "comments": {},
            "currentCostume": 0,
            "costumes": [],
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
        }],
        "monitors": [],
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "0.2.0", "agent": ""}
    }
    
    ir = parse_scratch_project(scratch_json)
    python_code = generate_python(ir)
    
    assert "for _repeat in range(_sc_repeat_count(3)):" in python_code, "应该生成for循环"
    assert "while self._running:" in python_code, "应该生成while循环(forever)"
    assert "self.if_on_edge_bounce()" in python_code, "应该生成if_on_edge_bounce调用"
    
    print("  [PASS] Scratch循环 -> Python转换通过")
    return True


def test_scratch_variables_to_python():
    """测试Scratch变量到Python的转换"""
    print("[测试3] Scratch变量 -> Python转换")
    
    scratch_json = {
        "targets": [{
            "isStage": False,
            "name": "Var",
            "variables": {"v1": ["count", 0], "v2": ["name", "Scratch"]},
            "lists": {"l1": ["items", ["a", "b", "c"]]},
            "broadcasts": {},
            "blocks": {
                "b1": {
                    "opcode": "event_whenflagclicked",
                    "next": "b2",
                    "parent": None,
                    "inputs": {},
                    "fields": {},
                    "shadow": False,
                    "topLevel": True,
                    "x": 100,
                    "y": 100
                },
                "b2": {
                    "opcode": "data_setvariableto",
                    "next": "b3",
                    "parent": "b1",
                    "inputs": {"VALUE": [1, "42"]},
                    "fields": {"VARIABLE": ["count", "v1"]},
                    "shadow": False,
                    "topLevel": False
                },
                "b3": {
                    "opcode": "data_changevariableby",
                    "next": None,
                    "parent": "b2",
                    "inputs": {"VALUE": [1, "10"]},
                    "fields": {"VARIABLE": ["count", "v1"]},
                    "shadow": False,
                    "topLevel": False
                }
            },
            "comments": {},
            "currentCostume": 0,
            "costumes": [],
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
        }],
        "monitors": [],
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "0.2.0", "agent": ""}
    }
    
    ir = parse_scratch_project(scratch_json)
    python_code = generate_python(ir)
    
    assert "self.count = 0" in python_code, "应该声明变量"
    assert "self.count = 42" in python_code, "应该设置变量值"
    assert "self.count = _sc_add(self.count, 10)" in python_code, "应该更改变量值"
    
    print("  [PASS] Scratch变量 -> Python转换通过")
    return True


def test_python_to_scratch():
    """测试Python到Scratch的转换"""
    print("[测试4] Python -> Scratch转换")
    
    python_code = '''# -*- coding: utf-8 -*-
class Cat(ScratchSprite):
    def __init__(self):
        super().__init__()
        self.x = 0
        self.y = 0
        self.score = 0
    
    def when_green_flag(self):
        """当绿旗被点击时"""
        while self._running:
            self.move(10)
            self.say("Hello!")
            self.turn_right(15)
    
    def run(self):
        self.when_green_flag()
'''
    
    sprite = parse_python_code(python_code, "Cat")
    project = python_to_project(sprite)
    scratch_json = write_scratch_project(project)
    
    assert "targets" in scratch_json, "应该生成Scratch JSON"
    sprites = [t for t in scratch_json["targets"] if not t.get("isStage")]
    stages = [t for t in scratch_json["targets"] if t.get("isStage")]
    assert len(sprites) == 1, "应该有1个精灵目标"
    assert len(stages) == 1, "Scratch项目必须有且只有一个舞台"
    
    target = sprites[0]
    assert target["name"] == "Cat", "精灵名应该是Cat"
    assert target["isStage"] == False, "不是舞台"
    
    blocks = target.get("blocks", {})
    has_event = any(b.get("opcode") == "event_whenflagclicked" for b in blocks.values())
    assert has_event, "应该有when_flag_clicked块"
    
    has_move = any(b.get("opcode") == "motion_movesteps" for b in blocks.values())
    assert has_move, "应该有move_steps块"
    
    has_say = any(b.get("opcode") == "looks_say" for b in blocks.values())
    assert has_say, "应该有say块"
    
    print("  [PASS] Python -> Scratch转换通过")
    return True


def test_roundtrip_scratch():
    """测试Scratch -> Python -> Scratch往返转换"""
    print("[测试5] Scratch往返转换")
    
    scratch_json = {
        "targets": [{
            "isStage": False,
            "name": "Test",
            "variables": {},
            "lists": {},
            "broadcasts": {},
            "blocks": {
                "b1": {
                    "opcode": "event_whenflagclicked",
                    "next": "b2",
                    "parent": None,
                    "inputs": {},
                    "fields": {},
                    "shadow": False,
                    "topLevel": True,
                    "x": 100,
                    "y": 100
                },
                "b2": {
                    "opcode": "motion_movesteps",
                    "next": "b3",
                    "parent": "b1",
                    "inputs": {"STEPS": [1, "20"]},
                    "fields": {},
                    "shadow": False,
                    "topLevel": False
                },
                "b3": {
                    "opcode": "motion_turnright",
                    "next": None,
                    "parent": "b2",
                    "inputs": {"DEGREES": [1, "30"]},
                    "fields": {},
                    "shadow": False,
                    "topLevel": False
                }
            },
            "comments": {},
            "currentCostume": 0,
            "costumes": [],
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
        }],
        "monitors": [],
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "0.2.0", "agent": ""}
    }
    
    # 第一次转换: Scratch -> Python
    ir1 = parse_scratch_project(scratch_json)
    python_code = generate_python(ir1)
    
    # 第二次转换: Python -> Scratch
    sprite = parse_python_code(python_code, "Test")
    project = python_to_project(sprite)
    scratch_json2 = write_scratch_project(project)
    
    # 验证往返转换保持了核心结构
    target1 = next(t for t in scratch_json["targets"] if not t.get("isStage"))
    target2 = next(t for t in scratch_json2["targets"] if not t.get("isStage"))
    
    blocks1 = target1.get("blocks", {})
    blocks2 = target2.get("blocks", {})
    
    opcodes1 = {b.get("opcode") for b in blocks1.values()}
    opcodes2 = {b.get("opcode") for b in blocks2.values()}
    
    # 验证关键块类型被保留
    assert "event_whenflagclicked" in opcodes2, "往返后应保留when_flag_clicked块"
    assert "motion_movesteps" in opcodes2, "往返后应保留move_steps块"
    assert "motion_turnright" in opcodes2, "往返后应保留turn_right块"
    
    print("  [PASS] Scratch往返转换通过")
    return True


def test_expressions():
    """测试表达式转换"""
    print("[测试6] 表达式转换")
    
    # 测试数字表达式
    num = make_number(42)
    assert num.to_python_source() == "42"
    
    # 测试字符串表达式
    s = make_string("hello")
    assert s.to_python_source() == "'hello'"
    
    # 测试布尔表达式
    b = make_boolean(True)
    assert b.to_python_source() == "True"
    
    # 测试二元运算（走Scratch类型转换辅助函数）
    expr = make_binary_op('+', make_number(1), make_number(2))
    assert expr.to_python_source() == "_sc_add(1, 2)"
    
    # 测试随机数
    rand = make_random(make_number(1), make_number(10))
    assert "_sc_random(1, 10)" == rand.to_python_source()
    
    print("  [PASS] 表达式转换通过")
    return True


def test_if_else():
    """测试if/else转换"""
    print("[测试7] if/else转换")
    
    scratch_json = {
        "targets": [{
            "isStage": False,
            "name": "IfElse",
            "variables": {},
            "lists": {},
            "broadcasts": {},
            "blocks": {
                "b1": {
                    "opcode": "event_whenflagclicked",
                    "next": "b2",
                    "parent": None,
                    "inputs": {},
                    "fields": {},
                    "shadow": False,
                    "topLevel": True,
                    "x": 100,
                    "y": 100
                },
                "b2": {
                    "opcode": "control_if_else",
                    "next": None,
                    "parent": "b1",
                    "inputs": {
                        "CONDITION": [2, "b_cond"],
                        "SUBSTACK": [2, "b_if"],
                        "SUBSTACK2": [2, "b_else"]
                    },
                    "fields": {},
                    "shadow": False,
                    "topLevel": False
                },
                "b_cond": {
                    "opcode": "operator_equals",
                    "next": None,
                    "parent": "b2",
                    "inputs": {
                        "OPERAND1": [1, "10"],
                        "OPERAND2": [1, "10"]
                    },
                    "fields": {},
                    "shadow": False,
                    "topLevel": False
                },
                "b_if": {
                    "opcode": "looks_say",
                    "next": None,
                    "parent": "b2",
                    "inputs": {"MESSAGE": [1, ["10", "Equal!"]]},
                    "fields": {},
                    "shadow": False,
                    "topLevel": False
                },
                "b_else": {
                    "opcode": "looks_say",
                    "next": None,
                    "parent": "b2",
                    "inputs": {"MESSAGE": [1, ["10", "Not equal!"]]},
                    "fields": {},
                    "shadow": False,
                    "topLevel": False
                }
            },
            "comments": {},
            "currentCostume": 0,
            "costumes": [],
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
        }],
        "monitors": [],
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "0.2.0", "agent": ""}
    }
    
    ir = parse_scratch_project(scratch_json)
    python_code = generate_python(ir)
    
    assert "if" in python_code, "应该生成if语句"
    assert "else:" in python_code, "应该生成else语句"
    
    print("  [PASS] if/else转换通过")
    return True


def test_real_sb3_literal_formats():
    """真实sb3的字面量是 [1,[4,"10"]]，不能解析成0或列表字符串"""
    print("[测试8] 真实sb3字面量格式")

    scratch_json = make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("control_repeat", None, "b1", {
            "TIMES": [1, [4, "3"]],
            "SUBSTACK": [2, "b3"],
        }),
        "b3": block("motion_movesteps", "b4", "b2", {"STEPS": [1, [4, "10"]]}),
        "b4": block("looks_say", None, "b3", {"MESSAGE": [1, [10, "Hello!"]]}),
    })

    code = generate_python(parse_scratch_project(scratch_json))

    assert "for _repeat in range(_sc_repeat_count(3)):" in code, "循环次数应为3"
    assert "self.move(10)" in code, "步数应为数字10"
    assert "self.say('Hello!')" in code, "字符串不应变成 [10, 'Hello!'] 列表"

    print("  [PASS] 真实sb3字面量格式通过")
    return True


def test_event_script_wrapper():
    """事件脚本在Scratch中只执行一次，不能额外包一层 while self._running"""
    print("[测试9] 事件脚本不被死循环包裹")

    scratch_json = make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("motion_movesteps", None, "b1", {"STEPS": [1, [4, "10"]]}),
    })

    code = generate_python(parse_scratch_project(scratch_json))
    sprite_part = code.split("class Test(ScratchSprite):", 1)[1]
    assert "while self._running:" not in sprite_part, "事件处理函数不应被死循环包裹"
    assert "self.move(10)" in sprite_part

    # 往返后不应凭空多出 control_forever
    restored = parse_python_code(code, "Test")
    scratch_json2 = write_scratch_project(python_to_project(restored))
    opcodes = [b.get("opcode") for b in get_sprite(scratch_json2["targets"])["blocks"].values()]
    assert "control_forever" not in opcodes, "往返后不应出现control_forever"

    print("  [PASS] 事件脚本单次执行通过")
    return True


def test_infinite_number_literals():
    """Infinity/NaN 数值字面量不应导致转换崩溃"""
    print("[测试81] 无限与 NaN 数值字面量")

    infinite = Expr(ExprType.NUMBER, value=float('inf'))
    negative = Expr(ExprType.NUMBER, value=float('-inf'))
    nan = Expr(ExprType.NUMBER, value=float('nan'))
    assert infinite.to_python_source() == "float('inf')"
    assert negative.to_python_source() == "float('-inf')"
    assert nan.to_python_source() == "float('nan')"

    expression = make_binary_op(
        '>', make_variable('x'), infinite)
    source = expression.to_python_source()
    assert "float('inf')" in source
    assert 'OverflowError' not in source

    print("  [PASS] 无限与 NaN 数值字面量通过")
    return True


def test_pure_computation_loop_no_yield():
    """纯变量/列表计算循环不应逐帧让出"""
    print("[测试82] 纯计算循环不逐帧让出")

    pure = make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("control_repeat", None, "b1",
                    inputs={"TIMES": [1, "100"],
                            "SUBSTACK": [2, "b3"]}),
        "b3": block("data_setvariableto", None, "b2",
                    inputs={"VALUE": [1, "1"]},
                    fields={"VARIABLE": ["x", "x1"]}),
    }, name="PureLoop")
    pure["targets"][0]["variables"] = {"x1": ["x", 0]}
    pure_code = generate_python(parse_scratch_project(pure))
    start = pure_code.index('for _repeat in range')
    segment = pure_code[start:start + 400]
    assert 'self._yield_frame()' not in segment, \
        "纯计算循环不应让出帧"

    motion = make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("control_repeat", None, "b1",
                    inputs={"TIMES": [1, "100"],
                            "SUBSTACK": [2, "b3"]}),
        "b3": block("motion_movesteps", None, "b2",
                    inputs={"STEPS": [1, "1"]}),
    }, name="MotionLoop")
    motion_code = generate_python(parse_scratch_project(motion))
    start = motion_code.index('for _repeat in range')
    segment = motion_code[start:start + 400]
    assert 'self._yield_frame()' in segment, \
        "有画面副作用的循环仍应逐帧让出"

    print("  [PASS] 纯计算循环不逐帧让出通过")
    return True


def test_large_list_json_initialization():
    """超大列表初始值改用 JSON 解析，避免拖慢编译"""
    print("[测试83] 超大列表 JSON 初始化")

    import json as _json
    from python_generator import _json_literal

    big = list(range(300))
    source = _json_literal(big)
    assert source.startswith("json.loads("), "大列表应使用 JSON 字符串"
    assert eval(source, {"json": _json}) == big, "JSON 解析结果应保持一致"

    assert _json_literal(float('inf')) == "float('inf')"
    assert _json_literal([1, 2, 3]) == "[1, 2, 3]", "小列表保持普通字面量"

    scratch_json = make_project({
        "b1": block("event_whenflagclicked", None, None, top_level=True),
    }, name="BigList")
    scratch_json["targets"][0]["lists"] = {
        "l1": ["data", list(range(300))],
        "l2": ["small", [1, 2, 3]],
    }
    code = generate_python(parse_scratch_project(scratch_json))
    assert "json.loads(" in code, "大列表应生成 JSON 解析"
    assert "__sc_init_list_0" in code, "大列表应作为类属性只解析一次"
    assert "self.data = list(self.__sc_init_list_0)" in code
    assert "self.small = [1, 2, 3]" in code, "小列表保持普通字面量"

    print("  [PASS] 超大列表 JSON 初始化通过")
    return True


TESTS = [
    test_basic_scratch_to_python,
    test_scratch_loop_to_python,
    test_scratch_variables_to_python,
    test_python_to_scratch,
    test_roundtrip_scratch,
    test_expressions,
    test_if_else,
    test_real_sb3_literal_formats,
    test_event_script_wrapper,
    test_infinite_number_literals,
    test_pure_computation_loop_no_yield,
    test_large_list_json_initialization,
]
