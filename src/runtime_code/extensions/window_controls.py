# -*- coding: utf-8 -*-
"""cubesterWindowControls 窗口控制"""

# ===================== Window Controls (cubesterWindowControls) =====================

def _window_position(runtime):
    try:
        return pygame.display.get_window_position()
    except Exception:
        pass
    try:
        from pygame._sdl2 import video
        window = video.Window.from_display_module()
        return window.position
    except Exception:
        return (0, 0)


def _window_set_position(runtime, x, y):
    try:
        pygame.display.set_window_position((int(x), int(y)))
        return
    except Exception:
        pass
    try:
        from pygame._sdl2 import video
        window = video.Window.from_display_module()
        window.position = (int(x), int(y))
    except Exception:
        pass


def _window_screen_size(runtime):
    try:
        info = pygame.display.Info()
        return (info.current_w or 1920, info.current_h or 1080)
    except Exception:
        return (1920, 1080)


def _extension_window_controls(runtime, sprite, opcode, inputs, fields):
    """cubesterWindowControls：窗口位置/大小/标题/全屏"""
    key = str(opcode).lower().replace('_', '')
    screen_w, screen_h = _window_screen_size(runtime)
    try:
        width, height = runtime.screen.get_size()
        pos_x, pos_y = _window_position(runtime)
    except Exception:
        width, height, pos_x, pos_y = runtime.stage_width, runtime.stage_height, 0, 0

    if key.endswith('windowx'):
        return pos_x
    if key.endswith('windowy'):
        return pos_y
    if key.endswith('windoww'):
        return width
    if key.endswith('windowh'):
        return height
    if key.endswith('screenw'):
        return screen_w
    if key.endswith('screenh'):
        return screen_h
    if key.endswith('istouchingedge'):
        return (pos_x <= 0 or pos_y <= 0
                or pos_x + width >= screen_w or pos_y + height >= screen_h)
    if key.endswith('isfocused'):
        try:
            return bool(pygame.key.get_focused())
        except Exception:
            return False
    if key.endswith('isfullscreen'):
        return bool(getattr(runtime, 'fullscreen', False))
    if key.endswith('windowtitle'):
        try:
            return pygame.display.get_caption()[0]
        except Exception:
            return ''
    if key.endswith('changetitleto'):
        runtime.user_window_title = _sc_str(
            _ext_input(inputs, fields, 'TITLE', 'title', default=''))
        try:
            pygame.display.set_caption(runtime.user_window_title)
        except Exception:
            pass
        return 0
    if key.endswith('enterfullscreen'):
        runtime.set_fullscreen(True)
        return 0
    if key.endswith('exitfullscreen'):
        runtime.set_fullscreen(False)
        return 0
    if key.endswith('closewindow'):
        runtime.running = False
        try:
            pygame.event.post(pygame.event.Event(pygame.QUIT))
        except Exception:
            pass
        return 0

    if key.endswith('moveto'):
        _window_set_position(
            runtime, _sc_num(_ext_input(inputs, fields, 'X', 'x', default=0)),
            _sc_num(_ext_input(inputs, fields, 'Y', 'y', default=0)))
        return 0
    if key.endswith('movetopresets'):
        preset = _sc_str(_ext_input(inputs, fields, 'PRESETS', 'presets',
                                    default='center')).lower()
        max_x = max(0, screen_w - width)
        max_y = max(0, screen_h - height)
        positions = {
            'center': (max_x // 2, max_y // 2),
            'left': (0, max_y // 2),
            'right': (max_x, max_y // 2),
            'top': (max_x // 2, 0),
            'bottom': (max_x // 2, max_y),
            'top right': (max_x, 0), 'top left': (0, 0),
            'bottom right': (max_x, max_y),
            'bottom left': (0, max_y),
        }
        if preset in ('random position', 'random', '随机位置'):
            target = (random.randint(0, max_x), random.randint(0, max_y))
        else:
            target = positions.get(preset, (max_x // 2, max_y // 2))
        _window_set_position(runtime, target[0], target[1])
        return 0
    if key.endswith('changex'):
        _window_set_position(runtime, pos_x + _sc_num(
            _ext_input(inputs, fields, 'X', 'x', default=0)), pos_y)
        return 0
    if key.endswith('setx'):
        _window_set_position(runtime, _sc_num(
            _ext_input(inputs, fields, 'X', 'x', default=0)), pos_y)
        return 0
    if key.endswith('changey'):
        _window_set_position(runtime, pos_x, pos_y + _sc_num(
            _ext_input(inputs, fields, 'Y', 'y', default=0)))
        return 0
    if key.endswith('sety'):
        _window_set_position(runtime, pos_x, _sc_num(
            _ext_input(inputs, fields, 'Y', 'y', default=0)))
        return 0
    if key.endswith('resizeto'):
        runtime.set_window_size(
            int(_sc_num(_ext_input(inputs, fields, 'W', 'w', default=width))),
            int(_sc_num(_ext_input(inputs, fields, 'H', 'h', default=height))))
        return 0
    if key.endswith('resizetopresets'):
        preset = _sc_str(_ext_input(inputs, fields, 'PRESETS', 'presets',
                                    default='480x360')).lower()
        try:
            new_w, new_h = preset.split('x', 1)
            runtime.set_window_size(int(new_w), int(new_h))
        except (ValueError, AttributeError):
            pass
        return 0
    if key.endswith('changew'):
        runtime.set_window_size(width + int(_sc_num(
            _ext_input(inputs, fields, 'W', 'w', default=0))), height)
        return 0
    if key.endswith('setw'):
        runtime.set_window_size(int(_sc_num(
            _ext_input(inputs, fields, 'W', 'w', default=width))), height)
        return 0
    if key.endswith('changeh'):
        runtime.set_window_size(width, height + int(_sc_num(
            _ext_input(inputs, fields, 'H', 'h', default=0))))
        return 0
    if key.endswith('seth'):
        runtime.set_window_size(width, int(_sc_num(
            _ext_input(inputs, fields, 'H', 'h', default=height))))
        return 0
    if key.endswith('matchstagesize'):
        runtime.set_window_size(runtime.stage_width,
                                runtime.stage_height + runtime.toolbar_height)
        return 0
    return 0
