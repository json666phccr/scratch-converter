#!/usr/bin/env python3
"""
Scratch 3.0 JSON 解析器
将 Scratch .sb3 (project.json) 解析为中间表示 (IR)
"""

import json
import math
import re
import hashlib
from typing import Dict, List, Any, Optional, Tuple

from ir import (
    BlockType, ExprType, Expr, Statement, SpriteIR, ProjectIR,
    make_number, make_string, make_boolean, make_variable,
    make_property, make_binary_op, make_unary_op, make_random,
    make_list_access, make_list_length, make_list_contains,
    sanitize_name,
)


class ScratchBlockRaw:
    """原始Scratch块，用于解析阶段"""
    def __init__(self, block_id: str, data: Dict):
        self.id = block_id
        self.opcode = data.get('opcode', '')
        self.inputs = data.get('inputs', {})
        self.fields = data.get('fields', {})
        self.next_id = data.get('next')
        self.parent_id = data.get('parent')
        self.x = data.get('x')
        self.y = data.get('y')
        self.shadow = data.get('shadow', False)
        self.top_level = data.get('topLevel', False)
        self.mutation = data.get('mutation', {})

    def __repr__(self):
        return f"RawBlock({self.id}: {self.opcode})"


# ===================== 操作码映射到BlockType =====================

OPCODE_TO_BLOCK_TYPE: Dict[str, BlockType] = {
    # 事件
    'event_whenflagclicked': BlockType.WHEN_FLAG_CLICKED,
    'event_whenkeypressed': BlockType.WHEN_KEY_PRESSED,
    'event_whenthisspriteclicked': BlockType.WHEN_THIS_SPRITE_CLICKED,
    'event_whenstageclicked': BlockType.WHEN_THIS_SPRITE_CLICKED,
    'event_whenbackdropswitchesto': BlockType.WHEN_BACKDROP_SWITCHES,
    'event_whenbroadcastreceived': BlockType.WHEN_BROADCAST_RECEIVED,
    'event_whengreaterthan': BlockType.WHEN_GREATER_THAN,
    'event_whenniteloudness': BlockType.WHEN_LOUDNESS,
    'event_whentimer': BlockType.WHEN_TIMER,

    # 运动
    'motion_movesteps': BlockType.MOVE_STEPS,
    'motion_turnright': BlockType.TURN_RIGHT,
    'motion_turnleft': BlockType.TURN_LEFT,
    'motion_gotoxy': BlockType.GO_TO_XY,
    'motion_goto': BlockType.GO_TO_RANDOM,
    'motion_glideto': BlockType.GLIDE_TO,
    'motion_glidesecstoxy': BlockType.GLIDE_SECS_TO,
    'motion_pointindirection': BlockType.POINT_IN_DIRECTION,
    'motion_pointtowards': BlockType.POINT_TOWARDS,
    'motion_changexby': BlockType.CHANGE_X,
    'motion_setx': BlockType.SET_X,
    'motion_changeyby': BlockType.CHANGE_Y,
    'motion_sety': BlockType.SET_Y,
    'motion_setrotationstyle': BlockType.SET_ROTATION_STYLE,
    'motion_ifonedgebounce': BlockType.IF_ON_EDGE_BOUNCE,

    # 外观
    'looks_say': BlockType.SAY,
    'looks_sayforsecs': BlockType.SAY_FOR_SECS,
    'looks_think': BlockType.THINK,
    'looks_thinkforsecs': BlockType.THINK_FOR_SECS,
    'looks_show': BlockType.SHOW,
    'looks_hide': BlockType.HIDE,
    'looks_switchcostumeto': BlockType.SWITCH_COSTUME,
    'looks_nextcostume': BlockType.NEXT_COSTUME,
    'looks_switchbackdropto': BlockType.SWITCH_BACKDROP,
    'looks_switchbackdroptoandwait': BlockType.SWITCH_BACKDROP_AND_WAIT,
    'looks_nextbackdrop': BlockType.NEXT_BACKDROP,
    'looks_changesizeby': BlockType.CHANGE_SIZE,
    'looks_setsizeto': BlockType.SET_SIZE,
    'looks_changeeffectby': BlockType.CHANGE_EFFECT,
    'looks_seteffectto': BlockType.SET_EFFECT,
    'looks_cleareffects': BlockType.CLEAR_EFFECTS,
    'looks_cleargraphiceffects': BlockType.CLEAR_EFFECTS,
    'looks_gotofrontback': BlockType.GO_TO_FRONT,
    'looks_gobacklayers': BlockType.GO_TO_BACK,
    'looks_goforwardbackwardlayers': BlockType.GO_FORWARD_LAYERS,

    # 声音
    'sound_play': BlockType.PLAY_SOUND,
    'sound_playuntildone': BlockType.PLAY_SOUND_UNTIL_DONE,
    'sound_stopallsounds': BlockType.STOP_ALL_SOUNDS,
    'sound_changevolumeby': BlockType.CHANGE_VOLUME,
    'sound_setvolumeto': BlockType.SET_VOLUME,
    'sound_seteffectto': BlockType.SET_SOUND_EFFECT,
    'sound_changeeffectby': BlockType.CHANGE_SOUND_EFFECT,
    'sound_cleareffects': BlockType.CLEAR_SOUND_EFFECTS,

    # 控制
    'control_wait': BlockType.WAIT,
    'control_repeat': BlockType.REPEAT,
    'control_forever': BlockType.FOREVER,
    'control_if': BlockType.IF,
    'control_if_else': BlockType.IF_ELSE,
    'control_wait_until': BlockType.WAIT_UNTIL,
    'control_repeat_until': BlockType.REPEAT_UNTIL,
    'control_while': BlockType.REPEAT_UNTIL,
    'control_for_each': BlockType.FOR_EACH,
    'control_all_at_once': BlockType.ALL_AT_ONCE,
    'control_incr_counter': BlockType.INCR_COUNTER,
    'control_clear_counter': BlockType.CLEAR_COUNTER,
    'control_stop': BlockType.STOP,
    'control_start_as_clone': BlockType.START_AS_CLONE,
    'control_create_clone_of': BlockType.CREATE_CLONE_OF,
    'control_delete_this_clone': BlockType.DELETE_THIS_CLONE,

    # 侦测
    'sensing_touchingobject': BlockType.TOUCHING_OBJECT,
    'sensing_touchingcolor': BlockType.TOUCHING_COLOR,
    'sensing_coloristouchingcolor': BlockType.COLOR_TOUCHING_COLOR,
    'sensing_distanceto': BlockType.DISTANCE_TO,
    'sensing_askandwait': BlockType.ASK_AND_WAIT,
    'sensing_keypressed': BlockType.KEY_PRESSED,
    'sensing_mousedown': BlockType.MOUSE_DOWN,
    'sensing_setdragmode': BlockType.SET_DRAG_MODE,
    'sensing_resettimer': BlockType.RESET_TIMER,
    'sensing_of': BlockType.OF_PROPERTY,
    'sensing_current': BlockType.CURRENT,

    # 变量和列表
    'data_setvariableto': BlockType.SET_VARIABLE,
    'data_changevariableby': BlockType.CHANGE_VARIABLE,
    'data_showvariable': BlockType.SHOW_VARIABLE,
    'data_hidevariable': BlockType.HIDE_VARIABLE,
    'data_addtolist': BlockType.ADD_TO_LIST,
    'data_deleteoflist': BlockType.DELETE_FROM_LIST,
    'data_deletealloflist': BlockType.DELETE_ALL_FROM_LIST,
    'data_insertatlist': BlockType.INSERT_IN_LIST,
    'data_replaceitemoflist': BlockType.REPLACE_IN_LIST,
    'data_showlist': BlockType.SHOW_LIST,
    'data_hidelist': BlockType.HIDE_LIST,

    # 广播
    'event_broadcast': BlockType.BROADCAST,
    'event_broadcastandwait': BlockType.BROADCAST_AND_WAIT,

    # 自制积木
    'procedures_definition': BlockType.PROCEDURE_DEFINE,
    'procedures_call': BlockType.PROCEDURE_CALL,
    'procedures_return': BlockType.PROCEDURE_RETURN,
}

# 事件帽块操作码（只有这些块可以作为一段脚本的开头）
HAT_OPCODES = {
    'event_whenflagclicked',
    'event_whenkeypressed',
    'event_whenthisspriteclicked',
    'event_whenstageclicked',
    'event_whenbackdropswitchesto',
    'event_whenbroadcastreceived',
    'event_whengreaterthan',
    'event_whenloudness',
    'event_whentimer',
    'control_start_as_clone',
}

# 扩展帽子块（不是标准HAT_OPCODES，但同样可以开启一段脚本）
EXTENSION_HAT_OPCODES = {
    # Clones+
    'lmsclonesplus_whenclonestartswithvar',
    # More Events
    'lmsmoreevents_whenstopclicked',
    'lmsmoreevents_forever',
    'lmsmoreevents_whentruefalse',
    'lmsmoreevents_whiletruefalse',
    'lmsmoreevents_whenvaluechanged',
    'lmsmoreevents_everyduration',
    'lmsmoreevents_whenkeyaction',
    'lmsmoreevents_whilekeypressed',
    'lmsmoreevents_beforesave',
    'lmsmoreevents_aftersave',
    # Clipboard
    'clipboard_whencopied',
    'clipboard_whenpasted',
}

# 这些扩展的动态菜单保存的是变量ID，需要还原成变量名
VARIABLE_MENU_EXTENSIONS = {'lmsclonesplus', 'jeremygamertweening'}
VARIABLE_MENU_FIELDS = {
    'INPUT', 'INPUTA', 'INPUTB', 'INPUTC', 'INPUTD', 'VAR',
}

# 表达式类操作码(不是语句，在输入中作为值使用)
EXPRESSION_OPCODES = {
    'operator_add', 'operator_subtract', 'operator_multiply', 'operator_divide',
    'operator_random', 'operator_lt', 'operator_equals', 'operator_gt',
    'operator_and', 'operator_or', 'operator_not', 'operator_join',
    'operator_letter_of', 'operator_length', 'operator_contains',
    'operator_mod', 'operator_round', 'operator_mathop',
    'data_variable', 'data_listcontents',
    'data_itemoflist', 'data_itemnumoflist', 'data_lengthoflist', 'data_listcontainsitem',
    'sensing_touchingobject', 'sensing_touchingcolor', 'sensing_coloristouchingcolor',
    'sensing_distanceto', 'sensing_answer', 'sensing_keypressed',
    'sensing_mousedown', 'sensing_mousex', 'sensing_mousey',
    'sensing_loudness', 'sensing_loud', 'sensing_timer', 'sensing_of', 'sensing_current',
    'sensing_dayssince2000', 'sensing_username', 'control_get_counter',
    'note', 'music_menu_DRUM', 'music_menu_INSTRUMENT',
    'music_getTempo',
    'motion_xposition', 'motion_yposition', 'motion_direction',
    'looks_costumenumbername', 'looks_backdropnumbername', 'looks_size',
    'sound_volume',
    'argument_reporter_string_number', 'argument_reporter_boolean',
}


def proccode_to_name(proccode: str) -> str:
    """把Scratch的proccode转换为合法且尽量可读的Python标识符

    例如: "add %s" -> "add"，"我的积木 %s %s" -> "我的积木"
    """
    if not proccode:
        return 'procedure'
    name = re.sub(r'%[sbn]', ' ', proccode)
    name = re.sub(r'\s+', ' ', name).strip()
    if not name:
        return 'block'

    sanitized = sanitize_name(name, 'proc')
    if sanitized in ('unnamed', 'block'):
        # 纯符号的proccode（例如 "// %s"、"%s === %s ?"）给出可读名字
        if '//' in proccode:
            return 'comment_block'
        if '===' in proccode:
            return 'equal_question'
        return 'block_' + hashlib.md5(proccode.encode('utf-8')).hexdigest()[:8]
    return sanitized


def proccode_arg_types(proccode: str, count: int) -> List[str]:
    """从proccode提取参数类型: %s字符串/数字, %n数字, %b布尔"""
    types = ['b' if item == '%b' else 'n' if item == '%n' else 's'
             for item in re.findall(r'%[sbn]', proccode or '')]
    while len(types) < count:
        types.append('s')
    return types[:count]


class ScratchParser:
    """将Scratch JSON解析为ProjectIR"""

    def __init__(self):
        self.raw_blocks: Dict[str, ScratchBlockRaw] = {}
        self.unsupported: Dict[str, int] = {}
        self.extensions = set()
        self.list_id_names: Dict[str, str] = {}
        self.variable_id_names: Dict[str, str] = {}
        # 变量/列表 -> 生成属性名（仅在局部与全局同名等冲突时才不同）
        self.global_var_names: Dict[str, str] = {}
        self.global_var_ids: Dict[str, str] = {}
        self.global_list_names: Dict[str, str] = {}
        self.global_list_ids: Dict[str, str] = {}
        self.current_var_names: Dict[str, str] = {}
        self.current_var_ids: Dict[str, str] = {}
        self.current_list_names: Dict[str, str] = {}
        self.current_list_ids: Dict[str, str] = {}

    @staticmethod
    def _unique_attr(base: str, used: set, prefix: str) -> str:
        """为冲突的变量/列表生成唯一属性名"""
        if base not in used:
            return base
        candidate = f"{prefix}_{base}"
        index = 2
        while candidate in used:
            candidate = f"{prefix}_{base}_{index}"
            index += 1
        return candidate

    @staticmethod
    def _field_pair(raw: ScratchBlockRaw, field_name: str,
                    default_name: str):
        """取出 [名字, ID] 形式的字段，兼容只有名字的旧格式"""
        field = raw.fields.get(field_name, [])
        name = str(field[0]) if field else default_name
        item_id = str(field[1]) if len(field) > 1 and field[1] else ''
        return name, item_id

    def _variable_attr(self, name: str, variable_id: str = '') -> str:
        key = str(variable_id or '')
        if key and key in self.global_var_ids:
            return self.global_var_ids[key]
        if key and key in self.current_var_ids:
            return self.current_var_ids[key]
        if name in self.current_var_names:
            return self.current_var_names[name]
        if name in self.global_var_names:
            return self.global_var_names[name]
        return sanitize_name(name, 'var')

    def _list_attr(self, name: str, list_id: str = '') -> str:
        key = str(list_id or '')
        if key and key in self.global_list_ids:
            return self.global_list_ids[key]
        if key and key in self.current_list_ids:
            return self.current_list_ids[key]
        if name in self.current_list_names:
            return self.current_list_names[name]
        if name in self.global_list_names:
            return self.global_list_names[name]
        return sanitize_name(name, 'lst')

    def _extension_namespace(self, opcode: str) -> Optional[str]:
        prefix = opcode.split('_', 1)[0]
        return prefix if prefix in self.extensions else None

    def _parse_extension_inputs(self, raw: ScratchBlockRaw):
        inputs = []
        namespace = (self._extension_namespace(raw.opcode) or '').lower()
        map_variables = namespace in VARIABLE_MENU_EXTENSIONS
        for name, value in raw.inputs.items():
            if name == 'SUBSTACK':
                continue
            expr = None
            # 菜单shadow积木（包括 looks_costume 这类特殊菜单）直接取字段文本，
            # 否则会被当成未知表达式块而丢失。
            input_data = raw.inputs.get(name)
            if isinstance(input_data, list) and len(input_data) >= 2:
                ref = input_data[1]
                block = self.raw_blocks.get(ref) if isinstance(ref, str) else None
                if block is not None and (
                        'menu' in block.opcode.lower()
                        or block.opcode in ('looks_costume', 'looks_backdrops',
                                            'sound_sounds_menu')):
                    text = self._menu_text_from_block(block, name)
                    if text is not None:
                        expr = make_string(text)
            if expr is None:
                expr = self.parse_input(raw, name, '')
            if name == 'list' and 'json_vm_' in raw.opcode \
                    and expr.type == ExprType.STRING \
                    and str(expr.value) in self.list_id_names:
                # JSON 扩展的 get_list 菜单保存的是列表ID，转换成名字
                expr = make_string(self.list_id_names[str(expr.value)])
            elif map_variables and name in VARIABLE_MENU_FIELDS \
                    and expr.type == ExprType.STRING \
                    and str(expr.value) in self.variable_id_names:
                # Clones+/Tween 的变量菜单保存的是变量ID
                expr = make_string(self.variable_id_names[str(expr.value)])
            inputs.append((name, expr))
        fields = {}
        for name, item in raw.fields.items():
            if not item:
                continue
            value = item[0]
            if map_variables and name in VARIABLE_MENU_FIELDS \
                    and str(value) in self.variable_id_names:
                value = self.variable_id_names[str(value)]
            fields[name] = value
        return inputs, fields

    def _warn_unsupported(self, opcode: str):
        self.unsupported[opcode] = self.unsupported.get(opcode, 0) + 1

    @staticmethod
    def _json_list(value: Any) -> list:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else []
            except (ValueError, TypeError):
                return []
        return []

    def _parse_turbowarp_options(self, json_data: Dict) -> Dict[str, Any]:
        """读取TurboWarp保存在注释里的高级选项（// _twconfig_）"""
        for target in json_data.get('targets', []):
            for comment in (target.get('comments') or {}).values():
                if not isinstance(comment, dict):
                    continue
                text = comment.get('text', '')
                if '_twconfig_' not in text:
                    continue
                start, end = text.find('{'), text.rfind('}')
                if start < 0 or end <= start:
                    continue
                try:
                    data = json.loads(text[start:end + 1])
                except (ValueError, TypeError):
                    continue
                if isinstance(data, dict):
                    return data
        return {}

    def _prepare_global_names(self, json_data: Dict):
        """预先计算舞台变量的Python属性名

        舞台变量就是Scratch全局变量。正常情况下属性名就是清洗后的变量名；
        只有多个名字清洗后撞车时才加前缀，保证GLOBALS键唯一。
        """
        self.global_var_names = {}
        self.global_var_ids = {}
        self.global_list_names = {}
        self.global_list_ids = {}
        stage = next((target for target in json_data.get('targets', [])
                      if target.get('isStage')), None)
        if stage is None:
            return
        used = set()
        for var_id, var_data in (stage.get('variables') or {}).items():
            if not isinstance(var_data, list) or not var_data:
                continue
            name = str(var_data[0])
            attr = self._unique_attr(sanitize_name(name, 'var'), used, 'global')
            used.add(attr)
            self.global_var_names[name] = attr
            self.global_var_ids[str(var_id)] = attr
        for list_id, list_data in (stage.get('lists') or {}).items():
            if not isinstance(list_data, list) or not list_data:
                continue
            name = str(list_data[0])
            attr = self._unique_attr(sanitize_name(name, 'lst'), used, 'global')
            used.add(attr)
            self.global_list_names[name] = attr
            self.global_list_ids[str(list_id)] = attr

    def parse_project(self, json_data: Dict) -> ProjectIR:
        """解析整个Scratch项目"""
        project = ProjectIR()
        project.meta = json_data.get('meta', {})
        project.monitors = json_data.get('monitors', [])
        self.extensions = set(json_data.get('extensions', []) or [])
        self.unsupported = {}
        # 扩展菜单里有时保存的是列表ID（如 JSON 扩展的“列表”菜单）
        self.list_id_names = {}
        # Clones+/Tween 的动态变量菜单保存变量ID，转换时需要还原成名字
        self.variable_id_names = {}
        for target_data in json_data.get('targets', []):
            for list_id, list_data in (target_data.get('lists') or {}).items():
                if isinstance(list_data, list) and len(list_data) >= 2:
                    self.list_id_names[list_id] = str(list_data[0])
            for var_id, var_data in (target_data.get('variables') or {}).items():
                if isinstance(var_data, list) and len(var_data) >= 1:
                    self.variable_id_names[str(var_id)] = str(var_data[0])
        self._prepare_global_names(json_data)
        project.runtime_options = self._parse_turbowarp_options(json_data)

        for target_data in json_data.get('targets', []):
            sprite = self.parse_sprite(target_data)
            project.add_sprite(sprite)

        project.warnings = dict(self.unsupported)
        project.extensions = set(self.extensions)
        return project

    def parse_sprite(self, data: Dict) -> SpriteIR:
        """解析单个精灵"""
        sprite = SpriteIR(
            name=data.get('name', 'Sprite'),
            is_stage=data.get('isStage', False),
            current_costume=data.get('currentCostume', 0),
            x=data.get('x', 0),
            y=data.get('y', 0),
            direction=data.get('direction', 90),
            visible=data.get('visible', True),
            size=data.get('size', 100),
            draggable=data.get('draggable', False),
            rotation_style=data.get('rotationStyle', 'all around'),
        )

        # 变量/列表属性名：舞台用预计算的全局映射，角色本地变量可与全局重名，
        # 重名时给本地变量加前缀，引用按变量ID区分，保证读写到正确的变量。
        if sprite.is_stage:
            sprite.variable_attrs = dict(self.global_var_names)
            sprite.variable_id_attrs = dict(self.global_var_ids)
            sprite.list_attrs = dict(self.global_list_names)
            sprite.list_id_attrs = dict(self.global_list_ids)
        else:
            used = set(self.global_var_ids.values()) \
                | set(self.global_list_ids.values())
            for var_id, var_data in data.get('variables', {}).items():
                if not isinstance(var_data, list) or not var_data:
                    continue
                name = str(var_data[0])
                attr = self._unique_attr(sanitize_name(name, 'var'), used, 'local')
                used.add(attr)
                sprite.variable_attrs[name] = attr
                sprite.variable_id_attrs[str(var_id)] = attr
            for list_id, list_data in data.get('lists', {}).items():
                if not isinstance(list_data, list) or not list_data:
                    continue
                name = str(list_data[0])
                attr = self._unique_attr(sanitize_name(name, 'lst'), used, 'local')
                used.add(attr)
                sprite.list_attrs[name] = attr
                sprite.list_id_attrs[str(list_id)] = attr
        self.current_var_names = sprite.variable_attrs
        self.current_var_ids = sprite.variable_id_attrs
        self.current_list_names = sprite.list_attrs
        self.current_list_ids = sprite.list_id_attrs

        # 解析变量
        for var_id, var_data in data.get('variables', {}).items():
            if isinstance(var_data, list) and len(var_data) >= 2:
                sprite.variables[var_data[0]] = var_data[1]

        # 解析列表
        for list_id, list_data in data.get('lists', {}).items():
            if isinstance(list_data, list) and len(list_data) >= 2:
                sprite.lists[list_data[0]] = list_data[1]

        # 解析广播
        for bc_id, bc_data in data.get('broadcasts', {}).items():
            if isinstance(bc_data, str):
                sprite.broadcasts.append(bc_data)

        # 解析造型和声音
        sprite.costumes = data.get('costumes', [])
        sprite.sounds = data.get('sounds', [])

        # 解析代码块
        blocks_data = data.get('blocks', {})
        self.raw_blocks = {}
        for block_id, block_data in blocks_data.items():
            if isinstance(block_data, dict):
                self.raw_blocks[block_id] = ScratchBlockRaw(block_id, block_data)

        # 找出所有顶层块(没有parent的块)
        top_level_blocks = []
        for block_id, raw in self.raw_blocks.items():
            if raw.top_level or (raw.parent_id is None and raw.opcode):
                top_level_blocks.append(raw)

        # 按y坐标排序
        top_level_blocks.sort(key=lambda b: b.y or 0)

        # 解析每个顶层块及其链。
        # 只处理以事件帽块开头的脚本和自制积木定义，
        # 其余没有被事件触发的“孤儿积木”直接忽略。
        for raw in top_level_blocks:
            if raw.opcode not in HAT_OPCODES \
                    and raw.opcode != 'procedures_definition' \
                    and raw.opcode.lower() not in EXTENSION_HAT_OPCODES:
                continue
            stmt = self.parse_statement_chain(raw)
            if stmt:
                sprite.add_statement(stmt)

        return sprite

    def parse_statement_chain(self, raw: ScratchBlockRaw) -> Optional[Statement]:
        """解析一个语句链"""
        if raw is None:
            return None

        stmt = self.parse_single_block(raw)
        if stmt is None:
            return None

        # 自制积木定义在Scratch中把函数体存放在next链里，
        # parse_single_block已经把整条链收进body，这里不能再重复挂接next。
        if stmt.type == BlockType.PROCEDURE_DEFINE:
            return stmt

        # 解析下一个块
        if raw.next_id and raw.next_id in self.raw_blocks:
            stmt.next = self.parse_statement_chain(self.raw_blocks[raw.next_id])

        return stmt

    def parse_single_block(self, raw: ScratchBlockRaw) -> Optional[Statement]:
        """解析单个Scratch块"""
        opcode = raw.opcode

        # 跳过表达式块（它们在输入中被处理）
        if opcode in EXPRESSION_OPCODES:
            return None

        # 跳过原型块
        if opcode in ('procedures_prototype',):
            return None

        namespace = self._extension_namespace(opcode)
        if namespace and opcode not in OPCODE_TO_BLOCK_TYPE:
            block_type = BlockType.EXTENSION_HAT \
                if opcode.lower() in EXTENSION_HAT_OPCODES \
                else BlockType.EXTENSION
            stmt = Statement(type=block_type, extra={
                'namespace': namespace,
                'opcode': opcode,
            })
            stmt.extra['inputs'], stmt.extra['fields'] = \
                self._parse_extension_inputs(raw)
            if block_type == BlockType.EXTENSION:
                stmt.body = self.parse_substack(raw, 'SUBSTACK')
            return stmt

        block_type = OPCODE_TO_BLOCK_TYPE.get(opcode, BlockType.UNKNOWN)

        if block_type == BlockType.UNKNOWN:
            # 尝试根据前缀猜测
            if opcode.startswith('event_'):
                block_type = BlockType.COMMENT  # 降级为注释
            else:
                self._warn_unsupported(opcode)
                return None

        stmt = Statement(type=block_type)

        # 根据块类型解析参数
        if block_type == BlockType.WHEN_FLAG_CLICKED:
            pass  # 没有参数

        elif block_type == BlockType.WHEN_KEY_PRESSED:
            key_field = raw.fields.get('KEY_OPTION', [])
            stmt.extra['key'] = key_field[0] if key_field else 'space'

        elif block_type == BlockType.WHEN_BROADCAST_RECEIVED:
            # 真实Scratch使用 BROADCAST_OPTION，部分工具使用 BROADCAST_INPUT
            bc_name = self.parse_menu(
                raw, 'BROADCAST_INPUT', 'BROADCAST_OPTION', '')
            stmt.value = make_string(bc_name)

        elif block_type == BlockType.WHEN_THIS_SPRITE_CLICKED:
            pass

        elif block_type == BlockType.MOVE_STEPS:
            stmt.value = self.parse_input(raw, 'STEPS', 10)

        elif block_type == BlockType.TURN_RIGHT:
            stmt.value = self.parse_input(raw, 'DEGREES', 15)

        elif block_type == BlockType.TURN_LEFT:
            stmt.value = self.parse_input(raw, 'DEGREES', 15)

        elif block_type == BlockType.GO_TO_XY:
            stmt.extra['x'] = self.parse_input(raw, 'X', 0)
            stmt.extra['y'] = self.parse_input(raw, 'Y', 0)

        elif block_type == BlockType.GO_TO_RANDOM:
            stmt.extra['target'] = self.parse_menu(raw, 'TO', 'TO', '_random_')

        elif block_type == BlockType.GLIDE_SECS_TO:
            stmt.value = self.parse_input(raw, 'SECS', 1)
            stmt.extra['x'] = self.parse_input(raw, 'X', 0)
            stmt.extra['y'] = self.parse_input(raw, 'Y', 0)

        elif block_type == BlockType.GLIDE_TO:
            stmt.value = self.parse_input(raw, 'SECS', 1)
            stmt.extra['target'] = self.parse_menu(raw, 'TO', 'TO', '_random_')

        elif block_type == BlockType.POINT_IN_DIRECTION:
            stmt.value = self.parse_input(raw, 'DIRECTION', 90)

        elif block_type == BlockType.POINT_TOWARDS:
            stmt.extra['target'] = self.parse_menu(
                raw, 'TOWARDS', 'TOWARDS', '_mouse_')

        elif block_type == BlockType.SET_ROTATION_STYLE:
            style_field = raw.fields.get('STYLE', [])
            stmt.extra['style'] = style_field[0] if style_field else 'all around'

        elif block_type == BlockType.CHANGE_X:
            stmt.value = self.parse_input(raw, 'DX', 10)

        elif block_type == BlockType.SET_X:
            stmt.value = self.parse_input(raw, 'X', 0)

        elif block_type == BlockType.CHANGE_Y:
            stmt.value = self.parse_input(raw, 'DY', 10)

        elif block_type == BlockType.SET_Y:
            stmt.value = self.parse_input(raw, 'Y', 0)

        elif block_type == BlockType.IF_ON_EDGE_BOUNCE:
            pass

        elif block_type == BlockType.SAY:
            stmt.value = self.parse_input(raw, 'MESSAGE', '')

        elif block_type == BlockType.SAY_FOR_SECS:
            stmt.extra['message'] = self.parse_input(raw, 'MESSAGE', '')
            stmt.value = self.parse_input(raw, 'SECS', 1)

        elif block_type == BlockType.THINK:
            stmt.value = self.parse_input(raw, 'MESSAGE', '')

        elif block_type == BlockType.THINK_FOR_SECS:
            stmt.extra['message'] = self.parse_input(raw, 'MESSAGE', '')
            stmt.value = self.parse_input(raw, 'SECS', 1)

        elif block_type == BlockType.SHOW:
            pass

        elif block_type == BlockType.HIDE:
            pass

        elif block_type == BlockType.SWITCH_COSTUME:
            stmt.value = self.parse_menu_expr(
                raw, 'COSTUME', 'COSTUME', 'costume1')

        elif block_type == BlockType.NEXT_COSTUME:
            pass

        elif block_type in (BlockType.SWITCH_BACKDROP,
                            BlockType.SWITCH_BACKDROP_AND_WAIT):
            stmt.value = self.parse_menu_expr(
                raw, 'BACKDROP', 'BACKDROP', 'backdrop1')

        elif block_type == BlockType.NEXT_BACKDROP:
            pass

        elif block_type in (BlockType.GO_TO_FRONT, BlockType.GO_TO_BACK):
            where_field = raw.fields.get('FRONT_BACK', [])
            stmt.extra['where'] = where_field[0] if where_field else 'front'

        elif block_type in (BlockType.GO_FORWARD_LAYERS,
                            BlockType.GO_BACKWARD_LAYERS):
            direction_field = raw.fields.get('FORWARD_BACKWARD', [])
            stmt.extra['direction'] = (direction_field[0]
                                       if direction_field else 'forward')
            stmt.value = self.parse_input(raw, 'NUM', 1)

        elif block_type == BlockType.CHANGE_SIZE:
            stmt.value = self.parse_input(raw, 'CHANGE', 10)

        elif block_type == BlockType.SET_SIZE:
            stmt.value = self.parse_input(raw, 'SIZE', 100)

        elif block_type == BlockType.CHANGE_EFFECT:
            effect_field = raw.fields.get('EFFECT', [])
            stmt.extra['effect'] = effect_field[0] if effect_field else 'color'
            stmt.value = self.parse_input(raw, 'CHANGE', 25)

        elif block_type == BlockType.SET_EFFECT:
            effect_field = raw.fields.get('EFFECT', [])
            stmt.extra['effect'] = effect_field[0] if effect_field else 'color'
            stmt.value = self.parse_input(raw, 'VALUE', 100)

        elif block_type == BlockType.CLEAR_EFFECTS:
            pass

        elif block_type == BlockType.PLAY_SOUND:
            stmt.value = self.parse_menu_expr(
                raw, 'SOUND_MENU', 'SOUND_MENU', 'sound1')

        elif block_type == BlockType.PLAY_SOUND_UNTIL_DONE:
            stmt.value = self.parse_menu_expr(
                raw, 'SOUND_MENU', 'SOUND_MENU', 'sound1')

        elif block_type == BlockType.STOP_ALL_SOUNDS:
            pass

        elif block_type == BlockType.CHANGE_VOLUME:
            stmt.value = self.parse_input(raw, 'VOLUME', 10)

        elif block_type == BlockType.SET_VOLUME:
            stmt.value = self.parse_input(raw, 'VOLUME', 100)

        elif block_type == BlockType.SET_SOUND_EFFECT:
            effect_field = raw.fields.get('SOUND_EFFECT', [])
            stmt.extra['effect'] = effect_field[0] if effect_field else 'PITCH'
            stmt.value = self.parse_input(raw, 'VALUE', 100)

        elif block_type == BlockType.CHANGE_SOUND_EFFECT:
            effect_field = raw.fields.get('SOUND_EFFECT', [])
            stmt.extra['effect'] = effect_field[0] if effect_field else 'PITCH'
            stmt.value = self.parse_input(raw, 'VALUE', 10)

        elif block_type == BlockType.CLEAR_SOUND_EFFECTS:
            pass

        elif block_type == BlockType.WAIT:
            stmt.value = self.parse_input(raw, 'DURATION', 1)

        elif block_type == BlockType.REPEAT:
            stmt.value = self.parse_input(raw, 'TIMES', 10)
            stmt.body = self.parse_substack(raw, 'SUBSTACK')

        elif block_type == BlockType.FOREVER:
            stmt.body = self.parse_substack(raw, 'SUBSTACK')

        elif block_type == BlockType.IF:
            stmt.condition = self.parse_boolean_input(raw, 'CONDITION')
            stmt.body = self.parse_substack(raw, 'SUBSTACK')

        elif block_type == BlockType.IF_ELSE:
            stmt.condition = self.parse_boolean_input(raw, 'CONDITION')
            stmt.body = self.parse_substack(raw, 'SUBSTACK')
            stmt.else_body = self.parse_substack(raw, 'SUBSTACK2')

        elif block_type == BlockType.WAIT_UNTIL:
            stmt.condition = self.parse_boolean_input(raw, 'CONDITION')

        elif block_type == BlockType.REPEAT_UNTIL:
            condition = self.parse_boolean_input(raw, 'CONDITION')
            if raw.opcode == 'control_while':
                # TurboWarp: while <condition> 等价于 repeat until not <condition>
                condition = Expr(ExprType.NOT, right=condition)
            stmt.condition = condition
            stmt.body = self.parse_substack(raw, 'SUBSTACK')

        elif block_type == BlockType.FOR_EACH:
            var_name, var_id = self._field_pair(raw, 'VARIABLE', 'item')
            stmt.extra['name'] = var_name
            stmt.extra['attr'] = self._variable_attr(var_name, var_id)
            stmt.value = self.parse_input(raw, 'VALUE', '')
            stmt.body = self.parse_substack(raw, 'SUBSTACK')

        elif block_type == BlockType.ALL_AT_ONCE:
            stmt.body = self.parse_substack(raw, 'SUBSTACK')

        elif block_type in (BlockType.INCR_COUNTER, BlockType.CLEAR_COUNTER):
            pass

        elif block_type == BlockType.STOP:
            stop_field = raw.fields.get('STOP_OPTION', [])
            stmt.extra['option'] = stop_field[0] if stop_field else 'all'

        elif block_type == BlockType.SET_DRAG_MODE:
            drag_field = raw.fields.get('DRAG_MODE', [])
            stmt.extra['mode'] = drag_field[0] if drag_field else 'draggable'

        elif block_type == BlockType.WHEN_BACKDROP_SWITCHES:
            backdrop_field = raw.fields.get('BACKDROP', [])
            stmt.extra['backdrop'] = (backdrop_field[0]
                                      if backdrop_field else 'backdrop1')

        elif block_type == BlockType.WHEN_GREATER_THAN:
            menu_field = raw.fields.get('WHENGREATERTHANMENU', [])
            stmt.extra['menu'] = (menu_field[0] if menu_field else 'TIMER')
            stmt.value = self.parse_input(raw, 'VALUE', 10)

        elif block_type in (BlockType.WHEN_LOUDNESS, BlockType.WHEN_TIMER):
            pass

        elif block_type == BlockType.SET_VARIABLE:
            var_name, var_id = self._field_pair(raw, 'VARIABLE', 'var')
            stmt.extra['name'] = var_name
            stmt.extra['id'] = var_id
            stmt.extra['attr'] = self._variable_attr(var_name, var_id)
            stmt.value = self.parse_input(raw, 'VALUE', 0)

        elif block_type == BlockType.CHANGE_VARIABLE:
            var_name, var_id = self._field_pair(raw, 'VARIABLE', 'var')
            stmt.extra['name'] = var_name
            stmt.extra['id'] = var_id
            stmt.extra['attr'] = self._variable_attr(var_name, var_id)
            stmt.value = self.parse_input(raw, 'VALUE', 1)

        elif block_type == BlockType.SHOW_VARIABLE:
            var_name, var_id = self._field_pair(raw, 'VARIABLE', 'var')
            stmt.extra['name'] = var_name
            stmt.extra['id'] = var_id
            stmt.extra['attr'] = self._variable_attr(var_name, var_id)

        elif block_type == BlockType.HIDE_VARIABLE:
            var_name, var_id = self._field_pair(raw, 'VARIABLE', 'var')
            stmt.extra['name'] = var_name
            stmt.extra['id'] = var_id
            stmt.extra['attr'] = self._variable_attr(var_name, var_id)

        elif block_type == BlockType.ADD_TO_LIST:
            list_name, list_id = self._field_pair(raw, 'LIST', 'list')
            stmt.extra['name'] = list_name
            stmt.extra['attr'] = self._list_attr(list_name, list_id)
            stmt.value = self.parse_input(raw, 'ITEM', '')

        elif block_type == BlockType.DELETE_FROM_LIST:
            list_name, list_id = self._field_pair(raw, 'LIST', 'list')
            stmt.extra['name'] = list_name
            stmt.extra['attr'] = self._list_attr(list_name, list_id)
            stmt.value = self.parse_input(raw, 'INDEX', 1)

        elif block_type == BlockType.DELETE_ALL_FROM_LIST:
            list_name, list_id = self._field_pair(raw, 'LIST', 'list')
            stmt.extra['name'] = list_name
            stmt.extra['attr'] = self._list_attr(list_name, list_id)

        elif block_type == BlockType.INSERT_IN_LIST:
            list_name, list_id = self._field_pair(raw, 'LIST', 'list')
            stmt.extra['name'] = list_name
            stmt.extra['attr'] = self._list_attr(list_name, list_id)
            stmt.extra['item'] = self.parse_input(raw, 'ITEM', '')
            stmt.value = self.parse_input(raw, 'INDEX', 1)

        elif block_type == BlockType.REPLACE_IN_LIST:
            list_name, list_id = self._field_pair(raw, 'LIST', 'list')
            stmt.extra['name'] = list_name
            stmt.extra['attr'] = self._list_attr(list_name, list_id)
            stmt.extra['item'] = self.parse_input(raw, 'ITEM', '')
            stmt.value = self.parse_input(raw, 'INDEX', 1)

        elif block_type == BlockType.SHOW_LIST:
            list_name, list_id = self._field_pair(raw, 'LIST', 'list')
            stmt.extra['name'] = list_name
            stmt.extra['attr'] = self._list_attr(list_name, list_id)

        elif block_type == BlockType.HIDE_LIST:
            list_name, list_id = self._field_pair(raw, 'LIST', 'list')
            stmt.extra['name'] = list_name
            stmt.extra['attr'] = self._list_attr(list_name, list_id)

        elif block_type in (BlockType.BROADCAST, BlockType.BROADCAST_AND_WAIT):
            if 'BROADCAST_INPUT' in raw.inputs:
                stmt.value = self.parse_input(raw, 'BROADCAST_INPUT', '')
            else:
                # 非标准变体可能只把消息写在 fields 里
                stmt.value = make_string(self.parse_menu(
                    raw, 'BROADCAST_INPUT', 'BROADCAST_OPTION', ''))

        elif block_type == BlockType.CREATE_CLONE_OF:
            stmt.value = make_string(
                self.parse_menu(raw, 'CLONE_OPTION', 'CLONE_OPTION', '_myself_'))

        elif block_type == BlockType.DELETE_THIS_CLONE:
            pass

        elif block_type == BlockType.START_AS_CLONE:
            pass  # 帽块，脚本体在next链中

        elif block_type == BlockType.PROCEDURE_DEFINE:
            # 从custom_block输入获取原型块的proccode
            proccode = 'procedure'
            mutation = raw.mutation

            custom_block_input = raw.inputs.get('custom_block')
            if custom_block_input and isinstance(custom_block_input, list) and len(custom_block_input) > 1:
                proto_id = custom_block_input[1]
                if proto_id in self.raw_blocks:
                    mutation = self.raw_blocks[proto_id].mutation

            proccode = mutation.get('proccode', 'procedure')
            arg_names_list = self._json_list(mutation.get('argumentnames', '[]'))
            arg_ids = self._json_list(mutation.get('argumentids', '[]'))
            arg_defaults = self._json_list(mutation.get('argumentdefaults', '[]'))
            warp = str(mutation.get('warp', 'false')).lower() == 'true'

            stmt.extra['name'] = proccode_to_name(proccode)
            stmt.extra['args'] = arg_names_list
            stmt.extra['arg_types'] = proccode_arg_types(proccode, len(arg_names_list))
            stmt.extra['argumentids'] = arg_ids
            stmt.extra['argumentdefaults'] = arg_defaults
            stmt.extra['warp'] = warp
            stmt.extra['proccode'] = proccode
            
            # procedures_definition 的body在next链中，不在SUBSTACK
            # 但是parse_single_block已经通过parse_statement_chain设置了next
            # 这里我们从next开始解析整个body
            stmt.body = []
            if raw.next_id and raw.next_id in self.raw_blocks:
                next_stmt = self.parse_statement_chain(self.raw_blocks[raw.next_id])
                if next_stmt:
                    current = next_stmt
                    while current:
                        nxt = current.next
                        current.next = None  # 断开链，body只保留扁平列表
                        stmt.body.append(current)
                        current = nxt

        elif block_type == BlockType.PROCEDURE_CALL:
            proccode = raw.mutation.get('proccode', 'procedure')
            stmt.extra['name'] = proccode_to_name(proccode)
            stmt.extra['proccode'] = proccode
            stmt.extra['argumentids'] = self._json_list(
                raw.mutation.get('argumentids', '[]'))
            stmt.extra['warp'] = str(
                raw.mutation.get('warp', 'false')).lower() == 'true'
            stmt.extra['arg_types'] = proccode_arg_types(
                proccode, len(stmt.extra['argumentids']))

            # 使用argumentids获取参数值
            argumentids = stmt.extra['argumentids']

            call_args = []
            for arg_id in argumentids:
                # 空输入/缺失输入都按空字符串处理：Scratch 调用时会用参数默认值
                # （通常是 ""），"" + 5 == 5，但参与连接时仍是空字符串
                call_args.append(self.parse_input_by_id(raw, arg_id, ''))
            stmt.extra['args'] = call_args

        elif block_type == BlockType.PROCEDURE_RETURN:
            # TurboWarp自定义reporter: return <值>
            if 'VALUE' in raw.inputs:
                stmt.value = self.parse_input(raw, 'VALUE', '')

        elif block_type == BlockType.ASK_AND_WAIT:
            stmt.value = self.parse_input(raw, 'QUESTION', 'What\'s your name?')

        elif block_type == BlockType.RESET_TIMER:
            pass

        elif block_type == BlockType.COMMENT:
            text = raw.fields.get('COMMENT', [''])[0] if raw.fields else ''
            stmt.extra['text'] = text

        else:
            # 未实现语句，跳过但记录到转换报告
            self._warn_unsupported(opcode)
            return None

        return stmt

    def parse_substack(self, raw: ScratchBlockRaw, input_name: str) -> List[Statement]:
        """解析子堆栈（循环体/if体等）"""
        input_data = raw.inputs.get(input_name)
        if not input_data or not isinstance(input_data, list):
            return []

        # SUBSTACK格式: [shadow_flag, block_id_or_null]
        # 有时是: [shadow_flag, [block_id]]
        if len(input_data) < 2:
            return []

        substack_id = None
        if isinstance(input_data[1], str):
            substack_id = input_data[1]
        elif isinstance(input_data[1], list) and len(input_data[1]) > 0:
            substack_id = input_data[1][0] if isinstance(input_data[1][0], str) else None

        if substack_id and substack_id in self.raw_blocks:
            chain = self.parse_statement_chain(self.raw_blocks[substack_id])
            if chain:
                # 收集整个链为列表，并断开next避免后续写入时重复生成
                stmts = []
                current = chain
                while current:
                    nxt = current.next
                    current.next = None
                    stmts.append(current)
                    current = nxt
                return stmts

        return []

    def _find_block_id(self, value: Any) -> Optional[str]:
        """在输入值中查找引用的积木ID"""
        if isinstance(value, str):
            return value if value in self.raw_blocks else None
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item in self.raw_blocks:
                    return item
        return None

    def _unwrap_primitive(self, value: Any) -> Tuple[Any, Optional[int]]:
        """展开Scratch的 [类型码, 值] 原始值，返回 (值, 类型码)

        真实sb3里的字面量可能是 [1, [4, "10"]] 或 [1, [10, "Hello!"]]，
        而测试/简化格式是 [1, "10"]。这里统一处理。
        """
        prim_type = None
        depth = 0
        while isinstance(value, list) and value and depth < 4:
            if len(value) >= 2 and isinstance(value[0], int):
                prim_type = value[0]
            value = value[-1]
            depth += 1
        return value, prim_type

    def _literal_to_expr(self, value: Any, prim_type: Optional[int] = None) -> Expr:
        """把字面量转换为Expr，prim_type为Scratch原始类型码"""
        if isinstance(value, bool):
            return make_boolean(value)
        if isinstance(value, (int, float)):
            return make_number(value)
        if isinstance(value, str):
            if prim_type in (4, 5, 6, 7, 8):
                # 数字输入里也可能出现 "last"/"random"/"any" 等列表索引特殊值，
                # 转换失败时保留字符串，交给运行时按Scratch规则处理
                try:
                    return make_number(int(value))
                except ValueError:
                    try:
                        return make_number(float(value))
                    except ValueError:
                        return make_string(value)
            if prim_type in (10, 11, 12, 13):
                return make_string(value)
            # 没有类型信息时按数字猜测
            try:
                return make_number(int(value))
            except ValueError:
                try:
                    return make_number(float(value))
                except ValueError:
                    return make_string(value)
        if value is None:
            return make_string('')
        return make_string(str(value))

    def _parse_primitive(self, value: Any, default: Any) -> Expr:
        """解析输入槽里的原始值

        真实sb3支持内联原始值：
        - [4, "10"] 数字
        - [10, "文本"] 文本
        - [11, 广播名, 广播ID] 广播
        - [12, 变量名, 变量ID] 变量引用
        - [13, 列表名, 列表ID] 列表引用
        """
        if isinstance(value, str):
            if value in self.raw_blocks:
                return self.parse_expression_block(self.raw_blocks[value])
            return self._literal_to_expr(value, None)

        if isinstance(value, list) and value:
            code = value[0] if isinstance(value[0], int) else None
            if code == 12:
                name = value[1] if len(value) > 1 else ''
                item_id = str(value[2]) if len(value) > 2 else ''
                expr = make_variable(name)
                expr.extra['attr'] = self._variable_attr(str(name), item_id)
                return expr
            if code == 13:
                name = value[1] if len(value) > 1 else ''
                item_id = str(value[2]) if len(value) > 2 else ''
                expr = Expr(ExprType.LIST_ACCESS, name=name)
                expr.extra['attr'] = self._list_attr(str(name), item_id)
                return expr
            if code == 11:
                # Scratch官方格式：[11, 广播名, 广播ID]，取第2项而不是ID
                return make_string(value[1] if len(value) > 1 else '')
            if code in (4, 5, 6, 7, 8):
                raw = value[1] if len(value) > 1 else '0'
                return self._literal_to_expr(raw, code)
            if code == 9:
                raw = value[1] if len(value) > 1 else '#000000'
                return self._literal_to_expr(raw, code)
            if code == 10:
                return make_string(value[1] if len(value) > 1 else '')

            literal, prim_type = self._unwrap_primitive(value)
            return self._literal_to_expr(literal, prim_type)

        if value is None:
            return self._default_to_expr(default)
        return self._literal_to_expr(value, None)

    def _parse_input_value(self, input_data: Any, default: Any) -> Expr:
        """解析一个输入槽 [类型, 值/积木ID, ...]"""
        if not isinstance(input_data, list) or len(input_data) < 2:
            return self._default_to_expr(default)

        raw_value = input_data[1]
        input_type = input_data[0]
        # 只有 [3, blockId, shadow] 这种块引用形式才需要检查悬空ID；
        # [1, "3"] 是简化格式里的字面量，不能当成积木ID。
        if input_type in (2, 3) and isinstance(raw_value, str) \
                and raw_value not in self.raw_blocks:
            if input_type == 3 and len(input_data) >= 3:
                return self._parse_primitive(input_data[2], default)
            return self._default_to_expr(default)

        return self._parse_primitive(raw_value, default)

    def parse_input(self, raw: ScratchBlockRaw, input_name: str, default: Any) -> Expr:
        """解析输入值（可以是字面量或块引用）"""
        if input_name not in raw.inputs:
            return self._default_to_expr(default)
        return self._parse_input_value(raw.inputs[input_name], default)

    def parse_input_by_id(self, raw: ScratchBlockRaw, input_id: str, default: Any) -> Expr:
        """按输入ID解析值（自制积木调用使用mutation里的argumentids）"""
        if input_id not in raw.inputs:
            return self._default_to_expr(default)
        return self._parse_input_value(raw.inputs[input_id], default)

    def parse_boolean_input(self, raw: ScratchBlockRaw, input_name: str) -> Expr:
        """解析布尔输入"""
        if input_name not in raw.inputs:
            return make_boolean(True)
        return self._parse_input_value(raw.inputs[input_name], True)

    @staticmethod
    def _menu_text_from_block(block: ScratchBlockRaw,
                              field_name: str) -> Optional[str]:
        """从菜单shadow积木中取文本值（菜单积木通常只有一个字段）"""
        field = block.fields.get(field_name)
        if field:
            return str(field[0])
        for value in block.fields.values():
            if value:
                return str(value[0])
        return None

    def _menu_text_from_ref(self, ref: Any,
                            field_name: str) -> Optional[str]:
        """从shadow引用/压缩原始值中取菜单文本

        变量与列表引用（[12]/[13]）不是菜单文本，返回None，避免把
        变量ID误当成造型/声音名字。
        """
        if isinstance(ref, str):
            block = self.raw_blocks.get(ref)
            if isinstance(block, ScratchBlockRaw):
                return self._menu_text_from_block(block, field_name)
            return ref
        if isinstance(ref, list) and ref and isinstance(ref[0], int):
            code = ref[0]
            if code in (4, 5, 6, 7, 8, 9, 10, 11):
                return str(ref[1]) if len(ref) > 1 else None
        return None

    def parse_menu(self, raw: ScratchBlockRaw, input_name: str,
                   field_name: str, default: str) -> str:
        """解析下拉菜单值

        Scratch 3中菜单通常是输入槽里的shadow积木（如looks_costume），
        但旧格式/测试数据直接写成fields。两种都兼容。

        注意：输入里可能是压缩原始值（如 [12, 变量名, 变量ID]）。
        绝不能把变量ID当作菜单文本返回，否则产物里会出现随机字符串。
        """
        # 标准字段名优先；部分工具会把同一个菜单写成输入名
        for name in (field_name, input_name):
            field = raw.fields.get(name)
            if field:
                return str(field[0])

        input_data = raw.inputs.get(input_name)
        if not isinstance(input_data, list) or len(input_data) < 2:
            return default
        kind = input_data[0] if isinstance(input_data[0], int) else None
        candidate = input_data[1]
        shadow = input_data[2] if len(input_data) >= 3 else None

        if isinstance(candidate, str):
            block = self.raw_blocks.get(candidate)
            if isinstance(block, ScratchBlockRaw):
                text = self._menu_text_from_block(block, field_name)
                if text is not None:
                    return text
                # 真实积木挡住了菜单shadow
                text = self._menu_text_from_ref(shadow, field_name)
                return text if text is not None else default
            if kind in (2, 3):
                # 悬空积木ID
                text = self._menu_text_from_ref(shadow, field_name)
                return text if text is not None else default
            return candidate  # 简化格式里的字面量

        text = self._menu_text_from_ref(candidate, field_name)
        if text is not None:
            return text
        # 变量/列表等动态值无法表示为菜单文本，退回shadow
        text = self._menu_text_from_ref(shadow, field_name)
        return text if text is not None else default

    def parse_menu_expr(self, raw: ScratchBlockRaw, input_name: str,
                        field_name: str, default: str) -> Expr:
        """解析“菜单或动态积木”输入

        例如“换成造型(字母(i) of 'FortunateOS')”：
        COSTUME = [3, "aS", "aT"]，aS是真实表达式，aT才是默认菜单shadow。
        也支持压缩原始值 [3, [12, "变量名", "变量ID"], "shadow"]，
        此时应生成变量引用而不是把变量ID当字面量。
        """
        input_data = raw.inputs.get(input_name)
        if not isinstance(input_data, list) or len(input_data) < 2:
            return make_string(
                self.parse_menu(raw, input_name, field_name, default))
        kind = input_data[0] if isinstance(input_data[0], int) else None
        candidate = input_data[1]

        if isinstance(candidate, str):
            block = self.raw_blocks.get(candidate)
            if isinstance(block, ScratchBlockRaw):
                is_menu = (
                    block.shadow or block.opcode.endswith('_menu')
                    or block.opcode in ('looks_costume', 'looks_backdrops',
                                        'sound_sounds_menu',
                                        'event_broadcast_menu'))
                if is_menu:
                    text = self._menu_text_from_block(block, field_name)
                    return make_string(text if text is not None else default)
                return self.parse_expression_block(block)
            if kind in (2, 3):
                # 悬空积木ID，退回shadow菜单
                return make_string(
                    self.parse_menu(raw, input_name, field_name, default))
            return make_string(candidate)  # 简化格式里的字面量

        if isinstance(candidate, list):
            # 压缩原始值：变量/列表/字面量
            return self._parse_primitive(candidate, default)

        return make_string(
            self.parse_menu(raw, input_name, field_name, default))

    def parse_expression_block(self, raw: ScratchBlockRaw) -> Expr:
        """解析表达式块为Expr"""
        opcode = raw.opcode

        # 音乐扩展的菜单shadow块
        if opcode in ('note', 'music_menu_DRUM', 'music_menu_INSTRUMENT'):
            for key in ('NOTE', 'DRUM', 'INSTRUMENT'):
                field = raw.fields.get(key)
                if field:
                    try:
                        return make_number(float(field[0]))
                    except (TypeError, ValueError):
                        return make_string(str(field[0]))
            return make_number(0)

        # 扩展菜单shadow块（如 text_menu_twAlign）：直接取字段里的菜单文本
        if '_menu_' in opcode or opcode.endswith('_menu'):
            for field in raw.fields.values():
                if field:
                    return make_string(field[0])

        namespace = self._extension_namespace(opcode)
        if namespace and opcode not in OPCODE_TO_BLOCK_TYPE:
            inputs, fields = self._parse_extension_inputs(raw)
            return Expr(ExprType.EXTENSION_CALL, name=opcode, extra={
                'namespace': namespace,
                'opcode': opcode,
                'inputs': inputs,
                'fields': fields,
            })

        if opcode == 'operator_add':
            left = self.parse_input(raw, 'NUM1', 0)
            right = self.parse_input(raw, 'NUM2', 0)
            return make_binary_op('+', left, right)

        elif opcode == 'operator_subtract':
            left = self.parse_input(raw, 'NUM1', 0)
            right = self.parse_input(raw, 'NUM2', 0)
            return make_binary_op('-', left, right)

        elif opcode == 'operator_multiply':
            left = self.parse_input(raw, 'NUM1', 0)
            right = self.parse_input(raw, 'NUM2', 0)
            return make_binary_op('*', left, right)

        elif opcode == 'operator_divide':
            left = self.parse_input(raw, 'NUM1', 0)
            right = self.parse_input(raw, 'NUM2', 1)
            return make_binary_op('/', left, right)

        elif opcode == 'operator_random':
            low = self.parse_input(raw, 'FROM', 1)
            high = self.parse_input(raw, 'TO', 10)
            return make_random(low, high)

        elif opcode == 'operator_lt':
            left = self.parse_input(raw, 'OPERAND1', '')
            right = self.parse_input(raw, 'OPERAND2', '')
            return Expr(ExprType.LESS_THAN, left=left, right=right)

        elif opcode == 'operator_equals':
            left = self.parse_input(raw, 'OPERAND1', '')
            right = self.parse_input(raw, 'OPERAND2', '')
            return Expr(ExprType.EQUAL, left=left, right=right)

        elif opcode == 'operator_gt':
            left = self.parse_input(raw, 'OPERAND1', '')
            right = self.parse_input(raw, 'OPERAND2', '')
            return Expr(ExprType.GREATER_THAN, left=left, right=right)

        elif opcode == 'operator_and':
            left = self.parse_boolean_input(raw, 'OPERAND1')
            right = self.parse_boolean_input(raw, 'OPERAND2')
            return Expr(ExprType.AND, left=left, right=right)

        elif opcode == 'operator_or':
            left = self.parse_boolean_input(raw, 'OPERAND1')
            right = self.parse_boolean_input(raw, 'OPERAND2')
            return Expr(ExprType.OR, left=left, right=right)

        elif opcode == 'operator_not':
            operand = self.parse_boolean_input(raw, 'OPERAND')
            return Expr(ExprType.NOT, right=operand)

        elif opcode == 'operator_join':
            left = self.parse_input(raw, 'STRING1', '')
            right = self.parse_input(raw, 'STRING2', '')
            return Expr(ExprType.JOIN, left=left, right=right)

        elif opcode == 'operator_letter_of':
            index = self.parse_input(raw, 'LETTER', 1)
            string = self.parse_input(raw, 'STRING', '')
            return Expr(ExprType.LETTER_OF, left=index, right=string)

        elif opcode == 'operator_length':
            string = self.parse_input(raw, 'STRING', '')
            return Expr(ExprType.LENGTH_OF_STRING, right=string)

        elif opcode == 'operator_contains':
            left = self.parse_input(raw, 'STRING1', '')
            right = self.parse_input(raw, 'STRING2', '')
            return Expr(ExprType.CONTAINS_STRING, left=left, right=right)

        elif opcode == 'operator_mod':
            left = self.parse_input(raw, 'NUM1', 0)
            right = self.parse_input(raw, 'NUM2', 1)
            return Expr(ExprType.MOD, left=left, right=right)

        elif opcode == 'operator_round':
            num = self.parse_input(raw, 'NUM', 0)
            return Expr(ExprType.ROUND, right=num)

        elif opcode == 'operator_mathop':
            op_field = raw.fields.get('OPERATOR', [])
            op_name = op_field[0] if op_field else 'abs'
            num = self.parse_input(raw, 'NUM', 0)
            math_map = {
                'abs': ExprType.ABS, 'floor': ExprType.FLOOR,
                'ceiling': ExprType.CEILING, 'sqrt': ExprType.SQRT,
                'sin': ExprType.SIN, 'cos': ExprType.COS,
                'tan': ExprType.TAN, 'asin': ExprType.ASIN,
                'acos': ExprType.ACOS, 'atan': ExprType.ATAN,
                'ln': ExprType.LN, 'log': ExprType.LOG,
                'e^': ExprType.EXP, 'e ^': ExprType.EXP,
                '10^': ExprType.POW10, '10 ^': ExprType.POW10,
            }
            expr_type = math_map.get(op_name, ExprType.MATH_OP)
            return Expr(type=expr_type, name=op_name, right=num)

        elif opcode == 'data_variable':
            var_name, var_id = self._field_pair(raw, 'VARIABLE', 'var')
            expr = make_variable(var_name)
            expr.extra['attr'] = self._variable_attr(var_name, var_id)
            return expr

        elif opcode == 'data_listcontents':
            list_name, list_id = self._field_pair(raw, 'LIST', 'list')
            expr = Expr(ExprType.LIST_ACCESS, name=list_name)
            expr.extra['attr'] = self._list_attr(list_name, list_id)
            return expr

        elif opcode == 'data_itemoflist':
            list_name, list_id = self._field_pair(raw, 'LIST', 'list')
            index = self.parse_input(raw, 'INDEX', 1)
            expr = make_list_access(list_name, index)
            expr.extra['attr'] = self._list_attr(list_name, list_id)
            return expr

        elif opcode == 'data_itemnumoflist':
            list_name, list_id = self._field_pair(raw, 'LIST', 'list')
            item = self.parse_input(raw, 'ITEM', '')
            expr = Expr(ExprType.ITEM_NUMBER_OF_LIST, name=list_name, left=item)
            expr.extra['attr'] = self._list_attr(list_name, list_id)
            return expr

        elif opcode == 'data_lengthoflist':
            list_name, list_id = self._field_pair(raw, 'LIST', 'list')
            expr = make_list_length(list_name)
            expr.extra['attr'] = self._list_attr(list_name, list_id)
            return expr

        elif opcode == 'data_listcontainsitem':
            list_name, list_id = self._field_pair(raw, 'LIST', 'list')
            item = self.parse_input(raw, 'ITEM', '')
            expr = make_list_contains(list_name, item)
            expr.extra['attr'] = self._list_attr(list_name, list_id)
            return expr

        elif opcode == 'sensing_answer':
            return Expr(ExprType.ANSWER)

        elif opcode == 'sensing_timer':
            return Expr(ExprType.TIMER)

        elif opcode == 'sensing_loudness':
            return Expr(ExprType.LOUDNESS)

        elif opcode == 'sensing_mousex':
            return Expr(ExprType.MOUSE_X)

        elif opcode == 'sensing_mousey':
            return Expr(ExprType.MOUSE_Y)

        elif opcode == 'sensing_mousedown':
            return Expr(ExprType.MOUSE_DOWN)

        elif opcode == 'sensing_dayssince2000':
            return Expr(ExprType.DAYS_SINCE_2000)

        elif opcode == 'sensing_keypressed':
            key = self.parse_menu(raw, 'KEY_OPTION', 'KEY_OPTION', 'space')
            return Expr(ExprType.FUNCTION_CALL, name='key_pressed', args=[make_string(key)])

        elif opcode == 'sensing_touchingobject':
            obj = self.parse_menu(
                raw, 'TOUCHINGOBJECTMENU', 'TOUCHINGOBJECTMENU', '_edge_')
            return Expr(ExprType.FUNCTION_CALL, name='touching', args=[make_string(obj)])

        elif opcode == 'sensing_distanceto':
            obj = self.parse_menu(
                raw, 'DISTANCEMENU', 'DISTANCEMENU', '_mouse_')
            return Expr(ExprType.FUNCTION_CALL, name='distance_to', args=[make_string(obj)])

        elif opcode == 'sensing_touchingcolor':
            color = self.parse_input(raw, 'COLOR', '#000000')
            return Expr(ExprType.TOUCHING_COLOR, left=color)

        elif opcode == 'sensing_coloristouchingcolor':
            color = self.parse_input(raw, 'COLOR', '#000000')
            color2 = self.parse_input(raw, 'COLOR2', '#000000')
            return Expr(ExprType.COLOR_TOUCHING_COLOR, left=color, right=color2)

        elif opcode == 'sensing_loud':
            return Expr(ExprType.LOUDNESS)

        elif opcode == 'sensing_username':
            return Expr(ExprType.FUNCTION_CALL, name='username')

        elif opcode == 'control_get_counter':
            return Expr(ExprType.FUNCTION_CALL, name='get_counter')

        elif opcode == 'sensing_of':
            # OBJECT 在官方格式里是输入槽（shadow: sensing_of_object_menu），
            # PROPERTY 是字段。旧格式/简写也可能把 OBJECT 直接放字段里。
            prop_field = raw.fields.get('PROPERTY', [])
            prop = prop_field[0] if prop_field else 'x position'
            obj_field = raw.fields.get('OBJECT')
            if obj_field:
                obj = obj_field[0]
            else:
                obj = self.parse_menu(raw, 'OBJECT', 'OBJECT', '_stage_')
            return make_property(obj, prop)

        elif opcode == 'sensing_current':
            prop_field = raw.fields.get('CURRENTMENU', [])
            prop = prop_field[0] if prop_field else 'YEAR'
            return Expr(ExprType.CURRENT, name=prop)

        elif opcode == 'event_broadcast_menu':
            # 广播下拉菜单shadow块，字段是[广播名, 广播ID]
            menu_field = raw.fields.get('BROADCAST_OPTION', [])
            return make_string(menu_field[0] if menu_field else '')

        elif opcode == 'motion_xposition':
            return make_property('_sprite_', 'x position')

        elif opcode == 'motion_yposition':
            return make_property('_sprite_', 'y position')

        elif opcode == 'motion_direction':
            return make_property('_sprite_', 'direction')

        elif opcode == 'looks_costumenumbername':
            name_field = raw.fields.get('NUMBER_NAME', [])
            prop = name_field[0] if name_field else 'number'
            if prop in ('number', '#'):
                return make_property('_sprite_', 'costume #')
            return make_property('_sprite_', 'costume name')

        elif opcode == 'looks_backdropnumbername':
            name_field = raw.fields.get('NUMBER_NAME', [])
            prop = name_field[0] if name_field else 'number'
            if prop in ('number', '#'):
                return make_property('_sprite_', 'backdrop #')
            return make_property('_sprite_', 'backdrop name')

        elif opcode == 'looks_size':
            return make_property('_sprite_', 'size')

        elif opcode == 'sound_volume':
            return make_property('_sprite_', 'volume')

        elif opcode == 'argument_reporter_string_number':
            arg_field = raw.fields.get('VALUE', [])
            arg_name = arg_field[0] if arg_field else 'arg'
            return Expr(ExprType.ARGUMENT, name=arg_name)

        elif opcode == 'argument_reporter_boolean':
            arg_field = raw.fields.get('VALUE', [])
            arg_name = arg_field[0] if arg_field else 'arg'
            return Expr(ExprType.ARGUMENT, name=arg_name)

        elif opcode == 'procedures_call':
            # TurboWarp自定义reporter：自制积木作为表达式使用
            mutation = raw.mutation
            proccode = mutation.get('proccode', 'procedure')
            argumentids = self._json_list(mutation.get('argumentids', '[]'))
            args = [self.parse_input_by_id(raw, arg_id, 0)
                    for arg_id in argumentids]
            return Expr(
                ExprType.PROCEDURE_CALL,
                name=proccode_to_name(proccode),
                args=args,
                extra={
                    'proccode': proccode,
                    'argumentids': argumentids,
                    'warp': str(mutation.get('warp', 'false')).lower() == 'true',
                    'arg_types': proccode_arg_types(proccode, len(args)),
                })

        else:
            # 未知表达式，记录到转换报告
            self._warn_unsupported(opcode)
            return make_string('')

    def _default_to_expr(self, default: Any) -> Expr:
        """将Python默认值转换为Expr"""
        if isinstance(default, bool):
            return make_boolean(default)
        elif isinstance(default, int):
            return make_number(default)
        elif isinstance(default, float):
            return make_number(default)
        elif isinstance(default, str):
            return make_string(default)
        return make_string(str(default))


def parse_scratch_project(json_data: Dict) -> ProjectIR:
    """便捷函数：解析Scratch项目JSON"""
    parser = ScratchParser()
    return parser.parse_project(json_data)


def load_scratch_file(file_path: str) -> ProjectIR:
    """从文件加载Scratch项目"""
    with open(file_path, 'r', encoding='utf-8') as f:
        json_data = json.load(f)
    return parse_scratch_project(json_data)
