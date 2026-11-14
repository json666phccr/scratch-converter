#!/usr/bin/env python3
"""
Scratch 3.0 JSON 写入器
将中间表示 (IR) 转换回 Scratch 3.0 project.json 格式
"""

import json
import math
from typing import Dict, List, Any, Optional, Tuple
import uuid

from ir import (
    BlockType, ExprType, Expr, Statement, SpriteIR, ProjectIR,
)


# ===================== BlockType 到操作码映射 =====================

BLOCK_TYPE_TO_OPCODE: Dict[BlockType, str] = {
    BlockType.WHEN_FLAG_CLICKED: 'event_whenflagclicked',
    BlockType.WHEN_KEY_PRESSED: 'event_whenkeypressed',
    BlockType.WHEN_THIS_SPRITE_CLICKED: 'event_whenthisspriteclicked',
    BlockType.WHEN_BACKDROP_SWITCHES: 'event_whenbackdropswitchesto',
    BlockType.WHEN_BROADCAST_RECEIVED: 'event_whenbroadcastreceived',

    BlockType.MOVE_STEPS: 'motion_movesteps',
    BlockType.TURN_RIGHT: 'motion_turnright',
    BlockType.TURN_LEFT: 'motion_turnleft',
    BlockType.GO_TO_XY: 'motion_gotoxy',
    BlockType.GO_TO_RANDOM: 'motion_goto',
    BlockType.GLIDE_SECS_TO: 'motion_glidesecstoxy',
    BlockType.GLIDE_TO: 'motion_glideto',
    BlockType.POINT_IN_DIRECTION: 'motion_pointindirection',
    BlockType.POINT_TOWARDS: 'motion_pointtowards',
    BlockType.CHANGE_X: 'motion_changexby',
    BlockType.SET_X: 'motion_setx',
    BlockType.CHANGE_Y: 'motion_changeyby',
    BlockType.SET_Y: 'motion_sety',
    BlockType.IF_ON_EDGE_BOUNCE: 'motion_ifonedgebounce',
    BlockType.SET_ROTATION_STYLE: 'motion_setrotationstyle',

    BlockType.SAY: 'looks_say',
    BlockType.SAY_FOR_SECS: 'looks_sayforsecs',
    BlockType.THINK: 'looks_think',
    BlockType.THINK_FOR_SECS: 'looks_thinkforsecs',
    BlockType.SHOW: 'looks_show',
    BlockType.HIDE: 'looks_hide',
    BlockType.SWITCH_COSTUME: 'looks_switchcostumeto',
    BlockType.NEXT_COSTUME: 'looks_nextcostume',
    BlockType.SWITCH_BACKDROP: 'looks_switchbackdropto',
    BlockType.SWITCH_BACKDROP_AND_WAIT: 'looks_switchbackdroptoandwait',
    BlockType.NEXT_BACKDROP: 'looks_nextbackdrop',
    BlockType.CHANGE_SIZE: 'looks_changesizeby',
    BlockType.SET_SIZE: 'looks_setsizeto',
    BlockType.CHANGE_EFFECT: 'looks_changeeffectby',
    BlockType.SET_EFFECT: 'looks_seteffectto',
    BlockType.CLEAR_EFFECTS: 'looks_cleareffects',
    BlockType.GO_TO_FRONT: 'looks_gotofrontback',
    BlockType.GO_TO_BACK: 'looks_gobacklayers',
    BlockType.GO_FORWARD_LAYERS: 'looks_goforwardbackwardlayers',

    BlockType.PLAY_SOUND: 'sound_play',
    BlockType.PLAY_SOUND_UNTIL_DONE: 'sound_playuntildone',
    BlockType.STOP_ALL_SOUNDS: 'sound_stopallsounds',
    BlockType.CHANGE_VOLUME: 'sound_changevolumeby',
    BlockType.SET_VOLUME: 'sound_setvolumeto',
    BlockType.SET_SOUND_EFFECT: 'sound_seteffectto',
    BlockType.CHANGE_SOUND_EFFECT: 'sound_changeeffectby',
    BlockType.CLEAR_SOUND_EFFECTS: 'sound_cleareffects',

    BlockType.WAIT: 'control_wait',
    BlockType.REPEAT: 'control_repeat',
    BlockType.FOREVER: 'control_forever',
    BlockType.IF: 'control_if',
    BlockType.IF_ELSE: 'control_if_else',
    BlockType.WAIT_UNTIL: 'control_wait_until',
    BlockType.REPEAT_UNTIL: 'control_repeat_until',
    BlockType.FOR_EACH: 'control_for_each',
    BlockType.ALL_AT_ONCE: 'control_all_at_once',
    BlockType.INCR_COUNTER: 'control_incr_counter',
    BlockType.CLEAR_COUNTER: 'control_clear_counter',
    BlockType.STOP: 'control_stop',
    BlockType.START_AS_CLONE: 'control_start_as_clone',
    BlockType.CREATE_CLONE_OF: 'control_create_clone_of',
    BlockType.DELETE_THIS_CLONE: 'control_delete_this_clone',

    BlockType.TOUCHING_OBJECT: 'sensing_touchingobject',
    BlockType.TOUCHING_COLOR: 'sensing_touchingcolor',
    BlockType.COLOR_TOUCHING_COLOR: 'sensing_coloristouchingcolor',
    BlockType.DISTANCE_TO: 'sensing_distanceto',
    BlockType.ASK_AND_WAIT: 'sensing_askandwait',
    BlockType.KEY_PRESSED: 'sensing_keypressed',
    BlockType.MOUSE_DOWN: 'sensing_mousedown',
    BlockType.SET_DRAG_MODE: 'sensing_setdragmode',
    BlockType.RESET_TIMER: 'sensing_resettimer',
    BlockType.OF_PROPERTY: 'sensing_of',
    BlockType.CURRENT: 'sensing_current',

    BlockType.SET_VARIABLE: 'data_setvariableto',
    BlockType.CHANGE_VARIABLE: 'data_changevariableby',
    BlockType.SHOW_VARIABLE: 'data_showvariable',
    BlockType.HIDE_VARIABLE: 'data_hidevariable',
    BlockType.ADD_TO_LIST: 'data_addtolist',
    BlockType.DELETE_FROM_LIST: 'data_deleteoflist',
    BlockType.DELETE_ALL_FROM_LIST: 'data_deletealloflist',
    BlockType.INSERT_IN_LIST: 'data_insertatlist',
    BlockType.REPLACE_IN_LIST: 'data_replaceitemoflist',
    BlockType.SHOW_LIST: 'data_showlist',
    BlockType.HIDE_LIST: 'data_hidelist',

    BlockType.BROADCAST: 'event_broadcast',
    BlockType.BROADCAST_AND_WAIT: 'event_broadcastandwait',

    BlockType.PROCEDURE_DEFINE: 'procedures_definition',
    BlockType.PROCEDURE_CALL: 'procedures_call',
    BlockType.PROCEDURE_RETURN: 'procedures_return',
}


class ScratchWriter:
    """将ProjectIR写入Scratch JSON格式"""

    def __init__(self):
        self.all_blocks: Dict[str, Dict] = {}
        self.block_counter = 0

    def new_block_id(self) -> str:
        """生成唯一的块ID"""
        self.block_counter += 1
        return f"block_{self.block_counter}"

    @staticmethod
    def _build_proccode(proc_name: str, arg_count: int,
                        arg_types: Optional[List[str]] = None) -> str:
        """由函数名和参数类型构造proccode"""
        if arg_count <= 0:
            return proc_name
        types = list(arg_types or [])
        while len(types) < arg_count:
            types.append('s')
        placeholders = ['%b' if item == 'b' else '%n' if item == 'n' else '%s'
                        for item in types[:arg_count]]
        return proc_name + ' ' + ' '.join(placeholders)

    @staticmethod
    def _chain_tail(first_id: str, blocks: Dict[str, Dict]) -> str:
        """返回一条next链的最后一个块ID"""
        current = first_id
        visited = set()
        while current in blocks and current not in visited:
            visited.add(current)
            nxt = blocks[current].get("next")
            if not nxt:
                break
            current = nxt
        return current

    def _walk_statements(self, statements: List[Statement]):
        """递归遍历语句树（body/else_body/next）"""
        seen = set()

        def walk(stmt):
            if stmt is None or id(stmt) in seen:
                return
            seen.add(id(stmt))
            yield stmt
            for child in stmt.body:
                yield from walk(child)
            for child in stmt.else_body:
                yield from walk(child)
            yield from walk(stmt.next)

        for stmt in statements:
            yield from walk(stmt)

    def _collect_broadcast_names(self, project: ProjectIR) -> List[str]:
        """收集项目中使用的广播名"""
        names = set()
        for sprite in project.sprites:
            for name in sprite.broadcasts:
                if name:
                    names.add(str(name))
            for stmt in self._walk_statements(sprite.statements):
                if stmt.type in (BlockType.WHEN_BROADCAST_RECEIVED,
                                 BlockType.BROADCAST,
                                 BlockType.BROADCAST_AND_WAIT) and stmt.value:
                    value = stmt.value.to_scratch_value()
                    if value:
                        names.add(str(value))
        return sorted(names)

    def _collect_var_list_names(self, statements: List[Statement]):
        """收集语句中引用到的变量和列表名"""
        var_names = set()
        list_names = set()

        def walk_expr(expr: Optional[Expr]):
            if expr is None:
                return
            if expr.type == ExprType.VARIABLE:
                var_names.add(expr.name)
            elif expr.type in (ExprType.LIST_ACCESS, ExprType.ITEM_OF_LIST,
                               ExprType.ITEM_NUMBER_OF_LIST,
                               ExprType.LENGTH_OF_LIST, ExprType.LIST_CONTAINS):
                list_names.add(expr.name)
            walk_expr(expr.left)
            walk_expr(expr.right)
            for child in expr.children:
                walk_expr(child)
            for arg in expr.args:
                walk_expr(arg)

        var_block_types = {
            BlockType.SET_VARIABLE, BlockType.CHANGE_VARIABLE,
            BlockType.SHOW_VARIABLE, BlockType.HIDE_VARIABLE,
        }
        list_block_types = {
            BlockType.ADD_TO_LIST, BlockType.DELETE_FROM_LIST,
            BlockType.DELETE_ALL_FROM_LIST, BlockType.INSERT_IN_LIST,
            BlockType.REPLACE_IN_LIST, BlockType.SHOW_LIST, BlockType.HIDE_LIST,
        }

        for stmt in self._walk_statements(statements):
            if stmt.type in var_block_types:
                var_names.add(stmt.extra.get('name', 'var'))
            elif stmt.type in list_block_types:
                list_names.add(stmt.extra.get('name', 'list'))
            walk_expr(stmt.value)
            walk_expr(stmt.condition)
            walk_expr(stmt.target)
            walk_expr(stmt.expr)
            for value in stmt.extra.values():
                if isinstance(value, Expr):
                    walk_expr(value)

        return var_names, list_names

    def write_project(self, project: ProjectIR) -> Dict:
        """将ProjectIR转换为Scratch项目JSON"""
        self.all_blocks = {}
        self.block_counter = 0

        targets = []
        for sprite in project.sprites:
            target = self.write_sprite(sprite)
            targets.append(target)

        # Scratch项目必须且只能有一个舞台，且必须位于targets[0]
        stage_index = next((i for i, item in enumerate(targets)
                            if item.get("isStage")), None)
        if stage_index is None:
            stage = SpriteIR(name="Stage", is_stage=True)
            targets.insert(0, self.write_sprite(stage))
        elif stage_index != 0:
            targets.insert(0, targets.pop(stage_index))
        # 只保留第一个舞台
        unique_targets = []
        stage_added = False
        for item in targets:
            if item.get("isStage"):
                if not stage_added:
                    unique_targets.append(item)
                    stage_added = True
            else:
                unique_targets.append(item)
        targets = unique_targets

        # 广播属于项目级资源，必须登记在舞台的broadcasts里
        stage_target = next(t for t in targets if t.get("isStage"))
        for name in self._collect_broadcast_names(project):
            stage_target["broadcasts"].setdefault(f"bc_{name}", name)

        return {
            "targets": targets,
            "monitors": [],
            "extensions": self._collect_extension_names(project),
            "meta": project.meta or {
                "semver": "3.0.0",
                "vm": "0.2.0-prerelease.20190521144711",
                "agent": ""
            }
        }

    def _collect_extension_names(self, project: ProjectIR) -> List[str]:
        """收集TurboWarp/Scratch扩展ID，写回project.json的extensions列表"""
        names: List[str] = []

        def add(name):
            if name and name not in names:
                names.append(name)

        def walk_expr(expr: Optional[Expr]):
            if not isinstance(expr, Expr):
                return
            if expr.type == ExprType.EXTENSION_CALL:
                add(expr.extra.get('namespace'))
            walk_expr(expr.left)
            walk_expr(expr.right)
            for child in expr.children:
                walk_expr(child)
            for arg in expr.args:
                walk_expr(arg)
            for value in expr.extra.values():
                if isinstance(value, Expr):
                    walk_expr(value)
                elif isinstance(value, (list, tuple)):
                    for item in value:
                        if isinstance(item, Expr):
                            walk_expr(item)
                        elif isinstance(item, tuple) and len(item) == 2:
                            walk_expr(item[1])

        seen = set()

        def walk_stmt(stmt: Optional[Statement]):
            if not isinstance(stmt, Statement) or id(stmt) in seen:
                return
            seen.add(id(stmt))
            if stmt.type == BlockType.EXTENSION:
                add(stmt.extra.get('namespace'))
            for field in ('value', 'condition', 'target', 'expr'):
                walk_expr(getattr(stmt, field, None))
            for value in stmt.extra.values():
                if isinstance(value, Expr):
                    walk_expr(value)
                elif isinstance(value, (list, tuple)):
                    for item in value:
                        if isinstance(item, Expr):
                            walk_expr(item)
                        elif isinstance(item, tuple) and len(item) == 2:
                            walk_expr(item[1])
            for child in stmt.body:
                walk_stmt(child)
            for child in stmt.else_body:
                walk_stmt(child)
            walk_stmt(stmt.next)

        for sprite in project.sprites:
            for stmt in sprite.statements:
                walk_stmt(stmt)
        return names

    def write_sprite(self, sprite: SpriteIR) -> Dict:
        """将SpriteIR转换为Scratch目标JSON"""
        # 每个精灵必须从空的子块集合开始，否则会把上一个精灵的块重复写进来
        self.all_blocks = {}

        blocks = {}
        for index, stmt in enumerate(sprite.statements):
            block_dict = self.write_statement(stmt, None)
            blocks.update(block_dict)
            # 顶层脚本（事件帽子/自制积木定义）必须带 topLevel 与坐标，
            # 否则 Scratch/TurboWarp 会把它们当成孤儿块不显示。
            top_id = next((bid for bid, data in block_dict.items()
                           if data.get("topLevel")), None)
            if top_id:
                block_dict[top_id]["x"] = 50 + (index % 2) * 560
                block_dict[top_id]["y"] = 50 + (index // 2) * 420
        # 合并子堆栈中创建的块
        blocks.update(self.all_blocks)

        # 收集脚本中引用但未在IR里声明的变量/列表，避免生成悬空引用
        used_vars, used_lists = self._collect_var_list_names(sprite.statements)

        # 构建变量字典
        variables = {}
        for name, value in sprite.variables.items():
            var_id = f"var_{name}"
            variables[var_id] = [name, value]
        for name in used_vars:
            var_id = f"var_{name}"
            if var_id not in variables:
                variables[var_id] = [name, 0]

        # 构建列表字典
        lists = {}
        for name, items in sprite.lists.items():
            list_id = f"list_{name}"
            lists[list_id] = [name, items]
        for name in used_lists:
            list_id = f"list_{name}"
            if list_id not in lists:
                lists[list_id] = [name, []]

        # 构建广播字典
        broadcasts = {}
        for bc in sprite.broadcasts:
            bc_id = f"bc_{bc}"
            broadcasts[bc_id] = bc

        result = {
            "isStage": sprite.is_stage,
            "name": sprite.name,
            "variables": variables,
            "lists": lists,
            "broadcasts": broadcasts,
            "blocks": blocks,
            "comments": {},
            "currentCostume": 0,
            "costumes": sprite.costumes or [],
            "sounds": sprite.sounds or [],
        }

        if not sprite.is_stage:
            result.update({
                "visible": sprite.visible,
                "x": sprite.x,
                "y": sprite.y,
                "size": sprite.size,
                "direction": sprite.direction,
                "draggable": sprite.draggable,
                "rotationStyle": sprite.rotation_style,
                "volume": 100,
                "layerOrder": 1,
            })
        else:
            result.update({
                "volume": 100,
                "layerOrder": 0,
                "tempo": 60,
                "videoTransparency": 50,
                "videoState": "on",
                "textToSpeechLanguage": None,
            })

        return result

    def write_statement(self, stmt: Statement, parent_id: Optional[str]) -> Dict[str, Dict]:
        """将Statement转换为Scratch块字典，返回 {block_id: block_data}"""
        blocks = {}

        block_id = self.new_block_id()
        opcode = BLOCK_TYPE_TO_OPCODE.get(stmt.type, 'unknown')

        block_data = {
            "opcode": opcode,
            "next": None,
            "parent": parent_id,
            "inputs": {},
            "fields": {},
            "shadow": False,
            "topLevel": False,
        }

        # 根据块类型设置输入和字段
        if stmt.type == BlockType.WHEN_FLAG_CLICKED:
            block_data["topLevel"] = True
            block_data["x"] = 50
            block_data["y"] = 50

        elif stmt.type == BlockType.WHEN_KEY_PRESSED:
            block_data["topLevel"] = True
            block_data["x"] = 50
            block_data["y"] = 50
            key = stmt.extra.get('key', 'space')
            block_data["fields"]["KEY_OPTION"] = [key, None]

        elif stmt.type == BlockType.WHEN_BROADCAST_RECEIVED:
            block_data["topLevel"] = True
            block_data["x"] = 50
            block_data["y"] = 50
            bc_name = stmt.value.to_scratch_value() if stmt.value else ''
            bc_id = f"bc_{bc_name}"
            block_data["fields"]["BROADCAST_OPTION"] = [bc_name, bc_id]

        elif stmt.type in (BlockType.WHEN_THIS_SPRITE_CLICKED,
                           BlockType.START_AS_CLONE,
                           BlockType.WHEN_BACKDROP_SWITCHES,
                           BlockType.WHEN_GREATER_THAN,
                           BlockType.WHEN_LOUDNESS,
                           BlockType.WHEN_TIMER):
            block_data["topLevel"] = True
            block_data["x"] = 50
            block_data["y"] = 50

        elif stmt.type == BlockType.MOVE_STEPS:
            block_data["inputs"]["STEPS"] = self.write_number_input(stmt.value, 10)

        elif stmt.type == BlockType.TURN_RIGHT:
            block_data["inputs"]["DEGREES"] = self.write_number_input(stmt.value, 15)

        elif stmt.type == BlockType.TURN_LEFT:
            block_data["inputs"]["DEGREES"] = self.write_number_input(stmt.value, 15)

        elif stmt.type == BlockType.GO_TO_XY:
            block_data["inputs"]["X"] = self.write_number_input(stmt.extra.get('x'), 0)
            block_data["inputs"]["Y"] = self.write_number_input(stmt.extra.get('y'), 0)

        elif stmt.type == BlockType.GLIDE_SECS_TO:
            block_data["inputs"]["SECS"] = self.write_number_input(stmt.value, 1)
            block_data["inputs"]["X"] = self.write_number_input(stmt.extra.get('x'), 0)
            block_data["inputs"]["Y"] = self.write_number_input(stmt.extra.get('y'), 0)

        elif stmt.type == BlockType.GO_TO_RANDOM:
            block_data["inputs"]["TO"] = self.write_menu_input(
                "motion_goto_menu", "TO",
                stmt.extra.get('target', '_random_'), block_id)

        elif stmt.type == BlockType.GLIDE_TO:
            block_data["inputs"]["SECS"] = self.write_number_input(stmt.value, 1)
            block_data["inputs"]["TO"] = self.write_menu_input(
                "motion_glideto_menu", "TO",
                stmt.extra.get('target', '_random_'), block_id)

        elif stmt.type == BlockType.POINT_IN_DIRECTION:
            block_data["inputs"]["DIRECTION"] = self.write_number_input(stmt.value, 90)

        elif stmt.type == BlockType.POINT_TOWARDS:
            block_data["inputs"]["TOWARDS"] = self.write_menu_input(
                "motion_pointtowards_menu", "TOWARDS",
                stmt.extra.get('target', '_mouse_'), block_id)

        elif stmt.type == BlockType.SET_ROTATION_STYLE:
            block_data["fields"]["STYLE"] = [
                stmt.extra.get('style', 'all around'), None]

        elif stmt.type == BlockType.CHANGE_X:
            block_data["inputs"]["DX"] = self.write_number_input(stmt.value, 10)

        elif stmt.type == BlockType.SET_X:
            block_data["inputs"]["X"] = self.write_number_input(stmt.value, 0)

        elif stmt.type == BlockType.CHANGE_Y:
            block_data["inputs"]["DY"] = self.write_number_input(stmt.value, 10)

        elif stmt.type == BlockType.SET_Y:
            block_data["inputs"]["Y"] = self.write_number_input(stmt.value, 0)

        elif stmt.type == BlockType.SAY:
            block_data["inputs"]["MESSAGE"] = self.write_string_input(stmt.value, '')

        elif stmt.type == BlockType.SAY_FOR_SECS:
            block_data["inputs"]["MESSAGE"] = self.write_string_input(
                stmt.extra.get('message'), '')
            block_data["inputs"]["SECS"] = self.write_number_input(stmt.value, 1)

        elif stmt.type == BlockType.THINK:
            block_data["inputs"]["MESSAGE"] = self.write_string_input(stmt.value, '')

        elif stmt.type == BlockType.THINK_FOR_SECS:
            block_data["inputs"]["MESSAGE"] = self.write_string_input(
                stmt.extra.get('message'), '')
            block_data["inputs"]["SECS"] = self.write_number_input(stmt.value, 1)

        elif stmt.type == BlockType.SHOW:
            pass

        elif stmt.type == BlockType.HIDE:
            pass

        elif stmt.type == BlockType.SWITCH_COSTUME:
            if stmt.value is not None and stmt.value.type != ExprType.STRING:
                block_data["inputs"]["COSTUME"] = self.write_any_input(stmt.value)
            else:
                cost_name = stmt.value.to_scratch_value() if stmt.value else 'costume1'
                block_data["inputs"]["COSTUME"] = self.write_menu_input(
                    "looks_costume", "COSTUME", cost_name, block_id)

        elif stmt.type == BlockType.NEXT_COSTUME:
            pass

        elif stmt.type in (BlockType.SWITCH_BACKDROP,
                           BlockType.SWITCH_BACKDROP_AND_WAIT):
            if stmt.value is not None and stmt.value.type != ExprType.STRING:
                block_data["inputs"]["BACKDROP"] = self.write_any_input(stmt.value)
            else:
                backdrop = stmt.value.to_scratch_value() if stmt.value else 'backdrop1'
                block_data["inputs"]["BACKDROP"] = self.write_menu_input(
                    "looks_backdrops", "BACKDROP", backdrop, block_id)

        elif stmt.type == BlockType.NEXT_BACKDROP:
            pass

        elif stmt.type in (BlockType.GO_TO_FRONT, BlockType.GO_TO_BACK):
            block_data["fields"]["FRONT_BACK"] = [
                stmt.extra.get('where', 'front'), None]

        elif stmt.type in (BlockType.GO_FORWARD_LAYERS,
                           BlockType.GO_BACKWARD_LAYERS):
            block_data["fields"]["FORWARD_BACKWARD"] = [
                stmt.extra.get('direction', 'forward'), None]
            block_data["inputs"]["NUM"] = self.write_number_input(stmt.value, 1)

        elif stmt.type == BlockType.CHANGE_SIZE:
            block_data["inputs"]["CHANGE"] = self.write_number_input(stmt.value, 10)

        elif stmt.type == BlockType.SET_SIZE:
            block_data["inputs"]["SIZE"] = self.write_number_input(stmt.value, 100)

        elif stmt.type == BlockType.CHANGE_EFFECT:
            effect = stmt.extra.get('effect', 'color')
            block_data["fields"]["EFFECT"] = [effect, None]
            block_data["inputs"]["CHANGE"] = self.write_number_input(stmt.value, 25)

        elif stmt.type == BlockType.SET_EFFECT:
            effect = stmt.extra.get('effect', 'color')
            block_data["fields"]["EFFECT"] = [effect, None]
            block_data["inputs"]["VALUE"] = self.write_number_input(stmt.value, 100)

        elif stmt.type == BlockType.CLEAR_EFFECTS:
            pass

        elif stmt.type == BlockType.PLAY_SOUND:
            if stmt.value is not None and stmt.value.type != ExprType.STRING:
                block_data["inputs"]["SOUND_MENU"] = self.write_any_input(stmt.value)
            else:
                sound_name = stmt.value.to_scratch_value() if stmt.value else 'sound1'
                block_data["inputs"]["SOUND_MENU"] = self.write_menu_input(
                    "sound_sounds_menu", "SOUND_MENU", sound_name, block_id)

        elif stmt.type == BlockType.PLAY_SOUND_UNTIL_DONE:
            if stmt.value is not None and stmt.value.type != ExprType.STRING:
                block_data["inputs"]["SOUND_MENU"] = self.write_any_input(stmt.value)
            else:
                sound_name = stmt.value.to_scratch_value() if stmt.value else 'sound1'
                block_data["inputs"]["SOUND_MENU"] = self.write_menu_input(
                    "sound_sounds_menu", "SOUND_MENU", sound_name, block_id)

        elif stmt.type in (BlockType.SET_SOUND_EFFECT,
                           BlockType.CHANGE_SOUND_EFFECT):
            block_data["fields"]["SOUND_EFFECT"] = [
                stmt.extra.get('effect', 'PITCH'), None]
            block_data["inputs"]["VALUE"] = self.write_number_input(stmt.value, 10)

        elif stmt.type == BlockType.CLEAR_SOUND_EFFECTS:
            pass

        elif stmt.type == BlockType.STOP_ALL_SOUNDS:
            pass

        elif stmt.type == BlockType.CHANGE_VOLUME:
            block_data["inputs"]["VOLUME"] = self.write_number_input(stmt.value, 10)

        elif stmt.type == BlockType.SET_VOLUME:
            block_data["inputs"]["VOLUME"] = self.write_number_input(stmt.value, 100)

        elif stmt.type == BlockType.IF_ON_EDGE_BOUNCE:
            pass

        elif stmt.type == BlockType.WAIT:
            block_data["inputs"]["DURATION"] = self.write_number_input(stmt.value, 1)

        elif stmt.type == BlockType.REPEAT:
            block_data["inputs"]["TIMES"] = self.write_number_input(stmt.value, 10)
            substack_id = self.write_substack(stmt.body)
            if substack_id:
                block_data["inputs"]["SUBSTACK"] = [2, substack_id]

        elif stmt.type == BlockType.FOREVER:
            substack_id = self.write_substack(stmt.body)
            if substack_id:
                block_data["inputs"]["SUBSTACK"] = [2, substack_id]

        elif stmt.type == BlockType.IF:
            block_data["inputs"]["CONDITION"] = self.write_boolean_input(stmt.condition)
            substack_id = self.write_substack(stmt.body)
            if substack_id:
                block_data["inputs"]["SUBSTACK"] = [2, substack_id]

        elif stmt.type == BlockType.IF_ELSE:
            block_data["inputs"]["CONDITION"] = self.write_boolean_input(stmt.condition)
            substack_id = self.write_substack(stmt.body)
            if substack_id:
                block_data["inputs"]["SUBSTACK"] = [2, substack_id]
            substack2_id = self.write_substack(stmt.else_body)
            if substack2_id:
                block_data["inputs"]["SUBSTACK2"] = [2, substack2_id]

        elif stmt.type == BlockType.WAIT_UNTIL:
            block_data["inputs"]["CONDITION"] = self.write_boolean_input(stmt.condition)

        elif stmt.type == BlockType.REPEAT_UNTIL:
            block_data["inputs"]["CONDITION"] = self.write_boolean_input(stmt.condition)
            substack_id = self.write_substack(stmt.body)
            if substack_id:
                block_data["inputs"]["SUBSTACK"] = [2, substack_id]

        elif stmt.type == BlockType.FOR_EACH:
            name = stmt.extra.get('name', 'item')
            block_data["fields"]["VARIABLE"] = [name, f"var_{name}"]
            block_data["inputs"]["VALUE"] = self.write_any_input(stmt.value)
            substack_id = self.write_substack(stmt.body)
            if substack_id:
                block_data["inputs"]["SUBSTACK"] = [2, substack_id]

        elif stmt.type == BlockType.ALL_AT_ONCE:
            substack_id = self.write_substack(stmt.body)
            if substack_id:
                block_data["inputs"]["SUBSTACK"] = [2, substack_id]

        elif stmt.type in (BlockType.INCR_COUNTER, BlockType.CLEAR_COUNTER):
            pass

        elif stmt.type == BlockType.STOP:
            option = stmt.extra.get('option', 'all')
            block_data["fields"]["STOP_OPTION"] = [option, None]
            block_data["mutation"] = {
                "tagName": "mutation",
                "children": [],
                "hasnext": "true" if option.startswith("other scripts") else "false"
            }

        elif stmt.type == BlockType.SET_DRAG_MODE:
            block_data["fields"]["DRAG_MODE"] = [
                stmt.extra.get('mode', 'draggable'), None]

        elif stmt.type == BlockType.SET_VARIABLE:
            var_name = stmt.extra.get('name', 'var')
            var_id = stmt.extra.get('id', f"var_{var_name}")
            block_data["fields"]["VARIABLE"] = [var_name, var_id]
            block_data["inputs"]["VALUE"] = self.write_any_input(stmt.value)

        elif stmt.type == BlockType.CHANGE_VARIABLE:
            var_name = stmt.extra.get('name', 'var')
            var_id = stmt.extra.get('id', f"var_{var_name}")
            block_data["fields"]["VARIABLE"] = [var_name, var_id]
            block_data["inputs"]["VALUE"] = self.write_any_input(stmt.value)

        elif stmt.type == BlockType.SHOW_VARIABLE:
            var_name = stmt.extra.get('name', 'var')
            block_data["fields"]["VARIABLE"] = [var_name, f"var_{var_name}"]

        elif stmt.type == BlockType.HIDE_VARIABLE:
            var_name = stmt.extra.get('name', 'var')
            block_data["fields"]["VARIABLE"] = [var_name, f"var_{var_name}"]

        elif stmt.type == BlockType.ADD_TO_LIST:
            list_name = stmt.extra.get('name', 'list')
            block_data["fields"]["LIST"] = [list_name, f"list_{list_name}"]
            block_data["inputs"]["ITEM"] = self.write_any_input(stmt.value)

        elif stmt.type == BlockType.DELETE_FROM_LIST:
            list_name = stmt.extra.get('name', 'list')
            block_data["fields"]["LIST"] = [list_name, f"list_{list_name}"]
            block_data["inputs"]["INDEX"] = self.write_any_input(stmt.value)

        elif stmt.type == BlockType.DELETE_ALL_FROM_LIST:
            list_name = stmt.extra.get('name', 'list')
            block_data["fields"]["LIST"] = [list_name, f"list_{list_name}"]

        elif stmt.type == BlockType.INSERT_IN_LIST:
            list_name = stmt.extra.get('name', 'list')
            block_data["fields"]["LIST"] = [list_name, f"list_{list_name}"]
            block_data["inputs"]["ITEM"] = self.write_any_input(
                stmt.extra.get('item'))
            block_data["inputs"]["INDEX"] = self.write_any_input(stmt.value)

        elif stmt.type == BlockType.REPLACE_IN_LIST:
            list_name = stmt.extra.get('name', 'list')
            block_data["fields"]["LIST"] = [list_name, f"list_{list_name}"]
            block_data["inputs"]["ITEM"] = self.write_any_input(
                stmt.extra.get('item'))
            block_data["inputs"]["INDEX"] = self.write_any_input(stmt.value)

        elif stmt.type == BlockType.SHOW_LIST:
            list_name = stmt.extra.get('name', 'list')
            block_data["fields"]["LIST"] = [list_name, f"list_{list_name}"]

        elif stmt.type == BlockType.HIDE_LIST:
            list_name = stmt.extra.get('name', 'list')
            block_data["fields"]["LIST"] = [list_name, f"list_{list_name}"]

        elif stmt.type == BlockType.BROADCAST:
            bc_name = stmt.value.to_scratch_value() if stmt.value else ''
            bc_id = f"bc_{bc_name}"
            block_data["inputs"]["BROADCAST_INPUT"] = [1, [11, bc_id, bc_name]]

        elif stmt.type == BlockType.BROADCAST_AND_WAIT:
            bc_name = stmt.value.to_scratch_value() if stmt.value else ''
            bc_id = f"bc_{bc_name}"
            block_data["inputs"]["BROADCAST_INPUT"] = [1, [11, bc_id, bc_name]]

        elif stmt.type == BlockType.CREATE_CLONE_OF:
            target = stmt.value.to_scratch_value() if stmt.value else '_myself_'
            block_data["inputs"]["CLONE_OPTION"] = self.write_menu_input(
                "control_create_clone_of_menu", "CLONE_OPTION", target, block_id)

        elif stmt.type == BlockType.EXTENSION:
            block_data["opcode"] = stmt.extra.get('opcode', 'unknown')
            for name, value in stmt.extra.get('inputs', []):
                block_data["inputs"][name] = self.write_any_input(value)
            for name, value in stmt.extra.get('fields', {}).items():
                block_data["fields"][name] = [value, None]
            substack_id = self.write_substack(stmt.body)
            if substack_id:
                block_data["inputs"]["SUBSTACK"] = [2, substack_id]

        elif stmt.type == BlockType.PROCEDURE_RETURN:
            if stmt.value is not None:
                block_data["inputs"]["VALUE"] = self.write_any_input(stmt.value)

        elif stmt.type == BlockType.PROCEDURE_DEFINE:
            # 自定义积木定义是独立的顶层脚本，必须有 topLevel/坐标
            block_data["topLevel"] = True
            proc_name = stmt.extra.get('name', 'procedure')
            arg_names = stmt.extra.get('args', [])
            arg_types = list(stmt.extra.get('arg_types') or [])
            while len(arg_types) < len(arg_names):
                arg_types.append('s')
            proccode = stmt.extra.get('proccode') or self._build_proccode(
                proc_name, len(arg_names), arg_types)
            saved_ids = stmt.extra.get('argumentids') or []
            arg_ids = saved_ids if len(saved_ids) == len(arg_names) else \
                [f"arg_{i}" for i in range(len(arg_names))]
            saved_defaults = stmt.extra.get('argumentdefaults') or []
            if len(saved_defaults) == len(arg_names):
                arg_defaults = saved_defaults
            else:
                # 原版 Scratch 新建自制积木时参数默认值是空字符串（布尔为 false）
                arg_defaults = [False if item == 'b' else '' for item in arg_types]
            warp = 'true' if stmt.extra.get('warp') else 'false'

            # 生成procedures_prototype以及参数reporter（Scratch加载项目时必需）
            proto_id = self.new_block_id()
            proto_inputs = {}
            for index, (arg_id, arg_name) in enumerate(zip(arg_ids, arg_names)):
                reporter_id = self.new_block_id()
                reporter_opcode = ('argument_reporter_boolean'
                                   if index < len(arg_types) and arg_types[index] == 'b'
                                   else 'argument_reporter_string_number')
                self.all_blocks[reporter_id] = {
                    "opcode": reporter_opcode,
                    "next": None,
                    "parent": proto_id,
                    "inputs": {},
                    "fields": {"VALUE": [arg_name, None]},
                    "shadow": True,
                    "topLevel": False,
                }
                proto_inputs[arg_id] = [1, reporter_id]
            self.all_blocks[proto_id] = {
                "opcode": "procedures_prototype",
                "next": None,
                "parent": block_id,
                "inputs": proto_inputs,
                "fields": {},
                "shadow": True,
                "topLevel": False,
                "mutation": {
                    "tagName": "mutation",
                    "children": [],
                    "proccode": proccode,
                    "argumentids": json.dumps(arg_ids),
                    "argumentnames": json.dumps(arg_names),
                    "argumentdefaults": json.dumps(arg_defaults),
                    "warp": warp
                }
            }
            block_data["inputs"]["custom_block"] = [1, proto_id]

            # Scratch中自制积木的函数体挂在definition块的next链上
            prev_id = block_id
            first_body_id = None
            for body_stmt in stmt.body:
                body_blocks = self.write_statement(body_stmt, prev_id)
                blocks.update(body_blocks)
                first_id = list(body_blocks.keys())[0]
                if first_body_id is None:
                    first_body_id = first_id
                # 把上一条函数体语句接到这一条上（definition本身稍后单独设置next）
                if prev_id != block_id and prev_id in blocks:
                    blocks[prev_id]["next"] = first_id
                prev_id = self._chain_tail(first_id, body_blocks)
            if first_body_id:
                block_data["next"] = first_body_id

        elif stmt.type == BlockType.PROCEDURE_CALL:
            proc_name = stmt.extra.get('name', 'procedure')
            call_args = stmt.extra.get('args', [])
            arg_types = list(stmt.extra.get('arg_types') or [])
            while len(arg_types) < len(call_args):
                arg_types.append('s')
            proccode = stmt.extra.get('proccode') or self._build_proccode(
                proc_name, len(call_args), arg_types)
            saved_ids = stmt.extra.get('argumentids') or []
            arg_ids = saved_ids if len(saved_ids) == len(call_args) else \
                [f"arg_{i}" for i in range(len(call_args))]
            block_data["mutation"] = {
                "tagName": "mutation",
                "children": [],
                "proccode": proccode,
                "argumentids": json.dumps(arg_ids),
                "argumentnames": json.dumps([]),
                "argumentdefaults": json.dumps([]),
                "warp": 'true' if stmt.extra.get('warp') else 'false'
            }
            for arg_id, arg in zip(arg_ids, call_args):
                block_data["inputs"][arg_id] = self.write_any_input(arg)

        blocks[block_id] = block_data

        # 处理下一个块（自制积木定义已在上面把body写入next）
        if stmt.next and stmt.type != BlockType.PROCEDURE_DEFINE:
            next_blocks = self.write_statement(stmt.next, block_id)
            blocks.update(next_blocks)
            first_next_id = list(next_blocks.keys())[0]
            block_data["next"] = first_next_id

        return blocks

    def write_substack(self, body: List[Statement]) -> Optional[str]:
        """写入子堆栈，返回子堆栈第一个块的ID；空堆栈返回None"""
        if not body:
            # 空C形积木不应写SUBSTACK输入，更不能塞入占位积木
            return None

        first_block_id = None
        prev_id = None

        for stmt in body:
            blocks = self.write_statement(stmt, prev_id)
            blocks.update(self.all_blocks)
            self.all_blocks.update(blocks)
            first_block_in_chain = list(blocks.keys())[0]

            if first_block_id is None:
                first_block_id = first_block_in_chain

            if prev_id and prev_id in self.all_blocks:
                self.all_blocks[prev_id]["next"] = first_block_in_chain

            # 链中的所有块
            current_id = first_block_in_chain
            while current_id and current_id in self.all_blocks:
                if self.all_blocks[current_id]["next"] is None:
                    prev_id = current_id
                    break
                current_id = self.all_blocks[current_id]["next"]

        return first_block_id

    def write_menu_input(self, menu_opcode: str, field_name: str,
                         value: Any, parent_id: Optional[str] = None) -> List:
        """写入下拉菜单输入（Scratch 3要求菜单是shadow积木而不是fields）"""
        shadow_id = self.new_block_id()
        self.all_blocks[shadow_id] = {
            "opcode": menu_opcode,
            "next": None,
            "parent": parent_id,
            "inputs": {},
            "fields": {field_name: [value, None]},
            "shadow": True,
            "topLevel": False,
        }
        return [1, shadow_id]

    def write_number_input(self, expr: Optional[Expr], default: float) -> List:
        """写入数字输入（真实sb3格式: [1, [4, "10"]]）"""
        if expr is None:
            return [1, [4, str(default)]]

        if expr.type == ExprType.NUMBER:
            val = expr.value
            if isinstance(val, float) and val == int(val):
                val = int(val)
            return [1, [4, str(val)]]
        elif expr.type == ExprType.BOOLEAN:
            return [1, [4, "1" if expr.value else "0"]]
        elif expr.type == ExprType.STRING:
            return [1, [4, str(expr.value)]]

        # 需要创建一个表达式块
        block_id = self.write_expression_block(expr)
        return [3, block_id, [4, str(default)]]

    def write_string_input(self, expr: Optional[Expr], default: str) -> List:
        """写入字符串输入（真实sb3格式: [1, [10, "文本"]]）"""
        if expr is None:
            return [1, [10, str(default)]]

        if expr.type == ExprType.STRING:
            return [1, [10, expr.value]]
        elif expr.type == ExprType.NUMBER:
            return [1, [10, str(expr.value)]]
        elif expr.type == ExprType.BOOLEAN:
            return [1, [10, "1" if expr.value else "0"]]

        block_id = self.write_expression_block(expr)
        return [3, block_id, [10, str(default)]]

    def write_any_input(self, expr: Optional[Expr]) -> List:
        """写入任意类型输入"""
        if expr is None:
            return [1, [10, ""]]

        if expr.type == ExprType.NUMBER:
            return [1, [4, str(expr.value)]]
        elif expr.type == ExprType.STRING:
            return [1, [10, expr.value]]
        elif expr.type == ExprType.BOOLEAN:
            return [1, [10, "1" if expr.value else "0"]]

        block_id = self.write_expression_block(expr)
        return [3, block_id, [10, ""]]

    def write_boolean_input(self, expr: Optional[Expr]) -> List:
        """写入布尔输入"""
        if expr is None:
            return [1, [10, "1"]]

        if expr.type == ExprType.BOOLEAN:
            return [1, [10, "1" if expr.value else "0"]]

        block_id = self.write_expression_block(expr)
        return [3, block_id, [10, "1"]]

    def write_expression_block(self, expr: Expr) -> str:
        """将表达式写入Scratch块，返回块ID"""
        block_id = self.new_block_id()

        block_data = {
            "opcode": "",
            "next": None,
            "parent": None,
            "inputs": {},
            "fields": {},
            "shadow": False,
            "topLevel": False,
        }

        if expr.type == ExprType.BINARY_OP:
            op_map = {
                '+': 'operator_add',
                '-': 'operator_subtract',
                '*': 'operator_multiply',
                '/': 'operator_divide',
                '%': 'operator_mod',
            }
            block_data["opcode"] = op_map.get(expr.name, 'operator_add')
            block_data["inputs"]["NUM1"] = self.write_any_input(expr.left)
            block_data["inputs"]["NUM2"] = self.write_any_input(expr.right)

        elif expr.type == ExprType.RANDOM:
            block_data["opcode"] = "operator_random"
            block_data["inputs"]["FROM"] = self.write_any_input(expr.left)
            block_data["inputs"]["TO"] = self.write_any_input(expr.right)

        elif expr.type == ExprType.LESS_THAN:
            block_data["opcode"] = "operator_lt"
            block_data["inputs"]["OPERAND1"] = self.write_any_input(expr.left)
            block_data["inputs"]["OPERAND2"] = self.write_any_input(expr.right)

        elif expr.type == ExprType.EQUAL:
            block_data["opcode"] = "operator_equals"
            block_data["inputs"]["OPERAND1"] = self.write_any_input(expr.left)
            block_data["inputs"]["OPERAND2"] = self.write_any_input(expr.right)

        elif expr.type == ExprType.GREATER_THAN:
            block_data["opcode"] = "operator_gt"
            block_data["inputs"]["OPERAND1"] = self.write_any_input(expr.left)
            block_data["inputs"]["OPERAND2"] = self.write_any_input(expr.right)

        elif expr.type == ExprType.AND:
            block_data["opcode"] = "operator_and"
            block_data["inputs"]["OPERAND1"] = self.write_boolean_input(expr.left)
            block_data["inputs"]["OPERAND2"] = self.write_boolean_input(expr.right)

        elif expr.type == ExprType.OR:
            block_data["opcode"] = "operator_or"
            block_data["inputs"]["OPERAND1"] = self.write_boolean_input(expr.left)
            block_data["inputs"]["OPERAND2"] = self.write_boolean_input(expr.right)

        elif expr.type == ExprType.NOT:
            block_data["opcode"] = "operator_not"
            block_data["inputs"]["OPERAND"] = self.write_boolean_input(expr.right)

        elif expr.type == ExprType.JOIN:
            block_data["opcode"] = "operator_join"
            block_data["inputs"]["STRING1"] = self.write_any_input(expr.left)
            block_data["inputs"]["STRING2"] = self.write_any_input(expr.right)

        elif expr.type == ExprType.LETTER_OF:
            block_data["opcode"] = "operator_letter_of"
            block_data["inputs"]["LETTER"] = self.write_any_input(expr.left)
            block_data["inputs"]["STRING"] = self.write_any_input(expr.right)

        elif expr.type == ExprType.LENGTH_OF_STRING:
            block_data["opcode"] = "operator_length"
            block_data["inputs"]["STRING"] = self.write_any_input(expr.right)

        elif expr.type == ExprType.CONTAINS_STRING:
            block_data["opcode"] = "operator_contains"
            block_data["inputs"]["STRING1"] = self.write_any_input(expr.left)
            block_data["inputs"]["STRING2"] = self.write_any_input(expr.right)

        elif expr.type == ExprType.MOD:
            block_data["opcode"] = "operator_mod"
            block_data["inputs"]["NUM1"] = self.write_any_input(expr.left)
            block_data["inputs"]["NUM2"] = self.write_any_input(expr.right)

        elif expr.type == ExprType.ROUND:
            block_data["opcode"] = "operator_round"
            block_data["inputs"]["NUM"] = self.write_any_input(expr.right)

        elif expr.type in (ExprType.ABS, ExprType.FLOOR, ExprType.CEILING,
                          ExprType.SQRT, ExprType.SIN, ExprType.COS,
                          ExprType.TAN, ExprType.ASIN, ExprType.ACOS,
                          ExprType.ATAN, ExprType.LN, ExprType.LOG,
                          ExprType.EXP, ExprType.POW10):
            op_map = {
                ExprType.ABS: 'abs', ExprType.FLOOR: 'floor',
                ExprType.CEILING: 'ceiling', ExprType.SQRT: 'sqrt',
                ExprType.SIN: 'sin', ExprType.COS: 'cos',
                ExprType.TAN: 'tan', ExprType.ASIN: 'asin',
                ExprType.ACOS: 'acos', ExprType.ATAN: 'atan',
                ExprType.LN: 'ln', ExprType.LOG: 'log',
                # Scratch VM的operator_mathop字段值是带空格的 "e ^" / "10 ^"
                ExprType.EXP: 'e ^', ExprType.POW10: '10 ^',
            }
            block_data["opcode"] = "operator_mathop"
            block_data["fields"]["OPERATOR"] = [op_map.get(expr.type, 'abs'), None]
            block_data["inputs"]["NUM"] = self.write_any_input(expr.right)

        elif expr.type == ExprType.EXTENSION_CALL:
            block_data["opcode"] = expr.extra.get('opcode', 'unknown')
            for name, value in expr.extra.get('inputs', []):
                block_data["inputs"][name] = self.write_any_input(value)
            for name, value in expr.extra.get('fields', {}).items():
                block_data["fields"][name] = [value, None]

        elif expr.type == ExprType.PROCEDURE_CALL:
            block_data["opcode"] = "procedures_call"
            arg_types = list(expr.extra.get('arg_types') or [])
            while len(arg_types) < len(expr.args):
                arg_types.append('s')
            proccode = expr.extra.get('proccode') or self._build_proccode(
                expr.name, len(expr.args), arg_types)
            saved_ids = expr.extra.get('argumentids') or []
            arg_ids = saved_ids if len(saved_ids) == len(expr.args) else \
                [f"arg_{i}" for i in range(len(expr.args))]
            block_data["mutation"] = {
                "tagName": "mutation",
                "children": [],
                "proccode": proccode,
                "argumentids": json.dumps(arg_ids),
                "argumentnames": json.dumps([]),
                "argumentdefaults": json.dumps([]),
                "warp": 'true' if expr.extra.get('warp') else 'false',
            }
            for arg_id, arg in zip(arg_ids, expr.args):
                block_data["inputs"][arg_id] = self.write_any_input(arg)

        elif expr.type == ExprType.VARIABLE:
            block_data["opcode"] = "data_variable"
            var_name = expr.name
            block_data["fields"]["VARIABLE"] = [var_name, f"var_{var_name}"]

        elif expr.type == ExprType.LIST_ACCESS:
            block_data["opcode"] = "data_listcontents"
            list_name = expr.name
            block_data["fields"]["LIST"] = [list_name, f"list_{list_name}"]

        elif expr.type == ExprType.ITEM_OF_LIST:
            block_data["opcode"] = "data_itemoflist"
            list_name = expr.name
            block_data["fields"]["LIST"] = [list_name, f"list_{list_name}"]
            block_data["inputs"]["INDEX"] = self.write_any_input(expr.left)

        elif expr.type == ExprType.ITEM_NUMBER_OF_LIST:
            block_data["opcode"] = "data_itemnumoflist"
            list_name = expr.name
            block_data["fields"]["LIST"] = [list_name, f"list_{list_name}"]
            block_data["inputs"]["ITEM"] = self.write_any_input(expr.left)

        elif expr.type == ExprType.LENGTH_OF_LIST:
            block_data["opcode"] = "data_lengthoflist"
            list_name = expr.name
            block_data["fields"]["LIST"] = [list_name, f"list_{list_name}"]

        elif expr.type == ExprType.LIST_CONTAINS:
            block_data["opcode"] = "data_listcontainsitem"
            list_name = expr.name
            block_data["fields"]["LIST"] = [list_name, f"list_{list_name}"]
            block_data["inputs"]["ITEM"] = self.write_any_input(expr.left)

        elif expr.type == ExprType.ANSWER:
            block_data["opcode"] = "sensing_answer"

        elif expr.type == ExprType.TIMER:
            block_data["opcode"] = "sensing_timer"

        elif expr.type == ExprType.TOUCHING_COLOR:
            block_data["opcode"] = "sensing_touchingcolor"
            block_data["inputs"]["COLOR"] = self.write_any_input(expr.left)

        elif expr.type == ExprType.COLOR_TOUCHING_COLOR:
            block_data["opcode"] = "sensing_coloristouchingcolor"
            block_data["inputs"]["COLOR"] = self.write_any_input(expr.left)
            block_data["inputs"]["COLOR2"] = self.write_any_input(expr.right)

        elif expr.type == ExprType.LOUDNESS:
            block_data["opcode"] = "sensing_loudness"

        elif expr.type == ExprType.MOUSE_X:
            block_data["opcode"] = "sensing_mousex"

        elif expr.type == ExprType.MOUSE_Y:
            block_data["opcode"] = "sensing_mousey"

        elif expr.type == ExprType.MOUSE_DOWN:
            block_data["opcode"] = "sensing_mousedown"

        elif expr.type == ExprType.DAYS_SINCE_2000:
            block_data["opcode"] = "sensing_dayssince2000"

        elif expr.type == ExprType.FUNCTION_CALL:
            if expr.name == 'key_pressed':
                block_data["opcode"] = "sensing_keypressed"
                key = expr.args[0].value if expr.args else 'space'
                block_data["inputs"]["KEY_OPTION"] = self.write_menu_input(
                    "sensing_keyoptions", "KEY_OPTION", key, block_id)
            elif expr.name == 'touching':
                block_data["opcode"] = "sensing_touchingobject"
                obj = expr.args[0].value if expr.args else '_edge_'
                block_data["inputs"]["TOUCHINGOBJECTMENU"] = self.write_menu_input(
                    "sensing_touchingobjectmenu", "TOUCHINGOBJECTMENU", obj, block_id)
            elif expr.name == 'distance_to':
                block_data["opcode"] = "sensing_distanceto"
                obj = expr.args[0].value if expr.args else '_mouse_'
                block_data["inputs"]["DISTANCEMENU"] = self.write_menu_input(
                    "sensing_distancetomenu", "DISTANCEMENU", obj, block_id)

        elif expr.type == ExprType.PROPERTY:
            prop = expr.name
            prop_l = prop.lower().replace(' ', '_')
            if prop_l in ('x', 'x_position'):
                block_data["opcode"] = "motion_xposition"
            elif prop_l in ('y', 'y_position'):
                block_data["opcode"] = "motion_yposition"
            elif 'direction' in prop_l:
                block_data["opcode"] = "motion_direction"
            elif prop_l in ('costume_#', 'costume_number', 'costume'):
                block_data["opcode"] = "looks_costumenumbername"
                block_data["fields"]["NUMBER_NAME"] = ["number", None]
            elif prop_l == 'costume_name':
                block_data["opcode"] = "looks_costumenumbername"
                block_data["fields"]["NUMBER_NAME"] = ["name", None]
            elif prop_l == 'size':
                block_data["opcode"] = "looks_size"
            elif prop_l == 'volume':
                block_data["opcode"] = "sound_volume"
            elif prop_l == 'answer':
                block_data["opcode"] = "sensing_answer"
            elif prop_l == 'timer':
                block_data["opcode"] = "sensing_timer"
            elif prop_l == 'loudness':
                block_data["opcode"] = "sensing_loudness"
            elif prop_l in ('mouse_x', 'mousex'):
                block_data["opcode"] = "sensing_mousex"
            elif prop_l in ('mouse_y', 'mousey'):
                block_data["opcode"] = "sensing_mousey"
            elif prop_l in ('mouse_down', 'mousedown'):
                block_data["opcode"] = "sensing_mousedown"
            elif prop_l in ('days_since_2000', 'dayssince2000'):
                block_data["opcode"] = "sensing_dayssince2000"
            else:
                # 未知属性退化为同名变量引用，避免生成空opcode的非法块
                block_data["opcode"] = "data_variable"
                block_data["fields"]["VARIABLE"] = [prop, f"var_{prop}"]

        elif expr.type == ExprType.CURRENT:
            block_data["opcode"] = "sensing_current"
            block_data["fields"]["CURRENTMENU"] = [expr.name, None]

        elif expr.type == ExprType.ARGUMENT:
            block_data["opcode"] = "argument_reporter_string_number"
            block_data["fields"]["VALUE"] = [expr.name, None]

        elif expr.type == ExprType.NUMBER:
            # 数字字面量不需要块
            self.all_blocks[block_id] = block_data
            return block_id

        elif expr.type == ExprType.STRING:
            self.all_blocks[block_id] = block_data
            return block_id

        else:
            block_data["opcode"] = "operator_add"
            block_data["inputs"]["NUM1"] = [1, "0"]
            block_data["inputs"]["NUM2"] = [1, "0"]

        self.all_blocks[block_id] = block_data
        return block_id


def write_scratch_project(project: ProjectIR) -> Dict:
    """便捷函数：将ProjectIR转换为Scratch项目JSON"""
    writer = ScratchWriter()
    return writer.write_project(project)


def save_scratch_file(project: ProjectIR, file_path: str):
    """将项目保存为Scratch文件"""
    data = write_scratch_project(project)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
