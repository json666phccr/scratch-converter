# -*- coding: utf-8 -*-
"""ScPython（src/scpython）语言与导出测试。"""

import json
import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import *  # noqa: F401,F403

from scpython import (
    ScPythonError, check_project, export_project, import_sb3,
)
from scratch_parser import parse_scratch_project
from scratch_vm import run_project

_STAGE_MIN = """\
init:
    costumes = ["bg.svg"]
"""

_BG_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360">'
    '<rect width="480" height="360" fill="#fff"/></svg>'
)
_CAT_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="80">'
    '<circle cx="50" cy="40" r="30" fill="#fc9"/></svg>'
)


def _write(folder, relative, content, binary=False):
    path = os.path.join(folder, relative)
    os.makedirs(os.path.dirname(path) or folder, exist_ok=True)
    mode = 'wb' if binary else 'w'
    kwargs = {} if binary else {'encoding': 'utf-8'}
    with open(path, mode, **kwargs) as handle:
        handle.write(content)
    return path


def _make_project(folder, files, assets=None):
    for name, content in files.items():
        _write(folder, name, content)
    for name, content in (assets or {}).items():
        _write(folder, os.path.join('assets', name), content)


def _export(folder):
    output = os.path.join(os.path.dirname(folder), 'out.sb3')
    return export_project(folder, output)


def _run(sb3_path):
    # 1.5s 时间盒：0.6s 在负载下会截断 VM 执行（观察到 95/96/98 随机失败）
    return run_project(sb3_path, headless=True, max_seconds=1.5, audio=False)


def _variable(result, sprite_name, variable_name):
    for entry in result['variables']:
        if entry['name'] == sprite_name:
            return entry['variables'].get(variable_name)
    raise AssertionError(f"找不到角色 {sprite_name}")


def _list_value(result, sprite_name, list_name):
    for entry in result['variables']:
        if entry['name'] == sprite_name:
            return entry['lists'].get(list_name)
    raise AssertionError(f"找不到角色 {sprite_name}")


# ===================== 测试 =====================

def test_scpython_end_to_end():
    """SC-1 完整工程：init、变量、列表、宏、自制积木、广播、资产"""
    print("[测试95] ScPython 端到端导出与运行")

    with tempfile.TemporaryDirectory() as folder:
        root = os.path.join(folder, 'demo')
        _make_project(root, {
            'stage.scpy': """\
init:
    costumes = ["bg.svg"]
    extensions = ["pen"]

when green_flag:
    broadcast("go")
""",
            'Cat.scpy': """\
init:
    costumes = ["cat.svg"]
    var score = 0
    list history = []

when green_flag:
    greet("ScPython")
    for i in range(5):
        score += i
        history.append(i)
    say(join("score=", score))
    add_score(3)

when broadcast("go"):
    say("got go")

def add_score(amount, *, types="n", warp=True):
    score += amount
""",
            'macros.scpy': """\
def greet(name, *, types="s"):
    say(join("Hi ", name))
""",
        }, assets={'bg.svg': _BG_SVG, 'cat.svg': _CAT_SVG})

        sb3 = _export(root)
        assert os.path.exists(sb3)

        with zipfile.ZipFile(sb3) as archive:
            names = archive.namelist()
            assert 'project.json' in names
            assets = [name for name in names if name != 'project.json']
            assert len(assets) == 2, assets
            assert all('.' in name for name in assets)

        with zipfile.ZipFile(sb3) as archive:
            data = json.loads(archive.read('project.json').decode('utf-8'))
        meta = data.get('meta') or {}
        import re
        assert re.match(r'^\d+\.\d+\.\d+(-.+)?$', meta.get('vm', '')), meta
        assert re.match(
            r'^\d+\.\d+\.\d+(-.+)?$', meta.get('semver', '')), meta
        for target in data['targets']:
            for costume in target['costumes']:
                assert costume.get('bitmapResolution') == 1, costume
        project = parse_scratch_project(data)
        names = [sprite.name for sprite in project.sprites]
        assert names == ['Stage', 'Cat'], names

        cat = project.sprites[1]
        procedures = [stmt for stmt in cat.statements
                      if stmt.type.name == 'PROCEDURE_DEFINE']
        assert len(procedures) == 2, len(procedures)
        assert cat.costumes and cat.costumes[0]['md5ext'].endswith('.svg')
        assert abs(cat.costumes[0]['rotationCenterX'] - 50) < 1e-6
        assert 'pen' in project.extensions

        result = _run(sb3)
        assert not result['errors'], result['errors']
        assert _variable(result, 'Cat', 'score') == 13
        assert _list_value(result, 'Cat', 'history') == [0, 1, 2, 3, 4]
        assert _variable(result, 'Cat', 'i') == 4

    print("  [PASS] ScPython 端到端通过")
    return True


def test_scpython_scratch_operators():
    """SC-2 ==/!=/join/列表与字符串使用 Scratch 语义"""
    print("[测试96] ScPython Scratch 运算语义")

    with tempfile.TemporaryDirectory() as folder:
        root = os.path.join(folder, 'ops')
        _make_project(root, {
            'stage.scpy': _STAGE_MIN,
            'Cat.scpy': """\
init:
    var a = 0
    var b = 0
    var w = 0
    var joined = ""
    list xs = []

when green_flag:
    if "ABC" == "abc":
        a = 1
    if "1.0" != 1:
        b = 1
    xs.append("a")
    xs.append("b")
    add_to_list(xs, "c")
    if len(xs) == 3 and "b" in xs and item_of(xs, 1) == "a":
        b = 2
    if join("x", 1) == "x1":
        a = 5
    for v in xs:
        joined = join(joined, v)
    while w < 3:
        w += 1
""",
        }, assets={'bg.svg': _BG_SVG})
        sb3 = _export(root)
        result = _run(sb3)
        assert not result['errors'], result['errors']
        assert _variable(result, 'Cat', 'a') == 5
        assert _variable(result, 'Cat', 'b') == 2
        assert _variable(result, 'Cat', 'w') == 3
        assert _variable(result, 'Cat', 'joined') == 'abc'
        assert _list_value(result, 'Cat', 'xs') == ['a', 'b', 'c']

    print("  [PASS] ScPython 运算语义通过")
    return True


def test_scpython_procedure_recursion():
    """SC-3 自制积木元信息、reporter 与递归"""
    print("[测试97] ScPython 自制积木递归")

    with tempfile.TemporaryDirectory() as folder:
        root = os.path.join(folder, 'rec')
        _make_project(root, {
            'stage.scpy': _STAGE_MIN,
            'Cat.scpy': """\
init:
    var result = 0

def fact(n, *, types="n", warp=True):
    if n <= 1:
        return 1
    return n * fact(n - 1)

when green_flag:
    result = fact(5)
    fact(3)
""",
        }, assets={'bg.svg': _BG_SVG})
        sb3 = _export(root)
        with zipfile.ZipFile(sb3) as archive:
            data = json.loads(archive.read('project.json').decode('utf-8'))
        project = parse_scratch_project(data)
        cat = project.sprites[1]
        procedure = next(stmt for stmt in cat.statements
                         if stmt.type.name == 'PROCEDURE_DEFINE')
        assert procedure.extra['proccode'] == 'fact %n'
        assert procedure.extra['arg_types'] == ['n']
        assert procedure.extra['warp'] is True
        # return 依赖 TurboWarp Custom Reporters，必须声明对应扩展
        assert 'procedures_enable_return' in data.get('extensions', []), \
            data.get('extensions')

        # 带返回值的自制积木调用必须是运算块（mutation.return），
        # 且不能出现在堆叠链 next 里
        blocks = data['targets'][1]['blocks']
        reporter_calls = [
            b for b in blocks.values()
            if isinstance(b, dict) and b.get('opcode') == 'procedures_call'
            and (b.get('mutation') or {}).get('return') == 'true']
        assert reporter_calls, 'fact 调用应标记为 reporter'
        for top_id, top in blocks.items():
            if not (isinstance(top, dict) and top.get('topLevel')):
                continue
            cur = top_id
            seen = set()
            while cur in blocks and cur not in seen:
                seen.add(cur)
                cur_block = blocks[cur]
                assert not (cur_block.get('opcode') == 'procedures_call'
                            and (cur_block.get('mutation') or {}).get(
                                'return') == 'true'), cur_block
                cur = cur_block.get('next')
        protos = [b for b in blocks.values()
                  if isinstance(b, dict)
                  and b.get('opcode') == 'procedures_prototype']
        assert protos and all(
            (b.get('mutation') or {}).get('return') == 'true'
            for b in protos), [b.get('mutation') for b in protos]

        result = _run(sb3)
        assert not result['errors'], result['errors']
        assert _variable(result, 'Cat', 'result') == 120

    print("  [PASS] ScPython 自制积木递归通过")
    return True


def test_scpython_break_continue():
    """SC-4 for/while 中的 break/continue"""
    print("[测试98] ScPython break/continue")

    with tempfile.TemporaryDirectory() as folder:
        root = os.path.join(folder, 'flow')
        _make_project(root, {
            'stage.scpy': _STAGE_MIN,
            'Cat.scpy': """\
init:
    var s = 0
    var n = 0

when green_flag:
    for i in range(10):
        if i == 3:
            continue
        if i == 6:
            break
        s += i
    while True:
        n += 1
        if n >= 3:
            break
""",
        }, assets={'bg.svg': _BG_SVG})
        sb3 = _export(root)
        result = _run(sb3)
        assert not result['errors'], result['errors']
        assert _variable(result, 'Cat', 's') == 12
        assert _variable(result, 'Cat', 'n') == 3

    print("  [PASS] ScPython break/continue 通过")
    return True


def test_scpython_recursive_loop_state():
    """SC-4b 递归重入时 break/continue 与循环计数器不能污染外层循环"""
    print("[测试98b] ScPython 递归中的循环状态")

    with tempfile.TemporaryDirectory() as folder:
        root = os.path.join(folder, 'recurse_loop')
        _make_project(root, {
            'stage.scpy': _STAGE_MIN,
            'Cat.scpy': """\
init:
    list trace_log = []

when green_flag:
    rec(1)

def rec(k, *, types="n", warp=True):
    trace_log.append(k)
    for i in range(k, 4):
        trace_log.append(10 + i)
        if i == 2:
            break
        rec(i + 1)
        trace_log.append("back")
    trace_log.append("e")
""",
        }, assets={'bg.svg': _BG_SVG})
        sb3 = _export(root)
        result = _run(sb3)
        assert not result['errors'], result['errors']
        assert _list_value(result, 'Cat', 'trace_log') == [
            1, 11, 2, 12, 'e', 'back', 12, 'e']

    print("  [PASS] ScPython 递归循环状态通过")
    return True


def test_scpython_recursive_while_variable():
    """SC-4c 递归函数里 while 条件用的角色级变量按调用局部语义恢复"""
    print("[测试98c] ScPython 递归中的 while 条件变量")

    with tempfile.TemporaryDirectory() as folder:
        root = os.path.join(folder, 'recurse_while')
        _make_project(root, {
            'stage.scpy': _STAGE_MIN,
            'Cat.scpy': """\
init:
    var k = 1
    list trace_log = []

when green_flag:
    rec()

def rec(*, types="", warp=True):
    trace_log.append(k)
    while k < 3:
        k += 1
        if k == 2:
            rec()
        trace_log.append(10 + k)
    trace_log.append("e")
""",
        }, assets={'bg.svg': _BG_SVG})
        sb3 = _export(root)
        result = _run(sb3)
        assert not result['errors'], result['errors']
        assert _list_value(result, 'Cat', 'trace_log') == [
            1, 2, 13, 'e', 12, 13, 'e']

    print("  [PASS] ScPython 递归 while 条件变量通过")
    return True


def test_scpython_macro_copy():
    """SC-5 宏函数按需复制到角色，局部同名函数优先"""
    print("[测试99] ScPython 宏复制")

    with tempfile.TemporaryDirectory() as folder:
        root = os.path.join(folder, 'macro')
        _make_project(root, {
            'stage.scpy': _STAGE_MIN,
            'macros.scpy': """\
def twice(x, *, types="n"):
    return x * 2

def quad(x, *, types="n"):
    return twice(twice(x))
""",
            'A.scpy': """\
when green_flag:
    say(quad(2))
""",
            'B.scpy': """\
def twice(x, *, types="n"):
    return x * 3

when green_flag:
    say(twice(2))
""",
            'C.scpy': """\
when green_flag:
    say("nothing")
""",
        }, assets={'bg.svg': _BG_SVG})
        sb3 = _export(root)
        with zipfile.ZipFile(sb3) as archive:
            data = json.loads(archive.read('project.json').decode('utf-8'))
        project = parse_scratch_project(data)
        by_name = {sprite.name: sprite for sprite in project.sprites}

        def proccodes(sprite):
            return sorted(
                stmt.extra.get('proccode') for stmt in sprite.statements
                if stmt.type.name == 'PROCEDURE_DEFINE')

        assert proccodes(by_name['A']) == ['quad %n', 'twice %n']
        assert proccodes(by_name['B']) == ['twice %n']
        assert proccodes(by_name['C']) == []

    print("  [PASS] ScPython 宏复制通过")
    return True


def test_scpython_nested_and_global():
    """SC-6 嵌套工程目录命名、全局变量共享与资产去重"""
    print("[测试100] ScPython 嵌套目录与全局变量")

    with tempfile.TemporaryDirectory() as folder:
        root = os.path.join(folder, 'nested')
        _make_project(root, {
            'stage.scpy': """\
init:
    costumes = ["bg.svg"]
    var g = 0
""",
            'units/Bat.scpy': """\
init:
    costumes = ["bg.svg"]

when green_flag:
    g += 10
""",
        }, assets={'bg.svg': _BG_SVG})
        sb3 = _export(root)
        with zipfile.ZipFile(sb3) as archive:
            data = json.loads(archive.read('project.json').decode('utf-8'))
        project = parse_scratch_project(data)
        assert [sprite.name for sprite in project.sprites] == [
            'Stage', 'units//Bat']
        assert project.stage.variables == {'g': 0}
        # 两个角色引用同一资产，只应导出一份
        assets = [name for name in zipfile.ZipFile(sb3).namelist()
                  if name != 'project.json']
        assert len(assets) == 1, assets

        result = _run(sb3)
        assert not result['errors'], result['errors']
        assert _variable(result, 'Stage', 'g') == 10

    print("  [PASS] ScPython 嵌套目录与全局变量通过")
    return True


def test_scpython_custom_extensions():
    """SC-7 extensions.json 自定义扩展、ext() 与 pen 内置封装"""
    print("[测试101] ScPython 自定义扩展")

    with tempfile.TemporaryDirectory() as folder:
        root = os.path.join(folder, 'ext')
        _make_project(root, {
            'stage.scpy': _STAGE_MIN,
            'extensions.json': json.dumps({
                'myext': {
                    'jump': {
                        'opcode': 'myext_jump',
                        'inputs': ['HEIGHT'],
                        'fields': {'MODE': 'MODE'},
                    },
                    'speed': {
                        'opcode': 'myext_getSpeed',
                        'expr': True,
                    },
                },
            }),
            'Cat.scpy': """\
init:
    var v = 0

when green_flag:
    myext.jump(10, MODE="fast")
    v = myext.speed()
    ext("other", "other_do", VALUE=1)
    pen_down()
""",
        }, assets={'bg.svg': _BG_SVG})
        sb3 = _export(root)
        with zipfile.ZipFile(sb3) as archive:
            data = json.loads(archive.read('project.json').decode('utf-8'))
        extensions = set(data['extensions'])
        assert {'myext', 'other', 'pen'} <= extensions, extensions

        opcodes = set()
        fields = {}
        for target in data['targets']:
            for block in (target.get('blocks') or {}).values():
                if not isinstance(block, dict):
                    continue
                opcodes.add(block.get('opcode'))
                if block.get('opcode') == 'myext_jump':
                    fields.update(block.get('fields') or {})
        assert {'myext_jump', 'myext_getSpeed', 'other_do',
                'pen_down'} <= opcodes, opcodes
        assert fields['MODE'][0] == 'fast'

    print("  [PASS] ScPython 自定义扩展通过")
    return True


def test_scpython_hats_and_init():
    """SC-8 各种事件头与 init 元数据"""
    print("[测试102] ScPython 事件头与 init")

    with tempfile.TemporaryDirectory() as folder:
        root = os.path.join(folder, 'hats')
        _make_project(root, {
            'stage.scpy': _STAGE_MIN,
            'Cat.scpy': """\
def init():
    costumes = ["cat.svg"]
    x = 10
    y = -20
    direction = 180
    visible = False
    size = 50
    rotation_style = "left-right"
    draggable = True

when key_pressed("space"):
    say("key")

when backdrop_switches_to("bg"):
    say("backdrop")

when timer > 5:
    say("timer")

when clicked:
    say(join(username(), backdrop_name()))
""",
        }, assets={'bg.svg': _BG_SVG, 'cat.svg': _CAT_SVG})
        sb3 = _export(root)
        with zipfile.ZipFile(sb3) as archive:
            data = json.loads(archive.read('project.json').decode('utf-8'))
        project = parse_scratch_project(data)
        cat = next(sprite for sprite in project.sprites
                   if sprite.name == 'Cat')
        assert cat.x == 10 and cat.y == -20
        assert cat.direction == 180
        assert cat.visible is False
        assert cat.size == 50
        assert cat.rotation_style == 'left-right'
        assert cat.draggable is True
        opcodes = set()
        for target in data['targets']:
            for block in (target.get('blocks') or {}).values():
                if isinstance(block, dict):
                    opcodes.add(block.get('opcode'))
        assert 'event_whenkeypressed' in opcodes
        assert 'event_whenbackdropswitchesto' in opcodes
        assert 'event_whengreaterthan' in opcodes
        assert 'event_whenthisspriteclicked' in opcodes
        assert 'sensing_username' in opcodes
        assert 'looks_backdropnumbername' in opcodes

    print("  [PASS] ScPython 事件头与 init 通过")
    return True


def test_scpython_rejects_advanced_syntax():
    """SC-9 拒绝 class/装饰器/字典/集合/f-string/字符串方法/切片"""
    print("[测试103] ScPython 语法限制")

    cases = {
        'class': "class X:\n    pass\n",
        'decorator': "@deco\ndef f():\n    pass\n",
        'dict': "init:\n    var d = {}\n",
        'set': "init:\n    var s = {1}\n",
        'fstring': 'when green_flag:\n    say(f"{1}")\n',
        'string_method': 'when green_flag:\n    say("a".upper())\n',
        'slice': "init:\n    list xs = []\n\nwhen green_flag:\n"
                 "    say(item_of(xs, 1))\n    xs[1:2]\n",
    }
    for label, body in cases.items():
        with tempfile.TemporaryDirectory() as folder:
            root = os.path.join(folder, label)
            files = {'stage.scpy': _STAGE_MIN}
            if label in ('class', 'decorator', 'dict', 'set'):
                files['Bad.scpy'] = body
            else:
                files['Bad.scpy'] = body
            _make_project(root, files, assets={'bg.svg': _BG_SVG})
            try:
                check_project(root)
            except ScPythonError:
                continue
            raise AssertionError(f"{label} 应被拒绝")

    print("  [PASS] ScPython 语法限制通过")
    return True


def _patch_sb3_comments(sb3_path, target_name, text, standalone_text):
    """给导出的 sb3 注入一条附着注释和一条独立注释"""
    with zipfile.ZipFile(sb3_path) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    data = json.loads(entries['project.json'].decode('utf-8'))
    target = next(t for t in data['targets'] if t.get('name') == target_name)
    blocks = target.get('blocks') or {}
    say_ids = [bid for bid, block in blocks.items()
               if isinstance(block, dict) and block.get('opcode') == 'looks_say']
    assert say_ids, "测试工程里应有一个 say 块"
    block_id = say_ids[-1]  # 取脚本里的 say，避免挂到重复积木上
    comments = target.setdefault('comments', {})
    comments['c_attached'] = {
        'blockId': block_id, 'x': 0, 'y': 0, 'width': 200, 'height': 100,
        'minimized': False, 'text': text,
    }
    comments['c_standalone'] = {
        'blockId': None, 'x': 0, 'y': 0, 'width': 200, 'height': 100,
        'minimized': False, 'text': standalone_text,
    }
    entries['project.json'] = json.dumps(data).encode('utf-8')
    with zipfile.ZipFile(sb3_path, 'w') as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)


def test_scpython_sb3_import_roundtrip():
    """SC-10 sb3 -> ScPython：注释、全局变量、相同自制积木抽到 macros"""
    print("[测试104] ScPython sb3 导入往返与宏拆分")

    with tempfile.TemporaryDirectory() as folder:
        root = os.path.join(folder, 'round')
        _make_project(root, {
            'stage.scpy': """\
init:
    costumes = ["bg.svg"]
    extensions = ["myext"]
    var g = 0
""",
            'extension_urls.json': json.dumps({
                'myext': 'https://extensions.turbowarp.org/demo.js',
            }),
            'A.scpy': """\
init:
    costumes = ["cat.svg", "bg.svg"]
    costume_names = ["猫", "背景图"]
    current_costume = 1
    layer_order = 7
    var score = 0
    variable_aliases = [["score", "得:分"]]

def spin(speed, *, types="n", warp=True):
    set_rotation_style("all around")
    turn_right(speed)

def orphan(*, warp=True):
    say("dead")

when green_flag:
    g += 1
    spin(15)
    score += 1
    for _ in range(2):
        say("loop")
    ext("myext", "myext_do", MODE="fast", _fields=["MODE"])
    ext("myext", "myext_pick", extension=".mp3", _inputs=[["as", "url"]])
    while not (score > 3):
        score += 1
    goto_target("B")
    say("A")
""",
            'units/Bat.scpy': """\
init:
    costumes = ["cat.svg"]

when green_flag:
    say("bat")
""",
            'Win-Dow.scpy': """\
init:
    costumes = ["bg.svg"]
""",
            'B.scpy': """\
init:
    costumes = ["cat.svg"]

def spin(speed, *, types="n", warp=True):
    set_rotation_style("all around")
    turn_right(speed)

def orphan(*, warp=True):
    say("dead")

when green_flag:
    g += 2
    spin(30)
    say("B")
""",
        }, assets={'bg.svg': _BG_SVG, 'cat.svg': _CAT_SVG})
        sb3 = _export(root)
        with zipfile.ZipFile(sb3) as archive:
            data = json.loads(archive.read('project.json').decode('utf-8'))
        assert 'myext' in data.get('extensions', [])
        assert data.get('extensionURLs', {}).get('myext') == \
            'https://extensions.turbowarp.org/demo.js', data.get('extensionURLs')
        pick_inputs = {}
        for target in data['targets']:
            for block in (target.get('blocks') or {}).values():
                if isinstance(block, dict) and \
                        block.get('opcode') == 'myext_pick':
                    pick_inputs = block.get('inputs') or {}
        assert 'as' in pick_inputs, pick_inputs
        _patch_sb3_comments(sb3, 'A', '旋转一次', '独立说明')

        imported = os.path.join(folder, 'imported')
        import_sb3(sb3, imported, split_macros=True)
        with open(os.path.join(imported, 'extension_urls.json'),
                  encoding='utf-8') as handle:
            urls = json.load(handle)
        assert urls.get('myext') == 'https://extensions.turbowarp.org/demo.js'

        with open(os.path.join(imported, 'macros.scpy'),
                  encoding='utf-8') as handle:
            macros = handle.read()
        assert 'def spin(speed' in macros, macros
        assert 'def orphan' in macros, macros
        with open(os.path.join(imported, 'comments.json'),
                  encoding='utf-8') as handle:
            saved_comments = json.load(handle)
        assert '旋转一次' in json.dumps(saved_comments, ensure_ascii=False)
        assert os.path.exists(os.path.join(imported, 'costume_meta.json'))

        a_source = open(os.path.join(imported, 'A.scpy'),
                        encoding='utf-8').read()
        b_source = open(os.path.join(imported, 'B.scpy'),
                        encoding='utf-8').read()
        stage_source = open(os.path.join(imported, 'stage.scpy'),
                            encoding='utf-8').read()
        assert 'def spin' not in a_source
        assert 'def spin' not in b_source
        assert "macros = ['orphan', 'spin']" in a_source, a_source
        assert 'variable_aliases' in a_source, a_source
        assert "_inputs=[['as', 'url']]" in a_source, a_source
        assert ' as=' not in a_source, a_source
        assert 'spin(15)' in a_source
        assert 'spin(30)' in b_source
        # 移到指定角色不能退化成 TODO
        assert "goto_target('B')" in a_source, a_source
        assert '# TODO goto' not in a_source
        # repeat_until 往返不应叠加 not
        assert 'while not (not' not in a_source, a_source
        bat_path = os.path.join(imported, 'units', 'Bat.scpy')
        assert os.path.exists(bat_path), bat_path
        assert "name = 'units//Bat'" in open(
            bat_path, encoding='utf-8').read()
        # 造型名/当前造型/图层顺序/角色名必须保留
        assert "costume_names = ['猫', '背景图']" in a_source, a_source
        assert 'current_costume = 1' in a_source
        assert 'layer_order = 7' in a_source
        win_source = open(os.path.join(imported, 'Win_Dow.scpy'),
                          encoding='utf-8').read()
        assert "name = 'Win-Dow'" in win_source, win_source
        # 注释：附着在 say 前，独立注释在文件头
        assert '# 旋转一次' in a_source, a_source
        assert '# 独立说明' in a_source, a_source
        # 全局变量只在舞台声明
        assert 'var g' in stage_source
        assert 'var g' not in a_source
        assert 'var g' not in b_source

        # 再导出，宏应合并回每个角色
        sb3_again = os.path.join(folder, 'again.sb3')
        export_project(imported, sb3_again)
        with zipfile.ZipFile(sb3_again) as archive:
            data = json.loads(archive.read('project.json').decode('utf-8'))
        project = parse_scratch_project(data)
        assert data.get('extensionURLs', {}).get('myext') == \
            'https://extensions.turbowarp.org/demo.js', data.get('extensionURLs')
        targets = {target['name']: target for target in data['targets']}
        assert 'Win-Dow' in targets, list(targets)
        assert 'units//Bat' in targets, list(targets)

        def _not_count(payload):
            return sum(
                1 for target in payload['targets']
                for block in (target.get('blocks') or {}).values()
                if isinstance(block, dict)
                and block.get('opcode') == 'operator_not')

        with zipfile.ZipFile(sb3) as archive:
            first_data = json.loads(archive.read('project.json').decode('utf-8'))
        assert _not_count(data) == _not_count(first_data)

        goto_blocks = [
            block for target in data['targets']
            for block in (target.get('blocks') or {}).values()
            if isinstance(block, dict) and block.get('opcode') == 'motion_goto']
        assert len(goto_blocks) == 1, goto_blocks

        sprite_a = targets['A']
        assert sprite_a['currentCostume'] == 1, sprite_a['currentCostume']
        assert sprite_a['layerOrder'] == 7, sprite_a['layerOrder']
        assert [c['name'] for c in sprite_a['costumes']] == ['猫', '背景图']
        by_name = {sprite.name: sprite for sprite in project.sprites}
        for name in ('A', 'B'):
            proccodes = sorted(
                stmt.extra.get('proccode')
                for stmt in by_name[name].statements
                if stmt.type.name == 'PROCEDURE_DEFINE')
            assert proccodes == ['orphan', 'spin %n'], (name, proccodes)

        # 变量原名、扩展字段与注释都应保留
        assert '得:分' in {value[0] for value in
                          sprite_a['variables'].values()}, sprite_a['variables']
        comments = sum(len(target.get('comments') or {})
                       for target in data['targets'])
        assert comments == 2, comments
        ext_fields = {}
        for target in data['targets']:
            for block in (target.get('blocks') or {}).values():
                if isinstance(block, dict) and block.get('opcode') == 'myext_do':
                    ext_fields = block.get('fields') or {}
        assert ext_fields.get('MODE') == ['fast', None], ext_fields
        pick_again = {}
        for target in data['targets']:
            for block in (target.get('blocks') or {}).values():
                if isinstance(block, dict) and \
                        block.get('opcode') == 'myext_pick':
                    pick_again = block.get('inputs') or {}
        assert 'as' in pick_again, pick_again

        # 造型旋转中心与分辨率必须保持
        first = {target['name']: {c['md5ext']: (
            c.get('rotationCenterX'), c.get('rotationCenterY'),
            c.get('bitmapResolution')) for c in target['costumes']}
            for target in json.loads(
                zipfile.ZipFile(sb3).read('project.json')).get('targets', [])}
        again = {target['name']: {c['md5ext']: (
            c.get('rotationCenterX'), c.get('rotationCenterY'),
            c.get('bitmapResolution')) for c in target['costumes']}
            for target in data['targets']}
        assert first == again

        result = _run(sb3_again)
        assert not result['errors'], result['errors']
        assert _variable(result, 'Stage', 'g') == 3

    print("  [PASS] sb3 导入往返与宏拆分通过")
    return True


def test_scpython_import_without_macros():
    """SC-11 --no-macros 时相同自制积木保留在各角色文件中"""
    print("[测试105] ScPython 导入 --no-macros")

    with tempfile.TemporaryDirectory() as folder:
        root = os.path.join(folder, 'plain')
        _make_project(root, {
            'stage.scpy': _STAGE_MIN,
            'A.scpy': """\
def ping(*, warp=True):
    say("ping")

when green_flag:
    ping()
""",
            'B.scpy': """\
def ping(*, warp=True):
    say("ping")

when green_flag:
    ping()
""",
        }, assets={'bg.svg': _BG_SVG})
        sb3 = _export(root)
        imported = os.path.join(folder, 'imported')
        import_sb3(sb3, imported, split_macros=False)
        assert not os.path.exists(os.path.join(imported, 'macros.scpy'))
        for name in ('A', 'B'):
            source = open(os.path.join(imported, name + '.scpy'),
                          encoding='utf-8').read()
            assert 'def ping' in source, source

    print("  [PASS] 导入 --no-macros 通过")
    return True


def test_scpython_txt_and_debug():
    """SC-12 txt 列表默认值、debug.set_default/import_list/set_var/reset"""
    print("[测试106] ScPython txt 与 debug 调试方法")

    with tempfile.TemporaryDirectory() as folder:
        root = os.path.join(folder, 'debug')
        _write(root, 'words.txt', 'alpha\nbeta\ngamma\n')
        _make_project(root, {
            'stage.scpy': _STAGE_MIN,
            'Cat.scpy': """\
init:
    costumes = ["cat.svg"]
    list words = txt("words.txt")
    debug.import_list(names, "words.txt")
    debug.set_default(score, 7)
    debug.set_list_default(nums, [1, 2, 3])

when green_flag:
    score = 99
    words.append("extra")
    for w in words:
        nums.append(w)
    debug.set_var(score, 42)
    debug.print("score before reset")
    debug.reset(score)
    debug.reset(words)
    debug.reset(nums)
    debug.trace("重置完成")
""",
        }, assets={'bg.svg': _BG_SVG, 'cat.svg': _CAT_SVG})
        sb3 = _export(root)
        result = _run(sb3)
        assert not result['errors'], result['errors']
        assert _list_value(result, 'Cat', 'words') == [
            'alpha', 'beta', 'gamma']
        assert _list_value(result, 'Cat', 'names') == [
            'alpha', 'beta', 'gamma']
        assert _list_value(result, 'Cat', 'nums') == [1, 2, 3]
        assert _variable(result, 'Cat', 'score') == 7

    print("  [PASS] txt 与 debug 调试方法通过")
    return True


def test_scpython_lint():
    """SC-13 lint 报告未使用的变量/列表/自制积木/宏"""
    print("[测试107] ScPython lint 静态检查")

    from scpython import lint_project

    with tempfile.TemporaryDirectory() as folder:
        root = os.path.join(folder, 'lint')
        _make_project(root, {
            'stage.scpy': """\
init:
    costumes = ["bg.svg"]
    var unused_g = 0
    var shared = 0
""",
            'Cat.scpy': """\
init:
    costumes = ["cat.svg"]
    var used = 0
    list unused_list = []

def orphan():
    say("x")

when green_flag:
    used += 1
    say(used)
    say(shared)
""",
            'macros.scpy': """\
def unused_macro():
    say("m")
""",
        }, assets={'bg.svg': _BG_SVG, 'cat.svg': _CAT_SVG})
        issues = lint_project(root)
        codes = {issue.code for issue in issues}
        assert {'W001', 'W002', 'W003', 'W004'} <= codes, [
            str(issue) for issue in issues]
        messages = ' '.join(str(issue) for issue in issues)
        assert 'unused_g' in messages
        assert 'shared' not in messages  # 舞台全局变量被角色使用
        assert 'unused_list' in messages
        assert 'orphan' in messages
        assert 'unused_macro' in messages

    print("  [PASS] ScPython lint 通过")
    return True


def test_scpython_cli_run():
    """SC-14 scpython run 无头运行并输出变量"""
    print("[测试108] ScPython CLI 无头运行")

    import contextlib
    import io

    from scpython.cli import main as cli_main

    with tempfile.TemporaryDirectory() as folder:
        root = os.path.join(folder, 'run')
        _make_project(root, {
            'stage.scpy': _STAGE_MIN,
            'Cat.scpy': """\
init:
    costumes = ["cat.svg"]
    var score = 0

when green_flag:
    score = 42
""",
        }, assets={'bg.svg': _BG_SVG, 'cat.svg': _CAT_SVG})

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = cli_main(['run', root, '--seconds', '0.4'])
        assert code == 0
        output = buffer.getvalue()
        assert '变量 score = 42' in output, output

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = cli_main(['run', root, '--seconds', '0.4', '--trace', '3'])
        assert code == 0
        assert '[trace]' in buffer.getvalue()

    print("  [PASS] ScPython CLI 无头运行通过")
    return True


TESTS = [
    test_scpython_end_to_end,
    test_scpython_scratch_operators,
    test_scpython_procedure_recursion,
    test_scpython_break_continue,
    test_scpython_macro_copy,
    test_scpython_nested_and_global,
    test_scpython_custom_extensions,
    test_scpython_hats_and_init,
    test_scpython_rejects_advanced_syntax,
    test_scpython_sb3_import_roundtrip,
    test_scpython_import_without_macros,
    test_scpython_txt_and_debug,
    test_scpython_lint,
    test_scpython_cli_run,
]
