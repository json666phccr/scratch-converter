# -*- coding: utf-8 -*-
"""由 test_all.py 拆分出的测试模块"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import *


def test_tween_extension():
    """Tween 补间扩展：缓动计算、变量/坐标/属性补间"""
    print("[测试60] Tween 补间扩展")

    import time

    project = make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("jeremygamerTweening_tweenVariable", "b3", "b1",
                    inputs={"VALUE": [1, [4, "100"]],
                            "SEC": [1, [4, "0.12"]],
                            "MODE": [1, [10, "linear"]],
                            "DIRECTION": [1, [10, "in"]]},
                    fields={"VAR": ["var1", None]}),
        "b3": block("jeremygamerTweening_tweenProperty", None, "b2",
                    inputs={"VALUE": [1, [4, "50"]],
                            "SEC": [1, [4, "0"]],
                            "MODE": [1, [10, "linear"]],
                            "DIRECTION": [1, [10, "in"]]},
                    fields={"PROPERTY": ["x position", None]}),
    }, name="Tween")
    project["targets"][0]["variables"] = {"var1": ["score", 0]}
    project["extensions"] = ["jeremygamerTweening"]

    code = generate_python(parse_scratch_project(project))
    assert "'VAR': 'score'" in code, "Tween 变量ID应转换为变量名"
    assert "jeremygamerTweening" in code

    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite = namespace["Tween"]()
    runtime.add_sprite(sprite)
    try:
        def call(opcode, inputs=None, fields=None):
            return sprite.extension('jeremygamerTweening', opcode,
                                    inputs or {}, fields or {})

        assert abs(call('jeremygamerTweening_tweenValue',
                        {'MODE': 'linear', 'DIRECTION': 'in',
                         'START': 0, 'END': 100, 'AMOUNT': 25}) - 25) < 1e-6
        assert abs(call('jeremygamerTweening_tweenValue',
                        {'MODE': 'quad', 'DIRECTION': 'out',
                         'START': 0, 'END': 100, 'AMOUNT': 50}) - 75) < 1e-6
        sine = call('jeremygamerTweening_tweenValue',
                    {'MODE': 'sine', 'DIRECTION': 'in',
                     'START': 0, 'END': 100, 'AMOUNT': 50})
        assert abs(sine - 29.2893) < 0.01
        assert abs(call('jeremygamerTweening_tweenValue',
                        {'MODE': 'nope', 'DIRECTION': 'in',
                         'START': 10, 'END': 20, 'AMOUNT': 50}) - 15) < 1e-6

        sprite.run()
        runtime.green_flag()
        for _ in range(50):
            runtime.step()
            time.sleep(0.005)
        assert abs(sprite.score - 100) < 1e-6, "变量补间应到达目标值"
        assert abs(sprite.x - 50) < 1e-6, "坐标补间应到达目标值"

        call('jeremygamerTweening_tweenXY',
             {'X': -30, 'Y': 40, 'SEC': 0, 'MODE': 'linear', 'DIRECTION': 'in'})
        assert abs(sprite.x + 30) < 1e-6 and abs(sprite.y - 40) < 1e-6
    finally:
        runtime.running = False
        runtime.shutdown()

    print("  [PASS] Tween 补间扩展通过")
    return True


def test_clones_plus_extension():
    """Clones+ 扩展：带变量克隆、克隆帽子、变量/属性读写与删除"""
    print("[测试61] Clones+ 克隆+ 扩展")

    import time

    project = make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("lmsclonesplus_createCloneOfMyselfWithVar", None, "b1",
                    fields={"INPUTA": ["vid", None],
                            "INPUTB": ["7", None]}),
        "h1": block("lmsclonesplus_whenCloneStartsWithVar", "h2", None,
                    top_level=True,
                    fields={"INPUTA": ["vid", None],
                            "INPUTB": ["7", None]}),
        "h2": block("data_setvariableto", None, "h1",
                    inputs={"VALUE": [1, [10, "yes"]]},
                    fields={"VARIABLE": ["hat", "hatid"]}),
    }, name="CloneSprite")
    project["targets"][0]["variables"] = {
        "vid": ["id", 0], "hatid": ["hat", 0],
    }
    project["extensions"] = ["lmsclonesplus"]

    parsed = parse_scratch_project(project)
    code = generate_python(parsed)
    assert "'INPUTA': 'id'" in code, "克隆变量ID应转换为变量名"
    assert "_register_extension_hat('lmsclonesplus'" in code

    written = write_scratch_project(parse_scratch_project(project))
    opcodes = [item.get("opcode") for target in written["targets"]
               for item in target["blocks"].values()]
    assert "lmsclonesplus_whenCloneStartsWithVar" in opcodes, "帽子块应能写回sb3"
    assert "lmsclonesplus" in written.get("extensions", [])

    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite = namespace["CloneSprite"]()
    runtime.add_sprite(sprite)
    try:
        def call(opcode, inputs=None, fields=None):
            return sprite.extension('lmsclonesplus', opcode,
                                    inputs or {}, fields or {})

        sprite.run()
        runtime.green_flag()
        for _ in range(15):
            runtime.step()
            time.sleep(0.004)

        clones = [item for item in runtime.sprites
                  if getattr(item, '_is_clone', False)]
        assert len(clones) == 1, "应创建一个克隆体"
        clone = clones[0]
        assert str(clone.id) == '7', "克隆体应带上指定变量值"
        assert clone.hat == 'yes', "带变量克隆帽子应在新克隆体上触发"

        assert call('lmsclonesplus_cloneCount') == 1
        assert call('lmsclonesplus_spriteCloneCount',
                    {'INPUT': 'CloneSprite'}) == 1
        assert call('lmsclonesplus_cloneExists',
                    {'INPUTA': 'id', 'INPUTB': 7}) is True
        assert str(call('lmsclonesplus_getVariableOfClone',
                        {'INPUTA': 'id', 'INPUTB': 'id',
                         'INPUTC': 7})) == '7'
        assert call('lmsclonesplus_getThingOfClone',
                    {'INPUTA': 'x position', 'INPUTB': 'id',
                     'INPUTC': 7}) == clone.x
        assert call('lmsclonesplus_getVariableOfMainSprite',
                    {'INPUT': 'hat'}) == 0

        call('lmsclonesplus_setVariableOfClone',
             {'INPUTA': 'hat', 'INPUTB': 'done',
              'INPUTC': 'id', 'INPUTD': 7})
        assert clone.hat == 'done'
        call('lmsclonesplus_setVariableOfMainSprite',
             {'INPUTA': 'hat', 'INPUTB': 'main'})
        assert sprite.hat == 'main'
        assert call('lmsclonesplus_isClone') is False

        call('lmsclonesplus_deleteCloneWithVar',
             {'INPUTA': 'id', 'INPUTB': 7})
        assert not [item for item in runtime.sprites
                    if getattr(item, '_is_clone', False)], "克隆体应被删除"
        assert call('lmsclonesplus_cloneCount') == 0
    finally:
        runtime.running = False
        runtime.shutdown()

    print("  [PASS] Clones+ 克隆+ 扩展通过")
    return True


def test_looks_plus_extension():
    """Looks+ 扩展：跨角色显示/图层/特效/造型信息/快照"""
    print("[测试62] Looks+ 外观+ 扩展")

    import tempfile

    project = make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("lmsLooksPlus_showSprite", None, "b1",
                    inputs={"TARGET": [1, "m1"]}),
        "m1": block("lmsLooksPlus_menu_spriteMenu", None, None,
                    fields={"spriteMenu": ["B", None]}),
    }, name="A")
    project["targets"][0]["blocks"]["m1"]["shadow"] = True
    sprite_a = project["targets"][0]
    sprite_a["costumes"] = [{
        "name": "png1", "md5ext": "abc.png", "dataFormat": "png",
        "rotationCenterX": 16, "rotationCenterY": 10,
    }]
    sprite_b = json.loads(json.dumps(sprite_a))
    sprite_b["name"] = "B"
    sprite_b["variables"] = {}
    sprite_b["costumes"] = [{
        "name": "svg1", "md5ext": "svg1.svg", "dataFormat": "svg",
        "rotationCenterX": 5, "rotationCenterY": 6,
    }]
    project["targets"].append(sprite_b)
    project["extensions"] = ["lmsLooksPlus"]

    code = generate_python(parse_scratch_project(project))
    assert "'TARGET': 'B'" in code, "菜单shadow积木应解析成角色名"
    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)

    assets = tempfile.mkdtemp()
    runtime = namespace["ScratchRuntime"](headless=True, audio=False,
                                          assets_dir=assets)
    sprite_a_obj = namespace["A"]()
    sprite_b_obj = namespace["B"]()
    runtime.add_sprite(sprite_a_obj)
    runtime.add_sprite(sprite_b_obj)

    try:
        import pygame
        pygame.image.save(pygame.Surface((32, 20), pygame.SRCALPHA),
                          os.path.join(assets, "abc.png"))
        with open(os.path.join(assets, "svg1.svg"), "w", encoding="utf-8") as handle:
            handle.write('<svg xmlns="http://www.w3.org/2000/svg" '
                         'fill="#FCB1E3"><rect width="10" height="10"/></svg>')

        def call(opcode, inputs=None, fields=None):
            return sprite_a_obj.extension('lmsLooksPlus', opcode,
                                          inputs or {}, fields or {})

        assert call('lmsLooksPlus_spriteLayerNumber',
                    {'TARGET': 'A'}) == 1
        assert call('lmsLooksPlus_spriteLayerNumber',
                    {'TARGET': 'B'}) == 2
        call('lmsLooksPlus_hideSprite', {'TARGET': 'B'})
        assert sprite_b_obj.visible is False
        assert call('lmsLooksPlus_spriteVisible',
                    {'TARGET': 'B'}) is False
        call('lmsLooksPlus_showSprite', {'TARGET': 'B'})
        assert sprite_b_obj.visible is True

        call('lmsLooksPlus_setLayerTo',
             {'TARGET': 'B', 'LAYER': 1})
        assert call('lmsLooksPlus_spriteLayerNumber',
                    {'TARGET': 'B'}) == 1
        assert call('lmsLooksPlus_spriteLayerNumber',
                    {'TARGET': 'A'}) == 2

        sprite_b_obj.set_effect('ghost', 40)
        assert call('lmsLooksPlus_effectValue',
                    {'TARGET': 'B', 'EFFECT': 'ghost'}) == 40
        assert call('lmsLooksPlus_targetCostumeNumber',
                    {'TARGET': 'B'}) == 1
        assert call('lmsLooksPlus_costumeAttribute',
                    {'COSTUME': 'png1'}, {'ATTRIBUTE': 'width'}) == 32
        assert call('lmsLooksPlus_costumeAttribute',
                    {'COSTUME': 'png1'}, {'ATTRIBUTE': 'height'}) == 20
        assert call('lmsLooksPlus_costumeAttribute',
                    {'COSTUME': 'png1'}, {'ATTRIBUTE': 'format'}) == 'png'
        assert call('lmsLooksPlus_costumeAttribute',
                    {'COSTUME': 'png1'},
                    {'ATTRIBUTE': 'rotationCenterX'}) == 16

        assert call('lmsLooksPlus_replaceColors',
                    {'COLOR1': '#FCB1E3', 'COLOR2': '#000000',
                     'SVG': '<svg fill="#FCB1E3"/>'}) == \
            '<svg fill="#000000"/>'
        assert call('lmsLooksPlus_colorHex',
                    {'COLOR': '#FFD983'}) == '#FFD983'

        content = call('lmsLooksPlus_costumeContent',
                       {'CONTENT': 'content', 'COSTUME': 1, 'TARGET': 'B'})
        assert 'FCB1E3' in content
        data_uri = call('lmsLooksPlus_costumeContent',
                        {'CONTENT': 'dataURI', 'COSTUME': 1, 'TARGET': 'B'})
        assert data_uri.startswith('data:image/svg+xml;base64,')

        sprite_b_obj.extension(
            'lmsLooksPlus', 'lmsLooksPlus_replaceCostumeContent',
            {'COSTUME': 1, 'CONTENT': '<svg fill="#123456"/>'}, {})
        replaced = call('lmsLooksPlus_costumeContent',
                        {'CONTENT': 'content', 'COSTUME': 1, 'TARGET': 'B'})
        assert '#123456' in replaced, "替换后的造型内容应可读取"
        sprite_b_obj.extension(
            'lmsLooksPlus', 'lmsLooksPlus_restoreCostumeContent',
            {'COSTUME': 1}, {})
        restored = call('lmsLooksPlus_costumeContent',
                        {'CONTENT': 'content', 'COSTUME': 1, 'TARGET': 'B'})
        assert 'FCB1E3' in restored, "恢复后应回到原始SVG内容"

        snapshot = call('lmsLooksPlus_snapshotStage')
        assert snapshot.startswith('data:image/png;base64,')
        assert len(snapshot) > 100
    finally:
        runtime.running = False
        runtime.shutdown()

    print("  [PASS] Looks+ 外观+ 扩展通过")
    return True


def test_more_events_extension():
    """More Events 扩展：forever/每隔帧/值变化/按键帽子与广播传数据"""
    print("[测试63] More Events 更多事件扩展")

    import time

    project = make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("data_setvariableto", None, "b1",
                    inputs={"VALUE": [1, [10, "a"]]},
                    fields={"VARIABLE": ["watch", "wid"]}),
        "h1": block("lmsMoreEvents_forever", "h1b", None, top_level=True),
        "h1b": block("data_changevariableby", None, "h1",
                     inputs={"VALUE": [1, [4, "1"]]},
                     fields={"VARIABLE": ["counter", "cid"]}),
        "h2": block("lmsMoreEvents_everyDuration", "h2b", None,
                    top_level=True,
                    inputs={"DURATION": [1, [4, "2"]]}),
        "h2b": block("data_changevariableby", None, "h2",
                     inputs={"VALUE": [1, [4, "1"]]},
                     fields={"VARIABLE": ["every", "eid"]}),
        "h3": block("lmsMoreEvents_whenValueChanged", "h3b", None,
                    top_level=True,
                    inputs={"INPUT": [3, "v3"]}),
        "h3b": block("data_changevariableby", None, "h3",
                     inputs={"VALUE": [1, [4, "1"]]},
                     fields={"VARIABLE": ["changed", "chid"]}),
        "v3": block("data_variable", None, "h3",
                    fields={"VARIABLE": ["watch", "wid"]}),
        "h4": block("lmsMoreEvents_whenKeyAction", "h4b", None,
                    top_level=True,
                    inputs={"KEY_OPTION": [1, "km"],
                            "ACTION": [1, [10, "hit"]]}),
        "km": block("lmsMoreEvents_menu_keyboardButtons", None, None,
                    fields={"keyboardButtons": ["space", None]}),
        "h4b": block("data_changevariableby", None, "h4",
                     inputs={"VALUE": [1, [4, "1"]]},
                     fields={"VARIABLE": ["hits", "hid"]}),
        "h5": block("event_whenbroadcastreceived", "h5b", None,
                    top_level=True,
                    fields={"BROADCAST_OPTION": ["msg", "msgid"]}),
        "h5b": block("data_setvariableto", None, "h5",
                     inputs={"VALUE": [3, "d1"]},
                     fields={"VARIABLE": ["received", "rid"]}),
        "d1": block("lmsMoreEvents_receivedData", None, "h5b"),
        "h6": block("lmsMoreEvents_whileTrueFalse", "h6b", None,
                    top_level=True,
                    inputs={"CONDITION": [2, "c6"]},
                    fields={"STATE": ["true", None]}),
        "c6": block("operator_equals", None, "h6",
                    inputs={"OPERAND1": [3, "g6"],
                            "OPERAND2": [1, [10, "1"]]}),
        "g6": block("data_variable", None, "c6",
                    fields={"VARIABLE": ["gate", "gid"]}),
        "h6b": block("data_changevariableby", None, "h6",
                     inputs={"VALUE": [1, [4, "1"]]},
                     fields={"VARIABLE": ["loops", "lid2"]}),
        "h7": block("lmsMoreEvents_whenStopClicked", "h7b", None,
                    top_level=True),
        "h7b": block("data_changevariableby", None, "h7",
                     inputs={"VALUE": [1, [4, "1"]]},
                     fields={"VARIABLE": ["stopped", "sid"]}),
    }, name="Events")
    project["targets"][0]["blocks"]["km"]["shadow"] = True
    project["targets"][0]["variables"] = {
        "wid": ["watch", 'a'], "cid": ["counter", 0],
        "eid": ["every", 0], "chid": ["changed", 0],
        "hid": ["hits", 0], "rid": ["received", ''],
        "gid": ["gate", 1], "lid2": ["loops", 0], "sid": ["stopped", 0],
    }
    project["extensions"] = ["lmsMoreEvents"]

    code = generate_python(parse_scratch_project(project))
    assert "self._register_extension_hat('lmsMoreEvents'" in code
    assert "when_forever" in code and "every_frames" in code

    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite = namespace["Events"]()
    runtime.add_sprite(sprite)
    try:
        sprite.run()
        runtime.green_flag()
        for _ in range(40):
            if sprite.counter >= 5 and sprite.every >= 3:
                break
            runtime.step()
            time.sleep(0.003)
        assert sprite.counter >= 5, "forever 帽子应反复执行"
        assert sprite.every >= 3, "每隔N帧帽子应触发"
        assert sprite.changed == 0, "值没变时不应触发"

        sprite.watch = 'b'
        for _ in range(10):
            if sprite.changed >= 1:
                break
            runtime.step()
            time.sleep(0.004)
        assert sprite.changed >= 1, "值变化帽子应触发"

        runtime.keys.add('space')
        for _ in range(10):
            runtime.step()
            time.sleep(0.003)
            if sprite.hits >= 1:
                break
        assert sprite.hits == 1, "按键按下帽子应触发一次"
        runtime.keys.discard('space')
        runtime.step()
        runtime.keys.add('space')
        for _ in range(10):
            runtime.step()
            time.sleep(0.003)
            if sprite.hits >= 2:
                break
        assert sprite.hits == 2, "再次按下应再次触发"

        sprite.extension('lmsMoreEvents', 'lmsMoreEvents_broadcastData',
                         {'BROADCAST_OPTION': 'msg', 'DATA': 'hello'}, {})
        for _ in range(5):
            runtime.step()
            time.sleep(0.003)
        assert sprite.received == 'hello', "广播应把数据传给接收脚本"

        assert sprite.loops > 0, "while 帽子应在条件为真时反复运行"
        sprite.gate = 0
        for _ in range(4):
            runtime.step()
            time.sleep(0.003)
        stopped_at = sprite.loops
        for _ in range(4):
            runtime.step()
            time.sleep(0.003)
        assert sprite.loops == stopped_at, "条件变假后 while 脚本应停止"

        runtime.stop_clicked()
        for _ in range(5):
            runtime.step()
            time.sleep(0.003)
        assert sprite.stopped >= 1, "点击停止按钮应触发停止帽子"
    finally:
        runtime.running = False
        runtime.shutdown()

    print("  [PASS] More Events 更多事件扩展通过")
    return True


def test_temporary_variables_extension():
    """Temporary Variables 扩展：线程变量/运行时变量/循环与旧版变量"""
    print("[测试64] Temporary Variables 临时变量扩展")

    import time

    project = make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("lmsTempVars2_forEachThreadVariable", None, "b1",
                    inputs={"VAR": [1, [10, "i"]],
                            "NUM": [1, [4, "3"]],
                            "SUBSTACK": [2, "b3"]}),
        "b3": block("data_addtolist", None, "b2",
                    inputs={"ITEM": [3, "e1"]},
                    fields={"LIST": ["values", "lid"]}),
        "e1": block("lmsTempVars2_getThreadVariable", None, "b3",
                    inputs={"VAR": [1, [10, "i"]]}),
    }, name="Temp")
    project["targets"][0]["lists"] = {"lid": ["values", []]}
    project["extensions"] = ["lmsTempVars2"]

    code = generate_python(parse_scratch_project(project))
    assert "_ext_temp_index" in code, "循环积木应生成Python for循环"
    assert "lmsTempVars2_getThreadVariable" in code

    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite = namespace["Temp"]()
    runtime.add_sprite(sprite)
    try:
        def call(opcode, inputs=None, fields=None):
            return sprite.extension('lmsTempVars2', opcode,
                                    inputs or {}, fields or {})

        sprite.run()
        runtime.green_flag()
        for _ in range(15):
            runtime.step()
            time.sleep(0.003)
        assert sprite.values == [1, 2, 3], "for 循环应把线程变量逐个写入列表"

        call('lmsTempVars2_setThreadVariable',
             {'VAR': 'x', 'STRING': '5'})
        assert call('lmsTempVars2_getThreadVariable', {'VAR': 'x'}) == '5'
        call('lmsTempVars2_changeThreadVariable', {'VAR': 'x', 'NUM': 2})
        assert call('lmsTempVars2_getThreadVariable', {'VAR': 'x'}) == 7
        assert call('lmsTempVars2_threadVariableExists',
                    {'VAR': 'x'}) is True

        call('lmsTempVars2_setRuntimeVariable',
             {'VAR': 'r', 'STRING': '4'})
        call('lmsTempVars2_changeRuntimeVariable',
             {'VAR': 'r', 'NUM': 3})
        assert call('lmsTempVars2_getRuntimeVariable', {'VAR': 'r'}) == 7
        assert call('lmsTempVars2_runtimeVariableExists',
                    {'VAR': 'r'}) is True
        assert call('lmsTempVars2_listRuntimeVariables') == 'r'
        call('lmsTempVars2_deleteRuntimeVariable', {'VAR': 'r'})
        assert call('lmsTempVars2_runtimeVariableExists',
                    {'VAR': 'r'}) is False

        call('lmsTempVars2_setRuntimeVariable',
             {'VAR': 'reset', 'STRING': '1'})
        runtime.green_flag()
        assert call('lmsTempVars2_getRuntimeVariable',
                    {'VAR': 'reset'}) == '', "绿旗应清空运行时变量"

        legacy = lambda opcode, inputs=None: sprite.extension(
            'lmstempvars', opcode, inputs or {}, {})
        legacy('lmstempvars_setVariableTo',
               {'INPUTA': 'v', 'INPUTB': '3'})
        legacy('lmstempvars_changeVariableBy',
               {'INPUTA': 'v', 'INPUTB': '2'})
        assert legacy('lmstempvars_getVariable', {'INPUT': 'v'}) == 5
        assert legacy('lmstempvars_listVariables') == 'v'
        legacy('lmstempvars_deleteAllVariables')
        assert legacy('lmstempvars_getVariable', {'INPUT': 'v'}) == ''
    finally:
        runtime.running = False
        runtime.shutdown()

    print("  [PASS] Temporary Variables 临时变量扩展通过")
    return True


TESTS = [
    test_tween_extension,
    test_clones_plus_extension,
    test_looks_plus_extension,
    test_more_events_extension,
    test_temporary_variables_extension,
]
