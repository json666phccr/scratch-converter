# -*- coding: utf-8 -*-
"""由 test_all.py 拆分出的测试模块"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import *


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


TESTS = [
    test_procedure_roundtrip,
    test_multi_sprite_blocks_isolated,
    test_list_contents_expression,
    test_list_operations_roundtrip,
    test_item_number_of_list,
    test_broadcast_name_with_space,
    test_undeclared_variable_is_created,
    test_clone_hat_block,
    test_orphan_blocks_ignored,
]
