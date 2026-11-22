# ScPython AI 速查表

面向 AI 智能体的最小、可执行规范。完整说明见 [scpython.md](scpython.md) 与
[scpython-tutorial.md](scpython-tutorial.md)。

---

## 1. 文件布局

```text
project/
├── stage.scpy          # 必须，且只能在根目录
├── Role.scpy           # 每个角色一个文件
├── macros.scpy         # 可选，只能包含 def
├── extensions.json     # 可选，自定义扩展
├── assets/             # 造型/声音
└── sub/Role.scpy       # -> 角色名 sub//Role
```

---

## 2. 模板

### 2.1 舞台

```python
init:
    costumes = ["backdrop.svg"]
    var global_score = 0

when green_flag:
    broadcast("start")
```

### 2.2 角色

```python
init:
    costumes = ["cat.svg"]
    sounds = ["meow.wav"]
    x = 0
    y = 0
    size = 100
    var hp = 100
    list items = []

when green_flag:
    say("hello")

def helper(x, *, types="n", warp=False):
    return x
```

### 2.3 宏

```python
def clamp(v, low, high, *, types="nnn"):
    if v < low:
        return low
    if v > high:
        return high
    return v
```

---

## 3. 事件头

```python
when green_flag:
when clicked:
when this_sprite_clicked:
when clone_start:
when key_pressed("space"):
when broadcast("name"):
when backdrop_switches_to("name"):
when timer > 10:
when loudness > 20:
when extension("namespace", "opcode", ARG=value):
when myext.event(ARG=value):
```

限制：

- `timer/loudness` 只支持 `>`；
- 广播名必须是字符串常量；
- 不支持装饰器式事件。

---

## 4. 语句

```python
var x = 0                 # 声明（init/顶层/脚本内均可）
list xs = []              # 列表声明：只能写在 init 或文件顶层
x = 1
x += 1 / -= / *= / /= / %=
xs[1] = "a"
del xs[1]
if cond:
elif cond:
else:
while cond:
for i in range(5):
for i in range(2, 10, 2):
for item in xs:
break
continue
return value
pass
f(...)                    # 函数调用
```

`list` 声明不能写在 `when` 或函数体内；脚本内需要列表时，在 `init` 中先声明。

不支持：`for...else`、`while...else`、元组赋值、链式赋值。

---

## 5. 表达式

### 5.1 运算符

```python
+ - * / %          # Scratch 数字运算
== != < > <= >=    # Scratch 比较
and or not
x in xs            # 列表包含
"sub" in "text"    # 右侧必须是字符串常量
```

字符串拼接 **只能用** `join(a, b)`。

### 5.2 字符串/列表

```python
join(a, b)
letter_of(i, s)
length(s) / len(s)
contains(s, part)

item_of(xs, i)
item_number_of(xs, v)
length_of(xs)
contains_item(xs, v)
list_contents(xs)
len(xs)
xs[i]
xs.index(v)
```

列表索引从 **1** 开始。

### 5.3 数学

```python
round(x) abs(x) floor(x) ceiling(x)
sqrt(x) sin(x) cos(x) tan(x)
asin(x) acos(x) atan(x)
ln(x) log(x) exp(x) pow10(x)
math.sqrt(x) ...
random(a, b) randint(a, b) random.randint(a, b)
```

### 5.4 侦测/属性

```python
answer() timer() mouse_x() mouse_y() mouse_down()
loudness() days_since_2000() username()
current("YEAR")
key_pressed("space")
touching("_edge_") touching("Cat") touching("_mouse_")
distance_to("_mouse_")
x_position() y_position() direction_of_sprite()
costume_number() costume_name()
backdrop_number() backdrop_name()
size_of_sprite() volume()
```

### 5.5 转换

```python
to_number(x) to_string(x) to_boolean(x)
str(x) int(x) float(x) bool(x)
```

---

## 6. 内置语句函数

```python
# 运动
move(10) turn_right(15) turn_left(15)
goto(x, y) goto_random() goto_target("Sprite1")
glide(secs, x, y) glide_to_target(secs, "Sprite1")
point_in_direction(90) point_towards("_mouse_")
set_rotation_style("left-right")
change_x(n) set_x(n) change_y(n) set_y(n)
if_on_edge_bounce()

# 外观
say(msg) say_for(msg, secs)
think(msg) think_for(msg, secs)
show() hide()
switch_costume(name) next_costume()
switch_backdrop(name) next_backdrop()
set_size(n) change_size(n)
set_effect(name, value) change_effect(name, value)
clear_effects()
go_to_front() go_to_back()
go_forward(n) go_backward(n)

# 声音
play_sound(name) play_sound_until_done(name)
stop_all_sounds()
set_volume(n) change_volume(n)

# 控制
wait(secs) wait_until(cond)
broadcast(name) broadcast_and_wait(name)
create_clone("_myself_") create_clone("Role")
delete_this_clone()
stop_all() stop_this_script() stop_other_scripts()
reset_timer()
ask_and_wait(question)
set_drag_mode("draggable")

# 变量/列表显示
show_variable("x") hide_variable("x")
show_list("xs") hide_list("xs")

# 列表语句
add_to_list(xs, v)
delete_of_list(xs, i) delete_item(xs, i)
delete_all_of_list(xs)
insert_in_list(xs, i, v)
replace_in_list(xs, i, v)
xs.append(v) xs.insert(i, v) xs.clear()

# 扩展
pen_clear() pen_down() pen_up() pen_stamp()
set_pen_color("#ff0000") set_pen_size(5) change_pen_size(1)
set_pen_param("color", 50) change_pen_param("brightness", 10)
play_note(60, 0.5) play_drum(1, 0.25)
set_tempo(120) rest(0.5) set_instrument(1)
ext("namespace", "opcode", KEY=value)
```

---

## 7. 自制积木元信息

```python
def name(a, b=0, *, types="ns", warp=False, label=None):
    ...
```

| 键 | 规则 |
|----|------|
| `types` | 字符 `s/n/b`，长度必须等于参数个数 |
| `warp` | True/False |
| `label` | `%s/%n/%b` 数量必须等于参数个数 |

调用只能按位置传参。返回值用 `return`（TurboWarp `procedures_return`）。

---

## 8. 扩展

```python
init:
    extensions = ["pen", "music"]
```

`extensions.json`：

```json
{
  "myext": {
    "jump": {
      "opcode": "myext_jump",
      "inputs": ["HEIGHT"],
      "fields": {"MODE": "MODE"}
    },
    "speed": {"opcode": "myext_getSpeed", "expr": true}
  }
}
```

```python
myext.jump(10, MODE="fast")
v = myext.speed()
```

---

## 9. 禁止清单

| 禁止 | 替代 |
|------|------|
| `class` | 无 |
| `@decorator` | `def f(..., *, types=...)` |
| `lambda` | 定义函数 |
| `{}` / `{1,2}` | 无；用变量/列表 |
| `[x for x in xs]` | `for` 循环 + `append` |
| `try/except` | 无 |
| `import` | 无 |
| `async/await` | 无 |
| `f"{x}"` | `join(x, "")` |
| `"a" + "b"` | `join("a", "b")` |
| `s.upper()` / `s.split()` | `contains/join/letter_of` |
| `s[0]` / `s[1:2]` | `letter_of` |
| `xs[1:3]` | `for` + `item_of` |
| `xs.sort()` / `pop` / `remove` | 自己用循环实现 |
| `a ** b` / `a // b` | 无 |
| `is` / `is not` | `==` / `!=` |
| `None` | 无 |
| `a if c else b` | `if` 语句 |
| `for...else` | 无 |

---

## 10. 语义陷阱

1. `==` 是 Scratch 比较：数字优先，否则忽略大小写字符串比较；
2. `+` 是数字加法，字符串拼接用 `join`；
3. 列表索引从 1 开始；
4. 越界读取返回 `""`；
5. `for` 循环每轮让出一帧；
6. `while True` 没有 break 会永久循环；
7. `warp=True` 适合纯计算递归；
8. 克隆体复制局部变量，全局共享；
9. `broadcast` 立即返回，`broadcast_and_wait` 等待；
10. 隐藏变量 `__scpy_*` 是正常产物；
11. 宏是编译期复制，不是运行时共享；
12. `return` 依赖 TurboWarp。

---

## 11. 生成后自检

```bash
cd src
python -m scpython check <工程目录>
python -m scpython export <工程目录> -o out.sb3
```

检查项：

- [ ] `stage.scpy` 存在；
- [ ] 所有资源在 `assets/`；
- [ ] 没有禁止语法；
- [ ] 所有函数名存在；
- [ ] `types` 长度正确；
- [ ] 列表索引用 1；
- [ ] 字符串拼接用 `join`；
- [ ] 导出成功且 TurboWarp 能打开。
