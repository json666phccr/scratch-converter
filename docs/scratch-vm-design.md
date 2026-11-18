# Scratch VM 实现设计

本文是本项目 `src/scratch_vm/` 的设计蓝图，明确模块职责、数据结构、执行流程、
调试协议与验收标准。实现必须与本文一致；行为语义以
[scratch-vm-execution.md](scratch-vm-execution.md) 为准。

---

## 1. 目标与范围

### 1.1 目标

1. 读取 `.sb3` / `.json`，**直接解释 IR 执行**，不生成中间 Python 脚本。
2. 复用现有 pygame 运行时（渲染、画笔、克隆、扩展、音频、询问框），
   避免重写一套图形栈。
3. 提供**命令行调试器**与**游戏窗口内可视化调试面板**：
   - 暂停 / 继续 / 单步积木 / 单帧；
   - 按 opcode、角色、block id、条件设置断点；
   - 执行轨迹（环形缓冲）、调用栈、线程列表；
   - 变量 / 列表查看与 watch 表达式；
   - 执行计数、耗时、错误上下文。

### 1.2 非目标

- 不复刻 Scratch 编辑器的积木拖拽与工作区。
- 不实现 TurboWarp 编译器（compiler），只解释执行。
- 不支持任意第三方 JS 扩展；未知扩展返回 0 并记录警告。
- 不保证 SVG / MP3 的 100% 渲染与解码一致性（沿用现有运行时的能力）。

---

## 2. 总体架构

```text
                 ┌────────────────────────────┐
  .sb3 ──loader──▶│ LoadedProject               │
                 │  project: ProjectIR         │
                 │  project_json: dict         │
                 │  assets_dir: str            │
                 └───────────┬────────────────┘
                             │
                 ┌───────────▼────────────────┐
                 │ module.RuntimeModule        │
                 │  exec 运行时模板            │
                 │  ScratchRuntime / Sprite    │
                 │  动态角色类                 │
                 └───────────┬────────────────┘
                             │
        ┌────────────────────▼─────────────────────┐
        │ interpreter.VMInterpreter                 │
        │  · 表达式编译缓存 / 求值                   │
        │  · 语句解释（控制流手写，叶子块编译执行）   │
        │  · 帽子注册 / 过程调用帧 / warp / yield     │
        └───────┬──────────────────────┬───────────┘
                │                      │
     ┌──────────▼─────────┐   ┌────────▼──────────┐
     │ debugger.Controller │   │ overlay.Panel     │
     │  暂停/断点/trace/栈 │   │  F2 可视化面板     │
     └──────────┬─────────┘   └────────┬──────────┘
                │                      │
                └──────────┬───────────┘
                           │
                    ┌──────▼──────┐
                    │ cli / main  │
                    └─────────────┘
```

数据流：

```text
sb3 → loader → ProjectIR ─┬─▶ module（运行时命名空间 + 角色类）
                          └─▶ interpreter（脚本/表达式/过程索引）
runtime + sprites → interpreter.install() → runtime.start()
```

---

## 3. 目录结构

```text
src/scratch_vm/
├── __init__.py          # 公开 API：run_project / VM / __version__
├── loader.py            # SB3/JSON 加载、资产解压、生命周期
├── module.py            # 运行时模板 exec、动态角色类生成
├── interpreter.py       # IR 解释器、表达式、过程帧、调试钩子
├── debugger.py          # DebugController、断点、trace、watch、统计
├── overlay.py           # pygame 可视化调试面板
├── cli.py               # 参数解析、交互命令循环
└── __main__.py          # python -m scratch_vm 入口
```

依赖方向：

```text
loader → ir / scratch_parser
module → python_generator / runtime_code / ir
interpreter → ir / module / debugger
debugger → interpreter（弱依赖：只调用 eval_expr / dump 接口）
overlay → pygame / debugger
cli → 以上全部
```

禁止反向依赖：`module` 不 import `interpreter`；`interpreter` 不 import `cli`。

---

## 4. loader.py

### 4.1 数据结构

```python
@dataclass
class LoadedProject:
    path: str                 # 原始文件路径
    project_json: dict        # project.json 原始字典
    project: ProjectIR        # 解析后的 IR
    assets_dir: str           # 资产目录
    temp_dir: Optional[str]   # 临时解压目录（.json 输入为 None）

    @property
    def name(self) -> str: ...          # 文件名（不含扩展名）
    def close(self) -> None: ...        # 清理临时目录
    def __enter__(self) -> "LoadedProject": ...
    def __exit__(self, *exc) -> None: ...
```

### 4.2 接口

```python
def load_project(path: str, extract_assets: bool = True) -> LoadedProject:
    """读取 .sb3/.zip/.json；失败时抛 LoadError（带路径和原因）"""
```

实现要点：

1. 读取：
   - `.json` → `json.load`；`assets_dir = dirname(path)`。
   - `.sb3` / `.zip` → `zipfile`，优先根目录 `project.json`，否则首个 `*.json`。
2. 资产：
   - 创建 `tempfile.mkdtemp(prefix="scratch_vm_")`；
   - 遍历 ZIP，跳过目录与 `project.json`；
   - `name = os.path.basename(info.filename)`，为空或含 `..` 时丢弃；
   - 写入 `assets_dir/name`。
3. IR：`project = parse_scratch_project(project_json)`。
4. 校验：`targets` 必须是非空数组；至少一个 `isStage=true`，否则合成一个空舞台。
5. 异常：包装成 `LoadError(path, message)`，CLI 打印后退出码 2。

---

## 5. module.py

### 5.1 职责

把字符串模板变成可用的运行时命名空间：

```python
class RuntimeModule:
    namespace: dict[str, Any]       # exec 结果
    Runtime: type                   # ScratchRuntime
    SpriteBase: type                # ScratchSprite
    sprite_classes: list[type]      # 每个 IR 角色一个类
    project: ProjectIR

    def create_runtime(self, **options) -> Any: ...
    def create_sprites(self, runtime) -> list[Any]: ...
```

### 5.2 构建命名空间

```python
def build_module(project: ProjectIR, assets_dir: str) -> RuntimeModule:
    gen = PythonGenerator()
    gen._prepare_globals(project)
    gen._prepare_extensions(project)

    lines = list(gen._module_imports())
    lines += gen._generate_runtime_helpers()      # 含扩展源码
    lines += gen._generate_runtime_constants(project)
    lines += gen._generate_runtime_class()
    lines += gen._generate_base_class()

    filename = os.path.join(assets_dir, "scratch_vm_runtime.py")
    source = "\n".join(lines)
    namespace = {
        "__name__": "scratch_vm_runtime",
        "__file__": filename,
    }
    exec(compile(source, filename, "exec"), namespace)
    ...
```

说明：

- `_generate_runtime_constants` 里 `ASSETS_DIR = _SCRIPT_DIR`，
  因此把 `__file__` 指向 `assets_dir` 内的虚拟文件即可，无需事后改常量。
- `_generate_runtime_helpers` 会拼入实际用到的扩展源码；
  扩展帽子存在时 `_prepare_extensions` 自动加入 `_ext_frame_hat_action`。
- 每次构建使用独立的命名空间，**不同 VM 实例互不污染**（`GLOBALS` 也是独立的）。

### 5.3 动态角色类

为每个 `SpriteIR` 生成类：

```python
class VM_Sprite_0(ScratchSprite):
    GLOBAL_NAMES = ('分数', '记录')
    GLOBAL_NAMES_SET = frozenset(GLOBAL_NAMES)
    VAR_ATTRS = {'分数': '分数'}
    LIST_ATTRS = {'记录': '记录'}

    def __init__(self):
        super().__init__()
        self.x = 0
        self.y = 0
        ...
```

生成规则（与 `PythonGenerator._generate_sprite_class` 保持一致）：

| 项 | 规则 |
|----|------|
| 类名 | `VM_Sprite_<index>_<sanitize_name(name)>`，索引保证唯一 |
| `GLOBAL_NAMES` | 舞台：全部全局属性；角色：全局属性 − 本地同名属性 |
| `VAR_ATTRS` / `LIST_ATTRS` | 变量/列表**名字 → 属性名**，扩展按名字访问时使用 |
| `__init__` | 调用 `super().__init__()`，写入初始坐标/方向/造型/声音/变量/列表 |
| 初始变量 | 非舞台角色写入 `self.<attr>`；舞台变量已在 `GLOBALS` 中 |
| 大列表 | 直接 `list(...)` 赋值（VM 加载一次，无需类常量优化） |
| 过程方法 | 由解释器在 `install()` 阶段动态挂载 |
| `run()` | 由解释器挂载：`type(self).VM.register_hats(self)` |

类属性（由解释器设置）：

```python
cls.VM = interpreter
cls.VM_IR = sprite_ir
cls.VM_SCRIPTS = [hat_stmt, ...]
cls.VM_PROCEDURES = {proccode: definition_stmt}
```

> 使用类属性而不是实例属性，克隆体自动共享，无需在 `_make_clone` 里复制。

### 5.4 创建实例

```python
def create_sprites(self, runtime):
    sprites = []
    for ir, cls in zip(self.project.sprites, self.sprite_classes):
        sprite = cls()
        runtime.add_sprite(sprite)
        sprites.append(sprite)
    return sprites
```

`runtime.add_sprite` 负责 `sprite._runtime = runtime`；
舞台会被记录为 `runtime.stage_sprite`。

---

## 6. interpreter.py

### 6.1 数据结构

```python
@dataclass
class VMFrame:
    kind: str                    # 'script' | 'procedure'
    title: str                   # 显示名：绿旗 / 广播xxx / 过程 proccode
    proc_stmt: Optional[Statement]
    locals: dict[str, Any]       # arg_<name> -> value
    warp: bool = False

@dataclass
class VMThreadState:
    tid: int
    sprite: Any
    script_title: str
    frames: list[VMFrame]
    block: Optional[Statement] = None
    steps: int = 0
    started: float = 0.0
```

线程状态放在 `threading.local()`：

```python
self._local = threading.local()
def state(self) -> Optional[VMThreadState]:
    return getattr(self._local, "state", None)
```

### 6.2 初始化

```python
class VMInterpreter:
    def __init__(self, project, module, runtime, debug=None):
        self.project = project
        self.module = module
        self.runtime = runtime
        self.debug = debug
        self.gen = PythonGenerator()
        self.gen._prepare_globals(project)
        self.gen._prepare_extensions(project)
        self._expr_codes: dict[int, Optional[CodeType]] = {}
        self._leaf_codes: dict[int, Optional[CodeType]] = {}
        self._sprite_meta: dict[int, SpriteMeta] = {}   # id(SpriteIR) -> meta
        self._build_indexes()
```

`_build_indexes()`：

1. 遍历每个 `SpriteIR`：
   - `gen._build_procedure_names(sprite)`（设置全局 proccode 解析器）；
   - 建立 `proccode → PROCEDURE_DEFINE`、`python_name → (sprite, stmt)`；
   - 收集该角色的所有表达式并编译缓存；
   - 收集所有语句，生成叶子语句代码缓存（按 `id(stmt)`）。
2. 每个角色调用 `install_class_methods(sprite, cls)`：
   - `cls.run = _make_run(cls)`
   - `cls._vm_script_<i> = _make_script_method(i)`
   - 过程方法：`setattr(cls, python_name, _make_proc_method(...))`

> `_build_procedure_names` 依赖全局 `set_procedure_name_resolver`，
> 因此必须**按角色依次**构建表达式源码，不能并行。

### 6.3 表达式编译与求值

```python
def _compile_expr(self, expr) -> Optional[CodeType]:
    if expr is None:
        return None
    try:
        source = expr.to_python_source()
        return compile(source, "<scratch-expr>", "eval")
    except Exception as error:
        self._warn_expr(expr, error)
        return None

def eval_expr(self, expr, sprite, locals_=None):
    code = self._expr_codes.get(id(expr))
    if code is None:
        return self._expr_fallback(expr)
    env = {"self": sprite}
    if locals_:
        env.update(locals_)
    try:
        return eval(code, self.module.namespace, env)
    except Exception as error:
        self._warn_expr(expr, error)
        return self._expr_fallback(expr)
```

兜底值按上下文推断：

| 表达式类型 | 兜底 |
|------------|------|
| `BOOLEAN` / `AND` / `OR` / `NOT` / 比较 | `False` |
| 列表相关 | `""` / `0` / `False`（按具体类型） |
| 其他 | `0` |

编译缓存以 `id(expr)` 为键：IR 在 VM 生命周期内不会被回收或修改。

### 6.4 叶子语句编译

“叶子语句”指不包含子栈、不需要解释器控制流处理的语句。
直接把 `PythonGenerator._generate_statement(stmt, 0)` 的源码编译成
`exec` 代码对象：

```python
def _compile_leaf(self, stmt) -> Optional[CodeType]:
    lines = self.gen._generate_statement(stmt, 0)
    source = "\n".join(lines).strip()
    if not source or source.startswith("#"):
        return None
    try:
        return compile(source, "<scratch-block>", "exec")
    except Exception as error:
        self._warn_block(stmt, error)
        return None

def _exec_leaf(self, sprite, stmt):
    code = self._leaf_codes.get(id(stmt))
    if code is None:
        return
    frame = self._current_frame()
    env = {"self": sprite}
    if frame is not None:
        env.update(frame.locals)
    exec(code, self.module.namespace, env)
```

为什么用 `exec` + `locals`：

- `_generate_statement` 会把表达式直接内联成源码；
- 自制积木参数表达式编译为 `arg_<name>`，必须从当前调用帧注入；
- `exec` 的 `LOAD_NAME` 先查 locals，再查 globals，正好满足；
- 每个线程、每次调用使用独立 `env`，线程安全。

### 6.5 语句分派

```python
def execute_statement(self, stmt):
    state = self.state()
    self.debug.before_statement(state, stmt) if self.debug else None
    handler = self._handlers.get(stmt.type)
    if handler is not None:
        handler(stmt)
    else:
        self._exec_leaf(state.sprite, stmt)
```

需要手写的控制语句：

| BlockType | 实现要点 |
|-----------|----------|
| `REPEAT` | `_sc_repeat_count`；每轮 `execute_body`；按纯计算优化决定是否 `_yield_frame` |
| `FOREVER` | `while sprite._running:`；每轮 body + yield |
| `IF` / `IF_ELSE` | `_sc_bool` 条件 |
| `WAIT_UNTIL` | `while alive and not cond: _yield_frame()` |
| `REPEAT_UNTIL` | `while alive and not cond: body; yield` |
| `FOR_EACH` | 遍历 `_sc_list_values`，写变量，每轮 yield |
| `ALL_AT_ONCE` | 顺序执行 body，不额外 yield |
| `PROCEDURE_DEFINE` | 跳过 |
| `PROCEDURE_CALL` | 求值参数 → 进入过程帧 |
| `PROCEDURE_RETURN` | `raise _VMReturn(value)` |
| `EXTENSION` + body | 列表工具 foreach / 临时变量 foreach 特判；其余先执行扩展再执行 body |
| `COMMENT` / `UNKNOWN` | 跳过 |

其余语句（运动/外观/声音/变量/列表/广播/克隆/停止/询问等）走叶子编译。
`STOP` 也走叶子编译，因为 `sprite.stop()` 本身会抛
`StopIteration` / `_ProcedureReturn`。

### 6.6 脚本执行

```python
def _make_script_method(self, index):
    def script(self):
        return self.run_script(self, index)
    script.__name__ = f"_vm_script_{index}"
    return script
```

> 注意：闭包里的 `self` 在绑定前是解释器；挂载时要避免与角色实例的 `self` 混淆，
> 推荐写法：
>
> ```python
> interpreter = self
> def script(sprite, _i=index):
>     return interpreter.run_script(sprite, _i)
> ```

`run_script`：

```python
def run_script(self, sprite, index):
    ir = type(sprite).VM_IR
    hat = type(sprite).VM_SCRIPTS[index]
    title = self._describe_hat(hat)
    state = VMThreadState(tid=threading.get_ident(), sprite=sprite,
                          script_title=title, frames=[VMFrame('script', title, None, {})],
                          started=time.time())
    self._local.state = state
    if self.debug:
        self.debug.thread_started(state)
    try:
        self.execute_chain(hat.next)
    except StopIteration:
        pass
    finally:
        if self.debug:
            self.debug.thread_finished(state)
        self._local.state = None
```

- `StopIteration` 是 `stop all` / `stop this script` 的正常控制流，直接吞掉；
- 其他异常交给 runtime runner 打印 traceback，但解释器先调用
  `debug.record_error(state, state.block, exc)` 记录积木上下文。

`execute_chain`：

```python
def execute_chain(self, stmt):
    state = self.state()
    seen = set()
    while stmt is not None and state.sprite._running:
        if id(stmt) in seen:      # 防御异常 IR 环
            break
        seen.add(id(stmt))
        state.block = stmt
        self.execute_statement(stmt)
        stmt = stmt.next
```

> `seen` 只在单次 chain 调用内生效，避免误伤循环体重复执行同一语句。

`execute_body`：遍历列表，逐条调用 `execute_chain`（列表元素的 `next` 已被解析器断开）。

### 6.7 过程调用

```python
def _run_procedure(self, sprite, proc, args):
    arg_names = list(proc.extra.get("args") or [])
    defaults = list(proc.extra.get("argumentdefaults") or [])
    locals_ = {}
    for index, name in enumerate(arg_names):
        key = f"arg_{sanitize_name(str(name), 'arg')}"
        if index < len(args):
            locals_[key] = args[index]
        elif index < len(defaults):
            locals_[key] = defaults[index]
        else:
            locals_[key] = False if arg_types[index] == "b" else ""
    warp = bool(proc.extra.get("warp"))
    frame = VMFrame("procedure", proc.extra.get("proccode") or "procedure", proc,
                    locals_, warp)
    state = self.state()
    state.frames.append(frame)
    sprite._enter_procedure(warp)
    try:
        self.execute_body(proc.body)
        return None
    except _VMReturn as ret:
        return ret.value
    except _ProcedureReturn:
        return None
    finally:
        state.frames.pop()
        sprite._leave_procedure(warp)
```

`_ProcedureReturn`、`_VMReturn` 来自运行时命名空间：

```python
self._ProcedureReturn = module.namespace["_ProcedureReturn"]
```

过程方法（供表达式与 `PROCEDURE_CALL` 共用）：

```python
def _make_proc_method(self, proc):
    interpreter = self
    def method(sprite, *args):
        return interpreter._run_procedure(sprite, proc, list(args))
    method.__name__ = proc.extra["python_name"]
    return method
```

缺失参数补齐规则：

1. 调用实参够 → 用实参；
2. 否则取 `argumentdefaults[index]`；
3. 否则字符串参数 `""`、布尔参数 `False`。

### 6.8 帽子注册

```python
def register_hats(self, sprite):
    cls = type(sprite)
    sprite._handlers = {}
    sprite._conditions = []
    sprite._frame_hats = []
    for index, hat in enumerate(cls.VM_SCRIPTS):
        func = getattr(sprite, f"_vm_script_{index}")
        name, doc, event = self.gen._event_info(hat)
        if hat.type == BlockType.EXTENSION_HAT:
            values = {}
            for key, expr in hat.extra.get("inputs", []):
                values[key] = (lambda e=expr, s=sprite: self.eval_expr(e, s))
            for key, value in (hat.extra.get("fields") or {}).items():
                values.setdefault(key, (lambda v=value: v))
            sprite._register_extension_hat(
                hat.extra.get("namespace", ""), hat.extra.get("opcode", ""),
                values, func)
            continue
        if hat.type == BlockType.WHEN_GREATER_THAN:
            menu = str(hat.extra.get("menu") or "TIMER").lower()
            sprite._register_greater_than(
                menu,
                lambda e=hat.value, s=sprite: self.eval_expr(e, s),
                func)
            continue
        if event:
            sprite._register(event, func)
```

`run()`：

```python
def _make_run_method(self, cls):
    interpreter = self
    def run(sprite):
        interpreter.register_hats(sprite)
    return run
```

克隆体调用 `run()` 时会重新注册，解释器索引按类共享，天然可用。

### 6.9 yield 与 warp

- 循环使用 `sprite._yield_frame()`；
- `WAIT` 等阻塞块由叶子代码中的 `self.wait(...)` 处理；
- 过程调用使用 `sprite._enter_procedure(warp)` / `_leave_procedure(warp)`；
- **不要**在解释器里另建调度器或锁。

循环让帧优化：

```python
skip_yield = (self.gen._repeat_count_is_small(stmt)
              and self.gen._body_is_pure_computation(stmt.body))
for _ in range(count):
    self.execute_body(stmt.body)
    if not skip_yield and sprite._running:
        sprite._yield_frame()
```

> 与生成代码保持一致。纯计算循环在大型项目初始化列表时非常常见，
> 逐轮让帧会慢到不可用。

---

## 7. debugger.py

### 7.1 数据结构

```python
@dataclass
class Breakpoint:
    kind: str            # 'opcode' | 'sprite' | 'block' | 'cond'
    value: Any
    enabled: bool = True
    hits: int = 0
    label: str = ""

@dataclass
class TraceRecord:
    seq: int
    time: float
    tid: int
    frame: int
    sprite: str
    opcode: str
    block_id: str
    block: str           # 可读描述
    script: str

@dataclass
class ErrorRecord:
    time: float
    sprite: str
    opcode: str
    block_id: str
    message: str
```

### 7.2 DebugController

```python
class DebugController:
    def __init__(self, interpreter, runtime, project,
                 trace_size=2000, trace_print=False):
        self.paused = False
        self.mode = "run"            # 'run' | 'pause' | 'step_block' | 'step_frame'
        self.step_tid = None
        self.frame_target = None
        self.cond = threading.Condition()
        self.breakpoints = []
        self.trace = collections.deque(maxlen=trace_size)
        self.watches = []
        self.stats = collections.Counter()
        self.sprite_stats = collections.Counter()
        self.errors = collections.deque(maxlen=50)
        self.threads = {}
        self.last_state = None
        self.last_stmt = None
        self._stop = False
        self._print_lock = threading.Lock()
```

### 7.3 钩子

```python
def before_statement(self, state, stmt):
    """由解释器在每个语句执行前调用；可能阻塞（暂停/断点）"""
```

流程：

1. `self.stats[opcode] += 1`，`self.sprite_stats[sprite.name] += 1`；
2. 写入 trace 环形缓冲；
3. `trace_print` 时输出一行；
4. 检查断点：
   - `opcode`：`stmt.extra.get("opcode")` 或 IR 类型名；
   - `sprite`：角色名，支持 `name#clone`；
   - `block`：`stmt.extra.get("block_id")`；
   - `cond`：Python 表达式，环境含 `sprite/runtime/stmt/frame/var/lst`；
5. 命中且当前不是“单步放行”时：
   - `self.paused = True`，`self.mode = "pause"`；
   - `self.last_state = state`，`self.last_stmt = stmt`；
   - 打印断点信息；
6. `_wait_if_paused(state)`。

`_wait_if_paused`：

```python
with self.cond:
    while self.paused:
        if self.mode == "step_block" and self.step_tid == state.tid:
            self.mode = "pause"     # 只放行一个语句，下一个语句再次阻塞
            return
        if self.mode == "step_frame" and self._frame_advanced():
            self.mode = "pause"
            return
        self.cond.wait(0.1)
```

单帧放行由命令处理器控制：

```python
def step_frame(self):
    target = self.runtime.frame + 1
    with self.cond:
        self.mode = "step_frame"
        self.frame_target = target
        self.paused = False
        self.cond.notify_all()
    while self.runtime.running and self.runtime.frame < target:
        time.sleep(0.005)
    self.pause()
```

> 单帧命令会在**调用者线程**里等待帧推进，然后重新暂停。
> 调用者是 CLI 的 stdin 线程或测试代码，不阻塞渲染主循环。

### 7.4 命令接口

| 方法 | 行为 |
|------|------|
| `pause()` | `paused=True`，`mode='pause'`，打印当前位置 |
| `resume()` | `paused=False`，`mode='run'`，`cond.notify_all()` |
| `step_block()` | `paused=True`，`mode='step_block'`，`step_tid=当前线程`，notify |
| `step_frame()` | 见上 |
| `add_breakpoint(kind, value)` | 去重后追加 |
| `delete_breakpoint(index)` | 1 起始；`all` 清空 |
| `add_watch(expr)` | 追加表达式 |
| `eval_watches()` | 返回 `[(expr, value_or_error)]` |
| `dump_variables(sprite_name=None)` | 返回结构化变量/列表 |
| `call_stacks()` | 返回 `{tid: [frame titles]}` |
| `thread_list()` | 活动线程、角色、当前积木、运行时长 |
| `recent_trace(n=20)` | 最近 n 条 trace |
| `stats_report()` | 总语句数、按 opcode / 角色、运行时长 |
| `record_error(state, stmt, exc)` | 记录并打印带积木上下文的错误 |
| `shutdown()` | `_stop=True`，`paused=False`，notify_all |

### 7.5 线程安全

- `paused` / `mode` 的读写全部放在 `self.cond` 内；
- 打印使用 `self._print_lock`，避免多条 trace 交错；
- 调试器**不执行 IR**，只读取状态；watch 表达式允许调用 `var/lst` 读取变量；
- 暂停时脚本线程持有 runtime 的 turn lock，这是预期行为：
  整个 VM 冻结，但主线程仍可渲染、处理窗口事件与断点命令。

### 7.6 变量与调用栈读取

变量读取必须走 IR 元数据，不能遍历 `__dict__`（会混入内部属性）：

```python
def dump_variables(self, sprite_name=None):
    result = []
    for sprite_ir, sprite in self.interpreter.iter_sprites():
        if sprite_name and sprite.name != sprite_name:
            continue
        entry = {"name": sprite.name, "is_clone": ..., "variables": {}, "lists": {}}
        for name, attr in sprite_ir.variable_attrs.items():
            entry["variables"][name] = getattr(sprite, attr)
        for name, attr in sprite_ir.list_attrs.items():
            entry["lists"][name] = list(getattr(sprite, attr))
        result.append(entry)
    return result
```

调用栈来自 `interpreter.active_threads()`：

```python
def call_stacks(self):
    return {
        tid: [frame.title for frame in state.frames]
        for tid, state in self.threads.items()
    }
```

---

## 8. overlay.py

### 8.1 显示内容

窗口内面板（默认左上角，半透明黑底）：

```text
[VM] PAUSED  frame 123  fps 30  线程 4  克隆 2
当前位置: Cat  motion_movesteps  (blockId=abc123)
调用栈: 当绿旗被点击 > 我的积木 add %s %s
变量: 分数=10  速度=3
断点: 2  轨迹: 2000
```

- 暂停时红色标题，运行时绿色；
- 变量最多显示 8 条，调用栈最多 4 层；
- `headless` 时不绘制；
- F2 切换显示/隐藏。

### 8.2 挂载方式

不改运行时模板，包装 `runtime._draw`：

```python
class DebugOverlay:
    def __init__(self, runtime, debug):
        self.runtime = runtime
        self.debug = debug
        self.enabled = not runtime.headless
        self._orig_draw = runtime._draw
        runtime._draw = self._draw
        self._font = pygame.font.Font(runtime.font_path, 14) ...
```

```python
def _draw(self):
    self._orig_draw()
    if self.enabled:
        self._draw_panel()
```

F2 轮询：

```python
keys = pygame.key.get_pressed()
if keys[pygame.K_F2] and not self._f2_down:
    self.enabled = not self.enabled
self._f2_down = keys[pygame.K_F2]
```

绘制在 `runtime.stage_surface` 上，`_present()` 会把它放大到窗口。

---

## 9. cli.py

### 9.1 参数

```text
python -m scratch_vm PROJECT [options]

运行控制
  --headless                 无窗口（SDL dummy）
  --fps N                    覆盖帧率
  --frames N                 运行 N 帧后退出
  --seconds N                运行 N 秒后退出
  --seed N                   随机种子
  --turbo                    立即模式
  --no-fencing               关闭舞台边界限制
  --no-audio                 关闭声音
  --stage-size WxH           自定义舞台尺寸
  --infinite-clones          解除克隆上限

调试
  --debug                    启用交互调试器（stdin 命令）
  --pause-on-start           启动后立即暂停
  --trace                    打印每条执行的积木
  --trace-size N             trace 环形缓冲大小（默认 2000）
  --break-opcode OP          断点：opcode（可逗号分隔/多次指定）
  --break-sprite NAME        断点：角色名
  --break-block ID           断点：block id
  --break-if EXPR            条件断点（Python 表达式）
  --watch EXPR               watch 表达式（可多次）
  --no-overlay               关闭可视化调试面板
  --stats                    退出时打印执行统计
  --dump-vars                退出时打印变量/列表
```

### 9.2 交互命令

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
| `vars [角色]` | `v` | 变量/列表 |
| `watch [expr]` | `w` | 查看或添加 watch |
| `break opcode OP` | `b` | 按 opcode 设断点 |
| `break sprite NAME` | | 按角色设断点 |
| `break block ID` | | 按 block id 设断点 |
| `break if EXPR` | | 条件断点 |
| `breaks` | `bl` | 断点列表 |
| `delete N\|all` | `bd` | 删除断点 |
| `stats` | `st` | 执行统计 |
| `overlay` | `o` | 切换可视化面板 |
| `quit` | `q` | 退出 |

### 9.3 启动流程

```python
def main(argv=None):
    args = parse_args(argv)
    random.seed(args.seed) if args.seed is not None
    loaded = load_project(args.path)
    runtime_module = build_module(loaded.project, loaded.assets_dir)
    runtime = runtime_module.create_runtime(...)
    debug = DebugController(...) if args.debug else None
    interpreter = VMInterpreter(loaded.project, runtime_module, runtime, debug)
    interpreter.install()
    sprites = runtime_module.create_sprites(runtime)
    overlay = DebugOverlay(runtime, debug) unless disabled/headless
    if debug:
        configure breakpoints/watches
        start stdin thread
        if args.pause_on_start: debug.pause()
    try:
        runtime.start(max_frames=args.frames, max_seconds=args.seconds)
    finally:
        debug.shutdown() if debug
        runtime.shutdown()
        loaded.close()
        print stats/vars if requested
```

> stdin 线程是 daemon；`q` 先 `debug.shutdown()`，再 `runtime.running = False`，
> 保证被暂停的脚本线程能退出，`runtime.shutdown()` 的 join 不会卡住。

### 9.4 非交互模式

不传 `--debug` 时也允许 `--trace` / `--break-*`：
断点命中会打印信息并暂停，但没有命令线程，因此等价于“暂停后只能 Ctrl+C”。
为避免误导，非交互模式下断点命中**只打印一次并继续**，
除非显式传 `--debug`。

---

## 10. `__init__.py` 公开 API

```python
from .loader import load_project, LoadedProject, LoadError
from .module import build_module, RuntimeModule
from .interpreter import VMInterpreter
from .debugger import DebugController
from .overlay import DebugOverlay

__version__ = "0.10.0"

def run_project(path, headless=True, max_frames=None, max_seconds=None,
                debug=False, **options) -> dict:
    """便捷入口：加载 + 构建 + 运行，返回统计/变量快照"""
```

---

## 11. 解析器配合改动

`scratch_parser.py` 需要在 `Statement.extra` 中增加：

```python
stmt.extra["block_id"] = raw.id
stmt.extra["opcode"] = raw.opcode
```

位置：`parse_single_block` 创建 `Statement` 之后（扩展语句分支同样处理）。

影响：

- `python_generator` 不读取这两个键，生成代码不变；
- 调试器可按 block id 定位、按 opcode 统计；
- 错误信息可以显示原始积木 ID。

---

## 12. 测试计划

新增 `tests/test_scratch_vm.py`，并接入 `tests/test_all.py`。

### 12.1 单元测试

| 编号 | 内容 |
|------|------|
| VM-1 | loader：读取最小 JSON，IR 字段正确；临时目录清理 |
| VM-2 | module：运行时命名空间含 `ScratchRuntime`/`ScratchSprite`/`GLOBALS`；角色类 `GLOBAL_NAMES` 正确 |
| VM-3 | 表达式：变量、运算、比较、列表、过程 reporter |
| VM-4 | 控制流：repeat / if / repeat_until（用假 sprite 直接驱动，不启 pygame） |
| VM-5 | 过程：参数默认值、递归、返回值 |
| VM-6 | 调试器：断点命中、单步、trace、变量 dump、watch |

### 12.2 集成测试（headless）

| 编号 | 内容 |
|------|------|
| VM-7 | 绿旗脚本修改变量并 say；运行 5 帧后变量正确 |
| VM-8 | 广播 + 接收脚本；broadcast and wait |
| VM-9 | 克隆：创建、局部变量独立、delete this clone |
| VM-10 | 自制积木递归（阶乘/斐波那契），结果正确 |
| VM-11 | 调试器暂停/继续/单步不破坏运行时；overlay 在 headless 下无异常 |
| VM-12 | 带扩展的最小项目（pen 清空/落笔不报错） |

### 12.3 构造测试项目

优先使用 `scratch_writer` 或手写 JSON 字典：

```python
project_json = {
    "targets": [stage_target, sprite_target],
    "monitors": [],
    "extensions": [],
    "meta": {"semver": "3.0.0", "vm": "0.2.0", "agent": "test"},
}
```

脚本用固定 block id（如 `hat`、`b1`、`b2`），便于断点测试。

### 12.4 验收命令

```bash
python tests/test_all.py
python -m scratch_vm example/xxx.sb3 --headless --frames 60 --stats
```

---

## 13. 版本与文档

实现完成后：

1. `src/converter.py::__version__` → `0.10.0`
2. `src/runtime_code/helpers.py::_RUNTIME_VERSION` → `0.10.0`
3. `README.md` 顶部版本号与新增「Scratch VM」章节：
   - 运行方式
   - 调试参数
   - 交互命令表
   - 与转换器的区别
4. 本文三份文档加入 README 的文档索引。

---

## 14. 里程碑

| 阶段 | 内容 | 完成标准 |
|------|------|----------|
| M1 | loader + module | 能加载最小 sb3 并实例化运行时/角色 |
| M2 | interpreter 基础 | 绿旗、变量、运算、say、repeat、if 可执行 |
| M3 | 完整语句 | 自制积木/递归/克隆/广播/等待/停止 |
| M4 | debugger | 暂停/继续/单步/断点/trace/变量/调用栈 |
| M5 | overlay + cli | `python -m scratch_vm` 全功能可用 |
| M6 | 测试 + 文档 + 版本 | 全量测试通过，README 更新 |

---

## 15. 风险与对策

| 风险 | 影响 | 对策 |
|------|------|------|
| 暂停线程持有 turn lock | 其他脚本无法运行 | 预期行为；主线程仍渲染；退出时 `debug.shutdown()` 先释放 |
| `exec` + locals 性能 | 大循环变慢 | 叶子代码预编译；纯计算循环跳过 yield；必要时后续引入闭包特化 |
| 表达式编译失败 | 脚本崩溃 | 逐表达式 try/except，返回兜底值并记录警告 |
| 过程名解析全局状态 | 多角色过程同名冲突 | 按角色顺序构建缓存；`python_name` 带唯一后缀 |
| 克隆体 `run()` 重复调用 | 帽子重复注册 | `register_hats` 每次先清空 `_handlers/_conditions/_frame_hats` |
| 递归过深 | Python `RecursionError` | 文档标注限制；捕获后记录错误并结束该线程 |
| 扩展缺失 | 返回 0 导致逻辑异常 | 记录警告；`extensions` 未注册时 `call_extension` 已有兜底 |
| headless 音频/显示 | 初始化失败 | `--no-audio`、`headless=True` 时 SDL dummy；overlay 不绘制 |
| 调试输出与渲染交错 | 命令提示混乱 | 打印加锁；提示符只在 stdin 线程输出 |
| IR 环 | 死循环 | `next` 遍历带 `seen`；链长度上限保护 |

---

## 16. 参考实现

可参考但**不直接复制**的官方实现：

- `scratch-vm/src/engine/runtime.js`：target/thread 管理、帽子、广播
- `scratch-vm/src/engine/sequencer.js`：线程调度、yield、warp
- `scratch-vm/src/engine/thread.js`：线程栈、状态
- `scratch-vm/src/blocks/scratch3_control.js`：控制积木
- `scratch-vm/src/blocks/scratch3_procedures.js`：自制积木
- `scratch-vm/src/serialization/sb3.js`：SB3 反序列化
- TurboWarp `compiler/`：仅用于理解 warp / 帧语义，不实现编译器

本项目运行时模板：

- `src/runtime_code/helpers.py`：`_sc_*` 语义函数、`_as_procedure`
- `src/runtime_code/runtime_class.py`：调度、广播、克隆、渲染、监视器
- `src/runtime_code/sprite_base.py`：角色方法、`_make_clone`、`_yield_frame`
