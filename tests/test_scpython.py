# -*- coding: utf-8 -*-
"""ScPython（src/scpython）语言与导出测试。"""

import json
import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import *  # noqa: F401,F403

from scpython import ScPythonError, check_project, export_project
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
    return run_project(sb3_path, headless=True, max_seconds=0.6, audio=False)


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
    say("clicked")
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
]
