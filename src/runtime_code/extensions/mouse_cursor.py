# -*- coding: utf-8 -*-
"""MouseCursor 光标"""

# ===================== Mouse Cursor (MouseCursor) =====================

_CURSOR_KEYS = {
    'default': 'ARROW', 'arrow': 'ARROW', 'pointer': 'HAND',
    'hand': 'HAND', 'crosshair': 'CROSSHAIR', 'text': 'IBEAM',
    'ibeam': 'IBEAM', 'wait': 'WAIT', 'progress': 'WAITARROW',
    'help': 'ARROW', 'move': 'SIZEALL', 'all-scroll': 'SIZEALL',
    'not-allowed': 'NO', 'no-drop': 'NO', 'grab': 'HAND',
    'grabbing': 'HAND', 'zoom-in': 'SIZEALL', 'zoom-out': 'SIZEALL',
    'n-resize': 'SIZENS', 's-resize': 'SIZENS', 'ns-resize': 'SIZENS',
    'row-resize': 'SIZENS', 'e-resize': 'SIZEWE', 'w-resize': 'SIZEWE',
    'ew-resize': 'SIZEWE', 'col-resize': 'SIZEWE',
    'nw-resize': 'SIZENWSE', 'se-resize': 'SIZENWSE',
    'nwse-resize': 'SIZENWSE', 'ne-resize': 'SIZENESW',
    'sw-resize': 'SIZENESW', 'nesw-resize': 'SIZENESW',
    'vertical-text': 'IBEAM', 'cell': 'CROSSHAIR', 'copy': 'ARROW',
    'context-menu': 'ARROW', 'alias': 'HAND',
}


def _set_system_cursor(name):
    constant = getattr(pygame, 'SYSTEM_CURSOR_' + name, None)
    if constant is None:
        constant = pygame.SYSTEM_CURSOR_ARROW
    try:
        pygame.mouse.set_cursor(constant)
        return True
    except Exception:
        return False


def _extension_mouse_cursor(runtime, sprite, opcode, inputs, fields):
    """MouseCursor：系统光标与自定义造型光标（只在舞台区域内生效）"""
    key = str(opcode).lower().replace('_', '')
    if key.endswith('getcur'):
        return getattr(runtime, '_cursor_name', 'default')
    if key.endswith('hidecur'):
        runtime._cursor_visible = False
        runtime.apply_mouse_cursor()
        return 0
    if key.endswith('setcur'):
        name = _sc_str(_ext_input(inputs, fields, 'CUR', 'cur',
                                  default='default')).lower()
        runtime._cursor_name = name
        runtime._cursor_system = _CURSOR_KEYS.get(name, 'ARROW')
        runtime._cursor_custom = None
        runtime._cursor_visible = True
        runtime.apply_mouse_cursor()
        return 0
    if key.endswith('setcursorimage'):
        try:
            surface = sprite._costume_surface()
            if surface is None:
                return 0
            max_size = int(_sc_num(_ext_input(inputs, fields, 'SIZE', 'size',
                                              default=32)))
            max_size = max(8, min(128, max_size))
            width, height = surface.get_size()
            scale = min(1.0, max_size / float(max(width, height, 1)))
            if scale < 1.0:
                surface = pygame.transform.smoothscale(
                    surface, (max(1, int(width * scale)),
                              max(1, int(height * scale))))
            width, height = surface.get_size()
            position = _sc_str(_ext_input(inputs, fields, 'POSITION',
                                          'position', default='center')).lower()
            hotspots = {
                'top left': (0, 0), 'top': (width // 2, 0),
                'top right': (width - 1, 0), 'left': (0, height // 2),
                'center': (width // 2, height // 2),
                'right': (width - 1, height // 2),
                'bottom left': (0, height - 1),
                'bottom': (width // 2, height - 1),
                'bottom right': (width - 1, height - 1),
            }
            hotspot = hotspots.get(position, (width // 2, height // 2))
            data = []
            mask = []
            for y in range(height):
                for x in range(width):
                    color = surface.get_at((x, y))
                    data.append((color.r, color.g, color.b))
                    mask.append(255 if color.a > 0 else 0)
            # 保存光标数据，由运行时根据鼠标是否位于舞台内决定是否应用
            runtime._cursor_custom = (width, hotspot, data, mask)
            runtime._cursor_name = 'custom'
            runtime._cursor_visible = True
            runtime.apply_mouse_cursor()
        except Exception:
            pass
        return 0
    return 0
