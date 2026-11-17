# -*- coding: utf-8 -*-
"""lmsListTools 列表工具"""

# ===================== List Tools (lmsListTools) =====================

def _ext_list_object(sprite, name):
    """按扩展语义查找列表：先舞台全局，再角色本地。"""
    text = _sc_str(name)
    runtime = getattr(sprite, '_runtime', None)
    if runtime is not None and runtime.stage_sprite is not None:
        stage = runtime.stage_sprite
        attr = getattr(type(stage), 'LIST_ATTRS', {}).get(text)
        if attr and isinstance(GLOBALS.get(attr), list):
            return GLOBALS[attr]
    attr = getattr(type(sprite), 'LIST_ATTRS', {}).get(text)
    if attr:
        value = getattr(sprite, attr, None)
        if isinstance(value, list):
            return value
    if runtime is not None:
        data, key = runtime._find_list(sprite, text)
        if data is not None:
            return data[key]
    return None


def _ext_same_value(a, b):
    """尽可能贴近JS的严格相等：类型不同就不相等。"""
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return float(a) == float(b)
    return type(a) is type(b) and a == b


def _extension_list_tools(runtime, sprite, opcode, inputs, fields):
    """lmsListTools：列表排序、拼接、查找、数组转换"""
    key = str(opcode).lower().replace('_', '')
    list_name = _ext_input(inputs, fields, 'LIST', 'list', default='')
    values = _ext_list_object(sprite, list_name)

    if key.endswith('deleteitems'):
        if values is None:
            return 0
        first = int(_sc_num(_ext_input(inputs, fields, 'NUM1', 'num1', default=1)))
        last = int(_sc_num(_ext_input(inputs, fields, 'NUM2', 'num2', default=1)))
        if first > last:
            first, last = last, first
        start = max(0, first - 1)
        end = max(start, last)
        del values[start:end]
        return 0

    if key.endswith('deleteallofitem'):
        if values is None:
            return 0
        target = _ext_input(inputs, fields, 'ITEM', 'item', default='')
        values[:] = [item for item in values
                     if not _ext_same_value(item, target)]
        return 0

    if key.endswith('replaceallofitem'):
        if values is None:
            return 0
        old = _ext_input(inputs, fields, 'ITEM1', 'item1', default='')
        new = _ext_input(inputs, fields, 'ITEM2', 'item2', default='')
        for index, item in enumerate(values):
            if _ext_same_value(item, old):
                values[index] = new
        return 0

    if key.endswith('repeatlist'):
        if values is None:
            return 0
        source = _ext_list_object(
            sprite, _ext_input(inputs, fields, 'LIST1', 'list1', default=''))
        if source is None:
            return 0
        count = max(0, int(_sc_num(
            _ext_input(inputs, fields, 'NUM', 'num', default=1))))
        values.extend(list(source) * count)
        return 0

    if key.endswith('getlistjoin'):
        if values is None:
            return ''
        separator = _sc_str(_ext_input(inputs, fields, 'STRING', 'string',
                                       default=''))
        return separator.join(_sc_str(item) for item in values)

    if key.endswith('timesitemappears'):
        if values is None:
            return 0
        target = _ext_input(inputs, fields, 'ITEM', 'item', default='')
        return sum(1 for item in values if _sc_eq(item, target))

    if key.endswith('itemindex'):
        if values is None:
            return 0
        target = _ext_input(inputs, fields, 'ITEM', 'item', default='')
        indexes = [index for index, item in enumerate(values)
                   if _ext_same_value(item, target)]
        if not indexes:
            return 0
        mode = _sc_str(_ext_input(inputs, fields, 'INDEX', 'index',
                                  default='_first_')).lower()
        if mode in ('_last_', 'last'):
            return indexes[-1] + 1
        if mode in ('_random_', 'random'):
            return random.choice(indexes) + 1
        return indexes[0] + 1

    if key.endswith('listisempty'):
        return not values

    if key.endswith('itemnumexists'):
        if not values:
            return False
        number = _ext_input(inputs, fields, 'NUM', 'num', default=0)
        text = _sc_str(number).strip().lower()
        if text in ('last', '末尾'):
            return True
        if text in ('random', 'any'):
            return True
        index = _sc_round(_sc_num(number))
        return 1 <= index <= len(values)

    if key.endswith('orderis'):
        if values is None:
            return False
        order = _sc_str(_ext_input(inputs, fields, 'ORDER', 'order',
                                   default='ascending')).lower()
        pairs = zip(values, values[1:])
        if order in ('ascending', '升序'):
            return all(_sc_compare(a, b) <= 0 for a, b in pairs)
        if order in ('descending', '降序'):
            return all(_sc_compare(a, b) >= 0 for a, b in pairs)
        if order in ('reversed', '反向'):
            return all(_sc_compare(a, b) >= 0 for a, b in pairs)
        return False

    if key.endswith('orderlist'):
        if values is None:
            return 0
        order = _sc_str(_ext_input(inputs, fields, 'ORDER', 'order',
                                   default='reversed')).lower()
        if order in ('ascending', '升序'):
            values.sort(key=functools.cmp_to_key(_sc_compare))
        elif order in ('descending', '降序'):
            values.sort(key=functools.cmp_to_key(_sc_compare), reverse=True)
        elif order in ('randomised', 'randomized', 'random', '随机'):
            random.shuffle(values)
        else:
            values.reverse()
        return 0

    if key.endswith('setlisttolist'):
        if values is None:
            return 0
        source = _ext_list_object(
            sprite, _ext_input(inputs, fields, 'LIST2', 'list2', default=''))
        if source is not None:
            values[:] = list(source)
        return 0

    if key.endswith('joinlists'):
        if values is None:
            return 0
        source = _ext_list_object(
            sprite, _ext_input(inputs, fields, 'LIST2', 'list2', default=''))
        if source is not None:
            values.extend(source)
        return 0

    if key.endswith('setlistarray'):
        if values is None:
            return 0
        text = _sc_str(_ext_input(inputs, fields, 'ARRAY', 'array', default='[]'))
        try:
            data = json.loads(text)
        except (ValueError, TypeError):
            data = []
        values[:] = data if isinstance(data, list) else []
        return 0

    if key.endswith('getlistarray'):
        return json.dumps(values or [], ensure_ascii=False,
                          separators=(',', ':'))

    return 0
