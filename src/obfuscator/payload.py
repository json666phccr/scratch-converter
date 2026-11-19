# -*- coding: utf-8 -*-
"""混淆载荷与加载器生成 v2.2（多态壳）。

与 v2.0/v2.1 的本质区别：**每次导出的加密配方都不同**。压缩算法、编码、
哈希族、密钥派生形式、密钥流布局、段标识、分段表形态、片段算术混合全部
逐次随机，加载器按同一配方生成。通用解包脚本依赖的固定结构特征
（8 个整型片段常量、固定 sid 锚点、固定算法组合）不复存在——逆向者
必须逐个产物分析其加载器，无法一份脚本通吃。

安全结构：

- **密钥分裂 + 算术混合**：8 个 64 位片段中若干由其他片段
  ``(f_p * M + C) & 0xFFFF FFFF FFFF FFFF`` 派生，文件中不存在全部字面量；
- **多态配方**：压缩 zlib/bz2/lzma、编码 b85/b64、哈希族 6 种、
  KDF 形式 4 种、密钥流布局与计数器编码逐次随机；
- **随机段标识**：段名每次导出随机化，无 'str'/'main' 固定锚点；
- **段密钥链式派生**：key_i = KDF(prev_plain_digest, sid_i)，
  链条 K_root -> str -> main -> {簇, 资产}；
- **分段 HMAC**：每段独立 salt + HMAC 完整性标签；
- **builtins 完整性探针**：type(exec/compile/__import__/marshal.loads)
  与原生内建类型不一致即 Silent Corrupt（堵 Python 层 exec/loads hook）；
- **Silent Corrupt**：校验失败 / 调试器 / 版本不符不报清晰错误，
  翻转密钥字节让垃圾在远处自然崩溃；
- **函数簇懒加载**：类与 main 入末簇，hook 一次 exec 拿不到类骨架；
- **虚拟资产文件系统** + 字符串表以 tuple 形式存入命名空间
  （规避按 list[str] 结构特征捕获）。
"""

from __future__ import annotations

import base64
import bz2
import hashlib
import hmac
import lzma
import marshal
import os
import random
import sys
import zlib
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

_DEBUG_MODULES = ('pdb', 'pydevd', 'ptvsd', 'debugpy', 'frida')
_INJECTED_MODULES = (
    'math', 'time', 'random', 're', 'array', 'decimal', 'os', 'io',
    'base64', 'argparse', 'threading', 'json', 'functools', 'heapq',
    '_thread', 'pygame',
)
_HASHES = ('sha256', 'sha384', 'sha512', 'blake2b', 'sha3_256', 'sha3_512')
_COMPRESSION = ('zlib', 'bz2', 'lzma')
_ENCODERS = ('b85', 'b64')
_FLIP_XORS = (0x37, 0x5A, 0xA7, 0x91, 0x6C, 0xB3, 0xE2)
_SID_ALPHABET = 'abcdefghijklmnopqrstuvwxyz0123456789'
_MASK64 = (1 << 64) - 1


def _hash_fn(name: str):
    return getattr(hashlib, name)


def _xor(data: bytes, key: bytes) -> bytes:
    return bytes(byte ^ key[index % len(key)]
                 for index, byte in enumerate(data))


@dataclass
class Recipe:
    """一次导出的加密配方（生成端与加载器共同遵守）。"""
    hash_name: str          # 主哈希族（kroot / KDF / 段摘要 / tag）
    ks_hash_name: str       # 密钥流哈希族（可与主哈希不同）
    comp: str               # 压缩算法
    enc: str                # 密文文本编码
    kdf: int                # 段密钥派生形式 0..3
    ks_seed_order: int      # 解密时 seed = key+salt / salt+key
    ks_layout: int          # 块 = H(seed+ctr) / H(ctr+seed)
    ks_width: int           # 计数器字节宽
    ks_endian: str          # 计数器字节序
    ks_start: int           # 计数器起点
    flip_idx: int           # tag 校验失败时翻转的字节下标
    flip_xor: int           # 翻转异或值
    corrupt_idx: int        # Silent Corrupt 翻转的字节下标
    corrupt_xor: int        # Silent Corrupt 异或值
    str_ks_order: int       # 字符串条目 seed = sk+prev / prev+sk
    table_form: int         # 分段表形态 0=字典 / 1=行列表
    fragments: List[int]    # 8 个片段的实际值
    derived: List[Tuple[int, int, int, int]]  # (idx, parent, mult, add)
    str_sid: str
    main_sid: str
    cluster_sids: List[str] = field(default_factory=list)
    asset_sids: Dict[str, str] = field(default_factory=dict)

    # ---- 生成端密码学 ----
    def kroot(self) -> bytes:
        return _hash_fn(self.hash_name)(b''.join(
            f.to_bytes(8, 'big') for f in self.fragments)).digest()

    def derive_key(self, prev: bytes, sid: bytes) -> bytes:
        if self.kdf == 0:
            return hmac.new(prev, sid, self.hash_name).digest()
        if self.kdf == 1:
            return hmac.new(sid, prev, self.hash_name).digest()
        if self.kdf == 2:
            return _hash_fn(self.hash_name)(prev + sid).digest()
        return _hash_fn(self.hash_name)(sid + prev).digest()

    def keystream(self, seed: bytes, length: int) -> bytes:
        h = _hash_fn(self.ks_hash_name)
        output = bytearray()
        counter = self.ks_start
        while len(output) < length:
            block_seed = counter.to_bytes(self.ks_width, self.ks_endian)
            if self.ks_layout == 0:
                output.extend(h(seed + block_seed).digest())
            else:
                output.extend(h(block_seed + seed).digest())
            counter += 1
        return bytes(output[:length])

    def compress(self, data: bytes) -> bytes:
        if self.comp == 'zlib':
            return zlib.compress(data, 9)
        if self.comp == 'bz2':
            return bz2.compress(data, 9)
        return lzma.compress(data, preset=6)

    def encode_text(self, data: bytes) -> str:
        if self.enc == 'b85':
            return base64.b85encode(data).decode('ascii')
        return base64.b64encode(data).decode('ascii')

    def prev_digest(self, plain: bytes) -> bytes:
        return _hash_fn(self.hash_name)(plain).digest()

    def chain_digest(self, raw: bytes) -> bytes:
        return _hash_fn(self.ks_hash_name)(raw).digest()

    def str_key(self, kroot: bytes) -> bytes:
        return self.derive_key(kroot, self.str_sid.encode())


def make_recipe(rng: random.Random, cluster_count: int,
                asset_names: List[str]) -> Recipe:
    def sid_token() -> str:
        while True:
            token = ''.join(rng.choice(_SID_ALPHABET)
                            for _ in range(12))
            if token[0].isalpha():
                return token

    fragments = [rng.getrandbits(64) for _ in range(8)]
    derived: List[Tuple[int, int, int, int]] = []
    derived_count = rng.choice((1, 2, 3))
    # 派生下标唯一且父片段下标更小，保证加载器按序赋值可行
    candidate_idx = list(range(1, 8))
    rng.shuffle(candidate_idx)
    for idx in candidate_idx[:derived_count]:
        parent = rng.randrange(idx)
        mult = (rng.getrandbits(32) | 1)
        add = rng.getrandbits(48)
        derived.append((idx, parent, mult, add))
        fragments[idx] = (fragments[parent] * mult + add) & _MASK64
    derived.sort()

    return Recipe(
        hash_name=rng.choice(_HASHES),
        ks_hash_name=rng.choice(_HASHES),
        comp=rng.choice(_COMPRESSION),
        enc=rng.choice(_ENCODERS),
        kdf=rng.randrange(4),
        ks_seed_order=rng.randrange(2),
        ks_layout=rng.randrange(2),
        ks_width=rng.choice((4, 8)),
        ks_endian=rng.choice(('big', 'little')),
        ks_start=rng.choice((0, 1)),
        flip_idx=rng.randrange(32),
        flip_xor=rng.choice(_FLIP_XORS),
        corrupt_idx=rng.randrange(32),
        corrupt_xor=rng.choice(_FLIP_XORS),
        str_ks_order=rng.randrange(2),
        table_form=rng.randrange(2),
        fragments=fragments,
        derived=derived,
        str_sid=sid_token(),
        main_sid=sid_token(),
        cluster_sids=[sid_token() for _ in range(cluster_count)],
        asset_sids={name: sid_token() for name in asset_names},
    )


@dataclass
class PayloadSpec:
    recipe: Recipe
    segments: Dict[str, Tuple[bytes, bytes, bytes]]  # sid_hex -> (salt, tag, ct)
    version: Tuple[int, int]


def build_payload(stage1_code, cluster_sources: List[str],
                  str_entries: List[str], assets: Dict[str, bytes],
                  seed=None) -> PayloadSpec:
    rng = random.Random(seed)
    recipe = make_recipe(rng, len(cluster_sources), sorted(assets))
    kroot = recipe.kroot()

    segments: Dict[str, Tuple[bytes, bytes, bytes]] = {}

    def encrypt(sid: str, plain: bytes, prev_digest: bytes) -> bytes:
        """链式段加密：段密钥 = KDF(prev_digest, sid)。

        返回明文摘要，作为下一段密钥派生的输入——批量解密必须按
        链条顺序进行，无法乱序/并行静态求解。
        """
        salt = os.urandom(16)
        key = recipe.derive_key(prev_digest, sid.encode())
        compressed = recipe.compress(plain)
        seed = key + salt if recipe.ks_seed_order == 0 else salt + key
        ciphertext = _xor(compressed,
                          recipe.keystream(seed, len(compressed)))
        tag = hmac.new(key, ciphertext, recipe.hash_name).digest()
        segments[sid.encode().hex()] = (salt, tag, ciphertext)
        return recipe.prev_digest(plain)

    # 链条：K_root -> str -> main -> {簇, 资产}
    str_plain = marshal.dumps(_encode_chain(
        recipe, str_entries, recipe.str_key(kroot)))
    digest_str = encrypt(recipe.str_sid, str_plain, kroot)
    digest_main = encrypt(recipe.main_sid,
                          marshal.dumps({'c': stage1_code}), digest_str)

    for index, source in enumerate(cluster_sources):
        code = compile(source, f"<{rng.randrange(16 ** 12):012x}>",
                       'exec', dont_inherit=True)
        encrypt(recipe.cluster_sids[index], marshal.dumps(code), digest_main)

    for name, data in assets.items():
        encrypt(recipe.asset_sids[name], data, digest_main)

    return PayloadSpec(
        recipe=recipe,
        segments=segments,
        version=tuple(sys.version_info[:2]),
    )


def _encode_chain(recipe: Recipe, str_entries: List[str],
                  str_key: bytes) -> List[bytes]:
    """链式字符串表：条目密钥依赖前一条明文摘要。"""
    chain = b''
    entry_cts = []
    for entry in str_entries:
        raw = entry.encode('utf-8')
        seed = (str_key + chain if recipe.str_ks_order == 0
                else chain + str_key)
        entry_cts.append(_xor(raw, recipe.keystream(seed, len(raw))))
        chain = recipe.chain_digest(raw)
    return entry_cts


def _chunks(data: bytes, size: int = 2048) -> List[str]:
    text = data
    return [text[i:i + size] for i in range(0, len(text), size)]


def _sid_hex(sid: str) -> str:
    return sid.encode().hex()


def loader_source(spec: PayloadSpec, *, main_name: str,
                  strtable_name: str, cluster_helper: str,
                  asset_helper: str, embed_assets: bool,
                  asset_dir: str = 'assets', seed=None) -> str:
    rng = random.Random(seed)
    rec = spec.recipe
    used: set = set()

    def name(prefix='v'):
        while True:
            value = f"_{prefix}{rng.randrange(16 ** 6):06x}"
            if value not in used:
                used.add(value)
                return value

    # ---- 随机化标识符 ----
    n_imp = name('i')
    n_hex = name('x')
    mod_names = {mod: name('m') for mod in
                 ('os', 'sys', 'hashlib', 'hmac', 'marshal', rec.comp,
                  'base64', 'threading', 'io')}
    n_os = mod_names['os']
    n_sys = mod_names['sys']
    n_hash = mod_names['hashlib']
    n_hmac = mod_names['hmac']
    n_mar = mod_names['marshal']
    n_comp = mod_names[rec.comp]
    n_b85 = mod_names['base64']
    n_thr = mod_names['threading']
    n_io = mod_names['io']
    n_bi = name('b')
    n_ex = name('e')
    n_k = name('k')
    n_hf = name('h')
    n_kh = name('h')
    n_segs = name('s')
    n_ksf = name('k')
    n_dec = name('d')
    n_pd = name('p')
    n_cr = name('c')
    n_L = name('s')
    n_sk = name('k')
    n_ns = name('n')
    n_clh = name('c')
    n_csid = name('q')
    n_amap = name('a')
    n_acache = name('a')
    n_alh = name('a')
    n_pt = name('p')
    n_vdir = name('v')
    n_exw = name('e')
    n_opw = name('o')
    n_ilw0 = name('i')
    n_ilw = name('i')
    n_snd0 = name('s')
    n_sndw = name('s')
    n_mainc = name('m')
    n_pd2 = name('p')
    n_md = name('m')
    n_sp = name('s')
    n_mp = name('m')
    n_pg = name('p')
    n_rows = name('r')
    frag_names = [name('f') for _ in rec.fragments]

    str_sid_hex = _sid_hex(rec.str_sid)
    main_sid_hex = _sid_hex(rec.main_sid)
    cluster_sid_hexes = [_sid_hex(s) for s in rec.cluster_sids]
    dec_attr = {'b85': 'b85decode', 'b64': 'b64decode'}[rec.enc]

    # ---- 生成期辅助：把字符串变成 loader 端 hex 解码调用 ----
    def H(value: str) -> str:
        return f"{n_hex}({value.encode().hex()!r}).decode()"

    L: List[str] = []

    def add(line: str = '') -> None:
        L.append(line)

    # ---- imports（全部十六进制化）----
    add(f"{n_imp} = __import__")
    add(f"{n_hex} = bytes.fromhex")
    for mod, binding in mod_names.items():
        add(f"{binding} = {n_imp}({H(mod)})")
    add(f"{n_bi} = {n_imp}({H('builtins')})")
    add(f"{n_ex} = getattr({n_bi}, {H('exec')})")
    add(f"{n_hf} = getattr({n_hash}, {H(rec.hash_name)})")
    add(f"{n_kh} = getattr({n_hash}, {H(rec.ks_hash_name)})")
    add()

    # ---- 密钥分裂片段（含算术派生）----
    for index, (fname, fragment) in enumerate(
            zip(frag_names, rec.fragments)):
        derived_here = [d for d in rec.derived if d[0] == index]
        if derived_here:
            _, parent, mult, addend = derived_here[0]
            add(f"{fname} = ({frag_names[parent]} * 0x{mult:X} "
                f"+ 0x{addend:X}) & 0x{_MASK64:X}")
        else:
            add(f"{fname} = 0x{fragment:016X}")
    add(f"{n_k} = bytearray({n_hf}(b''.join(")
    add("    t.to_bytes(8, 'big') for t in ("
        + ", ".join(frag_names) + "))).digest())")
    add()

    # ---- 反调试探针（含 builtins 完整性检查）----
    add(f"def {n_pd}():")
    add("    try:")
    add(f"        if {n_sys}.gettrace() is not None:")
    add("            return True")
    add("    except Exception:")
    add("        pass")
    add("    try:")
    add(f"        m = getattr({n_sys}, {H('monitoring')}, None)")
    add("        if m is not None:")
    add("            for t in range(6):")
    add("                try:")
    add("                    if m.get_tool(t) is not None:")
    add("                        return True")
    add("                except Exception:")
    add("                    pass")
    add("    except Exception:")
    add("        pass")
    add(f"    mods = {n_sys}.modules")
    add(f"    for t in ({', '.join(H(mod) for mod in _DEBUG_MODULES)},):")
    add("        if t in mods:")
    add("            return True")
    # builtins 完整性：Python 层替换 exec/compile/__import__/marshal.loads
    # 的 hook（类型为 'function'）与原生内建类型不符
    add("    for t in (" + ", ".join(
        H(nm) for nm in ('exec', 'compile', '__import__')) + "):")
    add(f"        if type(getattr({n_bi}, t)) is not "
        f"type(getattr({n_bi}, {H('len')})):")
    add("            return True")
    add(f"    if type({n_mar}.loads) is not "
        f"type(getattr({n_bi}, {H('len')})):")
    add("        return True")
    add("    return False")
    add(f"def {n_cr}():")
    add(f"    {n_k}[{rec.corrupt_idx}] ^= 0x{rec.corrupt_xor:X}")
    add(f"if {n_pd}():")
    add(f"    {n_cr}()")
    add(f"if {n_sys}.version_info[:2] != {spec.version!r}:")
    add(f"    {n_cr}()")
    add()

    # ---- 分段表 ----
    if rec.table_form == 0:
        add(f"{n_segs} = {{")
        for sid, (salt, tag, ct) in spec.segments.items():
            parts = ", ".join(repr(chunk) for chunk in _chunks(
                rec.encode_text(ct)))
            add(f"    {sid!r}: ({salt!r}, {tag!r}, [{parts}]),")
        add("}")
    else:
        add(f"{n_rows} = [")
        for sid, (salt, tag, ct) in spec.segments.items():
            parts = ", ".join(repr(chunk) for chunk in _chunks(
                rec.encode_text(ct)))
            add(f"    [{sid!r}, {salt!r}, {tag!r}, [{parts}]],")
        add("]")
        add(f"{n_segs} = {{r[0]: (r[1], r[2], r[3]) for r in {n_rows}}}")
    add(f"def {n_ksf}(seed, n):")
    add("    out = bytearray()")
    add(f"    c = {rec.ks_start}")
    add("    while len(out) < n:")
    if rec.ks_layout == 0:
        ctr_expr = f"seed + c.to_bytes({rec.ks_width}, {rec.ks_endian!r})"
    else:
        ctr_expr = f"c.to_bytes({rec.ks_width}, {rec.ks_endian!r}) + seed"
    add(f"        out.extend({n_kh}({ctr_expr}).digest())")
    add("        c += 1")
    add("    return bytes(out[:n])")

    # ---- 段解密（KDF 形式按配方生成）----
    def kdf_expr(prev: str, sid: str) -> str:
        if rec.kdf == 0:
            return (f"bytearray({n_hmac}.new(bytes({prev}), "
                    f"{n_hex}({sid}), {n_hf}).digest())")
        if rec.kdf == 1:
            return (f"bytearray({n_hmac}.new({n_hex}({sid}), "
                    f"bytes({prev}), {n_hf}).digest())")
        if rec.kdf == 2:
            return (f"bytearray({n_hf}(bytes({prev}) + "
                    f"{n_hex}({sid})).digest())")
        return (f"bytearray({n_hf}({n_hex}({sid}) + "
                f"bytes({prev})).digest())")

    add(f"def {n_dec}(sidhex, prev):")
    add(f"    fr = {n_sys}._getframe(1)")
    add("    if fr is None or " +
        f"{n_os}.path.abspath(__file__) != fr.f_code.co_filename:")
    add(f"        {n_cr}()")
    add(f"    salt, tag, parts = {n_segs}[sidhex]")
    add(f"    ct = {n_b85}.{dec_attr}(''.join(parts))")
    add(f"    k2 = {kdf_expr('prev', 'sidhex')}")
    add("    if not " + f"{n_hmac}.compare_digest(")
    add(f"            {n_hmac}.new(bytes(k2), ct, "
        f"{n_hf}).digest(), tag):")
    add(f"        k2[{rec.flip_idx}] ^= 0x{rec.flip_xor:X}")
    if rec.ks_seed_order == 0:
        ks_input = "bytes(k2) + salt"
    else:
        ks_input = "salt + bytes(k2)"
    add(f"    ks = {n_ksf}({ks_input}, len(ct))")
    add("    plain = bytes(a ^ b for a, b in zip(ct, ks))")
    add(f"    return {n_comp}.decompress(plain)")
    add()

    # ---- 字符串表（链式解码，一次性展开）----
    kroot_expr = f"bytes({n_k})"
    str_sid_lit = repr(str_sid_hex)
    add(f"{n_L} = []")
    add(f"{n_sk} = {kdf_expr(kroot_expr, str_sid_lit)}")
    add(f"{n_sp} = {n_dec}({str_sid_lit}, {kroot_expr})")
    add("prev = b''")
    add(f"for ect in {n_mar}.loads({n_sp}):")
    if rec.str_ks_order == 0:
        entry_seed = f"{n_sk} + prev"
    else:
        entry_seed = f"prev + {n_sk}"
    add("    raw = bytes(a ^ b for a, b in zip(")
    add(f"        ect, {n_ksf}({entry_seed}, len(ect))))")
    add("    try:")
    add(f"        {n_L}.append(raw.decode('utf-8'))")
    add("    except Exception:")
    add(f"        {n_cr}()")
    add(f"        {n_L}.append('')")
    add(f"    prev = {n_kh}(raw).digest()")
    add(f"{n_pd2} = {n_hf}({n_sp}).digest()")
    add()

    # ---- 命名空间与模块注入 ----
    add(f"{n_ns} = {{")
    add(f"    {H('__name__')}: 'runtime',")
    add(f"    {H('__file__')}: {n_os}.path.abspath(__file__),")
    add("}")
    for mod in _INJECTED_MODULES:
        add("try:")
        add(f"    {n_ns}[{H(mod)}] = {n_imp}({H(mod)})")
        add("except Exception:")
        add(f"    {n_ns}[{H(mod)}] = None")
    add(f"{n_ns}[{H(strtable_name)}] = tuple({n_L})")
    add()

    # ---- 函数簇懒加载 ----
    add(f"{n_csid} = ({', '.join(repr(h) for h in cluster_sid_hexes)},)")
    add(f"def {n_clh}(cid, g):")
    add("    " + f"{n_ex}({n_mar}.loads({n_dec}({n_csid}[cid], {n_md})), g)")
    add(f"{n_ns}[{H(cluster_helper)}] = {n_clh}")
    add()

    # ---- 主程序 ----
    add(f"{n_mp} = {n_dec}({main_sid_hex!r}, {n_pd2})")
    add(f"{n_mainc} = {n_mar}.loads({n_mp})[{H('c')}]")
    add(f"{n_md} = {n_hf}({n_mp}).digest()")
    add(f"{n_ex}({n_mainc}, {n_ns})")
    add()

    # ---- 资产：内嵌虚拟 FS / 外部目录 ----
    if embed_assets:
        asset_map = {aname: _sid_hex(sid)
                     for aname, sid in rec.asset_sids.items()}
        amap_literal = ', '.join(
            f'{name!r}: {sidhex!r}' for name, sidhex in asset_map.items())
        add(f"{n_vdir} = {n_os}.path.join({n_os}.path.dirname(")
        add(f"    {n_os}.path.abspath(__file__)), {asset_dir + '_v'!r})")
        add(f"{n_ns}[{H('ASSETS_DIR')}] = {n_vdir}")
        add(f"{n_amap} = {{{amap_literal}}}")
        add(f"{n_acache} = {{}}")
        add(f"def {n_alh}(bn):")
        add(f"    d = {n_acache}.get(bn)")
        add("    if d is None:")
        add(f"        d = {n_dec}({n_amap}[bn], {n_md})")
        add(f"        {n_acache}[bn] = d")
        add("    return d")
        add(f"{n_ns}[{H(asset_helper)}] = {n_alh}")
        add(f"if {n_amap}:")
        add(f"    {n_exw} = {n_os}.path.exists")
        add("    def _ew(p, *a, **k):")
        add("        try:")
        add("            if isinstance(p, str) and "
            f"{n_os}.path.basename(p) in {n_amap}:")
        add("                return True")
        add("        except Exception:")
        add("            pass")
        add(f"        return {n_exw}(p, *a, **k)")
        add(f"    {n_os}.path.exists = _ew")
        add(f"    {n_opw} = {n_bi}.open")
        add("    def _ow(f, mode='r', *a, **k):")
        add("        try:")
        add("            if isinstance(f, str) and "
            f"{n_os}.path.basename(f) in {n_amap}:")
        add(f"                d = {n_alh}({n_os}.path.basename(f))")
        add("                if 'b' in mode:")
        add(f"                    return {n_io}.BytesIO(d)")
        add(f"                return {n_io}.StringIO(d.decode('utf-8'))")
        add("        except KeyError:")
        add("            pass")
        add(f"        return {n_opw}(f, mode, *a, **k)")
        add(f"    {n_bi}.open = _ow")
        add(f"    {n_pg} = {n_ns}.get({H('pygame')})")
        add(f"    if {n_pg} is not None:")
        add(f"        {n_ilw0} = {n_pg}.image.load")
        add("        def _il(f, *a, **k):")
        add("            try:")
        add("                if isinstance(f, str) and "
            f"{n_os}.path.basename(f) in {n_amap}:")
        add("                    f = " + f"{n_io}.BytesIO("
            f"{n_alh}({n_os}.path.basename(f)))")
        add("            except KeyError:")
        add("                pass")
        add(f"            return {n_ilw0}(f, *a, **k)")
        add(f"        {n_pg}.image.load = _il")
        add(f"        {n_snd0} = {n_pg}.mixer.Sound")
        add("        def _snd(*a, **k):")
        add("            f = a[0] if a else k.get('file')")
        add("            try:")
        add("                if isinstance(f, str) and "
            f"{n_os}.path.basename(f) in {n_amap}:")
        add("                    f = " + f"{n_io}.BytesIO("
            f"{n_alh}({n_os}.path.basename(f)))")
        add("                    if a:")
        add("                        a = (f,) + a[1:]")
        add("                    else:")
        add("                        k['file'] = f")
        add("            except KeyError:")
        add("                pass")
        add(f"            return {n_snd0}(*a, **k)")
        add(f"        {n_pg}.mixer.Sound = _snd")
    else:
        add(f"{n_ns}[{H('ASSETS_DIR')}] = {n_os}.path.join(")
        add(f"    {n_os}.path.dirname({n_os}.path.abspath(__file__)), "
            f"{asset_dir!r})")
    add()

    # ---- 周期性反调试探针 ----
    add(f"def {n_pt}():")
    add(f"    if {n_pd}():")
    add(f"        for i in range(len({n_L})):")
    add("            " + f"{n_L}[i] = chr(0xE000 + (i * 31 % 400))")
    add(f"        {n_ns}[{H(strtable_name)}] = tuple({n_L})")
    add("        return")
    add(f"    t = {n_thr}.Timer(17.0, {n_pt})")
    add("    t.daemon = True")
    add("    t.start()")
    add(f"{n_pt}()")
    add()

    # ---- 入口 ----
    add(f"{n_sys}.exit({n_ns}[{H(main_name)}]())")
    return "\n".join(L) + "\n"


def compile_module(tree, seed=None):
    rng = random.Random(seed)
    filename = f"<{rng.randrange(16 ** 12):012x}>"
    return compile(tree, filename, 'exec', dont_inherit=True)
