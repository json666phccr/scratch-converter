# -*- coding: utf-8 -*-
"""music 音乐扩展"""

def _extension_music(runtime, sprite, opcode, inputs, fields):
    """music扩展：音符/鼓点/节拍/速度"""
    key = str(opcode).lower().replace('_', '')
    if 'gettempo' in key:
        return runtime.music_tempo
    if 'settempo' in key:
        value = _sc_num(_ext_input(inputs, fields, 'TEMPO', 'tempo', default=60))
        runtime.music_tempo = max(20.0, min(500.0, value))
        return 0
    if 'changetempo' in key:
        value = _sc_num(_ext_input(inputs, fields, 'TEMPO', 'tempo', default=0))
        runtime.music_tempo = max(20.0, min(500.0, runtime.music_tempo + value))
        return 0
    if 'setinstrument' in key:
        runtime.music_instrument = int(_sc_num(
            _ext_input(inputs, fields, 'INSTRUMENT', 'instrument', default=1)))
        return 0
    if 'restforbeats' in key:
        runtime.music_wait(sprite, _sc_num(_ext_input(inputs, fields, 'BEATS', 'beats', default=0.25)))
        return 0
    if 'playdrum' in key:
        drum = int(_sc_num(_ext_input(inputs, fields, 'DRUM', 'drum', default=1)))
        beats = _sc_num(_ext_input(inputs, fields, 'BEATS', 'beats', default=0.25))
        runtime.music_play_drum(sprite, drum, beats)
        return 0
    if 'playnote' in key:
        note = _sc_num(_ext_input(inputs, fields, 'NOTE', 'note', default=60))
        beats = _sc_num(_ext_input(inputs, fields, 'BEATS', 'beats', default=0.5))
        runtime.music_play_note(sprite, note, beats)
        return 0
    return 0
