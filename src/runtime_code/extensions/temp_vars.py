# -*- coding: utf-8 -*-
"""lmsTempVars2 临时变量"""

# ===================== Temporary Variables 临时变量 =====================

def _ext_thread_vars(sprite):
    store = getattr(sprite._local, 'ext_thread_vars', None)
    if store is None:
        store = {}
        sprite._local.ext_thread_vars = store
    return store


def _extension_temp_vars(runtime, sprite, opcode, inputs, fields):
    """lmsTempVars2 / lmstempvars：线程变量与运行时变量"""
    key = str(opcode).lower().replace('_', '')
    name = _ext_input(inputs, fields, 'VAR', 'var', 'INPUT', 'input',
                      'INPUTA', 'inputa', default='')

    if key.endswith('setthreadvariable'):
        _ext_thread_vars(sprite)[_sc_str(name)] = \
            _ext_input(inputs, fields, 'STRING', 'string', default=0)
        return 0
    if key.endswith('changethreadvariable'):
        store = _ext_thread_vars(sprite)
        text = _sc_str(name)
        previous = _sc_num(store.get(text, 0))
        store[text] = previous + _sc_num(
            _ext_input(inputs, fields, 'NUM', 'num', default=1))
        return 0
    if key.endswith('getthreadvariable'):
        return _ext_thread_vars(sprite).get(_sc_str(name), '')
    if key.endswith('threadvariableexists'):
        return _sc_str(name) in _ext_thread_vars(sprite)
    if key.endswith('listthreadvariables'):
        return ','.join(_ext_thread_vars(sprite).keys())
    if key.endswith('foreachthreadvariable'):
        return 0

    if key.endswith('setruntimevariable'):
        runtime.ext_runtime_vars[_sc_str(name)] = \
            _ext_input(inputs, fields, 'STRING', 'string', default=0)
        return 0
    if key.endswith('changeruntimevariable'):
        text = _sc_str(name)
        previous = _sc_num(runtime.ext_runtime_vars.get(text, 0))
        runtime.ext_runtime_vars[text] = previous + _sc_num(
            _ext_input(inputs, fields, 'NUM', 'num', default=1))
        return 0
    if key.endswith('getruntimevariable'):
        return runtime.ext_runtime_vars.get(_sc_str(name), '')
    if key.endswith('runtimevariableexists'):
        return _sc_str(name) in runtime.ext_runtime_vars
    if key.endswith('deleteruntimevariable'):
        runtime.ext_runtime_vars.pop(_sc_str(name), None)
        return 0
    if key.endswith('deleteallruntimevariables'):
        runtime.ext_runtime_vars = {}
        return 0
    if key.endswith('listruntimevariables'):
        return ','.join(runtime.ext_runtime_vars.keys())

    # 旧版临时变量扩展：模块级字典，直到显式删除才清空
    if key.endswith('setvariableto'):
        runtime.ext_legacy_vars[_sc_str(name)] = \
            _ext_input(inputs, fields, 'INPUTB', 'inputb', default=0)
        return 0
    if key.endswith('changevariableby'):
        text = _sc_str(name)
        previous = _sc_num(runtime.ext_legacy_vars.get(text, 0))
        runtime.ext_legacy_vars[text] = previous + _sc_num(
            _ext_input(inputs, fields, 'INPUTB', 'inputb', default=1))
        return 0
    if key.endswith('getvariable'):
        return runtime.ext_legacy_vars.get(_sc_str(name), '')
    if key.endswith('deletevariable'):
        runtime.ext_legacy_vars.pop(_sc_str(name), None)
        return 0
    if key.endswith('deleteallvariables'):
        runtime.ext_legacy_vars = {}
        return 0
    if key.endswith('listvariables'):
        return ','.join(runtime.ext_legacy_vars.keys())

    return 0
