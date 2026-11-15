#!/usr/bin/env python3
"""
Scratch 3.0 <-> Python 双向转换器 综合测试
"""

import sys
import os
import json
import math

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ir import (
    BlockType, ExprType, Expr, Statement, SpriteIR, ProjectIR,
    make_number, make_string, make_boolean, make_variable, make_binary_op, make_random,
)
from scratch_parser import parse_scratch_project
from scratch_writer import write_scratch_project
from python_generator import generate_python
from python_parser import parse_python_code, python_to_project


def make_project(blocks, name="Test"):
    """构造一个最小Scratch项目（使用真实sb3的嵌套字面量格式）"""
    return {
        "targets": [{
            "isStage": False,
            "name": name,
            "variables": {},
            "lists": {},
            "broadcasts": {},
            "blocks": blocks,
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


def block(opcode, next_id=None, parent=None, inputs=None, fields=None,
          top_level=False, mutation=None):
    """构造Scratch块数据"""
    data = {
        "opcode": opcode,
        "next": next_id,
        "parent": parent,
        "inputs": inputs or {},
        "fields": fields or {},
        "shadow": False,
        "topLevel": top_level,
    }
    if top_level:
        data["x"] = 0
        data["y"] = 0
    if mutation:
        data["mutation"] = mutation
    return data


def get_sprite(targets):
    return next(t for t in targets if not t.get("isStage"))


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


def test_procedure_roundtrip():
    """自制积木：调用参数、函数体、原型都要能往返"""
    print("[测试10] 自制积木往返转换")

    scratch_json = make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("procedures_call", None, "b1", {"argid1": [1, [4, "7"]]},
                    mutation={"proccode": "add %s",
                              "argumentids": '["argid1"]', "warp": "false"}),
        "p1": block("procedures_definition", "p2", None,
                    {"custom_block": [1, "proto"]}, top_level=True),
        "proto": {
            "opcode": "procedures_prototype", "next": None, "parent": "p1",
            "inputs": {}, "fields": {}, "shadow": True, "topLevel": False,
            "mutation": {"proccode": "add %s", "argumentids": '["argid1"]',
                         "argumentnames": '["x"]', "argumentdefaults": '[""]',
                         "warp": "false"},
        },
        "p2": block("data_changevariableby", "p3", "p1",
                    {"VALUE": [1, [4, "1"]]}, {"VARIABLE": ["n", "v1"]}),
        "p3": block("looks_say", None, "p2", {"MESSAGE": [1, [10, "hi"]]}),
    })
    scratch_json["targets"][0]["variables"] = {"v1": ["n", 0]}

    code = generate_python(parse_scratch_project(scratch_json))
    assert "def add(self, arg_x=''):" in code, \
        "应生成带默认参数的函数（空字符串）"
    assert "self.add(7)" in code, "调用应带参数7"
    assert "self.n = _sc_add(self.n, 1)" in code, "函数体第一条语句"
    assert "self.say('hi')" in code, "函数体第二条语句不能丢失"

    restored = parse_python_code(code, "Test")
    scratch_json2 = write_scratch_project(python_to_project(restored))
    sprite = get_sprite(scratch_json2["targets"])
    blocks = sprite["blocks"]
    opcodes = [b.get("opcode") for b in blocks.values()]

    assert opcodes.count("procedures_definition") == 1
    assert opcodes.count("procedures_call") == 1
    assert opcodes.count("looks_say") == 1, "函数体不应重复"
    assert opcodes.count("data_changevariableby") == 1
    assert "procedures_prototype" in opcodes, "Scratch需要prototype块"
    assert sprite["name"] == "Test", "精灵名不应丢失"

    print("  [PASS] 自制积木往返转换通过")
    return True


def test_multi_sprite_blocks_isolated():
    """多个精灵时，块不能串到其他精灵里"""
    print("[测试11] 多精灵块隔离")

    from ir import ProjectIR, SpriteIR, Statement

    project = ProjectIR()
    a = SpriteIR(name="A")
    a.add_statement(Statement(type=BlockType.WHEN_FLAG_CLICKED,
                              next=Statement(type=BlockType.SHOW)))
    b = SpriteIR(name="B")
    b.add_statement(Statement(type=BlockType.WHEN_FLAG_CLICKED,
                              next=Statement(type=BlockType.HIDE)))
    project.add_sprite(a)
    project.add_sprite(b)

    data = write_scratch_project(project)
    sprites = {t["name"]: t for t in data["targets"] if not t.get("isStage")}

    ops_a = {blk.get("opcode") for blk in sprites["A"]["blocks"].values()}
    ops_b = {blk.get("opcode") for blk in sprites["B"]["blocks"].values()}
    assert ops_a == {"event_whenflagclicked", "looks_show"}
    assert ops_b == {"event_whenflagclicked", "looks_hide"}

    print("  [PASS] 多精灵块隔离通过")
    return True


def test_list_contents_expression():
    """列表内容作为表达式时，生成的Python必须可编译"""
    print("[测试12] 列表内容表达式")

    scratch_json = make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("looks_say", None, "b1", {"MESSAGE": [3, "b3", [10, ""]]}),
        "b3": block("data_listcontents", None, "b2", {}, {"LIST": ["items", "l1"]}),
    }, name="ListSprite")
    scratch_json["targets"][0]["lists"] = {"l1": ["items", [1, 2]]}

    code = generate_python(parse_scratch_project(scratch_json))
    assert "self.say(_sc_list_contents(self.items))" in code
    compile(code, "<generated>", "exec")

    print("  [PASS] 列表内容表达式通过")
    return True


def test_list_operations_roundtrip():
    """列表操作：添加/删除/清空/插入/替换/取值都要能往返"""
    print("[测试13] 列表操作往返")

    scratch_json = make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("data_addtolist", "b3", "b1", {"ITEM": [1, [10, "x"]]},
                    {"LIST": ["items", "l1"]}),
        "b3": block("data_deleteoflist", "b4", "b2", {"INDEX": [1, [4, "1"]]},
                    {"LIST": ["items", "l1"]}),
        "b4": block("data_deletealloflist", "b5", "b3", {},
                    {"LIST": ["items", "l1"]}),
        "b5": block("data_insertatlist", "b6", "b4",
                    {"ITEM": [1, [10, "y"]], "INDEX": [1, [4, "1"]]},
                    {"LIST": ["items", "l1"]}),
        "b6": block("data_replaceitemoflist", "b8", "b5",
                    {"ITEM": [1, [10, "z"]], "INDEX": [1, [4, "2"]]},
                    {"LIST": ["items", "l1"]}),
        "b8": block("looks_say", None, "b6", {"MESSAGE": [3, "b9", [10, ""]]}),
        "b9": block("data_itemoflist", None, "b8", {"INDEX": [1, [4, "2"]]},
                    {"LIST": ["items", "l1"]}),
    }, name="Lists")
    scratch_json["targets"][0]["lists"] = {"l1": ["items", [1, 2]]}

    code = generate_python(parse_scratch_project(scratch_json))
    assert "self.items.append('x')" in code
    assert "_sc_list_delete(self.items, 1)" in code
    assert "self.items.clear()" in code
    assert "_sc_list_insert(self.items, 1, 'y')" in code
    assert "_sc_list_replace(self.items, 2, 'z')" in code
    assert "self.say(_sc_item_of(self.items, 2))" in code

    restored = parse_python_code(code, "Lists")
    scratch_json2 = write_scratch_project(python_to_project(restored))
    blocks = get_sprite(scratch_json2["targets"])["blocks"]
    opcodes = [b.get("opcode") for b in blocks.values()]

    for opcode in ("data_addtolist", "data_deleteoflist",
                   "data_deletealloflist", "data_insertatlist",
                   "data_replaceitemoflist", "data_itemoflist"):
        assert opcode in opcodes, f"往返后缺少{opcode}"

    # item of list 的索引仍然是2，而不是 2-1
    item_block = next(b for b in blocks.values() if b.get("opcode") == "data_itemoflist")
    assert item_block["inputs"]["INDEX"] == [1, [4, "2"]], "索引应还原为2"

    print("  [PASS] 列表操作往返通过")
    return True


def test_item_number_of_list():
    """item # of list 返回位置，不能生成“包含”判断"""
    print("[测试14] 列表中项的位置")

    scratch_json = make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("looks_say", None, "b1", {"MESSAGE": [3, "b3", [10, ""]]}),
        "b3": block("data_itemnumoflist", None, "b2", {"ITEM": [1, [10, "a"]]},
                    {"LIST": ["items", "l1"]}),
    }, name="ItemNum")
    scratch_json["targets"][0]["lists"] = {"l1": ["items", ["a", "b"]]}

    code = generate_python(parse_scratch_project(scratch_json))
    assert "_sc_list_item_number(self.items, 'a')" in code
    assert " in self.items" not in code

    restored = parse_python_code(code, "ItemNum")
    scratch_json2 = write_scratch_project(python_to_project(restored))
    blocks = get_sprite(scratch_json2["targets"])["blocks"]
    opcodes = [b.get("opcode") for b in blocks.values()]
    assert "data_itemnumoflist" in opcodes
    assert "data_listcontainsitem" not in opcodes

    print("  [PASS] 列表中项的位置通过")
    return True


def test_broadcast_name_with_space():
    """广播名带空格时，往返后必须保持原样"""
    print("[测试15] 广播名保真")

    scratch_json = make_project({
        "b1": block("event_whenbroadcastreceived", "b2", None, top_level=True,
                    fields={"BROADCAST_OPTION": ["game over", "bc1"]}),
        "b2": block("looks_say", None, "b1", {"MESSAGE": [1, [10, "bye"]]}),
    }, name="Bc")

    code = generate_python(parse_scratch_project(scratch_json))
    assert "def when_broadcast_game_over(self):" in code

    restored = parse_python_code(code, "Bc")
    scratch_json2 = write_scratch_project(python_to_project(restored))
    blocks = get_sprite(scratch_json2["targets"])["blocks"]
    event = next(b for b in blocks.values()
                 if b.get("opcode") == "event_whenbroadcastreceived")
    assert event["fields"]["BROADCAST_OPTION"][0] == "game over"

    stage = next(t for t in scratch_json2["targets"] if t.get("isStage"))
    assert "game over" in stage["broadcasts"].values(), "广播必须登记到舞台"

    print("  [PASS] 广播名保真通过")
    return True


def test_undeclared_variable_is_created():
    """脚本中使用但__init__未声明的变量，写到Scratch时必须补上声明"""
    print("[测试16] 变量自动声明")

    code = '''class X(ScratchSprite):
    def when_green_flag(self):
        self.score += 1
'''
    sprite = parse_python_code(code, "X")
    data = write_scratch_project(python_to_project(sprite))
    target = get_sprite(data["targets"])
    var_names = [v[0] for v in target["variables"].values()]
    assert "score" in var_names

    print("  [PASS] 变量自动声明通过")
    return True


def test_clone_hat_block():
    """克隆体启动事件不能被丢弃"""
    print("[测试17] 克隆体启动事件")

    scratch_json = make_project({
        "b1": block("control_start_as_clone", "b2", None, top_level=True),
        "b2": block("looks_say", None, "b1", {"MESSAGE": [1, [10, "clone"]]}),
    }, name="Clone")

    code = generate_python(parse_scratch_project(scratch_json))
    assert "def when_clone_starts(self):" in code
    assert "self.say('clone')" in code

    restored = parse_python_code(code, "Clone")
    data = write_scratch_project(python_to_project(restored))
    blocks = get_sprite(data["targets"])["blocks"]
    opcodes = [b.get("opcode") for b in blocks.values()]
    assert "control_start_as_clone" in opcodes

    hat = next(b for b in blocks.values() if b.get("opcode") == "control_start_as_clone")
    assert hat["topLevel"] is True and "x" in hat and "y" in hat

    print("  [PASS] 克隆体启动事件通过")
    return True


def test_orphan_blocks_ignored():
    """没有事件帽块开头的孤儿积木必须被忽略"""
    print("[测试18] 忽略孤儿积木")

    scratch_json = make_project({
        # 正常脚本
        "h1": block("event_whenflagclicked", "h2", None, top_level=True),
        "h2": block("motion_movesteps", None, "h1", {"STEPS": [1, [4, "10"]]}),
        # 孤儿堆栈：不以事件块开头
        "o1": block("motion_movesteps", "o2", None, {"STEPS": [1, [4, "99"]]},
                    top_level=True),
        "o2": block("looks_say", None, "o1", {"MESSAGE": [1, [10, "orphan"]]}),
        # 孤儿自制积木调用
        "o3": block("procedures_call", None, None, {},
                    mutation={"proccode": "lost", "argumentids": "[]",
                              "warp": "false"}, top_level=True),
        # event_broadcast不是帽块，作为顶层块同样属于孤儿
        "o4": block("event_broadcast", None, None,
                    {"BROADCAST_INPUT": [1, [11, "bc", "msg"]]}, top_level=True),
    }, name="Orphan")

    code = generate_python(parse_scratch_project(scratch_json))
    sprite_part = code.split("class Orphan(ScratchSprite):", 1)[1]

    assert "self.move(10)" in sprite_part
    assert "self.move(99)" not in sprite_part, "孤儿脚本不应被转换"
    assert "self.say('orphan')" not in sprite_part, "孤儿脚本的后续积木也不应出现"
    assert "self.lost(" not in sprite_part, "孤儿自制积木调用不应出现"
    assert "self.broadcast(" not in sprite_part, "顶层广播积木不是事件帽块"

    print("  [PASS] 忽略孤儿积木通过")
    return True


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


def test_global_variables_and_monitor_labels():
    """舞台全局变量应在角色间共享；局部变量监视器应带角色名前缀"""
    print("[测试30] 全局变量共享与监视器前缀")

    import time

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {"g1": ["score", 0]}, "lists": {},
        "broadcasts": {}, "blocks": {}, "comments": {},
        "currentCostume": 0, "costumes": [], "sounds": [],
        "volume": 100, "layerOrder": 0,
    }
    project = make_project({
        "h1": block("event_whenflagclicked", "h2", None, top_level=True),
        "h2": block("data_setvariableto", "h3", "h1",
                    {"VALUE": [1, [4, "10"]]},
                    {"VARIABLE": ["score", "g1"]}),
        "h3": block("data_setvariableto", None, "h2",
                    {"VALUE": [1, [4, "3"]]},
                    {"VARIABLE": ["hp", "v1"]}),
    }, name="Hero")
    hero = project["targets"][0]
    hero["variables"] = {"v1": ["hp", 0]}

    villain = json.loads(json.dumps(hero))
    villain["name"] = "Villain"
    villain["blocks"] = {
        "v1": block("event_whenflagclicked", "v2", None, top_level=True),
        "v2": block("looks_say", None, "v1",
                    {"MESSAGE": [3, "v3", [10, ""]]}),
        "v3": block("data_variable", None, "v2", {},
                    {"VARIABLE": ["score", "g1"]}),
    }
    project["targets"] = [stage, hero, villain]
    project["monitors"] = [
        {
            "id": "m1", "mode": "default", "opcode": "data_variable",
            "params": {"VARIABLE": "hp"}, "spriteName": "Hero",
            "x": 5, "y": 5, "width": 0, "height": 0, "visible": True,
            "sliderMin": 0, "sliderMax": 100, "isDiscrete": True,
        },
        {
            "id": "m2", "mode": "default", "opcode": "data_variable",
            "params": {"VARIABLE": "score"}, "spriteName": None,
            "x": 5, "y": 30, "width": 0, "height": 0, "visible": True,
            "sliderMin": 0, "sliderMax": 100, "isDiscrete": True,
        },
    ]

    ir = parse_scratch_project(project)
    code = generate_python(ir)
    assert "GLOBAL_NAMES = ('score',)" in code, \
        "角色的GLOBAL_NAMES只应包含未被本地遮蔽的全局变量"
    assert "'label': 'Hero: hp'" in code, "局部变量监视器应带角色名前缀"
    assert "'label': 'score'" in code, "全局变量监视器不应加前缀"
    assert "'sprite': 'Hero'" in code

    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](headless=True)
    hero_obj = namespace["Hero"]()
    villain_obj = namespace["Villain"]()
    runtime.add_sprite(hero_obj)
    runtime.add_sprite(villain_obj)
    try:
        runtime.start(max_frames=10)
        time.sleep(0.3)
        assert namespace["GLOBALS"]["score"] == 10, "全局变量应写入共享GLOBALS"
        assert hero_obj.hp == 3
        assert hero_obj.score == 10, "角色应能通过属性读取全局变量"
        assert villain_obj._say_text == "10", "另一个角色应能读到同一全局变量"
        runtime._draw_monitors()
    finally:
        runtime.shutdown()

    print("  [PASS] 全局变量共享与监视器前缀通过")
    return True


def test_extra_blocks_supported():
    """补充积木：面向/旋转方式/拖动/背景/图层/循环/计数器/声音特效"""
    print("[测试31] 补充积木支持")

    import time

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {}, "lists": {}, "broadcasts": {}, "blocks": {},
        "comments": {}, "currentCostume": 0,
        "costumes": [
            {"name": "bg1", "dataFormat": "svg", "assetId": "", "md5ext": ""},
            {"name": "bg2", "dataFormat": "svg", "assetId": "", "md5ext": ""},
        ],
        "sounds": [], "volume": 100, "layerOrder": 0,
    }
    blocks = {
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("motion_pointindirection", "b3", "b1",
                    {"DIRECTION": [1, [4, "90"]]}),
        "b3": block("motion_setrotationstyle", "b4", "b2", {},
                    {"STYLE": ["left-right", None]}),
        "b4": block("sensing_setdragmode", "b5", "b3", {},
                    {"DRAG_MODE": ["draggable", None]}),
        "b5": block("motion_pointtowards", "b6", "b4", {},
                    {"TOWARDS": ["_mouse_", None]}),
        "b6": block("motion_goto", "b7", "b5", {},
                    {"TO": ["_mouse_", None]}),
        "b7": block("looks_switchbackdropto", "b8", "b6",
                    {}, {"BACKDROP": ["bg2", None]}),
        "b8": block("looks_seteffectto", "b9", "b7",
                    {"VALUE": [1, [4, "50"]]}, {"EFFECT": ["GHOST", None]}),
        "b9": block("looks_gotofrontback", "b10", "b8", {},
                    {"FRONT_BACK": ["front", None]}),
        "b10": block("looks_goforwardbackwardlayers", "b11", "b9",
                     {"NUM": [1, [4, "1"]]},
                     {"FORWARD_BACKWARD": ["backward", None]}),
        "b11": block("sound_seteffectto", "b12", "b10",
                     {"VALUE": [1, [4, "100"]]},
                     {"SOUND_EFFECT": ["PITCH", None]}),
        "b12": block("sound_cleareffects", "b13", "b11"),
        "b13": block("control_clear_counter", "b14", "b12"),
        "b14": block("control_all_at_once", "b15", "b13",
                     {"SUBSTACK": [2, "a1"]}),
        "a1": block("control_incr_counter", None, "b14"),
        "b15": block("control_for_each", "b16", "b14",
                     {"VALUE": [3, "lst", [10, ""]], "SUBSTACK": [2, "f1"]},
                     {"VARIABLE": ["each", "v_each"]}),
        "f1": block("data_changevariableby", None, "b15",
                    {"VALUE": [3, "arg", [4, "0"]]},
                    {"VARIABLE": ["total", "v_total"]}),
        "arg": block("data_variable", None, "f1", {}, {"VARIABLE": ["each", "v_each"]}),
        "lst": block("data_listcontents", None, "b15", {}, {"LIST": ["items", "l_items"]}),
        "b16": block("control_incr_counter", "b17", "b15"),
        "b17": block("control_while", "b18", "b16",
                     {"CONDITION": [3, "cmp", [7, "false"]],
                      "SUBSTACK": [2, "w1"]}),
        "cmp": block("operator_lt", None, "b17",
                     {"OPERAND1": [3, "x", [4, "0"]],
                      "OPERAND2": [1, [4, "3"]]}),
        "x": block("data_variable", None, "cmp", {}, {"VARIABLE": ["x", "v_x"]}),
        "w1": block("data_changevariableby", None, "b17",
                    {"VALUE": [1, [4, "1"]]}, {"VARIABLE": ["x", "v_x"]}),
        "b18": block("looks_say", "b19", "b17",
                     {"MESSAGE": [3, "bdname", [10, ""]]}),
        "bdname": block("looks_backdropnumbername", None, "b18", {},
                        {"NUMBER_NAME": ["name", None]}),
        "b19": block("looks_say", "b20", "b18",
                     {"MESSAGE": [3, "bdnum", [10, ""]]}),
        "bdnum": block("looks_backdropnumbername", None, "b19", {},
                       {"NUMBER_NAME": ["number", None]}),
        "b20": block("control_if", None, "b19",
                     {"CONDITION": [2, "touch"], "SUBSTACK": [2, "i1"]}),
        "touch": block("sensing_touchingcolor", None, "b20",
                       {"COLOR": [1, [9, "#ff0000"]]}),
        "i1": block("data_changevariableby", None, "b20",
                    {"VALUE": [1, [4, "1"]]}, {"VARIABLE": ["x", "v_x"]}),
    }
    project = {
        "targets": [
            stage,
            {
                "isStage": False, "name": "Hero",
                "variables": {
                    "v_total": ["total", 0],
                    "v_each": ["each", 0],
                    "v_x": ["x", 0],
                },
                "lists": {"l_items": ["items", [1, 2, 3]]},
                "broadcasts": {}, "blocks": blocks, "comments": {},
                "currentCostume": 0, "costumes": [], "sounds": [],
                "visible": True, "x": 0, "y": 0, "size": 100,
                "direction": 90, "draggable": False,
                "rotationStyle": "all around", "volume": 100, "layerOrder": 1,
            },
        ],
        "monitors": [], "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "0.2.0", "agent": ""},
    }

    ir = parse_scratch_project(project)
    assert not ir.warnings, f"不应再有未支持积木: {ir.warnings}"
    code = generate_python(ir)
    for snippet in ("point_in_direction", "point_towards", "goto_target",
                    "set_rotation_style", "set_drag_mode", "set_backdrop",
                    "go_to_layer", "change_layer", "set_sound_effect",
                    "clear_sound_effects", "for _each in", "incr_counter",
                    "clear_counter", "while not", "touching_color",
                    "backdrop_name", "backdrop_number"):
        assert snippet in code, f"缺少生成代码: {snippet}"
    assert "# TODO" not in code

    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](headless=True)
    sprite = namespace["Hero"]()
    runtime.add_sprite(sprite)
    try:
        runtime.start(max_frames=20)
        time.sleep(0.4)
        assert sprite.rotation_style == 'left-right'
        assert sprite.draggable is True
        assert sprite.total == 6, "for-each 应遍历列表 [1,2,3]"
        assert sprite.x == 3, "while 循环应执行到条件不成立"
        assert runtime.counter == 2, "清空后再自增两次"
        assert runtime.backdrop_number == 2
        assert runtime.backdrop_name == 'bg2'
        assert runtime.find_sprite('Hero') is sprite
        assert sprite._say_text == '2', "最后一条say应显示背景编号"
    finally:
        runtime.shutdown()

    print("  [PASS] 补充积木支持通过")
    return True


def test_more_blocks_supported():
    """补充积木：滑行到目标/切换背景并等待/声音特效变化/计数器与用户名表达式"""
    print("[测试32] 更多补充积木")

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {}, "lists": {}, "broadcasts": {}, "blocks": {},
        "comments": {}, "currentCostume": 0,
        "costumes": [
            {"name": "bg1", "dataFormat": "svg", "assetId": "", "md5ext": ""},
            {"name": "bg2", "dataFormat": "svg", "assetId": "", "md5ext": ""},
        ],
        "sounds": [], "volume": 100, "layerOrder": 0,
    }
    blocks = {
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("motion_glideto", "b3", "b1",
                    {"SECS": [1, [4, "0"]]}, {"TO": ["_random_", None]}),
        "b3": block("looks_switchbackdroptoandwait", "b4", "b2",
                    {}, {"BACKDROP": ["bg2", None]}),
        "b4": block("sound_changeeffectby", "b5", "b3",
                    {"VALUE": [1, [4, "10"]]}, {"SOUND_EFFECT": ["PAN", None]}),
        "b5": block("looks_say", None, "b4",
                    {"MESSAGE": [3, "j2", [10, ""]]}),
        "j2": block("operator_join", None, "b5",
                    {"STRING1": [3, "j1", [10, ""]],
                     "STRING2": [3, "user", [10, ""]]}),
        "j1": block("operator_join", None, "j2",
                    {"STRING1": [3, "cnt", [10, ""]],
                     "STRING2": [3, "loud", [10, ""]]}),
        "cnt": block("control_get_counter", None, "j1"),
        "loud": block("sensing_loud", None, "j1"),
        "user": block("sensing_username", None, "j2"),
    }
    project = {
        "targets": [
            stage,
            {
                "isStage": False, "name": "Hero", "variables": {}, "lists": {},
                "broadcasts": {}, "blocks": blocks, "comments": {},
                "currentCostume": 0, "costumes": [], "sounds": [],
                "visible": True, "x": 0, "y": 0, "size": 100,
                "direction": 90, "draggable": False,
                "rotationStyle": "all around", "volume": 100, "layerOrder": 1,
            },
        ],
        "monitors": [], "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "0.2.0", "agent": ""},
    }

    ir = parse_scratch_project(project)
    assert not ir.warnings, f"不应再有未支持积木: {ir.warnings}"
    code = generate_python(ir)
    for snippet in ("glide_to_target", "set_backdrop_and_wait",
                    "change_sound_effect", "self.get_counter()",
                    "self.username()", "self.loudness"):
        assert snippet in code, f"缺少生成代码: {snippet}"
    assert "# TODO" not in code

    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](headless=True)
    sprite = namespace["Hero"]()
    runtime.add_sprite(sprite)
    try:
        runtime.start(max_frames=40)
        import time
        time.sleep(0.4)
        assert runtime.backdrop_name == 'bg2'
        assert sprite._say_text == '00player', sprite._say_text
    finally:
        runtime.shutdown()

    print("  [PASS] 更多补充积木通过")
    return True


def test_svg_costume_and_dynamic_costume_name():
    """动态造型名应递归求值；SVG造型应能渲染；角色下方不再绘制名字"""
    print("[测试33] SVG造型与动态造型名")

    import time

    blocks = {
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("looks_switchcostumeto", None, "b1",
                    {"COSTUME": [3, "expr", "menu"]}),
        "expr": block("operator_letter_of", None, "b2",
                      {"STRING": [1, [10, "AB"]], "LETTER": [1, [4, "2"]]}),
        "menu": {**block("looks_costume", None, "b2", {},
                         {"COSTUME": ["A", None]}), "shadow": True},
    }
    project = make_project(blocks, name="SvgHero")
    project["targets"][0]["costumes"] = [
        {"name": "A", "dataFormat": "svg", "assetId": "a", "md5ext": "a.svg",
         "rotationCenterX": 10, "rotationCenterY": 26},
        {"name": "B", "dataFormat": "svg", "assetId": "b", "md5ext": "b.svg",
         "rotationCenterX": 10, "rotationCenterY": 26},
    ]

    ir = parse_scratch_project(project)
    code = generate_python(ir)
    assert "self.switch_costume(_sc_letter_of(" in code, \
        "动态造型名不能被当成block id字符串"
    assert "font.render(self.name" not in code, "不应再绘制角色名字标签"

    import tempfile
    folder = tempfile.mkdtemp()
    svg_path = os.path.join(folder, "a.svg")
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="52" '
                'viewBox="0,0,20,52"><g transform="translate(0,0)">'
                '<g fill="#82ff98" font-size="40">'
                '<text transform="translate(1,41) scale(0.9,0.9)" fill="#82ff98">'
                '<tspan x="0" dy="0">B</tspan></text></g></g></svg>')

    namespace = {"__file__": os.path.join(folder, "run.py")}
    exec(compile(code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](headless=True)
    sprite = namespace["SvgHero"]()
    runtime.add_sprite(sprite)
    try:
        image = runtime._load_image("a.svg")
        assert image is not None, "SVG造型应能被渲染"
        opaque = sum(1 for x in range(image.get_width())
                     for y in range(image.get_height())
                     if image.get_at((x, y)).a > 0)
        assert opaque > 0, "SVG文本应渲染出可见像素"
        runtime.start(max_frames=6)
        time.sleep(0.3)
        assert sprite.costume_name == "B", f"应切换到字母B，实际{sprite.costume_name}"
    finally:
        runtime.shutdown()

    print("  [PASS] SVG造型与动态造型名通过")
    return True


def test_stage_scripts_and_music_extension():
    """舞台脚本应参与运行；music扩展应能转换和执行"""
    print("[测试34] 舞台脚本与音乐扩展")

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {"g1": ["x", 0]}, "lists": {}, "broadcasts": {},
        "blocks": {
            "s1": block("event_whenflagclicked", "s2", None, top_level=True),
            "s2": block("data_setvariableto", "s3", "s1",
                        {"VALUE": [1, [4, "1"]]}, {"VARIABLE": ["x", "g1"]}),
            "s3": block("event_broadcast", "s4", "s2",
                        {"BROADCAST_INPUT": [1, [11, "go", "go_id"]]}),
            "s4": block("music_playNoteForBeats", "s5", "s3",
                        {"NOTE": [1, "n1"], "BEATS": [1, [4, "0"]]}),
            "n1": {**block("note", None, "s4", {}, {"NOTE": ["72", None]}),
                   "shadow": True},
            "s5": block("looks_switchbackdropto", None, "s4",
                        {}, {"BACKDROP": ["bg2", None]}),
        },
        "comments": {}, "currentCostume": 0,
        "costumes": [
            {"name": "bg1", "dataFormat": "svg", "assetId": "", "md5ext": ""},
            {"name": "bg2", "dataFormat": "svg", "assetId": "", "md5ext": ""},
        ],
        "sounds": [], "volume": 100, "layerOrder": 0,
    }
    hero = {
        "isStage": False, "name": "Hero", "variables": {}, "lists": {},
        "broadcasts": {},
        "blocks": {
            "h1": block("event_whenbroadcastreceived", "h2", None,
                        top_level=True, fields={"BROADCAST_OPTION": ["go", "go_id"]}),
            "h2": block("looks_say", None, "h1",
                        {"MESSAGE": [3, "hv", [10, ""]]}),
            "hv": block("data_variable", None, "h2", {}, {"VARIABLE": ["x", "g1"]}),
        },
        "comments": {}, "currentCostume": 0, "costumes": [], "sounds": [],
        "visible": True, "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "all around", "volume": 100, "layerOrder": 1,
    }
    project = {
        "targets": [stage, hero],
        "monitors": [], "extensions": ["music"],
        "meta": {"semver": "3.0.0", "vm": "0.2.0", "agent": ""},
    }

    ir = parse_scratch_project(project)
    assert not ir.warnings, f"音乐扩展不应再报未支持: {ir.warnings}"
    code = generate_python(ir)
    assert "class Stage(ScratchSprite)" in code
    assert "self.extension('music', 'music_playNoteForBeats'" in code
    assert "self.is_stage = True" in code

    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    stage_obj = namespace["Stage"]()
    hero_obj = namespace["Hero"]()
    runtime.add_sprite(stage_obj)
    runtime.add_sprite(hero_obj)
    import time
    try:
        runtime.start(max_frames=20)
        time.sleep(0.4)
        assert namespace["GLOBALS"]["x"] == 1, "舞台脚本应写入全局变量"
        assert runtime.backdrop_name == "bg2"
        assert hero_obj._say_text == "1", "角色应收到舞台广播"
        assert not hasattr(stage_obj, "_screen_rect"), "舞台不应被绘制"

        stage_obj.extension('music', 'music_setTempo', {'TEMPO': 120}, {})
        assert runtime.music_tempo == 120
        assert stage_obj.extension('music', 'music_getTempo', {}, {}) == 120
        stage_obj.extension('music', 'music_restForBeats', {'BEATS': 0}, {})
    finally:
        runtime.shutdown()

    print("  [PASS] 舞台脚本与音乐扩展通过")
    return True


def test_duplicate_hats_and_svg_text():
    """同一帽子事件的多脚本都要保留；SVG文字要画在形状之后"""
    print("[测试35] 同名事件脚本与SVG文字")

    blocks = {
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("data_setvariableto", None, "b1",
                    {"VALUE": [1, [4, "1"]]}, {"VARIABLE": ["a", "v_a"]}),
        "c1": block("event_whenflagclicked", "c2", None, top_level=True),
        "c2": block("data_setvariableto", None, "c1",
                    {"VALUE": [1, [4, "2"]]}, {"VARIABLE": ["b", "v_b"]}),
    }
    project = make_project(blocks, name="MultiHat")
    project["targets"][0]["variables"] = {"v_a": ["a", 0], "v_b": ["b", 0]}

    ir = parse_scratch_project(project)
    code = generate_python(ir)
    assert "def when_green_flag(self):" in code
    assert "def when_green_flag_2(self):" in code, "重复帽子事件应生成独立方法名"
    assert code.count("self._register('green_flag', self.when_green_flag") == 2
    assert code.count("def when_green_flag") == 2, "不能有同名方法覆盖"

    # SVG：白色矩形 + 黑色文字，文字应在矩形之后绘制
    import tempfile
    folder = tempfile.mkdtemp()
    svg = os.path.join(folder, "label.svg")
    with open(svg, "w", encoding="utf-8") as f:
        f.write('<svg xmlns="http://www.w3.org/2000/svg" width="120" height="40">'
                '<g transform="translate(0,0)">'
                '<rect x="0" y="0" width="120" height="40" fill="#ffffff"/>'
                '<text transform="translate(8,28)" font-size="20" fill="#000000">'
                '<tspan x="0" dy="0">文字Hi</tspan></text></g></svg>')

    namespace = {"__file__": os.path.join(folder, "run.py")}
    exec(compile(code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite = namespace["MultiHat"]()
    runtime.add_sprite(sprite)
    import time
    try:
        runtime.start(max_frames=10)
        time.sleep(0.3)
        assert sprite.a == 1 and sprite.b == 2, "两个绿旗脚本都应执行"
    finally:
        runtime.shutdown()

    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    try:
        image = runtime._load_image("label.svg")
        assert image is not None
        dark = 0
        for x in range(0, image.get_width(), 2):
            for y in range(0, image.get_height(), 2):
                pixel = image.get_at((x, y))
                if pixel.a > 0 and pixel.r < 60 and pixel.g < 60 and pixel.b < 60:
                    dark += 1
        assert dark > 0, "SVG文字应渲染出来"
    finally:
        runtime.shutdown()

    print("  [PASS] 同名事件脚本与SVG文字通过")
    return True


def test_effects_monitors_and_mask_touching():
    """颜色/亮度/透明度特效、监视器显示隐藏、像素级碰撞"""
    print("[测试36] 图形特效与细节转换")

    import tempfile
    folder = tempfile.mkdtemp()
    with open(os.path.join(folder, "box.svg"), "w", encoding="utf-8") as f:
        f.write('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20">'
                '<rect x="0" y="0" width="20" height="20" fill="#ff0000"/></svg>')

    project = make_project({
        "b1": block("event_whenflagclicked", None, None, top_level=True),
    }, name="Fx")
    project["targets"][0]["variables"] = {"v1": ["score", 7]}
    project["targets"][0]["costumes"] = [{
        "name": "box", "dataFormat": "svg", "assetId": "box",
        "md5ext": "box.svg", "rotationCenterX": 10, "rotationCenterY": 10,
    }]
    other = json.loads(json.dumps(project["targets"][0]))
    other["name"] = "Other"
    other["blocks"] = {}
    other["x"], other["y"] = 12, 0
    project["targets"].append(other)

    ir = parse_scratch_project(project)
    code = generate_python(ir)
    namespace = {"__file__": os.path.join(folder, "run.py")}
    exec(compile(code, "<generated>", "exec"), namespace)

    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite = namespace["Fx"]()
    neighbor = namespace["Other"]()
    runtime.add_sprite(sprite)
    runtime.add_sprite(neighbor)
    try:
        assert namespace["_sc_str"](1e-06) == '0.000001', "小数格式应贴近JS"
        runtime._draw()
        base = runtime.screen.get_at((240, 180))
        assert base.r > 200 and base.g < 60, f"基础造型应为红色: {base}"

        sprite.set_effect('COLOR', 100)   # 色相旋转180度，红->青
        runtime._draw()
        shifted = runtime.screen.get_at((240, 180))
        assert shifted.r < 80 and shifted.g > 150 and shifted.b > 150, \
            f"颜色特效应旋转色相: {shifted}"

        sprite.clear_effects()
        sprite.set_effect('BRIGHTNESS', 50)
        runtime._draw()
        bright = runtime.screen.get_at((240, 180))
        assert bright.g > 90, f"亮度特效应提亮: {bright}"

        sprite.clear_effects()
        sprite.set_effect('GHOST', 100)
        runtime._draw()
        invisible = runtime.screen.get_at((240, 180))
        assert invisible.r > 200 and invisible.g > 200, \
            f"透明度100应露出背景: {invisible}"
        sprite.clear_effects()
        runtime._draw()

        # 形状类特效（像素化）应能正常绘制
        sprite.set_effect('PIXELATE', 50)
        runtime._draw()
        assert runtime.screen.get_at((240, 180)).r > 200, "像素化后中心仍应为红色"
        sprite.clear_effects()
        runtime._draw()

        # 像素级碰撞：两者矩形有重叠但不接触时应为False
        assert runtime.touching(sprite, "Other") is True, "相邻造型应发生碰撞"
        neighbor.x = 100
        runtime._draw()
        assert runtime.touching(sprite, "Other") is False, "分开后不应碰撞"

        # 监视器显示/隐藏
        sprite.show_variable('score')
        entries = [m for m in runtime._all_monitors() if m.get('attr') == 'score']
        assert entries and entries[0]['visible'] is True
        runtime._draw_monitors()
        sprite.hide_variable('score')
        assert entries[0]['visible'] is False
    finally:
        runtime.shutdown()

    print("  [PASS] 图形特效与细节转换通过")
    return True


def test_turbowarp_options_and_rotation_center():
    """TurboWarp高级选项注释读取；造型旋转中心定位"""
    print("[测试37] TurboWarp选项与旋转中心")

    import tempfile
    folder = tempfile.mkdtemp()
    with open(os.path.join(folder, "dot.svg"), "w", encoding="utf-8") as f:
        f.write('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20">'
                '<rect x="0" y="0" width="20" height="20" fill="#ff0000"/></svg>')

    project = make_project({
        "b1": block("event_whenflagclicked", None, None, top_level=True),
    }, name="TwOpts")
    project["targets"][0]["comments"] = {
        "c1": {"text": '配置： {"framerate":60,"runtimeOptions":'
                       '{"fencing":false,"interpolation":true,'
                       '"cloneLimit":0,"hqPen":true,"warpTimer":0.25}} // _twconfig_'}
    }
    project["targets"][0]["costumes"] = [
        {"name": "a", "dataFormat": "svg", "assetId": "dot", "md5ext": "dot.svg",
         "rotationCenterX": 0, "rotationCenterY": 0},
        {"name": "b", "dataFormat": "svg", "assetId": "dot", "md5ext": "dot.svg",
         "rotationCenterX": 20, "rotationCenterY": 20},
    ]

    ir = parse_scratch_project(project)
    assert ir.runtime_options.get("framerate") == 60
    assert ir.runtime_options["runtimeOptions"]["fencing"] is False

    code = generate_python(ir)
    for snippet in ("parser.set_defaults(fps=60)",
                    "parser.set_defaults(fencing=False)",
                    "parser.set_defaults(interpolation=True)",
                    "parser.set_defaults(hq_pen=True)",
                    "parser.set_defaults(infinite_clones=True)",
                    "parser.set_defaults(warp_timer=0.25)"):
        assert snippet in code, f"缺少高级选项默认值: {snippet}"

    namespace = {"__file__": os.path.join(folder, "run.py")}
    exec(compile(code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite = namespace["TwOpts"]()
    runtime.add_sprite(sprite)
    try:
        sprite.visible = True
        sprite.x, sprite.y, sprite.size = 0, 0, 100
        sprite.costume_number = 1
        runtime._draw()
        assert sprite._screen_rect.topleft == (240, 180), \
            f"旋转中心(0,0)应让造型左上角对齐角色位置: {sprite._screen_rect}"
        sprite.costume_number = 2
        runtime._draw()
        assert sprite._screen_rect.topleft == (220, 160), \
            f"旋转中心(20,20)应向左上偏移: {sprite._screen_rect}"
    finally:
        runtime.shutdown()

    print("  [PASS] TurboWarp选项与旋转中心通过")
    return True


def test_list_out_of_range_reads():
    """列表越界读取应返回空字符串，而不是抛异常"""
    print("[测试38] 列表越界读取")

    project = make_project({
        "b1": block("event_whenflagclicked", None, None, top_level=True),
    }, name="ListSafe")
    code = generate_python(parse_scratch_project(project))
    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    item_of = namespace["_sc_item_of"]
    items = [10, 20, 30]
    assert item_of(items, 1) == 10
    assert item_of(items, 3) == 30
    assert item_of(items, 0) == ''
    assert item_of(items, 4) == ''
    assert item_of(items, 999) == ''
    assert item_of([], 1) == ''
    assert item_of(items, 'last') == 30
    assert item_of([], 'last') == ''
    assert item_of(items, 'random') in items
    assert item_of([], 'any') == ''
    # 并发缩短列表时也不能崩
    shrinking = [1, 2, 3]
    namespace["_sc_list_delete"](shrinking, 1)
    assert item_of(shrinking, 3) == ''

    print("  [PASS] 列表越界读取通过")
    return True


def test_general_python_mode():
    print("[测试39] 通用Python -> Scratch")
    from general_python import parse_general_project

    code = '''
total = 0
nums = [1, 2, 3, 4]
for n in nums:
    total += n
print("sum", total)

def fib(n):
    a = 0
    b = 1
    i = 0
    while i < n:
        t = a + b
        a = b
        b = t
        i += 1
    return a

x = fib(6)
print("fib", x)
'''
    project = parse_general_project(code, 'PyTest')
    assert project.sprites[0].is_stage, "通用模式必须生成舞台"
    assert project.assets, "必须输出默认造型资源"
    sprite = [item for item in project.sprites if not item.is_stage][0]
    assert sprite.costumes, "精灵必须有默认造型"

    data = write_scratch_project(project)
    assert data['targets'][0]['isStage']
    opcodes = {}
    for target in data['targets']:
        for block in target['blocks'].values():
            opcodes[block['opcode']] = opcodes.get(block['opcode'], 0) + 1
    for expected in ('event_whenflagclicked', 'control_repeat',
                     'data_lengthoflist', 'data_itemoflist',
                     'data_changevariableby', 'procedures_definition',
                     'procedures_call', 'control_repeat_until', 'looks_say'):
        assert expected in opcodes, f"缺少积木: {expected}"
    assert not project.warnings, f"简单脚本不应有未支持特性: {project.warnings}"
    definitions = [block for target in data['targets']
                   for block in target['blocks'].values()
                   if block['opcode'] == 'procedures_definition']
    assert definitions, "必须生成自制积木定义"
    assert all(block.get('topLevel') and block.get('x') is not None
               for block in definitions), "自制积木定义必须是带坐标的顶层脚本"
    print("  [PASS] 通用Python转换通过")
    return True


def test_general_python_more_syntax():
    print("[测试40] 通用Python更多语法")
    from general_python import parse_general_project

    code = '''
a = b = 2
a -= 1
a *= 3
a //= 2
a %= 2
nums = [1, 2, 3, 4]
del nums[0]
nums[0] = 20
count = 0
for i in range(0, 6, 2):
    count += i
n = 10
total = 0
for i in range(0, n, 3):
    total += i
print(f"count={count}, total={total}")
print("a=" + str(a))
print("in list:", 20 in nums, 99 not in nums)
print("chain:", 0 < a <= 3)
'''
    project = parse_general_project(code, 'SyntaxTest')
    assert not project.warnings, f"不应有未支持特性: {project.warnings}"
    data = write_scratch_project(project)
    opcodes = {}
    for target in data['targets']:
        for block in target['blocks'].values():
            opcodes[block['opcode']] = opcodes.get(block['opcode'], 0) + 1
    for expected in ('operator_mod', 'operator_mathop',
                     'data_deleteoflist', 'data_listcontainsitem',
                     'operator_and', 'operator_join'):
        assert expected in opcodes, f"缺少积木: {expected}"
    assert opcodes.get('data_setvariableto', 0) >= 3, "链式赋值应生成多个设为块"
    print("  [PASS] 通用Python更多语法通过")
    return True


def test_general_python_break_continue():
    print("[测试41] 通用Python break/continue")
    from general_python import parse_general_project

    code = '''
nums = []
for i in range(10):
    if i == 3:
        continue
    if i == 7:
        break
    nums.append(i)

total = 0
i = 0
while i < 10:
    i += 1
    if i % 2 == 0:
        continue
    if i > 7:
        break
    total += i

count = 0
for x in [1, 2, 3, 4, 5]:
    if x == 4:
        break
    count += x
print(nums, total, count)
'''
    project = parse_general_project(code, 'BreakTest')
    assert not project.warnings, f"不应有未支持特性: {project.warnings}"
    data = write_scratch_project(project)
    opcodes = {}
    variables = []
    for target in data['targets']:
        variables.extend(name for name, _ in target.get('variables', {}).values())
        for block in target['blocks'].values():
            opcodes[block['opcode']] = opcodes.get(block['opcode'], 0) + 1
    assert any(name.startswith('__py_break_') for name in variables)
    assert any(name.startswith('__py_continue_') for name in variables)
    assert 'control_repeat_until' in opcodes
    assert 'operator_or' in opcodes
    assert 'operator_not' in opcodes
    print("  [PASS] 通用Python break/continue 通过")
    return True


def test_general_python_builtins_and_methods():
    """通用模式：**、min/max/sum、列表方法、join、enumerate/字符串循环、列表拷贝"""
    print("[测试42] 通用Python内置函数与列表方法")
    from general_python import parse_general_project

    code = '''
nums = [3, 1, 4, 1, 5]
total = sum(nums)
lo = min(nums)
hi = max(nums)
low2 = min(3, 8)
high2 = max(3, 8)
nums.sort()
sorted_first = nums[0]
nums.reverse()
reversed_first = nums[0]
last = nums.pop()
idx = nums.index(4)
cnt = nums.count(4)
nums.remove(1)
remaining = len(nums)
power = 2 ** 5
power2 = 3 ** 2
mod_power = 2
mod_power **= 3
b = [10, 20, 30]
joined = "-".join(b)
has_ell = "ell" in "hello"
no_z = "z" not in "hello"
pi_part = math.pi
count = 0
for i, v in enumerate(b):
    count += i * v
chars = []
for ch in "abc":
    chars.append(ch)
indexes = []
for i, ch in enumerate("xy"):
    indexes.append(i)
alias = b
alias_lo = min(alias)
text = "abc"
out = ""
for ch in text:
    if ch == "b":
        continue
    out = out + ch
x, y = 1, 2
x, y = y, x
print("done")
'''
    project = parse_general_project(code, 'BatchTest')
    assert not project.warnings, f"不应有未支持特性: {project.warnings}"

    data = write_scratch_project(project)
    opcodes = {}
    for target in data['targets']:
        for block in target['blocks'].values():
            opcodes[block['opcode']] = opcodes.get(block['opcode'], 0) + 1
    for expected in ('operator_mathop', 'operator_contains', 'operator_join',
                     'data_itemoflist', 'data_replaceitemoflist',
                     'data_deleteoflist', 'data_lengthoflist',
                     'data_addtolist', 'control_repeat_until'):
        assert expected in opcodes, f"缺少积木: {expected}"

    # 端到端：sb3 -> Python -> pygame 运行时，验证真实执行结果
    exec_code = generate_python(parse_scratch_project(data))
    namespace = {}
    exec(compile(exec_code, "<generated>", "exec"), namespace)

    import time
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite = namespace["BatchTest"]()
    runtime.add_sprite(sprite)
    try:
        runtime.start(max_frames=4)
        time.sleep(0.2)
        expected_values = {
            'total': 14, 'lo': 1, 'hi': 5, 'low2': 3, 'high2': 8,
            'sorted_first': 1, 'reversed_first': 5, 'last': 1, 'idx': 2,
            'cnt': 1, 'remaining': 3, 'power': 32, 'power2': 9,
            'mod_power': 8, 'count': 80, 'alias_lo': 10, 'x': 2, 'y': 1,
        }
        for name, expected in expected_values.items():
            actual = getattr(sprite, name)
            assert float(actual) == float(expected), \
                f"{name}: 期望 {expected}, 实际 {actual}"
        assert str(sprite.joined) == '10-20-30', \
            f"join 结果不正确: {sprite.joined}"
        assert str(sprite.out) == 'ac', \
            f"字符串变量累加应为拼接: {sprite.out!r}"
        assert bool(sprite.has_ell) is True, "字符串包含应成立"
        assert bool(sprite.no_z) is True, "字符串不包含应成立"
        assert abs(float(sprite.pi_part) - math.pi) < 1e-9, "math.pi 应保真"
        assert list(sprite.chars) == ['a', 'b', 'c'], "字符串遍历结果不正确"
        assert [float(v) for v in sprite.indexes] == [0.0, 1.0], \
            "enumerate 下标应从 0 开始"
        assert [float(v) for v in sprite.nums] == [5.0, 4.0, 3.0], \
            "sort/reverse/pop/remove 后的列表不正确"
        assert [float(v) for v in sprite.alias] == [10.0, 20.0, 30.0], \
            "列表拷贝不应共享内容"
    finally:
        runtime.shutdown()

    print("  [PASS] 通用Python内置函数与列表方法通过")
    return True


def test_ask_input_box():
    """询问框：TEXTINPUT 输入、回车/确认按钮提交、可以连续询问"""
    print("[测试45] 询问框输入")

    blocks = {
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("sensing_askandwait", "b3", "b1",
                    {"QUESTION": [1, [10, "q1"]]}),
        "b3": block("looks_say", "b4", "b2", {"MESSAGE": [3, "a1", [10, ""]]}),
        "a1": block("sensing_answer", None, "b3"),
        "b4": block("sensing_askandwait", "b5", "b3",
                    {"QUESTION": [1, [10, "q2"]]}),
        "b5": block("looks_say", "b6", "b4", {"MESSAGE": [3, "a2", [10, ""]]}),
        "a2": block("sensing_answer", None, "b5"),
        "b6": block("sensing_askandwait", "b7", "b5",
                    {"QUESTION": [1, [10, "q3"]]}),
        "b7": block("looks_say", None, "b6", {"MESSAGE": [3, "a3", [10, ""]]}),
        "a3": block("sensing_answer", None, "b7"),
    }
    project = make_project(blocks, name="AskTest")
    code = generate_python(parse_scratch_project(project))
    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    pygame = namespace["pygame"]
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite = namespace["AskTest"]()
    runtime.add_sprite(sprite)
    sprite.run()
    runtime.green_flag()

    import time

    def pump_until(predicate, timeout=5.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            runtime.step()
            if predicate():
                return True
            time.sleep(0.01)
        return False

    try:
        assert pump_until(lambda: runtime.ask_pending), "第一次询问没有出现"
        # KEYDOWN 与 TEXTINPUT 同时到达时不能重复输入
        for ch in "hi":
            pygame.event.post(pygame.event.Event(
                pygame.KEYDOWN, key=ord(ch), unicode=ch, mod=0))
            pygame.event.post(pygame.event.Event(pygame.TEXTINPUT, text=ch))
        pygame.event.post(pygame.event.Event(
            pygame.KEYDOWN, key=pygame.K_KP_ENTER, unicode="\r", mod=0))
        assert pump_until(lambda: sprite._say_text == "hi"), \
            f"小键盘回车提交后回答错误: {sprite._say_text!r}"

        assert pump_until(lambda: runtime.ask_pending), "第二次询问没有出现"
        assert runtime.ask_buffer == "", "第二次询问应重置输入内容"
        # 只有 KEYDOWN（部分环境不发 TEXTINPUT）也必须能输入
        for ch in "ok":
            pygame.event.post(pygame.event.Event(
                pygame.KEYDOWN, key=ord(ch), unicode=ch, mod=0))
        bar = runtime._ask_rect()
        pygame.event.post(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=(bar.x + 20, bar.centery)))
        pygame.event.post(pygame.event.Event(
            pygame.MOUSEBUTTONUP, button=1, pos=(bar.x + 20, bar.centery)))
        for _ in range(3):
            runtime.step()
            time.sleep(0.01)
        assert runtime.ask_pending, "点击输入框本身不应提交"
        assert sprite._say_text != "ok"

        button = runtime._ask_button_rect()
        pygame.event.post(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=button.center))
        assert pump_until(lambda: sprite._say_text == "ok"), \
            f"点击确认按钮应提交: {sprite._say_text!r}"

        assert pump_until(lambda: runtime.ask_pending), "第三次询问没有出现"
        # 只有 TEXTINPUT（输入法上屏）
        for ch in "up":
            pygame.event.post(pygame.event.Event(pygame.TEXTINPUT, text=ch))
        # 模拟输入法吞掉 KEYDOWN，只收到回车松开
        pygame.event.post(pygame.event.Event(
            pygame.KEYUP, key=pygame.K_RETURN, unicode="", mod=0))
        assert pump_until(lambda: sprite._say_text == "up"), \
            f"回车松开兜底提交失败: {sprite._say_text!r}"
        assert pump_until(lambda: not runtime.ask_pending), \
            "第三次询问框应已关闭"
    finally:
        runtime.running = False
        runtime.shutdown()

    print("  [PASS] 询问框输入通过")
    return True


def test_mouse_clamp_and_fencing():
    """鼠标坐标超出舞台时取边界值；角色不能离开舞台（可关闭）"""
    print("[测试48] 鼠标边界与角色围栏")

    project = make_project({
        "b1": block("event_whenflagclicked", None, None, top_level=True),
    }, name="Fence")
    code = generate_python(parse_scratch_project(project))
    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite = namespace["Fence"]()
    runtime.add_sprite(sprite)
    try:
        # 鼠标超出舞台 -> 取最大/最小值
        assert runtime._screen_to_scratch((-100, -100)) == (-240, 180)
        assert runtime._screen_to_scratch((1000, 1000)) == (240, -180)
        assert runtime._screen_to_scratch((240, 180)) == (0, 0)

        # 角色不能离开舞台（无造型时按 10px 半宽计算）
        sprite.set_x(999)
        sprite.set_y(-999)
        assert sprite.x == 230 and sprite.y == -170, \
            f"角色应被约束在舞台内: {sprite.x},{sprite.y}"

        sprite.goto_xy(-999, 999)
        assert sprite.x == -230 and sprite.y == 170, \
            f"移到坐标也应受约束: {sprite.x},{sprite.y}"

        # 关闭 fencing（TurboWarp 高级选项）后可以离开舞台
        runtime.fencing = False
        sprite.set_x(999)
        assert sprite.x == 999, "关闭 fencing 后不应再限制坐标"
    finally:
        runtime.running = False
        runtime.shutdown()

    print("  [PASS] 鼠标边界与角色围栏通过")
    return True


def test_stage_clear_with_tiny_backdrop():
    """背景是 2x2 空白造型时，舞台也必须每帧清屏，否则输入框会残留"""
    print("[测试47] 小尺寸背景每帧清屏")

    project = make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("sensing_askandwait", None, "b1",
                    {"QUESTION": [1, [10, "q"]]}),
    }, name="TinyBg")
    code = generate_python(parse_scratch_project(project))
    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    pygame = namespace["pygame"]
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite = namespace["TinyBg"]()
    runtime.add_sprite(sprite)
    # 模拟 Scratch 默认的 2x2 空白背景
    runtime.background = pygame.Surface((2, 2), pygame.SRCALPHA)

    import time
    sprite.run()
    runtime.green_flag()
    try:
        deadline = time.time() + 4
        while time.time() < deadline and not runtime.ask_pending:
            runtime.step()
            time.sleep(0.01)
        assert runtime.ask_pending, "询问框没有出现"
        time.sleep(0.05)

        runtime.step()
        probe = (runtime.stage_width // 2, runtime.stage_height - 60)
        border = runtime.stage_surface.get_at(probe)
        assert tuple(border)[:3] == (90, 90, 90), \
            f"询问框边框应已画出: {border}"

        pygame.event.post(pygame.event.Event(
            pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r", mod=0))
        deadline = time.time() + 4
        while time.time() < deadline and runtime.ask_pending:
            runtime.step()
            time.sleep(0.01)
        assert not runtime.ask_pending, "回车应提交询问"

        runtime.step()
        cleared = runtime.stage_surface.get_at(probe)
        assert tuple(cleared)[:3] == (255, 255, 255), \
            f"提交后舞台应清屏为白色，不能残留输入框: {cleared}"
    finally:
        runtime.running = False
        runtime.shutdown()

    print("  [PASS] 小尺寸背景每帧清屏通过")
    return True


def test_runtime_debug_overlay():
    """F1 调试面板：显示询问状态和最近事件"""
    print("[测试46] 运行时调试面板")

    project = make_project({
        "b1": block("event_whenflagclicked", None, None, top_level=True),
    }, name="Dbg")
    code = generate_python(parse_scratch_project(project))
    assert "按 F1 显示/隐藏调试面板" in code

    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    pygame = namespace["pygame"]
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite = namespace["Dbg"]()
    runtime.add_sprite(sprite)
    try:
        pygame.event.post(pygame.event.Event(
            pygame.KEYDOWN, key=pygame.K_F1, unicode="", mod=0))
        runtime.step()
        assert runtime.debug_overlay is True, "F1 应打开调试面板"

        pygame.event.post(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=(10, 10)))
        pygame.event.post(pygame.event.Event(
            pygame.KEYDOWN, key=ord('a'), unicode='a', mod=0))
        runtime.step()
        joined = " | ".join(runtime._debug_events)
        assert "MOUSEDOWN" in joined, f"应记录鼠标事件: {joined}"
        assert "'a'" in joined, f"应记录按键事件: {joined}"

        runtime._draw()  # 面板渲染不能报错

        pygame.event.post(pygame.event.Event(
            pygame.KEYDOWN, key=pygame.K_F1, unicode="", mod=0))
        runtime.step()
        assert runtime.debug_overlay is False, "F1 应关闭调试面板"
    finally:
        runtime.running = False
        runtime.shutdown()

    print("  [PASS] 运行时调试面板通过")
    return True


def test_distortion_effects():
    """鱼眼/旋涡/像素化/马赛克：按 scratch-render 的坐标变换实现"""
    print("[测试44] 更多图形特效")

    project = make_project({
        "b1": block("event_whenflagclicked", None, None, top_level=True),
    }, name="Fx2")
    code = generate_python(parse_scratch_project(project))
    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    pygame = namespace["pygame"]
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite = namespace["Fx2"]()
    runtime.add_sprite(sprite)
    try:
        gradient = pygame.Surface((80, 80), pygame.SRCALPHA)
        for x in range(80):
            for y in range(80):
                gradient.set_at((x, y),
                                (x * 3 % 256, y * 3 % 256, (x + y) % 256, 255))
        original = pygame.image.tobytes(gradient, 'RGBA')

        # 没有特效时不产生新Surface
        assert sprite._distortion_image(gradient) is gradient

        # 像素化：每 10 像素一个块，块内取值一致
        sprite.set_effect('PIXELATE', 100)
        pixelated = sprite._distortion_image(gradient)
        assert pixelated.get_at((3, 3)) == pixelated.get_at((7, 7)), \
            "同一像素块内颜色应一致"
        assert pixelated.get_at((3, 3)) != gradient.get_at((3, 3)), \
            "像素化应改变取样位置"

        # 马赛克：值 10 对应 2x2 平铺
        sprite.clear_effects()
        sprite.set_effect('MOSAIC', 10)
        mosaic = sprite._distortion_image(gradient)
        assert mosaic.get_at((5, 5)) == mosaic.get_at((45, 5)), \
            "马赛克应在水平方向重复"
        assert mosaic.get_at((5, 5)) == mosaic.get_at((5, 45)), \
            "马赛克应在垂直方向重复"

        # 旋涡与鱼眼：无 numpy 时允许跳过（返回原图）
        try:
            import numpy  # noqa: F401
            has_numpy = True
        except ImportError:
            has_numpy = False

        sprite.clear_effects()
        sprite.set_effect('WHIRL', 100)
        whirled = sprite._distortion_image(gradient)
        if has_numpy:
            assert pygame.image.tobytes(whirled, 'RGBA') != original, \
                "旋涡特效应改变图像"

        sprite.clear_effects()
        sprite.set_effect('FISHEYE', 100)
        fisheye = sprite._distortion_image(gradient)
        if has_numpy:
            assert pygame.image.tobytes(fisheye, 'RGBA') != original, \
                "鱼眼特效应改变图像"

        # 缩放等值（0）时恢复原图
        sprite.clear_effects()
        assert sprite._distortion_image(gradient) is gradient
    finally:
        runtime.shutdown()

    print("  [PASS] 更多图形特效通过")
    return True


def test_chinese_sprite_instance_name():
    """中文角色名 lower() 后与类名相同，不能被 main() 的局部变量遮蔽"""
    print("[测试43] 中文角色名的实例命名")

    project = make_project({
        "b1": block("event_whenflagclicked", None, None, top_level=True),
    }, name="角色1")
    code = generate_python(parse_scratch_project(project))

    lines = {line.strip() for line in code.splitlines()}
    assert "角色1 = 角色1()" not in lines, \
        "main() 里不能出现自我遮蔽的赋值"
    assert "inst_角色1 = 角色1()" in lines, "中文角色名应加 inst_ 前缀"

    # 实际执行 main()，确认不再抛 UnboundLocalError
    namespace = {"__file__": os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "generated_run.py")}
    exec(compile(code, "<generated>", "exec"), namespace)
    namespace["main"](["--headless", "--frames", "1", "--no-audio"])

    print("  [PASS] 中文角色名的实例命名通过")
    return True


def main():
    """运行所有测试"""
    print("=" * 60)
    print("Scratch 3.0 <-> Python 双向转换器 测试")
    print("=" * 60)
    
    tests = [
        test_basic_scratch_to_python,
        test_scratch_loop_to_python,
        test_scratch_variables_to_python,
        test_python_to_scratch,
        test_roundtrip_scratch,
        test_expressions,
        test_if_else,
        test_real_sb3_literal_formats,
        test_event_script_wrapper,
        test_procedure_roundtrip,
        test_multi_sprite_blocks_isolated,
        test_list_contents_expression,
        test_list_operations_roundtrip,
        test_item_number_of_list,
        test_broadcast_name_with_space,
        test_undeclared_variable_is_created,
        test_clone_hat_block,
        test_orphan_blocks_ignored,
        test_scratch_runtime_semantics,
        test_procedure_missing_args_default_empty,
        test_empty_string_argument_preserved,
        test_pygame_runtime_runs_generated_script,
        test_generated_cli_mixed_arguments,
        test_sb3_assets_extracted,
        test_turbowarp_warp_procedure_fidelity,
        test_turbowarp_custom_reporter,
        test_turbowarp_pen_extension_runtime,
        test_turbowarp_runtime_options_extension,
        test_turbowarp_extension_roundtrip_and_cli,
        test_global_variables_and_monitor_labels,
        test_extra_blocks_supported,
        test_more_blocks_supported,
        test_svg_costume_and_dynamic_costume_name,
        test_stage_scripts_and_music_extension,
        test_duplicate_hats_and_svg_text,
        test_effects_monitors_and_mask_touching,
        test_turbowarp_options_and_rotation_center,
        test_list_out_of_range_reads,
        test_general_python_mode,
        test_general_python_more_syntax,
        test_general_python_break_continue,
        test_general_python_builtins_and_methods,
        test_distortion_effects,
        test_ask_input_box,
        test_mouse_clamp_and_fencing,
        test_stage_clear_with_tiny_backdrop,
        test_runtime_debug_overlay,
        test_chinese_sprite_instance_name,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  [FAIL] 测试失败: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print()
    print("=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败, 共 {len(tests)} 个测试")
    print("=" * 60)
    
    return failed == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
