#!/usr/bin/env python3
"""
Python 代码解析器
将 Python 源代码解析为中间表示 (IR)

支持将scratch-converter生成的Python DSL代码转换回IR，
然后可以通过scratch_writer转换回Scratch JSON。

解析策略：
1. 使用Python标准ast模块解析语法树
2. 识别特殊函数调用（如move, say, if_on_edge_bounce等）映射回Scratch块
3. 识别循环结构（for/while）映射回Scratch控制块
4. 识别if/else映射回Scratch条件块
5. 识别变量赋值映射回Scratch变量操作
"""

import ast
import re
import math
from typing import Dict, List, Optional, Any, Tuple, Set

from ir import (
    BlockType, ExprType, Expr, Statement, SpriteIR, ProjectIR,
    make_number, make_string, make_boolean, make_variable, make_property,
    make_binary_op, make_random, make_list_access, make_list_contains,
    sanitize_name, identifier_to_key,
)


class PythonParser:
    """将Python源代码解析为ProjectIR"""

    # 已知的Scratch API方法名（不应被解析为自制积木）
    KNOWN_METHODS = {
        'move', 'turn_right', 'turn_left', 'goto_xy', 'set_x', 'set_y',
        'change_x', 'change_y', 'if_on_edge_bounce',
        'say', 'say_for', 'think', 'think_for',
        'show', 'hide', 'switch_costume', 'next_costume',
        'change_size', 'set_size', 'change_effect', 'set_effect', 'clear_effects',
        'play_sound', 'stop_all_sounds', 'change_volume', 'set_volume',
        'wait', 'wait_until', 'stop',
        'create_clone_of', 'delete_this_clone',
        'broadcast', 'broadcast_and_wait',
        'touching', 'distance_to', 'key_pressed', 'ask_and_wait', 'reset_timer',
        'show_variable', 'hide_variable', 'show_list', 'hide_list',
        'run', '_clamp_position', 'extension',
    }

    def __init__(self):
        self.sprite_name: str = "Sprite"
        self.sprite: Optional[SpriteIR] = None
        self.local_vars: Dict[str, Any] = {}
        self.in_event_handler: bool = False
        self._procedure_args: Dict[str, str] = {}
        self._procedure_meta: Dict[str, Dict] = {}

    def parse_code(self, code: str, sprite_name: str = "Sprite") -> SpriteIR:
        """解析Python代码为SpriteIR"""
        self.sprite_name = sprite_name
        self.sprite = SpriteIR(name=sprite_name)
        self.local_vars = {}
        self._procedure_meta = {}

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            print(f"Python语法错误: {e}")
            return self.sprite

        classes = [node for node in ast.iter_child_nodes(tree)
                   if isinstance(node, ast.ClassDef)]

        # 只解析目标精灵的类。生成代码里还包含ScratchSprite基类和其他精灵类，
        # 如果全部解析会把所有精灵的方法混到同一个精灵中。
        target_class = None
        if self.sprite_name:
            wanted = {self.sprite_name, sanitize_name(self.sprite_name, 'Sprite')}
            for cls in classes:
                if cls.name in wanted:
                    target_class = cls
                    break
        if target_class is None:
            for cls in classes:
                if any(isinstance(base, ast.Name) and base.id == 'ScratchSprite'
                       for base in cls.bases):
                    target_class = cls
                    break

        if target_class is not None:
            self._parse_class(target_class)
            self._pad_procedure_calls()
            # 未显式指定精灵名时，使用代码中的类名，避免Python->Scratch丢失精灵名
            if self.sprite_name == 'Sprite':
                self.sprite.name = target_class.name
        else:
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.FunctionDef):
                    self._parse_top_function(node)

        return self.sprite

    def _pad_procedure_calls(self):
        """给调用补参数，并补全TurboWarp的proccode/argumentids/warp元数据"""
        definitions = {}
        for stmt in self.sprite.statements:
            if stmt.type == BlockType.PROCEDURE_DEFINE:
                definitions[stmt.extra.get('name')] = stmt.extra

        def apply(node, args):
            meta = definitions.get(node.extra.get('name'))
            if meta is None:
                return args
            types = meta.get('arg_types') or []
            while len(args) < len(types):
                index = len(args)
                # 与原版 Scratch 一致：没填的参数取参数默认值（空字符串），
                # 而不是数字 0；空字符串参与数值运算时才按 0 处理。
                args.append(make_boolean(False) if types[index] == 'b'
                            else make_string(''))
            for key in ('proccode', 'argumentids', 'argumentdefaults',
                        'arg_types', 'warp'):
                if key in meta and key not in node.extra:
                    node.extra[key] = meta[key]
            return args

        def walk_expr(expr):
            if expr is None:
                return
            if expr.type == ExprType.PROCEDURE_CALL:
                expr.args = apply(expr, expr.args)
            walk_expr(expr.left)
            walk_expr(expr.right)
            for child in expr.children:
                walk_expr(child)
            for arg in expr.args:
                walk_expr(arg)

        seen = set()

        def visit(stmt):
            if stmt is None or id(stmt) in seen:
                return
            seen.add(id(stmt))
            if stmt.type == BlockType.PROCEDURE_CALL:
                stmt.extra['args'] = apply(stmt, stmt.extra.get('args', []))
            walk_expr(stmt.value)
            walk_expr(stmt.condition)
            walk_expr(stmt.target)
            walk_expr(stmt.expr)
            for value in stmt.extra.values():
                if isinstance(value, Expr):
                    walk_expr(value)
            for child in stmt.body:
                visit(child)
            for child in stmt.else_body:
                visit(child)
            visit(stmt.next)

        for stmt in self.sprite.statements:
            visit(stmt)

    def parse_file(self, file_path: str, sprite_name: str = "Sprite") -> SpriteIR:
        """从文件解析Python代码"""
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()
        return self.parse_code(code, sprite_name)

    def _parse_class(self, node: ast.ClassDef):
        """解析类定义"""
        # 如果继承自ScratchSprite，解析为精灵
        is_scratch_sprite = False
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id == 'ScratchSprite':
                is_scratch_sprite = True
                break
            elif isinstance(base, ast.Attribute) and base.attr == 'ScratchSprite':
                is_scratch_sprite = True
                break

        self._condition_hats = {}
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == 'run':
                self._collect_condition_hats(item)

        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                if item.name == '__init__':
                    self._parse_init(item)
                elif item.name == 'run':
                    self._parse_run_method(item)
                elif item.name.startswith('when_'):
                    self._parse_event_handler(item)
                elif item.name in self.KNOWN_METHODS:
                    pass  # 跳过已知的Scratch API方法
                elif not item.name.startswith('_'):
                    # 自制积木
                    self._parse_procedure(item)

    # 已知的ScratchSprite内置属性（不应作为用户变量）
    BUILTIN_ATTRS = {
        'x', 'y', 'direction', 'visible', 'size', 'costume', 'costume_number',
        'costume_name', 'volume', 'answer', 'mouse_x', 'mouse_y', 'mouse_down',
        'timer', 'loudness', 'days_since_2000', 'rotation_style',
        'name', 'costumes', 'sounds',
        '_running', '_clones',
    }

    # 运行时内部属性：仅这些以下划线开头的属性不当作Scratch变量，
    # 其余下划线名字（如Scratch里的 "_i"）仍是普通变量。
    INTERNAL_ATTRS = {
        '_local', '_global_running', '_clones', '_handlers', '_runtime',
        '_say_text', '_say_until', '_say_kind', '_is_clone',
        '_render_x', '_render_y', '_render_direction', '_render_size',
        '_pen_down', '_pen_alpha', '_pen_hsv', '_pen_size', '_pen_last',
        '_effects', '_sound_effects', '_conditions',
        '_stretch_x', '_stretch_y', '_text_state',
    }

    def _parse_init(self, node: ast.FunctionDef):
        """解析__init__方法"""
        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                        if target.value.id == 'self':
                            attr = target.id if hasattr(target, 'id') else target.attr
                            value = self._eval_expr(stmt.value)
                            if attr in self.INTERNAL_ATTRS or attr in self.BUILTIN_ATTRS:
                                continue
                            if isinstance(value, (int, float)):
                                self.sprite.variables[attr] = value
                            elif isinstance(value, str):
                                self.sprite.variables[attr] = value
                            elif isinstance(value, list):
                                self.sprite.lists[attr] = value

            elif isinstance(stmt, ast.Expr):
                if isinstance(stmt.value, ast.Call):
                    func = stmt.value.func
                    if isinstance(func, ast.Attribute):
                        if func.attr == '__init__':
                            pass  # super().__init__()

    def _collect_condition_hats(self, node: ast.FunctionDef):
        """从 run() 里恢复“当计时器/响度 > 值”帽子的阈值"""
        for stmt in node.body:
            if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
                continue
            call = stmt.value
            func = call.func
            if not (isinstance(func, ast.Attribute)
                    and func.attr == '_register_greater_than'
                    and len(call.args) >= 3):
                continue
            menu = self._eval_expr(call.args[0])
            limit = 10
            if isinstance(call.args[1], ast.Lambda):
                value = self._eval_expr(call.args[1].body)
                if isinstance(value, (int, float)):
                    limit = value
            method = call.args[2]
            if isinstance(method, ast.Attribute):
                name = method.attr
            elif isinstance(method, ast.Name):
                name = method.id
            else:
                continue
            self._condition_hats[name] = (str(menu).lower(), limit)

    def _parse_run_method(self, node: ast.FunctionDef):
        """解析run方法"""
        for stmt in node.body:
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                call = stmt.value
                if isinstance(call.func, ast.Attribute):
                    if call.func.attr == 'when_green_flag':
                        # 找到when_green_flag函数
                        for item in ast.iter_child_nodes(node):
                            pass
                    elif call.func.attr.startswith('when_'):
                        method_name = call.func.attr
                        # 调用事件处理方法
                        pass

    def _parse_event_handler(self, node: ast.FunctionDef):
        """解析事件处理函数"""
        func_name = node.name
        stmt = None

        if re.fullmatch(r'when_green_flag(_\d+)?', func_name):
            stmt = Statement(type=BlockType.WHEN_FLAG_CLICKED)
        elif func_name.startswith('when_key_pressed_'):
            key_ident = func_name[len('when_key_pressed_'):]
            matched = re.fullmatch(r'(.+?)_(\d+)', key_ident)
            if matched:
                candidate = matched.group(1)
                if len(candidate) == 1 or identifier_to_key(candidate) != candidate:
                    key_ident = candidate
            key = identifier_to_key(key_ident)
            stmt = Statement(type=BlockType.WHEN_KEY_PRESSED, extra={'key': key})
        elif re.fullmatch(r'when_clicked(_\d+)?', func_name):
            stmt = Statement(type=BlockType.WHEN_THIS_SPRITE_CLICKED)
        elif re.fullmatch(r'when_clone_starts(_\d+)?', func_name):
            stmt = Statement(type=BlockType.START_AS_CLONE)
        elif func_name.startswith('when_broadcast_'):
            msg = func_name.replace('when_broadcast_', '')
            # 从docstring恢复包含空格的原始广播名
            doc = ast.get_docstring(node) or ''
            match = re.search(r"当接收到广播'(.*)'时", doc)
            if match:
                msg = match.group(1)
            stmt = Statement(type=BlockType.WHEN_BROADCAST_RECEIVED, value=make_string(msg))
        elif func_name.startswith('when_backdrop_'):
            backdrop = func_name[len('when_backdrop_'):]
            doc = ast.get_docstring(node) or ''
            match = re.search(r"当背景换成'(.*)'时", doc)
            if match:
                backdrop = match.group(1)
            stmt = Statement(type=BlockType.WHEN_BACKDROP_SWITCHES,
                             extra={'backdrop': backdrop})
        elif func_name.startswith(('when_timer_greater_than',
                                   'when_loudness_greater_than')):
            menu, limit = self._condition_hats.get(
                func_name, ('timer' if 'timer' in func_name else 'loudness', 10))
            stmt = Statement(type=BlockType.WHEN_GREATER_THAN,
                             extra={'menu': 'TIMER' if menu == 'timer' else 'LOUDNESS'},
                             value=make_number(limit))
        else:
            return

        # 解析函数体
        prev = None
        for body_stmt in node.body:
            parsed = self._parse_statement(body_stmt)
            if parsed:
                if prev is None:
                    stmt.next = parsed
                    prev = parsed
                else:
                    prev.next = parsed
                    prev = parsed
                    # 遍历到链尾
                    while prev.next:
                        prev = prev.next

        self.sprite.add_statement(stmt)

    def _parse_procedure(self, node: ast.FunctionDef):
        """解析自制积木"""
        proc_name = node.name

        meta = {}
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) \
                    and isinstance(decorator.func, ast.Name) \
                    and decorator.func.id == '_as_procedure':
                for keyword in decorator.keywords:
                    try:
                        meta[keyword.arg] = ast.literal_eval(keyword.value)
                    except (ValueError, TypeError):
                        pass

        # 获取参数，并建立 Python参数名 -> Scratch参数名 的映射
        python_args = [arg.arg for arg in node.args.args if arg.arg != 'self']
        saved_names = meta.get('arg_names') or []
        args = saved_names if len(saved_names) == len(python_args) else [
            name[4:] if name.startswith('arg_') else name for name in python_args]
        arg_map = {name: args[index] for index, name in enumerate(python_args)}

        extra = {
            'name': proc_name,
            'args': args,
            'arg_types': meta.get('arg_types') or ['s'] * len(args),
            'warp': bool(meta.get('warp')),
        }
        for key in ('proccode', 'arg_ids', 'arg_defaults'):
            if key in meta:
                extra[key] = meta[key]
        if 'arg_ids' in meta:
            extra['argumentids'] = meta['arg_ids']
        if 'arg_defaults' in meta:
            extra['argumentdefaults'] = meta['arg_defaults']

        self._procedure_meta[proc_name] = extra
        stmt = Statement(type=BlockType.PROCEDURE_DEFINE, extra=extra)

        # 解析函数体：全部放入body，不挂next，
        # 避免写入Scratch时同时按body和next生成导致语句重复。
        previous_args = self._procedure_args
        self._procedure_args = arg_map
        try:
            for body_stmt in node.body:
                parsed = self._parse_statement(body_stmt)
                if parsed:
                    stmt.body.append(parsed)
        finally:
            self._procedure_args = previous_args

        self.sprite.add_statement(stmt)

    def _parse_top_function(self, node: ast.FunctionDef):
        """解析顶层函数"""
        if node.name == 'main':
            # 解析main函数中的精灵创建和调用
            pass

    def _parse_statement(self, node: ast.AST) -> Optional[Statement]:
        """解析单个语句"""
        if isinstance(node, ast.Expr):
            return self._parse_expr_statement(node)
        elif isinstance(node, ast.Assign):
            return self._parse_assignment(node)
        elif isinstance(node, ast.AugAssign):
            return self._parse_aug_assignment(node)
        elif isinstance(node, ast.For):
            return self._parse_for_loop(node)
        elif isinstance(node, ast.While):
            return self._parse_while_loop(node)
        elif isinstance(node, ast.If):
            return self._parse_if(node)
        elif isinstance(node, ast.Return):
            value = self._parse_expr_to_ir(node.value) if node.value else None
            return Statement(type=BlockType.PROCEDURE_RETURN, value=value)
        elif isinstance(node, ast.Delete):
            return self._parse_delete(node)
        elif isinstance(node, ast.Pass):
            return None

        return None

    def _list_name_from_node(self, node: ast.AST) -> Optional[str]:
        """从 self.<list> 节点中取出列表名"""
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                and node.value.id == 'self' and node.attr in self.sprite.lists:
            return node.attr
        return None

    def _parse_delete(self, node: ast.Delete) -> Optional[Statement]:
        """解析 del self.list[index - 1] -> 删除列表第n项"""
        if len(node.targets) != 1:
            return None
        target = node.targets[0]
        if isinstance(target, ast.Subscript):
            list_name = self._list_name_from_node(target.value)
            if list_name:
                index = self._normalize_index(self._parse_expr_to_ir(target.slice))
                return Statement(type=BlockType.DELETE_FROM_LIST, value=index,
                                 extra={'name': list_name})
        return None

    def _parse_expr_statement(self, node: ast.Expr) -> Optional[Statement]:
        """解析表达式语句"""
        expr = node.value
        if isinstance(expr, ast.Call):
            return self._parse_function_call(expr)
        return None

    def _parse_extension_arguments(self, call: ast.Call):
        """解析 self.extension(name, opcode, inputs, fields)"""
        if len(call.args) < 2:
            return None
        namespace = call.args[0].value if isinstance(call.args[0], ast.Constant) else ''
        opcode = call.args[1].value if isinstance(call.args[1], ast.Constant) else ''
        inputs = []
        if len(call.args) >= 3 and isinstance(call.args[2], ast.Dict):
            for key, value in zip(call.args[2].keys, call.args[2].values):
                if isinstance(key, ast.Constant):
                    inputs.append((str(key.value), self._parse_expr_to_ir(value)))
        fields = {}
        if len(call.args) >= 4 and isinstance(call.args[3], ast.Dict):
            for key, value in zip(call.args[3].keys, call.args[3].values):
                if isinstance(key, ast.Constant) and isinstance(value, ast.Constant):
                    fields[str(key.value)] = value.value
        return str(namespace), str(opcode), inputs, fields

    def _parse_function_call(self, call: ast.Call) -> Optional[Statement]:
        """解析函数调用"""
        func = call.func
        func_name = ""

        if isinstance(func, ast.Name):
            func_name = func.id
        elif isinstance(func, ast.Attribute):
            func_name = func.attr

        # TurboWarp扩展调用: self.extension(namespace, opcode, {inputs}, {fields})
        if func_name == 'extension' and isinstance(func, ast.Attribute) \
                and isinstance(func.value, ast.Name) and func.value.id == 'self':
            parsed = self._parse_extension_arguments(call)
            if parsed:
                namespace, opcode, inputs, fields = parsed
                return Statement(type=BlockType.EXTENSION, extra={
                    'namespace': namespace, 'opcode': opcode,
                    'inputs': inputs, 'fields': fields})

        # 解析参数
        args = [self._eval_expr(arg) for arg in call.args]
        kwargs = {kw.arg: self._eval_expr(kw.value) for kw in call.keywords}

        # 列表方法调用: self.items.append(x) / insert / clear
        if isinstance(func, ast.Attribute):
            list_name = self._list_name_from_node(func.value)
            if list_name:
                if func.attr == 'append':
                    item = self._parse_expr_to_ir(call.args[0]) if call.args else make_string('')
                    return Statement(type=BlockType.ADD_TO_LIST, value=item,
                                     extra={'name': list_name})
                elif func.attr == 'insert':
                    index = self._parse_expr_to_ir(call.args[0]) if call.args else make_number(1)
                    item = self._parse_expr_to_ir(call.args[1]) if len(call.args) > 1 else make_string('')
                    return Statement(type=BlockType.INSERT_IN_LIST,
                                     value=self._normalize_index(index),
                                     extra={'name': list_name, 'item': item})
                elif func.attr == 'clear':
                    return Statement(type=BlockType.DELETE_ALL_FROM_LIST,
                                     extra={'name': list_name})

        # 等待直到条件成立: self.wait_until(lambda: _sc_bool(cond))
        if func_name == 'wait_until' and call.args \
                and isinstance(call.args[0], ast.Lambda):
            return Statement(type=BlockType.WAIT_UNTIL,
                             condition=self._parse_expr_to_ir(call.args[0].body))

        # 列表操作辅助函数
        if func_name == '_sc_list_delete' and len(call.args) >= 2:
            list_name = self._list_name_from_node(call.args[0])
            if list_name:
                return Statement(type=BlockType.DELETE_FROM_LIST,
                                 value=self._parse_expr_to_ir(call.args[1]),
                                 extra={'name': list_name})
        if func_name == '_sc_list_insert' and len(call.args) >= 3:
            list_name = self._list_name_from_node(call.args[0])
            if list_name:
                return Statement(type=BlockType.INSERT_IN_LIST,
                                 value=self._parse_expr_to_ir(call.args[1]),
                                 extra={'name': list_name,
                                        'item': self._parse_expr_to_ir(call.args[2])})
        if func_name == '_sc_list_replace' and len(call.args) >= 3:
            list_name = self._list_name_from_node(call.args[0])
            if list_name:
                return Statement(type=BlockType.REPLACE_IN_LIST,
                                 value=self._parse_expr_to_ir(call.args[1]),
                                 extra={'name': list_name,
                                        'item': self._parse_expr_to_ir(call.args[2])})

        # 映射到Scratch块
        if func_name == 'move':
            steps = self._parse_expr_to_ir(call.args[0]) if call.args else make_number(10)
            return Statement(type=BlockType.MOVE_STEPS, value=steps)

        elif func_name == 'turn_right':
            deg = self._parse_expr_to_ir(call.args[0]) if call.args else make_number(15)
            return Statement(type=BlockType.TURN_RIGHT, value=deg)

        elif func_name == 'turn_left':
            deg = self._parse_expr_to_ir(call.args[0]) if call.args else make_number(15)
            return Statement(type=BlockType.TURN_LEFT, value=deg)

        elif func_name == 'goto_xy':
            x = self._parse_expr_to_ir(call.args[0]) if call.args else make_number(0)
            y = self._parse_expr_to_ir(call.args[1]) if len(call.args) > 1 else make_number(0)
            return Statement(type=BlockType.GO_TO_XY, extra={'x': x, 'y': y})

        elif func_name == 'glide_to':
            secs = self._parse_expr_to_ir(call.args[0]) if call.args else make_number(1)
            x = self._parse_expr_to_ir(call.args[1]) if len(call.args) > 1 else make_number(0)
            y = self._parse_expr_to_ir(call.args[2]) if len(call.args) > 2 else make_number(0)
            return Statement(type=BlockType.GLIDE_SECS_TO, value=secs,
                             extra={'x': x, 'y': y})

        elif func_name == 'goto_random':
            return Statement(type=BlockType.GO_TO_RANDOM, extra={'target': '_random_'})

        elif func_name == 'set_x':
            val = self._parse_expr_to_ir(call.args[0]) if call.args else make_number(0)
            return Statement(type=BlockType.SET_X, value=val)

        elif func_name == 'set_y':
            val = self._parse_expr_to_ir(call.args[0]) if call.args else make_number(0)
            return Statement(type=BlockType.SET_Y, value=val)

        elif func_name == 'change_x':
            val = self._parse_expr_to_ir(call.args[0]) if call.args else make_number(10)
            return Statement(type=BlockType.CHANGE_X, value=val)

        elif func_name == 'change_y':
            val = self._parse_expr_to_ir(call.args[0]) if call.args else make_number(10)
            return Statement(type=BlockType.CHANGE_Y, value=val)

        elif func_name == 'if_on_edge_bounce':
            return Statement(type=BlockType.IF_ON_EDGE_BOUNCE)

        elif func_name == 'point_in_direction':
            val = self._parse_expr_to_ir(call.args[0]) if call.args else make_number(90)
            return Statement(type=BlockType.POINT_IN_DIRECTION, value=val)

        elif func_name == 'point_towards':
            target = args[0] if args else '_mouse_'
            return Statement(type=BlockType.POINT_TOWARDS, extra={'target': target})

        elif func_name == 'goto_target':
            target = args[0] if args else '_random_'
            return Statement(type=BlockType.GO_TO_RANDOM, extra={'target': target})

        elif func_name == 'glide_to_target':
            secs = self._parse_expr_to_ir(call.args[0]) if call.args else make_number(1)
            target = args[1] if len(args) > 1 else '_random_'
            return Statement(type=BlockType.GLIDE_TO, value=secs,
                             extra={'target': target})

        elif func_name == 'set_rotation_style':
            style = args[0] if args else 'all around'
            return Statement(type=BlockType.SET_ROTATION_STYLE,
                             extra={'style': style})

        elif func_name == 'set_backdrop':
            name = self._parse_expr_to_ir(call.args[0]) if call.args else make_string('backdrop1')
            return Statement(type=BlockType.SWITCH_BACKDROP, value=name)

        elif func_name == 'set_backdrop_and_wait':
            name = self._parse_expr_to_ir(call.args[0]) if call.args else make_string('backdrop1')
            return Statement(type=BlockType.SWITCH_BACKDROP_AND_WAIT, value=name)

        elif func_name == 'next_backdrop':
            return Statement(type=BlockType.NEXT_BACKDROP)

        elif func_name in ('go_to_layer', 'change_layer'):
            if func_name == 'go_to_layer':
                where = args[0] if args else 'front'
                return Statement(type=BlockType.GO_TO_FRONT, extra={'where': where})
            layer = self._parse_expr_to_ir(call.args[0]) if call.args else make_number(1)
            return Statement(type=BlockType.GO_FORWARD_LAYERS,
                             value=layer, extra={'direction': 'forward'})

        elif func_name == 'set_drag_mode':
            mode = args[0] if args else 'draggable'
            return Statement(type=BlockType.SET_DRAG_MODE, extra={'mode': mode})

        elif func_name in ('set_sound_effect', 'change_sound_effect'):
            effect = args[0] if args else 'PITCH'
            val = self._parse_expr_to_ir(call.args[1]) if len(call.args) > 1 else make_number(10)
            kind = (BlockType.SET_SOUND_EFFECT
                    if func_name == 'set_sound_effect'
                    else BlockType.CHANGE_SOUND_EFFECT)
            return Statement(type=kind, value=val, extra={'effect': effect})

        elif func_name == 'clear_sound_effects':
            return Statement(type=BlockType.CLEAR_SOUND_EFFECTS)

        elif func_name == 'incr_counter':
            return Statement(type=BlockType.INCR_COUNTER)

        elif func_name == 'clear_counter':
            return Statement(type=BlockType.CLEAR_COUNTER)

        elif func_name == 'say':
            msg = self._parse_expr_to_ir(call.args[0]) if call.args else make_string('')
            return Statement(type=BlockType.SAY, value=msg)

        elif func_name == 'say_for':
            msg = self._parse_expr_to_ir(call.args[0]) if call.args else make_string('')
            secs = self._parse_expr_to_ir(call.args[1]) if len(call.args) > 1 else make_number(1)
            return Statement(type=BlockType.SAY_FOR_SECS, value=secs, extra={'message': msg})

        elif func_name == 'think':
            msg = self._parse_expr_to_ir(call.args[0]) if call.args else make_string('')
            return Statement(type=BlockType.THINK, value=msg)

        elif func_name == 'think_for':
            msg = self._parse_expr_to_ir(call.args[0]) if call.args else make_string('')
            secs = self._parse_expr_to_ir(call.args[1]) if len(call.args) > 1 else make_number(1)
            return Statement(type=BlockType.THINK_FOR_SECS, value=secs, extra={'message': msg})

        elif func_name == 'show':
            return Statement(type=BlockType.SHOW)

        elif func_name == 'hide':
            return Statement(type=BlockType.HIDE)

        elif func_name == 'switch_costume':
            name = self._parse_expr_to_ir(call.args[0]) if call.args else make_string('costume1')
            return Statement(type=BlockType.SWITCH_COSTUME, value=name)

        elif func_name == 'next_costume':
            return Statement(type=BlockType.NEXT_COSTUME)

        elif func_name == 'change_size':
            val = self._parse_expr_to_ir(call.args[0]) if call.args else make_number(10)
            return Statement(type=BlockType.CHANGE_SIZE, value=val)

        elif func_name == 'set_size':
            val = self._parse_expr_to_ir(call.args[0]) if call.args else make_number(100)
            return Statement(type=BlockType.SET_SIZE, value=val)

        elif func_name == 'change_effect':
            effect = args[0] if args else 'color'
            val = self._parse_expr_to_ir(call.args[1]) if len(call.args) > 1 else make_number(25)
            return Statement(type=BlockType.CHANGE_EFFECT, value=val, extra={'effect': effect})

        elif func_name == 'set_effect':
            effect = args[0] if args else 'color'
            val = self._parse_expr_to_ir(call.args[1]) if len(call.args) > 1 else make_number(100)
            return Statement(type=BlockType.SET_EFFECT, value=val, extra={'effect': effect})

        elif func_name == 'clear_effects':
            return Statement(type=BlockType.CLEAR_EFFECTS)

        elif func_name == 'play_sound':
            name = self._parse_expr_to_ir(call.args[0]) if call.args else make_string('sound1')
            wait = any(kw.arg == 'wait'
                       and isinstance(kw.value, ast.Constant)
                       and bool(kw.value.value)
                       for kw in call.keywords)
            return Statement(
                type=BlockType.PLAY_SOUND_UNTIL_DONE if wait else BlockType.PLAY_SOUND,
                value=name)

        elif func_name == 'stop_all_sounds':
            return Statement(type=BlockType.STOP_ALL_SOUNDS)

        elif func_name == 'change_volume':
            val = self._parse_expr_to_ir(call.args[0]) if call.args else make_number(10)
            return Statement(type=BlockType.CHANGE_VOLUME, value=val)

        elif func_name == 'set_volume':
            val = self._parse_expr_to_ir(call.args[0]) if call.args else make_number(100)
            return Statement(type=BlockType.SET_VOLUME, value=val)

        elif func_name == 'wait':
            val = self._parse_expr_to_ir(call.args[0]) if call.args else make_number(1)
            return Statement(type=BlockType.WAIT, value=val)

        elif func_name == 'stop':
            option = 'all'
            if call.args and isinstance(call.args[0], ast.Constant) \
                    and isinstance(call.args[0].value, str):
                option = call.args[0].value
            return Statement(type=BlockType.STOP, extra={'option': option})

        elif func_name == 'create_clone_of':
            val = self._parse_expr_to_ir(call.args[0]) if call.args else make_string('_myself_')
            return Statement(type=BlockType.CREATE_CLONE_OF, value=val)

        elif func_name == 'delete_this_clone':
            return Statement(type=BlockType.DELETE_THIS_CLONE)

        elif func_name == 'broadcast':
            val = self._parse_expr_to_ir(call.args[0]) if call.args else make_string('')
            return Statement(type=BlockType.BROADCAST, value=val)

        elif func_name == 'broadcast_and_wait':
            val = self._parse_expr_to_ir(call.args[0]) if call.args else make_string('')
            return Statement(type=BlockType.BROADCAST_AND_WAIT, value=val)

        elif func_name == 'ask_and_wait':
            val = self._parse_expr_to_ir(call.args[0]) if call.args else make_string("What's your name?")
            return Statement(type=BlockType.ASK_AND_WAIT, value=val)

        elif func_name == 'reset_timer':
            return Statement(type=BlockType.RESET_TIMER)

        elif func_name == 'show_variable':
            name = args[0] if args else 'var'
            return Statement(type=BlockType.SHOW_VARIABLE, extra={'name': name})

        elif func_name == 'hide_variable':
            name = args[0] if args else 'var'
            return Statement(type=BlockType.HIDE_VARIABLE, extra={'name': name})

        elif func_name == 'show_list':
            name = args[0] if args else 'list'
            return Statement(type=BlockType.SHOW_LIST, extra={'name': name})

        elif func_name == 'hide_list':
            name = args[0] if args else 'list'
            return Statement(type=BlockType.HIDE_LIST, extra={'name': name})

        # 自制积木调用
        elif not func_name.startswith('_'):
            call_args = [self._parse_expr_to_ir(arg) for arg in call.args]
            return Statement(
                type=BlockType.PROCEDURE_CALL,
                extra={'name': func_name, 'args': call_args}
            )

        return None

    def _parse_assignment(self, node: ast.Assign) -> Optional[Statement]:
        """解析赋值语句"""
        if len(node.targets) != 1:
            return None

        target = node.targets[0]
        if isinstance(target, ast.Name):
            var_name = target.id
            value = self._parse_expr_to_ir(node.value)
            return Statement(
                type=BlockType.SET_VARIABLE,
                extra={'name': var_name},
                value=value
            )
        elif isinstance(target, ast.Attribute):
            if isinstance(target.value, ast.Name) and target.value.id == 'self':
                attr = target.attr
                # self.var = _sc_add(self.var, delta) -> 将变量增加delta
                delta = self._self_add_delta(node.value, attr)
                if delta is not None:
                    return Statement(
                        type=BlockType.CHANGE_VARIABLE,
                        extra={'name': attr},
                        value=self._parse_expr_to_ir(delta)
                    )
                value = self._parse_expr_to_ir(node.value)
                return Statement(
                    type=BlockType.SET_VARIABLE,
                    extra={'name': attr},
                    value=value
                )
        elif isinstance(target, ast.Subscript):
            # self.items[index - 1] = value -> 替换列表第n项
            list_name = self._list_name_from_node(target.value)
            if list_name:
                index = self._normalize_index(self._parse_expr_to_ir(target.slice))
                item = self._parse_expr_to_ir(node.value)
                return Statement(type=BlockType.REPLACE_IN_LIST, value=index,
                                 extra={'name': list_name, 'item': item})

        return None

    def _parse_aug_assignment(self, node: ast.AugAssign) -> Optional[Statement]:
        """解析增强赋值语句 (+=)"""
        if isinstance(node.target, ast.Name):
            var_name = node.target.id
            value = self._parse_expr_to_ir(node.value)
            return Statement(
                type=BlockType.CHANGE_VARIABLE,
                extra={'name': var_name},
                value=value
            )
        elif isinstance(node.target, ast.Attribute):
            if isinstance(node.target.value, ast.Name) and node.target.value.id == 'self':
                attr = node.target.attr
                value = self._parse_expr_to_ir(node.value)
                return Statement(
                    type=BlockType.CHANGE_VARIABLE,
                    extra={'name': attr},
                    value=value
                )

        return None

    def _parse_for_loop(self, node: ast.For) -> Optional[Statement]:
        """解析for循环"""
        # for _repeat in range(N):
        if isinstance(node.iter, ast.Call):
            if isinstance(node.iter.func, ast.Name) and node.iter.func.id == 'range':
                times = self._parse_expr_to_ir(node.iter.args[0]) if node.iter.args else make_number(10)
                stmt = Statement(type=BlockType.REPEAT, value=times)

                # 解析循环体
                for body_stmt in node.body:
                    parsed = self._parse_statement(body_stmt)
                    if parsed:
                        stmt.body.append(parsed)

                return stmt

        # for _ in range(N):
        if isinstance(node.target, ast.Name) and node.target.id == '_':
            if isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name):
                if node.iter.func.id == 'range':
                    times = self._parse_expr_to_ir(node.iter.args[0]) if node.iter.args else make_number(10)
                    stmt = Statement(type=BlockType.REPEAT, value=times)
                    for body_stmt in node.body:
                        parsed = self._parse_statement(body_stmt)
                        if parsed:
                            stmt.body.append(parsed)
                    return stmt

        return None

    def _parse_while_loop(self, node: ast.While) -> Optional[Statement]:
        """解析while循环"""
        # while True:
        if isinstance(node.test, ast.Constant) and node.test.value == True:
            stmt = Statement(type=BlockType.FOREVER)
            for body_stmt in node.body:
                parsed = self._parse_statement(body_stmt)
                if parsed:
                    stmt.body.append(parsed)
            return stmt

        # while self._running:（Scratch的“重复执行”）
        if isinstance(node.test, ast.Attribute):
            if isinstance(node.test.value, ast.Name) and node.test.value.id == 'self' \
                    and node.test.attr == '_running':
                stmt = Statement(type=BlockType.FOREVER)
                for body_stmt in node.body:
                    parsed = self._parse_statement(body_stmt)
                    if parsed:
                        stmt.body.append(parsed)
                return stmt

        # while not (condition):
        if isinstance(node.test, ast.UnaryOp) and isinstance(node.test.op, ast.Not):
            condition = self._parse_expr_to_ir(node.test.operand)
            stmt = Statement(type=BlockType.REPEAT_UNTIL, condition=condition)
            for body_stmt in node.body:
                parsed = self._parse_statement(body_stmt)
                if parsed:
                    stmt.body.append(parsed)
            return stmt

        # while condition:
        condition = self._parse_expr_to_ir(node.test)
        stmt = Statement(type=BlockType.REPEAT_UNTIL, condition=Expr(ExprType.NOT, right=condition))
        for body_stmt in node.body:
            parsed = self._parse_statement(body_stmt)
            if parsed:
                stmt.body.append(parsed)
        return stmt

    def _parse_if(self, node: ast.If) -> Optional[Statement]:
        """解析if/else语句"""
        condition = self._parse_expr_to_ir(node.test)

        if node.orelse:
            stmt = Statement(type=BlockType.IF_ELSE, condition=condition)
            for body_stmt in node.body:
                parsed = self._parse_statement(body_stmt)
                if parsed:
                    stmt.body.append(parsed)
            for else_stmt in node.orelse:
                parsed = self._parse_statement(else_stmt)
                if parsed:
                    stmt.else_body.append(parsed)
            return stmt
        else:
            stmt = Statement(type=BlockType.IF, condition=condition)
            for body_stmt in node.body:
                parsed = self._parse_statement(body_stmt)
                if parsed:
                    stmt.body.append(parsed)
            return stmt

    def _parse_expr_to_ir(self, node: ast.AST) -> Expr:
        """将Python AST表达式转换为IR表达式"""
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool):
                return make_boolean(node.value)
            elif isinstance(node.value, (int, float)):
                return make_number(node.value)
            elif isinstance(node.value, str):
                return make_string(node.value)
            return make_string(str(node.value))

        elif isinstance(node, ast.Num):
            return make_number(node.n)

        elif isinstance(node, ast.Str):
            return make_string(node.s)

        elif isinstance(node, ast.NameConstant):
            if node.value is True:
                return make_boolean(True)
            elif node.value is False:
                return make_boolean(False)
            elif node.value is None:
                return make_string('None')

        elif isinstance(node, ast.Name):
            if node.id == 'self':
                return make_variable('self')
            if node.id in self._procedure_args:
                return Expr(ExprType.ARGUMENT, name=self._procedure_args[node.id])
            return make_variable(node.id)

        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == 'self':
                if node.attr in self.sprite.lists:
                    return Expr(ExprType.LIST_ACCESS, name=node.attr)
                if node.attr in self.sprite.variables:
                    return make_variable(node.attr)
                if node.attr == 'backdrop_number':
                    return make_property('_sprite_', 'backdrop #')
                if node.attr == 'backdrop_name':
                    return make_property('_sprite_', 'backdrop name')
                return make_property('_sprite_', node.attr)
            return make_property(node.value.id if isinstance(node.value, ast.Name) else 'unknown', node.attr)

        elif isinstance(node, ast.BinOp):
            # (str(a) + str(b)) 是连接到Scratch“连接”积木的生成形式
            if isinstance(node.op, ast.Add):
                left_str = self._str_call_arg(node.left)
                right_str = self._str_call_arg(node.right)
                if left_str is not None and right_str is not None:
                    return Expr(ExprType.JOIN,
                                left=self._parse_expr_to_ir(left_str),
                                right=self._parse_expr_to_ir(right_str))

            left = self._parse_expr_to_ir(node.left)
            right = self._parse_expr_to_ir(node.right)
            op_map = {
                ast.Add: '+', ast.Sub: '-',
                ast.Mult: '*', ast.Div: '/',
                ast.Mod: '%', ast.Pow: '**',
            }
            if isinstance(node.op, ast.Mod):
                # Scratch 有独立的“余数”积木
                return Expr(ExprType.MOD, left=left, right=right)
            op = op_map.get(type(node.op), '+')
            return make_binary_op(op, left, right)

        elif isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.Not):
                operand = self._parse_expr_to_ir(node.operand)
                return Expr(ExprType.NOT, right=operand)
            elif isinstance(node.op, ast.USub):
                operand = self._parse_expr_to_ir(node.operand)
                if operand.type == ExprType.NUMBER:
                    return make_number(-operand.value)
                return make_binary_op('-', make_number(0), operand)

        elif isinstance(node, ast.Compare):
            if len(node.ops) == 1 and len(node.comparators) == 1:
                left = self._parse_expr_to_ir(node.left)
                right = self._parse_expr_to_ir(node.comparators[0])
                op = node.ops[0]
                if isinstance(op, ast.Lt):
                    return Expr(ExprType.LESS_THAN, left=left, right=right)
                elif isinstance(op, ast.LtE):
                    # Scratch 没有 <=，用 not (a > b) 保持语义
                    return Expr(ExprType.NOT, right=Expr(
                        ExprType.GREATER_THAN, left=left, right=right))
                elif isinstance(op, ast.Gt):
                    return Expr(ExprType.GREATER_THAN, left=left, right=right)
                elif isinstance(op, ast.GtE):
                    # Scratch 没有 >=，用 not (a < b) 保持语义
                    return Expr(ExprType.NOT, right=Expr(
                        ExprType.LESS_THAN, left=left, right=right))
                elif isinstance(op, ast.Eq):
                    return Expr(ExprType.EQUAL, left=left, right=right)
                elif isinstance(op, ast.NotEq):
                    return Expr(ExprType.NOT, right=Expr(ExprType.EQUAL, left=left, right=right))

        elif isinstance(node, ast.BoolOp):
            values = [self._parse_expr_to_ir(v) for v in node.values]
            if isinstance(node.op, ast.And):
                result = values[0]
                for v in values[1:]:
                    result = Expr(ExprType.AND, left=result, right=v)
                return result
            elif isinstance(node.op, ast.Or):
                result = values[0]
                for v in values[1:]:
                    result = Expr(ExprType.OR, left=result, right=v)
                return result

        elif isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            # TurboWarp扩展表达式: self.extension(namespace, opcode, {inputs}, {fields})
            if func_name == 'extension' and isinstance(node.func, ast.Attribute) \
                    and isinstance(node.func.value, ast.Name) \
                    and node.func.value.id == 'self':
                parsed = self._parse_extension_arguments(node)
                if parsed:
                    namespace, opcode, inputs, fields = parsed
                    return Expr(ExprType.EXTENSION_CALL, name=opcode, extra={
                        'namespace': namespace, 'opcode': opcode,
                        'inputs': inputs, 'fields': fields})

            args = [self._parse_expr_to_ir(arg) for arg in node.args]

            # Scratch运行时辅助函数
            if func_name in ('_sc_num', '_sc_str', '_sc_bool',
                             '_sc_repeat_count', '_sc_wait_time'):
                return args[0] if args else make_number(0)
            elif func_name in ('_sc_add', '_sc_sub', '_sc_mul', '_sc_div', '_sc_mod'):
                if len(args) >= 2:
                    if func_name == '_sc_mod':
                        return Expr(ExprType.MOD, left=args[0], right=args[1])
                    op = {'_sc_add': '+', '_sc_sub': '-',
                          '_sc_mul': '*', '_sc_div': '/'}[func_name]
                    return make_binary_op(op, args[0], args[1])
            elif func_name == '_sc_eq':
                if len(args) >= 2:
                    return Expr(ExprType.EQUAL, left=args[0], right=args[1])
            elif func_name == '_sc_lt':
                if len(args) >= 2:
                    return Expr(ExprType.LESS_THAN, left=args[0], right=args[1])
            elif func_name == '_sc_gt':
                if len(args) >= 2:
                    return Expr(ExprType.GREATER_THAN, left=args[0], right=args[1])
            elif func_name == '_sc_and':
                if len(args) >= 2:
                    return Expr(ExprType.AND, left=args[0], right=args[1])
            elif func_name == '_sc_or':
                if len(args) >= 2:
                    return Expr(ExprType.OR, left=args[0], right=args[1])
            elif func_name == '_sc_not':
                if args:
                    return Expr(ExprType.NOT, right=args[0])
            elif func_name == '_sc_join':
                if len(args) >= 2:
                    return Expr(ExprType.JOIN, left=args[0], right=args[1])
            elif func_name == '_sc_letter_of':
                if len(args) >= 2:
                    return Expr(ExprType.LETTER_OF, left=args[0], right=args[1])
            elif func_name == '_sc_length':
                if args:
                    return Expr(ExprType.LENGTH_OF_STRING, right=args[0])
            elif func_name == '_sc_contains':
                if len(args) >= 2:
                    return Expr(ExprType.CONTAINS_STRING, left=args[0], right=args[1])
            elif func_name == '_sc_round':
                if args:
                    return Expr(ExprType.ROUND, right=args[0])
            elif func_name == '_sc_random':
                if len(args) >= 2:
                    return make_random(args[0], args[1])
            elif func_name == '_sc_mathop':
                if len(args) >= 2:
                    op_node = node.args[0]
                    op_name = op_node.value if isinstance(op_node, ast.Constant) else ''
                    op_name = str(op_name).lower().replace(' ', '')
                    math_types = {
                        'abs': ExprType.ABS, 'floor': ExprType.FLOOR,
                        'ceiling': ExprType.CEILING, 'sqrt': ExprType.SQRT,
                        'sin': ExprType.SIN, 'cos': ExprType.COS,
                        'tan': ExprType.TAN, 'asin': ExprType.ASIN,
                        'acos': ExprType.ACOS, 'atan': ExprType.ATAN,
                        'ln': ExprType.LN, 'log': ExprType.LOG,
                        'e^': ExprType.EXP, '10^': ExprType.POW10,
                    }
                    return Expr(math_types.get(op_name, ExprType.MATH_OP),
                                name=op_name, right=args[1])
            elif func_name == '_sc_item_of':
                if len(args) >= 2:
                    list_name = self._list_name_from_node(node.args[0])
                    if list_name:
                        return make_list_access(list_name, args[1])
            elif func_name == '_sc_list_item_number':
                if len(args) >= 2:
                    list_name = self._list_name_from_node(node.args[0])
                    if list_name:
                        return Expr(ExprType.ITEM_NUMBER_OF_LIST, name=list_name,
                                    left=args[1])
            elif func_name == '_sc_list_contains':
                if len(args) >= 2:
                    list_name = self._list_name_from_node(node.args[0])
                    if list_name:
                        return make_list_contains(list_name, args[1])
            elif func_name == '_sc_list_contents':
                if node.args:
                    list_name = self._list_name_from_node(node.args[0])
                    if list_name:
                        return Expr(ExprType.LIST_ACCESS, name=list_name)

            # 映射函数到表达式
            if func_name == 'random.randint' or func_name == 'randint':
                if len(args) >= 2:
                    return make_random(args[0], args[1])
            elif func_name == 'math.floor' or func_name == 'floor':
                if args:
                    return Expr(ExprType.FLOOR, right=args[0])
            elif func_name == 'math.ceil' or func_name == 'ceiling':
                if args:
                    return Expr(ExprType.CEILING, right=args[0])
            elif func_name == 'math.sqrt' or func_name == 'sqrt':
                if args:
                    return Expr(ExprType.SQRT, right=args[0])
            elif func_name == 'math.sin' or func_name == 'sin':
                if args:
                    return Expr(ExprType.SIN, right=args[0])
            elif func_name == 'math.cos' or func_name == 'cos':
                if args:
                    return Expr(ExprType.COS, right=args[0])
            elif func_name == 'abs':
                if args:
                    return Expr(ExprType.ABS, right=args[0])
            elif func_name == 'round':
                if args:
                    return Expr(ExprType.ROUND, right=args[0])
            elif func_name == 'list_item_number':
                if len(node.args) >= 2:
                    list_name = self._list_name_from_node(node.args[0])
                    if list_name:
                        return Expr(ExprType.ITEM_NUMBER_OF_LIST, name=list_name,
                                    left=self._parse_expr_to_ir(node.args[1]))
            elif func_name == 'len':
                if args:
                    if isinstance(node.args[0], ast.Attribute) \
                            and isinstance(node.args[0].value, ast.Name) \
                            and node.args[0].value.id == 'self' \
                            and node.args[0].attr in self.sprite.lists:
                        return Expr(ExprType.LENGTH_OF_LIST, name=node.args[0].attr)
                    return Expr(ExprType.LENGTH_OF_STRING, right=args[0])
            elif func_name == 'str':
                if args:
                    return args[0]
            elif func_name == 'int':
                if args:
                    return args[0]
            elif func_name == 'float':
                if args:
                    return args[0]
            elif func_name == 'key_pressed':
                return Expr(ExprType.FUNCTION_CALL, name='key_pressed', args=args)
            elif func_name == 'touching':
                return Expr(ExprType.FUNCTION_CALL, name='touching', args=args)
            elif func_name == 'distance_to':
                return Expr(ExprType.FUNCTION_CALL, name='distance_to', args=args)
            elif func_name == 'touching_color':
                if args:
                    return Expr(ExprType.TOUCHING_COLOR, left=args[0])
                return Expr(ExprType.TOUCHING_COLOR, left=make_string('#000000'))
            elif func_name == 'color_touching_color':
                left = args[0] if args else make_string('#000000')
                right = args[1] if len(args) > 1 else make_string('#000000')
                return Expr(ExprType.COLOR_TOUCHING_COLOR, left=left, right=right)
            elif func_name == 'sensing_of':
                if len(args) >= 2:
                    target = args[0].value if isinstance(args[0], Expr) else args[0]
                    prop = args[1].value if isinstance(args[1], Expr) else args[1]
                    return make_property(str(target), str(prop))
            elif func_name in ('get_counter', 'username'):
                return Expr(ExprType.FUNCTION_CALL, name=func_name, args=args)

            # 变量引用
            if func_name in self.sprite.variables:
                return make_variable(func_name)

            # 自制积木作为表达式（TurboWarp自定义reporter）
            if isinstance(node.func, ast.Attribute) \
                    and isinstance(node.func.value, ast.Name) \
                    and node.func.value.id == 'self':
                meta = dict(self._procedure_meta.get(func_name, {}))
                return Expr(ExprType.PROCEDURE_CALL, name=func_name,
                            args=args, extra=meta)

            return make_string(f"# function: {func_name}")

        elif isinstance(node, ast.List):
            elements = [self._parse_expr_to_ir(e) for e in node.elts]
            return make_string(str([e.value if hasattr(e, 'value') else str(e) for e in elements]))

        elif isinstance(node, ast.Subscript):
            # list[index]：生成代码是 self.items[index - 1]
            list_name = None
            if isinstance(node.value, ast.Attribute) \
                    and isinstance(node.value.value, ast.Name) \
                    and node.value.value.id == 'self':
                list_name = node.value.attr
            elif isinstance(node.value, ast.Name):
                list_name = node.value.id
            if list_name is not None:
                index = self._parse_expr_to_ir(node.slice)
                return make_list_access(list_name, self._normalize_index(index))

        return make_string("# unknown expression")

    def _str_call_arg(self, node: ast.AST) -> Optional[ast.AST]:
        """如果节点是 str(x)，返回x，否则返回None"""
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == 'str' and len(node.args) == 1:
            return node.args[0]
        return None

    def _self_add_delta(self, node: ast.AST, attr: str) -> Optional[ast.AST]:
        """识别 self.attr = _sc_add(self.attr, delta)，返回delta节点"""
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == '_sc_add' and len(node.args) == 2:
            first = node.args[0]
            if isinstance(first, ast.Attribute) and isinstance(first.value, ast.Name) \
                    and first.value.id == 'self' and first.attr == attr:
                return node.args[1]
        return None

    def _normalize_index(self, expr: Expr) -> Expr:
        """把Python的 (index - 1) 还原为Scratch的1起始索引"""
        if isinstance(expr, Expr) and expr.type == ExprType.BINARY_OP \
                and expr.name == '-' and expr.right \
                and expr.right.type == ExprType.NUMBER \
                and expr.right.value == 1:
            return expr.left
        return expr

    def _eval_expr(self, node: ast.AST) -> Any:
        """求值Python AST表达式为Python值"""
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, ast.Str):
            return node.s
        elif isinstance(node, ast.NameConstant):
            return node.value
        elif isinstance(node, ast.List):
            return [self._eval_expr(e) for e in node.elts]
        elif isinstance(node, ast.Name):
            return node.id
        return None


def parse_python_code(code: str, sprite_name: str = "Sprite") -> SpriteIR:
    """便捷函数：解析Python代码"""
    parser = PythonParser()
    return parser.parse_code(code, sprite_name)


def parse_python_file(file_path: str, sprite_name: str = "Sprite") -> SpriteIR:
    """从文件解析Python代码"""
    parser = PythonParser()
    return parser.parse_file(file_path, sprite_name)


def python_to_project(sprite: SpriteIR) -> ProjectIR:
    """将SpriteIR包装为ProjectIR"""
    project = ProjectIR()
    project.add_sprite(sprite)
    return project
