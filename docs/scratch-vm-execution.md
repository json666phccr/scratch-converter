# Scratch VM 执行语义

本文描述 Scratch 3.0 虚拟机“拿到 SB3 之后如何跑起来”，以及本项目现有 pygame 运行时
（`src/runtime_code/`）对它的映射。实现 `scratch_vm/interpreter.py` 时以本文为准。

配套文档：

- [sb3-format.md](sb3-format.md)：SB3 数据结构
- [scratch-vm-design.md](scratch-vm-design.md)：本项目虚拟机的实现设计
- [scratch-semantics.md](scratch-semantics.md)：类型转换、比较、列表边界等细节

---

## 1. 核心概念

| 概念 | 说明 |
|------|------|
| target | 舞台或一个角色（含克隆体），拥有自己的变量、造型、脚本 |
| block | 一块积木，对应 `blocks` 字典中的一个节点 |
| stack | 由 `next` 串联起来的一串积木 |
| hat | 帽子积木，脚本入口；只有帽子块能注册为可触发脚本 |
| thread | 一次脚本执行实例；同一顶帽子可以被多次触发（每个克隆体也各有线程） |
| frame / tick | VM 的一次主循环迭代，默认 30 FPS |
| yield | 线程主动让出执行权，等待下一帧或下一个条件 |
| warp | 「运行时不刷新屏幕」模式：连续执行直到结束或超过时间上限 |
| clone | 角色的运行时副本，拥有独立局部变量，但共享全局变量 |

关键结论：**Scratch 是单线程协作式调度**。任意时刻只有一个脚本在跑，
脚本在阻塞积木处主动让出（yield），VM 再按顺序唤醒其他脚本。

---

## 2. VM 生命周期

```text
loadProject(json)
  ├─ 创建 targets（舞台 + 角色）
  ├─ 解析 blocks，注册 hats：hat → [thread factory]
  ├─ 创建变量/列表、加载造型/声音
  └─ 不执行任何脚本

greenFlag()
  ├─ 删除所有克隆体
  ├─ 停止所有线程
  ├─ 重置计时器、清空临时变量
  ├─ 按 target 顺序启动所有 whengreenflag 脚本
  └─ 触发 whenbackdropswitchesto? （不触发，背景切换只在变化时触发）

loop:
  step()
    ├─ 处理输入事件（键盘/鼠标/点击）
    ├─ 更新传感器状态（timer / mouse / loudness / days since 2000）
    ├─ 评估帧帽子（when greater than、扩展帽子）
    ├─ 调度所有 runnable 线程，执行到各自 yield
    ├─ 执行待处理广播、克隆创建/删除
    └─ 渲染一帧

stopAll()
  ├─ 所有线程标记为停止
  ├─ 停止声音
  └─ 保留舞台状态（变量不清空）
```

对应现有运行时：

- `ScratchRuntime.start()`：`sprite.run()` 注册帽子 → `green_flag()` → 循环 `step()`
- `ScratchRuntime.green_flag()`：清克隆、停脚本、重置计时器、启动绿旗脚本
- `ScratchRuntime.step()`：事件 → `_update_state()` → 绘制 → 帧号 +1
- `ScratchSprite._register(event, func)`：帽子注册表
- `ScratchRuntime.start_script(func)`：**每个线程一个 Python 线程**

---

## 3. 线程与调度

### 3.1 官方 VM 的线程模型

- `Sequencer` 维护线程列表；每个线程保存当前 block、调用栈、warp 计数。
- 线程执行 `stepThread()`：从当前 block 开始，连续执行，直到：
  - 遇到阻塞积木（`wait`、`wait until`、`glide`、`say for secs`、`play sound until done`、
    `broadcast and wait`、`ask and wait`）→ 线程挂起；
  - 循环体执行完一轮 → `yield`（等待下一帧）；
  - 脚本结束 → 线程销毁。
- 同一帧内线程按创建顺序轮流执行；一个线程一旦 yield 就排到队尾。

### 3.2 本项目运行时

`start_script()` 为每个脚本创建 `_ScriptThread`（基于 `_thread`），并配一把
`_FairLock`：

```text
thread.run:
    _turn_acquire()          # 抢执行权，FIFO
    func()                   # 执行脚本
    _turn_release()
```

- `_yield_frame()`：释放执行权 → `wait_frame()` 等到下一帧 → 重新抢锁；
- `_sleep(seconds)`：释放执行权 → `time.sleep` → 重新抢锁；
- warp 模式下 `_yield_frame()` 不等待，只检查 `warp_timer` 上限（默认 0.5 秒）。

**结论**：解释器只要使用 `sprite._yield_frame()` / `sprite.wait()` /
`sprite._sleep()`，就自动获得与现有生成代码一致的调度行为，不需要自己写调度器。

### 3.3 解释器的 yield 规则

| 积木 | yield 行为 |
|------|-----------|
| `control_repeat` | 每轮结束后 `_yield_frame()`；若次数小且循环体是纯计算，可跳过（性能优化） |
| `control_forever` | 每轮结束后 `_yield_frame()` |
| `control_repeat_until` | 每轮结束后 `_yield_frame()` |
| `control_wait` | `sprite.wait(secs)`，内部 `_sleep` |
| `control_wait_until` | 条件为假时 `_yield_frame()` 轮询 |
| `control_all_at_once` | 不额外 yield，顺序执行子栈 |
| `control_stop` | 立即抛异常结束当前脚本/所有脚本 |
| `control_create_clone_of` | 立即返回；克隆体在下一帧启动 `when I start as a clone` |
| `event_broadcast` | 立即返回；接收脚本进入调度队列 |
| `event_broadcastandwait` | 等待所有接收线程结束，期间 `_yield_frame()` |
| `motion_glide_to` | 内部按帧插值，逐帧 yield |
| `looks_say_for_secs` | `_sleep` 指定秒数 |
| `sound_playuntildone` | 等待声音播放结束 |
| `sensing_askandwait` | 等待玩家提交答案 |

---

## 4. 帽子事件

### 4.1 标准帽子

| 帽子 opcode | 触发时机 | 现有运行时事件 key |
|-------------|----------|--------------------|
| `event_whenflagclicked` | 点击绿旗 / `greenFlag()` | `green_flag` |
| `event_whenkeypressed` | 按下指定键 | `key:<key>` |
| `event_whenthisspriteclicked` | 点击角色 | `clicked` |
| `event_whenstageclicked` | 点击舞台空白 | `clicked`（舞台） |
| `event_whenbackdropswitchesto` | 背景切换到指定名称 | `backdrop:<name>` |
| `event_whenbroadcastreceived` | 收到指定广播 | `broadcast:<name>` |
| `event_whengreaterthan` | 计时器/响度 > 阈值（**边沿触发**） | `_conditions` 列表 |
| `control_start_as_clone` | 克隆体启动 | `clone_start` |

边沿触发：`when timer > 10` 只在条件由假变真时启动一次，持续为真不会重复启动。
`whengreaterthan` 的菜单是 `TIMER` 或 `LOUDNESS`。

### 4.2 扩展帽子

TurboWarp 扩展帽子（opcode 带扩展命名空间）由 `_register_extension_hat` 处理：

```python
sprite._register_extension_hat(namespace, opcode, inputs, func)
```

- `inputs` 的值是**无参函数**，每帧重新求值；
- More Events 的 `whentruefalse` / `whiletruefalse` / `whenvaluechanged` /
  `everyduration` / `whenkeyaction` / `whilekeypressed` 由
  `_ext_frame_hat_action(runtime, sprite, entry)` 逐帧判断；
- `when stop clicked` / `when copied` / `when pasted` 走普通事件表。

### 4.3 多脚本与重复帽子

同一个角色可以有多个 `when green flag clicked` 脚本，必须**各自注册、各自启动**。
现有生成器用 `_2`、`_3` 后缀区分方法名；VM 用脚本索引区分。

---

## 5. 广播

```text
broadcast("消息")
  → 遍历所有 target（含克隆体）
  → 找到 broadcast:<消息> 的所有处理函数
  → 每个处理函数创建一个新线程
  → 立即返回
```

规则：

| 情况 | 行为 |
|------|------|
| 没有接收者 | 直接返回 |
| 同一脚本已在线程中运行 | **再启动一个新线程**（Scratch 允许同一帽子并发运行） |
| `broadcast and wait` | 等待本次启动的所有线程结束；期间当前线程 yield |
| 广播消息为空 | 忽略 |
| 广播带数据（Clones+） | 通过 `received_data` 传给 `_register` 的回调 |
| 绿旗 | 停止所有旧线程，再启动绿旗线程 |

现有运行时：`ScratchRuntime.broadcast()` / `broadcast_to()` / `broadcast_and_wait()`，
角色侧 `ScratchSprite.broadcast()` / `broadcast_and_wait()`。

---

## 6. 克隆

### 6.1 创建

```text
create clone of [myself / Sprite2]
  → 找到源角色（myself = 当前角色，名字 = runtime.find_sprite(name)）
  → source._make_clone()
     ├─ 复制实例属性（跳过 `_` 开头内部属性和全局变量）
     ├─ 列表/字典做浅拷贝
     ├─ 重置 _handlers / _conditions / _frame_hats
     ├─ 应用 initial_vars（Clones+）
     ├─ clone.run()  → 注册帽子
     ├─ runtime.sprites.append(clone)
     └─ 启动 clone_start 线程
```

### 6.2 语义

| 项 | 规则 |
|----|------|
| 局部变量 | 复制当前值 |
| 全局变量 | 共享（舞台 `GLOBALS`） |
| 造型/大小/方向/特效 | 复制当前状态 |
| 脚本 | 复制帽子注册，重新注册 |
| 克隆体点击 | 可以触发 `when this sprite clicked` |
| `delete this clone` | 停止该克隆体所有脚本并从 targets 移除；本体执行无效 |
| 克隆上限 | 默认 300；`--infinite-clones` 解除 |
| 克隆体不保存 | 停止/绿旗时全部删除 |

### 6.3 克隆与解释器

- 克隆体 `__class__` 与本体相同，因此解释器注册的 `run()` 方法会再次执行；
- `run()` 必须幂等、可重复调用（每次清空旧注册）；
- 解释器的脚本索引、过程表按**类**共享，不需要为克隆体单独构建；
- 调试器应能区分本体与克隆体（`sprite._is_clone`），显示名字时可加 `#clone`。

---

## 7. 自制积木

### 7.1 定义

```json
"proccode": "move %s steps and say %s",
"argumentids": ["id1", "id2"],
"argumentnames": ["steps", "message"],
"argumentdefaults": ["", ""],
"warp": "false"
```

执行定义块本身 = **什么都不做**，只把过程注册到角色。

### 7.2 调用

```text
procedures_call
  → 对每个 argumentid：
      调用块有该输入 → 求值输入
      没有           → 使用 definition 的 argumentdefaults
  → 进入新调用帧（参数名 → 值）
  → 执行过程体
  → 遇到 return / 过程体结束 → 返回调用处
```

规则：

| 项 | 说明 |
|----|------|
| 参数传递 | 按 `argumentids` 顺序，位置对应 |
| 参数默认值 | 缺失输入取 `argumentdefaults`，字符串参数默认 `""` |
| warp | 定义块 `warp=true` 时，整个调用期间不刷新屏幕（嵌套累加） |
| 递归 | 允许；每层一个 Python 调用帧，深递归受 Python 栈限制 |
| `stop this script` 在过程内 | 只返回上一层调用，不终止整个线程 |
| `procedures_return` | TurboWarp 扩展，立即返回并携带值 |
| 过程名解析 | `Expr.to_python_source()` 通过 `set_procedure_name_resolver` 把 proccode 映射到唯一方法名 |

### 7.3 过程与调试器

解释器必须维护**显式调用栈**，每帧包含：

```text
sprite, script_name, proccode, block_id, locals(arg_*), warp_depth
```

这样调试器才能打印调用栈、查看每层参数、在过程内设断点。

---

## 8. 语句执行细节

### 8.1 控制流

| 积木 | 语义 |
|------|------|
| `control_repeat` | `n = round(toNumber(VALUE))`，`n<=0` 跳过；每轮执行子栈 |
| `control_forever` | 无限循环，直到脚本被停止；每轮 yield |
| `control_if` | 条件 `toBoolean` 为真执行子栈 |
| `control_if_else` | 二选一 |
| `control_wait_until` | 条件为假时逐帧轮询 |
| `control_repeat_until` | 条件为真时结束；至少检查一次 |
| `control_for_each` | TurboWarp：遍历列表，把当前项写入变量，每轮 yield |
| `control_all_at_once` | 顺序执行子栈，不额外 yield（用于「运行不刷新」的近似） |
| `control_stop` | `all` = 停止全部脚本并抛 `StopIteration`；`this script` = 停止当前线程；`other scripts in sprite` = 停止同角色其他线程 |
| `control_create_clone_of` | 创建克隆体 |
| `control_delete_this_clone` | 删除自身（克隆体） |

`stop all` 的实现细节：现有运行时 `sprite.stop('all')` 先调用
`runtime.stop_all_scripts()`，再抛 `StopIteration`。`stop other scripts in sprite`
停止同角色其他线程后**正常返回**。`stop this script` 在过程内抛
`_ProcedureReturn`（被 `_as_procedure` 捕获），在顶层抛 `StopIteration`。

### 8.2 外观 / 运动 / 声音

这些积木大多是一条语句调用 `ScratchSprite` 的方法，可以直接执行生成器
`_generate_statement` 产生的代码（见设计文档的“叶子语句编译”）。

阻塞型：

| 积木 | 阻塞方式 |
|------|----------|
| `motion_glide_to` / `glidesecstoxy` | 逐帧插值，内部 yield |
| `looks_say_for_secs` / `thinkforsecs` | `_sleep` |
| `sound_playuntildone` | 等待 channel 结束 |
| `looks_switchbackdroptoandwait` | 等待所有角色切换完成 |

### 8.3 侦测与询问

| 积木 | 说明 |
|------|------|
| `sensing_askandwait` | 显示输入框，阻塞到玩家提交；答案写入 `answer` |
| `sensing_keypressed` | 查询当前按键集合 |
| `sensing_mousedown` | 鼠标左键状态 |
| `sensing_touchingobject` | 精灵/鼠标/边缘 |
| `sensing_touchingcolor` / `coloristouchingcolor` | 基于造型像素掩码 |
| `sensing_distanceto` | 到角色/鼠标的距离 |
| `sensing_of` | 读取其他角色的属性/变量 |
| `sensing_current` | 年/月/日/星期/小时/分钟/秒 |
| `sensing_dayssince2000` | 本地时区，2000-01-01 起的天数 |
| `sensing_timer` | 运行时计时器（可重置） |
| `sensing_loudness` | 麦克风响度，无麦克风时为 0 |
| `sensing_username` | 默认 `player`，可用 `SCRATCH_USERNAME` 覆盖 |

---

## 9. 表达式语义

表达式在 IR 中由 `Expr` 表示，现有生成器把它编译成 Python 表达式。
VM 采用「**编译一次 + 每次求值**」的策略：

```python
code = compile(expr.to_python_source(), '<expr>', 'eval')
value = eval(code, runtime_globals, {'self': sprite, **frame_locals})
```

规则：

1. 表达式源码中的 `self` 指向当前角色；
2. 自制积木参数编译为 `arg_<sanitize_name(name)>`，求值时注入 `frame_locals`；
3. 扩展调用编译为 `self.extension(namespace, opcode, inputs, fields)`；
4. 自制积木 reporter 编译为 `self.<python_name>(...)`，由解释器动态方法处理；
5. 所有类型转换、比较、列表边界由运行时辅助函数 `_sc_*` 完成
   （详见 [scratch-semantics.md](scratch-semantics.md)）。

求值失败（未知表达式、编译错误）必须：
- 记录一次警告（含 block id / opcode / 源码）；
- 返回与 Scratch 接近的兜底值（数字上下文 `0`，字符串上下文 `""`，布尔上下文 `False`）；
- **不能**让整个脚本线程崩溃。

---

## 10. 变量与列表

### 10.1 作用域

| 类型 | 存放 | 可见性 |
|------|------|--------|
| 全局变量 | 舞台 `variables` → `GLOBALS[attr]` | 所有 target |
| 全局列表 | 舞台 `lists` → `GLOBALS[attr]` | 所有 target |
| 局部变量 | 角色实例属性 `self.<attr>` | 该角色及其克隆体 |
| 局部列表 | 角色实例属性 `self.<attr>` | 该角色及其克隆体 |

- 解析器为每个变量生成唯一 `attr`，IR 中保留原变量名；
- 反序列化后，`SpriteIR.variable_attrs` / `list_attrs` 建立「名字 → 属性名」；
- 生成代码用属性名直接读写，`GLOBAL_NAMES_SET` 决定是否转发到 `GLOBALS`；
- 扩展按变量名访问时使用 `VAR_ATTRS` / `LIST_ATTRS`。

### 10.2 变量监视器

- 舞台上显示的变量/列表由 `MONITORS` 常量描述；
- 显示/隐藏变量积木会动态增删监视器；
- 监视器值来自角色实例或 `GLOBALS`；
- 滑动条模式可反向修改变量值。

---

## 11. 帧循环与传感器

每帧顺序（现有运行时 `step()`）：

```text
1. pygame.event.get()
   ├─ QUIT / ESC → running = False
   ├─ F1 → 调试面板
   ├─ KEYDOWN → 更新 keys，触发 key:<key> 帽子
   ├─ MOUSEBUTTONDOWN → 更新 mouse_down/x/y，触发 clicked 帽子、拖动
   ├─ MOUSEMOTION → 更新鼠标坐标、拖动
   └─ 询问框输入处理
2. _update_state()
   ├─ elapsed / loudness / days_since_2000
   ├─ 同步 timer/mouse/answer 到每个角色
   ├─ _update_conditions()  （when timer/loudness >）
   └─ _update_frame_hats()  （扩展帽子）
3. _draw() + _present()
4. frame += 1，notify_all()
5. clock.tick(fps)
```

传感器时间基准：

- `timer`：`time.time() - start_time - timer_offset`，绿旗重置；
- `days_since_2000`：本地时区 2000-01-01 00:00:00 起的天数；
- `loudness`：麦克风线程更新，未安装 sounddevice 时为 0；
- `current`：本地时间。

---

## 12. warp（运行时不刷新）

- 定义块 `warp=true` 时，调用 `sprite._enter_procedure(warp=True)`；
- 首次进入 warp 时 `runtime.warp_begin()`，退出时 `runtime.warp_end()`；
- warp 期间 `_yield_frame()` 不等待，但每 0.5 秒（`warp_timer`）强制让出一次，
  避免死循环卡死界面；
- warp 期间 `runtime.step()` 跳过绘制，只保留上一帧画面；
- 嵌套 warp 通过 `_local.warp_depth` 计数，只有最外层进入/退出时操作 runtime。

解释器调用过程时必须复刻：

```python
sprite._enter_procedure(warp=warp)
try:
    execute_procedure_body()
except _ProcedureReturn:
    pass
finally:
    sprite._leave_procedure(warp=warp)
```

---

## 13. Turbo / 插值 / 其它运行时选项

| 选项 | 来源 | 行为 |
|------|------|------|
| `framerate` | `_twconfig_` | 覆盖 FPS，默认 30 |
| `turbo` | `_twconfig_` / `--turbo` | 所有 `_yield_frame()` 不等待（除 warp_timer 限制） |
| `interpolation` | `_twconfig_` | 渲染位置/方向/大小在帧间插值 |
| `fencing` | `_twconfig_` | 是否限制角色在舞台边界内 |
| `miscLimits` | `_twconfig_` | 是否启用杂项限制（如列表长度） |
| `cloneLimit` | `_twconfig_` | 克隆体上限，`0`/`Infinity` 表示无限 |
| `warpTimer` | `_twconfig_` | warp 强制让出间隔 |
| `hqPen` | `_twconfig_` | 高质量画笔 |
| `stageWidth/Height` | `_twconfig_` | 自定义舞台尺寸 |

---

## 14. 与官方 VM 的已知差异

本项目运行时是 pygame 复刻，不是官方 JS VM，以下差异需要在 VM 中显式说明：

| 项 | 差异 | 处理 |
|----|------|------|
| JS 数字 | Python int 可无限精度 | `_sc_num` 在比较/运算时转 float |
| JS 字符串 | UTF-16 码元计数 | Python 按码点；emoji 长度不同 |
| 线程模型 | Python 线程 + 公平锁 | 行为接近，但顺序受 GIL 影响 |
| SVG | 简化渲染器 | 复杂 SVG 可能失真，降级为占位图 |
| 音频 | pygame.mixer | MP3 支持依赖 SDL_mixer |
| 视频/摄像头 | 不支持 | 相关积木降级为无操作 |
| 编译型积木（TurboWarp compiler） | 不支持 | 解释执行即可 |
| 自定义扩展 | 仅内置扩展 | 未知扩展返回 0，并记录警告 |

---

## 15. 参考

- [scratch-vm `src/engine/sequencer.js`](https://github.com/scratchfoundation/scratch-vm/blob/develop/src/engine/sequencer.js)
- [scratch-vm `src/engine/thread.js`](https://github.com/scratchfoundation/scratch-vm/blob/develop/src/engine/thread.js)
- [scratch-vm `src/blocks/scratch3_control.js`](https://github.com/scratchfoundation/scratch-vm/blob/develop/src/blocks/scratch3_control.js)
- [scratch-vm `src/blocks/scratch3_procedures.js`](https://github.com/scratchfoundation/scratch-vm/blob/develop/src/blocks/scratch3_procedures.js)
- [TurboWarp: Compiler & warp](https://docs.turbowarp.org/)
