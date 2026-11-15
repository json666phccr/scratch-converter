# -*- coding: utf-8 -*-
"""pygame 运行时主类模板"""

RUNTIME_CLASS = r'''class ScratchRuntime:
    """Scratch 3.0 / TurboWarp pygame运行时。

    通过 ScratchRuntime.register_extension(name, handler) 注册扩展，
    扩展handler签名为 handler(runtime, sprite, opcode, inputs, fields)。
    内置 pen、runtimeoptions、music、Tween、Clones+、Looks+、
    More Events、Temporary Variables 等常用扩展。
    """

    EXTENSIONS = {}
    FPS = 30
    STAGE_WIDTH = 480
    STAGE_HEIGHT = 360
    # 导出变量时排除的角色内置属性
    JSON_BUILTIN_ATTRS = {
        'x', 'y', 'direction', 'visible', 'size', 'costume_number',
        'costume_name', 'volume', 'answer', 'mouse_x', 'mouse_y',
        'mouse_down', 'timer', 'loudness', 'days_since_2000',
        'rotation_style', 'name', 'costumes', 'sounds', 'draggable',
    }

    def __init__(self, headless=False, fps=None, trace=False, audio=True,
                 assets_dir=None, interpolation=False, turbo=False,
                 fencing=True, infinite_clones=False, misc_limits=True,
                 hq_pen=False, stage_size=None, warp_timer=0.5,
                 disable_compiler=False, maximize=True):
        if pygame is None:
            raise RuntimeError("运行生成的脚本需要pygame: pip install pygame")
        self.headless = headless
        self.maximize = maximize
        self.fps = fps or self.FPS
        self.trace = trace
        self.assets_dir = assets_dir or ASSETS_DIR
        self.interpolation = interpolation
        self.turbo = turbo
        self.fencing = fencing
        self.infinite_clones = infinite_clones
        self.clone_limit = None if infinite_clones else 300
        self.misc_limits = misc_limits
        self.hq_pen = hq_pen
        self.warp_timer = warp_timer
        self.disable_compiler = disable_compiler
        if stage_size:
            self.stage_width, self.stage_height = int(stage_size[0]), int(stage_size[1])
        else:
            self.stage_width, self.stage_height = self.STAGE_WIDTH, self.STAGE_HEIGHT
        if headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.display.init()
        pygame.font.init()
        self._create_display(maximize=self.maximize)
        pygame.display.set_caption(
            "Scratch 3.0 Runtime " + _RUNTIME_VERSION
            + " (ESC 退出，F1 调试信息，可自由拉伸窗口)")
        if not self.headless:
            print("[runtime] Scratch 3 运行时 v" + _RUNTIME_VERSION
                  + "，按 F1 显示/隐藏调试面板")
        self.pen_layer = pygame.Surface((self.stage_width, self.stage_height),
                                        pygame.SRCALPHA)
        # 画笔图层是否画过东西：为空时跳过整层合成
        self._pen_used = False
        self._pen_color_cache = {}
        self.clock = pygame.time.Clock()
        self.sprites = []
        self.scripts = []
        self.turn_lock = threading.Lock()
        self.running = True
        self.frame = 0
        self.frame_condition = threading.Condition()
        self.start_time = time.time()
        self.timer_offset = 0.0
        # “2000年以来的天数”按本地时间计算，与Scratch一致
        self.epoch_2000 = time.mktime((2000, 1, 1, 0, 0, 0, 0, 0, -1))
        self.keys = set()
        self.mouse_down = False
        self.mouse_x = 0
        self.mouse_y = 0
        self.current_backdrop = 0
        self.stage_sprite = None
        self.counter = 0
        self.dragging = None
        self.dragging_offset = (0, 0)
        self.ask_pending = False
        self.ask_visible = False
        self.ask_question = ''
        self.ask_buffer = ''
        self.ask_composition = ''
        self.ask_key_pending = ''
        self.ask_answer = ''
        self.ask_token = 0
        self.ask_lock = threading.Lock()
        self.debug_overlay = False
        self._debug_events = []
        # 响度：安装 sounddevice + numpy 时用麦克风，否则恒为 0
        self.loudness = 0
        self._mic_value = 0.0
        self._mic_stream = None
        # Scratch 的“用户名”默认是 player，可设置环境变量 SCRATCH_USERNAME 覆盖
        self.username = os.environ.get('SCRATCH_USERNAME') or 'player'
        self._init_microphone()
        # pygame 2 起文本输入走 TEXTINPUT（支持中文输入法），不再用 KEYDOWN.unicode
        self._has_text_input = hasattr(pygame, 'TEXTINPUT')
        self.answer = ''
        self.music_tempo = 60.0
        self.music_instrument = 1
        self.music_cache = {}
        self.dynamic_monitors = []
        self.mask_cache = {}
        font_path = None
        for filename in ("msyh.ttc", "simhei.ttf", "arial.ttf"):
            candidate = os.path.join(os.environ.get("WINDIR", "C:\Windows"),
                                     "Fonts", filename)
            if os.path.exists(candidate):
                font_path = candidate
                break
        self.font = pygame.font.Font(font_path, 14) if font_path else pygame.font.Font(None, 14)
        self.font_path = font_path
        self.costume_cache = {}
        self.sound_cache = {}
        # Temporary Variables 扩展的运行时变量（每次绿旗/停止时清空）
        self.ext_runtime_vars = {}
        # 旧版临时变量扩展的变量（只有显式删除才清空）
        self.ext_legacy_vars = {}
        # Looks+ 的“修改造型内容”覆盖：{造型资源名: svg文本}
        self.costume_text_overrides = {}
        # 音高效变调后的 Sound 缓存：(资源路径, 音高) -> Sound
        self._pitched_cache = {}
        # 艺术字字体缓存：(字体名, 字号) -> pygame.font.Font
        self._text_font_cache = {}
        # 文字朗读（text2speech）：优先 pyttsx3，Windows 上退回到系统 SAPI
        self.tts_voice = 'alto'
        self.tts_language = 'English'
        self._tts_engine = None
        self._tts_failed = False
        self._tts_warned = False
        self.mixer_ready = False
        if audio:
            try:
                pygame.mixer.init()
                self.mixer_ready = True
            except Exception:
                pass
        self.background = self._load_image(STAGE_COSTUME) if STAGE_COSTUME else None
        if self.background is not None:
            self.background = pygame.transform.smoothscale(
                self.background, (self.stage_width, self.stage_height))
        # 内置TurboWarp扩展
        self.register_extension('pen', _extension_pen)
        self.register_extension('runtimeoptions', _extension_runtimeoptions)
        self.register_extension('runtime-options', _extension_runtimeoptions)
        self.register_extension('turbowarp', _extension_runtimeoptions)
        self.register_extension('tw', _extension_runtimeoptions)
        self.register_extension('music', _extension_music)
        self.register_extension('text2speech', _extension_text2speech)
        self.register_extension('speech', _extension_text2speech)
        self.register_extension('stretch', _extension_stretch)
        self.register_extension('text', _extension_text)
        self.register_extension('skyhigh173JSON', _extension_skyhigh_json)
        self.register_extension('skyhigh173json', _extension_skyhigh_json)
        for name in ('lmsclonesplus', 'lmsClonesPlus'):
            self.register_extension(name, _extension_clones_plus)
        for name in ('lmsLooksPlus', 'lmslooksplus'):
            self.register_extension(name, _extension_looks_plus)
        for name in ('lmsMoreEvents', 'lmsmoreevents'):
            self.register_extension(name, _extension_more_events)
        for name in ('lmsTempVars2', 'lmstempvars2', 'lmstempvars'):
            self.register_extension(name, _extension_temp_vars)
        for name in ('jeremygamerTweening', 'jeremygamertweening'):
            self.register_extension(name, _extension_tween)

    @classmethod
    def register_extension(cls, name, handler):
        cls.EXTENSIONS[name] = handler

    def call_extension(self, sprite, namespace, opcode, inputs=None, fields=None):
        handler = self.EXTENSIONS.get(namespace)
        if handler is None:
            handler = self.EXTENSIONS.get(str(namespace).lower())
        if handler is None:
            return 0
        return handler(self, sprite, opcode, inputs or {}, fields or {})

    def set_framerate(self, fps):
        self.fps = max(1, min(250, int(fps))) if fps else 0

    def _create_display(self, maximize=False):
        """创建可自由拉伸的窗口，启动时最大化，舞台按宽高比缩放到最大可用区域。

        不使用 pygame.SCALED：在高DPI屏幕上 SCALED 可能只按固定整数倍放大，
        导致舞台只占窗口一部分。这里始终把逻辑舞台软件缩放到窗口实际像素，
        保证最大化后一定填满可用区域（保留宽高比，多余部分补黑边）。
        """
        width, height = self.stage_width, self.stage_height
        self._scaled_view = False
        self._manual_view = False
        self.view_scale = 1.0
        self.view_offset = (0, 0)
        self._view_size = None
        self._view_scaled = None
        if self.headless:
            self.toolbar_height = 0
            self.screen = pygame.display.set_mode((width, height))
            self.stage_surface = self.screen
            return
        # 窗口顶部留一条工具栏放绿旗（类似 Scratch），舞台在工具栏下方缩放
        self.toolbar_height = 34
        try:
            self.screen = pygame.display.set_mode(
                (width, height + self.toolbar_height), pygame.RESIZABLE)
        except pygame.error:
            self.screen = pygame.display.set_mode(
                (width, height + self.toolbar_height))
        self.stage_surface = pygame.Surface((width, height))
        self._manual_view = True
        if maximize:
            self._maximize_window()

    def _maximize_window(self):
        """把窗口最大化到桌面可用区域（类似 Scratch 舞台放大到最大）"""
        try:
            if os.name == 'nt':
                import ctypes
                hwnd = pygame.display.get_wm_info().get('window')
                if hwnd:
                    ctypes.windll.user32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE
                    return
            maximize = getattr(pygame.display, 'maximize', None)
            if maximize is not None:
                maximize()
        except Exception:
            pass

    def _view_geometry(self):
        """返回 (缩放比, 黑边偏移, 绘制尺寸)；工具栏占用的高度不计入舞台区域"""
        window_width, window_height = self.screen.get_size()
        toolbar = getattr(self, 'toolbar_height', 0)
        if window_width <= 0 or window_height <= 0:
            return 1.0, (0, toolbar), (self.stage_width, self.stage_height)
        available = max(1, window_height - toolbar)
        scale = min(window_width / float(self.stage_width),
                    available / float(self.stage_height))
        draw_width = max(1, int(self.stage_width * scale))
        draw_height = max(1, int(self.stage_height * scale))
        return (draw_width / float(self.stage_width),
                ((window_width - draw_width) // 2,
                 toolbar + (available - draw_height) // 2),
                (draw_width, draw_height))

    def _window_to_stage(self, pos):
        """窗口坐标 -> 舞台逻辑坐标（窗口缩放/最大化后仍能正确点击）"""
        if not self._manual_view:
            return pos
        scale, offset, _size = self._view_geometry()
        return ((pos[0] - offset[0]) / scale, (pos[1] - offset[1]) / scale)

    def _present(self):
        """把逻辑舞台呈现到窗口；按宽高比居中放大到窗口最大可用区域"""
        if self._manual_view:
            scale, offset, (draw_width, draw_height) = self._view_geometry()
            self.view_scale = scale
            self.view_offset = offset
            window_width, window_height = self.screen.get_size()
            if window_width <= 0 or window_height <= 0:
                return
            if self._view_scaled is None or self._view_size != (draw_width, draw_height):
                self._view_size = (draw_width, draw_height)
                self._view_scaled = pygame.Surface((draw_width, draw_height)).convert()
            if self._view_size == (self.stage_width, self.stage_height):
                self._view_scaled.blit(self.stage_surface, (0, 0))
            else:
                pygame.transform.smoothscale(self.stage_surface,
                                             (draw_width, draw_height),
                                             self._view_scaled)
            self.screen.fill((0, 0, 0))
            self.screen.blit(self._view_scaled, offset)
            self._draw_toolbar()
        pygame.display.flip()

    def _green_flag_rect(self):
        """绿旗按钮在窗口中的位置（位于顶部工具栏内）"""
        return pygame.Rect(8, 6, 22, 22)

    def _stop_rect(self):
        """停止按钮在窗口中的位置（位于顶部工具栏内，绿旗右侧）"""
        return pygame.Rect(38, 6, 22, 22)

    def _draw_toolbar(self):
        """窗口顶部工具栏：绿旗与停止按钮，避免和舞台内容重叠"""
        toolbar = getattr(self, 'toolbar_height', 0)
        if toolbar <= 0:
            return
        width = self.screen.get_width()
        pygame.draw.rect(self.screen, (245, 245, 245), (0, 0, width, toolbar))
        pygame.draw.line(self.screen, (200, 200, 200),
                         (0, toolbar - 1), (width, toolbar - 1))
        flag = self._green_flag_rect()
        pygame.draw.rect(self.screen, (255, 255, 255),
                         flag.inflate(4, 4), border_radius=5)
        pygame.draw.polygon(self.screen, (60, 170, 90), [
            (flag.x + 4, flag.bottom - 3), (flag.x + 4, flag.y + 2),
            (flag.right - 2, flag.y + 2), (flag.right - 2, flag.centery),
            (flag.x + 4, flag.centery)])
        stop = self._stop_rect()
        pygame.draw.rect(self.screen, (255, 255, 255),
                         stop.inflate(4, 4), border_radius=5)
        center = stop.center
        radius = stop.width / 2.0
        points = []
        for index in range(8):
            angle = math.pi / 8 + index * math.pi / 4
            points.append((center[0] + radius * math.cos(angle) * 0.92,
                           center[1] + radius * math.sin(angle) * 0.92))
        pygame.draw.polygon(self.screen, (220, 70, 60), points)

    def resize_stage(self, width, height):
        width = max(1, int(width))
        height = max(1, int(height))
        if width == self.stage_width and height == self.stage_height:
            return
        self.stage_width, self.stage_height = width, height
        self.pen_layer = pygame.Surface((width, height), pygame.SRCALPHA)
        self._pen_used = False
        if self.background is not None:
            self.background = pygame.transform.smoothscale(self.background, (width, height))
        self._create_display(maximize=self.maximize)

    def pen_clear(self):
        self.pen_layer.fill((0, 0, 0, 0))
        self._pen_used = False

    def pen_color(self, hue, saturation, brightness, alpha):
        """画笔颜色缓存：同样颜色的线段不必每段重算 HSV"""
        key = (int(round(_sc_num(hue))),
               int(round(_sc_num(saturation))),
               int(round(_sc_num(brightness))),
               int(round(_sc_num(alpha))))
        cached = self._pen_color_cache.get(key)
        if cached is not None:
            return cached
        color = _hsv_to_rgb(key[0], key[1], key[2])
        if key[3] > 0:
            color = color + (int(255 * (1 - key[3] / 100.0)),)
        if len(self._pen_color_cache) > 256:
            self._pen_color_cache.clear()
        self._pen_color_cache[key] = color
        return color

    def pen_draw_segment(self, start, end, color, size, cap_start=False):
        size = max(1, int(size))
        if len(color) > 3 and color[3] <= 0:
            # 完全透明（透明度 100）的线段不会改变画面
            return
        sx = int(self.stage_width / 2 + start[0])
        sy = int(self.stage_height / 2 - start[1])
        ex = int(self.stage_width / 2 + end[0])
        ey = int(self.stage_height / 2 - end[1])
        self._pen_used = True
        pygame.draw.line(self.pen_layer, color, (sx, sy), (ex, ey), size)
        if size > 1:
            radius = size // 2
            # 起点圆帽通常已被上一段终点圆帽覆盖，只画终点即可
            if cap_start:
                pygame.draw.circle(self.pen_layer, color, (sx, sy), radius)
            pygame.draw.circle(self.pen_layer, color, (ex, ey), radius)
        if self.hq_pen:
            pygame.draw.aaline(self.pen_layer, color, (sx, sy), (ex, ey))

    def pen_stamp(self, sprite):
        # 图章使用角色当前外观：颜色/亮度/透明度/形状特效都会一起盖上去
        transformed, rect, x, y, scale, _direction = sprite._rendered_image()
        if transformed is not None:
            self.pen_layer.blit(transformed, rect)
        else:
            pygame.draw.circle(self.pen_layer, sprite._placeholder_color(),
                               (x, y), max(6, int(20 * scale)))
        self._pen_used = True

    def add_sprite(self, sprite):
        sprite._runtime = self
        self.sprites.append(sprite)
        if getattr(sprite, 'is_stage', False):
            self.stage_sprite = sprite

    def remove_sprite(self, sprite):
        if sprite in self.sprites:
            self.sprites.remove(sprite)

    def find_sprite(self, name):
        """按名字找角色，优先返回本体（原版Scratch的sensing/运动积木都基于本体）"""
        fallback = None
        for sprite in self.sprites:
            if sprite.name != name:
                continue
            if not getattr(sprite, '_is_clone', False):
                return sprite
            if fallback is None:
                fallback = sprite
        return fallback

    def _find_list(self, sprite, name):
        """按名字/标识找列表，返回 (容器, 键)；全局列表的容器是 GLOBALS"""
        text = _sc_str(name)
        candidates = [sprite] + list(self.sprites)
        if self.stage_sprite is not None:
            candidates.append(self.stage_sprite)
        for target in candidates:
            # 只看自己的属性，不能走 __getattr__：否则全局列表会从 GLOBALS
            # 读出来，却把角色自己的 __dict__ 当成容器，导致 KeyError
            data = getattr(target, '__dict__', None)
            if not isinstance(data, dict):
                continue
            for key in (_sc_ident(text, 'lst'), text):
                if isinstance(data.get(key), list):
                    return data, key
        for key in (_sc_ident(text, 'lst'), text):
            if isinstance(GLOBALS.get(key), list):
                return GLOBALS, key
        return None, None

    def elapsed(self):
        return max(0.0, time.time() - self.start_time - self.timer_offset)

    def reset_timer(self):
        self.timer_offset = time.time() - self.start_time

    def green_flag(self):
        self.running = True
        self.start_time = time.time()
        self.timer_offset = 0.0
        self.answer = ''
        if self.trace:
            print("[trace] green flag")
        # 绿旗会删除所有克隆体，并重启动原有脚本
        for sprite in list(self.sprites):
            if getattr(sprite, "_is_clone", False):
                sprite._running = False
                self.sprites.remove(sprite)
        self.stop_all_scripts()
        self.stop_sounds()
        # Temporary Variables 的运行时变量在项目开始时清空
        self.ext_runtime_vars = {}
        for sprite in list(self.sprites):
            # 绿旗会清空音效，但保留图形特效与造型
            sprite._sound_effects = {'pitch': 0.0, 'pan': 0.0}
            # 原版艺术字扩展在开始/停止时隐藏所有文字
            sprite._text_state = None
            for item in getattr(sprite, '_conditions', ()):
                item[3] = False
            for entry in getattr(sprite, '_frame_hats', ()):
                entry['state'] = None
                entry['thread'] = None
        time.sleep(0.02)
        for sprite in list(self.sprites):
            sprite._global_running = True
            for func in list(sprite._handlers.get("green_flag", [])):
                self.start_script(func)

    def start_script(self, func, received_data=None):
        sprite = getattr(func, "__self__", None)
        context = _ScriptContext()
        context.sprite = sprite
        context.func = func
        context.received_data = received_data
        self.scripts.append(context)

        def runner():
            # threading.local 必须在线程内部赋值，否则主线程的context会串到脚本线程
            if sprite is not None:
                sprite._local.context = context
                sprite._local.turn_owned = False
                sprite._turn_acquire()
            name = getattr(sprite, "name", getattr(func, "__name__", "script"))
            if self.trace:
                print("[trace] start", name, getattr(func, "__name__", ""))
            try:
                func()
            except StopIteration:
                pass
            except Exception:
                import traceback
                traceback.print_exc()
            finally:
                if sprite is not None:
                    sprite._turn_release()
                if context in self.scripts:
                    self.scripts.remove(context)
                if sprite is not None and getattr(sprite._local, "context", None) is context:
                    sprite._local.context = None
                if self.trace:
                    print("[trace] finish", name)

        thread = threading.Thread(target=runner, daemon=True)
        # 供 More Events 的 while 帽子在条件变假时停止对应线程
        thread._scratch_context = context
        thread.start()
        return thread

    def wait_frame(self, context=None):
        with self.frame_condition:
            current = self.frame
            while (self.running and self.frame == current and
                   (context is None or context.running)):
                self.frame_condition.wait(0.1)

    def ask(self, question, context=None):
        """在舞台上显示输入框并等待玩家输入

        同一时刻只允许一个询问：多个脚本同时询问时排队执行，
        避免后者清空前者的输入状态，导致输入框“卡住”。
        """
        def alive():
            return self.running and (context is None or context.running)

        # 抢询问锁；脚本被停止时也能退出等待
        while alive():
            if self.ask_lock.acquire(timeout=0.1):
                break
        else:
            return ''
        token = 0
        try:
            if not alive():
                return ''
            self.ask_token += 1
            token = self.ask_token
            self.ask_question = _sc_str(question)
            self.ask_buffer = ''
            self.ask_composition = ''
            self.ask_key_pending = ''
            self.ask_answer = ''
            self.ask_visible = True
            self.ask_pending = True
            if self.trace:
                print("[trace] ask", repr(self.ask_question))
            while alive() and self.ask_pending and self.ask_token == token:
                self.wait_frame()
            return self.ask_answer
        finally:
            if token and self.ask_token == token:
                self.ask_pending = False
                self.ask_visible = False
                self.ask_question = ''
                self.ask_composition = ''
                if self.trace:
                    print("[trace] ask done", repr(self.ask_answer))
            self.ask_lock.release()

    def _ask_rect(self):
        return pygame.Rect(20, self.stage_height - 60,
                           max(80, self.stage_width - 40), 40)

    def _ask_button_rect(self):
        rect = self._ask_rect()
        return pygame.Rect(rect.right - 66, rect.y + 7, 58, 26)

    def _ask_append_text(self, text):
        """TEXTINPUT 兜底：KEYDOWN 已经加入过的字符不重复添加"""
        pending = self.ask_key_pending
        for ch in text:
            if pending.startswith(ch):
                pending = pending[1:]
            else:
                self.ask_buffer += ch
        self.ask_key_pending = pending

    def _submit_ask(self):
        """回车/点击确认时提交输入"""
        self.ask_answer = self.ask_buffer + self.ask_composition
        self.ask_key_pending = ''
        self.ask_pending = False
        # 点击确认/回车后立刻停止渲染询问框，不等脚本线程调度
        self.ask_visible = False
        if self.trace:
            print("[trace] ask submit", repr(self.ask_answer))

    def _draw_ask(self):
        if not self.ask_visible or not self.ask_pending:
            return
        rect = self._ask_rect()
        pygame.draw.rect(self.stage_surface, (255, 255, 255), rect, border_radius=6)
        pygame.draw.rect(self.stage_surface, (90, 90, 90), rect, 1, border_radius=6)
        text = self.ask_question + ' ' + self.ask_buffer + self.ask_composition + '_'
        surface = self.font.render(text, True, (30, 30, 30))
        area_width = max(20, rect.width - 90)
        if surface.get_width() > area_width:
            # 文字太长时只显示末尾（当前输入的内容）
            clipped = pygame.Surface((area_width, rect.height - 8), pygame.SRCALPHA)
            clipped.blit(surface, (area_width - surface.get_width(), 0))
            surface = clipped
        self.stage_surface.blit(surface, (rect.x + 8, rect.y + 11))
        button = self._ask_button_rect()
        pygame.draw.rect(self.stage_surface, (80, 135, 220), button, border_radius=5)
        label = self.font.render('确认', True, (255, 255, 255))
        self.stage_surface.blit(label, label.get_rect(center=button.center))

    def stop_all_scripts(self):
        for context in list(self.scripts):
            context.running = False
        for sprite in self.sprites:
            sprite._global_running = False
        with self.frame_condition:
            self.frame_condition.notify_all()

    def stop_other_scripts(self, sprite):
        current = getattr(sprite._local, "context", None)
        for context in list(self.scripts):
            if context.sprite is sprite and context is not current:
                context.running = False
        with self.frame_condition:
            self.frame_condition.notify_all()

    def broadcast(self, message, data=None):
        message = _sc_str(message)
        if self.trace:
            print("[trace] broadcast", message)
        return self.broadcast_to(message, list(self.sprites), data)

    def broadcast_to(self, message, targets, data=None):
        """只向指定目标（含其克隆体）发送广播，可附带 received data"""
        message = _sc_str(message)
        if not message:
            return []
        threads = []
        for sprite in list(targets):
            sprite._running = True
            for func in list(sprite._handlers.get("broadcast:" + message, [])):
                threads.append(self.start_script(func, received_data=data))
        return threads

    def broadcast_and_wait(self, message, context=None, data=None):
        for thread in self.broadcast(message, data):
            while (thread.is_alive() and self.running and
                   (context is None or context.running)):
                self.wait_frame(context)

    def stop_scripts_of(self, sprite):
        """停止某个角色（不含克隆体）的所有脚本"""
        if sprite is None:
            return
        sprite._running = False
        for context in list(self.scripts):
            if context.sprite is sprite:
                context.running = False
        with self.frame_condition:
            self.frame_condition.notify_all()

    def dispose_clone(self, clone):
        """删除克隆体并停止它正在运行的脚本"""
        if clone is None or not getattr(clone, '_is_clone', False):
            return
        self.stop_scripts_of(clone)
        self.remove_sprite(clone)

    def stop_clicked(self):
        """停止按钮：停止所有脚本，然后触发 More Events 的停止帽子"""
        self.stop_all_scripts()
        self.stop_sounds()
        self.ext_runtime_vars = {}
        for sprite in list(self.sprites):
            sprite._running = True
            sprite._global_running = True
            for func in list(sprite._handlers.get('stop_clicked', [])):
                self.start_script(func)
        with self.frame_condition:
            self.frame_condition.notify_all()

    def _key_name(self, key):
        names = {
            pygame.K_SPACE: "space", pygame.K_RETURN: "enter",
            pygame.K_UP: "up arrow", pygame.K_DOWN: "down arrow",
            pygame.K_LEFT: "left arrow", pygame.K_RIGHT: "right arrow",
            pygame.K_BACKSPACE: "backspace", pygame.K_TAB: "tab",
        }
        if key in names:
            return names[key]
        name = pygame.key.name(key)
        if len(name) == 1:
            return name.lower()
        return name

    def _screen_to_scratch(self, pos):
        """窗口坐标 -> 舞台坐标；超出舞台范围时取边界值（与 Scratch 一致）"""
        x, y = self._window_to_stage(pos)
        scratch_x = int(round(x)) - self.stage_width // 2
        scratch_y = self.stage_height // 2 - int(round(y))
        limit_x = self.stage_width // 2
        limit_y = self.stage_height // 2
        return (max(-limit_x, min(limit_x, scratch_x)),
                max(-limit_y, min(limit_y, scratch_y)))

    def music_seconds(self, beats):
        tempo = _sc_num(self.music_tempo) or 60.0
        return max(0.0, _sc_num(beats)) * 60.0 / max(20.0, tempo)

    def music_tone(self, frequency, seconds):
        if not self.mixer_ready or seconds <= 0:
            return None
        key = (round(frequency, 2), round(seconds, 3))
        cached = self.music_cache.get(key)
        if cached is not None:
            return cached
        info = pygame.mixer.get_init()
        if not info:
            return None
        rate, _size, channels = info
        count = max(1, int(rate * seconds))
        samples = array.array('h')
        amplitude = 11000
        for index in range(count):
            moment = index / float(rate)
            envelope = min(1.0, moment * 80) * min(1.0, (seconds - moment) * 40)
            value = int(math.sin(2 * math.pi * frequency * moment) *
                        amplitude * max(0.0, envelope))
            for _channel in range(channels or 1):
                samples.append(value)
        try:
            sound = pygame.mixer.Sound(buffer=samples.tobytes())
        except Exception:
            return None
        if len(self.music_cache) > 96:
            self.music_cache.clear()
        self.music_cache[key] = sound
        return sound

    def music_play_note(self, sprite, note, beats):
        seconds = self.music_seconds(beats)
        frequency = 440.0 * (2 ** ((_sc_num(note) - 69) / 12.0))
        if self.mixer_ready:
            sound = self.music_tone(frequency, seconds)
            if sound is not None:
                sound.play()
        if seconds > 0:
            self._coop_sleep(sprite, seconds)

    def music_play_drum(self, sprite, drum, beats):
        seconds = self.music_seconds(beats)
        if self.mixer_ready:
            frequencies = {1: 261.63, 2: 196.0, 3: 130.81, 4: 523.25}
            sound = self.music_tone(frequencies.get(int(drum), 220.0),
                                    min(0.3, max(0.06, seconds)))
            if sound is not None:
                sound.play()
        if seconds > 0:
            self._coop_sleep(sprite, seconds)

    def music_wait(self, sprite, beats):
        seconds = self.music_seconds(beats)
        if seconds > 0:
            self._coop_sleep(sprite, seconds)

    def _coop_sleep(self, sprite, seconds):
        if sprite is None:
            time.sleep(seconds)
            return
        sprite._turn_release()
        try:
            time.sleep(seconds)
        finally:
            sprite._turn_acquire()

    def _start_drag(self, pos):
        """按下鼠标时，找到可拖动的角色开始拖动"""
        x, y = self._screen_to_scratch(pos)
        for sprite in reversed(list(self.sprites)):
            if not getattr(sprite, 'draggable', False) or not sprite.visible:
                continue
            if sprite._contains_point(x, y):
                self.dragging = sprite
                self.dragging_offset = (_sc_num(sprite.x) - x,
                                        _sc_num(sprite.y) - y)
                return

    def _handle_click(self, pos):
        if self.trace:
            print("[trace] click", pos)
        if self._green_flag_rect().collidepoint(pos):
            # 绿旗在窗口顶部工具栏里，用窗口坐标判断
            self.green_flag()
            return
        if self._stop_rect().collidepoint(pos):
            self.stop_clicked()
            return
        stage_pos = self._window_to_stage(pos)
        x, y = self._screen_to_scratch(pos)
        for sprite in reversed(list(self.sprites)):
            if not sprite.visible:
                continue
            if sprite._contains_point(x, y):
                for func in list(sprite._handlers.get("clicked", [])):
                    sprite._running = True
                    self.start_script(func)
                return

    def step(self):
        if not self.running or pygame is None:
            return
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F1:
                self.debug_overlay = not self.debug_overlay
                self._debug_events = []
                continue
            self._log_event(event)
            if event.type == pygame.QUIT:
                self.running = False
                return
            elif self._has_text_input and event.type == pygame.TEXTINPUT:
                # pygame 2 的文本输入（含中文输入法提交的文本）；
                # 部分环境只发 KEYDOWN，不去重会重复输入
                if self.ask_pending:
                    if self.trace:
                        print("[trace] ask text", repr(event.text))
                    self._ask_append_text(event.text)
                    self.ask_composition = ''
            elif self._has_text_input and event.type == pygame.TEXTEDITING:
                # 输入法正在拼写的文本，先显示出来但不计入答案
                if self.ask_pending:
                    if self.trace:
                        print("[trace] ask editing", repr(event.text))
                    self.ask_composition = event.text
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                    return
                if self.ask_pending:
                    if self.trace:
                        print("[trace] ask key", event.key,
                              repr(getattr(event, "unicode", "")))
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        self._submit_ask()
                    elif event.key == pygame.K_BACKSPACE:
                        if self.ask_composition:
                            self.ask_composition = self.ask_composition[:-1]
                        else:
                            self.ask_buffer = self.ask_buffer[:-1]
                        self.ask_key_pending = ''
                    elif event.unicode and event.unicode.isprintable():
                        # 始终接受 KEYDOWN 文本：有些环境不会发 TEXTINPUT
                        self.ask_buffer += event.unicode
                        if self._has_text_input:
                            self.ask_key_pending += event.unicode
                    continue
                key = self._key_name(event.key)
                if key:
                    if self.trace:
                        print("[trace] key", key)
                    self.keys.add(key)
                    for sprite in list(self.sprites):
                        handlers = list(sprite._handlers.get("key:" + key, []))
                        handlers += list(sprite._handlers.get("key:any", []))
                        for func in handlers:
                            sprite._running = True
                            self.start_script(func)
            elif event.type == pygame.KEYUP:
                if self.ask_pending and \
                        event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    # 输入法可能吞掉 KEYDOWN，回车松开时再兜底提交
                    self._submit_ask()
                    continue
                self.keys.discard(self._key_name(event.key))
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                stage_pos = self._window_to_stage(event.pos)
                if self.ask_pending:
                    if self.trace:
                        print("[trace] ask click", stage_pos,
                              self._ask_button_rect().collidepoint(stage_pos))
                    if self._ask_button_rect().collidepoint(stage_pos):
                        # 只有“确认”按钮提交；点击输入框本身不应提交
                        self._submit_ask()
                        continue
                self.mouse_down = True
                self.mouse_x, self.mouse_y = self._screen_to_scratch(event.pos)
                self._start_drag(event.pos)
                self._handle_click(event.pos)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if self.ask_pending:
                    stage_pos = self._window_to_stage(event.pos)
                    if self._ask_button_rect().collidepoint(stage_pos):
                        # 窗口激活时按下事件可能被系统吞掉，松开时再兜底
                        self._submit_ask()
                        continue
                self.mouse_down = False
                self.dragging = None
            elif event.type == pygame.MOUSEMOTION:
                self.mouse_x, self.mouse_y = self._screen_to_scratch(event.pos)
                if self.dragging is not None:
                    offset_x, offset_y = self.dragging_offset
                    self.dragging.x = self.mouse_x + offset_x
                    self.dragging.y = self.mouse_y + offset_y
                    self.dragging._apply_fencing()
        self._update_state()
        self._draw()
        self._present()
        with self.frame_condition:
            self.frame += 1
            self.frame_condition.notify_all()
        if not self.headless:
            self.clock.tick(self.fps)

    def _log_event(self, event):
        """记录最近的事件，供 F1 调试面板显示"""
        if not self.debug_overlay:
            return
        if event.type == pygame.KEYDOWN:
            text = "KEYDOWN %s %r" % (event.key, getattr(event, 'unicode', ''))
        elif self._has_text_input and event.type == pygame.TEXTINPUT:
            text = "TEXTINPUT %r" % (event.text,)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            text = "MOUSEDOWN %s %s" % (event.button, event.pos)
        elif event.type == pygame.MOUSEBUTTONUP:
            text = "MOUSEUP %s %s" % (event.button, event.pos)
        else:
            return
        self._debug_events.append(text)
        if len(self._debug_events) > 9:
            del self._debug_events[0]

    def _draw_debug(self):
        alive = sum(1 for context in self.scripts if context.running)
        lines = [
            "v%s frame=%s scripts=%s" % (_RUNTIME_VERSION, self.frame, alive),
            "ask pending=%s visible=%s token=%s buffer=%r comp=%r" % (
                self.ask_pending, self.ask_visible, self.ask_token,
                self.ask_buffer, self.ask_composition),
            "mouse=(%s,%s) down=%s keys=%s" % (
                self.mouse_x, self.mouse_y, self.mouse_down,
                sorted(self.keys)),
        ] + list(self._debug_events)
        width = max(self.font.size(line)[0] for line in lines) + 14
        height = len(lines) * 16 + 10
        panel = pygame.Surface((width, height), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 190))
        self.stage_surface.blit(panel, (6, 6))
        for index, line in enumerate(lines):
            surface = self.font.render(line, True, (255, 255, 255))
            self.stage_surface.blit(surface, (12, 10 + index * 16))

    def _init_microphone(self):
        """可选麦克风：安装 sounddevice + numpy 后“响度”才有真实数值"""
        if self.headless:
            return
        try:
            import sounddevice
            import numpy
        except Exception:
            return

        def callback(indata, frames, time_info, status):
            try:
                samples = indata[:, 0]
                rms = float(numpy.sqrt(numpy.mean(numpy.square(samples))))
            except Exception:
                return
            # 与 Scratch 的量级对齐：安静时约 0，正常说话约 10-40
            self._mic_value = min(100.0, rms * 200.0)

        try:
            stream = sounddevice.InputStream(channels=1, samplerate=44100,
                                             blocksize=1024, callback=callback)
            stream.start()
            self._mic_stream = stream
        except Exception:
            self._mic_stream = None

    def _close_microphone(self):
        if self._mic_stream is not None:
            try:
                self._mic_stream.stop()
                self._mic_stream.close()
            except Exception:
                pass
            self._mic_stream = None

    def _update_conditions(self, elapsed):
        """检查“当计时器/响度 > 值”帽子事件，条件由假变真时启动脚本"""
        for sprite in list(self.sprites):
            for item in list(getattr(sprite, '_conditions', ())):
                menu, threshold, func, was_true = item
                value = elapsed if menu == 'timer' else self.loudness
                try:
                    limit = _sc_num(threshold())
                except Exception:
                    limit = 0
                now_true = value > limit
                item[3] = now_true
                if now_true and not was_true:
                    sprite._running = True
                    self.start_script(func)

    def _update_state(self):
        elapsed = self.elapsed()
        self.loudness = self._mic_value
        days = (time.time() - self.epoch_2000) / 86400.0
        for sprite in list(self.sprites):
            sprite.timer = elapsed
            sprite.days_since_2000 = days
            sprite.loudness = self.loudness
            sprite.mouse_x = self.mouse_x
            sprite.mouse_y = self.mouse_y
            sprite.mouse_down = self.mouse_down
            sprite.answer = self.answer
            sprite._update_say()
            if self.interpolation:
                target_x = _sc_num(sprite.x)
                target_y = _sc_num(sprite.y)
                target_d = _sc_num(sprite.direction)
                target_s = _sc_num(sprite.size)
                if getattr(sprite, "_render_x", None) is None:
                    sprite._render_x = target_x
                    sprite._render_y = target_y
                    sprite._render_direction = target_d
                    sprite._render_size = target_s
                else:
                    sprite._render_x += (target_x - sprite._render_x) * 0.5
                    sprite._render_y += (target_y - sprite._render_y) * 0.5
                    delta = ((target_d - sprite._render_direction + 180) % 360) - 180
                    sprite._render_direction = (sprite._render_direction + delta * 0.5) % 360
                    sprite._render_size += (target_s - sprite._render_size) * 0.5
        self._update_conditions(elapsed)
        self._update_frame_hats()

    def _update_frame_hats(self):
        """逐帧评估扩展帽子（More Events / Clones+）"""
        for sprite in list(self.sprites):
            for entry in list(getattr(sprite, '_frame_hats', ())):
                action = _ext_frame_hat_action(self, sprite, entry)
                if action == 'start':
                    sprite._running = True
                    entry['thread'] = self.start_script(entry['func'])
                elif action == 'stop':
                    thread = entry.get('thread')
                    context = getattr(thread, '_scratch_context', None)
                    if context is not None:
                        context.running = False
                    entry['thread'] = None
                    with self.frame_condition:
                        self.frame_condition.notify_all()

    def _draw(self):
        background = self.background
        ghost = 0.0
        stage = self.stage_sprite
        if background is not None and stage is not None:
            # 舞台自身的图形特效要作用在背景上（Scratch 中舞台也是角色）
            effects = stage._effects
            color = _sc_num(effects.get('color', 0))
            brightness = _sc_num(effects.get('brightness', 0))
            ghost = max(0.0, min(100.0, _sc_num(effects.get('ghost', 0))))
            if color:
                background = stage._color_effect_image(background, color)
            if brightness:
                background = stage._brightness_image(background, brightness)
            background = stage._distortion_image(background)
            if ghost > 0:
                background = background.copy()
                background.set_alpha(int(255 * (1 - ghost / 100.0)))
        # 每帧先铺白底再画背景：背景可能只是 2x2 的空白造型（Scratch 默认背景），
        # 只 blit 背景无法覆盖整个舞台，上一帧的输入框/文字会残留。
        self.stage_surface.fill((255, 255, 255))
        if background is not None:
            self.stage_surface.blit(background, (0, 0))
        if self._pen_used:
            self.stage_surface.blit(self.pen_layer, (0, 0))
        for sprite in list(self.sprites):
            if sprite.visible and not getattr(sprite, 'is_stage', False):
                sprite._draw(self.stage_surface, self.font)
        self._draw_monitors()
        self._draw_ask()
        if self.debug_overlay:
            self._draw_debug()

    def _all_monitors(self):
        return list(MONITORS) + self.dynamic_monitors

    def show_monitor(self, kind, name, owner, visible):
        """显示/隐藏变量或列表监视器（不存在时动态创建）"""
        prefix = 'lst' if kind == 'list' else 'var'
        attr = _sc_ident(name, prefix)
        target = None
        for monitor in self._all_monitors():
            if (monitor.get('kind') == kind and monitor.get('attr') == attr
                    and monitor.get('sprite') == owner):
                target = monitor
                break
        if target is None:
            label = name if not owner or name.startswith(owner + ':') else f"{owner}: {name}"
            target = {
                'kind': kind, 'name': name, 'sprite': owner, 'label': label,
                'attr': attr, 'visible': visible,
                'x': 5, 'y': 5 + 22 * len(self.dynamic_monitors),
                'width': 200 if kind == 'list' else 120,
                'height': 150 if kind == 'list' else 20,
            }
            self.dynamic_monitors.append(target)
        target['visible'] = visible

    def _draw_monitors(self):
        for monitor in self._all_monitors():
            if monitor.get('visible') is False:
                continue
            rect = pygame.Rect(int(monitor["x"]), int(monitor["y"]),
                               int(monitor["width"]), int(monitor["height"]))
            label = monitor.get("label") or monitor["name"]
            owner = monitor.get("sprite")
            if owner:
                target = self.find_sprite(owner)
                value = getattr(target, monitor["attr"], None) if target else None
            else:
                value = GLOBALS.get(monitor["attr"])
            if monitor["kind"] == "list":
                pygame.draw.rect(self.stage_surface, (255, 255, 255), rect, border_radius=4)
                pygame.draw.rect(self.stage_surface, (130, 130, 130), rect, 1, border_radius=4)
                title = self.font.render(label, True, (40, 40, 40))
                self.stage_surface.blit(title, (rect.x + 5, rect.y + 3))
                if isinstance(value, list):
                    line_y = rect.y + 21
                    for item in value:
                        if line_y + 14 > rect.bottom - 2:
                            break
                        text = self.font.render(_sc_str(item), True, (60, 60, 60))
                        self.stage_surface.blit(text, (rect.x + 8, line_y))
                        line_y += 15
            else:
                text = f"{label} {_sc_str(value)}"
                pygame.draw.rect(self.stage_surface, (255, 255, 255), rect, border_radius=3)
                pygame.draw.rect(self.stage_surface, (130, 130, 130), rect, 1, border_radius=3)
                surface = self.font.render(text, True, (40, 40, 40))
                self.stage_surface.blit(surface, (rect.x + 5, rect.y + 3))

    @property
    def backdrop_name(self):
        if BACKDROPS:
            index = self.current_backdrop % len(BACKDROPS)
            return BACKDROPS[index][0]
        return ''

    @property
    def backdrop_number(self):
        return self.current_backdrop + 1

    def set_backdrop(self, name):
        # 与 scratch-vm 的 _setBackdrop 保持一致：
        # 数字→编号；字符串→名字/next/previous/random backdrop/数字字符串。
        # 无法识别的名字不切换背景，也不触发“当背景换成”帽子。
        if not BACKDROPS:
            return []
        count = len(BACKDROPS)
        names = [item[0] for item in BACKDROPS]
        if isinstance(name, (int, float)) and not isinstance(name, bool):
            number = float(name)
            if math.isnan(number) or math.isinf(number):
                index = 0
            else:
                index = _sc_round(number) - 1
        else:
            value = _sc_str(name)
            if value in names:
                index = names.index(value)
            elif value == 'next backdrop':
                index = self.current_backdrop + 1
            elif value == 'previous backdrop':
                index = self.current_backdrop - 1
            elif value == 'random backdrop':
                if count <= 1:
                    return []
                index = random.randrange(count - 1)
                if index >= self.current_backdrop:
                    index += 1
            elif _sc_is_white(value):
                return []
            else:
                number = _sc_number_or_nan(value)
                if math.isnan(number) or math.isinf(number):
                    return []
                index = _sc_round(number) - 1
        return self._apply_backdrop(index)

    def next_backdrop(self):
        if BACKDROPS:
            return self._apply_backdrop(self.current_backdrop + 1)
        return []

    def _apply_backdrop(self, index):
        self.current_backdrop = int(index) % len(BACKDROPS)
        filename = BACKDROPS[self.current_backdrop][1]
        image = self._load_image(filename) if filename else None
        self.background = None
        if image is not None:
            self.background = pygame.transform.smoothscale(
                image, (self.stage_width, self.stage_height))
        name = BACKDROPS[self.current_backdrop][0]
        threads = []
        for sprite in list(self.sprites):
            sprite._running = True
            for func in list(sprite._handlers.get('backdrop:' + name, [])):
                threads.append(self.start_script(func))
            for func in list(sprite._handlers.get('backdrop:any', [])):
                threads.append(self.start_script(func))
        return threads

    def go_to_layer(self, sprite, where):
        if sprite not in self.sprites:
            return
        self.sprites.remove(sprite)
        if _sc_str(where).lower().startswith('back'):
            self.sprites.insert(0, sprite)
        else:
            self.sprites.append(sprite)

    def change_layer(self, sprite, layers):
        if sprite not in self.sprites:
            return
        index = self.sprites.index(sprite)
        target = max(0, min(len(self.sprites) - 1, index + layers))
        self.sprites.remove(sprite)
        self.sprites.insert(target, sprite)

    def sensing_of(self, target, prop):
        prop = _sc_str(prop).lower()
        target = _sc_str(target)
        if target in ('_stage_', 'Stage', '舞台'):
            if prop in ('backdrop #', 'backdrop number'):
                return self.backdrop_number
            if prop == 'backdrop name':
                return self.backdrop_name
            if prop == 'volume':
                return 100
            return 0
        other = self.find_sprite(target)
        if other is None:
            return 0
        sprite_props = {
            'x position': 'x', 'y position': 'y',
            'direction': 'direction', 'costume #': 'costume_number',
            'costume name': 'costume_name', 'size': 'size',
            'volume': 'volume',
        }
        attr = sprite_props.get(prop)
        if attr is None:
            return 0
        return getattr(other, attr)

    def apply_color_effect(self, surface, effect):
        """颜色特效：按Scratch语义旋转HSV色相"""
        angle = (_sc_num(effect) / 200.0) * 360.0
        if abs(angle) < 0.1:
            return surface
        try:
            import numpy
            result = surface.copy()
            pixels = pygame.surfarray.pixels3d(result)
            data = pixels.astype(numpy.float32) / 255.0
            red, green, blue = data[:, :, 0], data[:, :, 1], data[:, :, 2]
            maximum = data.max(axis=2)
            minimum = data.min(axis=2)
            delta = maximum - minimum
            safe = numpy.where(delta == 0, 1.0, delta)
            hue = numpy.zeros_like(maximum)
            mask = delta > 1e-6
            red_mask = mask & (maximum == red)
            green_mask = mask & (maximum == green) & ~red_mask
            blue_mask = mask & (maximum == blue) & ~red_mask & ~green_mask
            hue[red_mask] = ((green - blue) / safe)[red_mask] % 6.0
            hue[green_mask] = ((blue - red) / safe)[green_mask] + 2.0
            hue[blue_mask] = ((red - green) / safe)[blue_mask] + 4.0
            hue = (hue * 60.0 + angle) % 360.0
            saturation = numpy.where(maximum > 0, delta / numpy.where(maximum == 0, 1.0, maximum), 0.0)

            chroma = maximum * saturation
            sector = hue / 60.0
            second = chroma * (1.0 - numpy.abs(sector % 2.0 - 1.0))
            offset = maximum - chroma
            out_red = numpy.select(
                [sector < 1, sector < 2, sector < 3, sector < 4, sector < 5],
                [chroma, second, 0.0, 0.0, second], default=chroma)
            out_green = numpy.select(
                [sector < 1, sector < 2, sector < 3, sector < 4, sector < 5],
                [second, chroma, chroma, second, 0.0], default=0.0)
            out_blue = numpy.select(
                [sector < 1, sector < 2, sector < 3, sector < 4, sector < 5],
                [0.0, 0.0, second, chroma, chroma], default=second)
            shifted = numpy.stack([out_red, out_green, out_blue], axis=2)
            shifted = numpy.clip((shifted + offset[:, :, None]) * 255.0, 0, 255)
            pixels[:, :, :] = shifted.astype(numpy.uint8)
            del pixels
            return result
        except Exception:
            # 没有numpy时退化为色相着色
            color = pygame.Color(0)
            color.hsva = (int(angle % 360), 100, 100, 100)
            gray = pygame.transform.grayscale(surface).convert_alpha()
            gray.fill((color.r, color.g, color.b, 255),
                      special_flags=pygame.BLEND_RGB_MULT)
            return gray

    def _costume_color_mask(self, sprite, color):
        image = sprite._costume_surface()
        if image is None:
            return None
        return pygame.mask.from_threshold(
            image, _sc_color(color), (16, 16, 16, 255))

    def touching_color(self, sprite, color):
        mask = self._costume_color_mask(sprite, color)
        return bool(mask and mask.count() > 0)

    def color_touching_color(self, sprite, color, other):
        first = self._costume_color_mask(sprite, color)
        second = self._costume_color_mask(sprite, other)
        return bool(first and second and first.count() > 0 and second.count() > 0)

    def get_sprite_image(self, name):
        if not name:
            return None
        if name in self.costume_cache:
            return self.costume_cache[name]
        image = self._load_image(name)
        self.costume_cache[name] = image
        return image

    def snapshot_data_uri(self):
        """把当前舞台画面编码成 data:image/png;base64,..."""
        import base64
        buffer = io.BytesIO()
        pygame.image.save(self.stage_surface, buffer, 'stage.png')
        return ('data:image/png;base64,'
                + base64.b64encode(buffer.getvalue()).decode('ascii'))

    def asset_bytes(self, filename):
        """读取素材原始字节（供 Looks+ 的造型内容积木使用）"""
        path = self._asset_path(filename)
        if not path or not os.path.exists(path):
            return None
        try:
            with open(path, 'rb') as handle:
                return handle.read()
        except OSError:
            return None

    def _sprite_rect(self, sprite):
        rect = getattr(sprite, "_screen_rect", None)
        if rect is not None:
            return rect
        radius = max(6, int(20 * _sc_num(sprite.size) / 100.0))
        center = (int(self.stage_width / 2 + _sc_num(sprite.x)),
                  int(self.stage_height / 2 - _sc_num(sprite.y)))
        return pygame.Rect(center[0] - radius, center[1] - radius,
                           radius * 2, radius * 2)

    def _sprite_mask(self, sprite):
        image = sprite._costume_surface()
        if image is None:
            return None
        scale = max(1.0, _sc_num(sprite.size)) / 100.0
        key = (id(sprite), sprite.costume_number, int(round(scale * 100)))
        cached = self.mask_cache.get(key)
        if cached is not None:
            return cached
        if abs(scale - 1.0) > 0.01:
            image = pygame.transform.smoothscale(
                image, (max(1, int(image.get_width() * scale)),
                        max(1, int(image.get_height() * scale))))
        mask = pygame.mask.from_surface(image)
        if len(self.mask_cache) > 256:
            self.mask_cache.clear()
        self.mask_cache[key] = mask
        return mask

    def touching(self, sprite, target):
        rect = self._sprite_rect(sprite)
        if target == "_edge_":
            return (rect.left <= 0 or rect.right >= self.stage_width or
                    rect.top <= 0 or rect.bottom >= self.stage_height)
        if target == "_mouse_":
            x = self.stage_width // 2 + self.mouse_x
            y = self.stage_height // 2 - self.mouse_y
            return rect.collidepoint(x, y)
        # “碰到角色”应检查该角色的所有可见克隆体（不包括自己）
        first = None
        for other in list(self.sprites):
            if other is sprite or not other.visible or other.name != target:
                continue
            other_rect = self._sprite_rect(other)
            if not rect.colliderect(other_rect):
                continue
            if first is None:
                first = self._sprite_mask(sprite)
            second = self._sprite_mask(other)
            if first is None or second is None:
                return True
            offset = (other_rect.x - rect.x, other_rect.y - rect.y)
            if first.overlap(second, offset) is not None:
                return True
        return False

    def distance_to(self, sprite, target):
        if getattr(sprite, 'is_stage', False):
            return 10000
        if target == "_mouse_":
            return math.hypot(_sc_num(sprite.x) - self.mouse_x,
                              _sc_num(sprite.y) - self.mouse_y)
        other = self.find_sprite(target)
        if other is None:
            return 10000
        return math.hypot(_sc_num(sprite.x) - _sc_num(other.x),
                          _sc_num(sprite.y) - _sc_num(other.y))

    def play_sound(self, sprite, name):
        if not self.mixer_ready:
            return 0
        sounds = getattr(sprite, "sounds", [])
        if not sounds:
            return 0
        # scratch-vm 的 _getSoundIndex：先按名字找，再按1起编号找
        text = _sc_str(name)
        filename = None
        for sound in sounds:
            if sound.get("name") == text:
                filename = sound.get("md5ext")
                break
        if not filename:
            number = _sc_parse_int10(text)
            if number is None:
                return 0
            index = int(number - 1) % len(sounds)
            filename = sounds[index].get("md5ext")
        if not filename:
            return 0
        path = self._asset_path(filename)
        if not path:
            return 0
        sound = self.sound_cache.get(path)
        if sound is None:
            try:
                sound = pygame.mixer.Sound(path)
            except Exception:
                sound = False
            self.sound_cache[path] = sound
        if not sound:
            return 0
        pitch = _sc_num(getattr(sprite, '_sound_effects', {}).get('pitch', 0))
        played = self._pitched_sound(sound, path, pitch) if pitch else sound
        channel = played.play()
        pan = _sc_num(getattr(sprite, '_sound_effects', {}).get('pan', 0))
        volume = max(0.0, min(1.0,
                                _sc_num(getattr(sprite, 'volume', 100)) / 100.0))
        left = max(0.0, min(1.0, 1.0 - max(0.0, pan) / 100.0))
        right = max(0.0, min(1.0, 1.0 + min(0.0, pan) / 100.0))
        if channel is not None and (pan or volume != 1.0):
            channel.set_volume(left * volume, right * volume)
        return played.get_length()

    def _pitched_sound(self, sound, path, pitch):
        """按音高效真正变调：scratch-audio 的速率公式 rate = 2^(pitch/120)"""
        pitch = max(-360.0, min(360.0, _sc_num(pitch)))
        if not pitch:
            return sound
        key = (path, int(round(pitch)))
        cached = self._pitched_cache.get(key)
        if cached is not None:
            return cached if cached is not False else sound
        result = None
        try:
            result = self._resample_sound(sound, 2.0 ** (pitch / 120.0))
        except Exception:
            result = None
        if result is not None and len(self._pitched_cache) > 64:
            self._pitched_cache.pop(next(iter(self._pitched_cache)))
        self._pitched_cache[key] = result if result is not None else False
        return result if result is not None else sound

    def _resample_sound(self, sound, rate):
        """按播放速率重采样；有 numpy 时用向量化插值，否则用纯 Python"""
        if rate <= 0:
            return None
        try:
            import numpy
        except Exception:
            numpy = None
        mixer = pygame.mixer.get_init()
        channels = mixer[2] if mixer else 2
        if numpy is not None:
            from pygame import sndarray
            samples = sndarray.array(sound)
            count = samples.shape[0]
            if count <= 1:
                return None
            total = max(1, int(round(count / rate)))
            positions = numpy.arange(total, dtype=numpy.float64) * rate
            base = numpy.clip(numpy.floor(positions).astype(numpy.int64),
                              0, count - 1)
            nxt = numpy.clip(base + 1, 0, count - 1)
            frac = positions - base
            data = samples.astype(numpy.float64)
            if data.ndim == 1:
                mixed = data[base] * (1.0 - frac) + data[nxt] * frac
            else:
                mixed = (data[base, :] * (1.0 - frac)[:, None]
                         + data[nxt, :] * frac[:, None])
            info = numpy.iinfo(samples.dtype)
            mixed = numpy.clip(numpy.rint(mixed), info.min, info.max)
            return sndarray.make_sound(
                numpy.ascontiguousarray(mixed.astype(samples.dtype)))
        # 纯 Python 回退只支持常见的 16 位有符号 PCM
        if not mixer or mixer[1] != -16:
            return None
        values = array.array('h')
        values.frombytes(sound.get_raw())
        if channels > 1:
            count = len(values) // channels
        else:
            count = len(values)
        if count <= 1:
            return None
        total = max(1, int(round(count / rate)))
        output = array.array('h')
        for index in range(total):
            position = index * rate
            base = int(position)
            if base >= count:
                base = count - 1
            nxt = base + 1 if base + 1 < count else base
            frac = position - base
            for channel in range(channels):
                first = values[base * channels + channel]
                second = values[nxt * channels + channel]
                output.append(int(first + (second - first) * frac))
        return pygame.mixer.Sound(buffer=output.tobytes())

    def speak(self, text, sprite=None):
        """朗读文本并等待结束（text2speech 扩展）"""
        text = _sc_str(text)
        if not text.strip():
            return
        # 朗读期间让出执行权，避免其他脚本被卡住
        if sprite is not None:
            sprite._turn_release()
        try:
            self._speak_blocking(text)
        finally:
            if sprite is not None:
                sprite._turn_acquire()

    def _speak_blocking(self, text):
        engine = self._tts_engine
        if engine is None and not self._tts_failed:
            try:
                import pyttsx3
                engine = pyttsx3.init()
                self._tts_engine = engine
            except Exception:
                self._tts_engine = None
                self._tts_failed = True
        if engine is not None:
            rates = {'alto': 170, 'tenor': 185, 'squeak': 220, 'giant': 130}
            try:
                engine.setProperty('rate', rates.get(self.tts_voice, 170))
                voice_id = self._tts_voice_id(engine)
                if voice_id:
                    engine.setProperty('voice', voice_id)
                engine.say(text)
                engine.runAndWait()
                return
            except Exception:
                self._tts_engine = None
                self._tts_failed = True
        if os.name == 'nt' and self._speak_windows(text):
            return
        if not self._tts_warned:
            self._tts_warned = True
            print("[runtime] 文字朗读不可用：可安装 pyttsx3（pip install pyttsx3）")

    def _tts_voice_id(self, engine):
        """按语言挑一个系统嗓音；找不到时返回 None 使用默认嗓音"""
        language = (self.tts_language or '').lower()
        if not language or language == 'english':
            return None
        if '中文' in language or 'chinese' in language or language.startswith('zh'):
            hints = ('chinese', 'zh')
        else:
            hints = (language,)
        try:
            voices = engine.getProperty('voices') or []
        except Exception:
            return None
        for voice in voices:
            name = str(getattr(voice, 'name', '') or '').lower()
            parts = []
            for item in getattr(voice, 'languages', []) or []:
                if isinstance(item, bytes):
                    parts.append(item.decode('utf-8', 'ignore'))
                else:
                    parts.append(str(item))
            langs = ' '.join(parts).lower()
            if any(hint in name or hint in langs for hint in hints):
                return getattr(voice, 'id', None)
        return None

    def _speak_windows(self, text):
        """没有 pyttsx3 时用 Windows 自带的 System.Speech 朗读"""
        rate = {'alto': 0, 'tenor': 1, 'squeak': 3, 'giant': -2}.get(self.tts_voice, 0)
        escaped = text.replace("'", "''")
        script = (
            "Add-Type -AssemblyName System.Speech;"
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
            f"$s.Rate = {rate};"
            f"$s.Speak('{escaped}')")
        try:
            import subprocess
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=0x08000000)
            return True
        except Exception:
            return False

    def stop_sounds(self):
        if self.mixer_ready:
            pygame.mixer.stop()

    def start(self, max_frames=None, max_seconds=None):
        if pygame is None:
            raise RuntimeError("运行生成的脚本需要pygame: pip install pygame")
        for sprite in list(self.sprites):
            sprite.run()
        self.green_flag()
        frames = 0
        deadline = None if max_seconds is None else time.time() + max_seconds
        try:
            while self.running:
                try:
                    self.step()
                except Exception:
                    # 单帧绘制/事件异常不应让整个窗口卡死
                    import traceback
                    traceback.print_exc()
                frames += 1
                if max_frames is not None and frames >= max_frames:
                    break
                if deadline is not None and time.time() >= deadline:
                    break
        finally:
            self.running = False
            with self.frame_condition:
                self.frame_condition.notify_all()

    def shutdown(self):
        self.running = False
        with self.frame_condition:
            self.frame_condition.notify_all()
        self._close_microphone()
        try:
            pygame.display.quit()
        except Exception:
            pass

    def _asset_path(self, filename):
        """素材优先从脚本同目录读取，其次兼容旧的assets子目录"""
        if not filename:
            return None
        name = os.path.basename(filename)
        for folder in (self.assets_dir, os.path.join(self.assets_dir, 'assets')):
            path = os.path.join(folder, name)
            if os.path.exists(path):
                return path
        return None

    def _load_image(self, filename):
        path = self._asset_path(filename)
        if not path:
            return None
        if path.lower().endswith(".svg"):
            try:
                import cairosvg
                png_data = cairosvg.svg2png(url=path)
                image = pygame.image.load(io.BytesIO(png_data))
                try:
                    return image.convert_alpha()
                except Exception:
                    return image
            except Exception:
                return self._render_svg(path)
        try:
            image = pygame.image.load(path)
        except Exception:
            return None
        try:
            return image.convert_alpha()
        except Exception:
            return image

    def _svg_style_at(self, text, position, base):
        """计算position处继承的 fill/stroke/font-size"""
        fill, stroke, width, font_size = base
        for match in re.finditer(r'<g\b([^>]*)>|</g>', text[:position]):
            tag = match.group(0)
            if tag.startswith('</g'):
                continue
            attrs = match.group(1)
            fill = _svg_attr(attrs, 'fill', fill)
            stroke = _svg_attr(attrs, 'stroke', stroke)
            width = _svg_attr(attrs, 'stroke-width', width)
            font_size = _svg_attr(attrs, 'font-size', font_size)
        return fill, stroke, width, font_size

    def _svg_matrix_at(self, text, position):
        stack = [(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)]
        for match in re.finditer(r'<g\b([^>]*)>|</g>', text[:position]):
            tag = match.group(0)
            if tag.startswith('</g'):
                if len(stack) > 1:
                    stack.pop()
            else:
                current = _svg_mul(stack[-1],
                                   _svg_transform(_svg_attr(match.group(1), 'transform')))
                stack.append(current)
        return stack[-1]

    def _render_svg(self, path):
        """没有cairosvg时的简易SVG渲染：支持text/常见形状/path"""
        try:
            with open(path, encoding='utf-8', errors='ignore') as handle:
                text = handle.read()
        except OSError:
            return None
        root = text.split('>', 1)[0]
        width = _sc_num(_svg_attr(root, 'width', '0') or 0)
        height = _sc_num(_svg_attr(root, 'height', '0') or 0)
        view = _svg_attr(root, 'viewBox')
        if view:
            parts = [item for item in re.split(r'[ ,]+', view.strip()) if item]
            if len(parts) == 4:
                if not width:
                    width = _sc_num(parts[2])
                if not height:
                    height = _sc_num(parts[3])
        width = max(1, int(round(width or 100)))
        height = max(1, int(round(height or 100)))
        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        default_style = ('#000000', 'none', '1', '16')

        # 渐变用平均色近似（完整渐变渲染成本过高）
        gradients = {}
        for gradient in re.finditer(
                r'<(linearGradient|radialGradient)\b([^>]*)>(.*?)</\1>', text, re.S):
            ident = _svg_attr(gradient.group(2), 'id')
            colors = [_svg_color(item) for item in
                      re.findall(r'stop-color="([^"]*)"', gradient.group(3))]
            colors = [color for color in colors if color]
            if ident and colors:
                gradients[ident] = tuple(
                    sum(color[index] for color in colors) // len(colors)
                    for index in range(3))

        # 内嵌位图（data:image/png;base64,...）
        for match in re.finditer(r'<image\b([^>]*?)/?>', text):
            attrs = match.group(1)
            href = _svg_attr(attrs, 'xlink:href') or _svg_attr(attrs, 'href')
            if not href.startswith('data:image') or 'base64,' not in href:
                continue
            try:
                import base64
                raw = base64.b64decode(href.split('base64,', 1)[1])
                image = pygame.image.load(io.BytesIO(raw))
            except Exception:
                continue
            matrix = _svg_mul(self._svg_matrix_at(text, match.start()),
                              _svg_transform(_svg_attr(attrs, 'transform')))
            width = _sc_num(_svg_attr(attrs, 'width', '0'))
            height = _sc_num(_svg_attr(attrs, 'height', '0'))
            if width <= 0 or height <= 0:
                width, height = float(image.get_width()), float(image.get_height())
            scale = math.hypot(matrix[0], matrix[1]) or 1.0
            angle = -math.degrees(math.atan2(matrix[1], matrix[0]))
            drawn = pygame.transform.rotozoom(image, angle, scale)
            offset_x = _sc_num(_svg_attr(attrs, 'x', '0'))
            offset_y = _sc_num(_svg_attr(attrs, 'y', '0'))
            center_x, center_y = _svg_point(matrix, offset_x + width / 2,
                                            offset_y + height / 2)
            surface.blit(drawn, drawn.get_rect(center=(int(center_x), int(center_y))))

        # 形状
        shape_re = r'<(rect|circle|ellipse|line|polygon|polyline|path)\b([^>]*?)/?>'
        for match in re.finditer(shape_re, text):
            kind, attrs = match.group(1), match.group(2)
            base_fill, base_stroke, base_width, _size = self._svg_style_at(
                text, match.start(), default_style)
            fill = _svg_resolve_paint(_svg_attr(attrs, 'fill', base_fill), gradients)
            stroke = _svg_resolve_paint(_svg_attr(attrs, 'stroke', base_stroke), gradients)
            stroke_width_value = _sc_num(_svg_attr(attrs, 'stroke-width', base_width))
            if stroke_width_value <= 0:
                stroke = None
            stroke_width = max(1, int(stroke_width_value))
            matrix = _svg_mul(self._svg_matrix_at(text, match.start()),
                              _svg_transform(_svg_attr(attrs, 'transform')))
            points = []
            try:
                if kind == 'rect':
                    rx = _sc_num(_svg_attr(attrs, 'x', '0'))
                    ry = _sc_num(_svg_attr(attrs, 'y', '0'))
                    rw = _sc_num(_svg_attr(attrs, 'width', '0'))
                    rh = _sc_num(_svg_attr(attrs, 'height', '0'))
                    points = [_svg_point(matrix, rx, ry),
                              _svg_point(matrix, rx + rw, ry),
                              _svg_point(matrix, rx + rw, ry + rh),
                              _svg_point(matrix, rx, ry + rh)]
                elif kind == 'circle':
                    cx = _sc_num(_svg_attr(attrs, 'cx', '0'))
                    cy = _sc_num(_svg_attr(attrs, 'cy', '0'))
                    radius = _sc_num(_svg_attr(attrs, 'r', '0'))
                    center = _svg_point(matrix, cx, cy)
                    points = [(center[0] - radius * abs(matrix[0]),
                               center[1] - radius * abs(matrix[3])),
                              (center[0] + radius * abs(matrix[0]),
                               center[1] + radius * abs(matrix[3]))]
                elif kind == 'ellipse':
                    cx = _sc_num(_svg_attr(attrs, 'cx', '0'))
                    cy = _sc_num(_svg_attr(attrs, 'cy', '0'))
                    rx = _sc_num(_svg_attr(attrs, 'rx', '0'))
                    ry = _sc_num(_svg_attr(attrs, 'ry', '0'))
                    center = _svg_point(matrix, cx, cy)
                    points = [(center[0] - rx, center[1] - ry),
                              (center[0] + rx, center[1] + ry)]
                elif kind == 'line':
                    points = [
                        _svg_point(matrix, _sc_num(_svg_attr(attrs, 'x1', '0')),
                                   _sc_num(_svg_attr(attrs, 'y1', '0'))),
                        _svg_point(matrix, _sc_num(_svg_attr(attrs, 'x2', '0')),
                                   _sc_num(_svg_attr(attrs, 'y2', '0'))),
                    ]
                elif kind in ('polygon', 'polyline'):
                    values = [_sc_num(item) for item in
                              re.split(r'[ ,]+', _svg_attr(attrs, 'points').strip())
                              if item]
                    points = [_svg_point(matrix, values[i], values[i + 1])
                              for i in range(0, len(values) - 1, 2)]
                elif kind == 'path':
                    points = [_svg_point(matrix, px, py)
                              for px, py in _svg_path_points(_svg_attr(attrs, 'd'))]
            except (ValueError, IndexError):
                continue
            if not points:
                continue
            if kind in ('circle', 'ellipse') and len(points) == 2:
                left, size = points[0], (points[1][0] - points[0][0],
                                         points[1][1] - points[0][1])
                rect = pygame.Rect(int(left[0]), int(left[1]),
                                   int(size[0]), int(size[1]))
                if fill:
                    pygame.draw.ellipse(surface, fill, rect)
                if stroke:
                    pygame.draw.ellipse(surface, stroke, rect, stroke_width)
                continue
            if len(points) >= 2:
                if fill and len(points) >= 3:
                    pygame.draw.polygon(surface, fill, [(int(px), int(py))
                                                        for px, py in points])
                if stroke:
                    pygame.draw.lines(surface, stroke, kind == 'polygon',
                                      [(int(px), int(py)) for px, py in points],
                                      stroke_width)

        # 文本最后绘制，避免被前面的背景形状遮住
        for match in re.finditer(r'<text\b([^>]*)>(.*?)</text>', text, re.S):
            attrs, inner = match.group(1), match.group(2)
            base_fill, _stroke, _width, base_size = self._svg_style_at(
                text, match.start(), default_style)
            fill = _svg_resolve_paint(_svg_attr(attrs, 'fill', base_fill), gradients)
            if fill is None:
                continue
            matrix = _svg_mul(self._svg_matrix_at(text, match.start()),
                              _svg_transform(_svg_attr(attrs, 'transform')))
            size = _sc_num(_svg_attr(attrs, 'font-size', base_size)) or 16
            scale = abs(matrix[0]) or 1.0
            font_size = max(1, int(round(size * scale)))
            font = self._font(font_size)
            contents = re.findall(r'<tspan[^>]*>(.*?)</tspan>', inner, re.S)
            label = (contents[0] if contents else inner)
            label = re.sub(r'<[^>]+>', '', label).strip()
            if not label:
                continue
            rendered = font.render(label, True, fill)
            x, y = matrix[4], matrix[5]
            anchor = _svg_attr(attrs, 'text-anchor')
            if anchor == 'middle':
                x -= rendered.get_width() / 2
            elif anchor == 'end':
                x -= rendered.get_width()
            surface.blit(rendered, (int(x), int(y - font.get_ascent())))
        try:
            return surface.convert_alpha()
        except Exception:
            return surface

    def _font(self, size):
        cache = getattr(self, '_font_cache', None)
        if cache is None:
            cache = {}
            self._font_cache = cache
        if size not in cache:
            cache[size] = pygame.font.Font(self.font_path, size) if self.font_path else pygame.font.Font(None, size)
        return cache[size]
'''
