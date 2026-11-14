# Scratch 输入与参数语义说明

本文说明 **Scratch 3.0 在收到空输入、缺失参数、非法输入时到底怎么处理**，
以及本转换器生成的 Python 运行时（文件顶部的 `_sc_*` 函数）如何复刻这些行为。

适用场景：

- 阅读 / 修改 `src/python_generator.py` 中的运行时辅助函数
- 判断某个转换结果“为什么是空”“为什么变成 0”“为什么没有报错”
- 给本转换器提交与语义相关的测试

不涉及：Scratch 编辑器操作、积木界面布局、Python 语法教程。

---

## 1. 先分清四种“空”

| 现象 | Scratch 的实际值 | 说明 |
|------|------------------|------|
| 输入框被清空 | 空字符串 `""` | 输入框本身仍然存在，值是 `""` |
| 调用自制积木时某个参数没填 | `""`（取自 `argumentdefaults`） | 见第 7 节，**不是 0** |
| 参数名在当前调用栈里不存在 | `0` | `argument_reporter_string_number` 的兜底值 |
| 数字积木收到 `""` 或 `"abc"` | `0` | 只发生在“需要数字”的积木内部，原值仍然是空 |

关键结论：**空就是空**。空字符串不会一出现就变成 0，
只有当它进入 `+ - × ÷ / 比较 / 重复次数` 这类需要数字的积木时，才会被强制转成 0。

---

## 2. 三种基础类型转换

来源：`scratch-vm/src/util/cast.js`。

### 2.1 `Cast.toNumber`：转数字

规则：`value` 本身是数字则直接使用（`NaN` → `0`），否则执行 JS 的 `Number(value)`，
结果仍是 `NaN` 时返回 `0`。

| 输入 | 结果 | 原因 |
|------|------|------|
| `""` / `"   "` | `0` | `Number("") === 0` |
| `"12"` / `"1.5"` / `"1e3"` | `12` / `1.5` / `1000` | 合法数字 |
| `"12px"` | `0` | `Number` 得到 `NaN` |
| `"0x10"` / `"0b11"` / `"0o10"` | `16` / `3` / `8` | JS 支持进制前缀 |
| `"+0x10"` | `0` | 带符号的进制前缀不是合法数字 |
| `"1_000"` | `0` | JS 不接受下划线分隔 |
| `"Infinity"` / `"+Infinity"` | `Infinity` | 合法 |
| `"infinity"` | `0` | 大小写敏感，`Number` 得到 `NaN` |
| `"NaN"` | `0` | `NaN` 最终按 0 处理 |
| `true` / `false` | `1` / `0` | JS 布尔转数字 |
| `NaN`（已经是数字） | `0` | 注释原文：`0 + NaN -> 0` |

### 2.2 `Cast.toBoolean`：转布尔

| 输入 | 结果 |
|------|------|
| `""`、`"0"`、`"false"` / `"FALSE"`（忽略大小写） | `false` |
| 其他任何字符串（包括 `" "`、`"0.0"`） | `true` |
| 数字 `0`、`NaN` | `false` |
| 其他数字、其他值 | `true` |

### 2.3 `Cast.toString`：转字符串

实际就是 JS 的 `String(value)`：

| 输入 | 结果 |
|------|------|
| `3.0` / `3` | `"3"` |
| `1.5` | `"1.5"` |
| `NaN` | `"NaN"` |
| `Infinity` / `-Infinity` | `"Infinity"` / `"-Infinity"` |
| `true` / `false` | `"true"` / `"false"` |
| `null` | `"null"` |

---

## 3. 比较规则（`Cast.compare`）

比较积木（`=`、`<`、`>`）不直接走 `toNumber`，而是：

1. 用 JS `Number()` 转两侧；
2. 如果某侧数值为 0、但原值是空或纯空白，把该侧改成 `NaN`；
3. 任一侧是 `NaN` → 两侧转成 **小写字符串** 比较；
4. 否则按数字比较（`Infinity` 与 `Infinity` 视为相等）。

| 表达式 | 结果 | 原因 |
|--------|------|------|
| `"ABC" = "abc"` | 真 | 字符串比较忽略大小写 |
| `"123" = 123` | 真 | 双方都能转数字 |
| `"1.0" = 1` | 真 | 数字比较 |
| `"" = 0` | 假 | `""` 被判为 `NaN`，走字符串比较 |
| `"" = " "` | 假 | 两者都是空白，按字符串比较 |
| `"36" < "100"` | 真 | 都能转数字，按数值比较 |
| `"abc" < "abd"` | 真 | 字符串比较 |
| `"Infinity" = "Infinity"` | 真 | 特殊值相等 |

---

## 4. 运算积木

| 积木 | 规则 | 边界值 |
|------|------|--------|
| `+` `-` `×` `/` | 两个输入都先 `toNumber` | `1/0 = Infinity`，`-1/0 = -Infinity`，`0/0 = NaN` |
| `mod` | 向下取整余数（结果与除数同号） | `x mod 0 = NaN` |
| `round` | `floor(x + 0.5)` | `round(2.5) = 3`，`round(-2.5) = -2` |
| `random(a, b)` | 先转数字；`a > b` 自动交换；两边都“像整数”时返回整数，否则返回浮点 | 非数字一律按 0 处理 |
| 幂运算 | **Scratch 没有 `**` 积木** | 本转换器的近似方案见 README「通用模式」 |

`mathop`（数学函数积木）的边界：

| 函数 | 边界结果 |
|------|----------|
| `sqrt(-1)` | `NaN` |
| `ln(0)` / `log(0)` | `-Infinity` |
| `ln(-1)` / `log(-1)` | `NaN` |
| `tan(90)` / `tan(-90)` / `tan(270)` | `Infinity` / `-Infinity` / `-Infinity` |
| `sin` / `cos` | 角度制，结果保留 10 位小数 |
| `floor` / `ceiling` | 对 `±Infinity`、`NaN` 原样返回 |

---

## 5. 字符串积木

| 积木 | 规则 | 示例 |
|------|------|------|
| `连接 (a) (b)` | 两侧 `toString` 后拼接 | `join("", 5) = "5"` |
| `(n) 的第 (i) 个字符` | `i = toNumber(i) - 1`；`i < 0` 或 `i >= 长度` 返回 `""`；小数按 `charAt` 截断 | `letter(1, "abc") = "a"`，`letter(0, "abc") = ""` |
| `(字符串) 的长度` | 先 `toString` 再取长度 | `length(123) = 3` |
| `(字符串) 包含 (子串)` | 两侧转小写后用 `includes` | `"HELLO" 包含 "ell"` 为真 |

---

## 6. 列表积木

### 6.1 下标

- 从 **1** 开始，不是 0。
- 数字下标先 `floor(toNumber(i))`。
- 特殊字符串：`last`（最后一项）、`random` / `any`（随机一项）、`all`（仅“删除”积木接受）。
- 非法下标（0、负数、超过长度、`all` 用于非删除积木）：
  - 读取（`第 i 项`）→ `""`
  - 写入 / 插入 / 删除 → 什么都不做
  - 空列表上的 `last` / `random` → `""`

### 6.2 其他列表运算

| 积木 | 规则 |
|------|------|
| `(列表) 包含 (值)` | 对每一项用 `Cast.compare`，数值优先、字符串忽略大小写 |
| `(值) 在 (列表) 中的位置` | 同上，返回第一个匹配的 1 起始下标；没有返回 0 |
| `(列表) 的内容` | 所有项都是单字符字符串时直接拼接，否则用空格连接 |
| 列表长度上限 | 原版 Scratch 为 200000 项；生成运行时的“插入”积木做了同样的上限检查 |

---

## 7. 自制积木的参数（本次修正的重点）

### 7.1 数据从哪来

自制积木定义带有 mutation 字段（Scratch Wiki 的说明）：

| 字段 | 含义 |
|------|------|
| `proccode` | 积木文本，如 `add %s %s` |
| `argumentids` | 参数 ID 数组 |
| `argumentnames` | 参数名数组 |
| `argumentdefaults` | 参数默认值数组：**字符串/数字参数是空字符串，布尔参数是 `false`** |

调用积木 `procedures_call` 执行时（`scratch3_procedures.js`）：

```text
对每个参数 ID：
    如果调用块里有这个输入 → 用输入值
    否则                   → 用 definition 的 argumentdefaults
```

所以：**没填的参数默认就是空，不是 0**。
例如定义 `add %s %s`，调用时只填第一个参数，第二个参数的值是 `""`；
只有把它放进 `+` 积木时才会被 `toNumber` 变成 0。

### 7.2 一个容易混淆的特例

`argument_reporter_string_number`（参数积木）在当前调用栈里
**找不到这个参数名** 时返回 `0`，而不是空字符串。

这通常只发生在参数积木被拖到另一个自制积木里、参数名不匹配的时候。
参数名存在但值为空时，仍然返回 `""`。

### 7.3 本转换器的对应行为

| 场景 | 原版 Scratch | 本转换器 |
|------|--------------|----------|
| 新建自制积木定义 | 默认值 `""` / `false` | `scratch_writer` 写入 `""` / `false` |
| DSL Python 调用少传参数 | 参数为空 | `python_parser` 补 `[1, [10, ""]]` |
| sb3 调用块缺少该输入 | 取 `argumentdefaults` | `scratch_parser` 读成 `""` |
| 生成 Python 方法签名 | — | 取 `argumentdefaults`，缺失时用 `''`（布尔 `False`） |
| 空参数参与加法 | 按 0 计算 | `_sc_add('', x)` 结果为 `x` |
| 空参数用于说话/连接 | 空文本 | `_sc_join('', x)` 结果为 `str(x)` |

> 旧版本把“没填的参数”补成 `0`，导致 `say(参数)` 会说出 `0`。
> 现在已按原版行为改为空字符串。

---

## 8. 生成运行时函数对照

生成脚本顶部的辅助函数与 Scratch 行为的对应关系：

| 生成函数 | 复刻的行为 |
|----------|------------|
| `_sc_num(v)` | `Cast.toNumber`：空/非数字/NaN → 0，支持 `Infinity`、进制前缀 |
| `_sc_str(v)` | `Cast.toString`：数字去掉多余小数、`NaN`/`Infinity`/布尔按 JS 规则显示 |
| `_sc_bool(v)` | `Cast.toBoolean`：`""`、`"0"`、`"false"` 为假 |
| `_sc_compare(a, b)` | `Cast.compare`：数值优先，空白视为 `NaN`，否则忽略大小写比较 |
| `_sc_eq` / `_sc_lt` / `_sc_gt` | 基于 `_sc_compare` 的三个比较积木 |
| `_sc_add` `_sc_sub` `_sc_mul` `_sc_div` | 四则运算，先 `toNumber` |
| `_sc_mod` | 向下取整余数，除 0 得 `NaN` |
| `_sc_round` | `floor(x + 0.5)` |
| `_sc_mathop(op, v)` | `abs/floor/ceiling/sqrt/sin/cos/tan/asin/acos/atan/ln/log/e^/10^` |
| `_sc_random(a, b)` | 交换上下界、整数/浮点结果判定 |
| `_sc_join(a, b)` | `toString` 后拼接 |
| `_sc_letter_of(i, s)` | 减 1 后按未取整下标判越界，再取字符 |
| `_sc_length(s)` | `toString` 后的长度 |
| `_sc_contains(s, part)` | 忽略大小写的子串判断 |
| `_sc_item_of(list, i)` | 1 起始、`last/random/any`、越界返回 `""` |
| `_sc_list_delete/insert/replace` | 1 起始、越界忽略、`all` 仅删除 |
| `_sc_list_contains` / `_sc_list_item_number` | 用 `_sc_compare` 比较 |
| `_sc_list_contents` | 单字符全拼接，否则空格连接 |
| `_sc_repeat_count` | `round` 后取非负整数，`NaN/Infinity` → 0 |
| `_sc_wait_time` | 非负秒数，非有限值 → 0 |
| `_sc_clamp_effect` | 颜色 0–200、透明度 0–100、亮度 -100–100 |

---

## 9. 已知差异

这些地方本转换器有意或暂时无法与 Scratch 完全一致：

1. **Unicode 长度**：JS 字符串按 UTF-16 码元计数，Python 按码点计数。
   emoji 等增补平面字符在 Scratch 里长度是 2，在生成的 Python 里是 1，
   会影响 `length of` / `letter of`。
2. **数值精度**：Scratch 全部使用 IEEE 双精度；生成的 Python 中，变量可能保留
   Python 的任意精度整数。超大整数在比较时会转成 `±Infinity`，
   但直接参与运算时仍是精确整数。
3. **浮点显示**：`_sc_str` 尽量贴近 JS `Number#toString`，极端指数区间可能有细微差异。
4. **`all` 下标**：只用于删除列表项，读取时按非法下标返回 `""`。
5. **列表项类型**：Scratch 的列表项本质是值；在 Python 侧把列表赋给另一个名字
   会得到同一对象，需要显式复制（通用模式的 `alias = nums` 已做逐项复制）。

---

## 10. 参考与验证

原始实现（阅读时间：2026-11）：

- [scratch-vm `src/util/cast.js`](https://github.com/scratchfoundation/scratch-vm/blob/develop/src/util/cast.js)
- [scratch-vm `src/blocks/scratch3_procedures.js`](https://github.com/scratchfoundation/scratch-vm/blob/develop/src/blocks/scratch3_procedures.js)
- [scratch-vm `src/blocks/scratch3_operators.js`](https://github.com/scratchfoundation/scratch-vm/blob/develop/src/blocks/scratch3_operators.js)
- [Scratch Wiki: Scratch File Format (3.0)](https://en.scratch-wiki.info/wiki/Scratch_File_Format_(3.0))

对应的测试：

| 测试 | 覆盖内容 |
|------|----------|
| 测试 10 | 自制积木往返、参数默认值 |
| 测试 19 | `_sc_*` 类型转换、比较、数学函数、列表边界 |
| 测试 20 | 调用少传参数时为 `""`，生成签名默认值为 `''` |
| 测试 21 | 显式空字符串参数保持 `""` |
| 测试 38 | 列表越界读取返回 `""` |

运行全部测试：

```bash
python tests/test_all.py
```
