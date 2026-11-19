# 混淆器商业级加固方案

本文针对 `src/obfuscator/` 当前单向转换（SB3 → 混淆 Python）的安全弱点做逐项分析，
并给出分层的商业级加固设计。文档同时是后续实施的蓝图：每一项都标注了改动模块、
实现要点与验证方式。

背景：主流 Scratch→HTML 方案被原生 Scratch VM 限制，产物逻辑透明；
02engine 打包器的混淆也已被破解。我们的产物是**独立可执行的 Python 程序**，
防护上限远高于 HTML 方案，但当前 v1 实现仍有多个单点突破口，必须补齐。

---

## 1. 当前实现的弱点清单

按攻击成本从低到高排列。攻击者视角：拿到 `*_obf.py` 后如何还原逻辑。

| # | 弱点 | 现状 | 攻击方式 | 成本 |
|---|------|------|----------|------|
| W1 | **加载器全程明文** | 解密算法、salt、CRC、执行顺序全部可读 | 读 60 行源码即理解整个保护 | 极低 |
| W2 | **密钥就在文件里** | 主密钥 = `SHA256(salt + counter)`，salt 以字面量紧邻密文 | 复制解密函数，离线解出 payload | 极低 |
| W3 | **单点 exec** | 整个程序是一个 code object，一次性 `exec` | hook `builtins.exec` 或 `marshal.loads` 一次，dump 全部代码 | 低 |
| W4 | **字节码可反编译** | Python 3.11 code object 对 pycdc / decompyle3 友好 | dump 后反编译，恢复出接近原始的源码（含缩进与控制流） | 低 |
| W5 | **方法名明文** | 字符串加密只覆盖 `Constant` 字符串；`self.move(x)` 的 `move` 存在于 `co_names` | 反编译结果里 `move/say/broadcast/create_clone` 一目了然，直接映射回 Scratch 积木 | 低 |
| W6 | **一次性整体解密** | 启动时全部代码+资产解密进内存，资产整体落盘 tempdir | 内存 dump 一次拿走全部；tempdir 直接复制资产 | 低 |
| W7 | **CRC 不是防篡改** | CRC32 无密钥，只防损坏 | 改 payload 后重算 CRC 即可通过 | 低 |
| W8 | **无反调试** | `sys.settrace` / `sys.monitoring` / pdb attach 无任何检测 | 挂 trace 跟踪执行流 | 低 |
| W9 | **字符串解码单点** | 单一解码函数 + 明文缓存列表 | hook 解码函数一次，全部字符串（台词/变量名/资源名）泄露 | 低 |
| W10 | **资产名未混淆** | 沿用 `md5ext` 命名，可直接识别 SVG/WAV 并按名引用 | 按 Scratch 资产惯例直接理解资产用途 | 低 |
| W11 | **错误信息助攻** | `unsupported interpreter`、`SystemExit(1)` 等明确指出校验位置 | 按报错定位 patch 点 | 极低 |
| W12 | **无环境绑定** | 任意机器可运行 | 拿到文件即获得永久完整副本 | — |
| W13 | **固定种子可复现** | `--seed` 固定时 AST 噪音完全相同 | 若 seed 泄露，差分两次构建可剥离垃圾代码 | 中 |

**结论**：当前方案防"直接打开读"有效，防"认真逆向"无效。核心缺陷是
**单点解密 + 单点 exec + 明文加载器** 三件套，必须全部消除。

---

## 2. 加固目标与威胁模型

**防御目标（按优先级）**：

1. 使 `hook 一次 exec/marshal → dump → pycdc 反编译` 这条最低成本路径失效；
2. 使静态阅读加载器无法还原解密流程与密钥；
3. 使篡改/补丁加载器或 payload 的成本高于重写；
4. 使内存 dump 只能得到碎片而非全貌；
5. 提供合法分发的授权与机器绑定能力。

**明确不承诺**（诚实边界，写进用户文档）：

- 无法防御能任意操纵解释器运行时的高级攻击者（读内存、C 级 hook）；
- 纯 Python 层无法做到"绝对不可破解"；最终极强度靠 Tier 2 的原生编译达成。

---

## 3. Tier 1：纯 Python 强化（默认全开，跨平台）

### 3.1 多阶段链式解密（消除 W2/W3/W6 的"一次拿下"）

把"一个大 payload 一次解密"改为 **N 个阶段链式解锁**：

```text
stage0（明文加载器内置）
  ├─ 用 K0 解出 stage1（小型调度器 code object）
stage1
  ├─ 校验自身段哈希
  ├─ 用 K1 = HMAC(K_root, "s1") 解出主程序 code object
  ├─ 主程序按"函数簇"再拆成 M 个子段，各自独立加密
stage2（主程序运行时）
  ├─ 自定义懒加载器：函数簇首次被调用时才解密执行
```

实现要点：

- 生成期用 `ast` 把模块顶层函数分组为 M 个"函数簇"，每簇单独 `compile` 成
  code object 后独立加密；原调用点替换为 trampoline（首调解密+替换全局名）；
- 每个 stage 的密钥由**上一 stage 明文的哈希**派生：不运行到 stage i 就算不出
  i+1 的密钥，静态分析必须逐级跟着跑；
- salt 每段独立随机，互不重复。

效果：hook 一次 `exec` 只能拿到当前正在执行的一个簇；要拿全量必须把每个簇
都触发一遍（而我们可以在簇入口加入调用图检测——见 3.5）。

改动模块：`payload.py` 重写、`ast_obf.py` 增加函数簇拆分。

### 3.2 密钥分裂与加载器自校验（消除 W1/W2/W7/W11）

主密钥 **K_root 不以任何完整形式出现在文件中**：

```text
K_root = SHA256( P1 || P2 || P3 )
P1 = 常量池里 3~5 个看似普通的大整数常量（混在垃圾代码里）
P2 = 加载器关键代码段自身的 SHA256（生成期算好，作为校验段嵌在数据段之后）
P3 = 可选机器指纹 / 许可证字段（Tier 2）
```

- 校验段覆盖数据段：攻击者 patch 任何一处 → P2 变化 → K_root 错 → 解出垃圾；
- 校验失败 **不报清晰错误**：走假解密路径产出垃圾数据，在运行后期随机位置
  以普通 Python 异常崩溃（如 AttributeError/TypeError），让破解者无法定位
  触发点（"Silent Corrupt" 策略）；
- 移除 `unsupported interpreter` 等明文提示，版本不符同样走 Silent Corrupt。

### 3.3 属性访问派发表（消除 W5）

当前字符串加密只处理 `ast.Constant`，方法名在 `co_names` 明文。
新增 AST 变换：

```python
# 变换前
self.move(10)
self._say_text = "hi"

# 变换后
getattr(self, _D(0x1F))(10)
setattr(self, _D(0x22), _S[7])
```

- `_D(idx)` / `_S[idx]` 走加密字符串表；
- 排除名单：Python 语法要求的 dunder、`__dict__`/`__class__` 等
  C 层必须的名字、`runtime`/`sprites` 等被字符串形式引用的名字
  （沿用"属性名出现在字符串常量中则跳过"的规则，该规则已验证可行）；
- 效果：反编译产物里所有 Scratch 方法调用都变成 `getattr(self, _D(...))`，
  无法直接映射回积木。

改动模块：`ast_obf.py` 新增 `_DispatchTableTransformer`。

### 3.4 链式加密字符串表（消除 W9）

```text
entry_i = XOR(plaintext_i, KS_i)
KS_i    = SHA256(K_root || i || digest(entry_{i-1}))
```

- 必须按顺序解码，无法单独 hook 某一条；
- 解码器拆成 3~4 个小函数 + 乱序跳转表，没有单一 hook 点；
- 表内混入 20%~30% **假条目**（随机乱码字符串），解码缓存按访问热度淘汰；
- 解码函数本身被 3.1 的函数簇机制保护。

### 3.5 反调试与反 hook（消除 W8）

启动时与运行中抽查（全部命中后走 Silent Corrupt，不报错）：

| 检测项 | 方法 |
|--------|------|
| 系统级 trace | `sys.gettrace() is not None`、`sys.monitoring` 回调探测（3.12+） |
| 外来栈帧 | `inspect.currentframe()` 回溯，统计非白名单文件名的帧 |
| builtins 被换 | 生成期记录 `id(type(exec))` 等指纹？不行（ASLR）——改为校验 `repr(type(marshal.loads)).count('built-in')` 与关键 dunder 行为探针（用一次性匿名函数验证语义） |
| gc 中的陌生追踪器 | `gc.get_objects()` 抽样统计自定义 trace 类 |
| 调试器模块 | `sys.modules` 中 `pdb`/`pydevd`/`ptvsd`/`debugpy` 探测 |

注意：检测逻辑本身拆散混入正常代码路径，不做集中式 `if debugger: exit()`。

### 3.6 资产保护（消除 W6/W10）

- **重命名**：资产改为 `a_<序号>`，映射表进加密载荷；
- **不落盘（优先方案）**：pygame 完全支持从内存加载——
  `pygame.image.load(io.BytesIO(data))`、`pygame.mixer.Sound(file=io.BytesIO(...))`；
  通过 `runtime._asset_path` 返回自定义内存对象实现"零落盘"；
  不支持内存加载的极端情况才退回"用时解密、用后即删"的临时文件；
- 每个资产独立密钥（HMAC 派生），解密时机跟随首次使用。

改动模块：`payload.py`、生成器 `_asset_path` 的内存挂钩。

### 3.7 载荷格式升级

```text
magic(4) | version(1) | flags(1) | segment_count(2)
per segment: [salt(16) | len(8) | hmac_tag(32) | ciphertext]
trailer: [loader_check(32) | total_hmac(32)]
```

- HMAC-SHA256 取代 CRC32（密钥防篡改）；
- 分段表支持 3.1 的多阶段结构；
- base85 → 改为分段嵌入多处（每段一个"看似普通"的字节串常量），不再有
  一眼可见的巨型密文块。

---

## 4. Tier 2：构建期原生编译 + 授权（强保护，可选）

### 4.1 Cython 编译关键层

- 把 **stage0/stage1 加载器 + 字符串表 + 解码器** 用 Cython 编译为 `.pyd`；
- 字节码级工具（pycdc 等）对原生扩展完全失效，只能上 IDA/Ghidra；
- 分发形态：`main.py`（纯 Python 壳）+ `core_<platform>.pyd`；
- 构建矩阵：Windows (MSVC) / macOS (clang) / Linux (gcc)，提供构建脚本；
- 退化路径：无编译器时自动回退 Tier 1 纯 Python。

### 4.2 Nuitka 单文件打包（文档级支持）

- `--onefile` 编译成原生可执行文件，C 层转换全部逻辑；
- 与 4.1 二选一或叠加；提供 `docs` 构建指引。

### 4.3 机器绑定 + Ed25519 许可证

```text
license {
  product_id, machine_fp (SHA256 of machine-id/MAC/CPU/OS),
  expires_at, features[], sig (Ed25519)
}
```

- `P3`（见 3.2）= `HMAC(license_payload, fp)` 参与主密钥派生：
  许可证错误 → 解密失败 → Silent Corrupt，**无需独立校验分支**（防 patch 掉校验）；
- 签名验证用纯 Python Ed25519（~400 行，无第三方依赖）或可选 `cryptography`；
- 离线验证，无网络依赖。

### 4.4 防差分（消除 W13）

- 默认禁用固定 seed（`--seed` 仅内部测试保留）；
- 垃圾代码块内容、数量、位置引入时间熵；
- 两次构建的公共子结构最小化。

---

## 5. Tier 3：企业级（远期可选）

| 项 | 说明 |
|----|------|
| 联网激活 | 激活服务器 challenge-response，许可证吊销列表 |
| 心跳上报 | 运行中低频上报指纹哈希，异常实例远程失效 |
| 崩溃遥测 | Silent Corrupt 事件的聚合分析（识别破解尝试模式） |
| 服务端逻辑 | 真正需要保密的核心算法下沉服务端，客户端只留壳 |

---

## 6. 实施计划

| 阶段 | 内容 | 验收 |
|------|------|------|
| P1 | 3.2 密钥分裂 + 自校验 + Silent Corrupt | patch 任一常量/加载器 → 垃圾崩溃；正常路径测试全绿 |
| P2 | 3.3 派发表 + 3.4 链式字符串表 | pycdc 反编译产物中无 `move/say` 等明文方法名 |
| P3 | 3.1 多阶段链式解密 + 函数簇懒加载 | hook 单次 exec 只能拿到单个簇 |
| P4 | 3.5 反调试 + 3.7 载荷格式 | settrace/pdb 命中后 Silent Corrupt；HMAC 防篡改生效 |
| P5 | 3.6 资产内存加载 + 重命名 | 运行全程无资产落盘 |
| P6 | 4.1 Cython 层 + 4.3 许可证 | Windows .pyd 构建通过；错误许可证 → 无法运行 |
| P7 | 4.4 防差分 + 文档 + 测试 | 两次构建差分无有效公共结构；106+ 测试全绿 |

每阶段独立可交付、可回退；P1–P5 为纯 Python 跨平台，P6 起按平台构建。

---

## 7. 测试策略

- **正确性**：混淆产物 headless 运行与明文版行为一致（变量快照对比）；
- **静态泄露扫描**：产物中不得出现 Scratch opcode、方法名、台词、类名；
- **反编译验证**：`marshal` dump + pycdc 流水线作为攻击模拟，断言产物不可读；
- **篡改验证**：byte 级翻转 payload / patch 加载器常量 → 断言 Silent Corrupt；
- **反调试验证**：子进程挂 `sys.settrace` 运行 → 断言行为异常且无明文报错；
- **性能**：混淆产物帧率与明文版差异 < 5%（Lazy 解密只在首调生效）。
