# -*- coding: utf-8 -*-
"""lmsMoreEvents 更多事件"""

def _ext_hat_input(entry, name, default=None):
    inputs = entry.get('inputs') or {}
    for key in (name, name.upper(), name.lower()):
        if key in inputs:
            value = inputs[key]
            try:
                return value() if callable(value) else value
            except Exception:
                return default
    return default


def _ext_hat_alive(entry):
    thread = entry.get('thread')
    return thread is not None and thread.is_alive()


def _ext_frame_hat_action(runtime, sprite, entry):
    """返回 'start' / 'stop' / None，由运行时逐帧调用"""
    opcode = str(entry.get('opcode') or '').lower()
    short = opcode.split('_', 1)[-1]

    if short == 'whenclonestartswithvar':
        if not getattr(sprite, '_is_clone', False):
            return None
        name = _ext_hat_input(entry, 'INPUTA', '')
        expected = _ext_hat_input(entry, 'INPUTB', '')
        now = _sc_compare(_ext_var_get(sprite, name), expected) == 0
        previous = entry.get('state')
        entry['state'] = now
        if now and previous is not True:
            return 'start'
        return None

    if short == 'forever':
        return None if _ext_hat_alive(entry) else 'start'

    if short == 'whentruefalse':
        state = _sc_str(_ext_hat_input(entry, 'STATE', 'true')).lower() == 'true'
        condition = _sc_bool(_ext_hat_input(entry, 'CONDITION', False))
        now = condition if state else not condition
        previous = entry.get('state')
        entry['state'] = now
        if now and previous is not True:
            return 'start'
        return None

    if short == 'whiletruefalse':
        state = _sc_str(_ext_hat_input(entry, 'STATE', 'true')).lower() == 'true'
        condition = _sc_bool(_ext_hat_input(entry, 'CONDITION', False))
        now = condition if state else not condition
        if now:
            return None if _ext_hat_alive(entry) else 'start'
        return 'stop' if _ext_hat_alive(entry) else None

    if short == 'whenvaluechanged':
        current = _sc_str(_ext_hat_input(entry, 'INPUT', ''))
        previous = entry.get('state')
        # 与原扩展一致：上一值为空（假值）时只记录，不触发
        if not previous:
            entry['state'] = current
            return None
        if previous == current:
            return None
        entry['state'] = current
        return 'start'

    if short == 'everyduration':
        steps = _sc_round(_ext_hat_input(entry, 'DURATION', 3))
        if not isinstance(steps, int) or steps <= 0:
            return None
        if (runtime.frame + 1) % steps != 0:
            return None
        return None if _ext_hat_alive(entry) else 'start'

    if short == 'whenkeyaction':
        key = _ext_hat_input(entry, 'KEY_OPTION', 'space')
        action = _sc_str(_ext_hat_input(entry, 'ACTION', 'hit')).lower()
        down = _ext_key_down(runtime, key)
        now = (not down) if action == 'released' else down
        previous = entry.get('state')
        entry['state'] = now
        if now and previous is not True:
            return 'start'
        return None

    if short == 'whilekeypressed':
        down = _ext_key_down(runtime, _ext_hat_input(entry, 'KEY_OPTION', 'space'))
        if down:
            return None if _ext_hat_alive(entry) else 'start'
        return 'stop' if _ext_hat_alive(entry) else None

    return None


# ===================== More Events 更多事件 =====================

def _ext_received_data(sprite):
    context = getattr(sprite._local, 'context', None)
    data = getattr(context, 'received_data', None) if context else None
    return data if data else ''


def _ext_wait_threads(sprite, runtime, threads):
    context = getattr(sprite._local, 'context', None)
    while any(thread.is_alive() for thread in threads):
        if not runtime.running or (context is not None and not context.running):
            return
        sprite._yield_frame()


def _extension_more_events(runtime, sprite, opcode, inputs, fields):
    """lmsMoreEvents：广播传数据等命令积木"""
    key = str(opcode).lower().replace('_', '')

    if key.endswith('receiveddata'):
        return _ext_received_data(sprite)

    message = _sc_str(_ext_input(inputs, fields, 'BROADCAST_OPTION',
                                 'broadcast_option', default=''))
    data = _ext_input(inputs, fields, 'DATA', 'data', default=None)
    target_name = _ext_input(inputs, fields, 'TARGET', 'target', default='')

    if key.endswith('broadcastdatatotargetandwait') \
            or key.endswith('broadcastdatatotarget'):
        if not message:
            return 0
        target = _ext_target(runtime, target_name)
        if target is None:
            return 0
        targets = _ext_family(runtime, target)
        threads = runtime.broadcast_to(message, targets, data)
        if key.endswith('andwait'):
            _ext_wait_threads(sprite, runtime, threads)
        return 0

    if key.endswith('broadcasttotargetandwait') \
            or key.endswith('broadcasttotarget'):
        if not message:
            return 0
        target = _ext_target(runtime, target_name)
        if target is None:
            return 0
        threads = runtime.broadcast_to(
            message, _ext_family(runtime, target), data)
        if key.endswith('andwait'):
            _ext_wait_threads(sprite, runtime, threads)
        return 0

    if key.endswith('broadcastdataandwait') or key.endswith('broadcastdata'):
        if not message:
            return 0
        threads = runtime.broadcast(message, data)
        if key.endswith('andwait'):
            _ext_wait_threads(sprite, runtime, threads)
        return 0

    return 0
