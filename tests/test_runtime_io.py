# -*- coding: utf-8 -*-
"""由 test_all.py 拆分出的测试模块"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import *


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


def test_timer_greater_than_hat():
    """当计时器 > 值 帽子事件：条件由假变真时触发一次，重复为真不重复触发"""
    print("[测试49] 当计时器大于设定值")

    project = make_project({
        "b1": block("event_whengreaterthan", "b2", None, top_level=True,
                    inputs={"VALUE": [1, [4, "0.05"]]},
                    fields={"WHENGREATERTHANMENU": ["TIMER", None]}),
        "b2": block("data_changevariableby", None, "b1",
                    inputs={"VALUE": [1, [4, "1"]]},
                    fields={"VARIABLE": ["hits", "v1"]}),
    }, name="TimerHat")
    project["targets"][0]["variables"] = {"v1": ["hits", 0]}

    ir = parse_scratch_project(project)
    code = generate_python(ir)
    assert "_register_greater_than('timer'" in code, "应生成计时器帽子注册"

    # 往返：Scratch -> Python -> Scratch 保留菜单和阈值
    written = write_scratch_project(ir)
    hats = [b for b in written["targets"][-1]["blocks"].values()
            if isinstance(b, dict) and b.get("opcode") == "event_whengreaterthan"]
    assert hats, "往返后应保留当计时器大于帽子"
    assert hats[0]["fields"]["WHENGREATERTHANMENU"][0] == "TIMER"
    assert hats[0]["inputs"].get("VALUE"), "应写入阈值输入"

    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite = namespace["TimerHat"]()
    runtime.add_sprite(sprite)
    sprite.run()
    runtime.green_flag()
    try:
        import time
        deadline = time.time() + 5
        while time.time() < deadline and sprite.hits == 0:
            runtime.step()
            time.sleep(0.01)
        assert sprite.hits >= 1, "计时器超过阈值后脚本应运行"

        for _ in range(10):
            runtime.step()
            time.sleep(0.01)
        assert sprite.hits == 1, \
            f"条件持续为真时不应重复触发: {sprite.hits}"

        # 重置计时器 -> 条件变假，再次超过阈值时应重新触发
        runtime.reset_timer()
        sprite.hits = 0
        deadline = time.time() + 5
        while time.time() < deadline and sprite.hits == 0:
            runtime.step()
            time.sleep(0.01)
        assert sprite.hits >= 1, "重置计时器后应再次触发"
    finally:
        runtime.running = False
        runtime.shutdown()

    print("  [PASS] 当计时器大于设定值通过")
    return True


def test_backdrop_hat_roundtrip():
    """当背景换成 帽子事件在往返中保留背景名"""
    print("[测试50] 背景帽子事件往返")

    project = make_project({
        "b1": block("event_whenbackdropswitchesto", None, None, top_level=True,
                    fields={"BACKDROP": ["夜景", None]}),
    }, name="BackdropHat")
    ir = parse_scratch_project(project)
    hat = next(s for s in ir.sprites[0].statements
               if s.type == BlockType.WHEN_BACKDROP_SWITCHES)
    assert hat.extra.get('backdrop') == '夜景'

    written = write_scratch_project(ir)
    backdrop_fields = [b["fields"]["BACKDROP"][0]
                       for b in written["targets"][-1]["blocks"].values()
                       if isinstance(b, dict) and b.get("opcode")
                       == "event_whenbackdropswitchesto"]
    assert backdrop_fields == ["夜景"], f"写回应保留背景名: {backdrop_fields}"

    code = generate_python(ir)
    restored = python_to_project(parse_python_code(code, "BackdropHat"))
    restored_hat = next(s for s in restored.sprites[0].statements
                        if s.type == BlockType.WHEN_BACKDROP_SWITCHES)
    assert restored_hat.extra.get('backdrop') == '夜景', \
        f"Python往返后背景名丢失: {restored_hat.extra}"

    print("  [PASS] 背景帽子事件往返通过")
    return True


def test_pitch_sound_resampling():
    """音高特效真正改变音调：rate = 2^(pitch/120)，且结果会缓存"""
    print("[测试51] 音高变调")

    project = make_project({
        "b1": block("event_whenflagclicked", None, None, top_level=True),
    }, name="Pitch")
    code = generate_python(parse_scratch_project(project))
    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    pygame = namespace["pygame"]
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite = namespace["Pitch"]()
    runtime.add_sprite(sprite)

    import array as array_module
    previous_driver = os.environ.get('SDL_AUDIODRIVER')
    os.environ['SDL_AUDIODRIVER'] = 'dummy'
    try:
        if pygame.mixer.get_init() is None:
            pygame.mixer.init(frequency=22050, size=-16, channels=1)
    except Exception:
        print("  [PASS] 音高变调（当前环境无音频设备，跳过校验）")
        return True

    try:
        frequency, _size, channels = pygame.mixer.get_init()
        total = frequency
        samples = array_module.array('h')
        for index in range(total):
            samples.append(int(10000 * math.sin(2 * math.pi * 440 * index / frequency)))
        sound = pygame.mixer.Sound(buffer=samples.tobytes())

        assert runtime._pitched_sound(sound, 'tone', 0) is sound, \
            "音高为 0 时应复用原 Sound"
        base = sound.get_length()
        higher = runtime._pitched_sound(sound, 'tone', 120)
        assert higher is not sound, "音高 +120 应生成变调副本"
        assert abs(higher.get_length() - base / 2) < 0.1, \
            f"高八度时长应减半: {base} -> {higher.get_length()}"
        assert runtime._pitched_sound(sound, 'tone', 120) is higher, \
            "同一音高应命中缓存"
        lower = runtime._pitched_sound(sound, 'tone', -120)
        assert abs(lower.get_length() - base * 2) < 0.2, \
            f"低八度时长应加倍: {base} -> {lower.get_length()}"
    finally:
        pygame.mixer.quit()
        if previous_driver is None:
            os.environ.pop('SDL_AUDIODRIVER', None)
        else:
            os.environ['SDL_AUDIODRIVER'] = previous_driver
        runtime.running = False
        runtime.shutdown()

    print("  [PASS] 音高变调通过")
    return True


TESTS = [
    test_ask_input_box,
    test_mouse_clamp_and_fencing,
    test_stage_clear_with_tiny_backdrop,
    test_runtime_debug_overlay,
    test_distortion_effects,
    test_chinese_sprite_instance_name,
    test_timer_greater_than_hat,
    test_backdrop_hat_roundtrip,
    test_pitch_sound_resampling,
]
