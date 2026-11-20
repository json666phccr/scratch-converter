# -*- coding: utf-8 -*-
"""第一层：源码级预混淆（在 AST 混淆与加密管线之前运行）。

输入是生成器产出的原始 Python（含运行时模板），输出是"已经不像原始
Python"的 AST，再交给 obfuscate_module 做第二层混淆与加密。两层之间
没有任何原始源码信息残留——最先被混淆的就不是依赖的 Python 文件。

本层变换（顺序敏感）：

1. **装饰器剥离**：删除全部 decorator（源信息抹除；当前生成器虽不产出
   装饰器，此 pass 保证任何来源的输入都不残留装饰器形态）；
2. **恒定折叠**：AST 级恒定分支消除（if True/False、while False、
   恒定 IfExp）、恒定返回合并（if/else 全分支 return 同值 → 单 return）、
   return 后死代码截断；
3. **恒定函数内联**：函数体恰为单条 `return <常量>` 且名字未被字符串
   引用时，调用点直接替换为该常量并删除定义；
4. **局部变量名混淆**：作用域感知（底向上解析闭包/global/nonlocal/
   class 作用域），把局部绑定名改为随机名——运行时模板一并处理；
5. **假结构注入**：注入与真实结构同形的假类/假方法/假分支，进入后续
   管线后被同样混淆与拆簇，与真实代码难分彼此。

安全性说明：生成代码与运行时模板对局部名无反射依赖（globals() 反射
只用字符串键访问模块级名），改名不影响行为；改名新名避让子树内出现的
全部标识符，杜绝遮蔽。
"""

from __future__ import annotations

import ast
import random
from typing import Dict, List, Optional, Set

_SCOPE_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                ast.Lambda)


# ---------------------------------------------------------------- 工具

def _fresh(rng: random.Random, taken: Set[str]) -> str:
    while True:
        name = f"_v{rng.randrange(16 ** 8):08x}"
        if name not in taken:
            taken.add(name)
            return name


def _const(node) -> bool:
    return isinstance(node, ast.Constant)


def _copy_body(stmts: List[ast.stmt]) -> List[ast.stmt]:
    return [ast.copy_location(ast.fix_missing_locations(s), s)
            for s in (ast.deep_copy(stmts) if hasattr(ast, 'deep_copy')
                      else _deepcopy_stmts(stmts))]


def _deepcopy_stmts(stmts):
    import copy
    return copy.deepcopy(stmts)


# ---------------------------------------------------------------- 1. 装饰器

# 语义装饰器白名单：剥离会改变方法绑定行为（staticmethod/classmethod/
# property 的调用约定依赖装饰器），必须保留；它们是内建名，无源信息价值
_SEMANTIC_DECORATORS = ('staticmethod', 'classmethod', 'property')


def strip_decorators(tree: ast.Module) -> None:
    """删除自定义装饰器（源信息抹除）；语义装饰器白名单保留。"""
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
            continue
        if not node.decorator_list:
            continue
        kept = []
        for dec in node.decorator_list:
            name = dec.id if isinstance(dec, ast.Name) else (
                dec.attr if isinstance(dec, ast.Attribute) else None)
            if name in _SEMANTIC_DECORATORS:
                kept.append(dec)
        node.decorator_list = kept


# ---------------------------------------------------------------- 2. 恒定折叠

class _FoldTrivial(ast.NodeTransformer):
    """AST 级恒定折叠：分支消除、恒定返回合并、死代码截断。"""

    def _trim_dead(self, body: List[ast.stmt]) -> List[ast.stmt]:
        """return/raise/break/continue 之后不可达语句删除。"""
        out = []
        for stmt in body:
            out.append(stmt)
            if isinstance(stmt, (ast.Return, ast.Raise, ast.Break,
                                 ast.Continue)):
                break
        return out

    def _all_return_same(self, body) -> Optional[ast.Constant]:
        """body 全为 return 同一常量 -> 返回该常量节点"""
        rets = [s for s in body if isinstance(s, ast.Return)]
        if not rets or len(rets) != len(body):
            return None
        first = rets[0].value
        if not _const(first):
            return None
        for r in rets[1:]:
            if not _const(r.value) or r.value.value != first.value:
                return None
        return first

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.generic_visit(node)
        node.body = self._trim_dead(node.body)
        folded = self._all_return_same(node.body)
        if folded is not None:
            node.body = [ast.copy_location(
                ast.Return(value=ast.Constant(value=folded.value)),
                node.body[0])]
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_If(self, node: ast.If):
        self.generic_visit(node)
        if _const(node.test) and isinstance(node.test.value, bool):
            keep = node.body if node.test.value else (
                node.orelse or [ast.Pass()])
            keep = self._trim_dead(_deepcopy_stmts(keep))
            if not keep:
                keep = [ast.Pass()]
            return keep if len(keep) > 1 else keep
        # 两分支均返回同一常量 -> 单 return（恒定返回合并）
        if isinstance(node.test, ast.Compare):
            a = self._all_return_same(node.body)
            b = self._all_return_same(node.orelse)
            if a is not None and b is not None and a.value == b.value:
                return [ast.copy_location(
                    ast.Return(value=ast.Constant(value=a.value)), node)]
        return node

    def visit_While(self, node: ast.While):
        self.generic_visit(node)
        if _const(node.test) and node.test.value is False:
            return node.orelse or []
        return node

    def visit_IfExp(self, node: ast.IfExp):
        self.generic_visit(node)
        if _const(node.test) and isinstance(node.test.value, bool):
            chosen = node.body if node.test.value else node.orelse
            return ast.copy_location(chosen, node)
        return node


def fold_trivial(tree: ast.Module) -> None:
    tree = ast.fix_missing_locations(tree)
    _FoldTrivial().visit(tree)
    ast.fix_missing_locations(tree)


# ---------------------------------------------------------------- 3. 恒定函数内联

def _constant_functions(tree: ast.Module) -> Dict[str, ast.Constant]:
    """收集模块级"恒定返回"函数：body 恰为单条 return <常量>。"""
    result = {}
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = [s for s in node.body if not _is_docstring(s)]
        if len(body) != 1 or not isinstance(body[0], ast.Return):
            continue
        value = body[0].value
        if not _const(value) or isinstance(value.value,
                                           (tuple, list, dict, set)):
            continue
        args = node.args
        if (args.posonlyargs or args.args or args.kwonlyargs
                or args.vararg or args.kwarg):
            continue
        result[node.name] = value
    return result


def _is_docstring(stmt) -> bool:
    return (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str))


def inline_constant_functions(tree: ast.Module) -> None:
    """恒定返回函数 -> 调用点内联常量并删除定义。

    防御：名字以字符串形式出现在任何常量中（getattr 反射等），
    或作为非调用位置的 Name 引用（函数对象被赋值/传递）时跳过。
    """
    funcs = _constant_functions(tree)
    if not funcs:
        return
    strings = {n.value for n in ast.walk(tree)
               if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    calls = {id(n.func) for n in ast.walk(tree)
             if isinstance(n, ast.Call)}
    name_refs = {n.id for n in ast.walk(tree)
                 if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
                 and id(n) not in calls}
    safe = {name: value for name, value in funcs.items()
            if name not in strings and name not in name_refs}
    if not safe:
        return

    class _Inline(ast.NodeTransformer):
        def visit_Call(self, node: ast.Call):
            self.generic_visit(node)
            if (isinstance(node.func, ast.Name)
                    and node.func.id in safe and not node.keywords):
                return ast.copy_location(
                    ast.Constant(value=safe[node.func.id].value), node)
            return node

        def visit_Name(self, node: ast.Name):
            return node

    _Inline().visit(tree)
    tree.body = [n for n in tree.body if not (
        isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.name in safe)]
    ast.fix_missing_locations(tree)


# ---------------------------------------------------------------- 4. 局部变量名混淆

def _walk_own(root):
    """遍历作用域 root 自己的节点；嵌套 def/class/lambda 的 body 不进入，
    但其 decorator_list / 默认值 / 注解属于当前作用域，需要遍历。"""
    todo = [root]
    while todo:
        node = todo.pop()
        yield node
        is_root = node is root
        if is_root or not isinstance(node, _SCOPE_NODES):
            for _, value in ast.iter_fields(node):
                if isinstance(value, ast.AST):
                    todo.append(value)
                elif isinstance(value, list):
                    todo.extend(v for v in value if isinstance(v, ast.AST))
        else:
            # 嵌套作用域：只有外层求值的字段
            for dec in getattr(node, 'decorator_list', ()):
                todo.append(dec)
            args = getattr(node, 'args', None)
            if args is not None:
                for d in list(args.defaults) + list(
                        [d for d in args.kw_defaults if d is not None]):
                    if isinstance(d, ast.AST):
                        todo.append(d)
                for a in list(args.posonlyargs) + list(args.args) + \
                        list(args.kwonlyargs):
                    if a.annotation is not None:
                        todo.append(a.annotation)
            ret = getattr(node, 'returns', None)
            if ret is not None:
                todo.append(ret)


def _bindings(scope_node, kind: str) -> Set[str]:
    """收集作用域直接绑定名（参数/赋值/for/with/except/walrus）。"""
    bound: Set[str] = set()
    if kind in ('def', 'asyncdef', 'lambda'):
        args = scope_node.args
        for a in (list(args.posonlyargs) + list(args.args)
                  + list(args.kwonlyargs)):
            bound.add(a.arg)
        if args.vararg:
            bound.add(args.vararg.arg)
        if args.kwarg:
            bound.add(args.kwarg.arg)
    for node in _walk_own(scope_node) if kind != 'lambda' else \
            ast.walk(scope_node):
        if isinstance(node, ast.Name) and isinstance(
                node.ctx, (ast.Store, ast.Del)):
            bound.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, ast.NamedExpr):
            bound.add(node.target.id)
    return bound


def _declared(scope_node, cls) -> Set[str]:
    out: Set[str] = set()
    for node in _walk_own(scope_node):
        if isinstance(node, cls):
            out.update(node.names)
    return out


def _declared_tree_nonlocal(scope_node) -> Set[str]:
    """收集子树（含嵌套作用域）全部 nonlocal 声明名。"""
    out: Set[str] = set()
    for node in ast.walk(scope_node):
        if isinstance(node, ast.Nonlocal):
            out.update(node.names)
    return out


def _has_match(node) -> bool:
    return any(isinstance(n, ast.Match) for n in ast.walk(node))


class _LocalRenamer:
    """底向上作用域感知局部改名。

    规则：
    - 每个函数/lambda 作用域先处理子作用域，再改自己的绑定名；
    - 子作用域自己的绑定已在子 pass 改名（旧名不再出现），不会误改；
    - 遍历子作用域时跳过其 global/nonlocal 声明名与 class 绑定名
      （class 绑定不做改名，保留原名以区分）；
    - 新名避让整个子树出现过的标识符，杜绝遮蔽。
    """

    def __init__(self, rng: random.Random):
        self.rng = rng

    def rename(self, tree: ast.Module) -> None:
        used: Set[str] = {n.id for n in ast.walk(tree)
                          if isinstance(n, ast.Name)}
        self._used = used
        for node in list(tree.body):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._process(node, 'def')
        ast.fix_missing_locations(tree)

    def _process(self, node, kind: str) -> None:
        if kind != 'def' and kind != 'asyncdef':
            # class/lambda 作用域不改名：class 绑定名与属性派发表
            # （Attribute/字符串键）必须保持一致；lambda 参数同理保守保留
            return
        if _has_match(node):
            return
        # 底向上：先处理子作用域
        for child in self._children(node):
            self._process(child[0], child[1])

        bound = _bindings(node, kind)
        if not bound:
            return
        globals_decl = _declared(node, ast.Global)
        nonlocals_decl = _declared(node, ast.Nonlocal)
        skip = (globals_decl | nonlocals_decl) & bound
        # 嵌套作用域若声明 nonlocal x 且 x 绑定在本作用域 -> x 不可改名
        # （nonlocal 声明字符串与引用需与绑定一致；保守起见整棵子树的
        #   nonlocal 声明名都保留原名）
        for child in self._children(node):
            skip |= _declared_tree_nonlocal(child[0])
        skip &= bound
        rename = {name: _fresh(self.rng, self._used)
                  for name in bound - skip
                  if not name.startswith('__')}
        if not rename:
            return

        self._rewrite(node, kind, rename, depth=0)

    def _children(self, node):
        """直接子作用域 (node, kind)——不进入嵌套 body，避免重复处理"""
        out = []
        for n in _walk_own(node):
            if n is node:
                continue
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out.append((n, 'def'))
            elif isinstance(n, ast.Lambda):
                out.append((n, 'lambda'))
            elif isinstance(n, ast.ClassDef):
                out.append((n, 'class'))
        return out

    def _rewrite(self, node, kind: str, mapping: Dict[str, str],
                 depth: int) -> None:
        """在 node 子树中重命名 mapping 里的名字（含嵌套作用域的自由引用）。"""
        self._visit(node, kind, mapping, is_root=True)

    def _visit(self, node, kind: str, mapping: Dict[str, str],
               is_root: bool = False) -> None:
        todo = [node]
        while todo:
            cur = todo.pop()
            if isinstance(cur, ast.Name) and cur.id in mapping:
                cur.id = mapping[cur.id]
            elif isinstance(cur, ast.arg) and cur.arg in mapping:
                # 本作用域自己的参数签名（嵌套作用域参数由
                # _visit_nested 跳过，不进入本分支）
                cur.arg = mapping[cur.arg]
            elif isinstance(cur, ast.ExceptHandler) and cur.name in mapping:
                cur.name = mapping[cur.name]
            elif isinstance(cur, (ast.Global, ast.Nonlocal)):
                continue  # 声明名不可改（引用外部作用域）
            is_scope_root = is_root and cur is node
            if isinstance(cur, _SCOPE_NODES) and not is_scope_root:
                # 嵌套作用域：其自绑定名（lambda 参数/class 绑定，可能仍
                # 是旧名）与 global/nonlocal 声明名必须跳过，其余子树中的
                # mapping 名是自由引用（闭包指向本作用域），跟随改名
                child_bound = self._quick_bound(cur)
                if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    child_decl = (_declared(cur, ast.Global)
                                  | _declared(cur, ast.Nonlocal))
                else:
                    child_decl = set()
                self._visit_nested(cur, mapping, child_bound, child_decl)
                continue
            for _, value in ast.iter_fields(cur):
                if isinstance(value, ast.AST):
                    todo.append(value)
                elif isinstance(value, list):
                    todo.extend(v for v in value if isinstance(v, ast.AST))

    def _visit_nested(self, node, mapping, own_bound, declared):
        """遍历嵌套作用域子树：自绑定名与 global/nonlocal 声明名跳过，
        其余 mapping 名是自由引用（闭包指向外层绑定），跟随改名。"""
        todo = [node]
        while todo:
            cur = todo.pop()
            if isinstance(cur, ast.Name):
                if cur.id in own_bound or cur.id in declared:
                    continue
                if cur.id in mapping:
                    cur.id = mapping[cur.id]
                continue
            if isinstance(cur, (ast.Global, ast.Nonlocal)):
                continue
            if isinstance(cur, ast.arg):
                continue  # 嵌套参数保持原名
            if isinstance(cur, ast.ExceptHandler) and cur.name in own_bound:
                continue
            if isinstance(cur, _SCOPE_NODES) and cur is not node:
                inner_bound = self._quick_bound(cur)
                inner_decl = (set()
                              if isinstance(cur, ast.ClassDef)
                              else _declared(cur, ast.Global)
                              | _declared(cur, ast.Nonlocal))
                self._visit_nested(cur, mapping, inner_bound, inner_decl)
                continue
            for _, value in ast.iter_fields(cur):
                if isinstance(value, ast.AST):
                    todo.append(value)
                elif isinstance(value, list):
                    todo.extend(v for v in value if isinstance(v, ast.AST))

    def _quick_bound(self, node) -> Set[str]:
        """快速收集子树内全部绑定痕迹（含未改名者）。"""
        bound = set()
        args = getattr(node, 'args', None)
        if args is not None:
            for a in (list(args.posonlyargs) + list(args.args)
                      + list(args.kwonlyargs)):
                bound.add(a.arg)
            if args.vararg:
                bound.add(args.vararg.arg)
            if args.kwarg:
                bound.add(args.kwarg.arg)
        for n in ast.walk(node):
            if isinstance(n, ast.Name) and isinstance(
                    n.ctx, (ast.Store, ast.Del)):
                bound.add(n.id)
            elif isinstance(n, ast.ExceptHandler) and n.name:
                bound.add(n.name)
            elif isinstance(n, ast.NamedExpr):
                bound.add(n.target.id)
        return bound


def rename_locals(tree: ast.Module, rng: random.Random) -> None:
    _LocalRenamer(rng).rename(tree)


# ---------------------------------------------------------------- 5. 假结构注入

_DECOY_OPS = ('motion_movesteps', 'looks_say', 'sound_play',
              'data_setvariableto', 'event_broadcast', 'control_forever',
              'sensing_timer', 'operator_random', 'motion_turnright',
              'looks_nextcostume', 'event_whenflagclicked')

_DECOY_VARS = ('score', 'lives', 'speed', 'timer', 'answer', 'level',
               'player_x', 'player_y', 'gravity', 'health')


def inject_decoy_structures(tree: ast.Module, rng: random.Random) -> None:
    """注入与真实结构同形的假类/假方法/假分支（进入后续管线被同样混淆）。"""
    taken: Set[str] = {n.id for n in ast.walk(tree)
                       if isinstance(n, ast.Name)}

    def fresh(prefix='d'):
        while True:
            name = f"_d{rng.randrange(16 ** 8):08x}"
            if name not in taken:
                taken.add(name)
                return name

    sources = []
    for _ in range(rng.randrange(2, 4)):
        cls_name = fresh('D')
        m1, m2, m3, v1, v2 = (fresh() for _ in range(5))
        op = rng.choice(_DECOY_OPS)
        var = rng.choice(_DECOY_VARS)
        sources.append(f"""
class {cls_name}:
    \"\"\"{op} handler\"\"\"

    def __init__(self, runtime):
        self._rt = runtime
        self.{v1} = 0
        self.{v2} = []

    def {m1}(self, steps):
        if steps == {rng.randrange(1 << 20)}:
            self.{v1} = self.{v1} * 2 + 7
        for _ in range(3):
            self.{v2}.append(steps ^ {rng.randrange(1 << 12)})
        return self.{v1}

    def {m2}(self, a, b):
        while False:
            self.{m1}(a)
        if a > b:
            return a - b
        return (a * {rng.randrange(3, 97)}) ^ b

    def {m3}(self):
        table = {{'{op}': self.{m2}, '{var}': self.{m1}}}
        return table.get('{op}', None) is not None
""")
    body: List[ast.stmt] = []
    for source in sources:
        body.extend(ast.parse(source).body)
    # 插到模块头部区域之后（避免干扰 __name__ 守卫的位置判断）
    insert_at = min(2, len(tree.body))
    tree.body[insert_at:insert_at] = body
    ast.fix_missing_locations(tree)


# ---------------------------------------------------------------- 入口

def make_decoy_cluster_sources(rng: random.Random, rng_decoys: int = 2
                               ) -> List[str]:
    """生成诱饵簇源码：与真簇同形（顶层函数 + 垃圾运算 + 假类），
    加密进载荷但加载器永不调用——静态解包者解出后真假难辨。"""
    sources = []
    for _ in range(rng_decoys):
        names = [f"_dc{rng.randrange(16 ** 8):08x}" for _ in range(3)]
        cls_name = f"_Dc{rng.randrange(16 ** 8):08x}"
        a, b = rng.randrange(1 << 16), rng.randrange(1 << 16)
        sources.append(f"""
def {names[0]}(x, y):
    if x == {rng.randrange(0x10000, 0xFFFFF)}:
        return (y * {rng.randrange(3, 99)}) ^ x
    acc = x
    for _ in range({rng.randrange(2, 6)}):
        acc = (acc * {a} + {b}) & 0xFFFFFFFF
    return acc ^ y


def {names[1]}(flag):
    table = {{
        'motion_movesteps': {names[0]},
        'looks_say': {names[2]},
        'data_setvariableto': {names[0]},
    }}
    if flag:
        return table
    return {{k: v for k, v in table.items() if k}}


def {names[2]}(runtime, target, value):
    if runtime is None:
        return {rng.randrange(1 << 20)}
    return target if target else value


class {cls_name}:
    def __init__(self, state):
        self._state = state
        self._cache = {{}}

    def _apply(self, key, amount):
        if key not in self._cache:
            self._cache[key] = {names[0]}(amount, {a})
        return self._cache[key]

    def step(self, delta):
        return self._apply('motion_movesteps', delta)
""")
    return sources


def pre_obfuscate(tree: ast.Module, seed=None) -> None:
    """第一层源码预混淆入口（先于 obfuscate_module）。"""
    rng = random.Random(seed)
    strip_decorators(tree)
    fold_trivial(tree)
    inline_constant_functions(tree)
    inject_decoy_structures(tree, rng)
    rename_locals(tree, rng)
    ast.fix_missing_locations(tree)
