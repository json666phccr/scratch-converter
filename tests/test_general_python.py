# -*- coding: utf-8 -*-
"""由 test_all.py 拆分出的测试模块"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import *


def test_general_python_mode():
    print("[测试39] 通用Python -> Scratch")
    from general_python import parse_general_project

    code = '''
total = 0
nums = [1, 2, 3, 4]
for n in nums:
    total += n
print("sum", total)

def fib(n):
    a = 0
    b = 1
    i = 0
    while i < n:
        t = a + b
        a = b
        b = t
        i += 1
    return a

x = fib(6)
print("fib", x)
'''
    project = parse_general_project(code, 'PyTest')
    assert project.sprites[0].is_stage, "通用模式必须生成舞台"
    assert project.assets, "必须输出默认造型资源"
    sprite = [item for item in project.sprites if not item.is_stage][0]
    assert sprite.costumes, "精灵必须有默认造型"

    data = write_scratch_project(project)
    assert data['targets'][0]['isStage']
    opcodes = {}
    for target in data['targets']:
        for block in target['blocks'].values():
            opcodes[block['opcode']] = opcodes.get(block['opcode'], 0) + 1
    for expected in ('event_whenflagclicked', 'control_repeat',
                     'data_lengthoflist', 'data_itemoflist',
                     'data_changevariableby', 'procedures_definition',
                     'procedures_call', 'control_repeat_until', 'looks_say'):
        assert expected in opcodes, f"缺少积木: {expected}"
    assert not project.warnings, f"简单脚本不应有未支持特性: {project.warnings}"
    definitions = [block for target in data['targets']
                   for block in target['blocks'].values()
                   if block['opcode'] == 'procedures_definition']
    assert definitions, "必须生成自制积木定义"
    assert all(block.get('topLevel') and block.get('x') is not None
               for block in definitions), "自制积木定义必须是带坐标的顶层脚本"
    print("  [PASS] 通用Python转换通过")
    return True


def test_general_python_more_syntax():
    print("[测试40] 通用Python更多语法")
    from general_python import parse_general_project

    code = '''
a = b = 2
a -= 1
a *= 3
a //= 2
a %= 2
nums = [1, 2, 3, 4]
del nums[0]
nums[0] = 20
count = 0
for i in range(0, 6, 2):
    count += i
n = 10
total = 0
for i in range(0, n, 3):
    total += i
print(f"count={count}, total={total}")
print("a=" + str(a))
print("in list:", 20 in nums, 99 not in nums)
print("chain:", 0 < a <= 3)
'''
    project = parse_general_project(code, 'SyntaxTest')
    assert not project.warnings, f"不应有未支持特性: {project.warnings}"
    data = write_scratch_project(project)
    opcodes = {}
    for target in data['targets']:
        for block in target['blocks'].values():
            opcodes[block['opcode']] = opcodes.get(block['opcode'], 0) + 1
    for expected in ('operator_mod', 'operator_mathop',
                     'data_deleteoflist', 'data_listcontainsitem',
                     'operator_and', 'operator_join'):
        assert expected in opcodes, f"缺少积木: {expected}"
    assert opcodes.get('data_setvariableto', 0) >= 3, "链式赋值应生成多个设为块"
    print("  [PASS] 通用Python更多语法通过")
    return True


def test_general_python_break_continue():
    print("[测试41] 通用Python break/continue")
    from general_python import parse_general_project

    code = '''
nums = []
for i in range(10):
    if i == 3:
        continue
    if i == 7:
        break
    nums.append(i)

total = 0
i = 0
while i < 10:
    i += 1
    if i % 2 == 0:
        continue
    if i > 7:
        break
    total += i

count = 0
for x in [1, 2, 3, 4, 5]:
    if x == 4:
        break
    count += x
print(nums, total, count)
'''
    project = parse_general_project(code, 'BreakTest')
    assert not project.warnings, f"不应有未支持特性: {project.warnings}"
    data = write_scratch_project(project)
    opcodes = {}
    variables = []
    for target in data['targets']:
        variables.extend(name for name, _ in target.get('variables', {}).values())
        for block in target['blocks'].values():
            opcodes[block['opcode']] = opcodes.get(block['opcode'], 0) + 1
    assert any(name.startswith('__py_break_') for name in variables)
    assert any(name.startswith('__py_continue_') for name in variables)
    assert 'control_repeat_until' in opcodes
    assert 'operator_or' in opcodes
    assert 'operator_not' in opcodes
    print("  [PASS] 通用Python break/continue 通过")
    return True


def test_general_python_builtins_and_methods():
    """通用模式：**、min/max/sum、列表方法、join、enumerate/字符串循环、列表拷贝"""
    print("[测试42] 通用Python内置函数与列表方法")
    from general_python import parse_general_project

    code = '''
nums = [3, 1, 4, 1, 5]
total = sum(nums)
lo = min(nums)
hi = max(nums)
low2 = min(3, 8)
high2 = max(3, 8)
nums.sort()
sorted_first = nums[0]
nums.reverse()
reversed_first = nums[0]
last = nums.pop()
idx = nums.index(4)
cnt = nums.count(4)
nums.remove(1)
remaining = len(nums)
power = 2 ** 5
power2 = 3 ** 2
mod_power = 2
mod_power **= 3
b = [10, 20, 30]
joined = "-".join(b)
has_ell = "ell" in "hello"
no_z = "z" not in "hello"
pi_part = math.pi
count = 0
for i, v in enumerate(b):
    count += i * v
chars = []
for ch in "abc":
    chars.append(ch)
indexes = []
for i, ch in enumerate("xy"):
    indexes.append(i)
alias = b
alias_lo = min(alias)
text = "abc"
out = ""
for ch in text:
    if ch == "b":
        continue
    out = out + ch
x, y = 1, 2
x, y = y, x
print("done")
'''
    project = parse_general_project(code, 'BatchTest')
    assert not project.warnings, f"不应有未支持特性: {project.warnings}"

    data = write_scratch_project(project)
    opcodes = {}
    for target in data['targets']:
        for block in target['blocks'].values():
            opcodes[block['opcode']] = opcodes.get(block['opcode'], 0) + 1
    for expected in ('operator_mathop', 'operator_contains', 'operator_join',
                     'data_itemoflist', 'data_replaceitemoflist',
                     'data_deleteoflist', 'data_lengthoflist',
                     'data_addtolist', 'control_repeat_until'):
        assert expected in opcodes, f"缺少积木: {expected}"

    # 端到端：sb3 -> Python -> pygame 运行时，验证真实执行结果
    exec_code = generate_python(parse_scratch_project(data))
    namespace = {}
    exec(compile(exec_code, "<generated>", "exec"), namespace)

    import time
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite = namespace["BatchTest"]()
    runtime.add_sprite(sprite)
    try:
        runtime.start(max_frames=4)
        time.sleep(0.2)
        expected_values = {
            'total': 14, 'lo': 1, 'hi': 5, 'low2': 3, 'high2': 8,
            'sorted_first': 1, 'reversed_first': 5, 'last': 1, 'idx': 2,
            'cnt': 1, 'remaining': 3, 'power': 32, 'power2': 9,
            'mod_power': 8, 'count': 80, 'alias_lo': 10, 'x': 2, 'y': 1,
        }
        for name, expected in expected_values.items():
            actual = getattr(sprite, name)
            assert float(actual) == float(expected), \
                f"{name}: 期望 {expected}, 实际 {actual}"
        assert str(sprite.joined) == '10-20-30', \
            f"join 结果不正确: {sprite.joined}"
        assert str(sprite.out) == 'ac', \
            f"字符串变量累加应为拼接: {sprite.out!r}"
        assert bool(sprite.has_ell) is True, "字符串包含应成立"
        assert bool(sprite.no_z) is True, "字符串不包含应成立"
        assert abs(float(sprite.pi_part) - math.pi) < 1e-9, "math.pi 应保真"
        assert list(sprite.chars) == ['a', 'b', 'c'], "字符串遍历结果不正确"
        assert [float(v) for v in sprite.indexes] == [0.0, 1.0], \
            "enumerate 下标应从 0 开始"
        assert [float(v) for v in sprite.nums] == [5.0, 4.0, 3.0], \
            "sort/reverse/pop/remove 后的列表不正确"
        assert [float(v) for v in sprite.alias] == [10.0, 20.0, 30.0], \
            "列表拷贝不应共享内容"
    finally:
        runtime.shutdown()

    print("  [PASS] 通用Python内置函数与列表方法通过")
    return True


def test_general_python_extended_syntax():
    """通用模式第二批语法：sorted/reversed/enumerate(start)、random、time.sleep、
    条件表达式、round 位数、pow、f-string 格式、列表 copy/extend"""
    print("[测试57] 通用Python扩展语法")
    from general_python import parse_general_project

    code = '''
import math
import random
import time

nums = [3, 1, 2]
nums.sort()
nums.extend([9, 10])
copy_nums = nums.copy()
sorted_copy = sorted(nums)
reversed_copy = reversed(nums)

for n in sorted(nums, reverse=True):
    print(n)
for i, n in enumerate(nums, 1):
    print(i, n)
for n in reversed(nums):
    print(n)

x = 10 if len(nums) > 3 else 0
y = round(3.14159, 2)
z = random.randint(1, 6)
r = random.random()
u = random.uniform(1, 2)
c = random.choice(nums)
p = pow(2, 10)
f = math.fabs(-3)
time.sleep(0.01)
print(f"{y:.2f}")
'''
    project = parse_general_project(code, 'Syntax2')
    assert not project.warnings, f"不应有未支持特性: {project.warnings}"

    data = write_scratch_project(project)
    opcodes = {}
    for target in data['targets']:
        for block in target['blocks'].values():
            opcodes[block['opcode']] = opcodes.get(block['opcode'], 0) + 1
    for expected in ('operator_random', 'control_wait', 'operator_round',
                     'operator_mathop', 'data_addtolist',
                     'data_deletealloflist', 'control_repeat'):
        assert expected in opcodes, f"缺少积木: {expected}"

    print("  [PASS] 通用Python扩展语法通过")
    return True


def test_general_python_recursion_and_more_syntax():
    """递归（含互递归与局部变量）以及切片/推导式/zip 等常见语法"""
    print("[测试88] 通用Python递归与更多语法")
    from general_python import parse_general_project
    from python_generator import generate_python

    code = '''
data = [1, 2, 3, 4]

def fact(n):
    if n <= 1:
        return 1
    return n * fact(n - 1)

def fib(n):
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)

def sum_list(n):
    if n <= 0:
        return 0
    total = data[n - 1]
    return total + sum_list(n - 1)

def is_even(n):
    if n == 0:
        return 1
    return is_odd(n - 1)

def is_odd(n):
    if n == 0:
        return 0
    return is_even(n - 1)

def digits(n):
    result = ""
    while n > 0:
        result = str(n) + result
        n = n - 1
    return result

def reverse_text(s):
    if s == "":
        return ""
    return reverse_text(s[1:]) + s[0]

def count_char(s, ch):
    if s == "":
        return 0
    hit = 1 if s[0] == ch else 0
    return hit + count_char(s[1:], ch)

text = "hello"
first = text[0]
last = text[-1]
mid = text[1:4]
line = "-" * 3

nums = [1, 2, 3]
doubled = [x * 2 for x in nums]
positive = [n + 10 for n in range(3) if n > 0]
part = nums[1:3]
shuffle_nums = [1, 2, 3, 4]
random.shuffle(shuffle_nums)

xs = [1, 2]
ys = [3, 4]
total_xy = 0
for a, b in zip(xs, ys):
    total_xy += a * b

answer = fact(5)
f6 = fib(6)
s = sum_list(4)
even = is_even(6)
digits_text = digits(3)
reversed_text = reverse_text("abcde")
hits = count_char("banana", "a")
'''
    project = parse_general_project(code, 'Recursion')
    assert not project.warnings, f"不应有未支持特性: {project.warnings}"

    generated = generate_python(project)
    assert 'var_answer' in generated, "answer 与运行时属性重名，应改用隐藏属性"
    assert generated.count('__py_frame_') > 0, "递归函数应生成帧栈"

    data = write_scratch_project(project)
    opcodes = set()
    for target in data['targets']:
        for block in target['blocks'].values():
            opcodes.add(block['opcode'])
    for expected in ('data_addtolist', 'data_replaceitemoflist',
                     'data_deleteoflist', 'data_itemoflist', 'procedures_call'):
        assert expected in opcodes, f"缺少积木: {expected}"

    def run_green(source):
        namespace = {}
        exec(compile(source, '<generated>', 'exec'), namespace)
        runtime = namespace['ScratchRuntime'](headless=True, audio=False)
        sprite = namespace['Recursion']()
        runtime.add_sprite(sprite)
        try:
            sprite.run()
            runtime.green_flag()
            for _ in range(120):
                runtime.step()
                import time
                time.sleep(0.004)
                if getattr(sprite, 'digits_text', None) \
                        and getattr(sprite, 'hits', 0) == 3:
                    break
            return sprite
        finally:
            runtime.running = False
            runtime.shutdown()

    sprite = run_green(generated)
    assert sprite.var_answer == 120, "递归阶乘结果"
    assert sprite.f6 == 8, "递归斐波那契结果"
    assert sprite.s == 10, "递归函数的局部变量应按每次调用隔离"
    assert sprite.even == 1, "互递归结果"
    assert sprite.digits_text == '123'
    assert sprite.reversed_text == 'edcba', "递归 + 字符串切片"
    assert sprite.hits == 3, "递归 + 字符串下标"
    assert sprite.first == 'h' and sprite.last == 'o'
    assert sprite.mid == 'ell' and sprite.line == '---'
    assert sprite.doubled == [2, 4, 6]
    assert sprite.positive == [11, 12]
    assert sprite.part == [2, 3]
    assert sorted(sprite.shuffle_nums) == [1, 2, 3, 4]
    assert sprite.total_xy == 11

    # 写回 sb3 后再转换，帧栈与递归语义仍要成立
    roundtrip = generate_python(parse_scratch_project(data))
    sprite = run_green(roundtrip)
    assert sprite.var_answer == 120
    assert sprite.f6 == 8
    assert sprite.s == 10

    print("  [PASS] 通用Python递归与更多语法通过")
    return True


TESTS = [
    test_general_python_mode,
    test_general_python_more_syntax,
    test_general_python_break_continue,
    test_general_python_builtins_and_methods,
    test_general_python_extended_syntax,
    test_general_python_recursion_and_more_syntax,
]
