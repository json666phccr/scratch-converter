# -*- coding: utf-8 -*-
"""clipboard 剪贴板"""

# ===================== Clipboard (clipboard) =====================

def _clipboard_read(runtime):
    text = ''
    try:
        if pygame is not None and getattr(runtime, '_scrap_ready', False):
            data = pygame.scrap.get(pygame.SCRAP_TEXT)
            if data:
                text = data.decode('utf-8', 'replace').rstrip('\x00')
    except Exception:
        text = ''
    if not text:
        text = getattr(runtime, '_clipboard_text', '')
    return text


def _clipboard_write(runtime, text):
    runtime._clipboard_text = text
    try:
        if pygame is not None and getattr(runtime, '_scrap_ready', False):
            pygame.scrap.put(pygame.SCRAP_TEXT, text.encode('utf-8'))
    except Exception:
        pass


def _extension_clipboard(runtime, sprite, opcode, inputs, fields):
    """clipboard：系统剪贴板"""
    key = str(opcode).lower().replace('_', '')
    if key.endswith('setclipboard'):
        _clipboard_write(runtime, _sc_str(
            _ext_input(inputs, fields, 'TEXT', 'text', default='')))
        return 0
    if key.endswith('resetclipboard'):
        _clipboard_write(runtime, '')
        return 0
    if key.endswith('getlastpastedtext'):
        return getattr(runtime, '_clipboard_last_pasted', '')
    if key.endswith('clipboard'):
        return _clipboard_read(runtime)
    return 0
