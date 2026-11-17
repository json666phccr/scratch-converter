# -*- coding: utf-8 -*-
"""skyhigh173JSON JSON 扩展"""

def _json_reject_constant(value):
    raise ValueError('invalid JSON constant')


def _json_load(text):
    try:
        return True, json.loads(_sc_str(text), parse_constant=_json_reject_constant)
    except Exception:
        return False, None


def _json_norm(value):
    if isinstance(value, float) and math.isfinite(value) and value == int(value):
        return int(value)
    if isinstance(value, list):
        return [_json_norm(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_norm(item) for key, item in value.items()}
    return value


def _json_dumps(value):
    try:
        return json.dumps(_json_norm(value), ensure_ascii=False,
                          separators=(',', ':'), allow_nan=False)
    except Exception:
        return ''


def _json_bracketed(value):
    if not isinstance(value, str):
        return False
    return ((value.startswith('[') and value.endswith(']'))
            or (value.startswith('{') and value.endswith('}')))


def _json_valid(value):
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    if not _json_bracketed(stripped):
        return False
    ok, _parsed = _json_load(stripped)
    return ok


def _json_valid_return(value):
    if not isinstance(value, str) or not _json_bracketed(value):
        return value
    ok, parsed = _json_load(value)
    if not ok:
        return value
    return '' if parsed is None else parsed


def _json_fix(value):
    if isinstance(value, float):
        if math.isnan(value):
            return 'NaN'
        if math.isinf(value):
            return 'Infinity' if value > 0 else '-Infinity'
    if value is None:
        return ''
    return value


def _json_strict_eq(first, second):
    if isinstance(first, bool) or isinstance(second, bool):
        return isinstance(first, bool) and isinstance(second, bool) and first == second
    if isinstance(first, (dict, list)) or isinstance(second, (dict, list)):
        return first is second
    if isinstance(first, (int, float)) and isinstance(second, (int, float)):
        return first == second
    if isinstance(first, str) and isinstance(second, str):
        return first == second
    if first is None or second is None:
        return first is None and second is None
    return False


def _json_member(container, key):
    """返回 (是否存在, 值)，兼容对象键、数组下标和数组的 length"""
    if isinstance(container, dict):
        text = _sc_str(key)
        return (text in container), container.get(text)
    if isinstance(container, list):
        text = _sc_str(key)
        if text == 'length':
            return True, len(container)
        number = _sc_num(key)
        if isinstance(number, float) and not number.is_integer():
            return False, None
        index = int(number)
        if 0 <= index < len(container):
            return True, container[index]
        return False, None
    return False, None


def _json_index(array, index):
    """Scratch 风格下标：1 是首项，-1 是末项，0 无效"""
    number = _sc_num(index)
    if isinstance(number, float) and not number.is_integer():
        return None
    index = int(number)
    if index == 0:
        return None
    if index > 0:
        index -= 1
    else:
        index += len(array)
    if index < 0 or index >= len(array):
        return None
    return index


def _json_key_text(key):
    return _sc_str(_json_fix(_json_valid_return(key)))


def _json_compare(first, second):
    return _sc_compare(first, second)


def _json_join_item(value):
    if value is None:
        return ''
    if isinstance(value, dict):
        return '[object Object]'
    if isinstance(value, list):
        return ','.join(_json_join_item(item) for item in value)
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return _sc_str(value)


def _json_spread(value):
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, list):
        return {str(index): item for index, item in enumerate(value)}
    return {}


def _json_flatten(value, depth):
    result = []
    for item in value:
        if isinstance(item, list) and depth > 0:
            result.extend(_json_flatten(item, depth - 1))
        else:
            result.append(item)
    return result


def _json_analysis(values, analysis):
    numbers = [_sc_num(item) for item in values]
    total = len(numbers)
    if analysis == 'maximum':
        if not numbers:
            return -math.inf
        best = -math.inf
        for number in numbers:
            if number > best:
                best = number
        return best
    if analysis == 'minimum':
        if not numbers:
            return math.inf
        best = math.inf
        for number in numbers:
            if number < best:
                best = number
        return best
    if analysis == 'sum':
        return math.fsum(numbers)
    if analysis == 'average':
        if not total:
            return math.nan
        return math.fsum(numbers) / total
    if analysis == 'median':
        if not total:
            return math.nan
        ordered = sorted(numbers)
        middle = total // 2
        if total % 2 == 0:
            return (ordered[middle - 1] + ordered[middle]) / 2.0
        return ordered[middle]
    if analysis == 'mode':
        counts = {}
        best, best_count = 0, 0
        for number in numbers:
            counts[number] = counts.get(number, 0) + 1
            if counts[number] > best_count:
                best, best_count = number, counts[number]
        return best
    if analysis == 'variance':
        if not total:
            return math.nan
        average = math.fsum(numbers) / total
        return math.fsum((number - average) ** 2 for number in numbers) / total
    return 0


def _extension_skyhigh_json(runtime, sprite, opcode, inputs, fields):
    """TurboWarp JSON 扩展（skyhigh173JSON）"""
    key = str(opcode).lower().replace('_', '')

    def arg(*names, default=''):
        return _ext_input(inputs, fields, *names, default=default)

    if key.endswith('jsonisvalid'):
        return _json_valid(arg('json'))

    if key.endswith('jsonerrmsg'):
        text = _sc_str(arg('json'))
        ok, _parsed = _json_load(text)
        if not ok:
            try:
                json.loads(text)
            except Exception as error:
                return str(error)
            return 'JSON must be an object or array'
        return ''

    if key.endswith('jsonis'):
        types = _sc_str(arg('types', default='Object'))
        ok, parsed = _json_load(arg('json'))
        if not ok:
            return False
        if types == 'Object':
            return isinstance(parsed, dict)
        if types == 'Array':
            return isinstance(parsed, list)
        return False

    if key.endswith('jsongetall'):
        ok, parsed = _json_load(arg('json'))
        if not ok:
            return ''
        kind = _sc_str(arg('Stype', default='keys'))
        if isinstance(parsed, list):
            keys = [str(index) for index in range(len(parsed))]
            values = list(parsed)
        elif isinstance(parsed, dict):
            keys = list(parsed.keys())
            values = list(parsed.values())
        else:
            return ''
        if kind == 'keys':
            return _json_dumps(keys)
        if kind == 'values':
            return _json_dumps([_json_fix(item) for item in values])
        if kind == 'datas':
            return _json_dumps([[_json_fix(key_item), _json_fix(value)]
                                for key_item, value in zip(keys, values)])
        return ''

    if key.endswith('jsonnew'):
        kind = _sc_str(arg('json', default='Object'))
        if kind == 'Object':
            return '{}'
        if kind == 'Array':
            return '[]'
        return ''

    if key.endswith('jsonhaskey'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, (dict, list)):
            return False
        text = _json_key_text(arg('key'))
        if isinstance(parsed, list) and text == 'length':
            return False
        found, _value = _json_member(parsed, text)
        return found

    if key.endswith('jsonhasvalue'):
        ok, parsed = _json_load(arg('json'))
        if not ok:
            return False
        wanted = _json_valid_return(arg('value'))
        if isinstance(parsed, list):
            return any(_json_strict_eq(item, wanted) for item in parsed)
        if isinstance(parsed, str):
            return _sc_str(wanted) in parsed
        return False

    if key.endswith('jsonequal'):
        ok1, first = _json_load(arg('json1'))
        ok2, second = _json_load(arg('json2'))
        if not ok1 or not ok2:
            return False
        left = _json_spread(first)
        right = _json_spread(second)
        same = len(left) == len(right) and all(
            _json_strict_eq(value, right.get(name))
            for name, value in left.items())
        operator = _sc_str(arg('equal', default='='))
        if operator == '=':
            return same
        if operator == '≠':
            return not same
        return False

    if key.endswith('jsonminify'):
        ok, parsed = _json_load(arg('json'))
        return _json_dumps(parsed) if ok else ''

    if key.endswith('jsonflip'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, dict):
            return ''
        result = {}
        for name, value in parsed.items():
            targets = value if isinstance(value, list) else [value]
            for target in targets:
                if isinstance(target, (dict, list)) or target is None:
                    continue
                target = _sc_str(target)
                if target in result:
                    if isinstance(result[target], list):
                        result[target].append(name)
                    else:
                        result[target] = [result[target], name]
                else:
                    result[target] = name
        return _json_dumps(result)

    if key.endswith('jsongetpath'):
        ok, path = _json_load(arg('path'))
        if not ok or not isinstance(path, list):
            return ''
        ok, parsed = _json_load(arg('json'))
        if not ok:
            return ''
        current = parsed
        for step in path:
            if isinstance(current, list):
                index = _json_index(current, step)
                if index is None:
                    return ''
                current = current[index]
            elif isinstance(current, dict):
                name = _sc_str(step)
                if name not in current:
                    return ''
                current = current[name]
            else:
                return ''
        if current is None:
            return ''
        if isinstance(current, (dict, list)):
            return _json_dumps(current)
        return _json_fix(current)

    if key.endswith('jsonsetpath'):
        ok, path = _json_load(arg('path'))
        if not ok or not isinstance(path, list) or not path:
            return ''
        ok, parsed = _json_load(arg('json'))
        if not ok:
            return ''
        data = _json_fix(_json_valid_return(arg('data')))
        current = parsed
        for position, step in enumerate(path):
            last = position == len(path) - 1
            if isinstance(current, list):
                index = _json_index(current, step)
                if index is None:
                    return ''
                if last:
                    current[index] = data
                else:
                    current = current[index]
            elif isinstance(current, dict):
                name = _sc_str(step)
                if last:
                    current[name] = data
                elif name in current:
                    current = current[name]
                else:
                    return ''
            else:
                return ''
        return _json_dumps(parsed)

    if key.endswith('jsonjlength') or key.endswith('jsonlength'):
        ok, parsed = _json_load(arg('json'))
        if not ok or parsed is None:
            return ' '
        if isinstance(parsed, (dict, list, str)):
            return len(parsed)
        return 0

    if key.endswith('jsonget'):
        ok, parsed = _json_load(arg('json'))
        if not ok:
            return ''
        found, value = _json_member(parsed, arg('item'))
        if not found:
            return ''
        value = _json_fix(value)
        return _json_dumps(value) if isinstance(value, (dict, list)) else value

    if key.endswith('jsonset'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, (dict, list)):
            return ''
        value = _json_fix(_json_valid_return(arg('value')))
        item = arg('item')
        if isinstance(parsed, list):
            number = _sc_num(item)
            if isinstance(number, float) and not number.is_integer():
                return _json_dumps(parsed)
            index = int(number)
            if index < 0:
                return _json_dumps(parsed)
            if index >= len(parsed):
                parsed.extend([None] * (index + 1 - len(parsed)))
            parsed[index] = value
        else:
            parsed[_sc_str(item)] = value
        return _json_dumps(parsed)

    if key.endswith('jsondelete'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, (dict, list)):
            return ''
        item = arg('item')
        if isinstance(parsed, list):
            number = _sc_num(item)
            if isinstance(number, float) and not number.is_integer():
                return _json_dumps(parsed)
            index = int(number)
            if 0 <= index < len(parsed):
                parsed[index] = None
        else:
            parsed.pop(_sc_str(item), None)
        return _json_dumps(parsed)

    if key.endswith('jsonarrayget'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, list):
            return ''
        index = _json_index(parsed, arg('item'))
        if index is None:
            return ''
        value = _json_fix(parsed[index])
        return _json_dumps(value) if isinstance(value, (dict, list)) else value

    if key.endswith('jsonarrayitemh'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, list):
            return ''
        wanted = _json_fix(_json_valid_return(arg('item')))
        for index, value in enumerate(parsed):
            if _json_strict_eq(value, wanted):
                return index + 1
        return 0

    if key.endswith('jsonarrayfromto'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, list):
            return ''
        start = int(_sc_num(arg('item'))) - 1
        end = int(_sc_num(arg('item2')))
        if start < 0:
            start = max(0, len(parsed) + start)
        if end < 0:
            end = max(0, len(parsed) + end)
        return _json_dumps(parsed[start:end])

    if key.endswith('jsonarrayfrom'):
        return _json_dumps(list(_sc_str(arg('json'))))

    if key.endswith('jsonarrayconcat'):
        ok1, first = _json_load(arg('json'))
        ok2, second = _json_load(arg('json2'))
        if not ok1 or not ok2:
            return ''
        if isinstance(first, list):
            if isinstance(second, list):
                return _json_dumps(first + second)
            return _json_dumps(first + [second])
        if isinstance(first, str) and isinstance(second, str):
            return first + second
        return ''

    if key.endswith('jsonarraypush'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, list):
            return ''
        parsed.append(_json_fix(_json_valid_return(arg('item'))))
        return _json_dumps(parsed)

    if key.endswith('jsonarrayinsert'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, list):
            return ''
        index = int(_sc_num(arg('pos'))) - 1
        if index < 0:
            index = max(0, len(parsed) + index)
        if index > len(parsed):
            index = len(parsed)
        parsed.insert(index, _json_fix(_json_valid_return(arg('item'))))
        return _json_dumps(parsed)

    if key.endswith('jsonarraysetlen'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, list):
            return ''
        length = int(_sc_num(arg('len', default=0)))
        if length < 0:
            return ''
        if length > len(parsed):
            parsed.extend([None] * (length - len(parsed)))
        else:
            del parsed[length:]
        return _json_dumps(parsed)

    if key.endswith('jsonarrayset'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, list):
            return ''
        index = int(_sc_num(arg('pos'))) - 1
        if index < 0:
            return _json_dumps(parsed)
        if index >= len(parsed):
            parsed.extend([None] * (index + 1 - len(parsed)))
        parsed[index] = _json_fix(_json_valid_return(arg('item')))
        return _json_dumps(parsed)

    if key.endswith('jsonarraydelete'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, list):
            return ''
        index = int(_sc_num(arg('item'))) - 1
        if index < 0:
            index = max(0, len(parsed) + index)
        if index < len(parsed):
            del parsed[index]
        return _json_dumps(parsed)

    if key.endswith('jsonarrayremoveall'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, list):
            return ''
        wanted = _json_fix(_json_valid_return(arg('item')))
        parsed[:] = [value for value in parsed
                     if not _json_strict_eq(value, wanted)]
        return _json_dumps(parsed)

    if key.endswith('jsonarrayreverse'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, list):
            return ''
        return _json_dumps(list(reversed(parsed)))

    if key.endswith('jsonarrayflat'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, list):
            return ''
        depth = _sc_num(arg('depth', default=2))
        if isinstance(depth, float) and math.isinf(depth):
            depth = 9999
        return _json_dumps(_json_flatten(parsed, int(depth)))

    if key.endswith('jsonarraycreate'):
        text = _sc_str(arg('text'))
        delimiter = _sc_str(arg('d'))
        return _json_dumps(list(text) if delimiter == '' else text.split(delimiter))

    if key.endswith('jsonarrayjoin'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, list):
            return ''
        return _sc_str(arg('d')).join(_json_join_item(item) for item in parsed)

    if key.endswith('jsonarrayfilter'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, list):
            return ''
        name = _sc_str(arg('key'))
        result = []
        for item in parsed:
            found, value = _json_member(item, name)
            result.append(_json_fix(value) if found else None)
        return _json_dumps(result)

    if key.endswith('jsonarraytextfilter'):
        ok, parsed = _json_load(arg('list'))
        if not ok:
            return ''
        option = _sc_str(arg('options', default='includes'))
        text = _sc_str(arg('text'))
        output = _sc_str(arg('type', default='Object'))
        if isinstance(parsed, list):
            entries = [(str(index), value) for index, value in enumerate(parsed)]
            was_array = True
        elif isinstance(parsed, dict):
            entries = list(parsed.items())
            was_array = False
        else:
            return ''
        kept = []
        for name, value in entries:
            if not isinstance(value, str):
                continue
            if option == 'starts with':
                matched = value.startswith(text)
            elif option == 'ends with':
                matched = value.endswith(text)
            else:
                matched = text in value
            if matched:
                kept.append((name, value))
        if output == 'Array':
            return _json_dumps([value for _name, value in kept])
        if was_array and output == 'Object':
            return _json_dumps({str(int(name) + 1): value for name, value in kept})
        return _json_dumps(dict(kept))

    if key.endswith('jsonarraysort'):
        ok, parsed = _json_load(arg('list'))
        if not ok or not isinstance(parsed, list):
            return ''
        ordered = sorted(parsed, key=functools.cmp_to_key(_json_compare))
        if _sc_str(arg('order', default='ascending')) == 'descending':
            ordered.reverse()
        return _json_dumps(ordered)

    if key.endswith('jsonmerge'):
        ok1, first = _json_load(arg('json1'))
        ok2, second = _json_load(arg('json2'))
        if not ok1 or not ok2:
            return ''
        if isinstance(first, list) and isinstance(second, list):
            return _json_dumps(first + second)
        merged = _json_spread(first)
        merged.update(_json_spread(second))
        return _json_dumps(merged)

    if key.endswith('jsonarrayanalysis'):
        ok, parsed = _json_load(arg('list'))
        if not ok or not isinstance(parsed, list):
            return 0
        return _json_analysis(parsed, _sc_str(arg('analysis', default='sum')))

    if key.endswith('jsonvmgetlist') or key.endswith('jsonvmsetlist'):
        target, name = runtime._find_list(sprite, arg('list'))
        if key.endswith('jsonvmgetlist'):
            return _json_dumps(list(target[name])) if target is not None else ''
        ok, parsed = _json_load(arg('json'))
        if target is None or not ok or not isinstance(parsed, list):
            return ''
        values = [_json_dumps(item) if isinstance(item, (dict, list))
                  else _json_fix(item) for item in parsed]
        target[name] = values
        return ''

    if key.endswith('jsonvmexportvar'):
        result = {}
        for name, value in GLOBALS.items():
            if isinstance(value, (str, int, float, bool)):
                result[name] = value
        for name, value in getattr(sprite, '__dict__', {}).items():
            if name.startswith('_') or name in runtime.JSON_BUILTIN_ATTRS:
                continue
            if isinstance(value, (str, int, float, bool)):
                result[name] = value
        return _json_dumps(result)

    if key.endswith('jsonvmimportvar'):
        ok, parsed = _json_load(arg('json'))
        if not ok or not isinstance(parsed, dict):
            return ''
        for name, value in parsed.items():
            attr = _sc_ident(name, 'var')
            if attr in GLOBALS:
                GLOBALS[attr] = value
            elif hasattr(sprite, name):
                setattr(sprite, name, value)
            elif hasattr(sprite, attr):
                setattr(sprite, attr, value)
        return ''

    return 0
