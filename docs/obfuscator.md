# SB3 -> 混淆 Python 单向转换

本工具把 Scratch 项目（`.sb3`）转换为**单文件、可执行、经过强混淆的 Python**。
“单向”只在**产品工作流**上成立：不提供反向转换入口；它**不是**密码学意义上
的不可逆。拿到运行时明文后，仍可通过 IR 重建器恢复出**语义级**的 SB3
（变量名/opcode/事件结构可还原，资产可另取；常量折叠会丢失部分表达式结构）。
结构级/字节级的完全还原不成立。

v2 强化版在 v1（常量折叠 + 字符串加密 + 载荷加密）之上新增：

- **属性派发表**：所有属性/方法访问改写为 `getattr(obj, 加密表引用)`，
  `co_names` 中不再出现 `move/say/broadcast` 等 Scratch 方法名；
- **类方法重命名**（黑名单保护 threading/os/pygame 同名方法）；
- **链式加密字符串表**：条目间哈希链关联，一次性展开解码；
- **函数簇懒加载**：顶层函数拆分为独立加密的簇，trampoline 首次调用才解密，
  hook 一次 `exec` 只能拿到单个簇；
- **密钥分裂**：主密钥 = SHA256(8 个散布的 64 位片段)，文件中不存在完整密钥；
- **分段 HMAC-SHA256**：每段独立 salt + 完整性标签，篡改任意字节即解密失败；
- **Silent Corrupt**：篡改/调试器/版本不符不报清晰错误，而是翻转密钥继续
  解密，让垃圾数据在远离检测点的地方自然崩溃；
- **反调试探针**：启动检测 `sys.gettrace`/`sys.monitoring`/调试器模块，
  运行中每 17 秒复查，命中后腐蚀字符串表；
- **虚拟资产文件系统**：内嵌资产不落盘，包装 `open`/`os.path.exists`/
  `pygame.image.load`/`pygame.mixer.Sound` 按需解密，资产重命名为匿名文件；
- **段密钥链式派生（v2.1）**：各段密钥由前一段明文摘要派生
  （K_root → 字符串表 → main → {簇, 资产}）；顺序解密不构成密钥壁垒，
  只消除“乱序/并行无脑解包”的实现；
- **类与 main 入末簇（v2.1）**：模块体 stage1 只剩 trampoline 与常量，
  hook 一次 `exec` 拿不到类骨架；
- **`_dec` 调用栈指纹（v2.1）**：解密入口校验调用方源文件，hook 注入式
  调用（如替换 `marshal.loads`）命中指纹后 Silent Corrupt；
- **资产内容重构（v2.1）**：SVG 规范化重序列化、PNG 插 tEXt、WAV 追加
  LIST/INFO、MP3 追加 ID3v1——语义等价但字节与原始文件不一致；
- **多态配方（v2.2/v2.4）**：v3.1 起载荷不压缩（移除可替换的解压原语），
  编码（b85/b64）、哈希族（6 种）、段密钥派生形式（**v2.4: 10 种**）、
  密钥流布局（**v2.4: 4 种**）、分段表形态与随机段标识（**长度随机**）——
  **不存在两个配方完全相同的产物**；v2.4 起所有字符串常量运行时由
  chr 码构造，依赖 `fromhex/getattr/属性名` 等表达式形状的静态解析器失效；
- **片段算术混合（v2.2/v2.4）**：8 个密钥片段中 1~3 个由其他片段经
  `(f_p*M+C) & 2^64-1` 或 `((f_p^C1)*M+C) & 2^64-1` 派生，文件中
  不存在全部字面量；
- **源码前缀自校验（v2.4）**：探针与密钥派生所在的加载器前缀参与哈希
  比对，patch 任一行即 Silent Corrupt（Tier 1）；
- **SCRATCH_OBF_DEBUG=1（v2.4）**：输出腐蚀诊断，区分工具自身故障与
  攻击腐蚀（发布模式保持静默）；
- **builtins 完整性探针（v2.2）**：`type(exec/compile/__import__/
  marshal.loads)` 与原生内建类型不符（如 Python 层 hook）即 Silent Corrupt；
- **字符串表 tuple 化（v2.2）**：命名空间中不出现大体积 `list[str]`
  结构特征；
- **Ed25519 许可证绑定（Tier 2，可选）**：许可证内容与机器指纹参与主
  密钥派生 `K' = H(K_root || H(payload‖sig‖fp))`——**指纹不进入许可证
  与产物**（0.13.4 起由开发者构建时 `--license-fp` 传入），机器不对即
  解密失败。**离线且未在授权机上插桩时**，无 fp 无法复算 K'；但在授权机
  上做一次运行时插桩/内存读取即可恢复该产物，许可证不是“防逆向”；
- **原生编译（Tier 2，可选）**：`--native` 把 loader 编译为 Cython 扩展
  （`main.py + core*.pyd`，已剥离调试信息），字节码级工具（marshal dump /
  pycdc / exec hook）失效、反编译成本显著提高；但**数据提取不依赖反编译**
  （压缩字符串表、片段/表材料、运行时内存都可能被提取），native 不等于加密。

> 重要：任何纯 Python 本地混淆都不是不可破解的加密。本工具的目标是显著提高
> 阅读、搜索、直接复用源码的成本，同时保证项目正常运行。确定要逆向的人仍然
> 可以通过调试器、hook `exec`、dump code object 等方式恢复部分逻辑。
> 完整威胁模型与后续路线见 [obfuscator-hardening.md](obfuscator-hardening.md)。

---

## 1. 快速开始

```bash
cd src

# 默认内嵌资产，输出单文件
python -m obfuscator ..\example\scpy_demo.sb3 ..\example\scpy_demo_obf.py

# 使用主转换器
python converter.py sb3obf ..\example\scpy_demo.sb3 ..\example\scpy_demo_obf.py

# 资产放外部目录
python -m obfuscator input.sb3 output.py --no-embed-assets

# 关闭常量折叠
python -m obfuscator input.sb3 output.py --no-fold

# 固定 AST 混淆随机种子（便于复现构建）
python -m obfuscator input.sb3 output.py --seed 123
```

运行：

```bash
python output.py --headless --frames 60 --no-audio
python output.py            # 窗口模式
```

---

## 2. 参数

| 参数 | 说明 |
|------|------|
| `input` | 输入 `.sb3` / `.json` |
| `output` | 输出 `.py`；默认 `<输入名>_obf.py` |
| `--no-embed-assets` | 资产不写入载荷，导出到 `<输出名>_assets/` |
| `--no-fold` | 关闭常量折叠与恒定条件简化 |
| `--seed N` | AST 混淆随机种子 |

Python API：

```python
from obfuscator import obfuscate_sb3

result = obfuscate_sb3(
    "game.sb3",
    "game_obf.py",
    embed_assets=True,
    fold=True,
    seed=123,
)
print(result.output, result.size, result.asset_count)
```

---

## 3. 转换流程

```text
SB3
 ├─ 解析为 IR
 ├─ 常量折叠 / 恒定条件简化
 ├─ 生成普通 Python
 ├─ 【第一层】源码级预混淆（first_pass.py）
 │   ├─ 剥离自定义装饰器（staticmethod/classmethod/property 白名单保留）
 │   ├─ AST 级恒定折叠：恒定分支消除、恒定返回合并、return 后死代码截断
 │   ├─ 恒定返回函数内联：调用点替换为常量并删除定义
 │   │   （名字被字符串/函数对象引用时自动跳过）
 │   ├─ 局部变量名混淆：作用域感知（闭包/global/nonlocal/class/lambda
 │   │   安全），运行时模板一并处理
 │   └─ 注入假类/假方法/假分支（与真实结构同形，随管线一起混淆）
 ├─ 【第二层】AST 混淆
 │   ├─ 删除 docstring 与注释
 │   ├─ 重命名模块级函数/类
 │   ├─ 重命名类方法（黑名单跳过 threading/os/pygame 同名）
 │   ├─ 属性访问 -> getattr/setattr/delattr + 加密字符串表
 │   ├─ 字符串常量 -> 链式加密表（尾部注入 Scratch 词汇语义诱饵）
 │   ├─ 注入垃圾函数与死分支
 │   ├─ 顶层 def -> 函数簇懒加载 trampoline
 │   └─ 抹平行号
 ├─ 编译为 stage1 code object + N 个簇 code object
 │   └─ 加密诱饵簇：与真簇同规格入表但永不调用（增加分析噪声，不保证不可识别）
 ├─ marshal -> 多态压缩/编码/HMAC 标签/密钥流异或
 └─ 写入极小加载器（密钥分裂 + 反调试 + Silent Corrupt）
```

运行时：

```text
加载器 -> 反调试探针 -> 密钥分裂重建 K_root
      -> 逐段 HMAC 校验（失败则静默翻钥）-> 解密字符串表
      -> 注入模块绑定与懒加载辅助 -> exec(stage1)
      -> 虚拟资产文件系统包装 -> 启动周期探针
      -> 调用混淆后的 main()（函数簇按需解密）
```

---

## 4. 常量折叠

折叠发生在 IR 层，使用运行时 `_sc_*` 函数，保证与 Scratch 语义一致。

示例：

| 原始表达式 | 折叠结果 |
|------------|----------|
| `1 + 2` | `3` |
| `join("a", 5)` | `"a5"` |
| `"ABC" == "abc"` | `true` |
| `length("hello")` | `5` |
| `round(2.5)` | `3` |
| `if 1 == 1:` | 只保留分支体 |
| `if 1 == 2:` | 删除整个分支 |
| `repeat 0` | 删除循环 |
| `wait until true` | 删除等待 |
| `repeat until true` | 删除循环 |

以下**不会**折叠：

- 涉及变量、列表、角色属性、计时器、随机数、扩展调用的表达式；
- 结果为 `NaN` / `Infinity` 的运算（保留运行时语义）；
- 超大字符串（避免生成巨型字面量）。

关闭折叠：

```bash
python -m obfuscator input.sb3 output.py --no-fold
```

---

## 5. 混淆内容

### 5.1 源码信息清除

- 删除所有注释与 docstring；
- 不保留原始项目名、转换器信息、调试报告；
- 不生成 SB3 元数据；
- 运行时窗口标题/日志中的 “Scratch 3.0” 标识替换为通用文本；
- 移除 `--trace` 选项，避免运行时打印原始脚本与自制积木名；
- code object 使用随机文件名，所有 AST 行号被抹平。

### 5.2 标识符重命名

模块级函数与类（包括运行时类、角色类、`main`、`_sc_*` 辅助函数）会改名为
随机标识符；**第一层预混淆（0.13.5 起）已先把所有局部变量名（含运行时
模板内部）改为随机名**——作用域感知改名，闭包/global/nonlocal/class
绑定安全，反射引用自动跳过。代码以 marshal 形式存在，普通阅读者看不到。

### 5.3 字符串加密

所有字符串常量（用户文本、积木参数、资源名、提示语等）被移入字符串表：

- 每条字符串用随机 16 字节密钥 XOR；
- 运行时惰性解码并缓存；
- 源码中不再出现原始文本，`grep` 搜索不到台词、变量名、opcode 等。

### 5.4 垃圾代码与诱饵

- 注入若干永不执行的随机函数与死分支，增加阅读与反编译噪音；
- 第一层注入与真实结构同形的**假类/假方法/假分支**，与真实代码一起
  被后续管线混淆拆簇，无法从形态区分；
- 加密载荷中混入**诱饵簇**：与真实函数簇同规格加密入表但永不调用，
  用于增加静态解包与人工分析噪声；它**可被**结构/调用图分析识别，
  不承诺“真假难辨”；
- 字符串表尾部注入 **Scratch 词汇语义诱饵**（假 opcode/假变量名/
  假台词）：静态搜索命中"情报"实为诱饵。

### 5.5 载荷加密

- 每个段独立 `salt` + 段密钥 + HMAC 完整性标签；
- **段密钥链式派生**：`key = KDF(前一段明文摘要, sid)`，链条为
  K_root → 字符串表 → main → {函数簇, 资产}；顺序解密不构成成本壁垒，
  只避免“无脑并行/乱序”这类实现；
- **随机段标识**：段名每次导出随机化，无固定锚点；
- **多态算法**：不压缩、密文编码（base64 / `binascii` C 级解码）、哈希族
  （sha256/sha384/sha512/sha3_256/sha3_512）、KDF 形式（HMAC
  双向 / 拼接双向）、密钥流布局与计数器编码（宽度/字节序/起点）逐次随机，
  加载器按同一配方生成；
- `K_root = H(64 字节片段 blob)`；派生素材只在生成端使用，运行端只出现
  一段编码文本，静态扫描不再有 8 个整数/派生公式锚点（v3.0）；
  Tier 1 源码仍可读出拼接顺序，只是混淆，不是“不可还原”（见 §8）；
- 校验失败 / 检测到调试器 / 内建函数被替换 / 解释器版本不符时**不报错**，
  而是翻转密钥字节，让垃圾数据在离检测点很远的解压阶段自然崩溃
  （Silent Corrupt）；
- 分段表以**单一二进制 blob**嵌入（v3.0），不再生成 `{sid: (...) }`
  字典或行列表；静态 `literal_eval`/`gc` 行扫描失去锚点。

### 5.6 函数簇懒加载

- 顶层 `def`（`_sc_*` 辅助函数、扩展处理器、`main` 等）按每簇最多 6 个拆分；
- **所有 ClassDef 与 main 移入同一末簇**：stage1 模块体只剩 trampoline 与
  常量，一次 `exec` 拿不到类骨架；
- 原位置替换为 trampoline：首次调用时经加载器解密该簇并在模块命名空间
  重新绑定真实函数；
- 效果：hook 一次 `exec`/`marshal.loads` 只能拿到当前簇，必须逐簇触发才能
  拼出全貌。

### 5.7 资产

默认 `embed_assets=True`：

- 资产重命名为 `a_<随机>.<扩展名>`，抹除 md5 身份；
- **内容重构**：SVG 经 XML 规范化重序列化、PNG 插入随机 tEXt 块、WAV
  追加 LIST/INFO 块、MP3 追加 ID3v1 标签——渲染结果不变但字节与原始文件
  不一致，无法用原文件比对识别；
- 每个资产独立加密段，**首次使用时才解密**；
- 运行时通过虚拟文件系统包装 `open`/`os.path.exists`/
  `pygame.image.load`/`pygame.mixer.Sound`，**全程不落盘**；
- 输出目录只保留一个 `.py`。

`--no-embed-assets`：

- 资产写入 `<输出名>_assets/`（保留原始 md5 名称，便于管理）；
- 加载器把 `ASSETS_DIR` 指向该目录，不做运行时包装。

---

## Tier 2：许可证绑定与原生编译（可选）

Tier 1 是纯 Python，密钥必然随文件走。Tier 2 提供两个量级提升
（可单独或组合使用）：

### Ed25519 许可证绑定

产物只能在**签发机器**上运行；许可证内容与机器指纹参与主密钥派生，
伪造/盗用/篡改许可证都导致解密失败（Silent Corrupt，无校验分支可 patch）。

```bash
cd src

# 1. 生成签发密钥对（私钥自留，切勿提交仓库）
python -m obfuscator.license keygen --out-dir license_keys/

# 2. 为目标机器签发许可证（默认绑定当前机器，--days 有效期）
python -m obfuscator.license issue --priv license_keys/private.key \
    --product mygame --days 365 --out license.dat

# 3. 构建绑定的产物
python -m obfuscator game.sb3 game_obf.py \
    --license-pubkey "$(cat license_keys/public.key)" \
    --license-file license.dat
```

- 错误机器 / 篡改许可证 → 产物 Silent Corrupt；
- 许可证与产物绑定后，换证/换机器需重新导出。

### 原生编译

```bash
# 需要 Cython 与 C 编译器（Windows: gcc/MSVC；Linux/mac: 默认编译器）
pip install cython
python -m obfuscator game.sb3 game_native/ --native

# 可与许可证叠加
python -m obfuscator game.sb3 game_native/ --native \
    --license-pubkey "$(cat license_keys/public.key)" \
    --license-file license.dat
```

产物为 `main.py`（壳）+ `core.cpXXX-xxx.pyd`（原生扩展）：解密、许可证
绑定、探针、exec 全在原生代码内，marshal dump / pycdc / exec hook 等
字节码级工具对原生扩展失效；反编译需要 IDA/Ghidra 级工具且有明显摩擦。
但**数据提取不需要反编译**，反编译摩擦不等于保密。

---

## 6. 兼容性

| 项 | 说明 |
|----|------|
| Python 版本 | **必须与生成时相同的 `major.minor`**（marshal code object 与版本相关） |
| 依赖 | pygame（与普通生成脚本相同） |
| 平台 | 跨平台，只要 Python 版本与 pygame 满足 |
| 资源 | 内嵌模式运行时会写临时目录；外部模式输出 `_assets` |
| 调试 | 混淆版移除了 `--trace`；保留 `--headless/--frames/--seconds/--no-audio` 等 |
| 反向转换 | 不支持；这是一次性单向输出 |

加载器会检查解释器版本；版本不匹配时走 Silent Corrupt 路径（无明文提示）。

---

## 7. 性能

- 常量折叠会减少运行时表达式数量；
- 字符串表在启动时一次性解码，之后为 O(1) 查表；
- 属性访问经 `getattr` + 查表，热点路径略慢于直接属性（实测整体可玩性不受影响）；
- 函数簇懒加载只在每个簇首次调用时付一次解密开销；
- 内嵌资产按需解密，无整包启动开销、无落盘；
- 混淆不引入逐语句解释器，不会显著拖慢游戏循环。

---

## 8. 安全边界（如实）

**能降低的成本**：

- 直接打开 `.py` 阅读源码（加载器逻辑混淆 + 材料结构化混淆）；
- 文本搜索变量名、台词、opcode、函数名（进入加密表）；
- `hook 一次 exec/marshal -> dump -> pycdc` 的最低成本路径；
- 未适配的通用解包脚本（多态配方 + 随机段标识 + 结构化 blob）；
- 未适配的运行时 dump（锁内命名空间 + `sys.exit`/`hashlib` 插桩检测 +
  退出前擦除）；
- 篡改文件后直接运行（自校验 + Silent Corrupt）。

**不能防御（明确不承诺）**：

- **静态离线还原**：纯 Python 产物必然携带全部解密要素；无许可证时，
  适配后的 AST/数据提取脚本仍可恢复载荷。
- **运行时内存读取**：C 级 hook、`gc`/`__closure__` 扫描、进程转储都能
  取得运行中必须存在的明文；native 不改变这一点。
- **语义级 SB3 重建**：项目在运行时必须还原为可执行对象；替换 `self`
  的 Recorder、事件记录、IR 重建可恢复语义级项目（v3.0 增加了注册守卫
  与 trace/profile 检测，但这是成本，不是不可行）。
- **授权机插桩**：许可证绑定保证非签发机离线不可解；但在授权机上做一次
  插桩/内存读取，即可恢复该产物并获得本机指纹，后续可离线复算。
- **反编译摩擦**：native 的 271KB 单体 init 让 Ghidra 超时/OOM，但攻击
  数据提取不需要反编译。

Tier 2（native + 许可证）的真实定位是：提高反编译与批量复制成本、守住
离线/错机两面；**不是**“防住有决心的逆向”。若要内容级保密，需要外部
密钥或服务端授权（当前不做 Tier 3）。详见
[obfuscator-hardening.md](obfuscator-hardening.md)。

---

## 9. 验证

项目测试包含：

```bash
python tests/test_all.py
```

混淆器测试覆盖：

- 常量折叠与恒定条件简化；
- 内嵌资产导出并可运行（源码无 import pygame/marshal/zlib 明文）；
- **字节码名字扫描**：dump 全部 code object 的 `co_names`/`co_varnames`，
  断言无积木 opcode、无原始类名/函数名；
- **防篡改**：翻转密文一个字符 → 非零退出且无明文校验提示；
- **反调试**：挂 `sys.settrace` → Silent Corrupt；不挂时正常；
- 外部资产导出并可运行。

手工验证：

```bash
python -m obfuscator ..\example\scpy_demo.sb3 ..\example\scpy_demo_obf.py --seed 1
python ..\example\scpy_demo_obf.py --headless --frames 60 --no-audio
```
