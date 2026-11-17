# -*- coding: utf-8 -*-
"""text2speech 文字朗读"""

def _extension_text2speech(runtime, sprite, opcode, inputs, fields):
    """text2speech扩展：朗读并等待、切换嗓音/语言"""
    key = str(opcode).lower().replace('_', '')
    if 'speak' in key:
        text = _sc_str(_ext_input(inputs, fields, 'WORDS', 'TEXT', 'words', 'text',
                                  default=''))
        runtime.speak(text, sprite)
    elif 'setvoice' in key:
        runtime.tts_voice = _sc_str(
            _ext_input(inputs, fields, 'VOICE', 'voice', default='alto')).lower()
    elif 'setlanguage' in key:
        runtime.tts_language = _sc_str(
            _ext_input(inputs, fields, 'LANGUAGE', 'language', default='English'))
    return 0
