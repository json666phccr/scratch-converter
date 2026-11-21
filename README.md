# Scratch 3.0 <-> Python 双向转换器

> 版本 **0.15.0** · [MIT License](LICENSE)

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
- **Scratch VM**: 内置纯 IR 解释器，可直接读取 sb3 并执行，无需先生成 Python；支持命令行调试器与窗口内可视化调试面板
- **ScPython**: 新语言 `.scpy`，Python 风格语法 + Scratch 语义；一个工程文件夹编译为 sb3，支持角色文件、舞台、宏、嵌套目录、资产与自定义扩展
- **混淆导出**: SB3 -> 单文件 Python，多态加密配方、常量折叠、AST 混淆、字符串加密、code object 加密载荷、builtins 完整性探针与资产内嵌内容重构
- **Tier 2 商业分发**（可选）: Ed25519 许可证绑定机器（参与密钥派生，无可 patch 的校验分支）+ `--native` Cython 原生编译（字节码级工具失效）
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
| `runtime_code/` | 生成脚本使用的运行时模板；`extensions/` 下按扩展拆分子文件，由 `config.json` 描述处理器、别名与依赖，生成时按需拼装 |
| `python_parser.py` | Python DSL -> IR 解析器（高保真） |
| `general_python.py` | 通用 Python -> IR 解析器（实验性） |
| `scratch_vm/` | 纯 IR 解释器：直接执行 sb3，支持断点、单步、trace、变量查看与可视化调试 |
| `scpython/` | `.scpy` 语言编译器：工程目录 -> sb3，支持宏、嵌套角色、资产与自定义扩展 |
| `obfuscator/` | SB3 -> 混淆 Python：常量折叠、AST 混淆、加密载荷、内嵌资产 |
| `convert_log.py` | 转换日志（阶段、中间状态、异常定位） |
| `converter.py` | 主转换器入口 |

## 使用方法

### 命令行使用

```bash
# Scratch -> Python
# 默认生成独立项目文件夹：output/output.py + output/assets/
python converter.py scratch2py input.sb3 output.py

# 同一目录转换多个项目时素材不会互相覆盖；--no-bundle 可恢复旧的平铺输出
python converter.py scratch2py input.sb3 output.py --no-bundle

# 模块化输出：入口 + 运行时 + 每个角色一个模块（大项目更易读）
python converter.py scratch2py input.sb3 output.py --split

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

# 转换日志：-v 输出各阶段与中间状态，--log-file 同时写入文件
python converter.py -v scratch2py input.sb3 output.py
python converter.py -v --log-file convert.log scratch2py input.sb3 output.py
python converter.py --quiet scratch2py input.sb3 output.py
```

日志级别可用 `--log-level debug|info|warning|error|quiet` 或环境变量
`SCRATCH_LOG_LEVEL` 设置。转换失败时会输出所处阶段、异常信息以及转换器源码中的
具体文件/行号（加 `-v` 还会打印完整调用栈），便于定位是哪个阶段、哪个积木出的问题。

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

## Scratch VM（解释执行与调试）

除转换之外，`src/scratch_vm/` 还提供一台**纯 IR 解释器**：直接读取 `.sb3`
并逐块执行，不需要先生成 Python 文件。它复用现有 pygame 运行时，因此渲染、
画笔、克隆、音频、询问框和内置扩展的行为与生成脚本一致。

### 运行

```bash
# 在 src 目录下执行（或把 src 加入 PYTHONPATH）
cd src

# 窗口运行
python -m scratch_vm ..\example\general_demo.sb3

# 无窗口运行 60 帧并输出统计
python -m scratch_vm ..\example\general_demo.sb3 --headless --frames 60 --no-audio --stats

# 启用交互调试
python -m scratch_vm ..\example\general_demo.sb3 --debug

# 启动即暂停，并在指定 opcode 上断点
python -m scratch_vm game.sb3 --debug --pause-on-start --break-opcode data_setvariableto

# 条件断点 + watch
python -m scratch_vm game.sb3 --debug --break-if "var('分数') > 10" --watch "var('分数')"
```

### 运行参数

| 参数 | 说明 |
|------|------|
| `--headless` | 无窗口（SDL dummy），适合自动化 |
| `--fps N` | 覆盖帧率 |
| `--frames N` / `--seconds N` | 运行上限 |
| `--seed N` | 随机种子 |
| `--turbo` | 立即模式（循环尽量不让帧） |
| `--no-fencing` | 关闭舞台边界限制 |
| `--no-audio` | 关闭声音 |
| `--stage-size WxH` | 自定义舞台尺寸 |
| `--infinite-clones` | 解除 300 克隆上限 |

### 调试参数

| 参数 | 说明 |
|------|------|
| `--debug` | 交互调试，从 stdin 读取命令 |
| `--pause-on-start` | 启动后立即暂停 |
| `--trace` | 打印每条执行的积木 |
| `--trace-size N` | trace 环形缓冲大小（默认 2000） |
| `--break-opcode OP` | 按 opcode 设断点，可逗号分隔或重复指定 |
| `--break-sprite NAME` | 按角色名设断点（克隆体写作 `名字#clone`） |
| `--break-block ID` | 按 block id 设断点 |
| `--break-if EXPR` | 条件断点，可用 `sprite`/`runtime`/`frame`/`var()`/`lst()` |
| `--watch EXPR` | watch 表达式，退出前可反复查看 |
| `--no-overlay` | 关闭窗口内可视化面板 |
| `--stats` | 退出时打印执行统计 |
| `--dump-vars` | 退出时打印变量/列表 |

### 交互命令

`--debug` 模式下输入：

| 命令 | 别名 | 说明 |
|------|------|------|
| `help` | `h` | 命令列表 |
| `continue` | `c` | 继续运行 |
| `pause` | `p` | 暂停 |
| `step` | `s` | 单步一个积木 |
| `frame` | `sf` | 单步一帧 |
| `trace [n]` | `t` | 最近 n 条执行记录 |
| `stack` | `bt` | 所有线程的调用栈 |
| `threads` | `th` | 活动线程列表 |
| `vars [角色]` | `v` | 查看变量/列表 |
| `watch [表达式]` | `w` | 查看或添加 watch |
| `break opcode/sprite/block/if 值` | `b` | 设置断点 |
| `breaks` | `bl` | 断点列表 |
| `delete N\|all` | `bd` | 删除断点 |
| `stats` | `st` | 执行统计 |
| `overlay` | `o` | 切换可视化面板 |
| `quit` | `q` | 退出 |

### 可视化调试面板

窗口模式下默认在左上角显示半透明面板（F2 开关）：

```text
[VM] PAUSED  frame 123  fps 30  threads 4  clones 2
位置: Cat  motion_movesteps  block=abc123
栈: 当绿旗被点击 > 我的积木 add %s %s
变量: 分数=10  速度=3
断点 2  trace 2000  语句 15352  错误 0
```

面板不会暂停 pygame 主循环；暂停的只是脚本线程。

### Python API

```python
from scratch_vm import run_project

result = run_project(
    "game.sb3",
    headless=True,
    max_frames=60,
    audio=False,
)
print(result["variables"])   # 变量/列表快照
print(result["stats"])       # opcode / 角色执行统计
```

### 实现文档

- [SB3 文件结构详解](docs/sb3-format.md)
- [Scratch VM 执行语义](docs/scratch-vm-execution.md)
- [Scratch VM 实现设计](docs/scratch-vm-design.md)
- [Scratch 输入与参数语义](docs/scratch-semantics.md)

### 已知限制

- 只支持内置扩展；未知扩展返回 0 并记录警告；
- 递归深度受 Python 栈限制；
- SVG 使用内置简化渲染器，复杂矢量图可能失真；
- 与官方 JS VM 的字符串长度（UTF-16 vs 码点）、超大整数精度存在差异。

## ScPython（.scpy）

ScPython 是一门 **Python 风格、Scratch 语义** 的文本语言。一个工程文件夹直接编译为 `.sb3`：

```text
my_project/
├── stage.scpy        # 舞台
├── Cat.scpy          # 角色（文件名即角色名）
├── macros.scpy       # 所有角色可复用的宏
├── extensions.json   # 自定义扩展声明
└── assets/
    ├── cat.svg
    └── meow.wav
```

```python
# Cat.scpy
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

def add_score(amount, *, types="n", warp=True):
    score += amount
```

```bash
cd src

# 语法检查
python -m scpython check ..\example\scpy_demo

# 导出 sb3
python -m scpython export ..\example\scpy_demo -o ..\example\scpy_demo.sb3

# 把现有 sb3 转成 ScPython 工程（相同自制积木自动抽到 macros.scpy）
python -m scpython import ..\example\scpy_demo.sb3 -o ..\example\scpy_imported

# 调试：静态检查 + 无头运行
python -m scpython lint ..\example\scpy_demo
python -m scpython run ..\example\scpy_demo --seconds 3 --trace 20 --stats

# 主转换器别名
python converter.py scpy2scratch ..\example\scpy_demo ..\example\scpy_demo.sb3
python converter.py sb32scpy ..\example\scpy_demo.sb3 ..\example\scpy_imported
```

特性：

- `==` / `!=` 使用 Scratch 比较规则；`+` 是 Scratch 数字加法，字符串用 `join`；
- 列表索引从 1 开始，只支持原版 Scratch 列表操作；
- 每个文件一个角色，`units/Bat.scpy` 导出为角色 `units//Bat`；
- `macros.scpy` 中的函数在角色调用时按需复制到角色内（含传递依赖）；
- **sb3 → ScPython**：转换事件/变量/列表/自制积木/注释；默认分析各角色中**完全相同**的自制积木并抽到 `macros.scpy`（`--no-macros` 可关闭）；全局变量只在舞台声明；
- **列表默认值**：`list xs = txt("data.txt")` 或 `debug.import_list(xs, "data.txt")` 直接读文本文件（每行一项）；
- **调试方法**：`debug.set_default` / `debug.set_list_default` 改变量/列表默认值，`debug.set_var` / `debug.reset` 运行期改值或恢复默认值，`debug.print/trace/watch/assert` 作为编译期提示输出；
- **调试工具**：`scpython lint` 检查未使用的变量/列表/自制积木/宏；`scpython run` 在本机无头 VM 中运行并输出变量、watch 表达式、统计与最近执行轨迹；编译错误附带源码行与列指示；
- 支持 pen/music 内置封装与 `extensions.json` 自定义扩展；
- `assets/` 自动计算 MD5、造型尺寸与旋转中心，资源自动去重；
- 导出前校验 SB3 元数据与目标结构（`meta.vm`、`targets`、造型/声音字段），避免 TurboWarp 拒绝打开；
- 事件用 `when ...:`，自制积木用 `def` + `*` 元信息（`types`/`warp`/`label`）；
- 拒绝 class、装饰器、字典/集合、推导式、f-string、字符串方法、列表切片等高级语法。

文档：

- [ScPython 编写教程](docs/scpython-tutorial.md)（Scratch 机制 + 从零教程 + 常用配方 + AI 工作流）
- [ScPython 语言指南](docs/scpython.md)
- [ScPython AI 速查表](docs/scpython-ai-cheatsheet.md)
- [ScPython 与 Scratch 行为参考](docs/scpython-scratch-behavior.md)

## SB3 -> 混淆 Python（单向）

把 `.sb3` 转换为**单文件、可执行的混淆 Python**，适合分发但不希望直接暴露源码的场景。

```bash
cd src

# 默认内嵌资产，输出单文件
python -m obfuscator ..\example\scpy_demo.sb3 ..\example\scpy_demo_obf.py

# 主转换器别名
python converter.py sb3obf ..\example\scpy_demo.sb3 ..\example\scpy_demo_obf.py

# 外部资产 / 关闭常量折叠 / 固定随机种子
python -m obfuscator input.sb3 output.py --no-embed-assets
python -m obfuscator input.sb3 output.py --no-fold
python -m obfuscator input.sb3 output.py --seed 123
```

处理内容：

- **常量折叠**：`1 + 2` -> `3`，`join("a", 5)` -> `"a5"`，恒定 `if`/`repeat 0`/`wait until true` 直接简化；
- **源码信息清除**：删除注释/docstring、运行时 “Scratch 3.0” 标识、`--trace` 调试输出；
- **AST 混淆**：顶层函数/类与类方法重命名、属性访问派发表（字节码无 Scratch 方法名）、链式加密字符串表、垃圾函数与死分支、行号抹平；
- **函数簇懒加载**：顶层函数拆分为独立加密的簇，首次调用才解密——hook 一次 `exec` 只能拿到单个簇；
- **载荷加密**：密钥分裂（文件中无完整密钥）+ 每段独立 salt + HMAC-SHA256 完整性标签 + SHA-256 密钥流异或 + base85；
- **Silent Corrupt**：篡改/调试器/版本不符不报错，静默翻钥让垃圾数据远处崩溃；启动 + 周期反调试探针；
- **资产内嵌**：匿名重命名 + 按需解密 + 虚拟文件系统，全程不落盘。

运行：

```bash
python output.py --headless --frames 60 --no-audio
```

注意：marshal code object 与 Python `major.minor` 绑定，输出脚本需用与生成时相同的 Python 版本运行。纯 Python 混淆无法做到绝对不可破解，详见文档。

文档：[SB3 -> 混淆 Python](docs/obfuscator.md)

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
| 递归 / 互相递归 | 参数与局部变量改用列表帧栈（进入压栈、返回出栈），多层调用互不覆盖 |
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
| `part = nums[1:3]` | 复制区间内的项到新列表（支持负下标与省略端点） |
| `[x * 2 for x in nums if x > 0]` | 简单列表推导式（单循环 + 可选条件） |
| `for a, b in zip(xs, ys):` | 按最短列表逐项遍历 |
| `random.shuffle(nums)` | 原地 Fisher-Yates 洗牌 |
| `a = b = 0` | 连续赋值（右侧只求值一次） |
| `a, b = b, a` | 临时变量解构交换 |
| `a -= x` / `*= x` / `/= x` / `//= x` / `%= x` / `**= x` | 增加/设值 + 对应运算 |
| `a ** b` | 小整数指数展开成乘法，其余按 `e^(b·ln a)` 计算 |
| `min/max(a, b)` / `min/max(列表)` / `sum(列表)` | 数学公式或遍历归并 |
| `"sep".join(列表)` | 循环使用连接积木拼接 |
| `0 < a <= 3` 链式比较 | `与` 组合的多个比较 |
| `x in nums` / `x not in nums` | 列表包含 / 不包含 |
| `"ell" in "hello"` | `包含` 积木（字符串包含） |
| `s[0]` / `s[-1]` | `第 n 个字符`，负下标自动换算到末尾 |
| `s[1:4]` / `s[-3:]` | 逐字符拼接出切片结果 |
| `"-" * 3` / `s * n` | 常量折叠或循环重复连接 |
| `f"count={count}"` | 连接积木（忽略格式说明） |
| `"a=" + str(a)` / `s += ch` | 含字符串操作数的 `+` 自动使用连接 |
| `a // b` | `floor(a / b)` |
| `range(a, b, step)` | 支持动态起止与步长 |
| `break` / `continue` | 循环标志变量 + 条件包裹，立即跳出/进入下一轮 |
| `print(...)` | 说话 |
| `input(...)` | 询问并等待，返回回答 |
| `math.pi` / `math.e` / `math.tau` | 直接写入常量值 |
| `random.randint(a, b)` / `random.random()` / `random.uniform(a, b)` | 随机数积木 |
| `random.choice(列表)` / `random.choice("abc")` | 列表随机项 / 随机字符 |
| `time.sleep(x)` | 等待 x 秒 |
| `sorted(列表)` / `reversed(列表)`（for 循环或赋值） | 复制到隐藏列表后排序 / 反转 |
| `列表.copy()` / `列表.extend(其它列表)` | 逐项复制 / 追加 |
| `a if cond else b` | 临时变量 + 如果/否则（两条分支都会先求值） |
| `round(x, n)` | `round(x × 10ⁿ) ÷ 10ⁿ` |
| `pow(a, b)` / `math.pow` / `math.fabs` | 幂运算 / 绝对值 |
| `f"{x:.2f}"` | 四舍五入到 N 位小数（末尾 0 会被省略） |
| `enumerate(列表, start)` | 从 start 开始的下标 |

自动生成一个蓝色 `Py` 造型和一个白色背景，项目可直接用 Scratch 打开。

**通用模式限制**：类、异常、生成器、装饰器、多返回值、
`match`、大部分字符串方法（`upper/lower/strip/replace/split` 等）、
把列表作为函数参数、文件/网络等不支持；遇到时会在命令行打印“转换报告”，
并把这些特性记录到 `ProjectIR.warnings`，不会静默改变语义。
递归函数通过列表帧栈隔离参数/局部变量，但递归深度仍受 Scratch 自制积木
调用栈限制；与运行时属性重名的变量（如 `answer`、`timer`）会改用
`var_answer` 之类的隐藏属性，Scratch 中显示的变量名保持不变。
条件表达式和 `if` 一样，两条分支都会先求值，含副作用的表达式结果可能不同。

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

- [x] 事件块 (绿旗、按键、点击、广播、背景切换、当计时器/响度大于设定值)
- [x] 运动块 (移动、转向、面向方向/角色、移到/滑行到随机位置·鼠标·角色、坐标)
- [x] 外观块 (说话、思考、显示/隐藏、造型、大小、背景切换、图层顺序、旋转方式、颜色/亮度/透明度特效)
- [x] 声音块 (播放、停止、音量、音高变调、左右平衡)
- [x] 控制块 (循环、while、for-each、条件、等待、停止、计数器、单帧执行)
- [x] 侦测块 (触摸、按键、鼠标、计时器、响度（可选麦克风）、颜色侦测、属性读取、拖拽模式、用户名、像素级碰撞)
- [x] 变量监视器 (显示/隐藏监视器积木会动态创建或隐藏监视器)
- [x] 变量滑动条监视器（`mode: slider`、`sliderMin`/`sliderMax`、可拖动调整、离散/连续）
- [x] 运算符 (算术、比较、逻辑、字符串、随机)
- [x] 变量 (设置、增加、显示/隐藏)
- [x] 列表 (添加、删除、插入、替换、查询)
- [x] 变量模型按 ID 解析：角色局部变量/列表与全局同名时互不覆盖，写回 sb3 时仍保留原变量名
- [x] 往返解析恢复 `GLOBALS` / `GLOBAL_NAMES`：非舞台角色引用舞台全局列表时，`clear()`/`append()` 等仍写回列表积木，不会误降级成自制积木
- [x] 兼容 JSON 中的 `Infinity` / `-Infinity` / `NaN` 数值字面量（生成 `float('inf')` 等，不再触发 OverflowError）
- [x] 纯变量/列表计算循环不再逐帧让出，编译型大项目（如 LLVM→Scratch 推理程序）的初始化与计算速度显著提升
- [x] 超大列表初始值（≥256 项）改以 JSON 字符串写入并在导入时解析一次，十万级列表的大项目启动编译时间从数秒降到毫秒级
- [x] Files 文件扩展：打开本地文件（文本 / data URL）、把文本或 URL 下载到系统“下载”文件夹
- [x] Clipping & Blending 裁剪与颜色混合扩展：矩形裁剪框，以及默认/加法/减法/正片叠底/反色/遮罩/擦除等混合模式，角色与画笔均生效
- [x] Asset Manager 资源管理扩展：造型/声音的 URL 添加、删除、改名、排序与格式/dataURI/编号/资源 ID 查询
- [x] 通用 Python 转换支持递归/互递归（列表帧栈隔离参数与局部变量）、字符串下标/切片/重复、简单列表推导式、`zip` 遍历、`random.shuffle` 与重名变量隔离
- [x] 公平脚本调度：FIFO 执行权 + 轻量脚本线程，大量克隆同时运行时不会互相饿死
- [x] 广播 (发送、接收、等待)，写回 sb3 时使用标准 `[11, 名字, ID]` 输入顺序，往返后发送端与接收端消息名一致
- [x] 自制积木 (定义、调用、参数)
- [x] 克隆 (创建、删除)
- [x] 表达式嵌套 (运算符、函数调用)
- [x] TurboWarp warp 自制积木 / 自定义 reporter / `%s %n %b` 参数
- [x] TurboWarp 扩展积木与 `extensions` 列表往返
- [x] TurboWarp pen / runtimeoptions 扩展与高级选项
- [x] 舞台脚本、music 音乐扩展
- [x] 文字朗读 `text2speech` 扩展（pyttsx3 或 Windows SAPI）
- [x] TurboWarp `stretch` 角色拉伸扩展
- [x] TurboWarp `text` 艺术字（Animated Text）扩展
- [x] TurboWarp `skyhigh173JSON` JSON 扩展（对象/数组/路径/统计/列表读写）
- [x] TurboWarp `jeremygamerTweening` 补间扩展（全部缓动函数、变量/坐标/属性补间）
- [x] TurboWarp `lmsclonesplus` 克隆+ 扩展（带变量克隆、克隆帽子、克隆变量与属性读写、批量停止/删除）
- [x] TurboWarp `lmsLooksPlus` 外观+ 扩展（跨角色显示/图层/特效/造型属性/快照/SVG 内容）
- [x] TurboWarp `lmsMoreEvents` 更多事件扩展（forever/while/值变化/按键/每 N 帧/停止帽子、广播传数据）
- [x] TurboWarp `lmsTempVars2` / 旧版 `lmstempvars` 临时变量扩展（线程变量、运行时变量、批量删除）
- [x] TurboWarp `lmsListTools` 列表工具扩展（排序/反向/随机、拼接、查找、遍历循环、数组转换）
- [x] TurboWarp `localstorage` 本地存储扩展（命名空间、读写/删除键、键数量）
- [x] TurboWarp `clipboard` 剪贴板扩展（复制/读取、复制/粘贴帽子）
- [x] TurboWarp `MouseCursor` 光标扩展（系统光标、隐藏光标、用当前造型做光标）
- [x] TurboWarp `cubesterWindowControls` 窗口控制扩展（位置/大小/标题/全屏/屏幕信息）
- [x] 同一帽子事件的多个并列脚本（自动生成 `when_xxx_2` 等独立方法并全部注册）
- [x] “不刷新屏幕”自制积木：warp 期间暂停其他脚本，结束后统一绘制，不显示中间状态
- [x] SVG 渐变填充（linear/radial、多个 stop、stop-opacity）与透明度（`opacity`/`fill-opacity`/`stroke-opacity`/`rgba()`）
- [x] SVG 渲染改为单次标签扫描 + `<g>` 样式栈，元素较多时不再重复解析整段 XML
- [x] 渲染性能优化：造型变换缓存、按倍率复用 SVG、素材路径缓存、内嵌位图解码缓存、帧耗时自适应降低超采样倍率
- [x] 运行时扩展按 `runtime_code/extensions/` 子文件拆分，由 `config.json` 描述处理器/别名/依赖并按需拼装
- [x] 导出默认生成独立项目文件夹（`<项目名>/<项目名>.py` + `assets/`），同目录多个项目素材互不覆盖
- [x] 启动时按时间预算分帧预加载造型/背景，并显示加载进度条，避免大项目一次性加载卡死
- [x] MouseCursor 扩展只在舞台区域内生效，工具栏/黑边自动恢复系统箭头，绿旗与停止按钮始终可点击
- [x] 转换日志：阶段耗时、IR/语句/扩展摘要，异常定位到转换器源码行
- [x] SVG 按窗口倍率重新栅格化（窗口越大越清晰，最高 3 倍超采样）
- [x] 运行时扩展按需拼装：只写入项目实际使用的扩展及其依赖函数

## 限制

1. **视觉属性**: 支持颜色(HSV色相旋转)、亮度、透明度(GHOST)、鱼眼、旋涡、像素化、马赛克特效，变换公式与 scratch-render 一致；舞台自身的特效同样作用于背景。鱼眼/旋涡使用 numpy 做逐像素重采样（未安装 numpy 时这两项不生效），像素化/马赛克在无 numpy 时用 pygame 缩放/平铺近似。碰撞检测仍按未变形的造型计算
2. **音效**: 声音播放需要音频库支持；音高(PITCH)通过重采样真正改变音调（时长也随之变化，与 Scratch 的音高特效一致，速率公式 `2^(pitch/120)`），平移(PAN)应用到左右声道
3. **响度/用户名**: `响度` 需要额外安装 `sounddevice` 与 `numpy` 并授予麦克风权限，否则恒为 0；`用户名` 默认 `player`，可用环境变量 `SCRATCH_USERNAME` 覆盖
4. **文字朗读**: `text2speech` 扩展的“说[]”会朗读并等待结束；优先使用 `pyttsx3`（`pip install pyttsx3`），Windows 上没有时退回系统自带 SAPI。嗓音 alto/tenor/squeak/giant 映射到不同语速，语言通过系统嗓音匹配
5. **舞台属性**: 背景切换、背景编号/名称已支持；视频侦测等扩展未实现
6. **画笔**: 内置 `pen` 扩展支持落笔/抬笔/颜色/粗细/图章/清空；图章会先应用角色当前的颜色/亮度/透明度/形状特效再盖章；透明度不做混色合成。性能方面：画笔图层为空时跳过整层合成，同色线段复用颜色缓存，粗线段只补终点圆帽，完全透明的线段直接跳过
7. **角色拉伸/艺术字**: `stretch` 按角色自身坐标轴非等比缩放造型，旋转中心与舞台围栏一并考虑；`text` 艺术字用系统字体近似 Scratch 内置的 SVG 字体（Sans Serif / Serif / Handwriting / Marker / Curly / Pixel / Scratch），彩虹、缩放、抖动、打字动画按原扩展参数实现
8. **JSON 扩展**: `skyhigh173JSON` 的对象/数组语义按原扩展实现（数组下标 1 起、负数从末尾、路径中的数组下标同样按 1 起）；解析错误文本是 Python 的原文；`export all variables` 使用 Python 侧变量名（空格等会被替换为下划线）；列表菜单里的列表 ID 会在转换时解析成列表名
9. **补间/克隆+/外观+/更多事件/临时变量**: 五个扩展的积木、动态变量菜单与帽子事件已按原扩展复刻。补间在脚本线程中逐帧更新，turbo/warp 下也不会阻塞主循环；克隆+ 的克隆体变量在 `run()` 之前写入，避免克隆帽子读到旧值；更多事件的按键帽子按帧做上升沿检测（`shift`/`control` 兼容左右键）；临时变量按 Python 脚本线程隔离，绿旗和停止按钮会清空运行时变量。停止按钮已加入窗口顶部工具栏。`更多事件` 的“项目保存前/后”在生成的 pygame 程序里没有保存动作，因此不会触发；`外观+` 的 SVG 造型内容修改需要安装 `cairosvg` 才能立即改变画面，否则只保存文本供 `costumeContent` 读取
10. **变量模型**: 解析时按变量/列表 ID 判断归属；角色局部变量与全局变量同名时，局部变量会自动生成独立属性名（如 `local_score`），IR 与写回的 sb3 仍使用原始名字。扩展积木的变量菜单仍按变量名访问，同名遮蔽时优先访问局部变量
11. **调度性能**: 执行权锁改为 FIFO 公平锁，脚本线程启动不再等待线程就绪，避免大量克隆创建时卡住创建者；每个脚本每帧执行一次，变量/列表访问保持 Python 原生属性速度。数百个同时运行的脚本仍受 Python 线程调度限制，帧率会随活动脚本数上升而下降
12. **扩展**: 未注册的第三方扩展会保留调用但返回 0，不会中断脚本
13. **新扩展细节**: `localstorage` 数据存放在 `~/.scratch-converter/localstorage/<命名空间>.json`（默认命名空间为生成脚本名），写入使用临时文件加 `os.replace` 原子替换；“当本地存储变化”类跨窗口帽子未实现。`clipboard` 优先使用 `pygame.scrap`（需要 SDL），不可用时退回到内存字符串，只能在同一个程序内复制粘贴。`MouseCursor` 用当前造型生成的系统光标限制在 8–128 像素。`cubesterWindowControls` 依赖 `pygame.display.set_window_position`，在 headless 或部分平台上是空操作。`Files` 扩展用系统文件选择框读取本地文件，`download`/`download URL` 保存到系统“下载”文件夹（可用环境变量 `SCRATCH_DOWNLOAD_DIR` 覆盖）；无图形界面时选择文件返回空字符串
14. **裁剪与颜色混合**: 裁剪框与混合模式按角色的 `_clipbox`/`_blend_mode` 生效，克隆体继承、停止全部时重置；画笔线段与图章同样受裁剪/混合影响。加法/减法/正片叠底用 pygame 混合标志实现，`default behind`/反色/遮罩/擦除需要 numpy 做逐像素运算，未安装 numpy 时这些模式不产生效果。混合模式是逐角色绘制时合成，与原始扩展在 WebGL 帧缓冲上的结果在边缘抗锯齿上可能略有差异；舞台背景按不透明处理，`default behind` 在背景上不可见
15. **资源管理**: 造型/声音会下载到素材目录并按内容哈希命名；舞台造型变化会同步背景菜单。`add sprite from URL`、`open project from URL`、`load extension from URL` 与作品 JSON/导出需要完整 Scratch VM，在生成的 Python 程序中是空操作；角色的 `dataURI` 导出同样返回空字符串
16. **渲染倍率与扩展拼装**: 舞台内部按窗口大小以 0.25 步进在 1–3 倍之间超采样（`SCRATCH_RENDER_SCALE_MAX` 可提高到 4），并依据每帧耗时自适应降低；窗口中缩放稳定后才切换倍率，切换时保留画笔内容与按倍率缓存的造型。大体积（>512KB）的 SVG 通常是包裹内嵌 PNG 的截图，固定最多按 2 倍栅格化以控制内存与切换开销；PNG/JPG 造型仍按原始像素绘制。启动预加载按约 12ms/帧分批进行并显示进度条，单个超大 SVG 仍可能占用较长时间。SVG 的渐变填充支持 linear/radial 与多 stop（含 stop 透明度），描边渐变按平均色近似；透明度按元素/组叠加近似。生成脚本只拼装项目实际使用的扩展（含依赖函数），未注册扩展仍返回 0。扩展源码位于 `runtime_code/extensions/`，新增内置扩展时添加子文件并在 `config.json` 登记处理器、别名与依赖即可，无需修改 `ext_assembly.py`

## 运行转换后的脚本

生成的 Python 文件自带一个 pygame 版 Scratch 3.0 运行时：

```bash
pip install pygame
python converter.py scratch2py 项目.sb3 项目.py
python 项目.py
```

### 模块化输出（`--split`）

大项目生成的单文件可能上万行。加 `--split` 后会在输出目录生成：

- `项目.py`：入口（解析命令行参数、实例化角色、启动运行时）
- `项目_runtime.py`：辅助函数、扩展处理器、pygame 运行时与角色基类
- `项目_sprite_01_角色名.py` …：每个角色一个模块

运行时模块包含 `GLOBALS` / `MONITORS` / 背景等常量，文件名按项目名区分，同一目录下多个项目不会互相覆盖；直接 `python 项目.py` 即可运行。

通用 Python 模式：

```bash
python converter.py py2scratch 脚本.py 项目.sb3 --mode general
```

> `example/` 只是本地示例目录，已在 `.gitignore` 中忽略，仓库不包含其中的 sb3/py 文件。

- 程序会打开舞台窗口，绿旗脚本在后台线程中逐帧执行。
- 启动时窗口自动最大化，舞台按宽高比缩放到窗口的最大可用区域，多余部分补黑边，类似 Scratch 舞台放大到最大时的行为；最大化后仍可自由拉伸窗口，舞台会实时重新适配。鼠标坐标始终换算回舞台逻辑坐标，点击/拖动不受缩放影响。使用 `--windowed` 可以普通窗口尺寸启动。
- 鼠标 `x 坐标` / `y 坐标` 超出舞台时返回边界值（默认 ±240 / ±180），与 Scratch 一致。
- 角色默认不能离开舞台：按造型旋转/缩放后的包围盒约束，造型比舞台还大时居中；对应 TurboWarp 的 Fencing 选项，可用 `--no-fencing` 或 Runtime Options 里的 `fencing: false` 关闭。
- 脚本采用 Scratch 式协作调度：同一时刻只有一个脚本在执行，遇到让帧/等待才切换，避免数据驱动的列表被并发读改写破坏。
- 勾选“不刷新屏幕”的自制积木会以 warp 方式运行：期间其他脚本暂停、画面不重绘，积木结束后一次性呈现最终状态；warp 超过 `--warp-timer`（默认 0.5 秒）会临时让出一帧。
- 窗口放大时舞台会按新的倍率重新栅格化（默认最多 3 倍超采样，可用 `SCRATCH_RENDER_SCALE_MAX` 调整；大体积内嵌位图 SVG 最多 2 倍），并根据每帧实际耗时自动降低倍率；SVG 造型不会随窗口拉伸而发糊。启动时会先显示资源加载进度条，按约 12ms/帧的预算分批缓存图片。
- 如果输入是 `.sb3`，转换器会把造型/声音资源直接导出到 `.py` 所在目录，脚本运行时从同目录加载；同时兼容旧的 `assets/` 子目录。
- 窗口模式可直接游玩：顶部工具栏有绿旗按钮（与 Scratch 一致，不占用舞台区域），舞台背景默认白色；按 `F1` 可显示运行时调试面板（版本、帧号、询问状态、鼠标/按键事件）；`ESC` 退出，可拖动开启了拖动模式的角色，`询问并等待` 会在舞台底部弹出输入框；支持中文输入法，按回车（含小键盘）或点击右侧“确认”按钮提交；点击输入框本身不会提交，多个脚本同时询问时按顺序排队。
- SVG 造型由内置渲染器光栅化（支持 text、内嵌 base64 位图、linear/radial 渐变、rect/circle/ellipse/line/polygon/polyline/path）；支持 `opacity`、`fill-opacity`、`stroke-opacity`、`stop-opacity`、`rgba()` 与 `transparent`，半透明形状按画布正确混色；`<g>` 的样式与变换通过一次扫描继承，内嵌位图的 base64 数据会先被遮罩再解析，避免反复扫描大数据。文字最后绘制，不会被背景形状遮挡。默认使用内置渲染器；需要 cairosvg 的高保真度时可设置环境变量 `SCRATCH_SVG_CAIROSVG=1`（首次导入可能较慢）。
- 支持 `当计时器 > 值` / `当响度 > 值` 帽子事件：条件由假变真时触发一次脚本，持续为真不会重复触发，重置计时器后可再次触发。响度需要可选依赖 `pip install sounddevice numpy` 并授予麦克风权限，未安装时恒为 0。
- `用户名` 默认返回 `player`（与离线播放器一致），可用环境变量 `SCRATCH_USERNAME=tom` 覆盖。
- 声音的 `音高` 特效会真正改变音调：按 `2^(pitch/120)` 重采样，音高升高时播放变快变短，与 Scratch 行为一致；同一段声音的常用音高会缓存，避免每帧重复重采样。
- `text2speech` 扩展的“说[]”会朗读并等待：安装 `pip install pyttsx3` 后使用本地语音引擎，Windows 上没有 pyttsx3 时自动退回系统 SAPI；`设置嗓音`（alto/tenor/squeak/giant）映射为不同语速，`设置语言` 会尝试匹配对应系统嗓音。
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
| `--frames N` | 运行 N 帧后退出（无头模式下会额外让出 1ms/帧给脚本线程；需要精确按时长结束请用 `--seconds`） |
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

支持读取：`framerate/fps`、`fencing`、`miscLimits`、`interpolation`、`turbo`、`hqPen/hq`、`compiler`、`cloneLimit/maxClones`（0 或 Infinity 表示无限）、`warpTimer`、`stageWidth/stageHeight`、`width/height`（只给宽度时高度保持默认 360）。

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
| `stretch` 角色拉伸 | 设置/增加 x、y 拉伸百分比，读取 x/y 拉伸值；渲染时按角色自身坐标轴非等比缩放，克隆体继承 |
| `text` 艺术字 | 显示/清除文字、字体、颜色、宽度与对齐、描边、追加行；打字/彩虹/缩放/抖动动画与时长、打字延迟；`is animating`、`displayed text`、`text [attribute]` 等读取积木 |
| `skyhigh173JSON` JSON 扩展 | 校验/格式化/合并/翻转/比较 JSON；按路径读写；对象与数组的增删改查；`sort`、`filter`、`flat`、`concat`、统计（min/max/sum/avg/median/mode/variance）；`get list as array` / `set list to` 读写 Scratch 列表 |
| `jeremygamerTweening` 补间 | linear/sine/quad/cubic/quart/quint/expo/circ/back/elastic/bounce 缓动，in/out/in out 方向；变量、x/y、方向、大小补间与 `tween value` 计算积木 |
| `lmsclonesplus` 克隆+ | 创建带变量值的克隆、按变量值查找/修改/删除克隆、克隆存在性与数量、克隆/本体属性读取、停止指定克隆或本体的脚本 |
| `lmsLooksPlus` 外观+ | 跨角色显示/隐藏/可见性、图层编号与设置、特效值读取、造型数量/宽高/格式/旋转中心、舞台快照、SVG 内容读取/替换/恢复与颜色替换 |
| `lmsMoreEvents` 更多事件 | when stop clicked / forever / when condition becomes / while condition is / when value changed / every N frames / key hit & released / while key pressed 帽子；广播到指定角色、广播携带数据、received data |
| `lmsTempVars2` / `lmstempvars` 临时变量 | 线程变量与运行时变量的设置/增加/读取/存在性/列表/删除；`for [var] in [n]` 循环；绿旗与停止时清空运行时变量 |
| `lmsListTools` 列表工具 | 删除/全量替换/随机/排序/反向、拼接、查找下标与出现次数、判空、判断顺序、列表互拷/合并、遍历项值与项号循环、数组转换 |
| `localstorage` 本地存储 | 按命名空间读写/删除键、清空、键数量；数据写入用户目录下的 JSON 文件，跨脚本运行保留 |
| `clipboard` 剪贴板 | 写入/读取文本；`当按下 Ctrl+C` / `当按下 Ctrl+V` 帽子事件 |
| `MouseCursor` 光标 | 系统光标类型、隐藏/显示、用当前造型生成自定义光标 |
| `cubesterWindowControls` 窗口控制 | 设置/增加窗口位置与大小、标题、全屏切换、屏幕尺寸与坐标、关闭窗口 |

TurboWarp 高级选项既可以通过生成脚本的命令行参数设置（见上表），也可以在项目里直接用 Runtime Options 扩展积木设置。

扩展入口：

```python
ScratchRuntime.register_extension("myext", handler)
# handler(runtime, sprite, opcode, inputs, fields)
# 精灵内调用: self.extension("myext", "opcode", {inputs}, {fields})
```

## 依赖

- Python 3.8+（兼容 3.12+；`python_parser.py` 不再依赖已移除的 `ast.Num`/`ast.Str`/`ast.NameConstant`）
- 转换本身只使用标准库
- 运行生成的脚本需要 `pygame`（`pip install pygame`）
- 可选：`numpy`（鱼眼/旋涡特效与更快的音高重采样）、`sounddevice`（麦克风响度）、`pyttsx3`（文字朗读）、`cairosvg`（设置 `SCRATCH_SVG_CAIROSVG=1` 后用于更高保真的 SVG 渲染）

## 许可

MIT License
