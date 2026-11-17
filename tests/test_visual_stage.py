# -*- coding: utf-8 -*-
"""由 test_all.py 拆分出的测试模块"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import *


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


TESTS = [
    test_global_variables_and_monitor_labels,
    test_extra_blocks_supported,
    test_more_blocks_supported,
    test_svg_costume_and_dynamic_costume_name,
    test_stage_scripts_and_music_extension,
    test_duplicate_hats_and_svg_text,
    test_effects_monitors_and_mask_touching,
    test_turbowarp_options_and_rotation_center,
    test_list_out_of_range_reads,
]
