# -*- coding: utf-8 -*-
"""lmsclonesplus 克隆+"""

# ===================== Clones+ 克隆+ =====================

def _extension_clones_plus(runtime, sprite, opcode, inputs, fields):
    """lmsclonesplus：带变量值的克隆管理"""
    key = str(opcode).lower().replace('_', '')
    var_a = _ext_input(inputs, fields, 'INPUTA', 'inputa', 'INPUT', 'input',
                       default='')
    var_b = _ext_input(inputs, fields, 'INPUTB', 'inputb', default=1)
    var_c = _ext_input(inputs, fields, 'INPUTC', 'inputc', default='')
    value_d = _ext_input(inputs, fields, 'INPUTD', 'inputd', default=1)

    if key.endswith('whenclonestartswithvar'):
        return 0

    if key.endswith('createcloneofmyselfwithvar'):
        sprite._make_clone({var_a: var_b})
        return 0

    if key.endswith('createclonewithvar'):
        _ext_origin(runtime, sprite)._make_clone({var_a: var_b})
        return 0

    if key.endswith('touchingclonewithvar'):
        clones = [item for item in _ext_family(runtime, sprite)
                  if getattr(item, '_is_clone', False)
                  and _sc_compare(_ext_var_get(item, var_a), var_b) == 0]
        return _ext_touching_targets(runtime, sprite, clones)

    if key.endswith('touchingmainsprite'):
        if not getattr(sprite, '_is_clone', False):
            return False
        origin = _ext_origin(runtime, sprite)
        return _ext_touching_targets(runtime, sprite, [origin])

    if key.endswith('setvariableofclone'):
        for item in _ext_family(runtime, sprite):
            if not getattr(item, '_is_clone', False):
                continue
            if _sc_compare(_ext_var_get(item, var_c), value_d) == 0:
                _ext_var_set(item, var_a, var_b)
        return 0

    if key.endswith('getvariableofclone'):
        # 该积木的匹配值是 INPUTC，没有 INPUTD
        match = _ext_input(inputs, fields, 'INPUTC', 'inputc', default=1)
        for item in _ext_family(runtime, sprite):
            if not getattr(item, '_is_clone', False):
                continue
            if _sc_compare(_ext_var_get(item, var_b), match) == 0:
                return _ext_var_get(item, var_a)
        return ''

    if key.endswith('setvariableofmainsprite'):
        _ext_var_set(_ext_origin(runtime, sprite), var_a, var_b)
        return 0

    if key.endswith('getvariableofmainsprite'):
        return _ext_var_get(_ext_origin(runtime, sprite), var_a)

    if key.endswith('cloneexists'):
        for item in _ext_family(runtime, sprite):
            if getattr(item, '_is_clone', False) \
                    and _sc_compare(_ext_var_get(item, var_a), var_b) == 0:
                return True
        return False

    if key.endswith('getthingofclone'):
        match = _ext_input(inputs, fields, 'INPUTC', 'inputc', default=1)
        for item in _ext_family(runtime, sprite):
            if not getattr(item, '_is_clone', False):
                continue
            if _sc_compare(_ext_var_get(item, var_b), match) == 0:
                return _ext_thing(item, var_a)
        return ''

    if key.endswith('getthingofmainsprite'):
        return _ext_thing(_ext_origin(runtime, sprite), var_a)

    if key.endswith('stopscriptsinclone'):
        for item in _ext_family(runtime, sprite):
            if getattr(item, '_is_clone', False) \
                    and _sc_compare(_ext_var_get(item, var_a), var_b) == 0:
                _ext_stop_target(runtime, sprite, item)
        return 0

    if key.endswith('stopscriptsinmainsprite'):
        _ext_stop_target(runtime, sprite, _ext_origin(runtime, sprite))
        return 0

    if key.endswith('stopscriptsinsprite'):
        _ext_stop_target(runtime, sprite, _ext_target(runtime, var_a))
        return 0

    if key.endswith('deleteclonesinsprite'):
        target = _ext_target(runtime, var_a)
        disposed_self = False
        if target is not None:
            for item in list(_ext_family(runtime, target)):
                if getattr(item, '_is_clone', False):
                    disposed_self = disposed_self or item is sprite
                    runtime.dispose_clone(item)
        if disposed_self:
            raise StopIteration('Clone deleted')
        return 0

    if key.endswith('deleteclonewithvar'):
        disposed_self = False
        for item in list(_ext_family(runtime, sprite)):
            if getattr(item, '_is_clone', False) \
                    and _sc_compare(_ext_var_get(item, var_a), var_b) == 0:
                disposed_self = disposed_self or item is sprite
                runtime.dispose_clone(item)
        if disposed_self:
            raise StopIteration('Clone deleted')
        return 0

    if key.endswith('isclone'):
        return bool(getattr(sprite, '_is_clone', False))

    if key.endswith('spriteclonecount'):
        target = _ext_target(runtime, var_a)
        if target is None:
            return 0
        return sum(1 for item in _ext_family(runtime, target)
                   if getattr(item, '_is_clone', False))

    if key.endswith('clonecount'):
        return sum(1 for item in runtime.sprites
                   if getattr(item, '_is_clone', False))

    return 0
