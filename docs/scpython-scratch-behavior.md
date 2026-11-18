# ScPython 与 Scratch 行为参考

本文说明 ScPython 代码在 Scratch 中实际如何运行。写 `.scpy` 或生成 `.scpy`
之前，应先理解这些行为。

配套文档：

- [ScPython 语言指南](scpython.md)
- [Scratch VM 执行语义](scratch-vm-execution.md)
- [Scratch 输入与参数语义](scratch-semantics.md)

---

## 1. 执行模型

Scratch 是 **单线程协作式调度**：

- 点击绿旗后，所有 `when green_flag` 脚本进入调度队列；
- 每个脚本是一个线程，任意时刻只有一个脚本在运行；
- 脚本在循环、等待、滑行等位置主动让出执行权（yield）；
- 默认 30 帧/秒；TurboWarp 可提高帧率或开启 turbo。

对 ScPython 的影响：

| 写法 | 运行行为 |
|------|----------|
| `forever` 循环（`while True` 无 break） | 每轮结束让出一帧 |
| `while 条件` / `for range(...)` | 每轮结束让出一帧 |
| `wait(秒)` | 阻塞指定秒数，期间其他脚本可运行 |
| `glide(秒, x, y)` | 逐帧移动，阻塞到结束 |
| `say_for(文本, 秒)` | 阻塞指定秒数 |
| `broadcast_and_wait` | 等待所有接收脚本结束 |
| `ask_and_wait` | 阻塞到玩家提交答案 |
| `warp=True` 的自制积木 | 循环内不让帧，直到返回或超过 warp 时间上限 |

脚本执行顺序按角色添加顺序与脚本创建顺序，公平锁保证没有脚本会永久饿死。

---

## 2. 事件头

| ScPython | Scratch | 触发 |
|----------|---------|------|
| `when green_flag:` | 当绿旗被点击 | 每次点绿旗 |
| `when clicked:` | 当角色被点击 | 鼠标点击角色 |
| `when clone_start:` | 当作为克隆体启动时 | 每个克隆体启动一次 |
| `when key_pressed("space"):` | 当按下空格键 | 按键按下 |
| `when broadcast("go"):` | 当接收到广播 | 每次收到广播启动一个新线程 |
| `when backdrop_switches_to("bg"):` | 当背景换成 | 背景切换时 |
| `when timer > 10:` | 当计时器 > | 条件由假变真时触发一次 |
| `when loudness > 20:` | 当响度 > | 同上 |

要点：

- 同一顶帽子可以写多个脚本，互不影响；
- 广播可以同时启动多个同名处理脚本；
- 绿旗会删除所有克隆体、停止旧脚本、重置计时器；
- 计时器/响度帽子是 **边沿触发**，持续为真不会重复启动。

---

## 3. 比较与类型转换

ScPython 的 `==` 和 `!=` 直接使用 Scratch 比较规则：

1. 两侧先尝试转数字；
2. 数字优先比较；
3. 任一侧无法转数字时，转成字符串并 **忽略大小写** 比较；
4. 空字符串、`"0"`、`"false"` 在布尔上下文为假。

示例：

| 表达式 | 结果 |
|--------|------|
| `"ABC" == "abc"` | 真 |
| `"123" == 123` | 真 |
| `"1.0" == 1` | 真 |
| `"" == 0` | 假 |
| `"1.0" != 1` | 假 |
| `"36" < "100"` | 真（按数字） |
| `"abc" < "abd"` | 真（按字符串） |

`+=`、`-`、`*`、`/`、`%` 都是 Scratch 数字运算：先 `toNumber`，
空字符串/非数字按 0 处理。

完整的边界值见 [scratch-semantics.md](scratch-semantics.md)。

---

## 4. 字符串

ScPython 只暴露 Scratch 的字符串能力：

| 操作 | ScPython |
|------|----------|
| 连接 | `join(a, b)` |
| 第 i 个字符 | `letter_of(i, s)`（1 起始） |
| 长度 | `length(s)` |
| 包含 | `contains(s, part)`（忽略大小写） |

没有字符串下标、切片、方法、f-string、格式化。

Scratch 的字符串长度按 UTF-16 码元计算，Python 按码点计算；
emoji 等字符在 ScPython 中进入 Scratch 后长度可能不同。

---

## 5. 数字

- Scratch 使用 IEEE 双精度；
- `1 / 0` → `Infinity`，`0 / 0` → `NaN`；
- `mod` 使用向下取整余数，结果与除数同号；
- `round` 使用 `floor(x + 0.5)`；
- `sin/cos/tan` 使用角度制。

ScPython 生成的是 Scratch `operator_*` 积木，因此这些行为由 Scratch 决定，
而不是 Python 的 `float` / `int` 行为。

---

## 6. 列表

列表是 Scratch 列表，不是 Python 列表：

- 索引从 **1** 开始；
- 越界读取返回 `""`，越界写入/删除忽略；
- `item_of(list, "last")` 支持 `last` / `random` / `any`；
- 删除/替换的索引也支持 `last` / `random` / `any`；
- 列表项可以是数字或字符串；
- 列表内容拼接：全部是单字符时直接相连，否则用空格连接。

ScPython 限制：

| 允许 | 不允许 |
|------|--------|
| `items[i]`、`items[i] = v`、`del items[i]` | 切片、负下标 |
| `item_of`、`item_number_of`、`length_of` | `sort/reverse/pop/remove/count/extend/copy` |
| `contains_item`、`list_contents` | 列表推导式 |
| `append/insert/clear` | 把列表当参数传递 |

下标不是整数时，Scratch 会取整（floor）；ScPython 直接生成对应积木。

---

## 7. 变量作用域

| 位置 | 作用域 |
|------|--------|
| 舞台 `init` 的 `var/list` | 全局，所有角色共享 |
| 角色 `init` 的 `var/list` | 该角色及其克隆体 |
| 脚本中未声明赋值 | 有同名全局则改全局，否则建局部 |
| 克隆体 | 复制局部变量当前值；全局共享 |

同名冲突：

- 角色显式声明同名变量时，局部优先；
- 导出的 Scratch 使用不同的变量 ID 区分全局/局部，
  不会因为名字相同而错误合并。

---

## 8. 广播

```python
broadcast("go")
broadcast_and_wait("go")
```

- `broadcast` 立即返回；每个接收脚本启动一个新线程；
- `broadcast_and_wait` 等待本次启动的所有接收线程结束；
- 没有接收者时直接返回；
- 广播名必须是字符串常量（导出时需要生成 Scratch 广播 ID）。

---

## 9. 克隆

```python
create_clone("_myself_")   # 或 "Cat"
delete_this_clone()
```

- 克隆体复制：位置、方向、大小、造型、图形特效、局部变量/列表当前值；
- 全局变量/列表共享；
- 克隆体会注册 `when clone_start` 脚本；
- `delete_this_clone` 删除自身并停止其所有脚本；本体调用无效；
- 默认最多 300 个克隆体；
- 绿旗会删除所有克隆体。

---

## 10. 自制积木与递归

```python
def fact(n, *, types="n", warp=True):
    if n <= 1:
        return 1
    return n * fact(n - 1)
```

- 参数按位置传递；调用时缺少的参数取定义里的默认值；
- 没有默认值：字符串参数 `""`，布尔参数 `false`；
- `return 值` 生成 TurboWarp 的 `procedures_return`；
- 递归/互递归由 Scratch 线程栈执行，深度过大可能受浏览器/运行时限制；
- `warp=True` 时整个调用期间不刷新屏幕，嵌套 warp 会累加；
- 在自制积木内执行 `stop_this_script()` 只返回上一层调用；
- 普通 `stop_all()` 停止所有脚本。

Scratch 原生不支持「返回值」的自制积木；ScPython 使用 TurboWarp 的
`procedures_return` 扩展块。若目标不是 TurboWarp，需要把结果写入变量再读取。

---

## 11. 循环

### 11.1 `for i in range(...)`

生成结构（简化）：

```text
set counter = start
set limit = stop
repeat until counter >= limit:
    set i = counter
    body
    change counter by step
```

行为：

- `stop` 只求值一次；
- `step` 必须是常量，支持负数；
- 循环变量 `i` 是普通 Scratch 变量，循环结束后保留最后一个值；
- 循环体每轮让出一帧。

### 11.2 `for item in items`

```text
set index = 1
repeat until index > length_of(items):
    set item = item_of(items, index)
    body
    change index by 1
```

列表在循环中被修改时，长度每轮重新读取；不要在遍历时依赖 Python 的
“按原长度遍历”行为。

### 11.3 `while`

```python
while score < 10:
    score += 1
```

生成 `repeat until not (score < 10)`。`while True` 生成 `forever`。

### 11.4 `break` / `continue`

ScPython 使用隐藏变量实现：

- `break`：设置 `__scpy_break_N = 1`，循环条件检查后退出；
- `continue`：设置 `__scpy_continue_N = 1`，跳过本轮剩余语句，
  循环变量仍会正常递增；
- 每轮开始会重置 `continue` 标志；
- 这些隐藏变量会出现在 Scratch 变量列表中（名字以 `__scpy_` 开头）。

---

## 12. 计时器、鼠标与询问

| ScPython | Scratch |
|----------|---------|
| `timer()` | 计时器（绿旗重置，可 `reset_timer()`） |
| `mouse_x()` / `mouse_y()` | 鼠标坐标 |
| `mouse_down()` | 鼠标按下 |
| `key_pressed("space")` | 按键是否按下 |
| `answer()` | 最近一次询问答案 |
| `ask_and_wait("问题")` | 显示输入框并阻塞 |
| `current("YEAR")` | 当前年/月/日/星期/时/分/秒 |
| `days_since_2000()` | 2000-01-01 起的天数（本地时区） |
| `loudness()` | 麦克风响度；无麦克风为 0 |
| `username()` | 默认 `player` |

询问框同一时刻只处理一个询问，多个脚本同时询问会排队。

---

## 13. 造型、声音与渲染

- `costumes` 按声明顺序写入，索引 0 为第一个；
- 造型名默认是文件名；同名自动加 `_2`；
- 旋转中心默认图片中心；SVG 读取 `width/height` 或 `viewBox`；
- `switch_costume(name)` 支持名字或编号；
- 背景是舞台的造型；
- 角色层级按角色添加顺序，`go_to_front` / `go_to_back` 调整；
- 图形特效范围与 Scratch 一致：颜色 0–200、透明度 0–100、亮度 -100–100。

资源缺失会在编译期报错。SVG 使用运行时的简化渲染器，复杂 SVG 可能失真。

---

## 14. 扩展

- `pen`、`music` 有内置函数封装；
- 自定义扩展通过 `extensions.json` 或 `ext(ns, opcode, ...)`；
- 扩展字段（下拉菜单）只能通过 `extensions.json` 的 `fields` 设置；
- 未知扩展在运行时返回 0（不会崩溃）。

---

## 15. 与原生 Scratch 的差异

| 项 | ScPython/本运行时 | 原生 Scratch |
|----|------------------|--------------|
| 自制积木返回值 | TurboWarp `procedures_return` | 原生不支持 |
| `for` 循环 | 计数/索引循环 | 原生没有 for |
| `break/continue` | 隐藏标志变量 | 原生没有 |
| 字符串长度 | 受 UTF-16/码点差异影响 | UTF-16 |
| `stage_clicked` | 目前等同 `clicked` | 独立的舞台点击帽 |
| 超长整数 | 运行时按双精度处理 | 双精度 |
| 自定义扩展 | 需要清单或已知 opcode | 扩展加载器 |

---

## 16. 参考

- [Scratch VM 执行语义](scratch-vm-execution.md)
- [SB3 文件结构](sb3-format.md)
- [Scratch 输入与参数语义](scratch-semantics.md)
- [Scratch Wiki: Blocks](https://en.scratch-wiki.info/wiki/Blocks)
- [TurboWarp Docs](https://docs.turbowarp.org/)
