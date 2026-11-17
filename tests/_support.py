# -*- coding: utf-8 -*-
"""测试共享的导入、构造辅助与运行器"""

import os
import sys
import json
import math
import traceback

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from ir import (
    BlockType, ExprType, Expr, Statement, SpriteIR, ProjectIR,
    make_number, make_string, make_boolean, make_variable,
    make_binary_op, make_random,
)
from scratch_parser import parse_scratch_project
from scratch_writer import write_scratch_project
from python_generator import generate_python, generate_modules
from python_parser import parse_python_code, python_to_project


def make_project(blocks, name="Test"):
    """构造一个最小Scratch项目（使用真实sb3的嵌套字面量格式）"""
    return {
        "targets": [{
            "isStage": False,
            "name": name,
            "variables": {},
            "lists": {},
            "broadcasts": {},
            "blocks": blocks,
            "comments": {},
            "currentCostume": 0,
            "costumes": [],
            "sounds": [],
            "visible": True,
            "x": 0,
            "y": 0,
            "size": 100,
            "direction": 90,
            "draggable": False,
            "rotationStyle": "all around",
            "volume": 100,
            "layerOrder": 1
        }],
        "monitors": [],
        "extensions": [],
        "meta": {"semver": "3.0.0", "vm": "0.2.0", "agent": ""}
    }


def block(opcode, next_id=None, parent=None, inputs=None, fields=None,
          top_level=False, mutation=None):
    """构造Scratch块数据"""
    data = {
        "opcode": opcode,
        "next": next_id,
        "parent": parent,
        "inputs": inputs or {},
        "fields": fields or {},
        "shadow": False,
        "topLevel": top_level,
    }
    if top_level:
        data["x"] = 0
        data["y"] = 0
    if mutation:
        data["mutation"] = mutation
    return data


def get_sprite(targets):
    return next(t for t in targets if not t.get("isStage"))


def run_tests(tests):
    """按顺序运行测试并输出汇总"""
    print("=" * 60)
    print("Scratch 3.0 <-> Python 双向转换器 测试")
    print("=" * 60)

    passed = 0
    failed = 0
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as error:
            print(f"  [FAIL] 测试失败: {error}")
            traceback.print_exc()
            failed += 1

    print()
    print("=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败, 共 {len(tests)} 个测试")
    print("=" * 60)
    return failed == 0
