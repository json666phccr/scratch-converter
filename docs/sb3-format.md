# SB3 文件结构详解

本文描述 Scratch 3.0 项目文件（`.sb3`）的物理结构与 `project.json` 的完整数据模型，
作为 `scratch_vm/loader.py`、`scratch_vm/module.py` 以及解析器的实现依据。

配套文档：

- [scratch-vm-execution.md](scratch-vm-execution.md)：拿到数据之后如何执行
- [scratch-vm-design.md](scratch-vm-design.md)：本项目虚拟机的实现设计

---

## 1. 容器格式

`.sb3` 本质上是一个 **ZIP 压缩包**（不加密、不要求特定压缩等级），典型内容：

```text
project.sb3
├── project.json                 # 唯一的必需文件，UTF-8 JSON
├── cd21514d0531fdffb22204e0ec5ed84a.svg   # 舞台背景（示例）
├── bcf454acf82e4504149f7ffe07081dbc.svg   # 角色造型
├── 83a9787d4cb6f3b7632b4ddfebf74367.wav   # 声音
└── ...
```

规则：

| 规则 | 说明 |
|------|------|
| `project.json` 位置 | ZIP 根目录；少数工具会放在子目录，加载器应扫描所有 `*.json` 兜底 |
| 资产命名 | 文件名 = `md5ext`，即 `资源MD5.扩展名`，例如 `bcf454acf82e4504149f7ffe07081dbc.svg` |
| 资产扩展名 | `svg` / `png` / `jpg` / `jpeg` / `wav` / `mp3`，与 `dataFormat` 一致 |
| 资产引用 | `target.costumes[].md5ext`、`target.sounds[].md5ext` 直接对应 ZIP 内的文件名 |
| 缺失资产 | 允许缺失；运行时必须降级（占位图 / 静音），不能因此加载失败 |

加载器解压时只取**文件名部分**（`os.path.basename`），避免 ZIP 内恶意相对路径
（`../`）写出到目标目录之外。

---

## 2. `project.json` 顶层结构

```json
{
  "targets": [ ... ],
  "monitors": [ ... ],
  "extensions": [ "pen", "music" ],
  "meta": {
    "semver": "3.0.0",
    "vm": "0.2.0",
    "agent": "Mozilla/5.0 ..."
  },
  "comments": { ... }
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `targets` | `array` | 是 | 舞台 + 所有角色，**顺序即渲染层级**（舞台必须 `isStage=true`，通常第一个） |
| `monitors` | `array` | 否 | 舞台上显示的变量/列表监视器 |
| `extensions` | `string[]` | 否 | 项目用到的扩展 ID，如 `pen`、`music`、`text2speech` |
| `meta` | `object` | 否 | 生成该文件的 VM 版本信息，仅用于展示/兼容判断 |
| `comments` | `object` | 否 | 工作区注释（部分工具放在 target 内部，见 §9） |

> TurboWarp 的「高级选项」不在此处，而是藏在某条注释文本里的
> `// _twconfig_ {...}` JSON，见 §9。

---

## 3. target（舞台 / 角色）

每个 target 的公共结构：

```json
{
  "isStage": false,
  "name": "Cat",
  "variables": { "varId": ["分数", 0] },
  "lists": { "listId": ["记录", ["a", "b"]] },
  "broadcasts": { "bcId": "开始游戏" },
  "blocks": { "blockId": { ... } },
  "comments": { "commentId": { ... } },
  "currentCostume": 0,
  "costumes": [
    {
      "name": "costume1",
      "assetId": "bcf454acf82e4504149f7ffe07081dbc",
      "md5ext": "bcf454acf82e4504149f7ffe07081dbc.svg",
      "dataFormat": "svg",
      "rotationCenterX": 48,
      "rotationCenterY": 50
    }
  ],
  "sounds": [
    {
      "name": "Meow",
      "assetId": "83a9787d4cb6f3b7632b4ddfebf74367",
      "md5ext": "83a9787d4cb6f3b7632b4ddfebf74367.wav",
      "dataFormat": "wav",
      "rate": 44100,
      "sampleCount": 1024
    }
  ],
  "volume": 100,
  "layerOrder": 1
}
```

### 3.1 舞台专有字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `isStage` | `true` | 必须为 true |
| `tempo` | `number` | 音乐扩展的速度（BPM），默认 60 |
| `videoTransparency` | `number` | 视频透明度，默认 50 |
| `videoState` | `string` | `on` / `off` / `on-flipped` |
| `textToSpeechLanguage` | `string \| null` | 朗读语言 |
| `currentCostume` | `number` | 当前背景序号（0 起始） |

舞台的 `variables` / `lists` 就是 **全局变量 / 全局列表**，所有角色共享。

### 3.2 角色专有字段

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `x` / `y` | `number` | 0 | 舞台坐标，中心为 (0,0)，范围约 ±240 / ±180 |
| `direction` | `number` | 90 | 0=上，90=右，180=下，-90=左 |
| `visible` | `boolean` | true | 是否显示 |
| `size` | `number` | 100 | 缩放百分比 |
| `draggable` | `boolean` | false | 是否可用鼠标拖动 |
| `rotationStyle` | `string` | `"all around"` | `all around` / `left-right` / `don't rotate` |
| `layerOrder` | `number` | 1 | 层级；越大越靠前。舞台固定为 0 |

### 3.3 变量与列表的存储格式

```json
"variables": {
  "7f3a...": ["我的变量", 42]
},
"lists": {
  "9b21...": ["我的列表", ["苹果", "香蕉"]]
}
```

- 键是**变量 ID**（随机字符串），不是变量名。
- 值固定为二元数组 `[name, value]`，列表的 `value` 是数组。
- 同一个项目里，舞台的变量对所有角色可见；角色也可以定义同名局部变量，
  二者通过 **变量 ID** 区分。VM 的读写积木保存的是 ID，因此实现必须以 ID 为准。
- 变量值可能是 number / string / boolean，保留原始类型，除非积木内部做强制转换。
- 列表值通常是字符串数组，但也可能混入数字/布尔（导入工具生成）。

---

## 4. `blocks`：积木图

```json
"blocks": {
  "blockId": {
    "opcode": "motion_movesteps",
    "next": "nextBlockId | null",
    "parent": "parentBlockId | null",
    "inputs": { ... },
    "fields": { ... },
    "shadow": false,
    "topLevel": false,
    "x": 0,
    "y": 0,
    "mutation": { ... }
  }
}
```

| 字段 | 说明 |
|------|------|
| `opcode` | 积木操作码，决定积木种类，如 `motion_movesteps`、`control_repeat` |
| `next` | 同一堆栈里的下一个积木 ID；`null` 或缺失表示堆栈结束 |
| `parent` | 父积木 ID（输入槽或堆栈的上一个块）；顶层块无 parent |
| `inputs` | 输入槽，值可能是字面量、积木引用或变量/列表引用 |
| `fields` | 下拉菜单、变量字段等**非可插拔**参数 |
| `shadow` | 是否为影子块（菜单占位、字面量占位），影子块一般不参与执行 |
| `topLevel` | 是否工作区顶层积木（帽子块或孤立积木） |
| `x` / `y` | 工作区坐标，仅 `topLevel` 有意义 |
| `mutation` | 自制积木的参数声明（proccode / argumentids / ...） |

`blocks` 是一个**扁平字典**，堆栈、嵌套、输入全部通过 ID 引用，形成一张有向图：

```text
hat(next=A) ──next──▶ A(next=B) ──next──▶ B(next=null)
                         │
                         └─inputs.SUBSTACK──▶ C(next=D) ...
```

解析注意事项：

1. **必须防环**：手工编辑或损坏的文件可能出现 `next`/`parent` 成环，遍历要带 `seen` 集合。
2. **影子块可以被覆盖**：输入槽里可能同时有影子块和真实积木，真实积木优先。
3. **同一种输入有两种形态**：旧版把 block id 直接写成字符串，新版写成数组，见 §5。
4. **`parent` 不可靠**：部分生成器不写 `parent`，找顶层块应以 `topLevel` + 无 `parent` 为准。

---

## 5. `inputs` 编码

`inputs` 的键是输入槽名称，值描述“这个槽里有什么”。常见形态：

### 5.1 数组形态（官方）

```json
"inputs": {
  "STEPS": [1, [4, "10"]],
  "SUBSTACK": [2, "blockId"],
  "CONDITION": [2, "blockId"],
  "MESSAGE": [1, [11, "开始", "bcId"]]
}
```

数组第一个元素是 **shadow 标志**：

| 标志 | 含义 |
|------|------|
| `1` | 只有影子（字面量/菜单），没有真实积木 |
| `2` | 槽里是真实积木（block id），影子被覆盖 |
| `3` | 真实积木 + 影子同时存在（少见，编辑器内部状态） |

第二个元素可能是：

| 形态 | 含义 |
|------|------|
| `[4, "10"]` | 数字字面量，`4` = math_number |
| `[5, "hello"]` | 文本字面量，`5` = text |
| `[6, ...]` | 颜色字面量（颜色扩展/画笔） |
| `[7, ...]` | 角度字面量 |
| `[8, "name", "id"]` | 广播菜单项，`8` = broadcast |
| `[9, "name", "id"]` | 变量引用，`9` = variable |
| `[10, "name", "id"]` | 列表引用，`10` = list |
| `[11, "name", "id"]` | 广播引用（`broadcast_menu`） |
| `[12, "name"]` | 变量名文本（少见） |
| `[13, "name", "id"]` | 列表名文本（少见） |
| `"blockId"` | 直接引用一个积木（旧格式） |
| `[12, "blockId"]` | 引用一个积木（部分工具） |

### 5.2 字符串形态（旧格式）

```json
"inputs": {
  "STEPS": "blockIdOrLiteral"
}
```

解析器必须两种都接受。本项目 `scratch_parser.parse_input` / `_parse_input_value`
已经做了完整兼容。

### 5.3 子堆栈

`SUBSTACK`（if/repeat/forever）、`SUBSTACK2`（else）指向一条积木链的**第一个块**，
通过该块的 `next` 链展开。解析后应把链拆成列表并断开 `next`，避免写回时重复。

---

## 6. `fields` 编码

```json
"fields": {
  "KEY_OPTION": ["space", null],
  "VARIABLE": ["分数", "varId"],
  "LIST": ["记录", "listId"],
  "OPERATOR": ["+", null],
  "COSTUME": ["costume1", null],
  "CURRENTMENU": ["YEAR", null]
}
```

- 值固定为数组：`[显示值, id?]`；第二项通常为 `null`，变量/列表/广播字段则是 ID。
- 字段不是可插拔的：不能放积木，只能选菜单项。
- 扩展积木的字段命名由扩展自己决定，未识别时按字符串保留即可。

---

## 7. 自制积木 `mutation`

### 7.1 定义块（`procedures_definition`）

```json
{
  "opcode": "procedures_definition",
  "inputs": { "custom_block": [1, "prototypeId"] },
  "next": "bodyFirstBlockId"
}
```

定义块的 `inputs.custom_block` 指向 **原型块** `procedures_prototype`：

```json
"prototypeId": {
  "opcode": "procedures_prototype",
  "inputs": {
    "argId1": [1, [4, ""]],
    "argId2": [1, [4, ""]]
  },
  "mutation": {
    "tagName": "mutation",
    "children": [],
    "proccode": "add %s %s",
    "argumentids": "[\"argId1\",\"argId2\"]",
    "argumentnames": "[\"a\",\"b\"]",
    "argumentdefaults": "[\"\",\"\"]",
    "warp": "false"
  },
  "shadow": true
}
```

要点：

| 字段 | 说明 |
|------|------|
| `proccode` | 积木文本 + 参数占位符：`%s` 字符串/数字，`%b` 布尔，`%n` 数字 |
| `argumentids` | JSON **字符串**（注意是字符串化的数组），参数 ID 顺序 |
| `argumentnames` | JSON 字符串，参数显示名，可与 ID 不同 |
| `argumentdefaults` | JSON 字符串，未填参数时的默认值；字符串参数为 `""`，布尔为 `false` |
| `warp` | `"true"` 表示「运行时不刷新屏幕」 |

### 7.2 调用块（`procedures_call`）

```json
{
  "opcode": "procedures_call",
  "inputs": { "argId1": [1, [10, "5"]] },
  "mutation": {
    "proccode": "add %s %s",
    "argumentids": "[\"argId1\",\"argId2\"]",
    "warp": "false"
  }
}
```

调用块用 **argId → 输入值** 匹配参数；缺失的输入取定义块的 `argumentdefaults`。

### 7.3 TurboWarp 返回值（`procedures_return`）

TurboWarp 扩展支持自制积木带返回值：

```json
{ "opcode": "procedures_return", "inputs": { "value": [1, [4, "0"]] } }
```

执行 `return` 立即结束当前自制积木，并把值交给调用处。
定义块需要被当作 reporter 使用时，调用可能出现在 `inputs` 中而不是堆栈里。

---

## 8. `monitors`：舞台监视器

```json
{
  "id": "varId",
  "mode": "default",
  "opcode": "data_variable",
  "params": { "VARIABLE": "分数" },
  "spriteName": null,
  "value": 0,
  "width": 120,
  "height": 20,
  "x": 5,
  "y": 5,
  "visible": true,
  "sliderMin": 0,
  "sliderMax": 100,
  "isDiscrete": true
}
```

| 字段 | 说明 |
|------|------|
| `id` | 变量/列表 ID；舞台监视器与 target 内的 ID 对应 |
| `opcode` | `data_variable` / `data_listcontents` |
| `params` | 变量名 / 列表名（注意存的是**名字**，不是 ID） |
| `spriteName` | `null` 表示舞台全局；否则为角色局部变量 |
| `mode` | `default` / `large` / `slider` / `list` |
| `value` | 上次保存的值，仅用于恢复显示 |
| `visible` | 是否显示 |
| `x` / `y` | 舞台坐标（左上角） |
| `sliderMin` / `sliderMax` / `isDiscrete` | 滑块模式参数 |

本项目生成运行时的 `MONITORS` 常量就是由这些字段整理而来，VM 可直接复用。

---

## 9. 注释与 TurboWarp 配置

### 9.1 注释对象

```json
"comments": {
  "commentId": {
    "blockId": "blockId | null",
    "x": 0, "y": 0,
    "width": 200, "height": 100,
    "minimized": false,
    "text": "说明文字"
  }
}
```

注释可以挂在 target 顶层（`target.comments`），也可能出现在顶层
`project.comments`（工作区注释）。

### 9.2 `_twconfig_`

TurboWarp 把高级选项写在一条注释里：

```text
// _twconfig_
{
  "framerate": 60,
  "runtimeOptions": {
    "fencing": false,
    "miscLimits": false,
    "interpolation": true,
    "turbo": true,
    "warpTimer": 0.5,
    "cloneLimit": 300,
    "stageWidth": 480,
    "stageHeight": 360,
    "hqPen": false
  }
}
```

本项目的 `scratch_parser._parse_turbowarp_options` 会扫描所有 target 的注释，
取第一个包含 `_twconfig_` 的注释，截取其中 `{...}` 解析。VM 启动时应把
这些选项映射为 `ScratchRuntime` 构造参数。

---

## 10. 资源格式

| 格式 | 说明 | 运行时处理 |
|------|------|------------|
| `.svg` | 矢量造型，`rotationCenterX/Y` 为旋转中心（原图像素坐标） | pygame 无原生 SVG；现有运行时内置简化 SVG 渲染，失败时用占位色块 |
| `.png` | 位图造型，支持透明通道 | `pygame.image.load` |
| `.jpg` / `.jpeg` | 不透明位图 | `pygame.image.load` |
| `.wav` | 未压缩音频 | `pygame.mixer.Sound` |
| `.mp3` | 压缩音频 | 依赖 SDL_mixer 解码支持 |

坐标与尺寸换算（Scratch 舞台 480×360，中心原点）：

```text
屏幕 x = 舞台宽/2 + scratch_x
屏幕 y = 舞台高/2 - scratch_y
```

造型渲染尺寸：原始像素尺寸 × `size / 100`，再按造型自身分辨率缩放。

---

## 11. 与本项目 IR 的对应关系

| SB3 数据 | IR（`src/ir.py`） |
|----------|-------------------|
| `target`（舞台） | `SpriteIR(is_stage=True)`，`ProjectIR.stage` |
| `target`（角色） | `SpriteIR`，`ProjectIR.sprites` |
| `variables` | `SpriteIR.variables`（名字 → 值），`variable_attrs` / `variable_id_attrs` 保存属性名映射 |
| `lists` | `SpriteIR.lists`，`list_attrs` / `list_id_attrs` |
| `blocks` 堆栈 | `SpriteIR.statements`（顶层帽子块链） |
| 帽子块 | `Statement(type=WHEN_*, next=...)` |
| 普通块 | `Statement(type=..., next=...)` |
| 输入槽 | `Statement.value` / `condition` / `extra` 中的 `Expr` |
| `SUBSTACK` | `Statement.body`（已拆成列表） |
| `procedures_definition` | `Statement(PROCEDURE_DEFINE, body=[...], extra={proccode, args, ...})` |
| `procedures_call` | `Statement(PROCEDURE_CALL, extra={args: [Expr], proccode})` |
| 表达式块 | `Expr(type=..., left/right/args/extra)` |
| `monitors` | `ProjectIR.monitors`（原始字典） |
| `extensions` | `ProjectIR.extensions` |
| `_twconfig_` | `ProjectIR.runtime_options` |

IR 解析器的入口：

```python
from scratch_parser import parse_scratch_project
project = parse_scratch_project(project_json)
```

---

## 12. 最小可运行示例

ZIP 内：

```text
project.json
cd21514d0531fdffb22204e0ec5ed84a.svg
```

`project.json`：

```json
{
  "targets": [
    {
      "isStage": true,
      "name": "Stage",
      "variables": {},
      "lists": {},
      "broadcasts": {},
      "blocks": {},
      "comments": {},
      "currentCostume": 0,
      "costumes": [{
        "name": "backdrop1",
        "assetId": "cd21514d0531fdffb22204e0ec5ed84a",
        "md5ext": "cd21514d0531fdffb22204e0ec5ed84a.svg",
        "dataFormat": "svg",
        "rotationCenterX": 240,
        "rotationCenterY": 180
      }],
      "sounds": [],
      "volume": 100,
      "layerOrder": 0,
      "tempo": 60,
      "videoTransparency": 50,
      "videoState": "on",
      "textToSpeechLanguage": null
    },
    {
      "isStage": false,
      "name": "Sprite1",
      "variables": { "v1": ["计数", 0] },
      "lists": {},
      "broadcasts": {},
      "blocks": {
        "hat": {
          "opcode": "event_whenflagclicked",
          "next": "add",
          "parent": null,
          "inputs": {},
          "fields": {},
          "shadow": false,
          "topLevel": true,
          "x": 0,
          "y": 0
        },
        "add": {
          "opcode": "data_changevariableby",
          "next": "say",
          "parent": "hat",
          "inputs": { "VALUE": [1, [4, "1"]] },
          "fields": { "VARIABLE": ["计数", "v1"] },
          "shadow": false,
          "topLevel": false
        },
        "say": {
          "opcode": "looks_say",
          "next": null,
          "parent": "add",
          "inputs": { "MESSAGE": [1, [10, "Hello"]] },
          "fields": {},
          "shadow": false,
          "topLevel": false
        }
      },
      "comments": {},
      "currentCostume": 0,
      "costumes": [{
        "name": "costume1",
        "assetId": "bcf454acf82e4504149f7ffe07081dbc",
        "md5ext": "bcf454acf82e4504149f7ffe07081dbc.svg",
        "dataFormat": "svg",
        "rotationCenterX": 48,
        "rotationCenterY": 50
      }],
      "sounds": [],
      "volume": 100,
      "layerOrder": 1,
      "x": 0,
      "y": 0,
      "direction": 90,
      "visible": true,
      "size": 100,
      "draggable": false,
      "rotationStyle": "all around"
    }
  ],
  "monitors": [],
  "extensions": [],
  "meta": { "semver": "3.0.0", "vm": "0.2.0", "agent": "scratch-vm" }
}
```

---

## 13. 加载器实现清单

`scratch_vm/loader.py` 需要保证：

- [x] 输入支持 `.sb3`、`.zip`、`.json` 三种；
- [x] ZIP 内定位 `project.json`，找不到时回退到任意 `*.json`；
- [x] 解压所有资产到临时目录（`tempfile.mkdtemp`），返回 `assets_dir`；
- [x] 资产解压使用 `basename`，拒绝路径穿越；
- [x] 调用 `parse_scratch_project` 生成 `ProjectIR`；
- [x] 暴露 `project_json` 原始字典，调试器需要读取 block 的 `opcode` / `id`；
- [x] 提供 `close()` / 上下文管理器，退出时清理临时目录；
- [x] 解析失败时给出包含文件路径与 JSON 位置的错误信息。

---

## 14. 参考

- [Scratch Wiki: Scratch File Format (3.0)](https://en.scratch-wiki.info/wiki/Scratch_File_Format_(3.0))
- [scratch-vm `src/serialization/sb3.js`](https://github.com/scratchfoundation/scratch-vm/blob/develop/src/serialization/sb3.js)
- [TurboWarp `_twconfig_` 说明](https://docs.turbowarp.org/advanced-settings)
