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
        # 内部渲染倍率：窗口放大时按比例重新栅格化，避免整层拉伸发糊
        self.render_scale = 1.0
        # 超采样上限（默认 3 倍，可用 SCRATCH_RENDER_SCALE_MAX 调整）
        try:
            self.max_render_scale = min(4.0, max(1.0, float(
                os.environ.get('SCRATCH_RENDER_SCALE_MAX') or 3.0)))
        except (TypeError, ValueError):
            self.max_render_scale = 3.0
        # 内置 SVG 渲染器默认启用；cairosvg 首次导入可能耗时数秒，改为按需开启
        self.use_cairosvg = os.environ.get(
            'SCRATCH_SVG_CAIROSVG', '').lower() in ('1', 'true', 'yes', 'on')
        # 倍率切换的稳定帧数/画质上限（自适应降低，避免卡顿时仍按 3 倍绘制）
        self._scale_target = 1.0
        self._scale_stable = 0
        self._quality_cap = self.max_render_scale
        self._slow_streak = 0
        self._fast_streak = 0
        self._scale_cooldown = 0
        self._ui_font_obj = None
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
        self.turn_lock = _FairLock()
        self._script_order = 0
        # 绿旗脚本的首次执行顺序闸门，保证角色按添加顺序先跑一帧
        self._start_gate_cond = threading.Condition()
        self._start_gate_total = 0
        self._start_gate_next = 0
        # “不刷新屏幕”自制积木：warp 执行期间冻结其他脚本并延后绘制
        self._warp_active = 0
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
        # 变量滑动条监视器：拖动时记录当前监视器
        self._slider_drag = None
        self._slider_hits = []
        self.mask_cache = {}
        # 新扩展状态：本地存储 / 剪贴板 / 光标 / 窗口
        self.localstorage_namespace = ''
        self._localstorage_cache = None
        self._clipboard_text = ''
        self._clipboard_last_pasted = ''
        self._scrap_ready = False
        self._cursor_name = 'default'
        # 光标状态：只在舞台区域内生效，工具栏/黑边恢复系统箭头
        self._cursor_visible = True
        self._cursor_system = 'ARROW'
        self._cursor_custom = None
        self._cursor_over_stage = True
        # 最近一次实际应用的光标（供调试/测试观察）
        self._applied_cursor = None
        self.fullscreen = False
        self.user_window_title = ''
        self._windowed_size = None
        try:
            pygame.scrap.init()
            self._scrap_ready = True
        except Exception:
            self._scrap_ready = False
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
        # 每个造型位图的栅格化倍率（SVG 会按窗口大小重新栅格化）
        self.costume_image_scales = {}
        # (造型名, 倍率) -> 位图：窗口来回缩放时复用，避免反复重新栅格化
        self.costume_cache_scales = {}
        # 素材路径/是否为 SVG 的缓存，避免每帧对每个角色做 os.path.exists
        self._asset_path_cache = {}
        self._asset_path_root = None
        self._costume_kind = {}
        self._costume_scale_caps = {}
        # 内嵌位图（base64）解码缓存：切换窗口倍率时无需重复解码
        self._svg_bitmap_cache = {}
        # 启动阶段已预加载的图片资源
        self._preloaded_names = set()
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
                self.background, self._stage_pixel_size())
        # 内置扩展按需注册：_BUILTIN_EXTENSIONS 只包含项目实际用到的扩展
        for _ext_name, _ext_handler in _BUILTIN_EXTENSIONS.items():
            self.register_extension(_ext_name, _ext_handler)

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

    def warp_begin(self):
        """进入“不刷新屏幕”的自制积木：暂停其他脚本并停止重绘"""
        self._warp_active += 1

    def warp_end(self):
        """离开 warp：最后一次绘制会在本帧结束时统一完成"""
        if self._warp_active > 0:
            self._warp_active -= 1

    @property
    def warping(self):
        return self._warp_active > 0

    def _read_clipboard(self):
        """读取系统剪贴板，失败时退回内存文本"""
        text = ''
        try:
            if getattr(self, '_scrap_ready', False):
                data = pygame.scrap.get(pygame.SCRAP_TEXT)
                if data:
                    text = data.decode('utf-8', 'replace').rstrip('\x00')
        except Exception:
            text = ''
        return text or getattr(self, '_clipboard_text', '')

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
        self.stage_surface = self._make_stage_surface()
        self._manual_view = True
        if maximize:
            self._maximize_window()

    def _stage_pixel_size(self):
        """舞台内部渲染尺寸（窗口较大时按 render_scale 超采样）"""
        return (max(1, int(round(self.stage_width * self.render_scale))),
                max(1, int(round(self.stage_height * self.render_scale))))

    def _make_stage_surface(self):
        surface = pygame.Surface(self._stage_pixel_size())
        surface.fill((255, 255, 255))
        return surface

    def _ui_font(self):
        """按渲染倍率放大的界面字体（监视器/询问框/调试面板）"""
        font = self._ui_font_obj
        if font is None:
            font = self._font(max(1, int(round(14 * self.render_scale))))
            self._ui_font_obj = font
        return font

    def _clear_sprite_caches(self):
        """切换渲染倍率后清理按 id 缓存的特效/变换结果，避免旧 Surface id 复用导致闪烁"""
        for sprite in self.sprites:
            for name in ('_color_cache', '_brightness_cache',
                         '_distortion_cache', '_transform_cache',
                         '_text_cache'):
                if name in sprite.__dict__:
                    sprite.__dict__[name] = {}
        self._slider_hits = []

    def _set_render_scale(self, scale):
        scale = max(1.0, min(self.max_render_scale, float(scale)))
        if abs(scale - self.render_scale) < 1e-3:
            return
        old_pen = self.pen_layer
        old_used = self._pen_used
        self.render_scale = scale
        self._ui_font_obj = None
        self.stage_surface = self._make_stage_surface()
        new_size = self._stage_pixel_size()
        self.pen_layer = pygame.Surface(new_size, pygame.SRCALPHA)
        # 画笔内容不能因为缩放窗口就丢失：按新倍率重建而不是直接清空
        self._pen_used = bool(old_used and old_pen is not None)
        if self._pen_used:
            try:
                pygame.transform.smoothscale(old_pen, new_size, self.pen_layer)
            except Exception:
                self.pen_layer.blit(pygame.transform.smoothscale(
                    old_pen, new_size), (0, 0))
        if self.background is not None:
            self.background = pygame.transform.smoothscale(
                self.background, new_size)
        # 造型位图按 (名字, 倍率) 保留，窗口来回缩放时无需重新栅格化
        self.costume_cache.clear()
        self.costume_image_scales.clear()
        self.mask_cache.clear()
        self._clear_sprite_caches()
        self._view_scaled = None
        self._view_size = None
        # 切换倍率后的一段帧内不做自适应判断：避免把重新栅格化的耗时误判为持续卡顿
        self._scale_cooldown = 30
        self._slow_streak = 0
        self._fast_streak = 0

    def _ensure_render_scale(self):
        """窗口尺寸稳定后再切换内部渲染倍率，避免拖动窗口时反复重建/闪烁"""
        if self.headless or not self._manual_view:
            return
        try:
            scale = self._view_geometry()[0]
        except Exception:
            return
        target = max(1.0, min(self.max_render_scale,
                              round(scale * 4) / 4.0))
        target = min(target, self._quality_cap)
        if target != self._scale_target:
            # 目标变化（窗口仍在拖动）：重新计时
            self._scale_target = target
            self._scale_stable = 0
            return
        if abs(target - self.render_scale) < 0.25:
            self._scale_stable = 0
            return
        self._scale_stable += 1
        if self._scale_stable < 6:
            return
        self._scale_stable = 0
        self._set_render_scale(target)

    def set_window_size(self, width, height):
        """调整窗口大小（舞台仍按宽高比缩放）"""
        width, height = max(1, int(width)), max(1, int(height))
        if self.headless:
            return
        try:
            flags = pygame.RESIZABLE
            if self.fullscreen:
                flags |= pygame.FULLSCREEN
            self.screen = pygame.display.set_mode((width, height), flags)
            self._windowed_size = (width, height)
            self._view_size = None
            self._view_scaled = None
        except Exception:
            pass

    def set_fullscreen(self, enabled):
        """进入/退出全屏，退出时恢复之前的窗口尺寸"""
        if self.headless:
            return
        enabled = bool(enabled)
        if enabled == self.fullscreen:
            return
        try:
            if enabled:
                self._windowed_size = self.screen.get_size()
                self.screen = pygame.display.set_mode((0, 0),
                                                      pygame.FULLSCREEN)
                self.fullscreen = True
            else:
                width, height = self._windowed_size or (
                    self.stage_width, self.stage_height + self.toolbar_height)
                self.screen = pygame.display.set_mode((width, height),
                                                      pygame.RESIZABLE)
                self.fullscreen = False
            self._view_size = None
            self._view_scaled = None
        except Exception:
            pass

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

    def _stage_area_contains(self, pos):
        """窗口坐标是否落在舞台区域（不含顶部工具栏与黑边）"""
        if not self._manual_view:
            return True
        _scale, offset, size = self._view_geometry()
        return pygame.Rect(offset, size).collidepoint(pos)

    def apply_mouse_cursor(self):
        """按“是否在舞台内”应用光标状态：工具栏/黑边始终显示系统箭头"""
        if not self._manual_view:
            return
        if not self._cursor_over_stage:
            self._applied_cursor = 'arrow-outside'
            try:
                pygame.mouse.set_visible(True)
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
            except Exception:
                pass
            return
        if not self._cursor_visible:
            self._applied_cursor = 'hidden'
            try:
                pygame.mouse.set_visible(False)
            except Exception:
                pass
            return
        self._applied_cursor = 'custom' if self._cursor_custom is not None \
            else ('system', self._cursor_system)
        try:
            pygame.mouse.set_visible(True)
            if self._cursor_custom is not None:
                pygame.mouse.set_cursor(*self._cursor_custom)
            else:
                constant = getattr(
                    pygame, 'SYSTEM_CURSOR_' + self._cursor_system,
                    pygame.SYSTEM_CURSOR_ARROW)
                pygame.mouse.set_cursor(constant)
        except Exception:
            pass

    def _update_cursor_for_position(self, pos):
        """鼠标在舞台/工具栏之间移动时切换光标的作用范围"""
        over_stage = self._stage_area_contains(pos)
        if over_stage != self._cursor_over_stage:
            self._cursor_over_stage = over_stage
            self.apply_mouse_cursor()

    def _present(self):
        """把逻辑舞台呈现到窗口；按宽高比居中放大到窗口最大可用区域"""
        if self._manual_view:
            scale, offset, (draw_width, draw_height) = self._view_geometry()
            self.view_scale = scale
            self.view_offset = offset
            window_width, window_height = self.screen.get_size()
            if window_width <= 0 or window_height <= 0:
                return
            stage_width_px, stage_height_px = self.stage_surface.get_size()
            if abs(draw_width - stage_width_px) <= 1 \
                    and abs(draw_height - stage_height_px) <= 1:
                # 内部倍率与窗口像素接近 1:1，直接 blit，省掉每帧 smoothscale
                self.screen.fill((0, 0, 0))
                self.screen.blit(self.stage_surface, offset)
            else:
                if self._view_scaled is None \
                        or self._view_size != (draw_width, draw_height):
                    self._view_size = (draw_width, draw_height)
                    self._view_scaled = pygame.Surface(
                        (draw_width, draw_height)).convert()
                # 放大到 1.5 倍以上时用最近邻，速度远快于 smoothscale 且观感接近
                if draw_width >= stage_width_px * 1.5:
                    pygame.transform.scale(self.stage_surface,
                                           (draw_width, draw_height),
                                           self._view_scaled)
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
        self.pen_layer = pygame.Surface(self._stage_pixel_size(), pygame.SRCALPHA)
        self._pen_used = False
        if self.background is not None:
            self.background = pygame.transform.smoothscale(
                self.background, self._stage_pixel_size())
        self.mask_cache.clear()
        self._clear_sprite_caches()
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

    def pen_draw_segment(self, start, end, color, size, cap_start=False,
                         sprite=None):
        size = max(1, int(round(_sc_num(size) * self.render_scale)))
        if len(color) > 3 and color[3] <= 0:
            # 完全透明（透明度 100）的线段不会改变画面
            return
        scale = self.render_scale
        sx = int((self.stage_width / 2 + start[0]) * scale)
        sy = int((self.stage_height / 2 - start[1]) * scale)
        ex = int((self.stage_width / 2 + end[0]) * scale)
        ey = int((self.stage_height / 2 - end[1]) * scale)
        self._pen_used = True
        # Clipping & Blending：画笔线段同样受角色裁剪框/混合模式影响
        clip_applied, previous_clip = (False, None)
        if sprite is not None and getattr(sprite, '_clipbox', None) is not None:
            clip_applied, previous_clip = _clipbox_apply(
                self.pen_layer, self, sprite)
        mode = getattr(sprite, '_blend_mode', 'default') if sprite else 'default'
        try:
            if mode and mode != 'default':
                self._pen_segment_blended(
                    color, sx, sy, ex, ey, size, cap_start, mode)
            else:
                pygame.draw.line(self.pen_layer, color, (sx, sy), (ex, ey), size)
                if size > 1:
                    radius = size // 2
                    # 起点圆帽通常已被上一段终点圆帽覆盖，只画终点即可
                    if cap_start:
                        pygame.draw.circle(self.pen_layer, color, (sx, sy), radius)
                    pygame.draw.circle(self.pen_layer, color, (ex, ey), radius)
                if self.hq_pen:
                    pygame.draw.aaline(self.pen_layer, color, (sx, sy), (ex, ey))
        finally:
            if clip_applied:
                self.pen_layer.set_clip(previous_clip)

    def _pen_segment_blended(self, color, sx, sy, ex, ey, size, cap_start, mode):
        """混合模式线段：先画到临时小图，再按混合模式贴回画笔层"""
        radius = size // 2 if size > 1 else 0
        left = min(sx, ex) - radius
        top = min(sy, ey) - radius
        width = max(1, abs(ex - sx) + radius * 2 + 1)
        height = max(1, abs(sy - ey) + radius * 2 + 1)
        temp = pygame.Surface((width, height), pygame.SRCALPHA)
        lx, ly = sx - left, sy - top
        rx, ry = ex - left, ey - top
        pygame.draw.line(temp, color, (lx, ly), (rx, ry), size)
        if size > 1:
            if cap_start:
                pygame.draw.circle(temp, color, (lx, ly), radius)
            pygame.draw.circle(temp, color, (rx, ry), radius)
        if self.hq_pen:
            pygame.draw.aaline(temp, color, (lx, ly), (rx, ry))
        _blend_blit(self.pen_layer, temp,
                    pygame.Rect(left, top, width, height), mode)

    def pen_stamp(self, sprite):
        # 图章使用角色当前外观：颜色/亮度/透明度/形状特效都会一起盖上去
        transformed, rect, x, y, scale, _direction = sprite._rendered_image()
        clip_applied, previous_clip = (False, None)
        if sprite._clipbox is not None:
            clip_applied, previous_clip = _clipbox_apply(
                self.pen_layer, self, sprite)
        mode = getattr(sprite, '_blend_mode', 'default')
        try:
            if transformed is not None:
                if mode and mode != 'default':
                    _blend_blit(self.pen_layer, transformed, rect, mode)
                else:
                    self.pen_layer.blit(transformed, rect)
            else:
                pygame.draw.circle(self.pen_layer, sprite._placeholder_color(),
                                   (x, y), max(6, int(20 * scale)))
        finally:
            if clip_applied:
                self.pen_layer.set_clip(previous_clip)
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
            mapped = getattr(type(target), 'LIST_ATTRS', {}).get(text)
            for key in (mapped, _sc_ident(text, 'lst'), text):
                if key and isinstance(data.get(key), list):
                    return data, key
        stage = self.stage_sprite
        mapped = getattr(type(stage), 'LIST_ATTRS', {}).get(text) \
            if stage is not None else None
        for key in (mapped, _sc_ident(text, 'lst'), text):
            if key and isinstance(GLOBALS.get(key), list):
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
        entries = []
        for sprite in list(self.sprites):
            sprite._global_running = True
            entries.extend(sprite._handlers.get("green_flag", []))
        with self._start_gate_cond:
            self._start_gate_total = len(entries)
            self._start_gate_next = 0
        for index, func in enumerate(entries):
            self.start_script(func, gate_index=index)

    def start_script(self, func, received_data=None, gate_index=None):
        sprite = getattr(func, "__self__", None)
        context = _ScriptContext(self._script_order)
        self._script_order += 1
        context.sprite = sprite
        context.func = func
        context.received_data = received_data
        context.gate_index = gate_index
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

        thread = _ScriptThread(runner)
        # 供 More Events 的 while 帽子在条件变假时停止对应线程
        thread._scratch_context = context
        context.thread = thread
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
        scale = self.render_scale
        rect = self._ask_rect()
        draw_rect = pygame.Rect(int(rect.x * scale), int(rect.y * scale),
                                int(rect.width * scale),
                                int(rect.height * scale))
        pygame.draw.rect(self.stage_surface, (255, 255, 255), draw_rect,
                         border_radius=max(1, int(6 * scale)))
        pygame.draw.rect(self.stage_surface, (90, 90, 90), draw_rect,
                         max(1, int(scale)), border_radius=max(1, int(6 * scale)))
        font = self._ui_font()
        text = self.ask_question + ' ' + self.ask_buffer + self.ask_composition + '_'
        surface = font.render(text, True, (30, 30, 30))
        area_width = max(20, draw_rect.width - int(90 * scale))
        if surface.get_width() > area_width:
            # 文字太长时只显示末尾（当前输入的内容）
            clipped = pygame.Surface((area_width, draw_rect.height - int(8 * scale)),
                                     pygame.SRCALPHA)
            clipped.blit(surface, (area_width - surface.get_width(), 0))
            surface = clipped
        self.stage_surface.blit(surface, (draw_rect.x + int(8 * scale),
                                          draw_rect.y + int(11 * scale)))
        button = self._ask_button_rect()
        draw_button = pygame.Rect(int(button.x * scale), int(button.y * scale),
                                  int(button.width * scale),
                                  int(button.height * scale))
        pygame.draw.rect(self.stage_surface, (80, 135, 220), draw_button,
                         border_radius=max(1, int(5 * scale)))
        label = font.render('确认', True, (255, 255, 255))
        self.stage_surface.blit(label, label.get_rect(center=draw_button.center))

    def stop_all_scripts(self):
        for context in list(self.scripts):
            context.running = False
        for sprite in self.sprites:
            sprite._global_running = False
            # Clipping & Blending：停止全部时清除裁剪框与混合模式
            sprite._clipbox = None
            sprite._blend_mode = 'default'
            # 递归函数的局部变量栈：停止时清空，避免被中断的递归留下残帧
            for name, value in list(sprite.__dict__.items()):
                if name.startswith(('lst__py_frame_', '__py_frame_')) \
                        and isinstance(value, list):
                    value.clear()
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

    def _wait_start_gate(self, context):
        """绿旗脚本按注册顺序依次获得第一次执行权"""
        index = getattr(context, 'gate_index', None)
        if index is None or getattr(context, 'first_turn_done', False):
            return
        with self._start_gate_cond:
            while self.running and self._start_gate_next != index:
                self._start_gate_cond.wait(0.05)
            context.first_turn_done = True
            if self._start_gate_next == index:
                self._start_gate_next += 1
            self._start_gate_cond.notify_all()

    def _trigger_event(self, event):
        """启动注册在指定普通事件上的脚本（如剪贴板复制/粘贴帽子）"""
        for sprite in list(self.sprites):
            handlers = list(sprite._handlers.get(event, []))
            if not handlers:
                continue
            sprite._running = True
            for func in handlers:
                self.start_script(func)

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
        self._ensure_render_scale()
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
                # Clipboard扩展：Ctrl+C / Ctrl+V 触发复制/粘贴帽子
                try:
                    ctrl = bool(pygame.key.get_mods() & pygame.KMOD_CTRL)
                except Exception:
                    ctrl = False
                if ctrl and event.key in (pygame.K_c, pygame.K_v):
                    if event.key == pygame.K_c:
                        self._trigger_event('clipboard_copy')
                    else:
                        self._clipboard_last_pasted = self._read_clipboard()
                        if self.ask_pending and self._clipboard_last_pasted:
                            self.ask_buffer += self._clipboard_last_pasted
                            self.ask_key_pending = ''
                        self._trigger_event('clipboard_paste')
                    if not self.ask_pending:
                        continue
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
                self._update_cursor_for_position(event.pos)
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
                slider, slider_rect = self._slider_hit(stage_pos)
                if slider is not None:
                    self._slider_drag = (slider, slider_rect)
                    self._apply_slider(slider, slider_rect, stage_pos[0])
                    continue
                self._start_drag(event.pos)
                self._handle_click(event.pos)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self._update_cursor_for_position(event.pos)
                if self.ask_pending:
                    stage_pos = self._window_to_stage(event.pos)
                    if self._ask_button_rect().collidepoint(stage_pos):
                        # 窗口激活时按下事件可能被系统吞掉，松开时再兜底
                        self._submit_ask()
                        continue
                self.mouse_down = False
                self.dragging = None
                self._slider_drag = None
            elif event.type == pygame.MOUSEMOTION:
                self._update_cursor_for_position(event.pos)
                self.mouse_x, self.mouse_y = self._screen_to_scratch(event.pos)
                if self._slider_drag is not None:
                    slider, slider_rect = self._slider_drag
                    self._apply_slider(
                        slider, slider_rect, self._window_to_stage(event.pos)[0])
                if self.dragging is not None:
                    offset_x, offset_y = self.dragging_offset
                    self.dragging.x = self.mouse_x + offset_x
                    self.dragging.y = self.mouse_y + offset_y
                    self.dragging._apply_fencing()
        work_start = time.time()
        self._update_state()
        if self._warp_active <= 0:
            # warp 块运行期间保持上一帧画面，结束后再统一渲染
            self._draw()
            self._present()
        self._adapt_quality(time.time() - work_start)
        with self.frame_condition:
            self.frame += 1
            self.frame_condition.notify_all()
        if not self.headless:
            self.clock.tick(self.fps)

    def _adapt_quality(self, work_seconds):
        """按实际每帧耗时自适应降低渲染倍率，避免大窗口下持续掉帧"""
        if self.headless or not self.fps or not self._manual_view:
            return
        if self._scale_cooldown > 0:
            self._scale_cooldown -= 1
        budget = max(0.012, 0.9 / float(self.fps))
        if work_seconds > budget:
            self._slow_streak += 1
            self._fast_streak = 0
        else:
            self._slow_streak = 0
            if work_seconds < budget * 0.5:
                self._fast_streak += 1
            else:
                self._fast_streak = 0
        if self._scale_cooldown > 0:
            return
        severe = work_seconds > budget * 2
        if ((self._slow_streak >= 8 or (severe and self._slow_streak >= 3))
                and self.render_scale > 1.0):
            step = 1.0 if (severe and self._slow_streak >= 3) else 0.5
            self._quality_cap = max(1.0, self.render_scale - step)
            self._scale_target = self._quality_cap
            self._scale_stable = 0
            self._set_render_scale(self._quality_cap)
            self._slow_streak = 0
        elif self._fast_streak >= 240 \
                and self._quality_cap < self.max_render_scale:
            self._quality_cap = min(self.max_render_scale,
                                    self._quality_cap + 0.5)
            self._fast_streak = 0

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
        scale = self.render_scale
        panel = pygame.Surface((int(width * scale), int(height * scale)),
                               pygame.SRCALPHA)
        panel.fill((0, 0, 0, 190))
        self.stage_surface.blit(panel, (int(6 * scale), int(6 * scale)))
        font = self._ui_font()
        for index, line in enumerate(lines):
            surface = font.render(line, True, (255, 255, 255))
            self.stage_surface.blit(
                surface, (int(12 * scale), int((10 + index * 16) * scale)))

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
                sprite._draw(self.stage_surface, self._ui_font())
        self._draw_monitors()
        self._draw_ask()
        if self.debug_overlay:
            self._draw_debug()

    def _all_monitors(self):
        return list(MONITORS) + self.dynamic_monitors

    def show_monitor(self, kind, name, owner, visible, attr=None):
        """显示/隐藏变量或列表监视器（不存在时动态创建）"""
        prefix = 'lst' if kind == 'list' else 'var'
        attr = attr or _sc_ident(name, prefix)
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

    def _monitor_value(self, monitor):
        owner = monitor.get("sprite")
        if owner:
            target = self.find_sprite(owner)
            return getattr(target, monitor["attr"], None) if target else None
        return GLOBALS.get(monitor["attr"])

    def _set_monitor_value(self, monitor, value):
        """把滑动条拖动结果写回对应的变量"""
        owner = monitor.get("sprite")
        if owner:
            target = self.find_sprite(owner)
            if target is not None:
                setattr(target, monitor["attr"], value)
        else:
            GLOBALS[monitor["attr"]] = value

    @staticmethod
    def _slider_range(monitor):
        low = _sc_num(monitor.get("slider_min", 0))
        high = _sc_num(monitor.get("slider_max", 100))
        if high < low:
            low, high = high, low
        return low, high

    def _slider_track_rect(self, rect):
        """滑动条轨道区域（监视器底部）"""
        return pygame.Rect(rect.x + 10, rect.bottom - 16,
                           max(10, rect.width - 20), 8)

    def _slider_hit(self, pos):
        """返回鼠标位置命中的滑动条监视器"""
        for monitor, rect in self._slider_hits:
            if self._slider_track_rect(rect).inflate(4, 8).collidepoint(pos):
                return monitor, rect
        return None, None

    def _apply_slider(self, monitor, rect, x):
        track = self._slider_track_rect(rect)
        ratio = (x - track.x) / float(max(1, track.width))
        ratio = max(0.0, min(1.0, ratio))
        low, high = self._slider_range(monitor)
        value = low + (high - low) * ratio
        if monitor.get("discrete", True):
            value = _sc_round(value)
        value = max(low, min(high, value))
        self._set_monitor_value(monitor, value)

    def _draw_monitors(self):
        self._slider_hits = []
        scale = self.render_scale
        font = self._ui_font()

        def scaled_rect(rect):
            return pygame.Rect(int(rect.x * scale), int(rect.y * scale),
                               int(rect.width * scale),
                               int(rect.height * scale))

        def scaled_point(x, y):
            return (int(x * scale), int(y * scale))

        for monitor in self._all_monitors():
            if monitor.get('visible') is False:
                continue
            rect = pygame.Rect(int(monitor["x"]), int(monitor["y"]),
                               int(monitor["width"]), int(monitor["height"]))
            draw_rect = scaled_rect(rect)
            label = monitor.get("label") or monitor["name"]
            value = self._monitor_value(monitor)
            if monitor["kind"] == "list":
                pygame.draw.rect(self.stage_surface, (255, 255, 255), draw_rect,
                                 border_radius=max(1, int(4 * scale)))
                pygame.draw.rect(self.stage_surface, (130, 130, 130), draw_rect,
                                 max(1, int(scale)), border_radius=max(1, int(4 * scale)))
                title = font.render(label, True, (40, 40, 40))
                self.stage_surface.blit(title, scaled_point(rect.x + 5, rect.y + 3))
                if isinstance(value, list):
                    line_y = rect.y + 21
                    for item in value:
                        if line_y + 14 > rect.bottom - 2:
                            break
                        text = font.render(_sc_str(item), True, (60, 60, 60))
                        self.stage_surface.blit(
                            text, scaled_point(rect.x + 8, line_y))
                        line_y += 15
            elif monitor.get("mode") == "slider":
                pygame.draw.rect(self.stage_surface, (255, 255, 255), draw_rect,
                                 border_radius=max(1, int(3 * scale)))
                pygame.draw.rect(self.stage_surface, (130, 130, 130), draw_rect,
                                 max(1, int(scale)), border_radius=max(1, int(3 * scale)))
                name_surface = font.render(label, True, (40, 40, 40))
                value_surface = font.render(_sc_str(value), True, (40, 40, 40))
                self.stage_surface.blit(
                    name_surface, scaled_point(rect.x + 5, rect.y + 2))
                self.stage_surface.blit(
                    value_surface,
                    (draw_rect.right - int(5 * scale) - value_surface.get_width(),
                     int((rect.y + 2) * scale)))
                track = self._slider_track_rect(rect)
                draw_track = scaled_rect(track)
                knob_radius = max(2, int(round(6 * scale)))
                pygame.draw.rect(self.stage_surface, (210, 210, 210), draw_track,
                                 border_radius=max(1, int(4 * scale)))
                low, high = self._slider_range(monitor)
                span = high - low
                ratio = 0.0 if abs(span) < 1e-9 else \
                    max(0.0, min(1.0, (_sc_num(value) - low) / span))
                fill = pygame.Rect(draw_track.x, draw_track.y,
                                   max(0, int(round(draw_track.width * ratio))),
                                   draw_track.height)
                if fill.width:
                    pygame.draw.rect(self.stage_surface, (76, 151, 255), fill,
                                     border_radius=max(1, int(4 * scale)))
                knob_x = draw_track.x + int(round(draw_track.width * ratio))
                pygame.draw.circle(self.stage_surface, (76, 151, 255),
                                   (knob_x, draw_track.centery), knob_radius)
                pygame.draw.circle(self.stage_surface, (255, 255, 255),
                                   (knob_x, draw_track.centery), knob_radius,
                                   max(1, int(scale)))
                self._slider_hits.append((monitor, rect))
            else:
                text = f"{label} {_sc_str(value)}"
                pygame.draw.rect(self.stage_surface, (255, 255, 255), draw_rect,
                                 border_radius=max(1, int(3 * scale)))
                pygame.draw.rect(self.stage_surface, (130, 130, 130), draw_rect,
                                 max(1, int(scale)), border_radius=max(1, int(3 * scale)))
                surface = font.render(text, True, (40, 40, 40))
                self.stage_surface.blit(surface, scaled_point(rect.x + 5, rect.y + 3))

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
                image, self._stage_pixel_size())
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

    def _costume_scale_cap(self, name):
        """大体积的 SVG 通常是包裹内嵌 PNG 的截图，放大栅格化不会增加细节"""
        cap = self._costume_scale_caps.get(name)
        if cap is not None:
            return cap
        cap = 3.0
        path = self._asset_path(name)
        if path:
            try:
                if os.path.getsize(path) > 512 * 1024:
                    # 内嵌位图截图型 SVG：2 倍足够清晰，同时控制内存/重栅格化开销
                    cap = 2.0
            except OSError:
                pass
        self._costume_scale_caps[name] = cap
        return cap

    def get_sprite_image(self, name):
        if not name:
            return None
        is_svg = self._costume_kind.get(name)
        if is_svg is None:
            path = self._asset_path(name)
            is_svg = bool(path and path.lower().endswith('.svg'))
            self._costume_kind[name] = is_svg
        if is_svg:
            scale = min(self.render_scale, self._costume_scale_cap(name))
        else:
            scale = 1.0
        if name in self.costume_cache \
                and self.costume_image_scales.get(name) == scale:
            return self.costume_cache[name]
        key = (name, scale)
        image = self.costume_cache_scales.get(key)
        if image is None:
            image = self._load_image(name, scale)
            if image is not None:
                self.costume_cache_scales[key] = image
                if len(self.costume_cache_scales) > 64:
                    # 简单裁剪：丢掉最早缓存的一批，控制显存
                    for old_key in list(self.costume_cache_scales)[:16]:
                        self.costume_cache_scales.pop(old_key, None)
        self.costume_cache[name] = image
        self.costume_image_scales[name] = scale
        return image

    def get_sprite_image_scale(self, name):
        """返回造型位图的栅格化倍率（SVG 可能是 1~3 倍）"""
        if not name:
            return 1.0
        if name not in self.costume_cache:
            self.get_sprite_image(name)
        return self.costume_image_scales.get(name, 1.0)

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
        radius = max(6, int(20 * _sc_num(sprite.size) / 100.0
                           * self.render_scale))
        center = (int((self.stage_width / 2 + _sc_num(sprite.x))
                      * self.render_scale),
                  int((self.stage_height / 2 - _sc_num(sprite.y))
                      * self.render_scale))
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
        scale = self.render_scale
        if target == "_edge_":
            return (rect.left <= 0 or rect.right >= self.stage_width * scale or
                    rect.top <= 0 or rect.bottom >= self.stage_height * scale)
        if target == "_mouse_":
            x = (self.stage_width / 2 + self.mouse_x) * scale
            y = (self.stage_height / 2 - self.mouse_y) * scale
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

    def _prepare_render_scale_for_start(self):
        """启动时先按最终窗口大小确定渲染倍率，避免预加载后马上重栅格化"""
        if self.headless or not self._manual_view:
            return
        try:
            scale = self._view_geometry()[0]
        except Exception:
            return
        target = max(1.0, min(self.max_render_scale,
                              round(scale * 4) / 4.0))
        target = min(target, self._quality_cap)
        if abs(target - self.render_scale) >= 0.25:
            self._set_render_scale(target)
        self._scale_target = target
        self._scale_stable = 6

    def _preload_assets(self):
        """分帧预加载造型/背景，并显示加载进度条

        每帧最多占用约 12ms，避免一次性加载大项目导致窗口长时间无响应。
        """
        names = []
        seen = set()

        def add(name):
            if not name:
                return
            name = str(name)
            if name in seen:
                return
            if not name.lower().endswith(
                    ('.svg', '.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp')):
                return
            seen.add(name)
            names.append(name)

        add(STAGE_COSTUME)
        for backdrop in BACKDROPS:
            add(backdrop[1])
        for sprite in self.sprites:
            for costume in getattr(sprite, 'costumes', ()) or ():
                add(costume.get('md5ext') or costume.get('name'))
        pending = [name for name in names
                   if name not in self._preloaded_names]
        total = len(pending)
        if not total:
            return
        index = 0
        while index < total and self.running:
            started = time.time()
            while index < total and time.time() - started < 0.012:
                name = pending[index]
                index += 1
                self.get_sprite_image(name)
                self._preloaded_names.add(name)
            if self.headless:
                continue
            self._draw_loading(index, total)
            self._present()
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (
                        event.type == pygame.KEYDOWN
                        and event.key == pygame.K_ESCAPE):
                    self.running = False
            if self.fps:
                self.clock.tick(self.fps)
        if not self.headless and self.running:
            self.stage_surface.fill((255, 255, 255))

    def _draw_loading(self, done, total):
        """绘制启动加载进度条"""
        scale = self.render_scale
        width, height = self.stage_surface.get_size()
        self.stage_surface.fill((30, 34, 42))
        font = self._ui_font()
        title = font.render('正在加载资源…', True, (240, 240, 240))
        self.stage_surface.blit(
            title, title.get_rect(center=(width // 2,
                                          height // 2 - int(46 * scale))))
        bar_width = max(80, int(self.stage_width * 0.62 * scale))
        bar_height = max(6, int(10 * scale))
        bar_x = (width - bar_width) // 2
        bar_y = height // 2
        ratio = 0.0 if total <= 0 else done / float(total)
        radius = max(1, int(5 * scale))
        pygame.draw.rect(self.stage_surface, (68, 74, 86),
                         (bar_x, bar_y, bar_width, bar_height),
                         border_radius=radius)
        if ratio > 0:
            pygame.draw.rect(
                self.stage_surface, (76, 151, 255),
                (bar_x, bar_y, max(1, int(bar_width * ratio)), bar_height),
                border_radius=radius)
        detail = font.render('%d / %d' % (done, total), True, (200, 205, 215))
        self.stage_surface.blit(
            detail, detail.get_rect(center=(width // 2,
                                            bar_y + int(28 * scale))))

    def start(self, max_frames=None, max_seconds=None):
        if pygame is None:
            raise RuntimeError("运行生成的脚本需要pygame: pip install pygame")
        for sprite in list(self.sprites):
            sprite.run()
        if not self.headless:
            self._prepare_render_scale_for_start()
            self._preload_assets()
            if not self.running:
                return
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
                if self.headless and max_frames is not None:
                    # 无头主循环远快于脚本线程；给脚本线程一点调度时间，
                    # 避免 --frames 在脚本还没执行完时就退出。
                    # 需要精确按时间结束时请使用 --seconds。
                    time.sleep(0.001)
                if deadline is not None and time.time() >= deadline:
                    break
        finally:
            self.running = False
            with self.frame_condition:
                self.frame_condition.notify_all()

    def shutdown(self):
        self.running = False
        # 先停掉所有脚本，避免关闭窗口后仍有线程在后台空转
        self.stop_all_scripts()
        with self.frame_condition:
            self.frame_condition.notify_all()
        deadline = time.time() + 0.2
        for context in list(self.scripts):
            thread = getattr(context, 'thread', None)
            remaining = deadline - time.time()
            if thread is None or remaining <= 0:
                break
            thread.join(remaining)
        self._close_microphone()
        try:
            pygame.display.quit()
        except Exception:
            pass

    def _asset_path(self, filename):
        """素材优先从脚本同目录读取，其次兼容旧的assets子目录"""
        if not filename:
            return None
        if self._asset_path_root != self.assets_dir:
            self._asset_path_cache.clear()
            self._asset_path_root = self.assets_dir
        if filename in self._asset_path_cache:
            return self._asset_path_cache[filename]
        name = os.path.basename(filename)
        result = None
        for folder in (self.assets_dir, os.path.join(self.assets_dir, 'assets')):
            path = os.path.join(folder, name)
            if os.path.exists(path):
                result = path
                break
        self._asset_path_cache[filename] = result
        return result

    def _load_image(self, filename, scale=1.0):
        path = self._asset_path(filename)
        if not path:
            return None
        if path.lower().endswith(".svg"):
            # 内置渲染器已支持渐变/透明度，且不会像 cairosvg 那样在首次使用时
            # 触发数秒的导入开销；需要更高保真度时可设置 SCRATCH_SVG_CAIROSVG=1
            if self.use_cairosvg:
                try:
                    import cairosvg
                    data = cairosvg.svg2png(url=path, scale=max(1.0, scale))
                    image = pygame.image.load(io.BytesIO(data))
                    try:
                        return image.convert_alpha()
                    except Exception:
                        return image
                except Exception:
                    pass
            return self._render_svg(path, scale)
        try:
            image = pygame.image.load(path)
        except Exception:
            return None
        try:
            return image.convert_alpha()
        except Exception:
            return image

    # ===================== SVG 渲染 =====================
    # 说明：先一次性扫描所有标签，把 <g> 的样式/变换压栈，元素处直接取栈顶，
    # 避免旧实现对每个元素重复扫描整段 XML（元素多时是 O(n^2)）。

    def _svg_default_style(self):
        return {
            'fill': '#000000',
            'stroke': 'none',
            'stroke_width': '1',
            'font_size': '16',
            'opacity': 1.0,
            'fill_opacity': 1.0,
            'stroke_opacity': 1.0,
        }

    def _svg_child_style(self, base, attrs):
        style = dict(base)
        for key, name in (('fill', 'fill'), ('stroke', 'stroke'),
                          ('stroke_width', 'stroke-width'),
                          ('font_size', 'font-size')):
            value = _svg_get(attrs, name)
            if value is not None:
                style[key] = value
        style['opacity'] = base['opacity'] * _svg_opacity(
            _svg_get(attrs, 'opacity'))
        for key, name in (('fill_opacity', 'fill-opacity'),
                          ('stroke_opacity', 'stroke-opacity')):
            value = _svg_opacity(_svg_get(attrs, name), None)
            if value is not None:
                style[key] = base[key] * value
        return style

    def _svg_parse_gradients(self, text):
        """解析 linearGradient / radialGradient 及其中的 stop"""
        gradients = {}
        pattern = re.compile(
            r'<(linearGradient|radialGradient)\b([^>]*)>(.*?)</\1>', re.S)
        for match in pattern.finditer(text):
            kind, attrs, body = match.group(1), match.group(2), match.group(3)
            ident = _svg_get(attrs, 'id')
            if not ident:
                continue
            stops = []
            for stop in re.finditer(r'<stop\b([^>]*?)/?>', body):
                stop_attrs = stop.group(1)
                offset_text = _sc_str(_svg_attr(stop_attrs, 'offset', '0')).strip()
                if offset_text.endswith('%'):
                    offset = _sc_num(offset_text[:-1]) / 100.0
                else:
                    offset = _sc_num(offset_text)
                color_text = _svg_prop(stop_attrs, 'stop-color', '#000000')
                opacity_text = _svg_prop(stop_attrs, 'stop-opacity', '1')
                color = _svg_color(color_text) or (0, 0, 0, 255)
                alpha = int(round(color[3] * _svg_opacity(opacity_text)))
                stops.append((max(0.0, min(1.0, offset)),
                              (color[0], color[1], color[2],
                               max(0, min(255, alpha)))))
            stops.sort(key=lambda item: item[0])
            gradients[ident] = {
                'type': 'linear' if kind == 'linearGradient' else 'radial',
                'attrs': attrs,
                'stops': stops,
            }
        # xlink:href 复用其它渐变的 stop
        for gradient in gradients.values():
            if gradient['stops']:
                continue
            href = _svg_attr(gradient['attrs'], 'xlink:href') \
                or _svg_attr(gradient['attrs'], 'href')
            if href.startswith('#'):
                gradient['stops'] = list(
                    gradients.get(href[1:], {}).get('stops') or ())
        return gradients

    @staticmethod
    def _svg_matrix_scale(matrix):
        return max(0.01, math.hypot(matrix[0], matrix[1]))

    def _svg_geometry(self, kind, attrs, matrix):
        """计算元素在输出画布上的几何：折线点或椭圆矩形"""
        try:
            if kind == 'rect':
                rx = _sc_num(_svg_get(attrs, 'x', '0'))
                ry = _sc_num(_svg_get(attrs, 'y', '0'))
                rw = _sc_num(_svg_get(attrs, 'width', '0'))
                rh = _sc_num(_svg_get(attrs, 'height', '0'))
                return 'polygon', [
                    _svg_point(matrix, rx, ry),
                    _svg_point(matrix, rx + rw, ry),
                    _svg_point(matrix, rx + rw, ry + rh),
                    _svg_point(matrix, rx, ry + rh),
                ]
            if kind in ('circle', 'ellipse'):
                if kind == 'circle':
                    cx = _sc_num(_svg_get(attrs, 'cx', '0'))
                    cy = _sc_num(_svg_get(attrs, 'cy', '0'))
                    radius = _sc_num(_svg_get(attrs, 'r', '0'))
                    rx = ry = radius
                else:
                    cx = _sc_num(_svg_get(attrs, 'cx', '0'))
                    cy = _sc_num(_svg_get(attrs, 'cy', '0'))
                    rx = _sc_num(_svg_get(attrs, 'rx', '0'))
                    ry = _sc_num(_svg_get(attrs, 'ry', '0'))
                center = _svg_point(matrix, cx, cy)
                scale_x = math.hypot(matrix[0], matrix[1])
                scale_y = math.hypot(matrix[2], matrix[3])
                width = max(1, int(round(rx * scale_x * 2)))
                height = max(1, int(round(ry * scale_y * 2)))
                return 'ellipse', pygame.Rect(
                    int(round(center[0] - width / 2)),
                    int(round(center[1] - height / 2)), width, height)
            if kind == 'line':
                return 'line', [
                    _svg_point(matrix, _sc_num(_svg_get(attrs, 'x1', '0')),
                               _sc_num(_svg_get(attrs, 'y1', '0'))),
                    _svg_point(matrix, _sc_num(_svg_get(attrs, 'x2', '0')),
                               _sc_num(_svg_get(attrs, 'y2', '0'))),
                ]
            if kind in ('polygon', 'polyline'):
                values = [_sc_num(item) for item in
                          re.split(r'[ ,]+',
                                   _svg_get(attrs, 'points', '').strip())
                          if item]
                return kind, [
                    _svg_point(matrix, values[index], values[index + 1])
                    for index in range(0, len(values) - 1, 2)]
            if kind == 'path':
                return 'path', [
                    _svg_point(matrix, px, py)
                    for px, py in _svg_path_points(_svg_get(attrs, 'd', ''))]
        except (ValueError, TypeError, IndexError):
            return None
        return None

    def _svg_paint(self, surface, kind, geometry, color, width=0,
                   offset=(0, 0)):
        """把几何形状填充/描边到画布

        半透明颜色不能直接 draw（pygame 会覆盖而不是混色），
        先画到同尺寸临时层再 blit，才能得到正确的透明度叠加。
        """
        if color is None:
            return
        alpha = color[3] if len(color) > 3 else 255
        ox, oy = int(offset[0]), int(offset[1])
        target = surface
        base_x = base_y = 0
        if alpha < 255:
            bounds = self._svg_bbox(kind, geometry)
            if bounds is None:
                return
            margin = max(1, int(width)) + 2
            bounds = bounds.inflate(margin * 2, margin * 2).move(ox, oy)
            target = pygame.Surface(bounds.size, pygame.SRCALPHA)
            base_x, base_y = bounds.x, bounds.y
            ox -= base_x
            oy -= base_y
        if kind == 'ellipse':
            rect = geometry.move(ox, oy)
            if rect.width > 0 and rect.height > 0:
                if width > 0:
                    pygame.draw.ellipse(target, color, rect,
                                        max(1, int(width)))
                else:
                    pygame.draw.ellipse(target, color, rect)
        else:
            points = [(int(x + ox), int(y + oy)) for x, y in geometry]
            if len(points) >= 2:
                if width > 0:
                    pygame.draw.lines(target, color, kind == 'polygon', points,
                                      max(1, int(width)))
                elif len(points) >= 3:
                    pygame.draw.polygon(target, color, points)
        if target is not surface:
            surface.blit(target, (base_x, base_y))

    @staticmethod
    def _svg_apply_opacity(color, opacity):
        alpha = int(round(color[3] * max(0.0, min(1.0, opacity))))
        return (color[0], color[1], color[2], max(0, min(255, alpha)))

    @staticmethod
    def _svg_gradient_average(gradient):
        stops = gradient.get('stops') or []
        if not stops:
            return None
        count = float(len(stops))
        return tuple(int(round(sum(stop[1][index] for stop in stops) / count))
                     for index in range(4))

    def _svg_fill_paint(self, raw, gradients):
        """把 fill/stroke 值解析为 RGBA 或渐变定义"""
        if raw is None:
            return None
        text = _sc_str(raw).strip()
        if not text or text.lower() == 'none':
            return None
        if text.startswith('url('):
            start = text.find('#')
            end = text.find(')', start + 1)
            if start >= 0 and end > start:
                return gradients.get(text[start + 1:end])
            return None
        return _svg_color(text)

    @staticmethod
    def _svg_bbox(kind, geometry):
        if kind == 'ellipse':
            return geometry.copy()
        if not geometry:
            return None
        xs = [point[0] for point in geometry]
        ys = [point[1] for point in geometry]
        left = int(math.floor(min(xs)))
        top = int(math.floor(min(ys)))
        width = max(1, int(math.ceil(max(xs))) - left)
        height = max(1, int(math.ceil(max(ys))) - top)
        return pygame.Rect(left, top, width, height)

    def _svg_gradient_surface(self, gradient, bbox, matrix):
        """按包围盒生成渐变位图（支持线性/径向、stop 透明度）"""
        width = max(1, bbox.width)
        height = max(1, bbox.height)
        stops = gradient.get('stops') or []
        if not stops:
            return None
        attrs = gradient.get('attrs') or ''
        units = _svg_get(attrs, 'gradientUnits', 'objectBoundingBox')
        user_space = units == 'userSpaceOnUse'
        unit_scale = self._svg_matrix_scale(matrix)

        def coord_x(value, fallback):
            text = _sc_str(value if value not in (None, '') else fallback).strip()
            if text.endswith('%'):
                return _sc_num(text[:-1]) / 100.0 * width
            number = _sc_num(text)
            return number * unit_scale - bbox.x if user_space else number * width

        def coord_y(value, fallback):
            text = _sc_str(value if value not in (None, '') else fallback).strip()
            if text.endswith('%'):
                return _sc_num(text[:-1]) / 100.0 * height
            number = _sc_num(text)
            return number * unit_scale - bbox.y if user_space else number * height

        offsets = [stop[0] for stop in stops]
        colors = [stop[1] for stop in stops]

        def sample(t):
            if t <= offsets[0]:
                return colors[0]
            if t >= offsets[-1]:
                return colors[-1]
            for index in range(1, len(offsets)):
                if t <= offsets[index]:
                    span = offsets[index] - offsets[index - 1]
                    local = 0.0 if span <= 1e-9 else \
                        (t - offsets[index - 1]) / span
                    first, second = colors[index - 1], colors[index]
                    return tuple(
                        int(round(first[channel] +
                                  (second[channel] - first[channel]) * local))
                        for channel in range(4))
            return colors[-1]

        if gradient['type'] == 'linear':
            x1 = coord_x(_svg_get(attrs, 'x1'), '0%')
            y1 = coord_y(_svg_get(attrs, 'y1'), '0%')
            x2 = coord_x(_svg_get(attrs, 'x2'), '100%')
            y2 = coord_y(_svg_get(attrs, 'y2'), '0%')
        else:
            cx = coord_x(_svg_get(attrs, 'cx'), '50%')
            cy = coord_y(_svg_get(attrs, 'cy'), '50%')
            radius_text = _sc_str(_svg_get(attrs, 'r', '50%')).strip()
            if radius_text.endswith('%'):
                radius = _sc_num(radius_text[:-1]) / 100.0 * \
                    math.hypot(width, height) / math.sqrt(2)
            else:
                radius = _sc_num(radius_text) * (
                    unit_scale if user_space else
                    math.hypot(width, height) / math.sqrt(2))

        try:
            import numpy
            xs = numpy.arange(width, dtype=numpy.float32)
            ys = numpy.arange(height, dtype=numpy.float32)
            grid_x, grid_y = numpy.meshgrid(xs, ys, indexing='ij')
            if gradient['type'] == 'linear':
                dx = x2 - x1
                dy = y2 - y1
                denominator = dx * dx + dy * dy
                if denominator < 1e-6:
                    ratio = numpy.zeros((width, height), dtype=numpy.float32)
                else:
                    ratio = ((grid_x - x1) * dx + (grid_y - y1) * dy) \
                        / denominator
            else:
                ratio = numpy.sqrt((grid_x - cx) ** 2 +
                                   (grid_y - cy) ** 2) / max(1e-6, radius)
            ratio = numpy.clip(ratio, 0.0, 1.0)
            offsets_array = numpy.array(offsets, dtype=numpy.float32)
            channels = [
                numpy.interp(ratio, offsets_array,
                             numpy.array([color[channel] for color in colors],
                                         dtype=numpy.float32))
                for channel in range(4)]
            result = pygame.Surface((width, height), pygame.SRCALPHA)
            pixels = pygame.surfarray.pixels3d(result)
            pixels[:, :, 0] = channels[0].astype(numpy.uint8)
            pixels[:, :, 1] = channels[1].astype(numpy.uint8)
            pixels[:, :, 2] = channels[2].astype(numpy.uint8)
            alpha = pygame.surfarray.pixels_alpha(result)
            alpha[:, :] = channels[3].astype(numpy.uint8)
            del pixels, alpha
            return result
        except Exception:
            pass

        result = pygame.Surface((width, height), pygame.SRCALPHA)
        if gradient['type'] == 'linear':
            dx = x2 - x1
            dy = y2 - y1
            steps = max(2, int(max(abs(dx), abs(dy), 1)))
            steps = min(256, steps)
            for index in range(steps):
                t = index / float(steps - 1)
                color = sample(t)
                if abs(dx) >= abs(dy):
                    pygame.draw.line(result, color,
                                     (int(x1 + dx * t), 0),
                                     (int(x1 + dx * t), height))
                else:
                    pygame.draw.line(result, color,
                                     (0, int(y1 + dy * t)),
                                     (width, int(y1 + dy * t)))
        else:
            steps = min(64, max(8, int(radius)))
            for index in range(steps, 0, -1):
                t = index / float(steps)
                pygame.draw.circle(result, sample(t),
                                   (int(cx), int(cy)), int(radius * t))
        return result

    def _svg_gradient_fill(self, surface, gradient, kind, geometry, style,
                           matrix):
        bbox = self._svg_bbox(kind, geometry)
        if bbox is None:
            return
        paint = self._svg_gradient_surface(gradient, bbox, matrix)
        if paint is None:
            color = self._svg_gradient_average(gradient)
            if color is not None:
                self._svg_paint(
                    surface, kind, geometry,
                    self._svg_apply_opacity(color, style['fill_opacity'] *
                                            style['opacity']))
            return
        mask = pygame.Surface(paint.get_size(), pygame.SRCALPHA)
        self._svg_paint(mask, kind, geometry, (255, 255, 255, 255), 0,
                        offset=(-bbox.x, -bbox.y))
        paint.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        alpha = int(round(255 * style['fill_opacity'] * style['opacity']))
        if alpha < 255:
            paint.fill((255, 255, 255, max(0, alpha)),
                       special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(paint, (bbox.x, bbox.y))

    def _svg_draw_record(self, surface, record, gradients):
        tag, attrs, style, matrix, inner = record
        if tag == 'image':
            self._svg_draw_image(surface, attrs, style, matrix)
            return
        if tag == 'text':
            self._svg_draw_text(surface, attrs, style, matrix, inner,
                                gradients)
            return
        geometry = self._svg_geometry(tag, attrs, matrix)
        if geometry is None:
            return
        kind, points = geometry
        fill = self._svg_fill_paint(style['fill'], gradients)
        if isinstance(fill, dict):
            self._svg_gradient_fill(surface, fill, kind, points, style, matrix)
        elif fill is not None:
            color = self._svg_apply_opacity(
                fill, style['fill_opacity'] * style['opacity'])
            if color[3] > 0:
                self._svg_paint(surface, kind, points, color)
        stroke = self._svg_fill_paint(style['stroke'], gradients)
        if isinstance(stroke, dict):
            stroke = self._svg_gradient_average(stroke)
        if stroke is not None:
            color = self._svg_apply_opacity(
                stroke, style['stroke_opacity'] * style['opacity'])
            width = _sc_num(style['stroke_width']) * \
                self._svg_matrix_scale(matrix)
            if color[3] > 0:
                self._svg_paint(surface, kind, points, color,
                                max(1, int(round(width))))

    def _svg_draw_image(self, surface, attrs, style, matrix):
        href = attrs.get('__href') if isinstance(attrs, dict) else None
        if not href:
            href = _svg_get(attrs, 'xlink:href') or _svg_get(attrs, 'href')
        if not href.startswith('data:image') or 'base64,' not in href:
            return
        try:
            key = (len(href), hash(href))
            image = self._svg_bitmap_cache.get(key)
            if image is None:
                import base64
                raw = base64.b64decode(href.split('base64,', 1)[1])
                image = pygame.image.load(io.BytesIO(raw))
                if len(self._svg_bitmap_cache) >= 12:
                    self._svg_bitmap_cache.clear()
                self._svg_bitmap_cache[key] = image
        except Exception:
            return
        width = _sc_num(_svg_get(attrs, 'width', '0'))
        height = _sc_num(_svg_get(attrs, 'height', '0'))
        if width <= 0 or height <= 0:
            width, height = float(image.get_width()), float(image.get_height())
        scale = math.hypot(matrix[0], matrix[1]) or 1.0
        angle = -math.degrees(math.atan2(matrix[1], matrix[0]))
        if abs(angle) < 1e-6:
            # 纯缩放（绝大多数内嵌位图）用 smoothscale，比 rotozoom 快很多
            drawn = pygame.transform.smoothscale(
                image, (max(1, int(round(image.get_width() * scale))),
                        max(1, int(round(image.get_height() * scale)))))
        else:
            drawn = pygame.transform.rotozoom(image, angle, scale)
        offset_x = _sc_num(_svg_get(attrs, 'x', '0'))
        offset_y = _sc_num(_svg_get(attrs, 'y', '0'))
        center_x, center_y = _svg_point(matrix, offset_x + width / 2,
                                        offset_y + height / 2)
        alpha = int(round(255 * style['opacity']))
        if alpha < 255:
            drawn.set_alpha(max(0, alpha))
        surface.blit(drawn, drawn.get_rect(
            center=(int(center_x), int(center_y))))

    def _svg_draw_text(self, surface, attrs, style, matrix, inner, gradients):
        fill = self._svg_fill_paint(style['fill'], gradients)
        if isinstance(fill, dict):
            fill = self._svg_gradient_average(fill)
        if fill is None:
            return
        size = _sc_num(style['font_size']) or 16
        scale = abs(matrix[0]) or 1.0
        font_size = max(1, int(round(size * scale)))
        font = self._font(font_size)
        contents = re.findall(r'<tspan[^>]*>(.*?)</tspan>', inner, re.S)
        label = contents[0] if contents else inner
        label = re.sub(r'<[^>]+>', '', label).strip()
        if not label:
            return
        rendered = font.render(label, True, fill[:3])
        alpha = int(round(fill[3] * style['fill_opacity'] * style['opacity']))
        if alpha < 255:
            rendered.set_alpha(max(0, alpha))
        x, y = matrix[4], matrix[5]
        anchor = _svg_get(attrs, 'text-anchor')
        if anchor == 'middle':
            x -= rendered.get_width() / 2
        elif anchor == 'end':
            x -= rendered.get_width()
        surface.blit(rendered, (int(x), int(y - font.get_ascent())))

    def _render_svg(self, path, image_scale=1.0):
        """没有 cairosvg 时的 SVG 渲染：text/常见形状/path/渐变/透明度

        image_scale > 1 时按更高分辨率栅格化，窗口放大后仍然清晰。
        单次扫描标签并按 <g> 样式栈求值，避免逐元素重复解析整段 XML。
        """
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
        texture_scale = max(1.0, float(image_scale))
        texture_width = max(1, int(round(width * texture_scale)))
        texture_height = max(1, int(round(height * texture_scale)))
        surface = pygame.Surface((texture_width, texture_height),
                                 pygame.SRCALPHA)
        scale_matrix = (texture_scale, 0.0, 0.0, texture_scale, 0.0, 0.0)

        # 先把内嵌位图的 base64 换成占位符：标签扫描不需要反复经过几百 KB 的图片数据
        image_hrefs = []
        image_re = re.compile(r'<image\b([^>]*?)/?>', re.S)
        href_re = re.compile(r'(?:xlink:)?href\s*=\s*"([^"]*)"')

        def mask_image(match):
            attrs = match.group(1)
            href_match = href_re.search(attrs)
            if href_match is None:
                image_hrefs.append('')
                return '<image%s>' % attrs
            image_hrefs.append(href_match.group(1))
            return '<image%s>' % (attrs[:href_match.start()] +
                                  attrs[href_match.end():])

        try:
            masked_text = image_re.sub(mask_image, text)
        except Exception:
            masked_text = text

        gradients = self._svg_parse_gradients(masked_text)
        body = re.sub(r'<defs\b.*?</defs>', '', masked_text, flags=re.S)
        body = re.sub(r'<(linearGradient|radialGradient)\b.*?</\1>', '',
                      body, flags=re.S)

        token_re = re.compile(
            r'<(/?)(g|rect|circle|ellipse|line|polygon|polyline|path|'
            r'text|image)\b([^>]*?)(/?)>', re.S)
        style_stack = [self._svg_default_style()]
        matrix_stack = [(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)]
        records = []
        image_index = 0
        position = 0
        while True:
            match = token_re.search(body, position)
            if match is None:
                break
            closing, tag, attrs, self_closing = match.groups()
            position = match.end()
            # 一次解析属性：内嵌位图的 base64 属性可达数百 KB，
            # 逐属性 search 会把整段字符串反复扫描多遍
            attr_map = _svg_parse_attrs(attrs)
            if tag == 'g':
                if closing:
                    if len(style_stack) > 1:
                        style_stack.pop()
                        matrix_stack.pop()
                elif not self_closing:
                    style_stack.append(
                        self._svg_child_style(style_stack[-1], attr_map))
                    matrix_stack.append(_svg_mul(
                        matrix_stack[-1],
                        _svg_transform(_svg_get(attr_map, 'transform') or '')))
                continue
            if closing:
                continue
            style = self._svg_child_style(style_stack[-1], attr_map)
            matrix = _svg_mul(
                scale_matrix,
                _svg_mul(matrix_stack[-1],
                         _svg_transform(_svg_get(attr_map, 'transform') or '')))
            if tag == 'image':
                if image_index < len(image_hrefs):
                    attr_map['__href'] = image_hrefs[image_index]
                image_index += 1
            if tag == 'text':
                end = body.find('</text>', match.end())
                if end < 0:
                    continue
                inner = body[match.end():end]
                position = end + len('</text>')
                records.append(('text', attr_map, style, matrix, inner))
            else:
                records.append((tag, attr_map, style, matrix, ''))

        # 先画形状/位图，再画文本（与 Scratch SVG 的常见层级一致）
        for record in records:
            if record[0] != 'text':
                self._svg_draw_record(surface, record, gradients)
        for record in records:
            if record[0] == 'text':
                self._svg_draw_record(surface, record, gradients)
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
