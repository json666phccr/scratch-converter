# -*- coding: utf-8 -*-
"""ScPython 错误类型。"""

from __future__ import annotations

from typing import Optional


class ScPythonError(Exception):
    """带文件与行号的编译错误"""

    def __init__(self, message: str, path: Optional[str] = None,
                 line: Optional[int] = None, column: Optional[int] = None):
        self.message = message
        self.path = path
        self.line = line
        self.column = column
        super().__init__(str(self))

    def __str__(self) -> str:
        location = ""
        if self.path:
            location = self.path
            if self.line:
                location += f":{self.line}"
                if self.column:
                    location += f":{self.column}"
            location += ": "
        return f"{location}{self.message}"


class ScPythonSyntaxError(ScPythonError):
    """语法不符合 ScPython 子集"""
