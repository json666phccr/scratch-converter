# -*- coding: utf-8 -*-
"""由 test_all.py 拆分出的测试模块"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import *


def test_variable_shadowing_fidelity():
    """局部变量/列表与全局同名时，按变量ID读写正确的存储"""
    print("[测试65] 变量模型保真（局部遮蔽全局）")

    import time

    project = make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("data_setvariableto", "b3", "b1",
                    inputs={"VALUE": [1, [4, "1"]]},
                    fields={"VARIABLE": ["score", "lvar"]}),
        "b3": block("data_changevariableby", "b4", "b2",
                    inputs={"VALUE": [1, [4, "5"]]},
                    fields={"VARIABLE": ["score", "gvar"]}),
        "b4": block("data_addtolist", "b5", "b3",
                    inputs={"ITEM": [1, [10, "local"]]},
                    fields={"LIST": ["items", "llist"]}),
        "b5": block("data_addtolist", "b6", "b4",
                    inputs={"ITEM": [1, [10, "global"]]},
                    fields={"LIST": ["items", "glist"]}),
        "b6": block("data_setvariableto", "b7", "b5",
                    inputs={"VALUE": [3, "v_local"]},
                    fields={"VARIABLE": ["read_local", "readid1"]}),
        "b7": block("data_setvariableto", None, "b6",
                    inputs={"VALUE": [3, "v_global"]},
                    fields={"VARIABLE": ["read_global", "readid2"]}),
        "v_local": block("data_variable", None, "b6",
                         fields={"VARIABLE": ["score", "lvar"]}),
        "v_global": block("data_variable", None, "b7",
                          fields={"VARIABLE": ["score", "gvar"]}),
    }, name="Shadow")
    project["targets"][0]["variables"] = {
        "lvar": ["score", 0],
        "readid1": ["read_local", 0],
        "readid2": ["read_global", 0],
    }
    project["targets"][0]["lists"] = {"llist": ["items", []]}
    project["targets"].insert(0, {
        "isStage": True, "name": "Stage",
        "variables": {"gvar": ["score", 0]},
        "lists": {"glist": ["items", []]},
        "broadcasts": {}, "blocks": {}, "comments": {},
        "currentCostume": 0, "costumes": [], "sounds": [],
        "volume": 100, "layerOrder": 0,
    })

    parsed = parse_scratch_project(project)
    shadow = next(sprite for sprite in parsed.sprites
                  if sprite.name == "Shadow")
    stage = parsed.stage
    assert shadow.variable_attrs.get("score") == "local_score"
    assert shadow.list_attrs.get("items") == "local_items"
    assert stage.variable_attrs.get("score") == "score"

    code = generate_python(parsed)
    assert "self.local_score = 1" in code
    assert "self.local_items" in code

    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite = namespace["Shadow"]()
    runtime.add_sprite(sprite)
    try:
        sprite.run()
        runtime.green_flag()
        for _ in range(8):
            runtime.step()
            time.sleep(0.003)

        assert sprite.local_score == 1, "局部变量应写入独立属性"
        assert namespace["GLOBALS"]["score"] == 5, "全局变量应写入GLOBALS"
        assert sprite.read_local == 1, "局部变量引用应解析到局部"
        assert sprite.read_global == 5, "全局变量引用应解析到GLOBALS"
        assert sprite.local_items == ["local"], "局部列表应独立"
        assert namespace["GLOBALS"]["items"] == ["global"], "全局列表应独立"

        sprite.show_variable("score")
        monitor = runtime.dynamic_monitors[-1]
        assert monitor["attr"] == "local_score"
        assert monitor["sprite"] == "Shadow"
        sprite.show_list("items")
        monitor = runtime.dynamic_monitors[-1]
        assert monitor["attr"] == "local_items"
        assert monitor["sprite"] == "Shadow"
    finally:
        runtime.running = False
        runtime.shutdown()

    # 写回sb3时仍使用原始变量名，不暴露Python属性别名
    written = write_scratch_project(parse_scratch_project(project))
    shadow_json = next(target for target in written["targets"]
                       if target.get("name") == "Shadow")
    names = [value[0] for value in shadow_json["variables"].values()]
    list_names = [value[0] for value in shadow_json["lists"].values()]
    assert "score" in names and "local_score" not in names
    assert "items" in list_names and "local_items" not in list_names

    print("  [PASS] 变量模型保真通过")
    return True


def test_scheduler_fairness_with_clones():
    """大量克隆脚本不会互相饿死，创建循环能正常完成"""
    print("[测试66] 大项目调度公平性")

    import time

    project = make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("control_repeat", "b3", "b1",
                    inputs={"TIMES": [1, [4, "5"]],
                            "SUBSTACK": [2, "b4"]}),
        "b3": block("data_setvariableto", None, "b2",
                    inputs={"VALUE": [1, [4, "1"]]},
                    fields={"VARIABLE": ["done", "doneid"]}),
        "b4": block("control_create_clone_of", None, "b2",
                    inputs={"CLONE_OPTION": [1, [10, "_myself_"]]}),
        "h1": block("control_start_as_clone", "h2", None, top_level=True),
        "h2": block("control_forever", None, "h1",
                    inputs={"SUBSTACK": [2, "h3"]}),
        "h3": block("data_changevariableby", None, "h2",
                    inputs={"VALUE": [1, [4, "1"]]},
                    fields={"VARIABLE": ["ticks", "ticksid"]}),
    }, name="Scheduler")
    project["targets"][0]["variables"] = {
        "doneid": ["done", 0], "ticksid": ["ticks", 0],
    }

    code = generate_python(parse_scratch_project(project))
    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite = namespace["Scheduler"]()
    runtime.add_sprite(sprite)
    try:
        sprite.run()
        runtime.green_flag()
        for _ in range(120):
            runtime.step()
            time.sleep(0.003)

        clones = [item for item in runtime.sprites
                  if getattr(item, '_is_clone', False)]
        assert len(clones) == 5, f"应创建5个克隆，实际 {len(clones)}"
        assert sprite.done == 1, "创建克隆的循环不应被饿死"
        assert all(clone.ticks > 0 for clone in clones), \
            "每个克隆脚本都应至少执行过一次"
        assert len(runtime.scripts) <= 6
    finally:
        runtime.running = False
        runtime.shutdown()

    print("  [PASS] 大项目调度公平性通过")
    return True


def test_list_tools_extension():
    """List Tools：列表查找、排序、数组与遍历循环"""
    print("[测试67] List Tools 扩展")

    import time

    project = make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("data_setvariableto", "b3", "b1",
                    inputs={"VALUE": [3, "joinblock"]},
                    fields={"VARIABLE": ["joined", "j1"]}),
        "b3": block("data_setvariableto", "b4", "b2",
                    inputs={"VALUE": [3, "countblock"]},
                    fields={"VARIABLE": ["count", "c1"]}),
        "b4": block("data_setvariableto", "b5", "b3",
                    inputs={"VALUE": [3, "indexblock"]},
                    fields={"VARIABLE": ["last_index", "i1"]}),
        "b5": block("lmsListTools_orderList", "b6", "b4",
                    inputs={"LIST": [1, [10, "items"]],
                            "ORDER": [1, [10, "ascending"]]}),
        "b6": block("lmsListTools_setListArray", "b7", "b5",
                    inputs={"LIST": [1, [10, "localItems"]],
                            "ARRAY": [1, [10, '["a","b"]']]}),
        "b7": block("lmsListTools_forEachItemValue", None, "b6",
                    inputs={"VAR": [1, [10, "current"]],
                            "LIST": [1, [10, "localItems"]],
                            "SUBSTACK": [2, "b8"]}),
        "b8": block("data_addtolist", None, "b7",
                    inputs={"ITEM": [3, "tmpvar", [10, ""]]},
                    fields={"LIST": ["seen", "s1"]}),
        "tmpvar": block("lmsTempVars2_getThreadVariable", None, "b8",
                        inputs={"VAR": [1, [10, "current"]]}),
        "joinblock": block("lmsListTools_getListJoin", None, "b2",
                           inputs={"LIST": [1, [10, "items"]],
                                   "STRING": [1, [10, "-"]]}),
        "countblock": block("lmsListTools_timesItemAppears", None, "b3",
                            inputs={"ITEM": [1, [10, "apple"]],
                                    "LIST": [1, [10, "items"]]}),
        "indexblock": block("lmsListTools_itemIndex", None, "b4",
                            inputs={"INDEX": [1, [10, "_last_"]],
                                    "ITEM": [1, [10, "apple"]],
                                    "LIST": [1, [10, "items"]]}),
    }, name="ListSprite")
    project["extensions"] = ["lmsListTools", "lmsTempVars2"]
    project["targets"][0]["variables"] = {
        "j1": ["joined", ""], "c1": ["count", 0], "i1": ["last_index", 0],
    }
    project["targets"][0]["lists"] = {"l1": ["localItems", []]}
    project["targets"].insert(0, {
        "isStage": True, "name": "Stage",
        "variables": {}, "lists": {
            "g1": ["items", ["banana", "apple", "apple"]],
            "g2": ["seen", []],
        },
        "broadcasts": {}, "blocks": {}, "comments": {},
        "currentCostume": 0, "costumes": [], "sounds": [],
        "volume": 100, "layerOrder": 0,
    })

    code = generate_python(parse_scratch_project(project))
    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite = namespace["ListSprite"]()
    runtime.add_sprite(sprite)
    try:
        sprite.run()
        runtime.green_flag()
        for _ in range(40):
            runtime.step()
            time.sleep(0.003)

        assert sprite.joined == "banana-apple-apple"
        assert sprite.count == 2
        assert sprite.last_index == 3
        assert namespace["GLOBALS"]["items"] == ["apple", "apple", "banana"]
        assert sprite.localItems == ["a", "b"]
        assert namespace["GLOBALS"]["seen"] == ["a", "b"]
    finally:
        runtime.running = False
        runtime.shutdown()

    print("  [PASS] List Tools 扩展通过")
    return True


def test_new_runtime_extensions():
    """Local Storage / Clipboard / Mouse Cursor / Window Controls"""
    print("[测试68] 本地存储、剪贴板、光标、窗口扩展")

    import time
    import os

    namespace_name = "scratch_converter_test_ns"
    storage_path = os.path.join(
        os.path.expanduser("~"), ".scratch-converter", "localstorage",
        namespace_name + ".json")

    project = make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("localstorage_setProjectId", "b3", "b1",
                    inputs={"ID": [1, [10, namespace_name]]}),
        "b3": block("localstorage_set", "b4", "b2",
                    inputs={"KEY": [1, [10, "k"]],
                            "VALUE": [1, [10, "v"]]}),
        "b4": block("data_setvariableto", "b5", "b3",
                    inputs={"VALUE": [3, "getblock"]},
                    fields={"VARIABLE": ["got", "g1"]}),
        "b5": block("data_setvariableto", "b6", "b4",
                    inputs={"VALUE": [3, "countblock"]},
                    fields={"VARIABLE": ["keys", "k1"]}),
        "b6": block("data_setvariableto", "b7", "b5",
                    inputs={"VALUE": [3, "firstkey"]},
                    fields={"VARIABLE": ["first_key", "f1"]}),
        "b7": block("clipboard_setClipboard", "b8", "b6",
                    inputs={"TEXT": [1, [10, "hello"]]}),
        "b8": block("data_setvariableto", "b9", "b7",
                    inputs={"VALUE": [3, "clipblock"]},
                    fields={"VARIABLE": ["clip", "c1"]}),
        "b9": block("MouseCursor_setCur", "b10", "b8",
                    inputs={"CUR": [1, [10, "pointer"]]}),
        "b10": block("data_setvariableto", "b11", "b9",
                     inputs={"VALUE": [3, "curblock"]},
                     fields={"VARIABLE": ["cursor", "u1"]}),
        "b11": block("cubesterWindowControls_changeTitleTo", "b12", "b10",
                     inputs={"TITLE": [1, [10, "测试窗口"]]}),
        "b12": block("data_setvariableto", "b13", "b11",
                     inputs={"VALUE": [3, "titleblock"]},
                     fields={"VARIABLE": ["title", "t1"]}),
        "b13": block("data_setvariableto", "b14", "b12",
                     inputs={"VALUE": [3, "widthblock"]},
                     fields={"VARIABLE": ["win_width", "w1"]}),
        "b14": block("data_setvariableto", None, "b13",
                     inputs={"VALUE": [3, "fullblock"]},
                     fields={"VARIABLE": ["fullscreen", "s1"]}),
        "getblock": block("localstorage_get", None, "b4",
                          inputs={"KEY": [1, [10, "k"]]}),
        "countblock": block("localstorage_keyCount", None, "b5"),
        "firstkey": block("localstorage_itemOfKey", None, "b6",
                          inputs={"NUM": [1, [10, "1"]]}),
        "clipblock": block("clipboard_clipboard", None, "b8"),
        "curblock": block("MouseCursor_getCur", None, "b10"),
        "titleblock": block("cubesterWindowControls_windowTitle", None, "b12"),
        "widthblock": block("cubesterWindowControls_windowW", None, "b13"),
        "fullblock": block("cubesterWindowControls_isFullscreen", None, "b14"),
        # 复制帽子：runtime._trigger_event('clipboard_copy') 时应执行
        "h1": block("clipboard_whencopied", "h2", None, top_level=True),
        "h2": block("data_setvariableto", None, "h1",
                    inputs={"VALUE": [1, [4, "1"]]},
                    fields={"VARIABLE": ["copied", "p1"]}),
    }, name="ExtSprite")
    project["extensions"] = ["localstorage", "clipboard", "MouseCursor",
                             "cubesterWindowControls"]
    project["targets"][0]["variables"] = {
        "g1": ["got", ""], "k1": ["keys", 0], "f1": ["first_key", ""],
        "c1": ["clip", ""], "u1": ["cursor", ""], "t1": ["title", ""],
        "w1": ["win_width", 0], "s1": ["fullscreen", False],
        "p1": ["copied", 0],
    }

    code = generate_python(parse_scratch_project(project))
    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite = namespace["ExtSprite"]()
    runtime.add_sprite(sprite)
    try:
        sprite.run()
        runtime.green_flag()
        for _ in range(30):
            runtime.step()
            time.sleep(0.003)

        assert sprite.got == "v"
        assert sprite.keys == 1
        assert sprite.first_key == "k"
        assert sprite.clip == "hello"
        assert sprite.cursor == "pointer"
        assert sprite.title == "测试窗口"
        assert sprite.win_width == 480
        assert sprite.fullscreen is False
        assert os.path.exists(storage_path)

        runtime._trigger_event("clipboard_copy")
        for _ in range(10):
            runtime.step()
            time.sleep(0.003)
        assert sprite.copied == 1, "复制帽子应被触发"
    finally:
        runtime.running = False
        runtime.shutdown()
        try:
            if os.path.exists(storage_path):
                os.remove(storage_path)
        except OSError:
            pass

    print("  [PASS] 新运行时扩展通过")
    return True


def test_slider_monitor():
    """变量滑动条监视器：解析 sliderMin/sliderMax 并支持拖动写回"""
    print("[测试69] 变量滑动条监视器")

    project = make_project({
        "b1": block("event_whenflagclicked", None, None, top_level=True),
    }, name="SliderSprite")
    project["targets"][0]["variables"] = {"v1": ["speed", 50]}
    project["monitors"] = [{
        "id": "m1", "mode": "slider", "opcode": "data_variable",
        "params": {"VARIABLE": "speed"}, "spriteName": "SliderSprite",
        "value": 50, "width": 0, "height": 0, "x": 10, "y": 10,
        "visible": True, "sliderMin": 0, "sliderMax": 100,
        "isDiscrete": True,
    }]

    parsed = parse_scratch_project(project)
    code = generate_python(parsed)
    assert "'mode': 'slider'" in code, "应保留滑动条模式"
    assert "'slider_min': 0" in code and "'slider_max': 100" in code

    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite = namespace["SliderSprite"]()
    runtime.add_sprite(sprite)
    try:
        runtime._draw_monitors()
        assert runtime._slider_hits, "滑动条监视器应产生可拖动区域"
        monitor, rect = runtime._slider_hits[0]
        track = runtime._slider_track_rect(rect)
        runtime._apply_slider(monitor, rect, track.x + track.width * 0.25)
        assert 24 <= sprite.speed <= 26, f"拖动到 25% 应约为 25: {sprite.speed}"

        runtime._apply_slider(monitor, rect, track.x - 50)
        assert sprite.speed == 0, "拖动越界应夹到最小值"
        runtime._apply_slider(monitor, rect, track.right + 50)
        assert sprite.speed == 100, "拖动越界应夹到最大值"
    finally:
        runtime.running = False
        runtime.shutdown()

    print("  [PASS] 变量滑动条监视器通过")
    return True


def test_warp_render_semantics():
    """不刷新屏幕：warp 期间暂停其他脚本并延后绘制"""
    print("[测试70] 不刷新屏幕渲染语义")

    project = make_project({
        "b1": block("event_whenflagclicked", None, None, top_level=True),
    }, name="WarpSprite")
    code = generate_python(parse_scratch_project(project))
    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite = namespace["WarpSprite"]()
    runtime.add_sprite(sprite)
    drawn = []
    runtime._draw = lambda: drawn.append(runtime.frame)
    runtime._present = lambda: None
    try:
        sprite._enter_procedure(warp=True)
        assert runtime.warping and runtime._warp_active == 1
        runtime.step()
        assert not drawn, "warp 期间不应绘制"

        sprite._leave_procedure(warp=True)
        assert not runtime.warping
        runtime.step()
        assert drawn, "warp 结束后应恢复绘制"
    finally:
        runtime.running = False
        runtime.shutdown()

    print("  [PASS] warp 延后绘制通过")
    return True


def test_conversion_log():
    """转换日志：阶段记录与异常定位"""
    print("[测试71] 转换日志")

    import io
    from convert_log import ConversionLog

    stream = io.StringIO()
    log = ConversionLog()
    log.configure(level='debug', stream=stream)
    with log.stage('解析 IR'):
        log.debug('精灵: 1，语句: 3')
    output = stream.getvalue()
    assert '开始: 解析 IR' in output
    assert '精灵: 1，语句: 3' in output

    try:
        with log.stage('生成 Python'):
            raise ValueError('boom')
    except ValueError:
        pass
    output = stream.getvalue()
    assert '阶段失败: 生成 Python' in output
    assert 'ValueError: boom' in output
    assert 'at ' in output and '.py:' in output, "应输出报错位置"

    log.close()
    print("  [PASS] 转换日志通过")
    return True


def test_on_demand_extension_assembly():
    """扩展按需拼装：未使用的扩展不写入生成代码"""
    print("[测试72] 扩展按需拼装")

    plain = make_project({
        "b1": block("event_whenflagclicked", None, None, top_level=True),
    }, name="Plain")
    plain_code = generate_python(parse_scratch_project(plain))
    assert "_BUILTIN_EXTENSIONS = {}" in plain_code
    assert "_extension_pen" not in plain_code
    assert "_extension_tween" not in plain_code
    assert "_extension_music" not in plain_code
    assert "def _hsv_to_rgb" in plain_code, "运行时画笔颜色依赖的辅助函数应保留"

    project = make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("pen_penDown", None, "b1"),
    }, name="PenOnly")
    project["extensions"] = ["pen"]
    pen_code = generate_python(parse_scratch_project(project))
    assert "'pen': _extension_pen" in pen_code
    assert "def _extension_pen" in pen_code
    assert "_extension_tween" not in pen_code
    assert "_extension_music" not in pen_code

    # 与“全部扩展”对比：按需拼装应显著减少代码量
    all_ids = ['pen', 'runtimeoptions', 'music', 'text2speech', 'stretch',
               'text', 'skyhigh173JSON', 'lmsclonesplus', 'lmsLooksPlus',
               'lmsMoreEvents', 'lmsTempVars2', 'jeremygamerTweening',
               'lmsListTools', 'localstorage', 'clipboard', 'MouseCursor',
               'cubesterWindowControls']
    full = make_project({
        "b1": block("event_whenflagclicked", None, None, top_level=True),
    }, name="Plain")
    full["extensions"] = all_ids
    full_code = generate_python(parse_scratch_project(full))
    assert len(plain_code.splitlines()) < len(full_code.splitlines()) - 1000

    print("  [PASS] 扩展按需拼装通过")
    return True


def test_svg_high_resolution_rendering():
    """SVG 按窗口倍率重新栅格化"""
    print("[测试73] SVG 高分辨率渲染")

    import tempfile

    project = make_project({
        "b1": block("event_whenflagclicked", None, None, top_level=True),
    }, name="SvgSprite")
    code = generate_python(parse_scratch_project(project))
    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)

    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="10">'
           '<rect x="0" y="0" width="20" height="10" fill="#ff0000"/>'
           '</svg>')
    temp_dir = tempfile.mkdtemp()
    svg_path = os.path.join(temp_dir, 'shape.svg')
    with open(svg_path, 'w', encoding='utf-8') as handle:
        handle.write(svg)

    runtime = namespace["ScratchRuntime"](headless=True, audio=False,
                                          assets_dir=temp_dir)
    sprite = namespace["SvgSprite"]()
    sprite.costumes = [{
        'name': 'shape.svg', 'md5ext': 'shape.svg',
        'dataFormat': 'svg', 'rotationCenterX': 10, 'rotationCenterY': 5,
    }]
    sprite.costume_number = 1
    sprite.costume_name = 'shape.svg'
    runtime.add_sprite(sprite)
    try:
        runtime.render_scale = 2.0
        runtime.costume_cache.clear()
        runtime.costume_image_scales.clear()
        image = runtime.get_sprite_image('shape.svg')
        assert image is not None
        assert image.get_size() == (40, 20), image.get_size()
        assert runtime.get_sprite_image_scale('shape.svg') == 2.0

        _image, rect, x, y, _scale, _direction = sprite._rendered_image()
        assert rect.width == 40 and rect.height == 20, rect
        assert (rect.centerx, rect.centery) == (480, 360)
        half_w, half_h = sprite._sprite_bounds()
        assert abs(half_w - 10) < 1.5 and abs(half_h - 5) < 1.5, \
            f"围栏应按逻辑尺寸计算: {half_w},{half_h}"

        runtime._set_render_scale(1.0)
        image = runtime.get_sprite_image('shape.svg')
        assert image.get_size() == (20, 10), "降低倍率后应重新栅格化"
        assert runtime.get_sprite_image_scale('shape.svg') == 1.0
    finally:
        runtime.running = False
        runtime.shutdown()
        try:
            os.remove(svg_path)
            os.rmdir(temp_dir)
        except OSError:
            pass

    print("  [PASS] SVG 高分辨率渲染通过")
    return True


def test_svg_gradient_and_opacity():
    """SVG 渐变填充、颜色透明度与 group opacity"""
    print("[测试74] SVG 渐变与透明度")

    import tempfile
    import time

    project = make_project({
        "b1": block("event_whenflagclicked", None, None, top_level=True),
    }, name="SvgPaint")
    code = generate_python(parse_scratch_project(project))
    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)

    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20">'
        '<defs><linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="0%">'
        '<stop offset="0%" stop-color="#ff0000"/>'
        '<stop offset="100%" stop-color="#0000ff"/>'
        '</linearGradient></defs>'
        '<rect x="0" y="0" width="40" height="20" fill="url(#g)"/>'
        '<rect x="30" y="0" width="10" height="10" fill="#00ff00" '
        'opacity="0.5"/>'
        '<circle cx="10" cy="15" r="5" fill="rgba(0,255,0,0.5)"/>'
        '</svg>')
    alpha_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
        '<rect width="10" height="10" fill="#00ff00" opacity="50%"/>'
        '</svg>')

    temp_dir = tempfile.mkdtemp()
    svg_path = os.path.join(temp_dir, 'gradient.svg')
    alpha_path = os.path.join(temp_dir, 'alpha.svg')
    with open(svg_path, 'w', encoding='utf-8') as handle:
        handle.write(svg)
    with open(alpha_path, 'w', encoding='utf-8') as handle:
        handle.write(alpha_svg)
    try:
        image = runtime._render_svg(svg_path)
        assert image is not None and image.get_size() == (40, 20)
        left = image.get_at((2, 10))
        right = image.get_at((38, 12))
        assert left[0] > 200 and left[2] < 60, f"左侧应为红色: {left}"
        assert right[2] > 200 and right[0] < 60, f"右侧应为蓝色: {right}"

        overlap = image.get_at((35, 5))
        assert 100 <= overlap[1] <= 160, f"半透明绿色应混入渐变: {overlap}"
        assert overlap[3] == 255, "叠加后应保持不透明"

        circle = image.get_at((10, 15))
        assert 100 <= circle[1] <= 160, f"rgba 圆形应有半透明绿色: {circle}"

        alpha_image = runtime._render_svg(alpha_path)
        pixel = alpha_image.get_at((5, 5))
        assert 120 <= pixel[3] <= 135, f"opacity=50% 的 alpha 应约为 128: {pixel}"

        scaled = runtime._render_svg(svg_path, 2.0)
        assert scaled.get_size() == (80, 40), scaled.get_size()

        # 单次扫描解析：几百个半透明形状也应快速完成
        many = ['<svg xmlns="http://www.w3.org/2000/svg" width="240" '
                'height="180">']
        for index in range(300):
            many.append('<rect x="%d" y="%d" width="12" height="9" '
                        'fill="#%02x%02x%02x" opacity="0.6"/>'
                        % (index % 220, (index * 7) % 170, index % 255,
                           (index * 3) % 255, (index * 5) % 255))
        many.append('</svg>')
        many_path = os.path.join(temp_dir, 'many.svg')
        with open(many_path, 'w', encoding='utf-8') as handle:
            handle.write(''.join(many))
        started = time.time()
        runtime._render_svg(many_path)
        elapsed = time.time() - started
        assert elapsed < 2.0, f"SVG 渲染过慢: {elapsed:.3f}s"
    finally:
        runtime.running = False
        runtime.shutdown()
        for name in os.listdir(temp_dir):
            try:
                os.remove(os.path.join(temp_dir, name))
            except OSError:
                pass
        try:
            os.rmdir(temp_dir)
        except OSError:
            pass

    print("  [PASS] SVG 渐变与透明度通过")
    return True


def test_extensions_package_config():
    """扩展源码包：按 config.json 读取子文件并拼装"""
    print("[测试75] 扩展源码包与 JSON 配置")

    import runtime_code.extensions as package

    assert os.path.exists(package._CONFIG_PATH), "config.json 应存在"
    assert package.HANDLER_GROUPS['pen'][0] == '_extension_pen'
    assert package.HANDLER_GROUPS['lmslisttools'][0] == '_extension_list_tools'
    assert 'pen.py' in package.EXTENSION_CONFIG['pen']['files']
    assert 'def _extension_pen' in package.read_source('pen.py')
    assert 'def _extension_window_controls' in package.EXTENSIONS

    for name, spec in package.EXTENSION_CONFIG.items():
        for filename in spec['files']:
            path = os.path.join(package._DIR, filename)
            assert os.path.exists(path), f"缺少扩展文件: {name} -> {filename}"

    from runtime_code import assemble_extensions
    with_pen, registrations, names = assemble_extensions(['pen'])
    assert '_extension_pen' in names
    assert '_extension_tween' not in names
    assert "'pen': _extension_pen" not in with_pen
    assert registrations['pen'] == '_extension_pen'

    print("  [PASS] 扩展源码包与 JSON 配置通过")
    return True


def test_rendering_caches_and_pen():
    """渲染缓存：变换复用、按倍率复用 SVG、缩放窗口保留画笔"""
    print("[测试76] 渲染缓存与画笔保留")

    import tempfile

    project = make_project({
        "b1": block("event_whenflagclicked", None, None, top_level=True),
    }, name="CacheSprite")
    code = generate_python(parse_scratch_project(project))
    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite = namespace["CacheSprite"]()
    runtime.add_sprite(sprite)

    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="10">'
           '<rect width="20" height="10" fill="#00ff00"/></svg>')
    temp_dir = tempfile.mkdtemp()
    svg_path = os.path.join(temp_dir, 'cache.svg')
    with open(svg_path, 'w', encoding='utf-8') as handle:
        handle.write(svg)
    runtime.assets_dir = temp_dir
    sprite.costumes = [{
        'name': 'cache.svg', 'md5ext': 'cache.svg', 'dataFormat': 'svg',
        'rotationCenterX': 10, 'rotationCenterY': 5,
    }]
    sprite.costume_number = 1
    sprite.costume_name = 'cache.svg'
    try:
        first = sprite._rendered_image()[0]
        second = sprite._rendered_image()[0]
        assert first is second, "外观不变时应复用变换缓存"
        sprite.direction = 45
        rotated = sprite._rendered_image()[0]
        assert rotated is not first, "方向变化后应重新生成"

        runtime.render_scale = 1.0
        image_one = runtime.get_sprite_image('cache.svg')
        runtime._set_render_scale(2.0)
        image_two = runtime.get_sprite_image('cache.svg')
        assert image_two.get_size() == (40, 20), image_two.get_size()
        runtime._set_render_scale(1.0)
        image_again = runtime.get_sprite_image('cache.svg')
        assert image_again is image_one, "切回原倍率应复用已栅格化的位图"

        runtime.pen_clear()
        runtime.pen_draw_segment((0, 0), (40, 0), (255, 0, 0, 255), 10)
        assert runtime._pen_used
        width, height = runtime.pen_layer.get_size()
        assert runtime.pen_layer.get_at((width // 2, height // 2))[3] > 0
        runtime._set_render_scale(2.0)
        assert runtime._pen_used, "缩放窗口不应清空画笔内容"
        width, height = runtime.pen_layer.get_size()
        assert runtime.pen_layer.get_at((width // 2, height // 2))[3] > 0
    finally:
        runtime.running = False
        runtime.shutdown()
        try:
            os.remove(svg_path)
            os.rmdir(temp_dir)
        except OSError:
            pass

    print("  [PASS] 渲染缓存与画笔保留通过")
    return True


def test_global_list_roundtrip():
    """全局列表往返：clear/append 不应变成自制积木"""
    print("[测试77] 全局列表往返解析")

    stage = {
        "isStage": True, "name": "Stage",
        "variables": {"vid_score": ["score", 0]},
        "lists": {"lid_results": ["results", ["a", "b"]]},
        "broadcasts": {}, "blocks": {}, "comments": {},
        "currentCostume": 0, "costumes": [], "sounds": [],
        "volume": 100, "layerOrder": 0,
    }
    runner = {
        "isStage": False, "name": "Runner",
        "variables": {"lcid": ["localCount", 3]},
        "lists": {}, "broadcasts": {},
        "blocks": {
            "b1": block("event_whenflagclicked", "b2", None, top_level=True),
            "b2": block("data_deletealloflist", "b3", "b1",
                        fields={"LIST": ["results", "lid_results"]}),
            "b3": block("data_addtolist", "b4", "b2",
                        inputs={"ITEM": [3, "v1"]},
                        fields={"LIST": ["results", "lid_results"]}),
            "v1": block("data_variable", None, "b3",
                        fields={"VARIABLE": ["localCount", "lcid"]}),
            "b4": block("procedures_call", None, "b3", mutation={
                "tagName": "mutation", "children": [], "proccode": "my proc",
                "argumentids": "[]", "warp": "false"}),
            "p1": block("procedures_definition", "p2", None, top_level=True,
                        inputs={"custom_block": [1, "proto"]}),
            "proto": block("procedures_prototype", None, "p1",
                           mutation={
                               "tagName": "mutation", "children": [],
                               "proccode": "my proc", "argumentids": "[]",
                               "argumentnames": "[]", "argumentdefaults": "[]",
                               "warp": "false"}),
            "p2": block("data_setvariableto", None, "p1",
                        inputs={"VALUE": [1, [10, "x"]]},
                        fields={"VARIABLE": ["score", "vid_score"]}),
        },
        "comments": {}, "currentCostume": 0, "costumes": [], "sounds": [],
        "visible": True, "x": 0, "y": 0, "size": 100, "direction": 90,
        "draggable": False, "rotationStyle": "all around",
        "volume": 100, "layerOrder": 1,
    }
    project = {"targets": [stage, runner], "monitors": [], "extensions": [],
               "meta": {"semver": "3.0.0"}}

    ir = parse_scratch_project(project)
    code = generate_python(ir)
    assert 'self.results.clear()' in code
    assert 'self.results.append(self.localCount)' in code

    restored = parse_python_code(code, 'Runner')
    assert 'results' in restored.global_list_names
    assert 'score' in restored.global_variable_names
    assert 'results' not in restored.lists, "全局列表不应变成角色局部列表"

    types = []
    names = []

    def walk(stmt):
        if stmt is None:
            return
        types.append(stmt.type)
        names.append(stmt.extra.get('name'))
        for child in stmt.body:
            walk(child)
        for child in stmt.else_body:
            walk(child)
        walk(stmt.next)

    for stmt in restored.statements:
        walk(stmt)
    assert BlockType.DELETE_ALL_FROM_LIST in types
    assert BlockType.ADD_TO_LIST in types
    assert BlockType.PROCEDURE_DEFINE in types
    calls = [name for kind, name in zip(types, names)
             if kind == BlockType.PROCEDURE_CALL]
    assert calls == ['my_proc'], f"只应保留真实自制积木调用: {calls}"

    out_project = ProjectIR()
    out_project.add_sprite(ir.stage)
    out_project.add_sprite(restored)
    written = write_scratch_project(out_project)
    targets = {item["name"]: item for item in written["targets"]}
    assert "list_results" in targets["Stage"]["lists"]
    assert "list_results" not in targets["Runner"]["lists"], \
        "角色不应生成同名的局部列表来遮蔽全局列表"
    opcodes = [data.get("opcode")
               for data in targets["Runner"]["blocks"].values()]
    assert "data_deletealloflist" in opcodes
    assert "data_addtolist" in opcodes
    proccodes = [data["mutation"]["proccode"]
                 for data in targets["Runner"]["blocks"].values()
                 if data.get("opcode") == "procedures_call"]
    assert "clear" not in proccodes and "append %s" not in proccodes
    assert "my proc" in proccodes

    # 没有定义的未知方法不应降级成自制积木
    weird = parse_python_code(
        "class Weird(ScratchSprite):\n"
        "    def when_green_flag(self):\n"
        "        self.mystery(1)\n", 'Weird')
    assert all(stmt.type != BlockType.PROCEDURE_CALL
               for stmt in weird.statements)

    print("  [PASS] 全局列表往返解析通过")
    return True


def test_mouse_cursor_stage_scope():
    """MouseCursor 只在舞台区域内生效，工具栏恢复系统箭头"""
    print("[测试78] 光标仅在舞台内生效")

    project = make_project({
        "b1": block("event_whenflagclicked", None, None, top_level=True),
    }, name="CursorSprite")
    project["extensions"] = ["MouseCursor"]
    code = generate_python(parse_scratch_project(project))
    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite = namespace["CursorSprite"]()
    runtime.add_sprite(sprite)
    try:
        # 模拟窗口模式：屏幕 480x360，顶部工具栏 34px，舞台缩放到剩余区域
        runtime._manual_view = True
        runtime.toolbar_height = 34
        assert not runtime._stage_area_contains((8, 6)), "工具栏不属于舞台"
        stage_center = runtime._view_geometry()[1]
        assert runtime._stage_area_contains(
            (stage_center[0] + 50, stage_center[1] + 50))

        sprite.extension('MouseCursor', 'MouseCursor_setCur',
                         {'CUR': 'pointer'}, {})
        runtime._cursor_over_stage = True
        runtime.apply_mouse_cursor()
        assert runtime._applied_cursor == ('system', 'HAND')

        runtime._update_cursor_for_position((8, 6))
        assert runtime._applied_cursor == 'arrow-outside'
        runtime._update_cursor_for_position(
            (stage_center[0] + 50, stage_center[1] + 50))
        assert runtime._applied_cursor == ('system', 'HAND')

        sprite.extension('MouseCursor', 'MouseCursor_hideCur', {}, {})
        assert runtime._applied_cursor == 'hidden'
        runtime._update_cursor_for_position((8, 6))
        assert runtime._applied_cursor == 'arrow-outside', \
            "工具栏上不应隐藏光标"

        # 光标状态不影响绿旗点击
        runtime.flag_clicked = False
        runtime.green_flag = lambda: setattr(runtime, 'flag_clicked', True)
        runtime._handle_click((8, 6))
        assert runtime.flag_clicked, "绿旗按钮应保持可点击"
    finally:
        runtime.running = False
        runtime.shutdown()

    print("  [PASS] 光标仅在舞台内生效通过")
    return True


def test_bundle_output_layout():
    """导出项目文件夹：每个项目独立的 py 与 assets，互不覆盖"""
    print("[测试79] 项目文件夹导出")

    import json
    import shutil
    import tempfile
    import zipfile
    from converter import ScratchConverter

    temp_dir = tempfile.mkdtemp()

    def make_sb3(name, asset):
        path = os.path.join(temp_dir, name + '.sb3')
        data = {
            "targets": [{
                "isStage": True, "name": "Stage", "variables": {},
                "lists": {}, "broadcasts": {}, "blocks": {}, "comments": {},
                "currentCostume": 0,
                "costumes": [{"name": asset, "md5ext": asset,
                              "dataFormat": "svg"}],
                "sounds": [], "volume": 100, "layerOrder": 0,
            }],
            "monitors": [], "extensions": [], "meta": {},
        }
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('project.json',
                             json.dumps(data, ensure_ascii=False))
            archive.writestr(asset, '<svg xmlns="http://www.w3.org/2000/svg" '
                                    'width="2" height="2"></svg>')
        return path

    try:
        first = make_sb3('alpha', 'a.svg')
        second = make_sb3('beta', 'b.svg')
        converter = ScratchConverter()
        converter.scratch_to_python(
            first, os.path.join(temp_dir, 'alpha.py'), bundle=True)
        converter.scratch_to_python(
            second, os.path.join(temp_dir, 'beta.py'), bundle=True)

        assert os.path.exists(os.path.join(temp_dir, 'alpha', 'alpha.py'))
        assert os.path.exists(os.path.join(temp_dir, 'beta', 'beta.py'))
        assert os.path.exists(os.path.join(temp_dir, 'alpha', 'assets', 'a.svg'))
        assert os.path.exists(os.path.join(temp_dir, 'beta', 'assets', 'b.svg'))
        assert not os.path.exists(
            os.path.join(temp_dir, 'alpha', 'assets', 'b.svg'))
        assert not os.path.exists(
            os.path.join(temp_dir, 'beta', 'assets', 'a.svg'))
        assert not os.path.exists(os.path.join(temp_dir, 'alpha.py')), \
            "bundle 模式不应再生成同目录的平铺脚本"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    print("  [PASS] 项目文件夹导出通过")
    return True


def test_asset_preload_and_scale_caps():
    """启动预加载、进度条绘制与清晰度上限"""
    print("[测试80] 资源预加载与清晰度上限")

    import tempfile

    project = make_project({
        "b1": block("event_whenflagclicked", None, None, top_level=True),
    }, name="PreloadSprite")
    code = generate_python(parse_scratch_project(project))
    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite = namespace["PreloadSprite"]()
    runtime.add_sprite(sprite)

    temp_dir = tempfile.mkdtemp()
    small_svg = os.path.join(temp_dir, 'small.svg')
    big_svg = os.path.join(temp_dir, 'big.svg')
    with open(small_svg, 'w', encoding='utf-8') as handle:
        handle.write('<svg xmlns="http://www.w3.org/2000/svg" width="8" '
                     'height="8"><rect width="8" height="8" '
                     'fill="#00ff00"/></svg>')
    with open(big_svg, 'w', encoding='utf-8') as handle:
        handle.write('<svg xmlns="http://www.w3.org/2000/svg" width="8" '
                     'height="8"><rect width="8" height="8" '
                     'fill="#00ff00"/></svg>')
        handle.write(' ' * (520 * 1024))
    runtime.assets_dir = temp_dir
    sprite.costumes = [
        {'name': 'small.svg', 'md5ext': 'small.svg', 'dataFormat': 'svg',
         'rotationCenterX': 4, 'rotationCenterY': 4},
        {'name': 'big.svg', 'md5ext': 'big.svg', 'dataFormat': 'svg',
         'rotationCenterX': 4, 'rotationCenterY': 4},
    ]
    try:
        assert runtime.max_render_scale == 3.0
        assert runtime._costume_scale_cap('small.svg') == 3.0
        assert runtime._costume_scale_cap('big.svg') == 2.0

        runtime.render_scale = 1.0
        runtime._preload_assets()
        assert 'small.svg' in runtime._preloaded_names
        assert 'big.svg' in runtime._preloaded_names
        assert runtime.get_sprite_image('small.svg') is not None
        assert runtime.get_sprite_image('big.svg') is not None

        # 进度条绘制不应报错
        runtime._draw_loading(1, 2)
        runtime._draw_loading(2, 2)
    finally:
        runtime.running = False
        runtime.shutdown()
        try:
            os.remove(small_svg)
            os.remove(big_svg)
            os.rmdir(temp_dir)
        except OSError:
            pass

    print("  [PASS] 资源预加载与清晰度上限通过")
    return True


def test_broadcast_input_order():
    """广播发送端必须写成 [11, 名字, ID]，否则消息名会被解析成ID"""
    print("[测试87] 广播发送端名字/ID顺序")

    code = '''class Cat(ScratchSprite):
    def when_green_flag(self):
        self.broadcast("go")
        self.broadcast_and_wait("done")

    def when_broadcast_go(self):
        self.say("received")
'''
    sprite = parse_python_code(code, "Cat")
    data = write_scratch_project(python_to_project(sprite))
    blocks = get_sprite(data["targets"])["blocks"]
    sends = [item for item in blocks.values()
             if item.get("opcode") in ("event_broadcast",
                                       "event_broadcastandwait")]
    assert len(sends) == 2, "应有普通广播与等待广播各一个"
    for item in sends:
        payload = item["inputs"]["BROADCAST_INPUT"][1]
        assert payload[0] == 11
        assert payload[2] == "bc_" + payload[1], "第三项应为 bc_<名字>"
    assert sorted(item["inputs"]["BROADCAST_INPUT"][1][1]
                  for item in sends) == ["done", "go"]

    # 重新解析回来，发送端与接收端的消息名必须一致
    regenerated = generate_python(parse_scratch_project(data))
    assert "self.broadcast('go')" in regenerated
    assert "self.broadcast_and_wait('done')" in regenerated
    assert "def when_broadcast_go(self):" in regenerated

    # 非标准变体：消息只写在 fields 里时也要能解析
    legacy = make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("event_broadcast", None, "b1",
                    fields={"BROADCAST_OPTION": ["legacy", "bc_legacy"]}),
        "h1": block("event_whenbroadcastreceived", None, None, top_level=True,
                    fields={"BROADCAST_INPUT": ["legacy", "bc_legacy"]}),
    }, name="LegacyBc")
    legacy_code = generate_python(parse_scratch_project(legacy))
    assert "self.broadcast('legacy')" in legacy_code
    assert "def when_broadcast_legacy(self):" in legacy_code

    # 实际运行：广播接收端必须被触发
    import time
    namespace = {}
    exec(compile(regenerated, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    cat = namespace["Cat"]()
    runtime.add_sprite(cat)
    try:
        cat.run()
        runtime.green_flag()
        for _ in range(20):
            runtime.step()
            time.sleep(0.004)
            if cat._say_text == 'received':
                break
        assert cat._say_text == 'received', "广播接收端应收到 go"
    finally:
        runtime.running = False
        runtime.shutdown()

    print("  [PASS] 广播发送端名字/ID顺序通过")
    return True


TESTS = [
    test_variable_shadowing_fidelity,
    test_scheduler_fairness_with_clones,
    test_list_tools_extension,
    test_new_runtime_extensions,
    test_slider_monitor,
    test_warp_render_semantics,
    test_conversion_log,
    test_on_demand_extension_assembly,
    test_svg_high_resolution_rendering,
    test_svg_gradient_and_opacity,
    test_extensions_package_config,
    test_rendering_caches_and_pen,
    test_global_list_roundtrip,
    test_mouse_cursor_stage_scope,
    test_bundle_output_layout,
    test_asset_preload_and_scale_caps,
    test_broadcast_input_order,
]
