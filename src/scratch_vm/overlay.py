# -*- coding: utf-8 -*-
"""游戏窗口内的可视化调试面板。

通过包装 ``runtime._draw``，在每帧绘制完成后把面板画到 ``stage_surface`` 上。
F2 切换显示；headless 模式下不安装。

面板内容：

- 运行状态（运行/暂停）、帧号、FPS、线程数、克隆数；
- 当前暂停位置：角色、积木、block id；
- 调用栈（最近 4 层）；
- 当前角色的变量（最多 8 条）；
- 断点数量、trace 数量、累计执行语句数。
"""

from __future__ import annotations

from typing import Optional

try:
    import pygame
except ImportError:  # pragma: no cover - 项目运行时依赖 pygame
    pygame = None


class DebugOverlay:
    """可视化调试面板"""

    def __init__(self, runtime, debug, enabled: bool = True):
        self.runtime = runtime
        self.debug = debug
        self.enabled = bool(enabled) and not getattr(runtime, "headless", False)
        self.available = pygame is not None
        self._f2_down = False
        self._orig_draw = None
        self._font = None
        self._small = None
        if not self.available:
            self.enabled = False
            return
        self._font = getattr(runtime, "font", None) or pygame.font.Font(None, 14)
        try:
            self._small = pygame.font.Font(
                getattr(runtime, "font_path", None), 12)
        except Exception:
            self._small = self._font
        if not getattr(runtime, "headless", False):
            self._orig_draw = runtime._draw
            runtime._draw = self._draw

    # ===================== 开关 =====================

    def toggle(self) -> bool:
        if not self.available or getattr(self.runtime, "headless", False):
            self.enabled = False
            return False
        self.enabled = not self.enabled
        return self.enabled

    # ===================== 绘制 =====================

    def _draw(self) -> None:
        if self._orig_draw is not None:
            self._orig_draw()
        self._poll_toggle()
        if not self.enabled or pygame is None:
            return
        try:
            self._draw_panel()
        except Exception:
            # 调试面板不能影响正常渲染
            pass

    def _poll_toggle(self) -> None:
        if pygame is None:
            return
        try:
            keys = pygame.key.get_pressed()
            down = bool(keys[pygame.K_F2])
        except Exception:
            return
        if down and not self._f2_down:
            self.enabled = not self.enabled
        self._f2_down = down

    def _panel_lines(self):
        lines = []
        debug = self.debug
        runtime = self.runtime
        paused = bool(debug and debug.paused)
        status = "PAUSED" if paused else "RUNNING"
        threads = len(debug.threads) if debug is not None else 0
        clones = sum(1 for sprite in runtime.sprites
                     if getattr(sprite, "_is_clone", False))
        lines.append(
            f"[VM] {status}  frame {runtime.frame}  fps {runtime.fps}  "
            f"threads {threads}  clones {clones}")

        state = debug.last_state if debug is not None else None
        if state is not None:
            sprite_name = getattr(state.sprite, "name", "?")
            if getattr(state.sprite, "_is_clone", False):
                sprite_name += "#clone"
            stmt = debug.last_stmt
            opcode = ""
            block_id = ""
            if stmt is not None:
                from .debugger import describe_statement, statement_block_id
                opcode = describe_statement(stmt)
                block_id = statement_block_id(stmt)
            lines.append(f"位置: {sprite_name}  {opcode}  block={block_id or '-'}")
            stack = [frame.title for frame in state.frames]
            if stack:
                shown = " > ".join(stack[-4:])
                if len(stack) > 4:
                    shown = "... > " + shown
                lines.append(f"栈: {shown}")
            sprite_ir = getattr(type(state.sprite), "VM_IR", None)
            if sprite_ir is not None:
                parts = []
                for name, attr in list(sprite_ir.variable_attrs.items())[:8]:
                    try:
                        parts.append(f"{name}={getattr(state.sprite, attr)}")
                    except Exception:
                        parts.append(f"{name}=?")
                if parts:
                    lines.append("变量: " + "  ".join(parts))
        else:
            lines.append("位置: -")

        if debug is not None:
            lines.append(
                f"断点 {len(debug.breakpoints)}  trace {len(debug.trace)}  "
                f"语句 {sum(debug.stats.values())}  错误 {len(debug.errors)}")
        lines.append("F2 开关调试面板")
        return lines

    def _draw_panel(self) -> None:
        if pygame is None or self._font is None:
            return
        surface = getattr(self.runtime, "stage_surface", None)
        if surface is None:
            return
        lines = self._panel_lines()
        font = self._small or self._font
        padding = 6
        line_height = font.get_linesize()
        width = max(font.size(line)[0] for line in lines) + padding * 2
        width = min(max(width, 300), max(200, surface.get_width() - 12))
        height = line_height * len(lines) + padding * 2

        panel = pygame.Surface((width, height), pygame.SRCALPHA)
        panel.fill((10, 10, 14, 185))
        pygame.draw.rect(panel, (90, 160, 220, 220), panel.get_rect(), 1)
        for index, line in enumerate(lines):
            color = (255, 120, 120) if (index == 0 and "PAUSED" in line) \
                else (235, 235, 235)
            text = font.render(line, True, color)
            panel.blit(text, (padding, padding + index * line_height))
        surface.blit(panel, (6, 6))

    def draw_once(self) -> Optional[str]:
        """供测试使用：返回当前面板文本"""
        return "\n".join(self._panel_lines())
