# ScPython for VS Code

给 `.scpy`（ScPython）文件提供语法高亮：`when` / `init` / `var` / `list`、事件头、`init` 元数据键、字符串、数字、运算符等。

## 方式一：先快速映射到 Python（不用装扩展）

在工程根目录新建 `.vscode/settings.json`：

```json
{
  "files.associations": {
    "*.scpy": "python"
  }
}
```

ScPython 基本是 Python 子集，映射后由 VS Code 内置 Python 语法着色，`when green_flag:` 这类写法也能正常上色（只是 `when/init/var/list` 不会单独着色）。

## 方式二：安装本扩展（推荐，ScPython 专属颜色）

三种装法任选其一：

1. **调试运行**：用 VS Code 打开本目录 `scratch-converter/vscode-scpython`（仓库已带 `.vscode/launch.json`），按 `F5`，会弹出一个“扩展开发宿主”窗口，在其中打开任意 `.scpy` 即可看到高亮。若弹窗提示“没有用于调试 JSON 的扩展”，说明打开的不是本扩展目录或 `launch.json` 未生效，重新用“文件 → 打开文件夹”打开 `vscode-scpython` 再按 `F5`。
2. **直接拷贝**：把 `vscode-scpython` 整个文件夹复制到：
   `%USERPROFILE%\.vscode\extensions\scpython-0.1.0\`
   重启 VS Code。
3. **打包安装**：
   ```powershell
   npx @vscode/vsce package
   ```
   然后在 VS Code 里 `Ctrl+Shift+P` → `Extensions: Install from VSIX...` 选择生成的 `.vsix`。

安装后打开 `.scpy`，右下角语言模式应显示 `ScPython`。
若显示的是 `Plain Text`/`Python`，按 `Ctrl+Shift+P` → `Change Language Mode` → 选择 `ScPython`；
或在项目 `.vscode/settings.json` 里固定：

```json
{
  "files.associations": {
    "*.scpy": "scpython"
  }
}
```

## 高亮效果说明

| 语法 | 颜色分类 |
|------|----------|
| `when` / `init` | 事件关键字 |
| `green_flag` / `broadcast` 等事件名 | 事件标签 |
| `var` / `list` | 声明关键字 |
| `costumes` / `name` / `x` 等 `init` 键 | 属性名 |
| `if/while/for/def/and/or/not` | 控制关键字 |
| `True/False/None` | 常量 |
| `say(...)` / `set_effect(...)` 等调用 | 函数 |
| `# 注释`、`"字符串"`、`数字` | 对应字面量 |
