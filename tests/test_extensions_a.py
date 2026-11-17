# -*- coding: utf-8 -*-
"""由 test_all.py 拆分出的测试模块"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import *


def test_text2speech_extension():
    """text2speech：朗读调用与嗓音/语言切换"""
    print("[测试52] 文字朗读扩展")

    project = make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("text2speech_speakAndWait", None, "b1",
                    inputs={"WORDS": [1, [10, "你好"]]}),
    }, name="TTS")
    project["extensions"] = ["text2speech"]

    code = generate_python(parse_scratch_project(project))
    assert "'text2speech': _extension_text2speech" in code
    assert "'text2speech_speakAndWait'" in code

    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite = namespace["TTS"]()
    runtime.add_sprite(sprite)
    spoken = []
    runtime._speak_blocking = spoken.append
    try:
        assert runtime.tts_voice == 'alto' and runtime.tts_language == 'English'
        sprite.extension('text2speech', 'text2speech_speakAndWait',
                         {'WORDS': '你好'}, {})
        assert spoken == ['你好'], f"朗读内容不正确: {spoken}"

        sprite.extension('text2speech', 'text2speech_setVoice', {},
                         {'VOICE': 'giant'})
        assert runtime.tts_voice == 'giant'
        sprite.extension('text2speech', 'text2speech_setLanguage', {},
                         {'LANGUAGE': '简体中文'})
        assert runtime.tts_language == '简体中文'
    finally:
        runtime.running = False
        runtime.shutdown()

    print("  [PASS] 文字朗读扩展通过")
    return True


def test_stretch_extension():
    """角色拉伸：设置/增加 x、y 拉伸，并作用到渲染与舞台围栏"""
    print("[测试53] 角色拉伸扩展")

    project = make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("stretch_setStretchX", None, "b1",
                    inputs={"X": [1, [4, "150"]]}),
    }, name="Stretch")
    project["extensions"] = ["stretch"]
    code = generate_python(parse_scratch_project(project))
    assert "'stretch': _extension_stretch" in code
    assert "self.extension('stretch', 'stretch_setStretchX'" in code

    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    pygame = namespace["pygame"]
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite = namespace["Stretch"]()
    runtime.add_sprite(sprite)
    try:
        sprite.extension('stretch', 'stretch_setStretchX', {'X': 200}, {})
        assert sprite._stretch_x == 200
        assert sprite.extension('stretch', 'stretch_getX', {}, {}) == 200
        sprite.extension('stretch', 'stretch_changeStretchY', {'DY': 50}, {})
        assert sprite._stretch_y == 150
        sprite.extension('stretch', 'stretch_setStretch', {'X': 50, 'Y': 25}, {})
        assert (sprite._stretch_x, sprite._stretch_y) == (50, 25)
        assert sprite.extension('stretch', 'stretch_getY', {}, {}) == 25

        surface = pygame.Surface((40, 20), pygame.SRCALPHA)
        surface.fill((255, 0, 0, 255))
        sprite._costume_surface = lambda: surface
        sprite._stretch_x = 200
        sprite._stretch_y = 100
        image, _rect, _x, _y, _scale, _direction = sprite._rendered_image()
        assert image.get_width() == 80 and image.get_height() == 20, \
            f"拉伸后尺寸应为 80x20: {image.get_size()}"
        half_w, half_h = sprite._sprite_bounds()
        assert abs(half_w - 40) < 2 and abs(half_h - 10) < 2, \
            f"围栏半宽/半高应包含拉伸: {half_w},{half_h}"

        # 克隆体继承拉伸
        clone = sprite._make_clone()
        assert clone is not None
        assert clone._stretch_x == 200 and clone._stretch_y == 100
    finally:
        runtime.running = False
        runtime.shutdown()

    print("  [PASS] 角色拉伸扩展通过")
    return True


def test_animated_text_extension():
    """艺术字：显示文字、样式、宽度换行、打字动画与清除"""
    print("[测试54] 艺术字扩展")

    import time

    project = make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("text_setText", "b3", "b1",
                    inputs={"TEXT": [1, [10, "Hello"]]}),
        "b3": block("text_setWidthInput", None, "b2",
                    inputs={"WIDTH": [1, [4, "120"]], "ALIGN": [1, "m1"]}),
        "m1": block("text_menu_twAlign", None, None,
                    fields={"twAlign": ["left", None]}),
    }, name="ArtText")
    project["targets"][0]["blocks"]["m1"]["shadow"] = True
    project["extensions"] = ["text"]
    code = generate_python(parse_scratch_project(project))
    assert "'text': _extension_text" in code
    assert "self.extension('text', 'text_setText'" in code
    assert "'ALIGN': 'left'" in code, "菜单 shadow 块应解析成菜单文本"

    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    pygame = namespace["pygame"]
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite = namespace["ArtText"]()
    runtime.add_sprite(sprite)
    try:
        sprite.extension('text', 'text_setText', {'TEXT': 'Hello'}, {})
        assert sprite._text_active()
        assert sprite._text_displayed() == 'Hello'
        image, _cx, _cy = sprite._text_image()
        assert image.get_width() > 10 and image.get_height() > 10
        assert pygame.mask.from_surface(image).count() > 0, "文字应被渲染出来"

        sprite.extension('text', 'text_setFont', {}, {'FONT': 'Serif'})
        assert sprite._text_attribute('font') == 'Serif'
        sprite.extension('text', 'text_setColor', {}, {'COLOR': '#ff0000'})
        assert sprite._text_attribute('color') == '#ff0000'
        sprite.extension('text', 'text_setAlignment', {}, {'ALIGN': 'left'})
        assert sprite._text_attribute('alignment') == 'left'
        sprite.extension('text', 'text_setOutlineWidth', {'WIDTH': 2}, {})
        assert sprite._text_attribute('outline width') == 2

        # 宽度限制会换行
        sprite.extension('text', 'text_setText',
                         {'TEXT': 'Hello world this is a long line'}, {})
        sprite.extension('text', 'text_setWidthValue', {'WIDTH': 60}, {})
        assert sprite._text_count_lines(True) > 1, "窄宽度下应自动换行"

        # 打字动画：延迟很小，等待显示完整文本
        text = 'Hello world this is a long line'
        sprite.extension('text', 'text_setTypeDelay', {'NUM': 0.01}, {})
        sprite.extension('text', 'text_startAnimate', {}, {'ANIMATE': 'type'})
        deadline = time.time() + 5
        while time.time() < deadline and sprite._text_displayed() != text:
            time.sleep(0.01)
        assert sprite._text_displayed() == text, \
            f"打字动画应显示完整文本: {sprite._text_displayed()!r}"
        assert sprite._text_is_animating() is False

        # 清除文字
        sprite.extension('text', 'text_clearText', {}, {})
        assert not sprite._text_active()
        assert sprite._text_image() is None
    finally:
        runtime.running = False
        runtime.shutdown()

    print("  [PASS] 艺术字扩展通过")
    return True


def test_json_extension():
    """TurboWarp JSON 扩展：解析、对象/数组操作、路径、分析、列表读写"""
    print("[测试55] JSON 扩展")

    project = make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("skyhigh173JSON_json_get", None, "b1",
                    inputs={"item": [1, [10, "key"]],
                            "json": [1, [10, '{"key":"value"}']]}),
    }, name="Json")
    project["targets"][0]["lists"] = {"l1": ["mylist", ["a", "b"]]}
    project["targets"][0]["blocks"]["b3"] = block(
        "skyhigh173JSON_json_vm_getlist", None, "b2", inputs={"list": [1, "m1"]})
    project["targets"][0]["blocks"]["b2"]["next"] = "b3"
    project["targets"][0]["blocks"]["m1"] = block(
        "skyhigh173JSON_menu_get_list", None, None,
        fields={"get_list": ["l1", None]})
    project["targets"][0]["blocks"]["m1"]["shadow"] = True
    project["extensions"] = ["skyhigh173JSON"]

    code = generate_python(parse_scratch_project(project))
    assert "'skyhigh173JSON': _extension_skyhigh_json" in code
    assert "self.extension('skyhigh173JSON', 'skyhigh173JSON_json_get'" in code
    assert "'list': 'mylist'" in code, "列表ID菜单应解析成列表名"

    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite = namespace["Json"]()
    runtime.add_sprite(sprite)

    def call(opcode, inputs=None, fields=None):
        return sprite.extension('skyhigh173JSON', opcode, inputs or {}, fields or {})

    try:
        # 通用工具
        assert call('skyhigh173JSON_json_is_valid', {'json': '{"a":1}'}) is True
        assert call('skyhigh173JSON_json_is_valid', {'json': 'nope'}) is False
        assert call('skyhigh173JSON_json_is', {'json': '[1,2]'},
                    {'types': 'Array'}) is True
        assert call('skyhigh173JSON_json_is', {'json': '{"a":1}'},
                    {'types': 'Array'}) is False
        assert call('skyhigh173JSON_json_new', {}, {'json': 'Array'}) == '[]'
        assert call('skyhigh173JSON_json_minify', {'json': ' {"a" : 1 } '}) == '{"a":1}'
        assert call('skyhigh173JSON_json_length', {'json': '[1,2,3]'}) == 3
        assert call('skyhigh173JSON_json_get_all',
                    {'json': '{"a":1,"b":2}'}, {'Stype': 'keys'}) == '["a","b"]'
        assert call('skyhigh173JSON_json_get_all',
                    {'json': '{"a":1,"b":2}'}, {'Stype': 'values'}) == '[1,2]'
        assert call('skyhigh173JSON_json_equal',
                    {'json1': '{"a":0,"b":1}', 'json2': '{"b":1,"a":0}'},
                    {'equal': '='}) is True
        assert call('skyhigh173JSON_json_flip',
                    {'json': '{"a":"b"}'}) == '{"b":"a"}'
        assert call('skyhigh173JSON_json_has_key',
                    {'json': '{"a":1}', 'key': 'a'}) is True
        assert call('skyhigh173JSON_json_has_value',
                    {'json': '["x","y"]', 'value': 'y'}) is True

        # 对象读写与路径
        assert call('skyhigh173JSON_json_get',
                    {'item': 'b', 'json': '{"a":1,"b":{"c":2}}'}) == '{"c":2}'
        assert call('skyhigh173JSON_json_set',
                    {'item': 'b', 'value': '5', 'json': '{"a":1}'}) == '{"a":1,"b":"5"}'
        assert call('skyhigh173JSON_json_delete',
                    {'item': 'a', 'json': '{"a":1,"b":2}'}) == '{"b":2}'
        path_json = '{"key":{"inner":[true,false]}}'
        assert call('skyhigh173JSON_json_get_path',
                    {'path': '["key","inner",1]', 'json': path_json}) is True
        assert call('skyhigh173JSON_json_set_path',
                    {'path': '["key","inner",1]', 'json': path_json,
                     'data': 'x'}) == '{"key":{"inner":["x",false]}}'

        # 数组操作
        assert call('skyhigh173JSON_json_array_get',
                    {'item': 2, 'json': '["a","b","c"]'}) == 'b'
        assert call('skyhigh173JSON_json_array_get',
                    {'item': -1, 'json': '["a","b","c"]'}) == 'c'
        assert call('skyhigh173JSON_json_array_push',
                    {'item': 'c', 'json': '["a","b"]'}) == '["a","b","c"]'
        assert call('skyhigh173JSON_json_array_insert',
                    {'item': 'x', 'pos': 2, 'json': '["a","b"]'}) == '["a","x","b"]'
        assert call('skyhigh173JSON_json_array_set',
                    {'item': 'x', 'pos': 2, 'json': '["a","b"]'}) == '["a","x"]'
        assert call('skyhigh173JSON_json_array_delete',
                    {'item': 1, 'json': '["a","b"]'}) == '["b"]'
        assert call('skyhigh173JSON_json_array_remove_all',
                    {'item': 'a', 'json': '["a","b","a"]'}) == '["b"]'
        assert call('skyhigh173JSON_json_array_itemH',
                    {'item': 'b', 'json': '["a","b"]'}) == 2
        assert call('skyhigh173JSON_json_array_from',
                    {'json': 'abcd'}) == '["a","b","c","d"]'
        assert call('skyhigh173JSON_json_array_fromto',
                    {'json': '[1,2,3,4]', 'item': 2, 'item2': 3}) == '[2,3]'
        assert call('skyhigh173JSON_json_array_reverse',
                    {'json': '[1,2]'}) == '[2,1]'
        assert call('skyhigh173JSON_json_array_flat',
                    {'json': '[[1],2,[3,4],[5,[6]]]', 'depth': 1}) == '[1,2,3,4,5,[6]]'
        assert call('skyhigh173JSON_json_array_concat',
                    {'json': '[1]', 'json2': '[2]'}) == '[1,2]'
        assert call('skyhigh173JSON_json_array_filter',
                    {'key': 'id', 'json': '[{"id":12},{"x":1}]'}) == '[12,null]'
        assert call('skyhigh173JSON_json_array_setlen',
                    {'json': '[1,2,3]', 'len': 2}) == '[1,2]'
        assert call('skyhigh173JSON_json_array_filter',
                    {'key': 'id', 'json': '[{"id":1}]'}) == '[1]'
        assert call('skyhigh173JSON_json_merge',
                    {'json1': '{"a":1}', 'json2': '{"b":2}'}) == '{"a":1,"b":2}'
        assert call('skyhigh173JSON_json_array_create',
                    {'text': 'a,b,c', 'd': ','}) == '["a","b","c"]'
        assert call('skyhigh173JSON_json_array_join',
                    {'json': '["a","b"]', 'd': '-'}) == 'a-b'
        assert call('skyhigh173JSON_json_array_sort',
                    {'list': '[3,1,2]'}, {'order': 'ascending'}) == '[1,2,3]'
        assert call('skyhigh173JSON_json_array_textfilter',
                    {'list': '["apple","banana","orange"]',
                     'text': 'e'}, {'options': 'includes', 'type': 'Array'}) \
            == '["apple","orange"]'

        # 数据分析
        numbers = '[17,1,2017,0,120,14]'
        assert call('skyhigh173JSON_json_array_analysis',
                    {'list': numbers}, {'analysis': 'sum'}) == 2169
        assert call('skyhigh173JSON_json_array_analysis',
                    {'list': numbers}, {'analysis': 'minimum'}) == 0
        assert call('skyhigh173JSON_json_array_analysis',
                    {'list': numbers}, {'analysis': 'maximum'}) == 2017
        assert call('skyhigh173JSON_json_array_analysis',
                    {'list': '[1,2,3]'}, {'analysis': 'average'}) == 2

        # 列表读写
        assert call('skyhigh173JSON_json_vm_getlist', {'list': 'mylist'}) == '["a","b"]'
        call('skyhigh173JSON_json_vm_setlist',
             {'list': 'mylist', 'json': '[1,{"x":2}]'})
        assert sprite.mylist == [1, '{"x":2}']
    finally:
        runtime.running = False
        runtime.shutdown()

    print("  [PASS] JSON 扩展通过")
    return True


def test_split_modules_output():
    """模块化多文件输出：入口 + 运行时 + 每个角色独立模块，且能实际运行"""
    print("[测试56] 模块化多文件输出")

    import tempfile
    import shutil
    import subprocess

    project = make_project({
        "b1": block("event_whenflagclicked", None, None, top_level=True),
    }, name="First")
    second = json.loads(json.dumps(project["targets"][0]))
    second["name"] = "Second"
    second["blocks"] = {
        "b1": block("event_whenflagclicked", None, None, top_level=True)}
    project["targets"].append(second)

    ir = parse_scratch_project(project)
    entry, files = generate_modules(ir, "demo")

    assert "from demo_runtime import ScratchRuntime" in entry
    assert "from demo_sprite_01_First import First" in entry
    assert "from demo_sprite_02_Second import Second" in entry
    assert "demo_runtime.py" in files
    assert len([name for name in files if "_sprite_" in name]) == 2

    runtime_lines = len(files["demo_runtime.py"].splitlines())
    sprite_lines = [len(code.splitlines()) for name, code in files.items()
                    if "_sprite_" in name]
    assert runtime_lines > 1000, "运行时是独立模块"
    assert all(lines < runtime_lines / 2 for lines in sprite_lines), \
        f"角色模块应远小于运行时: {sprite_lines} vs {runtime_lines}"

    directory = tempfile.mkdtemp()
    try:
        for name, code in files.items():
            with open(os.path.join(directory, name), "w", encoding="utf-8") as f:
                f.write(code)
        entry_path = os.path.join(directory, "demo.py")
        with open(entry_path, "w", encoding="utf-8") as f:
            f.write(entry)
        result = subprocess.run(
            [sys.executable, entry_path, "--headless", "--frames", "1",
             "--no-audio", "--windowed"],
            capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, result.stderr
        assert "Traceback" not in result.stderr, result.stderr
    finally:
        shutil.rmtree(directory, ignore_errors=True)

    print("  [PASS] 模块化多文件输出通过")
    return True


def test_dunder_variables_and_tw_stage_size():
    """双下划线变量不会被 name mangling 破坏；TurboWarp width 选项生效"""
    print("[测试58] 双下划线变量与舞台尺寸")

    import time

    project = make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("data_changevariableby", None, "b1",
                    inputs={"VALUE": [1, [4, "1"]]},
                    fields={"VARIABLE": ["__计数", "v1"]}),
    }, name="Dunder")
    project["targets"][0]["variables"] = {"v1": ["__计数", 0]}
    project["targets"][0]["comments"] = {"c1": {
        "blockId": None, "x": 0, "y": 0, "width": 200, "height": 100,
        "minimized": False,
        "text": 'Configuration for TurboWarp\n{"width":640} // _twconfig_'}}

    code = generate_python(parse_scratch_project(project))
    assert "parser.set_defaults(stage_size='640x360')" in code, \
        "TurboWarp width 选项应转换为舞台尺寸"
    assert "self.var__计数" in code, "双下划线变量应加前缀避免 name mangling"
    assert "self.__计数" not in code

    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite = namespace["Dunder"]()
    runtime.add_sprite(sprite)
    sprite.run()
    runtime.green_flag()
    try:
        deadline = time.time() + 3
        while time.time() < deadline and getattr(sprite, "var__计数", 0) < 1:
            runtime.step()
            time.sleep(0.01)
        assert getattr(sprite, "var__计数", 0) == 1, \
            "双下划线变量应能正常读写"
    finally:
        runtime.running = False
        runtime.shutdown()

    print("  [PASS] 双下划线变量与舞台尺寸通过")
    return True


def test_pen_performance_paths():
    """画笔优化：空图层跳过合成、颜色缓存、透明线段不绘制"""
    print("[测试59] 画笔性能优化")

    project = make_project({
        "b1": block("event_whenflagclicked", None, None, top_level=True),
    }, name="Pen")
    code = generate_python(parse_scratch_project(project))
    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    pygame = namespace["pygame"]
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    try:
        assert runtime._pen_used is False, "初始画笔图层应为空"
        probe = (runtime.stage_width // 2, runtime.stage_height // 2)
        # 画过东西却不标记 used 时，合成应跳过画笔层
        runtime.pen_layer.fill((255, 0, 0, 255))
        runtime._draw()
        assert tuple(runtime.stage_surface.get_at(probe))[:3] == (255, 255, 255), \
            "画笔图层为空时应跳过合成"
        runtime._pen_used = True
        runtime._draw()
        assert tuple(runtime.stage_surface.get_at(probe))[:3] == (255, 0, 0), \
            "有内容时应正常合成画笔层"

        runtime.pen_clear()
        assert runtime._pen_used is False
        assert tuple(runtime.pen_layer.get_at(probe))[3] == 0

        color_a = runtime.pen_color(0, 100, 100, 0)
        color_b = runtime.pen_color(0, 100, 100, 0)
        assert color_a is color_b, "相同画笔颜色应命中缓存"

        # 透明度 100 的线段不会绘制，也不会标记图层
        runtime.pen_draw_segment((0, 0), (50, 0),
                                 runtime.pen_color(0, 100, 100, 100), 10)
        assert runtime._pen_used is False
        assert tuple(runtime.pen_layer.get_at(probe))[3] == 0, \
            "完全透明的线段不应留下像素"

        runtime.pen_draw_segment((-50, 0), (50, 0), (0, 0, 255, 255), 8)
        assert runtime._pen_used is True
        assert tuple(runtime.pen_layer.get_at(probe))[3] > 0
    finally:
        runtime.running = False
        runtime.shutdown()

    print("  [PASS] 画笔性能优化通过")
    return True


TESTS = [
    test_text2speech_extension,
    test_stretch_extension,
    test_animated_text_extension,
    test_json_extension,
    test_split_modules_output,
    test_dunder_variables_and_tw_stage_size,
    test_pen_performance_paths,
]
