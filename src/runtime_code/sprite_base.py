# -*- coding: utf-8 -*-
"""Scratch 角色基类模板"""

SPRITE_BASE = r'''class ScratchSprite:
    """Scratch精灵基类"""

    GLOBAL_NAMES = ()
    GLOBAL_NAMES_SET = frozenset()

    def __init__(self):
        self.x = 0
        self.y = 0
        self.direction = 90
        self.visible = True
        self.size = 100
        self.costume = 0
        self.costume_number = 0
        self.costume_name = ''
        self.volume = 100
        self.answer = ''
        self.mouse_x = 0
        self.mouse_y = 0
        self.mouse_down = False
        self.timer = 0
        self.loudness = 0
        self.days_since_2000 = 0
        self.rotation_style = 'all around'
        self._local = threading.local()
        self._global_running = True
        self._clones = []
        self.name = ''
        self.costumes = []
        self.sounds = []
        self._handlers = {}
        self._conditions = []
        self._frame_hats = []
        self._runtime = None
        self._say_text = ''
        self._say_until = None
        self._say_kind = 'say'
        self._is_clone = False
        self._render_x = None
        self._render_y = None
        self._render_direction = None
        self._render_size = None
        self._pen_down = False
        self._pen_alpha = 0.0
        self._pen_hsv = [0.0, 100.0, 100.0]
        self._pen_size = 1.0
        self._pen_last = None
        # 下一段是否需要补起点圆帽（落笔后的第一段）
        self._pen_cap = True
        self._effects = {}
        self._sound_effects = {'pitch': 0.0, 'pan': 0.0}
        # TurboWarp 角色拉伸（百分比）与艺术字状态
        self._stretch_x = 100.0
        self._stretch_y = 100.0
        self._text_state = None
        self.draggable = False

    def __getattr__(self, name):
        if name in GLOBALS:
            return GLOBALS[name]
        raise AttributeError(name)

    def __setattr__(self, name, value):
        # 用 frozenset 做 O(1) 判断，替代逐项扫描GLOBAL_NAMES元组
        if name in type(self).GLOBAL_NAMES_SET:
            GLOBALS[name] = value
        else:
            object.__setattr__(self, name, value)

    def move(self, steps):
        """移动指定步数"""
        steps = _sc_num(steps)
        rad = math.radians(self.direction)
        # Scratch方向: 0=上, 90=右
        self.x += steps * math.sin(rad)
        self.y += steps * math.cos(rad)
        self._apply_fencing()
        self._pen_update()

    def turn_right(self, degrees):
        """右转指定度数"""
        degrees = _sc_num(degrees)
        self.direction = (self.direction + degrees) % 360

    def turn_left(self, degrees):
        """左转指定度数"""
        degrees = _sc_num(degrees)
        self.direction = (self.direction - degrees) % 360
        if self.direction < 0:
            self.direction += 360

    def goto_xy(self, x, y):
        """跳转到指定坐标"""
        self.x = _sc_num(x)
        self.y = _sc_num(y)
        self._apply_fencing()
        self._pen_update()

    def set_x(self, x):
        self.x = _sc_num(x)
        self._apply_fencing()
        self._pen_update()

    def set_y(self, y):
        self.y = _sc_num(y)
        self._apply_fencing()
        self._pen_update()

    def change_x(self, dx):
        self.x += _sc_num(dx)
        self._apply_fencing()
        self._pen_update()

    def change_y(self, dy):
        self.y += _sc_num(dy)
        self._apply_fencing()
        self._pen_update()

    def if_on_edge_bounce(self):
        """碰到边缘反弹"""
        width = self._runtime.stage_width / 2 if self._runtime else 240
        height = self._runtime.stage_height / 2 if self._runtime else 180
        if self.x > width:
            self.x = width
            self.direction = (-self.direction) % 360
        elif self.x < -width:
            self.x = -width
            self.direction = (-self.direction) % 360
        if self.y > height:
            self.y = height
            self.direction = (180 - self.direction) % 360
        elif self.y < -height:
            self.y = -height
            self.direction = (180 - self.direction) % 360
        self.direction = self.direction % 360
        self._pen_update()

    def _clamp_position(self):
        width = self._runtime.stage_width / 2 if self._runtime else 240
        height = self._runtime.stage_height / 2 if self._runtime else 180
        self.x = max(-width, min(width, self.x))
        self.y = max(-height, min(height, self.y))

    def _sprite_bounds(self):
        """当前造型旋转/缩放/拉伸后的半宽、半高（用于舞台边界约束）"""
        text_image = self._text_image()
        if text_image is not None:
            image = text_image[0]
        else:
            image = self._costume_surface()
        if image is None:
            return max(1.0, 20 * abs(_sc_num(self.size)) / 200.0), \
                max(1.0, 20 * abs(_sc_num(self.size)) / 200.0)
        scale = max(1.0, _sc_num(self.size)) / 100.0
        stretch_x = abs(_sc_num(getattr(self, '_stretch_x', 100))) / 100.0
        stretch_y = abs(_sc_num(getattr(self, '_stretch_y', 100))) / 100.0
        width = image.get_width() * scale * stretch_x
        height = image.get_height() * scale * stretch_y
        angle = math.radians(90 - _sc_num(self.direction))
        if self.rotation_style in ('left-right', "don't rotate"):
            angle = 0.0
        cos_value, sin_value = abs(math.cos(angle)), abs(math.sin(angle))
        return ((width * cos_value + height * sin_value) / 2.0,
                (width * sin_value + height * cos_value) / 2.0)

    def _apply_fencing(self):
        """角色不能离开舞台（Scratch 的 Fencing，可用 TurboWarp 高级选项关闭）"""
        if self._runtime is None or not self._runtime.fencing:
            return
        half_w, half_h = self._sprite_bounds()
        stage_w = self._runtime.stage_width
        stage_h = self._runtime.stage_height
        if half_w * 2 > stage_w:
            # 比舞台还宽时居中（与 Scratch 一致）
            self.x = 0
        else:
            limit_x = stage_w / 2 - half_w
            self.x = max(-limit_x, min(limit_x, _sc_num(self.x)))
        if half_h * 2 > stage_h:
            self.y = 0
        else:
            limit_y = stage_h / 2 - half_h
            self.y = max(-limit_y, min(limit_y, _sc_num(self.y)))

    def _pen_update(self):
        """画笔落下时，把移动轨迹画到画布上"""
        runtime = self._runtime
        if runtime is None:
            return
        current = (float(_sc_num(self.x)), float(_sc_num(self.y)))
        if not getattr(self, '_pen_down', False):
            self._pen_last = None
            return
        last = getattr(self, '_pen_last', None)
        if last is not None and last != current:
            hue, saturation, brightness = getattr(self, '_pen_hsv',
                                                    [0.0, 100.0, 100.0])
            alpha = max(0.0, min(100.0, _sc_num(getattr(self, '_pen_alpha', 0))))
            color = runtime.pen_color(hue, saturation, brightness, alpha)
            runtime.pen_draw_segment(
                last, current, color,
                max(1, int(_sc_num(getattr(self, '_pen_size', 1)))),
                getattr(self, '_pen_cap', False))
            self._pen_cap = False
        self._pen_last = current

    def say(self, message):
        """说话（显示对话气泡）"""
        self._say_text = _sc_str(message)
        self._say_until = None
        self._say_kind = 'say'

    def say_for(self, message, secs):
        text = _sc_str(message)
        self._say_text = text
        self._say_kind = 'say'
        duration = _sc_wait_time(secs)
        self._say_until = time.time() + duration
        self._sleep(duration)
        if self._say_text == text:
            self._say_text = ''
            self._say_until = None

    def think(self, message):
        """思考（显示思考气泡）"""
        self._say_text = _sc_str(message)
        self._say_until = None
        self._say_kind = 'think'

    def think_for(self, message, secs):
        text = _sc_str(message)
        self._say_text = text
        self._say_kind = 'think'
        duration = _sc_wait_time(secs)
        self._say_until = time.time() + duration
        self._sleep(duration)
        if self._say_text == text:
            self._say_text = ''
            self._say_until = None

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def switch_costume(self, costume):
        # 与 scratch-vm 的 _setCostume/setCostume 保持一致：
        # - 数字类型一律当作1起的造型编号（四舍五入，越界循环）
        # - 字符串先按名字匹配，再处理 next/previous costume，最后才尝试转数字
        names = [item.get('name', '') for item in self.costumes]
        count = len(names)
        if not count:
            return
        if isinstance(costume, (int, float)) and not isinstance(costume, bool):
            number = float(costume)
            if math.isnan(number) or math.isinf(number):
                index = 0
            else:
                index = _sc_round(number) - 1
        else:
            value = _sc_str(costume)
            if value in names:
                index = names.index(value)
            elif value == 'next costume':
                index = int(_sc_num(self.costume_number))
            elif value == 'previous costume':
                index = int(_sc_num(self.costume_number)) - 2
            elif _sc_is_white(value):
                return
            else:
                number = _sc_number_or_nan(value)
                if math.isnan(number) or math.isinf(number):
                    return
                index = _sc_round(number) - 1
        index = int(index) % count
        self.costume_number = index + 1
        self.costume_name = names[index]

    def next_costume(self):
        count = len(self.costumes)
        if count:
            index = (self.costume_number) % count
            self.costume_number = index + 1
            self.costume_name = self.costumes[index].get('name', '')

    def change_size(self, change):
        self.size += _sc_num(change)
        self._apply_fencing()

    def set_size(self, size):
        self.size = _sc_num(size)
        self._apply_fencing()

    def change_effect(self, effect, change):
        key = str(effect).lower()
        self._effects[key] = _sc_clamp_effect(
            key, _sc_num(self._effects.get(key, 0)) + _sc_num(change))

    def set_effect(self, effect, value):
        key = str(effect).lower()
        self._effects[key] = _sc_clamp_effect(key, _sc_num(value))

    def clear_effects(self):
        self._effects = {}

    def play_sound(self, sound, wait=False):
        duration = 0
        if self._runtime is not None:
            duration = self._runtime.play_sound(self, _sc_str(sound))
        if wait and duration:
            self._sleep(duration)

    def stop_all_sounds(self):
        if self._runtime is not None:
            self._runtime.stop_sounds()

    def change_volume(self, change):
        self.volume = _sc_add(self.volume, change)
        if self._runtime is None or self._runtime.misc_limits:
            self.volume = max(0, min(100, self.volume))

    def set_volume(self, volume):
        self.volume = _sc_num(volume)
        if self._runtime is None or self._runtime.misc_limits:
            self.volume = max(0, min(100, self.volume))

    def wait(self, seconds):
        """等待指定秒数"""
        self._sleep(seconds)

    def wait_until(self, condition_func):
        """等待直到条件为真"""
        while self._running and not condition_func():
            self._yield_frame()

    def stop(self, option='all'):
        option = _sc_str(option)
        if option == 'all':
            if self._runtime is not None:
                self._runtime.stop_all_scripts()
            raise StopIteration('stop all')
        if option.startswith('other scripts'):
            if self._runtime is not None:
                self._runtime.stop_other_scripts(self)
            return
        # 停止这个脚本：在自制积木内相当于return到调用处
        if getattr(self._local, 'depth', 0) > 0:
            raise _ProcedureReturn()
        context = getattr(self._local, 'context', None)
        if context is not None:
            context.running = False
        else:
            self._global_running = False
        raise StopIteration('stop this script')

    def create_clone_of(self, target):
        target = _sc_str(target)
        if self._runtime is None:
            return
        clone_source = self if target in ('_myself_', self.name) \
            else self._runtime.find_sprite(target)
        if clone_source is not None:
            clone_source._make_clone()

    def delete_this_clone(self):
        if not self._is_clone:
            return
        if self._runtime is not None:
            self._runtime.remove_sprite(self)
        raise StopIteration('Clone deleted')

    def broadcast(self, message):
        if self._runtime is not None:
            self._runtime.broadcast(message)

    def broadcast_and_wait(self, message):
        if self._runtime is not None:
            self._turn_release()
            try:
                self._runtime.broadcast_and_wait(
                    message, getattr(self._local, 'context', None))
            finally:
                self._turn_acquire()

    def touching(self, object):
        if self._runtime is None:
            return False
        return self._runtime.touching(self, _sc_str(object))

    def distance_to(self, object):
        if self._runtime is None:
            return 0
        return self._runtime.distance_to(self, _sc_str(object))

    def key_pressed(self, key):
        if self._runtime is None:
            return False
        key = _sc_str(key)
        if key == 'any':
            return bool(self._runtime.keys)
        return key in self._runtime.keys

    def ask_and_wait(self, question):
        question = _sc_str(question)
        if self._runtime is None:
            self.answer = input(question)
            return
        self._turn_release()
        try:
            context = getattr(self._local, 'context', None)
            self.answer = self._runtime.ask(question, context)
            self._runtime.answer = self.answer
        finally:
            self._turn_acquire()

    def reset_timer(self):
        if self._runtime is not None:
            self._runtime.reset_timer()
        self.timer = 0

    def current_time(self, unit):
        """当前日期/时间（对应Scratch的“当前时间”积木）"""
        t = time.localtime()
        values = {
            'YEAR': t.tm_year,
            'MONTH': t.tm_mon,
            'DATE': t.tm_mday,
            'DAYOFWEEK': ((t.tm_wday + 1) % 7) + 1,
            'HOUR': t.tm_hour,
            'MINUTE': t.tm_min,
            'SECOND': t.tm_sec,
        }
        return values.get(unit, 0)

    def goto_random(self):
        """移动到随机位置"""
        width = self._runtime.stage_width if self._runtime else 480
        height = self._runtime.stage_height if self._runtime else 360
        self.x = random.randint(-width // 2, width // 2)
        self.y = random.randint(-height // 2, height // 2)
        self._apply_fencing()
        self._pen_update()

    def glide_to(self, secs, x, y):
        """在指定秒数内滑行到目标坐标"""
        secs = _sc_wait_time(secs)
        x = _sc_num(x)
        y = _sc_num(y)
        start_x, start_y = self.x, self.y
        steps = 20
        for i in range(1, steps + 1):
            self._sleep(secs / steps)
            self.x = start_x + (x - start_x) * i / steps
            self.y = start_y + (y - start_y) * i / steps
            self._apply_fencing()
            self._pen_update()

    def show_variable(self, name):
        if self._runtime is None:
            return
        text = _sc_str(name)
        local = _sc_ident(text, 'var') in self.__dict__
        self._runtime.show_monitor('var', text, self.name if local else None, True)

    def hide_variable(self, name):
        if self._runtime is None:
            return
        text = _sc_str(name)
        local = _sc_ident(text, 'var') in self.__dict__
        self._runtime.show_monitor('var', text, self.name if local else None, False)

    def show_list(self, name):
        if self._runtime is None:
            return
        text = _sc_str(name)
        local = _sc_ident(text, 'lst') in self.__dict__
        self._runtime.show_monitor('list', text, self.name if local else None, True)

    def hide_list(self, name):
        if self._runtime is None:
            return
        text = _sc_str(name)
        local = _sc_ident(text, 'lst') in self.__dict__
        self._runtime.show_monitor('list', text, self.name if local else None, False)

    def list_item_number(self, items, item):
        """返回item在列表中的位置(1起始)，不存在返回0"""
        return _sc_list_item_number(items, item)

    @property
    def _running(self):
        context = getattr(self._local, 'context', None)
        return context.running if context is not None else self._global_running

    @_running.setter
    def _running(self, value):
        context = getattr(self._local, 'context', None)
        if context is not None:
            context.running = value
        else:
            self._global_running = value

    def _enter_procedure(self, warp=False):
        self._local.depth = getattr(self._local, 'depth', 0) + 1
        if warp:
            self._local.warp_depth = getattr(self._local, 'warp_depth', 0) + 1

    def _leave_procedure(self, warp=False):
        self._local.depth = max(0, getattr(self._local, 'depth', 0) - 1)
        if warp:
            self._local.warp_depth = max(0, getattr(self._local, 'warp_depth', 0) - 1)
            if self._local.warp_depth == 0:
                self._local.warp_start = None

    def _register(self, event, func):
        handlers = self._handlers.setdefault(event, [])
        if func not in handlers:
            handlers.append(func)

    def _register_greater_than(self, menu, threshold, func):
        """注册“当计时器/响度 > 值”帽子事件，阈值为可重复求值的函数"""
        self._conditions.append([menu, threshold, func, False])

    def _register_extension_hat(self, namespace, opcode, inputs, func):
        """注册扩展帽子事件（More Events / Clones+）

        inputs 里的值都是无参函数，每帧重新求值，确保读取的是当前变量。
        """
        key = str(opcode).lower()
        if key.endswith('whenstopclicked'):
            # 停止按钮是显式事件，直接走普通事件表
            self._register('stop_clicked', func)
            return
        if key.endswith('beforesave') or key.endswith('aftersave'):
            # 生成脚本没有“保存项目”动作，这两个帽子永远不会触发
            return
        self._frame_hats.append({
            'namespace': namespace,
            'opcode': opcode,
            'inputs': dict(inputs or {}),
            'func': func,
            'state': None,
            'thread': None,
        })

    def _turn_acquire(self):
        """获取脚本执行权（同一时刻只让一个脚本执行，模拟Scratch单线程调度）"""
        runtime = self._runtime
        if runtime is not None and not getattr(self._local, 'turn_owned', False):
            runtime.turn_lock.acquire()
            self._local.turn_owned = True

    def _turn_release(self):
        runtime = self._runtime
        if runtime is not None and getattr(self._local, 'turn_owned', False):
            self._local.turn_owned = False
            runtime.turn_lock.release()

    def _sleep(self, seconds):
        """等待期间让出执行权，避免阻塞其他脚本"""
        seconds = _sc_wait_time(seconds)
        if seconds <= 0:
            return
        self._turn_release()
        try:
            time.sleep(seconds)
        finally:
            self._turn_acquire()

    def _yield_frame(self):
        """让当前脚本等待到下一帧；warp/turbo模式下不等待"""
        if self._runtime is None:
            time.sleep(0.01)
            return
        context = getattr(self._local, 'context', None)
        warp = getattr(self._local, 'warp_depth', 0) > 0 or getattr(self._runtime, 'turbo', False)
        if not warp:
            self._turn_release()
            self._runtime.wait_frame(context)
            self._turn_acquire()
            return
        limit = getattr(self._runtime, 'warp_timer', 0.5)
        if limit:
            now = time.time()
            start = getattr(self._local, 'warp_start', None)
            if start is None:
                self._local.warp_start = now
            elif now - start >= limit:
                self._local.warp_start = now
                self._turn_release()
                self._runtime.wait_frame(context)
                self._turn_acquire()

    def _update_say(self):
        if self._say_until is not None and time.time() >= self._say_until:
            self._say_text = ''
            self._say_until = None

    def _contains_point(self, x, y):
        rect = getattr(self, '_screen_rect', None)
        if rect is None:
            return False
        width = self._runtime.stage_width // 2 if self._runtime else 240
        height = self._runtime.stage_height // 2 if self._runtime else 180
        return rect.collidepoint(width + x, height - y)

    def _costume_info(self):
        if not self.costumes:
            return {}
        index = max(0, int(_sc_num(self.costume_number)) - 1) if self.costume_number else 0
        return self.costumes[index % len(self.costumes)]

    def _costume_surface(self):
        if self._runtime is None or not self.costumes:
            return None
        costume = self._costume_info()
        name = costume.get('md5ext') or costume.get('name')
        return self._runtime.get_sprite_image(name)

    def _placeholder_color(self):
        seed = sum(ord(ch) for ch in self.name) if self.name else 0
        return (70 + seed * 37 % 150, 70 + seed * 67 % 150, 70 + seed * 97 % 150)

    def _color_effect_image(self, image, effect):
        """按(造型Surface, 特效值)缓存颜色特效结果，避免每帧做HSV转换"""
        cache = getattr(self, '_color_cache', None)
        if cache is None:
            cache = self._color_cache = {}
        key = (id(image), round(_sc_num(effect), 3))
        surface = cache.get(key)
        if surface is None:
            surface = self._runtime.apply_color_effect(image, effect)
            if len(cache) >= 8:
                cache.clear()
            cache[key] = surface
        return surface

    def _brightness_image(self, image, brightness):
        """按(造型Surface, 亮度值)缓存亮度特效结果，避免每帧fill整张图"""
        cache = getattr(self, '_brightness_cache', None)
        if cache is None:
            cache = self._brightness_cache = {}
        delta = int(255 * max(-100.0, min(100.0, _sc_num(brightness))) / 100.0)
        if delta == 0:
            return image
        key = (id(image), delta)
        surface = cache.get(key)
        if surface is None:
            surface = image.copy()
            if delta > 0:
                surface.fill((delta, delta, delta, 0),
                             special_flags=pygame.BLEND_RGB_ADD)
            else:
                surface.fill((-delta, -delta, -delta, 0),
                             special_flags=pygame.BLEND_RGB_SUB)
            if len(cache) >= 8:
                cache.clear()
            cache[key] = surface
        return surface

    def _distortion_image(self, image):
        """鱼眼/旋涡/像素化/马赛克：按(造型Surface, 特效值)缓存结果"""
        effects = self._effects
        mosaic = _sc_num(effects.get('mosaic', 0))
        pixelate = _sc_num(effects.get('pixelate', 0))
        whirl = _sc_num(effects.get('whirl', 0))
        fisheye = _sc_num(effects.get('fisheye', 0))
        if abs(mosaic) < 1e-3 and abs(pixelate) < 1e-3 \
                and abs(whirl) < 1e-3 and abs(fisheye) < 1e-3:
            return image
        cache = getattr(self, '_distortion_cache', None)
        if cache is None:
            cache = self._distortion_cache = {}
        key = (id(image), round(mosaic, 2), round(pixelate, 2),
               round(whirl, 2), round(fisheye, 2))
        surface = cache.get(key)
        if surface is None:
            surface = self._distort_surface(
                image, mosaic, pixelate, whirl, fisheye)
            if len(cache) >= 6:
                cache.clear()
            cache[key] = surface
        return surface

    def _distort_surface(self, image, mosaic, pixelate, whirl, fisheye):
        """复刻 scratch-render 的 EffectTransform：马赛克→像素化→旋涡→鱼眼"""
        width, height = image.get_size()
        if width <= 0 or height <= 0:
            return image
        try:
            import numpy
        except ImportError:
            return self._distort_fallback(image, mosaic, pixelate)
        try:
            xs = (numpy.arange(width, dtype=numpy.float32) + 0.5) / width
            ys = (numpy.arange(height, dtype=numpy.float32) + 0.5) / height
            u = numpy.repeat(xs[:, None], height, axis=1)
            v = numpy.repeat(ys[None, :], width, axis=0)

            if abs(mosaic) > 1e-3:
                tiles = max(1.0, min(
                    float(round((abs(mosaic) + 10.0) / 10.0)), 512.0))
                u = numpy.mod(u * tiles, 1.0)
                v = numpy.mod(v * tiles, 1.0)

            if abs(pixelate) > 1e-3:
                block = max(abs(pixelate) / 10.0, 1e-3)
                columns = max(1.0, width / block)
                rows = max(1.0, height / block)
                u = (numpy.floor(u * columns) + 0.5) / columns
                v = (numpy.floor(v * rows) + 0.5) / rows

            if abs(whirl) > 1e-3:
                angle = -whirl * math.pi / 180.0
                offset_x = u - 0.5
                offset_y = v - 0.5
                radius = numpy.sqrt(offset_x * offset_x + offset_y * offset_y)
                factor = numpy.maximum(1.0 - radius / 0.5, 0.0)
                actual = angle * factor * factor
                cos_value = numpy.cos(actual)
                sin_value = numpy.sin(actual)
                u = cos_value * offset_x + sin_value * offset_y + 0.5
                v = -sin_value * offset_x + cos_value * offset_y + 0.5

            if abs(fisheye) > 1e-3:
                power = max(0.0, (fisheye + 100.0) / 100.0)
                vec_x = (u - 0.5) / 0.5
                vec_y = (v - 0.5) / 0.5
                length = numpy.sqrt(vec_x * vec_x + vec_y * vec_y)
                safe = numpy.where(length < 1e-6, 1.0, length)
                r = numpy.power(numpy.minimum(length, 1.0), power) \
                    * numpy.maximum(1.0, length)
                u = 0.5 + r * (vec_x / safe) * 0.5
                v = 0.5 + r * (vec_y / safe) * 0.5

            x_index = numpy.clip(
                numpy.floor(u * width).astype(numpy.int32), 0, width - 1)
            y_index = numpy.clip(
                numpy.floor(v * height).astype(numpy.int32), 0, height - 1)
            source = pygame.surfarray.pixels3d(image)
            source_alpha = pygame.surfarray.pixels_alpha(image)
            sampled = source[x_index, y_index]
            sampled_alpha = source_alpha[x_index, y_index]
            result = pygame.Surface((width, height), pygame.SRCALPHA)
            target = pygame.surfarray.pixels3d(result)
            target[:, :, :] = sampled
            target_alpha = pygame.surfarray.pixels_alpha(result)
            target_alpha[:, :] = sampled_alpha
            del source, source_alpha, target, target_alpha
            return result
        except Exception:
            return self._distort_fallback(image, mosaic, pixelate)

    def _distort_fallback(self, image, mosaic, pixelate):
        """没有 numpy 时用 pygame 缩放/平铺近似像素化与马赛克"""
        try:
            width, height = image.get_size()
            if abs(mosaic) > 0.5:
                tiles = int(max(1, min(
                    round((abs(mosaic) + 10.0) / 10.0), 128)))
                if tiles > 1:
                    tile = pygame.transform.scale(
                        image, (max(1, width // tiles),
                                max(1, height // tiles)))
                    result = pygame.Surface((width, height), pygame.SRCALPHA)
                    tile_width, tile_height = tile.get_size()
                    for y in range(0, height, tile_height):
                        for x in range(0, width, tile_width):
                            result.blit(tile, (x, y))
                    return result
            if abs(pixelate) > 0.5:
                block = max(1, int(abs(pixelate) / 10.0))
                small = pygame.transform.scale(
                    image, (max(1, width // block),
                            max(1, height // block)))
                return pygame.transform.scale(small, (width, height))
        except Exception:
            pass
        return image

    def _rendered_image(self):
        """当前外观（含颜色/亮度/形状特效、旋转、缩放、旋转中心）

        返回 (surface, rect, x, y, scale, direction)；没有造型时 surface 为 None。
        图章（stamp）复用同一份结果，保证图章与画面一致。
        """
        text_image = self._text_image()
        if text_image is not None:
            image, center_x, center_y = text_image
        else:
            image = self._costume_surface()
            center_x = center_y = None
        runtime = self._runtime
        use_interp = runtime is not None and runtime.interpolation and getattr(self, '_render_x', None) is not None
        draw_x = self._render_x if use_interp else _sc_num(self.x)
        draw_y = self._render_y if use_interp else _sc_num(self.y)
        draw_direction = self._render_direction if use_interp else _sc_num(self.direction)
        draw_size = self._render_size if use_interp else _sc_num(self.size)
        stage_width = runtime.stage_width if runtime else 480
        stage_height = runtime.stage_height if runtime else 360
        scale = max(1.0, draw_size) / 100.0
        x = int(stage_width / 2 + draw_x)
        y = int(stage_height / 2 - draw_y)
        if image is None:
            return None, None, x, y, scale, draw_direction
        angle = 90 - draw_direction
        if self.rotation_style in ('left-right', "don't rotate"):
            angle = 0
        color_effect = _sc_num(self._effects.get('color', 0))
        brightness = _sc_num(self._effects.get('brightness', 0))
        ghost = max(0.0, min(100.0, _sc_num(self._effects.get('ghost', 0))))
        # 颜色/亮度特效很耗CPU，按(造型Surface, 特效值)缓存；特效值不变时直接复用
        base = image
        if color_effect and runtime is not None:
            base = self._color_effect_image(image, color_effect)
        if brightness and runtime is not None:
            base = self._brightness_image(base, brightness)
        # 鱼眼/旋涡/像素化/马赛克作用在造型上，再参与旋转与缩放
        if runtime is not None:
            base = self._distortion_image(base)
        # TurboWarp 角色拉伸：在角色自身坐标轴上非等比缩放，再旋转
        stretch_x = _sc_num(getattr(self, '_stretch_x', 100)) / 100.0
        stretch_y = _sc_num(getattr(self, '_stretch_y', 100)) / 100.0
        if stretch_x != 1.0 or stretch_y != 1.0:
            base = pygame.transform.scale(
                base, (max(1, int(base.get_width() * stretch_x)),
                       max(1, int(base.get_height() * stretch_y))))
        surface_width = base.get_width()
        surface_height = base.get_height()
        # 无旋转/无缩放时直接复用缓存的Surface，避免每帧rotozoom拷贝
        if angle == 0 and scale == 1.0:
            transformed = base
            fresh = False
        else:
            transformed = pygame.transform.rotozoom(base, angle, scale)
            fresh = True
        if self.rotation_style == 'left-right' and math.cos(math.radians(draw_direction)) < 0:
            transformed = pygame.transform.flip(transformed, True, False)
            fresh = True
        # 幽灵特效需要修改Surface，不能污染缓存
        if ghost > 0:
            if not fresh:
                transformed = transformed.copy()
            transformed.set_alpha(int(255 * (1 - ghost / 100.0)))
        rect = transformed.get_rect(center=(x, y))
        if center_x is None:
            info = self._costume_info()
            center_x = info.get('rotationCenterX')
            center_y = info.get('rotationCenterY')
            center_x = (surface_width / 2 if center_x is None
                        else _sc_num(center_x) * stretch_x)
            center_y = (surface_height / 2 if center_y is None
                        else _sc_num(center_y) * stretch_y)
        else:
            center_x *= stretch_x
            center_y *= stretch_y
        if angle == 0:
            # Scratch的position对应旋转中心，旋转中心坐标以图片左上角为原点(y向下)
            rect.center = (x - int((center_x - surface_width / 2) * scale),
                           y - int((center_y - surface_height / 2) * scale))
        return transformed, rect, x, y, scale, draw_direction

    def _draw(self, screen, font):
        transformed, rect, x, y, scale, direction = self._rendered_image()
        if transformed is not None:
            screen.blit(transformed, rect)
        else:
            radius = max(6, int(20 * scale))
            pygame.draw.circle(screen, self._placeholder_color(), (x, y), radius)
            end = (x + int(math.sin(math.radians(direction)) * radius),
                   y - int(math.cos(math.radians(direction)) * radius))
            pygame.draw.line(screen, (40, 40, 40), (x, y), end, 2)
            rect = pygame.Rect(x - radius, y - radius, radius * 2, radius * 2)
        self._screen_rect = rect
        self._draw_bubble(screen, font)

    def _draw_bubble(self, screen, font):
        text = self._say_text
        if not text:
            return
        chunk = 16
        lines = [text[i:i + chunk] for i in range(0, len(text), chunk)] or ['']
        width = max(font.size(line)[0] for line in lines) + 12
        height = len(lines) * 15 + 8
        rect = getattr(self, '_screen_rect', pygame.Rect(220, 160, 40, 40))
        stage_width = self._runtime.stage_width if self._runtime else 480
        x = max(2, min(stage_width - width - 2, rect.centerx - width // 2))
        y = max(2, rect.top - height - 8)
        bubble = pygame.Rect(x, y, width, height)
        pygame.draw.rect(screen, (255, 255, 255), bubble, border_radius=6)
        pygame.draw.rect(screen, (120, 120, 120), bubble, 1, border_radius=6)
        for index, line in enumerate(lines):
            surface = font.render(line, True, (30, 30, 30))
            screen.blit(surface, (x + 6, y + 4 + index * 15))

    # ===================== 艺术字（Animated Text） =====================

    def _text_ensure(self):
        """取得（必要时创建）艺术字状态，默认值与扩展一致"""
        if getattr(self, '_text_state', None) is None:
            stage_width = self._runtime.stage_width if self._runtime else 480
            self._text_state = {
                'text': '',
                'font': 'Handwriting',
                'color': '#575e75',
                'width': float(stage_width),
                'align': 'center',
                'outline_width': 0.0,
                'outline_color': '#000000',
                'animate': None,
                'animate_start': 0.0,
                'rainbow_duration': 2.0,
                'zoom_duration': 0.5,
                'shake_duration': 0.5,
                'shake_intensity': 100.0,
                'type_delay': 1.0 / 15.0,
            }
        return self._text_state

    def _text_set(self, text):
        state = self._text_ensure()
        state['text'] = _sc_str(text)
        state['animate'] = None

    def _text_clear(self):
        self._text_state = None

    def _text_add_line(self, text):
        state = self._text_ensure()
        existing = state.get('text', '')
        state['text'] = (existing + '\n' if existing else '') + _sc_str(text)
        state['animate'] = None

    def _text_set_font(self, font):
        font = _sc_str(font)
        if font.lower() == 'random':
            fonts = ['Sans Serif', 'Serif', 'Handwriting', 'Marker',
                     'Curly', 'Pixel', 'Scratch']
            current = self._text_ensure().get('font')
            options = [item for item in fonts if item != current] or fonts
            font = random.choice(options)
        self._text_ensure()['font'] = font

    def _text_set_color(self, color):
        self._text_ensure()['color'] = _sc_str(color)

    def _text_set_width(self, width, align=None):
        state = self._text_ensure()
        state['width'] = max(1.0, _sc_num(width))
        if align is not None:
            self._text_set_align(align)

    def _text_set_align(self, align):
        align = _sc_str(align).lower()
        if align not in ('left', 'center', 'right'):
            align = 'left'
        self._text_ensure()['align'] = align

    def _text_set_outline_width(self, width):
        self._text_ensure()['outline_width'] = max(0.0, _sc_num(width))

    def _text_set_outline_color(self, color):
        self._text_ensure()['outline_color'] = _sc_str(color)

    def _text_animation_duration(self, animation):
        state = self._text_ensure()
        animation = _sc_str(animation).lower()
        if animation == 'rainbow':
            return _sc_num(state.get('rainbow_duration', 2.0))
        if animation == 'zoom':
            return _sc_num(state.get('zoom_duration', 0.5))
        if animation == 'shake':
            return _sc_num(state.get('shake_duration', 0.5))
        if animation == 'type':
            return len(state.get('text', '')) * max(
                0.001, _sc_num(state.get('type_delay', 1.0 / 15.0)))
        return 0.0

    def _text_set_duration(self, animation, seconds):
        state = self._text_ensure()
        key = _sc_str(animation).lower()
        if key in ('rainbow', 'zoom', 'shake'):
            state['%s_duration' % key] = max(0.0, _sc_num(seconds))

    def _text_reset_duration(self, animation):
        defaults = {'rainbow': 2.0, 'zoom': 0.5, 'shake': 0.5}
        key = _sc_str(animation).lower()
        if key in defaults:
            self._text_ensure()['%s_duration' % key] = defaults[key]

    def _text_start_animation(self, animation):
        state = self._text_ensure()
        state['animate'] = _sc_str(animation).lower()
        state['animate_start'] = time.time()
        return self._text_animation_duration(state['animate'])

    def _text_animate(self, animation, text=None):
        state = self._text_ensure()
        if text is not None:
            state['text'] = _sc_str(text)
            state['animate'] = None
        return self._text_start_animation(animation)

    def _text_view(self):
        state = getattr(self, '_text_state', None)
        if not state:
            return None
        text = state.get('text', '')
        animation = state.get('animate')
        now = time.time()
        elapsed = now - state.get('animate_start', now)
        duration = self._text_animation_duration(animation) if animation else 0.0
        progress = 1.0 if duration <= 0 else max(0.0, min(1.0, elapsed / duration))
        displayed = text
        if animation == 'type':
            delay = max(0.001, _sc_num(state.get('type_delay', 1.0 / 15.0)))
            displayed = text[:max(0, int(elapsed / delay))]
        if animation and animation != 'type' and progress >= 1.0:
            # 非打字动画播放完就停在最终画面
            state['animate'] = None
            animation = None
        return {'state': state, 'text': text, 'displayed': displayed,
                'animation': animation, 'progress': progress,
                'duration': duration, 'elapsed': elapsed, 'now': now}

    def _text_active(self):
        state = getattr(self, '_text_state', None)
        return bool(state and state.get('text'))

    def _text_displayed(self):
        view = self._text_view()
        return view['displayed'] if view else ''

    def _text_is_animating(self):
        view = self._text_view()
        return bool(view and view['animation'] and view['progress'] < 1.0)

    def _text_count_lines(self, with_wrap):
        state = self._text_ensure()
        text = state.get('text', '')
        if not with_wrap:
            return len(text.split('\n')) if text else 0
        font = self._text_font(state.get('font'), 24)
        return len(self._text_wrap_lines(font, text, _sc_num(state.get('width', 480))))

    def _text_attribute(self, attribute):
        state = self._text_ensure()
        key = _sc_str(attribute).lower()
        if key == 'font':
            return state.get('font', 'Handwriting')
        if key == 'color':
            return state.get('color', '#575e75')
        if key == 'width':
            return state.get('width', 0)
        if key == 'outline color':
            return state.get('outline_color', '#000000')
        if key == 'outline width':
            return state.get('outline_width', 0)
        if key == 'alignment':
            return state.get('align', 'center')
        return ''

    def _text_font(self, family, size):
        names = {
            'sans serif': 'Arial,DejaVu Sans',
            'serif': 'Times New Roman,DejaVu Serif',
            'handwriting': 'Comic Sans MS,Segoe Script,DejaVu Sans',
            'marker': 'Comic Sans MS,Arial',
            'curly': 'Segoe Script,Comic Sans MS',
            'pixel': 'Courier New,DejaVu Sans Mono',
            'scratch': 'Verdana,Arial',
        }.get(_sc_str(family).lower(), 'Arial,DejaVu Sans')
        size = max(1, int(round(_sc_num(size))))
        cache = None
        if self._runtime is not None:
            cache = self._runtime._text_font_cache
        key = (names, size)
        if cache is not None and key in cache:
            return cache[key]
        try:
            font = pygame.font.SysFont(names, size)
        except Exception:
            font = pygame.font.Font(None, size)
        if cache is not None:
            cache[key] = font
        return font

    @staticmethod
    def _text_tokens(paragraph):
        """把段落切成可换行的单元：西文按单词，中日韩按单字"""
        tokens = []
        word = ''
        for char in paragraph:
            if char == ' ':
                if word:
                    tokens.append(word)
                    word = ''
                tokens.append(' ')
            elif ord(char) > 0x2E7F:
                if word:
                    tokens.append(word)
                    word = ''
                tokens.append(char)
            else:
                word += char
        if word:
            tokens.append(word)
        return tokens

    def _text_wrap_lines(self, font, text, width):
        lines = []
        for paragraph in _sc_str(text).split('\n'):
            if not paragraph:
                lines.append('')
                continue
            current = ''
            for token in self._text_tokens(paragraph):
                candidate = current + token
                if current and font.size(candidate)[0] > width:
                    lines.append(current.rstrip())
                    current = '' if token == ' ' else token
                else:
                    current = candidate
            lines.append(current.rstrip())
        return lines

    def _text_image(self):
        """把当前艺术字渲染成 Surface，返回 (surface, 旋转中心x, 旋转中心y)"""
        view = self._text_view()
        if view is None or not view['displayed']:
            return None
        state = view['state']
        animation = view['animation']
        font_size = 24.0
        if animation == 'zoom':
            font_size = max(1.0, 24.0 * max(0.02, view['progress']))
        font = self._text_font(state.get('font'), font_size)
        width = max(1.0, _sc_num(state.get('width', 480)))
        outline = max(0.0, _sc_num(state.get('outline_width', 0)))
        line_height = font_size * 8.0 / 7.0
        padding = font_size / 7.0
        lines = self._text_wrap_lines(font, view['displayed'], width)
        surface_width = max(1, int(width + 2 * outline) + 2)
        surface_height = max(1, int(len(lines) * line_height + 2 * padding
                                    + 2 * outline) + 2)
        surface = pygame.Surface((surface_width, surface_height), pygame.SRCALPHA)
        color = _ext_color(state.get('color', '#575e75'))
        outline_color = _ext_color(state.get('outline_color', '#000000'))
        align = state.get('align', 'center')
        for index, line in enumerate(lines):
            if not line:
                continue
            line_width = font.size(line)[0]
            if align == 'left':
                x = outline + 1
            elif align == 'right':
                x = width - line_width + outline + 1
            else:
                x = (width - line_width) / 2.0 + outline + 1
            y = padding + index * line_height + outline
            if outline > 0:
                outline_surface = font.render(line, True, outline_color)
                for dx, dy in ((-1, -1), (0, -1), (1, -1), (-1, 0),
                               (1, 0), (-1, 1), (0, 1), (1, 1)):
                    surface.blit(outline_surface, (x + dx * outline,
                                                   y + dy * outline))
            if animation == 'rainbow':
                cursor = x
                offset = (view['now'] - state['animate_start']) % 2.0 / 2.0
                for char in line:
                    hue = ((cursor - x) / max(1.0, width) + offset) % 1.0
                    glyph = font.render(
                        char, True, _hsv_to_rgb(hue * 100.0, 80.0, 100.0))
                    surface.blit(glyph, (cursor, y))
                    cursor += glyph.get_width()
            else:
                surface.blit(font.render(line, True, color), (x, y))
        center_x = surface_width / 2.0
        center_y = font_size * 0.9 + padding + outline + 1
        if animation == 'shake':
            pad = max(0.0, _sc_num(state.get('shake_intensity', 100)) / 20.0)
            center_x += random.uniform(-pad, pad)
            center_y += random.uniform(-pad, pad)
        return surface, center_x, center_y

    def _make_clone(self, initial_vars=None):
        if self._runtime is None:
            return None
        if self._runtime.clone_limit is not None:
            clones = sum(1 for item in self._runtime.sprites if getattr(item, '_is_clone', False))
            if clones >= self._runtime.clone_limit:
                return None
        clone = self.__class__()
        for key, value in self.__dict__.items():
            if key.startswith('_') or key in getattr(type(self), 'GLOBAL_NAMES', ()):
                continue
            setattr(clone, key, value.copy() if isinstance(value, (list, dict)) else value)
        clone._handlers = {}
        clone._conditions = []
        clone._frame_hats = []
        # Clones+ 的“克隆时设置变量”需要在run()注册帽子前就生效
        for name, value in (initial_vars or {}).items():
            text = _sc_str(name)
            if not text:
                continue
            attr = getattr(type(clone), 'VAR_ATTRS', {}).get(text) \
                or _sc_ident(text, 'var')
            if attr in getattr(type(clone), 'GLOBAL_NAMES_SET', ()):
                GLOBALS[attr] = value
            else:
                setattr(clone, attr, value)
        clone._stretch_x = self._stretch_x
        clone._stretch_y = self._stretch_y
        clone._text_state = dict(self._text_state) if self._text_state else None
        clone._runtime = self._runtime
        clone._running = True
        clone._is_clone = True
        clone.run()
        self._runtime.sprites.append(clone)
        for func in list(clone._handlers.get('clone_start', [])):
            self._runtime.start_script(func)
        return clone

    def point_in_direction(self, direction):
        """面向指定方向"""
        self.direction = _sc_num(direction) % 360

    def point_towards(self, target):
        """面向鼠标指针或另一个角色"""
        if target == '_mouse_':
            dx = _sc_num(self.mouse_x) - _sc_num(self.x)
            dy = _sc_num(self.mouse_y) - _sc_num(self.y)
        else:
            other = self._runtime.find_sprite(target) if self._runtime else None
            if other is None:
                return
            dx = _sc_num(other.x) - _sc_num(self.x)
            dy = _sc_num(other.y) - _sc_num(self.y)
        if dx == 0 and dy == 0:
            return
        self.direction = math.degrees(math.atan2(dx, dy)) % 360

    def goto_target(self, target):
        """移到随机位置/鼠标指针/某个角色"""
        if target == '_mouse_':
            self.goto_xy(self.mouse_x, self.mouse_y)
        elif target in ('_random_', ''):
            self.goto_random()
        else:
            other = self._runtime.find_sprite(target) if self._runtime else None
            if other is not None:
                self.goto_xy(other.x, other.y)

    def glide_to_target(self, secs, target):
        """在指定秒数内滑行到随机位置/鼠标指针/某个角色"""
        if target == '_mouse_':
            self.glide_to(secs, self.mouse_x, self.mouse_y)
        elif target in ('_random_', ''):
            width = self._runtime.stage_width if self._runtime else 480
            height = self._runtime.stage_height if self._runtime else 360
            self.glide_to(secs, random.randint(-width // 2, width // 2),
                          random.randint(-height // 2, height // 2))
        else:
            other = self._runtime.find_sprite(target) if self._runtime else None
            if other is not None:
                self.glide_to(secs, other.x, other.y)

    def set_rotation_style(self, style):
        """设置旋转方式"""
        style = _sc_str(style)
        if style in ('left-right', 'left right', '左右翻转'):
            self.rotation_style = 'left-right'
        elif "don't" in style or 'none' in style or '不旋转' in style:
            self.rotation_style = "don't rotate"
        else:
            self.rotation_style = 'all around'
        self._apply_fencing()

    def set_backdrop(self, name):
        """切换舞台背景"""
        if self._runtime is not None:
            self._runtime.set_backdrop(name)

    def set_backdrop_and_wait(self, name):
        """切换背景并等待这次切换触发的“当背景换成”脚本结束"""
        if self._runtime is None:
            return
        threads = self._runtime.set_backdrop(name)
        if not threads:
            self._yield_frame()
            return
        context = getattr(self._local, 'context', None)
        self._turn_release()
        try:
            for thread in threads:
                while (thread.is_alive() and self._runtime.running
                       and (context is None or context.running)):
                    self._runtime.wait_frame(context)
        finally:
            self._turn_acquire()

    def next_backdrop(self):
        if self._runtime is not None:
            self._runtime.next_backdrop()

    @property
    def backdrop_number(self):
        return self._runtime.backdrop_number if self._runtime else 1

    @property
    def backdrop_name(self):
        return self._runtime.backdrop_name if self._runtime else ''

    def go_to_layer(self, where):
        """移到最前面/最后面"""
        if self._runtime is not None:
            self._runtime.go_to_layer(self, _sc_str(where))

    def change_layer(self, layers):
        """向前/向后移动若干层"""
        if self._runtime is not None:
            self._runtime.change_layer(self, int(_sc_num(layers)))

    def set_drag_mode(self, mode):
        self.draggable = 'not' not in _sc_str(mode).lower()

    def set_sound_effect(self, effect, value):
        key = _sc_str(effect).lower()
        self._sound_effects[key] = _sc_num(value)

    def change_sound_effect(self, effect, value):
        key = _sc_str(effect).lower()
        self._sound_effects[key] = _sc_num(self._sound_effects.get(key, 0)) + _sc_num(value)

    def clear_sound_effects(self):
        self._sound_effects = {'pitch': 0.0, 'pan': 0.0}

    def touching_color(self, color):
        if self._runtime is None:
            return False
        return self._runtime.touching_color(self, color)

    def color_touching_color(self, color, other):
        if self._runtime is None:
            return False
        return self._runtime.color_touching_color(self, color, other)

    def sensing_of(self, target, prop):
        if self._runtime is None:
            return 0
        return self._runtime.sensing_of(_sc_str(target), _sc_str(prop))

    def get_counter(self):
        return self._runtime.counter if self._runtime is not None else 0

    def incr_counter(self):
        if self._runtime is not None:
            self._runtime.counter += 1

    def clear_counter(self):
        if self._runtime is not None:
            self._runtime.counter = 0

    def username(self):
        if self._runtime is not None:
            return self._runtime.username
        return 'player'

    def extension(self, name, opcode, inputs=None, fields=None):
        """TurboWarp扩展调用入口"""
        if self._runtime is None:
            return 0
        return self._runtime.call_extension(
            self, name, opcode, inputs or {}, fields or {})

    def run(self):
        """注册事件脚本（由运行时调用）"""
        pass'''
