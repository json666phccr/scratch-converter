# ScPython 编写教程

本教程面向两类读者：

- **人类开发者**：想把 Scratch 项目写成文本、用 Git 管理、批量生成；
- **AI 智能体**：需要一份可执行的语法、工程结构与自检规则，稳定生成 `.scpy` 工程。

阅读顺序建议：

1. 第 0 章：理解 Scratch 的运行机制；
2. 第 1-2 章：搭建工程并写出第一个项目；
3. 第 3-11 章：按主题学习语法；
4. 第 12 章：常用配方，直接复用；
5. 第 13-14 章：错误处理与 AI 生成流程；
6. 第 15 章：理解导出的 SB3 细节。

参考文档：

- [ScPython 语言参考](scpython.md)
- [ScPython 与 Scratch 行为](scpython-scratch-behavior.md)
- [Scratch VM 执行语义](scratch-vm-execution.md)
- [SB3 文件结构](sb3-format.md)
- [Scratch 输入与参数语义](scratch-semantics.md)

---

## 第 0 章 先理解 Scratch 的运行机制

写 ScPython 之前，必须知道它最终会变成什么。ScPython 不是 Python 运行时，
它的每个语法结构都会落到 Scratch 积木上。

### 0.1 Target、舞台与角色

Scratch 项目由 **targets** 组成：

```text
project
├── Stage（舞台，必须有且只有一个）
│   ├── 背景（造型）
│   ├── 全局变量/列表
│   └── 舞台脚本
├── Cat（角色）
│   ├── 造型、声音
│   ├── 局部变量/列表
│   └── 脚本
└── Dog（角色）
```

- 舞台坐标中心是 `(0, 0)`，默认尺寸 480×360；
- 每个角色有自己的位置、方向、大小、造型、图层、局部变量；
- 全局变量/列表放在舞台上，所有角色共享；
- 克隆体是角色的运行时副本，不是新角色类型。

ScPython 对应：

```text
stage.scpy          -> Stage
Cat.scpy            -> Cat
units/Bat.scpy      -> 角色 units//Bat
```

### 0.2 积木、堆栈与帽子

Scratch 的执行单位是 **积木**：

- 帽子积木（hat）是脚本入口，例如「当绿旗被点击」；
- 普通积木通过 `next` 串成一条堆栈；
- C 形积木（if/repeat）拥有子堆栈；
- 只有帽子开头的堆栈才会被触发，孤立积木不会执行。

ScPython 对应：

```python
when green_flag:      # 帽子
    say("hello")      # 普通积木
    if score > 10:    # C 形积木
        say("win")
```

### 0.3 线程与帧

Scratch 是 **协作式单线程调度**：

- 点绿旗后，每个绿旗脚本创建一个线程；
- 同一时刻只有一个线程持有执行权；
- 循环每执行一轮会让出一帧；
- `wait`、`glide`、`say_for`、`broadcast_and_wait`、`ask_and_wait` 会阻塞；
- 默认 30 帧/秒，TurboWarp 可调整。

这意味着：

| 写法 | 结果 |
|------|------|
| `while True:` 无 break | 永久循环，每轮让出一帧 |
| `for i in range(1000000)` | 约 100 万帧，非常慢 |
| `warp=True` 的自制积木 | 循环内不让帧，适合计算 |
| 多个 `when green_flag` | 各自独立线程，可能交替执行 |

### 0.4 事件帽子

| Scratch | ScPython |
|---------|----------|
| 当绿旗被点击 | `when green_flag:` |
| 当角色被点击 | `when clicked:` |
| 当作为克隆体启动时 | `when clone_start:` |
| 当按下空格键 | `when key_pressed("space"):` |
| 当接收到广播 | `when broadcast("go"):` |
| 当背景换成 | `when backdrop_switches_to("bg"):` |
| 当计时器 > | `when timer > 10:` |
| 当响度 > | `when loudness > 20:` |

计时器/响度帽子是 **边沿触发**：条件由假变真时启动一次。

### 0.5 广播

```python
broadcast("go")             # 立即返回
broadcast_and_wait("go")    # 等接收脚本全部结束
```

- 每个接收脚本启动一个新线程；
- 同一个广播可以同时触发多个角色、多个脚本；
- 没有接收者时直接返回；
- 广播名必须是字符串常量。

### 0.6 克隆

```python
create_clone("_myself_")
delete_this_clone()
```

- 克隆体复制位置、方向、大小、造型、特效、局部变量当前值；
- 全局变量/列表共享；
- 每个克隆体都会执行 `when clone_start`；
- 默认最多 300 个克隆体；
- 绿旗会删除所有克隆体。

### 0.7 变量与列表

- 全局变量在舞台上，所有角色共享；
- 局部变量只属于某个角色及其克隆体；
- 列表索引从 **1** 开始，不是 0；
- 越界读取返回 `""`，越界写入/删除忽略；
- Scratch 的变量/列表用 ID 区分，名字可以重复。

### 0.8 自制积木与 warp

```python
def fact(n, *, types="n", warp=True):
    if n <= 1:
        return 1
    return n * fact(n - 1)
```

- Scratch 自制积木通过 `proccode` 识别，例如 `fact %n`；
- 参数按位置传递；
- 未填参数取定义里的默认值；
- `warp=True` 表示「运行时不刷新屏幕」；
- `return` 使用 TurboWarp 的 `procedures_return`；
- 递归由线程调用栈执行。

### 0.9 造型、声音与资源

- 造型有名字、资源 MD5、格式、旋转中心；
- 资源文件名是 `<md5>.<扩展名>`；
- 背景是舞台的造型；
- 角色图层按添加顺序，`go_to_front`/`go_to_back` 调整；
- SVG 由运行时解析，复杂 SVG 可能失真。

### 0.10 项目生命周期

```text
加载项目 -> 注册帽子 -> 点击绿旗
  -> 删除克隆体
  -> 停止旧线程
  -> 重置计时器
  -> 启动所有绿旗脚本
  -> 每帧：事件 -> 更新传感器 -> 执行脚本 -> 渲染
```

ScPython 只负责生成这些结构；运行时行为由 Scratch/TurboWarp 决定。

---

## 第 1 章 准备工程

### 1.1 安装与命令

项目依赖 Python 3.10+（推荐 3.11）与 pygame。

```bash
cd src

# 语法检查
python -m scpython check ..\example\scpy_demo

# 导出 sb3
python -m scpython export ..\example\scpy_demo -o ..\example\scpy_demo.sb3

# 使用主转换器
python converter.py scpy2scratch ..\example\scpy_demo ..\example\scpy_demo.sb3
```

导出后用 Scratch 3 / TurboWarp 打开 `.sb3`。

### 1.2 最小工程

```text
hello/
├── stage.scpy
└── Cat.scpy
```

`stage.scpy`：

```python
init:
    costumes = ["backdrop.svg"]
```

`Cat.scpy`：

```python
init:
    costumes = ["cat.svg"]

when green_flag:
    say("Hello, ScPython!")
```

`assets/` 中放 `backdrop.svg`、`cat.svg`。

### 1.3 导出前自检

```bash
python -m scpython check hello
```

输出应类似：

```text
舞台: Stage
角色: 1 个
  - Cat: 脚本 1，自制积木 0，变量 0，列表 0
资产: 2 个
扩展: 无
```

---

## 第 2 章 Hello World：完整步骤

### 2.1 创建目录

```text
hello/
├── stage.scpy
├── Cat.scpy
└── assets/
    ├── backdrop.svg
    └── cat.svg
```

### 2.2 舞台

```python
# stage.scpy
init:
    costumes = ["backdrop.svg"]

when green_flag:
    say("舞台准备完毕")
```

> 舞台也可以 `say`，它会显示在舞台气泡中。

### 2.3 角色

```python
# Cat.scpy
init:
    costumes = ["cat.svg"]
    x = 0
    y = 0
    size = 80

when green_flag:
    say("我是 Cat")
    move(50)
```

### 2.4 导出并运行

```bash
python -m scpython export hello -o hello.sb3
```

在 TurboWarp 中打开，点击绿旗。

### 2.5 常见错误

| 错误 | 原因 |
|------|------|
| 缺少舞台文件 stage.scpy | 根目录必须有舞台 |
| 找不到资源 'cat.svg' | `assets/` 下没有该文件 |
| 未知函数 sayy | 拼写错误，内置函数名固定 |
| 不支持 f-string | ScPython 不支持 f-string |

---

## 第 3 章 变量、条件与循环

### 3.1 变量

```python
init:
    var score = 0

when green_flag:
    score = 10
    score += 5
    say(score)      # 15
```

- `var` 可以写在 `init`、文件顶层，或脚本内；
- 脚本内未声明的赋值会自动创建变量；
- 舞台声明的是全局变量，角色声明的是局部变量。

### 3.2 if / elif / else

```python
when green_flag:
    if score >= 90:
        say("A")
    elif score >= 60:
        say("B")
    else:
        say("C")
```

`>=` / `<=` / `!=` 都会转换成 Scratch 的 `<`、`>`、`=` 组合。

### 3.3 while

```python
when green_flag:
    var n = 0
    while n < 5:
        n += 1
    say(n)      # 5
```

`while True:` 且没有 `break` 会生成 `forever`。

### 3.4 for range

```python
when green_flag:
    for i in range(5):
        say(i)          # 0 1 2 3 4

    for i in range(2, 10, 2):
        say(i)          # 2 4 6 8
```

- `range` 的 stop 只求值一次；
- step 必须是常量，可为负数；
- 循环变量是普通 Scratch 变量，循环结束后保留最后一个值。

### 3.5 break / continue

```python
when green_flag:
    var total = 0
    for i in range(10):
        if i == 3:
            continue
        if i == 6:
            break
        total += i
    say(total)      # 12
```

ScPython 会生成隐藏变量 `__scpy_break_N` / `__scpy_continue_N`；
它们会出现在 Scratch 变量面板中，这是正常现象。

### 3.6 运算符陷阱

```python
say(1 + 2)              # 3
say("1" + 2)            # 3（Scratch 数字加法）
say(join("1", 2))       # "12"
```

`+` 是 Scratch 数字加法，不是字符串拼接。字符串拼接必须用 `join`。

比较：

```python
"ABC" == "abc"     # true
"1.0" == 1         # true
"" == 0            # false
```

---

## 第 4 章 列表

### 4.1 声明与添加

```python
init:
    list items = []

when green_flag:
    items.append("apple")
    add_to_list(items, "banana")
    insert_in_list(items, 1, "first")
    say(list_contents(items))
```

### 4.2 读取

```python
say(item_of(items, 1))          # 第 1 项
say(items[2])                   # 第 2 项
say(length_of(items))           # 长度
say(len(items))                 # 长度
say(item_number_of(items, "apple"))
say(contains_item(items, "apple"))
```

### 4.3 修改与删除

```python
items[1] = "new"
replace_in_list(items, 2, "x")
del items[2]
delete_of_list(items, 1)
delete_all_of_list(items)
```

### 4.4 遍历

```python
when green_flag:
    var text = ""
    for item in items:
        text = join(text, item)
    say(text)
```

列表在循环中被修改时，长度会每轮重新读取；不要依赖 Python 的遍历快照语义。

### 4.5 不支持

- `items[1:3]` 切片；
- 负下标；
- `pop/remove/sort/reverse/count/extend/copy`；
- 列表推导式；
- 把列表作为参数传递；
- 两个列表相加。

需要排序时，可以用循环 + 比较 + `replace_in_list` 实现，或使用扩展。

---

## 第 5 章 事件与广播

### 5.1 键盘

```python
when key_pressed("space"):
    say("跳")

when key_pressed("right arrow"):
    change_x(10)
```

键名使用 Scratch 写法：`"space"`、`"a"`、`"up arrow"`、`"left arrow"`、
`"any"` 等。

### 5.2 点击

```python
when clicked:
    say("你点了我")
```

### 5.3 广播

```python
# 舞台
when green_flag:
    broadcast("start")

# 角色
when broadcast("start"):
    say("开始！")
```

`broadcast_and_wait` 会等待接收脚本结束：

```python
when green_flag:
    broadcast_and_wait("load")
    say("加载完成")
```

### 5.4 背景切换

```python
when backdrop_switches_to("game"):
    say("进入游戏场景")
```

### 5.5 计时器与响度

```python
when timer > 10:
    say("10 秒了")

when loudness > 20:
    say("太吵了")
```

目前只支持 `>`。

### 5.6 克隆体启动

```python
when green_flag:
    create_clone("_myself_")

when clone_start:
    say("我是克隆体")
    delete_this_clone()
```

---

## 第 6 章 克隆

### 6.1 克隆自己

```python
when green_flag:
    for i in range(10):
        create_clone("_myself_")

when clone_start:
    set_size(random(20, 100))
    goto(random(-200, 200), random(-150, 150))
    wait(2)
    delete_this_clone()
```

### 6.2 克隆其他角色

```python
when green_flag:
    create_clone("Bullet")
```

角色名就是文件名（嵌套角色使用 `//` 名称）。

### 6.3 局部变量与全局变量

```python
init:
    var hp = 100          # 每个克隆体独立
    list trail = []       # 每个克隆体独立

# 舞台
init:
    var score = 0         # 所有角色/克隆体共享
```

克隆体复制局部变量的 **当前值**；之后互不影响。

### 6.4 删除克隆体

```python
when clone_start:
    if hp <= 0:
        delete_this_clone()
```

本体调用 `delete_this_clone()` 无效。

---

## 第 7 章 自制积木与递归

### 7.1 定义与调用

```python
def greet(name, *, types="s"):
    say(join("Hello ", name))

when green_flag:
    greet("Cat")
```

### 7.2 参数默认值

```python
def greet(name="world", *, types="s"):
    say(join("Hello ", name))

when green_flag:
    greet()
    greet("Cat")
```

### 7.3 返回值

```python
def add(a, b, *, types="nn"):
    return a + b

when green_flag:
    say(add(2, 3))
```

`return` 会生成 TurboWarp 的 `procedures_return`；原生 Scratch 不支持返回值。

### 7.4 递归

```python
def fact(n, *, types="n", warp=True):
    if n <= 1:
        return 1
    return n * fact(n - 1)

when green_flag:
    say(fact(5))       # 120
```

建议给纯计算递归加 `warp=True`，避免每层调用都让出一帧。

递归里用 `while` 维护循环状态时，最好把状态作为参数传入；编译器会对 `while` 条件里、循环体自身会赋值的角色级变量做调用前后保存/恢复，但参数传递更直观、也没有额外开销。

### 7.5 元信息

```python
def choose(a, b, flag, *, types="nnb", warp=False, label="choose %n %n %b"):
    if flag:
        return a
    return b
```

| 元信息 | 说明 |
|--------|------|
| `types` | `s` 字符串、`n` 数字、`b` 布尔；长度必须等于参数个数 |
| `warp` | 运行时不刷新屏幕 |
| `label` | 自定义 proccode；`%s/%n/%b` 数量必须等于参数个数 |

### 7.6 限制

- 不支持装饰器；
- 不支持 `*args` / `**kwargs`；
- 不支持嵌套函数；
- 不能在函数内给参数赋值；
- 调用参数只能按位置传递。

---

## 第 8 章 宏

### 8.1 定义

`macros.scpy` 只允许 `def`：

```python
def twice(x, *, types="n"):
    return x * 2

def quad(x, *, types="n"):
    return twice(twice(x))
```

### 8.2 使用

```python
when green_flag:
    say(quad(3))
```

导出时会：

1. 扫描角色调用了哪些宏；
2. 递归收集依赖（`quad` → `twice`）；
3. 把用到的宏复制到该角色；
4. 角色本地同名函数优先；
5. 未使用的宏不复制。

### 8.3 注意事项

- 宏里的变量按使用它的角色解析；
- 宏名不要与内置函数重名；
- 宏文件不能写 `when`、`init` 或普通语句；
- 子目录里的 `macros.scpy` 会被忽略。

---

## 第 9 章 造型、声音与资产

### 9.1 目录

```text
my_project/
├── assets/
│   ├── cat.svg
│   ├── cat2.png
│   └── meow.wav
├── stage.scpy
└── Cat.scpy
```

### 9.2 引用

```python
init:
    costumes = ["cat.svg", "cat2.png"]
    sounds = ["meow.wav"]
```

### 9.3 规则

- 支持 `svg/png/jpg/jpeg/wav/mp3`；
- 造型名默认是文件名（不含扩展名）；
- 同名自动加 `_2`；
- 旋转中心默认图片中心；
- 同一资源被多个角色引用时只导出一次；
- 缺失资源会在导出时报错。

### 9.4 切换

```python
when green_flag:
    switch_costume("cat2")
    next_costume()
    play_sound("meow")
    switch_backdrop("night")
```

---

## 第 10 章 扩展

### 10.1 声明

```python
init:
    extensions = ["pen", "music"]
```

### 10.2 内置封装

```python
when green_flag:
    pen_clear()
    pen_down()
    set_pen_color("#ff0000")
    set_pen_size(5)
    move(100)
    pen_up()

    set_tempo(120)
    play_note(60, 0.5)
    rest(0.5)
    play_drum(1, 0.25)
```

### 10.3 自定义扩展

`extensions.json`：

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
    }
  }
}
```

使用：

```python
when green_flag:
    myext.jump(10, MODE="fast")
    say(myext.speed())
```

### 10.4 通用调用

```python
ext("myext", "myext_jump", HEIGHT=10)
say(ext("myext", "myext_getSpeed"))
```

通用调用没有字段，所有关键字参数都作为输入。

---

## 第 11 章 嵌套工程目录

```text
game/
├── stage.scpy
├── Player.scpy
├── enemies/
│   ├── Slime.scpy
│   └── Boss.scpy
└── ui/
    └── HUD.scpy
```

导出后的角色名：

```text
Player
enemies//Slime
enemies//Boss
ui//HUD
```

规则：

- 舞台只能有一个，必须在根目录；
- 子目录不能有 `stage.scpy`；
- 资产仍然统一放在根目录 `assets/`；
- 角色名中的 `//` 是命名空间分隔符，不是路径。

---

## 第 12 章 常用配方

### 12.1 计数器

```python
init:
    var score = 0

when green_flag:
    while True:
        score += 1
        say(score)
        wait(1)
```

> ScPython 没有 `forever` 关键字；无限循环请写 `while True:`。

### 12.2 列表求和

```python
init:
    list values = []
    var total = 0

when green_flag:
    values.append(10)
    values.append(20)
    values.append(30)
    total = 0
    for v in values:
        total += v
    say(total)      # 60
```

### 12.3 键盘移动

```python
when green_flag:
    while True:
        if key_pressed("right arrow"):
            change_x(5)
        if key_pressed("left arrow"):
            change_x(-5)
        if key_pressed("up arrow"):
            change_y(5)
        if key_pressed("down arrow"):
            change_y(-5)
```

### 12.4 场景切换

```python
# stage.scpy
when green_flag:
    broadcast("menu")

# Menu.scpy
when broadcast("menu"):
    show()
    say("按空格开始")

when key_pressed("space"):
    hide()
    broadcast("game")
```

### 12.5 克隆雨

```python
when green_flag:
    while True:
        create_clone("_myself_")
        wait(0.2)

when clone_start:
    goto(random(-220, 220), 180)
    set_size(random(20, 60))
    while y_position() > -170:
        change_y(-5)
    delete_this_clone()
```

### 12.6 对话系统

```python
init:
    list lines = ["你好", "欢迎来到 ScPython", "再见"]
    var index = 0

when green_flag:
    index = 0
    for line in lines:
        say_for(line, 2)
```

### 12.7 生命值与伤害

```python
init:
    var hp = 100

when broadcast("hit"):
    hp -= 10
    if hp <= 0:
        say("游戏结束")
        stop_all()
```

### 12.8 递归阶乘

```python
def fact(n, *, types="n", warp=True):
    if n <= 1:
        return 1
    return n * fact(n - 1)

when green_flag:
    say(fact(6))       # 720
```

### 12.9 宏复用

```python
# macros.scpy
def clamp(v, low, high, *, types="nnn"):
    if v < low:
        return low
    if v > high:
        return high
    return v

# Cat.scpy
when green_flag:
    say(clamp(150, 0, 100))    # 100
```

### 12.10 画笔轨迹

```python
init:
    extensions = ["pen"]

when green_flag:
    pen_clear()
    pen_down()
    set_pen_size(3)
    for i in range(36):
        move(10)
        turn_right(10)
    pen_up()
```

---

## 第 13 章 错误与调试

### 13.1 错误格式

```text
C:\...\Cat.scpy:14: 列表不能作为值使用；请用 item_of/length_of/...
```

包含文件、行号、原因。

### 13.2 常见错误对照

| 错误 | 原因 | 修复 |
|------|------|------|
| 未知函数 xxx | 拼写错误或宏未定义 | 检查内置函数表/宏名 |
| 列表不能作为值使用 | 把列表当变量 | 用 `item_of/list_contents` |
| xxx 是变量，不是列表 | 对变量用下标 | 声明为 `list` |
| 不支持 f-string | 用了 `f"{x}"` | 用 `join(x, "")` |
| 不支持字符串方法 | `.upper()` 等 | 用 `contains/join/letter_of` |
| 不支持切片 | `items[1:3]` | 用循环 + `item_of` |
| 自定义积木不支持关键字参数 | 调用时写了 `f(x=1)` | 改为位置参数 |
| types 数量不匹配 | `types` 长度不等于参数个数 | 补齐 `s/n/b` |
| 找不到资源 | assets 下缺文件 | 补齐文件或修正路径 |
| meta.vm 格式错误 | 内部元数据 | 由导出器自动保证 |

### 13.3 调试流程

1. `python -m scpython check <目录>`；
2. 修复第一条错误；
3. 重复直到无错误；
4. 导出 `.sb3`；
5. 用 Scratch/TurboWarp 运行；
6. 需要逐积木排查时用 Scratch VM：

```bash
cd src
python -m scratch_vm ..\out.sb3 --headless --frames 60 --stats --dump-vars
python -m scratch_vm ..\out.sb3 --debug --break-opcode data_setvariableto
```

---

## 第 14 章 AI 生成工作流

### 14.1 生成前：建立项目计划

让 AI 先输出：

```text
项目名：
舞台：
角色列表：
每个角色的造型/声音：
全局变量：
每个角色的局部变量/列表：
事件与脚本：
宏函数：
扩展：
```

### 14.2 生成规则

AI 必须遵守：

1. 每个文件是完整 `.scpy`，不要输出 Markdown 代码围栏到文件内容；
2. 根目录必须有 `stage.scpy`；
3. 只用本文档列出的语法；
4. 不用 class、装饰器、字典、集合、推导式、f-string；
5. 字符串拼接用 `join`；
6. 列表索引用 1 起始；
7. `when` 头不能用装饰器；
8. 自制积木元信息写在 `*` 后；
9. 资源只引用 `assets/` 下已存在的文件；
10. 生成后必须运行 `python -m scpython check`。

### 14.3 推荐提示词模板

```text
你是一个 ScPython 代码生成器。
请为一个 Scratch 项目生成工程文件夹，严格使用 ScPython 语法。

要求：
- 根目录 stage.scpy；每个角色一个 .scpy；可选 macros.scpy；
- 只用 ScPython 支持的语法（参考 docs/scpython.md）；
- 不使用 class/装饰器/字典/集合/推导式/f-string/字符串方法；
- 字符串拼接用 join；
- 列表索引从 1 开始；
- 事件用 when ...:；自制积木用 def f(x, *, types="n", warp=False):
- 需要共享的函数放 macros.scpy；
- 资源引用 assets/ 下的文件。

输出格式：
【文件】相对路径
（文件内容，不要代码围栏）

项目需求：<在这里写需求>
```

### 14.4 AI 自检清单

生成完成后逐项检查：

- [ ] `stage.scpy` 存在；
- [ ] 每个角色有独立文件；
- [ ] 所有 `when` 头拼写正确；
- [ ] 所有函数调用名存在；
- [ ] 列表只用 1 起始下标和允许的函数；
- [ ] 没有 `==` 用于身份比较的误用；
- [ ] 字符串拼接用 `join`；
- [ ] 自定义积木 `types` 长度正确；
- [ ] 宏文件只有 `def`；
- [ ] 资产文件存在；
- [ ] `python -m scpython check` 通过。

### 14.5 修复循环

```text
运行 check
  -> 读取第一条错误（文件:行号）
  -> 只修复该处
  -> 再运行 check
  -> 直到通过
  -> 导出的 sb3 用 scratch_vm --stats 运行
```

不要一次重写整个项目；按错误逐条修复更稳定。

---

## 第 15 章 导出的 SB3 细节

### 15.1 变量 ID

ScPython 为变量生成唯一 ID：

```text
舞台全局: var_g_1, var_g_2 ...
角色局部: var_s1_1, var_s2_1 ...
列表:     list_g_1, list_s1_1 ...
```

同名全局/局部变量不会互相覆盖。

### 15.2 隐藏变量

`break/continue`、`for range` 会生成：

```text
__scpy_break_N
__scpy_continue_N
__scpy_i_N
__scpy_stop_N
__scpy_idx_N
```

它们会出现在变量面板中，可以忽略或隐藏。

### 15.3 宏复制

宏不是运行时共享，而是 **编译期复制**：

- 每个使用宏的角色都有一份自己的自制积木定义；
- 宏的依赖会递归复制；
- 角色本地同名函数优先。

### 15.4 资产

- 文件名是 MD5 + 扩展名；
- 造型包含 `bitmapResolution: 1`；
- 旋转中心自动计算；
- 同名造型自动加 `_2`。

### 15.5 元数据

导出器保证：

```json
"meta": {
  "semver": "3.0.0",
  "vm": "0.11.0",
  "agent": "ScPython exporter"
}
```

`vm` 必须符合 `x.y.z`，否则 TurboWarp 会拒绝加载。

---

## 第 16 章 进阶练习

1. 做一个打砖块：列表存砖块坐标，克隆体碰撞后删除列表项。
2. 做一个打字游戏：列表存单词，`ask_and_wait` 输入，比较答案。
3. 做一个塔防：宏定义 `distance`、`clamp`，多个角色共享。
4. 做一个状态机：用 `when broadcast` 切换菜单/游戏/结束。
5. 用 `extensions.json` 接入一个自定义扩展，并在 ScPython 中调用。

---

## 参考

- [ScPython 语言参考](scpython.md)
- [ScPython 与 Scratch 行为](scpython-scratch-behavior.md)
- [Scratch VM 执行语义](scratch-vm-execution.md)
- [SB3 文件结构](sb3-format.md)
- [Scratch 输入与参数语义](scratch-semantics.md)
- [Scratch Wiki](https://en.scratch-wiki.info/)
- [TurboWarp 文档](https://docs.turbowarp.org/)
