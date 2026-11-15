# Scratch 3.0 <-> Python 双向转换器

> 版本 **0.9.5** · [MIT License](LICENSE)

一个强大的 Scratch 3.0 与 Python 之间的双向转换工具，支持**一比一对应**的转换，同时支持高级 Python 语法。

## 核心特性

- **双向转换**: Scratch (.sb3) <-> Python (.py)
- **中间表示(IR)**: 所有转换通过统一的中间表示，确保一致性
- **一比一映射**: 每个Scratch积木 -> 对应的Python函数调用
- **循环保持**: Scratch的repeat/forever -> Python的for/while循环
- **条件保持**: Scratch的if/if-else -> Python的if/else语句
- **变量保持**: Scratch变量 -> Python实例变量
- **列表保持**: Scratch列表 -> Python列表
- **自制积木**: Scratch自制积木 -> Python类方法
- **两种 Python -> Scratch 模式**: DSL 模式保证高保真往返；通用模式可转换普通 Python 脚本（实验性）
- **语义说明**: 空输入、缺失参数与类型转换的完整规则见 [docs/scratch-semantics.md](docs/scratch-semantics.md)
- **图形特效**: 颜色、亮度、透明度、鱼眼、旋涡、像素化、马赛克（与 scratch-render 的变换公式一致）

## 架构

```
Scratch JSON  <--->  中间表示(IR)  <--->  Python 代码
   (sb3)          (AST/块结构)          (py文件)
```

### 模块说明

| 文件 | 说明 |
|------|------|
| `ir.py` | 中间表示定义（BlockType、Expr、Statement等） |
| `scratch_parser.py` | Scratch JSON -> IR 解析器 |
| `scratch_writer.py` | IR -> Scratch JSON 写入器 |
| `python_generator.py` | IR -> Python 代码生成器 |
| `python_parser.py` | Python DSL -> IR 解析器（高保真） |
| `general_python.py` | 通用 Python -> IR 解析器（实验性） |
| `converter.py` | 主转换器入口 |

## 使用方法

### 命令行使用

```bash
# Scratch -> Python
python converter.py scratch2py input.sb3 output.py

# Python -> Scratch（自动识别 DSL / 通用脚本）
python converter.py py2scratch input.py output.sb3

# 指定模式：dsl（本转换器生成的代码，高保真）或 general（任意普通Python脚本）
python converter.py py2scratch input.py output.sb3 --mode dsl
python converter.py py2scratch input.py output.sb3 --mode general

# 往返测试 (Scratch -> Python -> Scratch)
python converter.py roundtrip-sb3 input.sb3 output.sb3

# 往返测试 (Python -> Scratch -> Python)
python converter.py roundtrip-py input.py output.py

# 运行演示
python converter.py demo
```

### Python API 使用

```python
from converter import ScratchConverter

converter = ScratchConverter()

# Scratch -> Python
python_code = converter.scratch_to_python('project.sb3', 'output.py')

# Python -> Scratch
scratch_json = converter.python_to_scratch('script.py', 'project.sb3')

# JSON -> Python
ir = converter.scratch_json_to_python(scratch_json_dict)

# Python代码字符串 -> Scratch JSON
scratch_json = converter.python_code_to_scratch_json(python_code_string)

# 指定模式（auto / dsl / general）
converter.python_to_scratch('script.py', 'project.sb3', mode='general')
```

## 两种 Python -> Scratch 模式

### DSL 模式（默认自动识别，高保真）

输入是本转换器生成的 Python（包含 `ScratchSprite` 类、`when_green_flag`、
`@_as_procedure` 等标记）时自动使用。会解析文件中的所有角色类，
按原顺序生成舞台与多个角色，并完整恢复变量、列表、造型、广播、
自制积木与事件脚本，适合 Scratch -> Python -> Scratch 往返。

### 通用模式（实验性）

输入是普通 Python 脚本时使用（也可用 `--mode general` 强制）。
转换器会把常见语法翻译成 Scratch 积木：

| Python | Scratch |
|--------|---------|
| 顶层语句 | 绿旗脚本 |
| `def f(a):` + `return x` | 自制积木，返回值写入 `__py_ret_f` 变量 |
| `if / elif / else` | `如果…否则` |
| `while cond:` | `重复执行直到 <not cond>` |
| `for i in range(...)` | `重复执行 N 次` + 维护循环变量 |
| `for x in 列表:` | `重复执行 (列表长度) 次` + `第 n 项` |
| `for ch in "abc":` / `for ch in 文本:` | `重复执行 (字符数) 次` + `第 n 个字符` |
| `for i, v in enumerate(...)` | 循环计数器同时写入下标变量（0 起始） |
| `x = 1` / `x += 1` | `将 x 设为` / `将 x 增加` |
| `nums = [1,2,3]` | 创建列表并写入初值 |
| `alias = nums` | 逐项复制（保持 Python 的拷贝语义） |
| `nums.append(x)` / `insert` / `clear` | 列表添加 / 插入 / 删除全部 |
| `nums.pop()` / `pop(i)` | 读取后删除，结果写入临时变量 |
| `nums.index(x)` / `count(x)` / `remove(x)` | 顺序查找（`index` 未找到返回 -1） |
| `nums.reverse()` / `sort()` | 交换循环 / 冒泡排序 |
| `nums[i]` / `nums[i] = x` | 自动把 0 起始下标转换为 Scratch 的 1 起始 |
| `del nums[i]` | 删除列表第 i 项 |
| `a = b = 0` | 连续赋值（右侧只求值一次） |
| `a, b = b, a` | 临时变量解构交换 |
| `a -= x` / `*= x` / `/= x` / `//= x` / `%= x` / `**= x` | 增加/设值 + 对应运算 |
| `a ** b` | 小整数指数展开成乘法，其余按 `e^(b·ln a)` 计算 |
| `min/max(a, b)` / `min/max(列表)` / `sum(列表)` | 数学公式或遍历归并 |
| `"sep".join(列表)` | 循环使用连接积木拼接 |
| `0 < a <= 3` 链式比较 | `与` 组合的多个比较 |
| `x in nums` / `x not in nums` | 列表包含 / 不包含 |
| `"ell" in "hello"` | `包含` 积木（字符串包含） |
| `f"count={count}"` | 连接积木（忽略格式说明） |
| `"a=" + str(a)` / `s += ch` | 含字符串操作数的 `+` 自动使用连接 |
| `a // b` | `floor(a / b)` |
| `range(a, b, step)` | 支持动态起止与步长 |
| `break` / `continue` | 循环标志变量 + 条件包裹，立即跳出/进入下一轮 |
| `print(...)` | 说话 |
| `input(...)` | 询问并等待，返回回答 |
| `math.pi` / `math.e` / `math.tau` | 直接写入常量值 |

自动生成一个蓝色 `Py` 造型和一个白色背景，项目可直接用 Scratch 打开。

**通用模式限制**：类、异常、生成器、装饰器、多返回值、
`match`、`sorted`、大部分字符串方法（`upper/lower/strip/replace/split` 等）、
文件/网络等不支持；遇到时会在命令行打印“转换报告”，
并把这些特性记录到 `ProjectIR.warnings`，不会静默改变语义。

## 转换映射表

### 事件块

| Scratch 积木 | Python 代码 |
|-------------|-------------|
| `当绿旗被点击` | `def when_green_flag(self):` |
| `当按下[空格]键` | `def when_key_pressed_space(self):` |
| `当此角色被点击` | `def when_clicked(self):` |
| `当接收到[消息]` | `def when_broadcast_message(self):` |

### 运动块

| Scratch 积木 | Python 代码 |
|-------------|-------------|
| `移动(10)步` | `self.move(10)` |
| `右转(15)度` | `self.turn_right(15)` |
| `左转(15)度` | `self.turn_left(15)` |
| `移到 x:(0) y:(0)` | `self.goto_xy(0, 0)` |
| `在(1)秒内滑行到 x:(0) y:(0)` | `self.glide_to(1, 0, 0)` |
| `将x坐标增加(10)` | `self.change_x(10)` |
| `将x坐标设为(0)` | `self.set_x(0)` |
| `将y坐标增加(10)` | `self.change_y(10)` |
| `将y坐标设为(0)` | `self.set_y(0)` |
| `碰到边缘就反弹` | `self.if_on_edge_bounce()` |

### 外观块

| Scratch 积木 | Python 代码 |
|-------------|-------------|
| `说[Hello!]` | `self.say("Hello!")` |
| `说[Hello!]持续(2)秒` | `self.say_for("Hello!", 2)` |
| `思考[...]` | `self.think("...")` |
| `思考[...]持续(2)秒` | `self.think_for("...", 2)` |
| `显示` | `self.show()` |
| `隐藏` | `self.hide()` |
| `换成[造型1]造型` | `self.switch_costume("costume1")` |
| `下一个造型` | `self.next_costume()` |
| `将大小增加(10)` | `self.change_size(10)` |
| `将大小设为(100)` | `self.set_size(100)` |

### 控制块

| Scratch 积木 | Python 代码 |
|-------------|-------------|
| `等待(1)秒` | `self.wait(1)` |
| `重复(10)次` | `for _repeat in range(10):` |
| `重复执行` | `while True:` |
| `如果<条件>那么` | `if condition:` |
| `如果<条件>那么...否则` | `if condition: ... else: ...` |
| `等到<条件>` | `self.wait_until(lambda: condition)` |
| `重复执行直到<条件>` | `while not (condition):` |
| `停止[全部]` | `self.stop()` |

### 变量/列表

| Scratch 积木 | Python 代码 |
|-------------|-------------|
| `将[变量]设为(0)` | `variable = 0` |
| `将[变量]增加(1)` | `variable = _sc_add(variable, 1)` |
| `将[项]加入[列表]` | `my_list.append(item)` |
| `删除[列表]的第(1)项` | `_sc_list_delete(my_list, 1)` |
| `删除[列表]的全部项目` | `my_list.clear()` |

### 运算符

| Scratch 积木 | Python 表达式 |
|-------------|-------------|
| `(1) + (2)` | `_sc_add(1, 2)` |
| `(1) - (2)` | `_sc_sub(1, 2)` |
| `(1) * (2)` | `_sc_mul(1, 2)` |
| `(1) / (2)` | `_sc_div(1, 2)` |
| `<(1) < (2)>` | `_sc_lt(1, 2)` |
| `<(1) = (2)>` | `_sc_eq(1, 2)` |
| `<(1) > (2)>` | `_sc_gt(1, 2)` |
| `<()> 且 <()>` | `_sc_and(a, b)` |
| `<()> 或 <()>` | `_sc_or(a, b)` |
| `<不成立>` | `_sc_not(condition)` |
| `在(1)和(10)间取随机数` | `_sc_random(1, 10)` |
| `连接[Hello][World]` | `_sc_join("Hello", "World")` |
| `[Hello]的第(1)个字符` | `_sc_letter_of(1, "Hello")` |
| `[Hello]的字符数` | `_sc_length("Hello")` |
| `(1)对(2)取余` | `_sc_mod(1, 2)` |
| `四舍五入(1.5)` | `_sc_round(1.5)` |

## Scratch 运行时语义

生成的 Python 会在文件顶部定义一组 `_sc_*` 辅助函数，用于复刻 Scratch VM 的行为：

- **类型转换**：`_sc_num`、`_sc_str`、`_sc_bool` 按 Scratch 规则处理空字符串、`"0"`、`"false"`、`NaN`、`Infinity`、`0x/0o/0b` 等。
- **比较**：`_sc_eq/_sc_lt/_sc_gt` 两边都能转数字时按数字比较，否则忽略大小写按字符串比较。
- **运算**：除以 0 得到 `Infinity/NaN`；`_sc_mod` 使用向下取整余数；`_sc_round` 使用 `floor(x + 0.5)`；三角函数使用角度制。
- **列表**：下标支持 `last/random/any`，越界返回空而不是抛异常；“包含/项的位置”使用 Scratch 比较规则。
- **自制积木参数**：未填参数取空字符串（布尔为 `false`），**不是 0**；空字符串只有进入数值运算时才按 0 处理。
- **孤儿积木**：只有以事件帽块（绿旗、按键、点击、广播、背景、克隆体启动等）或自制积木定义开头的脚本会被转换。

完整的输入/参数语义、边界值与已知差异见
[Scratch 输入与参数语义说明](docs/scratch-semantics.md)。

## 示例

### Scratch 原始项目

```json
{
  "blocks": {
    "b1": {
      "opcode": "event_whenflagclicked",
      "next": "b2",
      "topLevel": true
    },
    "b2": {
      "opcode": "control_repeat",
      "inputs": {
        "TIMES": [1, "3"],
        "SUBSTACK": [2, "b3"]
      }
    },
    "b3": {
      "opcode": "motion_movesteps",
      "inputs": {"STEPS": [1, "10"]}
    }
  }
}
```

### 转换后的 Python 代码

```python
class Cat(ScratchSprite):
    def when_green_flag(self):
        """当绿旗被点击时"""
        for _repeat in range(3):
            self.move(10)
```

### 反向转换回 Scratch

从上面的Python代码可以精确地转换回相同的Scratch结构。

## 测试

```bash
# 运行全部测试
python tests/test_all.py

# 运行演示
python converter.py demo
```

## 支持的 Scratch 特性

- [x] 事件块 (绿旗、按键、点击、广播、背景切换)
- [x] 运动块 (移动、转向、面向方向/角色、移到/滑行到随机位置·鼠标·角色、坐标)
- [x] 外观块 (说话、思考、显示/隐藏、造型、大小、背景切换、图层顺序、旋转方式、颜色/亮度/透明度特效)
- [x] 声音块 (播放、停止、音量、音效)
- [x] 控制块 (循环、while、for-each、条件、等待、停止、计数器、单帧执行)
- [x] 侦测块 (触摸、按键、鼠标、计时器、颜色侦测、属性读取、拖拽模式、用户名、像素级碰撞)
- [x] 变量监视器 (显示/隐藏监视器积木会动态创建或隐藏监视器)
- [x] 运算符 (算术、比较、逻辑、字符串、随机)
- [x] 变量 (设置、增加、显示/隐藏)
- [x] 列表 (添加、删除、插入、替换、查询)
- [x] 广播 (发送、接收、等待)
- [x] 自制积木 (定义、调用、参数)
- [x] 克隆 (创建、删除)
- [x] 表达式嵌套 (运算符、函数调用)
- [x] TurboWarp warp 自制积木 / 自定义 reporter / `%s %n %b` 参数
- [x] TurboWarp 扩展积木与 `extensions` 列表往返
- [x] TurboWarp pen / runtimeoptions 扩展与高级选项
- [x] 舞台脚本、music 音乐扩展
- [x] 同一帽子事件的多个并列脚本（自动生成 `when_xxx_2` 等独立方法并全部注册）

## 限制

1. **视觉属性**: 支持颜色(HSV色相旋转)、亮度、透明度(GHOST)、鱼眼、旋涡、像素化、马赛克特效，变换公式与 scratch-render 一致；舞台自身的特效同样作用于背景。鱼眼/旋涡使用 numpy 做逐像素重采样（未安装 numpy 时这两项不生效），像素化/马赛克在无 numpy 时用 pygame 缩放/平铺近似。碰撞检测仍按未变形的造型计算
2. **音效**: 声音播放需要音频库支持；音高(PITCH)只记录数值，平移(PAN)应用到左右声道
3. **舞台属性**: 背景切换、背景编号/名称已支持；视频侦测、文字朗读等扩展未实现
4. **画笔**: 内置 `pen` 扩展支持落笔/抬笔/颜色/粗细/图章/清空；图章会先应用角色当前的颜色/亮度/透明度/形状特效再盖章；透明度不做混色合成
5. **扩展**: 未注册的第三方扩展会保留调用但返回 0，不会中断脚本

## 运行转换后的脚本

生成的 Python 文件自带一个 pygame 版 Scratch 3.0 运行时：

```bash
pip install pygame
python converter.py scratch2py 项目.sb3 项目.py
python 项目.py
```

通用 Python 模式：

```bash
python converter.py py2scratch 脚本.py 项目.sb3 --mode general
```

> `example/` 只是本地示例目录，已在 `.gitignore` 中忽略，仓库不包含其中的 sb3/py 文件。

- 程序会打开舞台窗口，绿旗脚本在后台线程中逐帧执行。
- 启动时窗口自动最大化，舞台按宽高比缩放到窗口的最大可用区域，多余部分补黑边，类似 Scratch 舞台放大到最大时的行为；最大化后仍可自由拉伸窗口，舞台会实时重新适配。鼠标坐标始终换算回舞台逻辑坐标，点击/拖动不受缩放影响。使用 `--windowed` 可以普通窗口尺寸启动。
- 脚本采用 Scratch 式协作调度：同一时刻只有一个脚本在执行，遇到让帧/等待才切换，避免数据驱动的列表被并发读改写破坏。
- 如果输入是 `.sb3`，转换器会把造型/声音资源直接导出到 `.py` 所在目录，脚本运行时从同目录加载；同时兼容旧的 `assets/` 子目录。
- 窗口模式可直接游玩：顶部工具栏有绿旗按钮（与 Scratch 一致，不占用舞台区域），舞台背景默认白色；`ESC` 退出，可拖动开启了拖动模式的角色，`询问并等待` 会在舞台底部弹出输入框；支持中文输入法，按回车（含小键盘）或点击输入框/确认按钮提交；已经输入过内容时，点击窗口任意位置也会提交，多个脚本同时询问时按顺序排队。
- SVG 造型由内置渲染器光栅化（支持 text、内嵌 base64 位图、linear/radial 渐变、rect/circle/ellipse/line/polygon/polyline/path）；文字最后绘制，不会被背景形状遮挡。安装 `cairosvg` 时优先使用 cairosvg。
- 造型按 Scratch 的旋转中心（rotationCenterX/Y）定位，不再在角色下方绘制名字标签。
- 旋转中心可以位于造型左侧/上方（坐标为负），窗口标题栏、拖拽边框等拼接造型会按 Scratch 的位置正确对齐。
- 可见的变量/列表监视器会按 Scratch 中的位置和大小绘制。
- 舞台上的全局变量/列表由所有角色共享；局部变量监视器显示为 `角色名: 变量名`。
- 转换报告会列出暂不支持的积木，生成的 Python 头部也会带同样的注释。

### 调试参数

生成脚本支持任意组合的运行参数：

```bash
python output.py --headless --frames 120 --no-audio
python output.py --headless --seconds 2.5 --fps 60 --seed 42 --trace
python output.py --assets ./my_assets --trace
```

| 参数 | 作用 |
|------|------|
| `--headless` | 无窗口（dummy video），适合 CI/调试 |
| `--frames N` | 运行 N 帧后退出 |
| `--seconds T` | 运行 T 秒后退出 |
| `--fps N` | 覆盖运行时帧率 |
| `--seed N` | 设置随机种子 |
| `--trace` | 打印绿旗/按键/广播/脚本/自制积木调用 |
| `--no-audio` | 禁用 pygame.mixer |
| `--assets DIR` | 覆盖素材目录 |
| `--interpolation` | TurboWarp 插值（平滑渲染） |
| `--turbo` | Turbo 模式（循环不逐帧等待） |
| `--no-fencing` | Remove Fencing（移除舞台边界限制） |
| `--infinite-clones` | Infinite Clones（取消 300 克隆上限） |
| `--remove-misc-limits` | Remove Misc Limits（移除音量等杂项限制） |
| `--stage-size 640x360` | Custom Stage Size（自定义舞台尺寸） |
| `--hq-pen` | High Quality Pen（画笔抗锯齿） |
| `--warp-timer 0.5` | Warp Timer（warp 过程最长占用秒数） |
| `--disable-compiler` | 兼容参数（Python 版无编译器） |
| `--windowed` | 普通窗口启动（默认启动即最大化） |

## TurboWarp 兼容

转换器会读取 TurboWarp 保存在注释里的高级选项（注释内包含 `// _twconfig_`，格式如
`{"framerate":60,"runtimeOptions":{"fencing":false}}`），并把它作为生成脚本的默认运行参数；
命令行参数仍然可以覆盖这些默认值。

支持读取：`framerate/fps`、`fencing`、`miscLimits`、`interpolation`、`turbo`、`hqPen`、`compiler`、`cloneLimit`（0 表示无限）、`warpTimer`、`stageWidth/stageHeight`。

转换器按 TurboWarp 的 `project.json` 行为处理，而不是把 TurboWarp 特性降级成普通 Scratch：

| 特性 | 行为 |
|------|------|
| `warp` 自制积木 | 保留 definition/call 的 mutation，Python 侧生成 `@_as_procedure(warp=True)`，循环内不逐帧等待 |
| `proccode` / `argumentids` / `argumentdefaults` | 原样保留并写回，参数名不再被重新生成 |
| `%s` / `%n` / `%b` 参数 | 按 proccode 解析类型；Python 缺省值取 `argumentdefaults`（空字符串 / `False`）；布尔参数使用 `argument_reporter_boolean` |
| 自定义 reporter | `procedures_return` → `return`，`procedures_call` 可作为表达式参与运算 |
| 扩展积木 | 任意 `extensions` 中的扩展块转为 `self.extension(namespace, opcode, inputs, fields)`；未注册的扩展返回 `0` 而不是报错 |
| `pen` 扩展 | 落笔/抬笔/清空/图章/颜色/颜色参数/粗细/色相/明度 |
| `runtimeoptions` 扩展 | 运行时修改帧率、插值、Turbo、Fencing、杂项限制、克隆上限、舞台尺寸 |

TurboWarp 高级选项既可以通过生成脚本的命令行参数设置（见上表），也可以在项目里直接用 Runtime Options 扩展积木设置。

扩展入口：

```python
ScratchRuntime.register_extension("myext", handler)
# handler(runtime, sprite, opcode, inputs, fields)
# 精灵内调用: self.extension("myext", "opcode", {inputs}, {fields})
```

## 依赖

- Python 3.8+
- 转换本身只使用标准库
- 运行生成的脚本需要 `pygame`（`pip install pygame`）

## 许可

MIT License
