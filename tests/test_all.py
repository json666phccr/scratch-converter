#!/usr/bin/env python3
"""Scratch 3.0 <-> Python 双向转换器 测试入口

测试按功能拆分到同目录的多个模块中，本文件只负责汇总运行。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _support import run_tests
from test_basic_conversion import TESTS as BASIC_TESTS
from test_procedures_lists import TESTS as PROCEDURE_TESTS
from test_runtime_core import TESTS as RUNTIME_TESTS
from test_turbowarp_core import TESTS as TURBOWARP_TESTS
from test_visual_stage import TESTS as VISUAL_TESTS
from test_general_python import TESTS as GENERAL_TESTS
from test_runtime_io import TESTS as IO_TESTS
from test_extensions_a import TESTS as EXTENSION_A_TESTS
from test_extensions_b import TESTS as EXTENSION_B_TESTS
from test_extensions_c import TESTS as EXTENSION_C_TESTS
from test_regressions import TESTS as REGRESSION_TESTS
from test_scratch_vm import TESTS as VM_TESTS

TESTS = (
    BASIC_TESTS + PROCEDURE_TESTS + RUNTIME_TESTS + TURBOWARP_TESTS
    + VISUAL_TESTS + GENERAL_TESTS + IO_TESTS + EXTENSION_A_TESTS
    + EXTENSION_B_TESTS + EXTENSION_C_TESTS + REGRESSION_TESTS
    + VM_TESTS
)


def main():
    """运行所有测试"""
    return 0 if run_tests(TESTS) else 1


if __name__ == '__main__':
    sys.exit(main())
