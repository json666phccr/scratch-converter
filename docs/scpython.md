# ScPython 语言指南

ScPython（Scratch Python，后缀 `.scpy`）是一门 **Python 风格、Scratch 语义** 的脚本语言。
一个 ScPython **工程文件夹** 会编译成一个 Scratch 3.0 项目（`.sb3`）：

- 每个 `.scpy` 文件是一个角色；
- 根目录的 `stage.scpy` 是舞台；
- `macros.scpy` 定义所有角色可复用的宏函数；
- `assets/` 存放造型与声音；
- `extensions.json` 声明自定义扩展。

> 目标读者：想用文本写 Scratch 项目的人，以及需要生成 `.scpy` 代码的 AI 智能体。
>
> 推荐阅读顺序：
> 1. [ScPython 编写教程](scpython-tutorial.md)（从 Scratch 机制到完整项目）
> 2. 本文（语言参考）
> 3. [ScPython AI 速查表](scpython-ai-cheatsheet.md)（生成代码时对照）
> 4. [ScPython 与 Scratch 行为](scpython-scratch-behavior.md)（语义细节）

---

## 1. 快速开始

```bash
cd src

# 检查语法并打印摘要
python -m scpython check ..\example\scpy_demo

# 导出 sb3
python -m scpython export ..\example\scpy_demo -o ..\example\scpy_demo.sb3
```

也可以使用主转换器：

```bash
python converter.py scpy2scratch ..\example\scpy_demo ..\example\scpy_demo.sb3
```

Python API：

```python
from scpython import export_project, check_project

export_project("my_project", "out.sb3")
project = check_project("my_project")
```

---

## 2. 工程结构

```text
my_project/
├── stage.scpy              # 必需：舞台（背景、全局变量、舞台脚本）
├── Cat.scpy                # 角色：文件名即角色名
├── Dog.scpy
├── macros.scpy             # 可选：宏函数
├── extensions.json         # 可选：自定义扩展声明
├── extension_urls.json     # 可选：TurboWarp 第三方扩展 {ID: URL}
├── assets/
│   ├── cat.svg
│   ├── dog.png
│   └── meow.wav
└── units/
    └── Bat.scpy            # 嵌套目录 -> 角色名 units//Bat
```

规则：

| 项 | 规则 |
|----|------|
| 舞台 | 只能是根目录的 `stage.scpy`（大小写不敏感） |
| 角色 | 根目录及子目录下所有 `.scpy`，文件名（不含扩展名）是角色名 |
| 嵌套目录 | `units/Bat.scpy` 导出为角色 `units//Bat`；更深的目录逐级用 `//` 连接 |
| 子目录 `stage.scpy` | 报错；舞台只能有一个 |
| 子目录 `macros.scpy` | 忽略并给出警告；宏文件只认根目录 |
| 资产 | 统一放在根目录 `assets/`，角色文件只写相对路径 |
| 扩展声明 | 舞台/角色的 `init` 中 `extensions = [...]`，或用 `extensions.json` |

---

## 3. 文件结构

每个 `.scpy` 文件按顺序可以包含：

1. `init:` 初始化块（可选，最多一个）；
2. 顶层初始化赋值（等同 init，可选）；
3. `def` 自制积木/宏函数（可多个）；
4. `when ...:` 事件脚本（可多个）。

```python
init:
    costumes = ["cat.svg"]
    x = 0
    y = 0
    var score = 0
    list history = []

def fact(n, *, types="n", warp=True):
    if n <= 1:
        return 1
    return n * fact(n - 1)

when green_flag:
    score = fact(5)
    say(join("score=", score))
```

> 「顶层初始化赋值」指直接写在文件顶层、不在 `when` 里的赋值，
> 例如 `costumes = ["cat.svg"]`、`var score = 0`。

---

## 4. init 块 / 初始化函数

初始化可以写成 `init:` 块，也可以写成无参数函数 `def init():`，两者等价：

```python
init:
    costumes = ["cat.svg"]
    var score = 0

# 等价写法
def init():
    costumes = ["cat.svg"]
    var score = 0
```

`init` 只接受初始化赋值，不接受普通脚本语句。带参数的 `def init(x)` 会被
当作普通自制积木，而不是初始化函数。

| 键 | 类型 | 说明 |
|----|------|------|
| `costumes` | 字符串列表 | 造型/背景，按顺序写入，引用 `assets/` 下的文件 |
| `costume_names` | 字符串列表 | 可选，与 `costumes` 一一对应的造型名（脚本按名字切换造型） |
| `sounds` | 字符串列表 | 声音，引用 `assets/` 下的文件 |
| `sound_names` | 字符串列表 | 可选，与 `sounds` 一一对应的声音名 |
| `extensions` | 字符串列表 | 声明项目用到的扩展，如 `["pen", "music"]` |
| `name` | 字符串 | 覆盖角色名（舞台默认 `Stage`） |
| `x` / `y` | 数字 | 角色坐标，默认 0 |
| `direction` | 数字 | 方向，默认 90 |
| `visible` | 布尔 | 默认 True |
| `size` | 数字 | 大小百分比，默认 100 |
| `rotation_style` | 字符串 | `all around` / `left-right` / `don't rotate` |
| `draggable` | 布尔 | 默认 False |
| `current_costume` | 数字 | 当前造型下标（0 起始） |
| `layer_order` | 数字 | 图层顺序，越大越靠前（默认 1） |
| `var 名字 = 初始值` | 声明 | 变量；舞台上是全局变量，角色上是局部变量 |
| `list 名字 = [..]` | 声明 | 列表；舞台上是全局列表，角色上是局部列表 |
| 其他 `名字 = 常量` | 声明 | 自动视为变量 |

示例：

```python
init:
    costumes = ["cat.svg", "cat2.png"]
    sounds = ["meow.wav"]
    x = 0
    y = -40
    direction = 90
    visible = True
    size = 80
    rotation_style = "left-right"
    var score = 0
    list history = []
```

### 变量作用域规则

- 舞台 `init` 中声明的变量/列表是 **全局**，所有角色共享；
- 角色 `init` 中显式声明的是 **局部**，优先于同名全局；
- 角色脚本里直接赋值但未声明的名字：
  - 若舞台存在同名全局变量 → 修改全局；
  - 否则自动创建该角色的局部变量（初始 0）；
- 列表同理；但列表必须通过 `list` 声明、下标、`append` 或列表函数被识别为列表。

---

## 5. 事件头（hats）

事件头用 `when ...:` 开始，缩进体是脚本：

```python
when green_flag:
    say("start")
```

| 写法 | 对应 Scratch 积木 |
|------|------------------|
| `when green_flag:` | 当绿旗被点击 |
| `when clicked:` | 当角色被点击 |
| `when this_sprite_clicked:` | 同上 |
| `when clone_start:` | 当作为克隆体启动时 |
| `when key_pressed("space"):` | 当按下空格键 |
| `when broadcast("go"):` | 当接收到广播 "go" |
| `when backdrop_switches_to("bg1"):` | 当背景换成 "bg1" |
| `when timer > 10:` | 当计时器 > 10 |
| `when loudness > 20:` | 当响度 > 20 |
| `when extension("ns", "opcode", ARG=value):` | 扩展帽子（通用） |
| `when myext.event(...):` | 扩展帽子（extensions.json 声明） |

规则：

- 同一个事件可以写多次，会生成多个并列脚本；
- `timer` / `loudness` 头目前只支持 `>`；
- `when broadcast` 的消息必须是字符串常量；
- `when key_pressed` 的键名用 Scratch 写法：`"space"`、`"a"`、`"up arrow"` 等；
- `stage_clicked` 目前与 `clicked` 相同（舞台点击帽在部分运行时可能不触发）。

---

## 6. 变量与列表

### 6.1 变量

```python
var score = 0          # 声明（init 或顶层）
score = 10             # 赋值
score += 1             # 增量
```

也允许在脚本内直接赋值未声明变量。变量值可以是数字、字符串、布尔。

### 6.2 列表

列表只支持原版 Scratch 的操作，**索引从 1 开始**：

```python
init:
    list items = []

when green_flag:
    items.append("a")          # 加到末尾
    add_to_list(items, "b")    # 同上
    insert_in_list(items, 1, "x")
    replace_in_list(items, 2, "y")
    delete_of_list(items, 1)
    delete_all_of_list(items)

    say(item_of(items, 1))     # 第 1 项
    say(item_number_of(items, "b"))  # 的位置
    say(length_of(items))
    say(contains_item(items, "b"))
    say(list_contents(items))
    say(len(items))            # 列表长度
```

支持的下标形式：

```python
items[1] = "first"    # 替换第 1 项
say(items[2])         # 读取第 2 项
del items[2]          # 删除第 2 项
```

不支持：

- 切片 `items[1:3]`；
- 负下标；
- `pop / remove / sort / reverse / count / extend / copy`；
- 列表整体赋值、列表作为参数、列表推导式。

### 6.3 `in` 判断

```python
if "b" in items:        # 列表包含
if "ell" in "hello":    # 字符串包含（右侧必须是字符串常量）
```

其他情况请用 `contains_item(items, v)` / `contains(s, part)`。

---

## 7. 语句

| 语句 | 说明 |
|------|------|
| `x = 表达式` | 变量赋值 |
| `x += / -= / *= / /= / %=` | 增量赋值 |
| `items[i] = 值` | 列表项替换 |
| `if / elif / else` | 条件 |
| `while 条件:` | 循环 |
| `for i in range(...):` | 计数循环 |
| `for item in items:` | 遍历列表 |
| `break` / `continue` | 仅循环内 |
| `del items[i]` | 删除列表项 |
| `return [值]` | 自制积木返回 |
| `pass` | 空语句 |
| 函数调用 | 见下方内置函数与自制积木 |

循环说明：

- `range(n)` / `range(start, stop)` / `range(start, stop, step)`；
- `step` 必须是非零常量数字，可为负数；
- 循环变量会被写成 Scratch 变量（可见）；
- `break` / `continue` 会生成隐藏标志变量来实现；
- 不支持 `for...else`、`while...else`。

---

## 8. 表达式与内置函数

### 8.1 运算符

| 写法 | Scratch 行为 |
|------|--------------|
| `a + b` `a - b` `a * b` `a / b` `a % b` | 数字运算；先把两侧转数字 |
| `a == b` | Scratch `=`（数字优先，否则忽略大小写字符串比较） |
| `a != b` | `not (a == b)` |
| `a < b` `a > b` `a <= b` `a >= b` | Scratch 比较 |
| `and` / `or` / `not` | Scratch 布尔 |
| `a in items` | 列表包含 |
| `"子串" in "字符串常量"` | 字符串包含 |

不支持：`**`、`//`、位运算、`is`、`is not`、链式赋值、元组解包。

### 8.2 字符串（只有 Scratch 操作）

```python
join("a", "b")        # 连接
letter_of(2, "abc")   # 第 2 个字符 -> "b"
length("abc")         # 3
contains("hello", "ell")
```

**不要**使用：

- `s[0]`、`s[1:2]`；
- `s.upper()`、`s.replace()`、`s.split()` 等任何字符串方法；
- f-string、`.format()`、`%` 格式化。

字符串拼接请写 `join(a, b)`；`+` 是 Scratch 的数字加法。

### 8.3 数学

```python
round(x)              # Scratch 四舍五入
abs(x) / floor(x) / ceiling(x)
sqrt(x) / sin(x) / cos(x) / tan(x)
asin(x) / acos(x) / atan(x)
ln(x) / log(x) / exp(x) / pow10(x)
math.sqrt(x)          # 同上，可写 math.xxx
random(1, 10)         # 随机数（Scratch random）
randint(1, 10)
random.randint(1, 10) # 语法糖
```

### 8.4 侦测与角色属性

```python
answer()              # 询问答案
timer()               # 计时器
mouse_x() / mouse_y() / mouse_down()
loudness()
days_since_2000()
username()
current("YEAR")       # YEAR/MONTH/DATE/DAYOFWEEK/HOUR/MINUTE/SECOND
key_pressed("space")
touching("_edge_")    # 或角色名、"_mouse_"
distance_to("_mouse_")
x_position() / y_position()
direction_of_sprite()
costume_number() / costume_name()
backdrop_number() / backdrop_name()
size_of_sprite()
volume()
```

### 8.5 类型转换

```python
to_number(x)   # Scratch 转数字
to_string(x)   # Scratch 转字符串（等价 join(x, "")）
to_boolean(x)  # Scratch 转布尔
str(x) / int(x) / float(x) / bool(x)
```

---

## 9. 内置语句函数

### 运动

```python
move(10)
turn_right(15)
turn_left(15)
goto(0, 0)
goto_random()
glide(1, 100, 0)      # 1 秒滑到 (100,0)
point_in_direction(90)
point_towards("_mouse_")
set_rotation_style("left-right")
change_x(10) / set_x(0)
change_y(10) / set_y(0)
if_on_edge_bounce()
```

### 外观

```python
say("hello")
say_for("hello", 2)
think("hmm")
think_for("hmm", 2)
show() / hide()
switch_costume("costume1")
next_costume()
switch_backdrop("backdrop1")
next_backdrop()
set_size(100) / change_size(10)
set_effect("color", 25)
change_effect("brightness", 10)
clear_effects()
go_to_front() / go_to_back()
go_forward(1) / go_backward(1)
```

### 声音

```python
play_sound("Meow")
play_sound_until_done("Meow")
stop_all_sounds()
set_volume(100) / change_volume(10)
```

### 控制

```python
wait(1)
wait_until(score > 10)
broadcast("go")
broadcast_and_wait("go")
create_clone("_myself_")    # 或角色名
delete_this_clone()
stop_all()
stop_this_script()
stop_other_scripts()
reset_timer()
ask_and_wait("你的名字？")
set_drag_mode("draggable")
```

### 变量/列表显示

```python
show_variable("score")
hide_variable("score")
show_list("items")
hide_list("items")
```

---

## 10. 自制积木

```python
def add(a, b, *, types="nn", warp=False):
    return a + b
```

- 每个 `def` 会生成一个 Scratch 自制积木；
- 参数按位置传递，支持默认值：

```python
def greet(name="world", *, types="s"):
    say(join("Hi ", name))
```

- 元信息只能通过 **关键字参数（`*` 之后）** 提供：

| 元信息 | 说明 |
|--------|------|
| `types` | 参数字符串，`s` 字符串、`n` 数字、`b` 布尔；长度必须等于参数个数 |
| `warp` | `True` 表示「运行时不刷新屏幕」 |
| `label` | 自定义 proccode，如 `"add %n and %n"`；占位符数量必须等于参数个数 |

- 未写 `types` 时，按默认值推断：`True/False` → `b`，数字 → `n`，字符串 → `s`，无默认值 → `s`。
- 缺省参数值会写入 Scratch 的 `argumentdefaults`；没有默认值的布尔参数为 `false`，其他为 `""`。
- 用 `return 值` 返回结果，可以当表达式使用：

```python
def fact(n, *, types="n", warp=True):
    if n <= 1:
        return 1
    return n * fact(n - 1)

when green_flag:
    say(fact(5))
```

- 不支持装饰器、`*args`、`**kwargs`、嵌套函数、在函数内给参数赋值。

---

## 11. 宏（macros.scpy）

宏文件只能包含 `def`：

```python
# macros.scpy
def twice(x, *, types="n"):
    return x * 2

def quad(x, *, types="n"):
    return twice(twice(x))
```

角色使用宏：

```python
when green_flag:
    say(quad(3))
```

导出时：

1. 扫描角色调用了哪些宏；
2. 递归收集宏依赖（`quad` → `twice`）；
3. 把用到的宏定义 **复制一份** 到该角色；
4. 角色自己定义的同名函数优先，不复制宏；
5. 未使用的宏不会出现在角色里。

注意：

- 宏里的变量会按当前角色解析（角色局部或舞台全局）；
- 宏名不要与内置函数（`say`、`move` 等）重名；
- 宏文件里不能写事件头、`init` 或普通语句。

用 `python -m scpython import` 把 sb3 转成 ScPython 时，会对比各角色中的自制积木：
函数名、参数、类型、warp、label 与函数体完全相同的定义会被抽到 `macros.scpy`，
角色文件里只保留调用；导出时再自动复制回每个角色。

---

## 12. 扩展

### 12.1 声明

在 `stage.scpy` 或角色 `init` 中：

```python
init:
    extensions = ["pen", "music"]
```

### 12.2 内置扩展函数

画笔：

```python
pen_clear()
pen_down() / pen_up()
pen_stamp()
set_pen_color("#ff0000")
set_pen_size(5)
change_pen_size(1)
set_pen_param("color", 50)
change_pen_param("brightness", 10)
```

音乐：

```python
play_note(60, 0.5)
play_drum(1, 0.25)
set_tempo(120)
rest(0.5)
set_instrument(1)
```

### 12.3 自定义扩展（extensions.json）

工程根目录：

```json
{
  "myext": {
    "jump": {
      "opcode": "myext_jump",
      "inputs": ["HEIGHT"],
      "fields": {"MODE": "MODE"}
    },
    "speed": {
      "opcode": "myext_getSpeed",
      "expr": true
    },
    "whenEvent": {
      "opcode": "myext_whenEvent",
      "hat": true,
      "inputs": ["VALUE"]
    }
  }
}
```

使用：

```python
when green_flag:
    myext.jump(10, MODE="fast")   # fields: MODE="fast"
    v = myext.speed()             # 表达式
```

规则：

- `inputs` 决定位置参数顺序；
- `fields` 里的键作为调用参数时写入 Scratch 字段，必须是常量；
- 其他关键字参数会作为额外输入（槽名即参数名）；
- 未声明 `opcode` 时默认 `namespace_函数名`；
- 扩展帽子可用 `when myext.whenEvent(...):`，或通用写法
  `when extension("myext", "myext_whenEvent", VALUE=1):`。

### 12.4 通用扩展调用

没有清单时可以直接写 opcode：

```python
ext("myext", "myext_jump", HEIGHT=10)
v = ext("myext", "myext_getSpeed")
```

`ext` 的所有关键字参数都作为输入，不能设置字段。

---

## 13. 资产

- 所有资源放在工程根目录的 `assets/` 下；
- 角色文件写相对路径：

```python
init:
    costumes = ["cat.svg", "sub/cat2.png"]
    sounds = ["meow.wav"]
```

- 支持：`svg`、`png`、`jpg`、`jpeg`、`wav`、`mp3`；
- 造型名默认取文件名（不含扩展名），同名时自动加 `_2`；
- 旋转中心自动设为图片宽高的一半（SVG 读取 width/height 或 viewBox）；
- 多个角色引用同一个文件时只导出一份资源；
- 找不到资源会报错并指出引用的角色文件。

---

## 14. 数据文件、调试与 sb3 导入

### 14.1 用 txt 文件做列表默认值

`txt("文件.txt")` 在编译时读取文本文件，每个非空行作为一项，路径相对于当前 `.scpy` 文件：

```python
init:
    list words = txt("data/words.txt")
```

等价写法：

```python
init:
    debug.import_list(words, "data/words.txt")
```

文件使用 UTF-8（自动兼容 BOM），换行符 `\n`/`\r\n` 均可。

### 14.2 修改默认值

`init` 中可以用调试指令声明/覆盖默认值，导出后就是角色的初始变量值：

```python
init:
    debug.set_default(score, 100)
    debug.set_list_default(nums, [1, 2, 3])
```

### 14.3 运行期调试指令

```python
when green_flag:
    debug.set_var(score, 42)   # 立即赋值
    debug.reset(score)         # 恢复 init 中的默认值
    debug.reset(words)         # 列表恢复默认值（清空后重新填入）
    debug.reset()              # 重置当前角色所有显式声明的变量/列表
    debug.print("debug")       # 编译期提示，不生成积木
    debug.trace("done")
    debug.watch(score)
    debug.assert(score > 0)
```

说明：

- `set_var` / `reset` 会生成普通的「将变量设为」/ 列表清空与添加积木；
- `reset`/`set_var` 的目标可以写字符串 `"score"`，也可以直接写变量名 `score`；
- `print` / `trace` / `watch` / `assert` 只做编译期记录，导出时在命令行打印；
- `reset` 的默认值来自 `init` 中的 `var`/`list`/`debug.set_default`/`debug.set_list_default`。

### 14.4 sb3 -> ScPython

```bash
python -m scpython import input.sb3 -o my_project
python -m scpython import input.sb3 -o my_project --no-macros
python converter.py sb32scpy input.sb3 my_project
```

```python
from scpython import sb3_to_scpython

sb3_to_scpython("input.sb3", "my_project", split_macros=True)
```

转换内容：

- 事件帽子、运动/外观/声音/控制/侦测块、变量与列表、自制积木与调用；
- Scratch 注释：文字写入工程根目录 `comments.json`（导出时回写为独立注释，
  保留位置/大小），源码里同时保留 `#` 便于阅读；
- 变量/列表原名列在 `variable_aliases` / `list_aliases` 中，导出时还原
  `FortunateOS:系统版本号` 这类含冒号、问号的名字；
- 保留角色原始名称、造型/声音名称、`currentCostume` 与 `layerOrder`，
  造型旋转中心/分辨率写入 `costume_meta.json`，坐标与点击判定和原工程一致；
- `for _ in range(n)` 会还原为 Scratch 的「重复 n 次」，不会多出计数器；
- 扩展下拉字段通过 `ext("ns", "opcode", MODE="fast", _fields=["MODE"])`
  写回字段；动态广播与第三方扩展 URL 也会保留；
- 保留 TurboWarp 第三方扩展：`extensionURLs` 写入工程根目录的
  `extension_urls.json`，导出时回写到 `project.json`，避免 TurboWarp 报
  `Unknown extension`；
- 全局变量只在 `stage.scpy` 中声明一次，角色文件不再重复声明；
- 默认把多个角色中**完全相同**的自制积木抽到 `macros.scpy`；
- 无法表达的块会写成 `# TODO` 并在命令行给出警告，不会静默丢弃。

---

## 15. 命令行与 API

```bash
# 检查
python -m scpython check <工程目录>

# 静态检查（未使用的变量/列表/自制积木/宏）
python -m scpython lint <工程目录>

# 无头运行并查看变量、统计、最近执行轨迹
python -m scpython run <工程目录> --seconds 3 --stats
python -m scpython run <工程目录> --seconds 3 --trace 20
python -m scpython run <工程目录> --no-vars --json

# 导出
python -m scpython export <工程目录> -o out.sb3

# sb3 导入
python -m scpython import <input.sb3> -o <工程目录>

# 主转换器别名
python converter.py scpy2scratch <工程目录> out.sb3
python converter.py sb32scpy <input.sb3> <工程目录>
```

`run` 会先在临时目录编译为 sb3，再调用本机 VM 无头执行：

- `--seconds` / `--frames` 控制运行时长；
- `--seed` 固定随机数；`--turbo` 立即模式；`--audio` 启用声音；
- 结束后默认打印每个角色的变量/列表（内部 `__scpy_*` 变量已隐藏）；
- `--trace N` 打印最近 N 条执行记录，`--stats` 打印帧数/语句数/克隆数；
- `--watch "var('score')"` / `--watch "lst('history')"` 在结束后求值变量或列表；
- `--json` 输出完整结果（含运行时错误），便于脚本处理；
- `--no-vars` 关闭结束时的变量/列表打印；
- 退出码：0 正常，1 有运行时错误，2 编译/加载失败。

编译错误会附带出错源码行与列指示：

```text
错误: C:\...\Cat.scpy:12:5: 未知函数 foo
  12 |     foo(1)
     |     ^
```

```python
from scpython import export_project, check_project, lint_project, ScPythonError

try:
    export_project("my_project", "out.sb3")
except ScPythonError as error:
    print(error)   # 文件:行:列: 错误信息

for issue in lint_project("my_project"):
    print(issue)
```

导出前会自动校验 SB3 的关键结构：

- `meta.vm` / `meta.semver` 必须是 `x.y.z`（可带 `-suffix`）；
- `targets[0]` 必须是舞台；
- 每个 target 必须包含 `variables/lists/broadcasts/blocks/comments/costumes/sounds` 等字段；
- 造型必须包含 `assetId/md5ext/dataFormat/rotationCenterX/rotationCenterY`；
- `extensions` 必须是字符串数组。

这些校验用于避免 TurboWarp/Scratch 因元数据不合法而拒绝打开项目。

---

## 16. 完整示例

```python
# Cat.scpy
init:
    costumes = ["cat.svg"]
    sounds = ["meow.wav"]
    x = 0
    y = 0
    size = 80
    var score = 0
    list history = []

when green_flag:
    say("hello")
    for i in range(5):
        if i == 3:
            continue
        score += i
        history.append(i)
    say(join("score=", score))
    greet("ScPython")

when broadcast("reset"):
    delete_all_of_list(history)
    score = 0

def add_score(amount, *, types="n", warp=True):
    score += amount
```

```python
# stage.scpy
init:
    costumes = ["backdrop.svg"]
    extensions = ["pen"]
    var global_time = 0

when green_flag:
    broadcast("reset")
```

```python
# macros.scpy
def greet(name, *, types="s"):
    say(join("Hi ", name))
```

---

## 17. 限制一览

不支持：

| 类别 | 示例 |
|------|------|
| 类/装饰器 | `class X:`、`@deco` |
| 字典/集合 | `{}`、`{1, 2}` |
| 推导式/生成器 | `[x for x in xs]`、`(x for x in xs)` |
| 异常 | `try/except`、`raise` |
| 导入 | `import`、`from ... import` |
| 异步 | `async def`、`await` |
| lambda | `lambda x: x` |
| 高级字符串 | f-string、`.upper()`、`.split()`、切片 |
| 高级列表 | 列表切片、负下标、`sort/reverse/pop/remove/count/extend/copy` |
| 幂/整除 | `**`、`//` |
| 其他 | `is`、`None`、条件表达式、`match`、`for...else` |

如果写了不支持的语法，导出会给出 **文件:行号** 错误，而不是静默忽略。

---

## 18. AI 编写检查清单

生成 `.scpy` 时按以下顺序检查：

1. 根目录有 `stage.scpy`；
2. 每个角色一个 `.scpy`，文件名合法；
3. 需要共享的函数放进 `macros.scpy`，只写 `def`；
4. 角色 `init` 声明造型/声音/变量/列表/位置；
5. 事件用 `when ...:`，不要用装饰器；
6. 自制积木元信息写在 `*` 后的 `types` / `warp` / `label`；
7. 列表索引从 1 开始，只用 Scratch 列表操作；
8. 字符串拼接用 `join`，不用 `+`、f-string 或字符串方法；
9. 比较用 `==`/`!=`（Scratch 语义），不要用 `is`；
10. 循环里用 `range` 或列表，不用 `enumerate/zip/推导式`；
11. 需要扩展时写 `extensions = [...]` 或 `extensions.json`；
12. 运行 `python -m scpython check <目录>` 确认无错误。
