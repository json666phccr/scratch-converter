# -*- coding: utf-8 -*-
"""混淆载荷与加载器生成 v2.4（多态壳 + 反形状解析）。

与 v2.0/v2.1 的本质区别：**每次导出的加密配方都不同**。压缩算法、编码、
哈希族、密钥派生形式、密钥流布局、段标识、分段表形态、片段算术混合全部
逐次随机，加载器按同一配方生成。通用解包脚本依赖的固定结构特征
（8 个整型片段常量、固定 sid 锚点、固定算法组合）不复存在——逆向者
必须逐个产物分析其加载器，无法一份脚本通吃。

v2.4 追加（对抗"表达式形状解析器"——解析 `fromhex/getattr/decompress`
等结构提取配方的那类工具）：

- **字符串常量运行时构造**：加载器内所有字符串一律 `chr` 码 join，
  不再出现 `bytes.fromhex('...')` 形状；
- **KDF 10 形态 / 密钥流 4 布局 / 字符串链 4 拼接 / 片段两种混合式**；
- **sid 长度随机化**；
- **源码前缀自校验**：探针与密钥派生所在的加载器前缀参与哈希比对，
  patch 即 Silent Corrupt（Tier 1）；
- **SCRATCH_OBF_DEBUG=1** 输出诊断（区分工具自身故障与攻击腐蚀）。

安全结构：

- **密钥分裂 + 算术混合**：8 个 64 位片段中若干由其他片段派生；
- **多态配方**：压缩 zlib/bz2/lzma、编码 b85/b64、哈希族 6 种；
- **随机段标识**：段名每次导出随机化，无固定锚点；
- **段密钥链式派生**：key_i = KDF(prev_plain_digest, sid_i)；
- **分段 HMAC**：每段独立 salt + HMAC 完整性标签；
- **builtins 完整性探针**：exec/compile/__import__/marshal.loads
  被 Python 层替换即 Silent Corrupt；
- **函数簇懒加载**：类与 main 入末簇；
- **虚拟资产文件系统** + 字符串表 tuple 化。
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
from typing import Dict, List, Optional, Tuple

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
    kdf: int                # 段密钥派生形式 0..9
    ks_seed_order: int      # 解密时 seed = key+salt / salt+key
    ks_layout: int          # 块 = f(seed,ctr) 4 种布局（含 seed 预哈希）
    ks_width: int           # 计数器字节宽
    ks_endian: str          # 计数器字节序
    ks_start: int           # 计数器起点
    flip_idx: int           # tag 校验失败时翻转的字节下标
    flip_xor: int           # 翻转异或值
    corrupt_idx: int        # Silent Corrupt 翻转的字节下标
    corrupt_xor: int        # Silent Corrupt 异或值
    str_ks_order: int       # 字符串条目 seed 拼接形态 0..3
    table_form: int         # 分段表形态 0=字典 / 1=行列表
    fragments: List[int]    # 8 个片段的实际值
    derived: List[Tuple[int, int, int, int, int, int]]
    # (idx, parent, mult, add, xor_c, form)  form 0: (P*M+C)  1: ((P^C1)*M+C)
    str_sid: str
    main_sid: str
    cluster_sids: List[str] = field(default_factory=list)
    asset_sids: Dict[str, str] = field(default_factory=dict)
    # 许可证绑定（Tier 2）：payload/sig 以 b64 嵌入 loader，
    # 运行端 machine_fp 参与主密钥派生——fp 不对即解密失败
    license_payload_b64: Optional[str] = None
    license_sig_b64: Optional[str] = None
    license_expires: Optional[int] = None

    # ---- 生成端密码学 ----
    def kroot(self) -> bytes:
        return _hash_fn(self.hash_name)(b''.join(
            f.to_bytes(8, 'big') for f in self.fragments)).digest()

    def derive_key(self, prev: bytes, sid: bytes) -> bytes:
        h = _hash_fn(self.hash_name)
        hd = h(prev).digest()
        sd = h(sid).digest()
        if self.kdf == 0:
            return hmac.new(prev, sid, self.hash_name).digest()
        if self.kdf == 1:
            return hmac.new(sid, prev, self.hash_name).digest()
        if self.kdf == 2:
            return h(prev + sid).digest()
        if self.kdf == 3:
            return h(sid + prev).digest()
        if self.kdf == 4:
            return h(hd + sid).digest()
        if self.kdf == 5:
            return h(prev + sd).digest()
        if self.kdf == 6:
            return hmac.new(prev, sd, self.hash_name).digest()
        if self.kdf == 7:
            return hmac.new(hd, sid, self.hash_name).digest()
        if self.kdf == 8:
            return h(sd + prev).digest()
        return h(sid + hd).digest()

    def keystream(self, seed: bytes, length: int) -> bytes:
        h = _hash_fn(self.ks_hash_name)
        output = bytearray()
        counter = self.ks_start
        pre = h(seed).digest() if self.ks_layout >= 2 else None
        while len(output) < length:
            block_seed = counter.to_bytes(self.ks_width, self.ks_endian)
            if self.ks_layout == 0:
                output.extend(h(seed + block_seed).digest())
            elif self.ks_layout == 1:
                output.extend(h(block_seed + seed).digest())
            elif self.ks_layout == 2:
                output.extend(h(pre + block_seed).digest())
            else:
                output.extend(h(block_seed + pre).digest())
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
                            for _ in range(rng.randrange(10, 17)))
            if token[0].isalpha():
                return token

    fragments = [rng.getrandbits(64) for _ in range(8)]
    derived: List[Tuple[int, int, int, int, int, int]] = []
    derived_count = rng.choice((1, 2, 3))
    # 派生下标唯一且父片段下标更小，保证加载器按序赋值可行
    candidate_idx = list(range(1, 8))
    rng.shuffle(candidate_idx)
    for idx in candidate_idx[:derived_count]:
        parent = rng.randrange(idx)
        mult = (rng.getrandbits(32) | 1)
        add = rng.getrandbits(48)
        xor_c = rng.getrandbits(16)
        form = rng.randrange(2)
        derived.append((idx, parent, mult, add, xor_c, form))
        base = (fragments[parent] ^ xor_c) if form else fragments[parent]
        fragments[idx] = (base * mult + add) & _MASK64
    derived.sort()

    return Recipe(
        hash_name=rng.choice(_HASHES),
        ks_hash_name=rng.choice(_HASHES),
        comp=rng.choice(_COMPRESSION),
        enc=rng.choice(_ENCODERS),
        kdf=rng.randrange(10),
        ks_seed_order=rng.randrange(2),
        ks_layout=rng.randrange(4),
        ks_width=rng.choice((4, 8)),
        ks_endian=rng.choice(('big', 'little')),
        ks_start=rng.choice((0, 1)),
        flip_idx=rng.randrange(32),
        flip_xor=rng.choice(_FLIP_XORS),
        corrupt_idx=rng.randrange(32),
        corrupt_xor=rng.choice(_FLIP_XORS),
        str_ks_order=rng.randrange(4),
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
                  seed=None,
                  license: Optional[Tuple[bytes, bytes, bytes]] = None,
                  decoy_sources: Optional[List[str]] = None
                  ) -> PayloadSpec:
    rng = random.Random(seed)
    recipe = make_recipe(rng, len(cluster_sources), sorted(assets))
    kroot = recipe.kroot()

    if license is not None:
        # Tier 2 许可证绑定：binding = H(payload || sig || machine_fp)
        # machine_fp 为签发机器指纹；运行端 fp 不符 -> binding 错 -> 垃圾。
        # payload/sig 嵌入 loader 供运行端重算 binding。
        payload_bytes, sig_bytes, fp_bytes = license
        binding = recipe.prev_digest(
            payload_bytes + sig_bytes + fp_bytes)
        kroot = _hash_fn(recipe.hash_name)(kroot + binding).digest()
        recipe.license_payload_b64 = base64.b64encode(
            payload_bytes).decode('ascii')
        recipe.license_sig_b64 = base64.b64encode(sig_bytes).decode('ascii')
        try:
            import json
            data = json.loads(payload_bytes.decode('utf-8'))
            recipe.license_expires = data.get('expires_at')
        except (ValueError, UnicodeDecodeError):
            recipe.license_expires = None

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

    # 诱饵簇：与真簇同规格加密入表，但加载器永不调用——静态解包者
    # 解出后真假难辨，必须逐个执行/反编译才能辨识（提高成品率门槛）
    for decoy_source in (decoy_sources or ()):
        code = compile(decoy_source, f"<{rng.randrange(16 ** 12):012x}>",
                       'exec', dont_inherit=True)
        sid = ''.join(rng.choice(_SID_ALPHABET) for _ in
                      range(rng.randrange(10, 17)))
        while not sid[0].isalpha():
            sid = ''.join(rng.choice(_SID_ALPHABET)
                          for _ in range(rng.randrange(10, 17)))
        encrypt(sid, marshal.dumps(code), digest_main)

    for name, data in assets.items():
        encrypt(recipe.asset_sids[name], data, digest_main)

    return PayloadSpec(
        recipe=recipe,
        segments=segments,
        version=tuple(sys.version_info[:2]),
    )


def _encode_chain(recipe: Recipe, str_entries: List[str],
                  str_key: bytes) -> List[bytes]:
    """链式字符串表：条目密钥依赖前一条明文摘要，seed 拼接形态随配方。"""
    chain = b''
    entry_cts = []
    for entry in str_entries:
        raw = entry.encode('utf-8')
        order = recipe.str_ks_order
        if order == 0:
            seed = str_key + chain
        elif order == 1:
            seed = chain + str_key
        elif order == 2:
            seed = str_key + chain + str_key
        else:
            seed = chain + str_key + chain
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
                  asset_dir: str = 'assets', seed=None,
                  frame_check: bool = True,
                  self_hash: bool = True) -> str:
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
    n_lpb = name('l')
    n_lsb = name('l')
    n_fpv = name('f')
    n_fpf = name('f')
    n_h256 = name('h')
    n_cf = name('c')
    n_ph = name('h')
    n_tx = name('t')
    n_dbg = name('g')
    frag_names = [name('f') for _ in rec.fragments]

    str_sid_hex = _sid_hex(rec.str_sid)
    main_sid_hex = _sid_hex(rec.main_sid)
    cluster_sid_hexes = [_sid_hex(s) for s in rec.cluster_sids]
    dec_attr = {'b85': 'b85decode', 'b64': 'b64decode'}[rec.enc]

    # ---- 生成期辅助：字符串常量一律运行时由 chr 码构造 ----
    # （不再出现 bytes.fromhex('...') 形态：依赖该形状的静态解析器
    #   无法提取模块名/哈希族名，同时避免原生编译时常量折叠落盘）
    def H(value: str) -> str:
        codes = ", ".join(str(byte) for byte in value.encode('utf-8'))
        return f"''.join(map(chr, ({codes},)))"

    L: List[str] = []

    def add(line: str = '') -> None:
        L.append(line)

    # ---- imports（字符串常量运行时构造）----
    add(f"{n_imp} = __import__")
    add(f"{n_hex} = bytes.fromhex")
    for mod, binding in mod_names.items():
        add(f"{binding} = {n_imp}({H(mod)})")
    add(f"{n_bi} = {n_imp}({H('builtins')})")
    add(f"{n_ex} = getattr({n_bi}, {H('exec')})")
    add(f"{n_hf} = getattr({n_hash}, {H(rec.hash_name)})")
    add(f"{n_kh} = getattr({n_hash}, {H(rec.ks_hash_name)})")
    add(f"{n_h256} = getattr({n_hash}, {H('sha256')})")
    add(f"{n_cf} = False")
    add()

    # ---- 密钥分裂片段（算术派生 + 异或混合，两种形态随机）----
    for index, (fname, fragment) in enumerate(
            zip(frag_names, rec.fragments)):
        derived_here = [d for d in rec.derived if d[0] == index]
        if derived_here:
            _, parent, mult, addend, xor_c, form = derived_here[0]
            if form:
                add(f"{fname} = (({frag_names[parent]} ^ 0x{xor_c:X}) "
                    f"* 0x{mult:X} + 0x{addend:X}) & 0x{_MASK64:X}")
            else:
                add(f"{fname} = ({frag_names[parent]} * 0x{mult:X} "
                    f"+ 0x{addend:X}) & 0x{_MASK64:X}")
        else:
            add(f"{fname} = 0x{fragment:016X}")
    add(f"{n_k} = bytearray({n_hf}(b''.join(")
    add("    t.to_bytes(8, 'big') for t in ("
        + ", ".join(frag_names) + "))).digest())")
    add()

    # ---- 许可证绑定（Tier 2）：fp 参与主密钥派生 ----
    if rec.license_payload_b64 is not None:
        reg_path = 'SOFTWARE\\Microsoft\\Cryptography'
        add(f"{n_lpb} = {n_b85}.b64decode({rec.license_payload_b64!r})")
        add(f"{n_lsb} = {n_b85}.b64decode({rec.license_sig_b64!r})")
        v_parts = name('v')
        v_rg = name('v')
        v_tk = name('v')
        v_vv = name('v')
        v_tf = name('v')
        add(f"def {n_fpf}():")
        add(f"    {v_parts} = []")
        add("    try:")
        add(f"        if {n_sys}.platform == {H('win32')}:")
        add(f"            {v_rg} = {n_imp}({H('winreg')})")
        add(f"            {v_tk} = {v_rg}.OpenKey({v_rg}.HKEY_LOCAL_MACHINE, "
            f"{H(reg_path)})")
        add(f"            {v_vv}, _ = {v_rg}.QueryValueEx({v_tk}, "
            f"{H('MachineGuid')})")
        add(f"            {v_parts}.append({v_vv}.encode('utf-8'))")
        add("        else:")
        add(f"            for {v_tk} in (" + ", ".join(
            H(p) for p in ('/etc/machine-id',
                           '/var/lib/dbus/machine-id')) + "):")
        add("                try:")
        add(f"                    with open({v_tk}, {H('r')}, "
            f"encoding={H('utf-8')}) as {v_tf}:")
        add(f"                        {v_parts}.append("
            f"{v_tf}.read().strip().encode('utf-8'))")
        add("                    break")
        add("                except Exception:")
        add("                    pass")
        add("    except Exception:")
        add("        pass")
        add(f"    if not {v_parts}:")
        add(f"        {v_parts}.append(str("
            f"{n_imp}({H('uuid')}).getnode()).encode('utf-8'))")
        add(f"    {v_parts}.append("
            f"{n_imp}({H('platform')}).machine().encode('utf-8'))")
        # 指纹哈希固定 sha256，与签发端 license.machine_fingerprint 一致
        add(f"    return {n_h256}(b'|'.join({v_parts})).digest()")
        add(f"{n_fpv} = {n_fpf}()")
        add(f"{n_k} = bytearray({n_hf}(bytes({n_k}) + "
            f"{n_hf}({n_lpb} + {n_lsb} + {n_fpv}).digest()).digest())")
        if rec.license_expires is not None:
            add(f"if {n_imp}({H('time')}).time() > "
                f"{rec.license_expires}:")
            add(f"    {n_cr}()")
        add()

    # ---- 反调试探针（含 builtins 完整性检查）----
    # 函数内参数/局部名一律随机化：Cython 编译后函数签名存于 code object，
    # 语义名（sidhex/salt/plain 等）会构成词汇泄露面
    v_m = name('v')
    v_t = name('v')
    v_ms = name('v')
    add(f"def {n_pd}():")
    add("    try:")
    add(f"        if {n_sys}.gettrace() is not None:")
    add("            return True")
    add("    except Exception:")
    add("        pass")
    add("    try:")
    add(f"        {v_m} = getattr({n_sys}, {H('monitoring')}, None)")
    add(f"        if {v_m} is not None:")
    add(f"            for {v_t} in range(6):")
    add("                try:")
    add(f"                    if {v_m}.get_tool({v_t}) is not None:")
    add("                        return True")
    add("                except Exception:")
    add("                    pass")
    add("    except Exception:")
    add("        pass")
    add(f"    {v_ms} = {n_sys}.modules")
    add(f"    for {v_t} in ({', '.join(H(mod) for mod in _DEBUG_MODULES)},):")
    add(f"        if {v_t} in {v_ms}:")
    add("            return True")
    # builtins 完整性：Python 层替换 exec/compile/__import__/marshal.loads
    # 的 hook（类型为 'function'）与原生内建类型不符
    add(f"    for {v_t} in (" + ", ".join(
        H(nm) for nm in ('exec', 'compile', '__import__')) + "):")
    add(f"        if type(getattr({n_bi}, {v_t})) is not "
        f"type(getattr({n_bi}, {H('len')})):")
    add("            return True")
    add(f"    if type({n_mar}.loads) is not "
        f"type(getattr({n_bi}, {H('len')})):")
    add("        return True")
    add("    return False")
    dbg_msg = 'obfuscator: integrity/license binding failure'
    add(f"def {n_dbg}():")
    add("    try:")
    add(f"        if {n_os}.environ.get({H('SCRATCH_OBF_DEBUG')}):")
    add(f"            print({H(dbg_msg)}, file={n_sys}.stderr)")
    add("    except Exception:")
    add("        pass")
    add(f"def {n_cr}():")
    add(f"    global {n_cf}")
    add(f"    {n_cf} = True")
    add(f"    {n_k}[{rec.corrupt_idx}] ^= 0x{rec.corrupt_xor:X}")
    add(f"    {n_dbg}()")
    add(f"if {n_pd}():")
    add(f"    {n_cr}()")
    add(f"if {n_sys}.version_info[:2] != {spec.version!r}:")
    add(f"    {n_cr}()")
    add()

    # ---- 源码前缀自校验：本行之前的全部加载器源码参与哈希 ----
    # 探针/密钥派生/许可证绑定任何一行被 patch -> 哈希不符 -> Silent Corrupt
    if self_hash:
        marker = '#obf-selfchk'
        prefix_text = "\n".join(L) + "\n"
        ph = _hash_fn(rec.hash_name)(
            prefix_text.encode('utf-8')).digest()
        add(marker)
        add(f"{n_ph} = {ph!r}")
        add("try:")
        add(f"    {n_tx} = open(__file__, {H('rb')}).read()"
            f".decode({H('utf-8')})")
        add(r"    " + f"{n_tx} = {n_tx}.replace('\\r\\n', '\\n')"
            f".replace('\\r', '\\n')")
        add(f"    {n_tx} = {n_tx}[: {n_tx}.index({H(marker)})]")
        add(f"    if {n_hf}({n_tx}.encode({H('utf-8')})).digest() "
            f"!= {n_ph}:")
        add(f"        {n_cr}()")
        add("except Exception:")
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
    acc_variant = rng.randrange(2)
    p_s = name('p')
    p_n = name('p')
    v_o = name('v')
    v_c = name('v')
    v_sd = name('v')
    add(f"def {n_ksf}({p_s}, {p_n}):")
    add(f"    {v_o} = bytearray()")
    add(f"    {v_c} = {rec.ks_start}")
    if rec.ks_layout >= 2:
        add(f"    {v_sd} = {n_kh}({p_s}).digest()")
    add(f"    while len({v_o}) < {p_n}:")
    ctr = f"{v_c}.to_bytes({rec.ks_width}, {rec.ks_endian!r})"
    if rec.ks_layout == 0:
        block = f"{n_kh}({p_s} + {ctr})"
    elif rec.ks_layout == 1:
        block = f"{n_kh}({ctr} + {p_s})"
    elif rec.ks_layout == 2:
        block = f"{n_kh}({v_sd} + {ctr})"
    else:
        block = f"{n_kh}({ctr} + {v_sd})"
    if acc_variant == 0:
        add(f"        {v_o}.extend({block}.digest())")
    else:
        add(f"        {v_o} += {block}.digest()")
    add(f"        {v_c} += 1")
    add(f"    return bytes({v_o}[:{p_n}])")

    # ---- 段解密（KDF 10 形态按配方生成）----
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
        if rec.kdf == 3:
            return (f"bytearray({n_hf}({n_hex}({sid}) + "
                    f"bytes({prev})).digest())")
        if rec.kdf == 4:
            return (f"bytearray({n_hf}({n_hf}(bytes({prev})).digest() "
                    f"+ {n_hex}({sid})).digest())")
        if rec.kdf == 5:
            return (f"bytearray({n_hf}(bytes({prev}) + "
                    f"{n_hf}({n_hex}({sid})).digest()).digest())")
        if rec.kdf == 6:
            return (f"bytearray({n_hmac}.new(bytes({prev}), "
                    f"{n_hf}({n_hex}({sid})).digest(), {n_hf}).digest())")
        if rec.kdf == 7:
            return (f"bytearray({n_hmac}.new("
                    f"{n_hf}(bytes({prev})).digest(), "
                    f"{n_hex}({sid}), {n_hf}).digest())")
        if rec.kdf == 8:
            return (f"bytearray({n_hf}({n_hf}({n_hex}({sid})).digest() "
                    f"+ bytes({prev})).digest())")
        return (f"bytearray({n_hf}({n_hex}({sid}) + "
                f"{n_hf}(bytes({prev})).digest()).digest())")

    p_sid = name('p')
    p_prev = name('p')
    v_fr = name('v')
    v_sa = name('v')
    v_tg = name('v')
    v_pt = name('v')
    v_ct = name('v')
    v_k2 = name('v')
    v_ks = name('v')
    v_pl = name('v')
    add(f"def {n_dec}({p_sid}, {p_prev}):")
    add(f"    global {n_cf}")
    if frame_check:
        add(f"    {v_fr} = {n_sys}._getframe(1)")
        add(f"    if {v_fr} is None or " +
            f"{n_os}.path.abspath(__file__) != "
            f"{v_fr}.f_code.co_filename:")
        add(f"        {n_cr}()")
    add(f"    {v_sa}, {v_tg}, {v_pt} = {n_segs}[{p_sid}]")
    add(f"    {v_ct} = getattr({n_b85}, {H(dec_attr)})"
        f"(''.join({v_pt}))")
    add(f"    {v_k2} = {kdf_expr(p_prev, p_sid)}")
    add("    if not " + f"{n_hmac}.compare_digest(")
    add(f"            {n_hmac}.new(bytes({v_k2}), {v_ct}, "
        f"{n_hf}).digest(), {v_tg}):")
    add(f"        {n_cf} = True")
    add(f"        {n_dbg}()")
    add(f"        {v_k2}[{rec.flip_idx}] ^= 0x{rec.flip_xor:X}")
    if rec.ks_seed_order == 0:
        ks_input = f"bytes({v_k2}) + {v_sa}"
    else:
        ks_input = f"{v_sa} + bytes({v_k2})"
    add(f"    {v_ks} = {n_ksf}({ks_input}, len({v_ct}))")
    add(f"    {v_pl} = bytes(a ^ b for a, b in zip({v_ct}, {v_ks}))")
    add(f"    return getattr({n_comp}, {H('decompress')})({v_pl})")
    add()

    # ---- 字符串表（链式解码，一次性展开）----
    v_raw = name('v')
    v_prev = name('v')
    v_ect = name('v')
    kroot_expr = f"bytes({n_k})"
    str_sid_lit = repr(str_sid_hex)
    add(f"{n_L} = []")
    add(f"{n_sk} = {kdf_expr(kroot_expr, str_sid_lit)}")
    add(f"{n_sp} = {n_dec}({str_sid_lit}, {kroot_expr})")
    add(f"{v_prev} = b''")
    add(f"for {v_ect} in {n_mar}.loads({n_sp}):")
    if rec.str_ks_order == 0:
        entry_seed = f"{n_sk} + {v_prev}"
    elif rec.str_ks_order == 1:
        entry_seed = f"{v_prev} + {n_sk}"
    elif rec.str_ks_order == 2:
        entry_seed = f"{n_sk} + {v_prev} + {n_sk}"
    else:
        entry_seed = f"{v_prev} + {n_sk} + {v_prev}"
    add(f"    {v_raw} = bytes(a ^ b for a, b in zip(")
    add(f"        {v_ect}, {n_ksf}({entry_seed}, len({v_ect}))))")
    add("    try:")
    add(f"        {n_L}.append({v_raw}.decode('utf-8'))")
    add("    except Exception:")
    add(f"        {n_cr}()")
    add(f"        {n_L}.append('')")
    add(f"    {v_prev} = {n_kh}({v_raw}).digest()")
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
    p_cid = name('p')
    p_g = name('p')
    add(f"{n_csid} = ({', '.join(repr(h) for h in cluster_sid_hexes)},)")
    add(f"def {n_clh}({p_cid}, {p_g}):")
    add("    " + f"{n_ex}({n_mar}.loads("
        f"{n_dec}({n_csid}[{p_cid}], {n_md})), {p_g})")
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
        p_bn = name('p')
        v_d = name('v')
        add(f"def {n_alh}({p_bn}):")
        add(f"    {v_d} = {n_acache}.get({p_bn})")
        add(f"    if {v_d} is None:")
        add(f"        {v_d} = {n_dec}({n_amap}[{p_bn}], {n_md})")
        add(f"        {n_acache}[{p_bn}] = {v_d}")
        add(f"    return {v_d}")
        add(f"{n_ns}[{H(asset_helper)}] = {n_alh}")
        add(f"if {n_amap}:")
        add(f"    {n_exw} = {n_os}.path.exists")
        p_p = name('p')
        p_a = name('p')
        p_k = name('p')
        p_f = name('p')
        p_m = name('p')
        add(f"    def _ew({p_p}, *{p_a}, **{p_k}):")
        add("        try:")
        add("            if isinstance(" + f"{p_p}, str) and "
            f"{n_os}.path.basename({p_p}) in {n_amap}:")
        add("                return True")
        add("        except Exception:")
        add("            pass")
        add(f"        return {n_exw}({p_p}, *{p_a}, **{p_k})")
        add(f"    {n_os}.path.exists = _ew")
        add(f"    {n_opw} = {n_bi}.open")
        add(f"    def _ow({p_f}, {p_m}='r', *{p_a}, **{p_k}):")
        add("        try:")
        add("            if isinstance(" + f"{p_f}, str) and "
            f"{n_os}.path.basename({p_f}) in {n_amap}:")
        add(f"                {v_d} = {n_alh}({n_os}.path.basename({p_f}))")
        add(f"                if 'b' in {p_m}:")
        add(f"                    return {n_io}.BytesIO({v_d})")
        add(f"                return {n_io}.StringIO({v_d}.decode('utf-8'))")
        add("        except KeyError:")
        add("            pass")
        add(f"        return {n_opw}({p_f}, {p_m}, *{p_a}, **{p_k})")
        add(f"    {n_bi}.open = _ow")
        add(f"    {n_pg} = {n_ns}.get({H('pygame')})")
        add(f"    if {n_pg} is not None:")
        add(f"        {n_ilw0} = {n_pg}.image.load")
        add(f"        def _il({p_f}, *{p_a}, **{p_k}):")
        add("            try:")
        add("                if isinstance(" + f"{p_f}, str) and "
            f"{n_os}.path.basename({p_f}) in {n_amap}:")
        add(f"                    {p_f} = " + f"{n_io}.BytesIO("
            f"{n_alh}({n_os}.path.basename({p_f})))")
        add("            except KeyError:")
        add("                pass")
        add(f"            return {n_ilw0}({p_f}, *{p_a}, **{p_k})")
        add(f"        {n_pg}.image.load = _il")
        add(f"        {n_snd0} = {n_pg}.mixer.Sound")
        add(f"        def _snd(*{p_a}, **{p_k}):")
        add(f"            {p_f} = {p_a}[0] if {p_a} else "
            f"{p_k}.get('file')")
        add("            try:")
        add("                if isinstance(" + f"{p_f}, str) and "
            f"{n_os}.path.basename({p_f}) in {n_amap}:")
        add(f"                    {p_f} = " + f"{n_io}.BytesIO("
            f"{n_alh}({n_os}.path.basename({p_f})))")
        add(f"                    if {p_a}:")
        add(f"                        {p_a} = ({p_f},) + {p_a}[1:]")
        add("                    else:")
        add(f"                        {p_k}['file'] = {p_f}")
        add("            except KeyError:")
        add("                pass")
        add(f"            return {n_snd0}(*{p_a}, **{p_k})")
        add(f"        {n_pg}.mixer.Sound = _snd")
    else:
        add(f"{n_ns}[{H('ASSETS_DIR')}] = {n_os}.path.join(")
        add(f"    {n_os}.path.dirname({n_os}.path.abspath(__file__)), "
            f"{asset_dir!r})")
    add()

    # ---- 周期性反调试探针 ----
    v_i = name('v')
    v_t2 = name('v')
    add(f"def {n_pt}():")
    add(f"    if {n_pd}():")
    add(f"        for {v_i} in range(len({n_L})):")
    add("            " + f"{n_L}[{v_i}] = chr(0xE000 + ({v_i} * 31 % 400))")
    add(f"        {n_ns}[{H(strtable_name)}] = tuple({n_L})")
    add("        return")
    add(f"    {v_t2} = {n_thr}.Timer(17.0, {n_pt})")
    add(f"    {v_t2}.daemon = True")
    add(f"    {v_t2}.start()")
    add(f"{n_pt}()")
    add()

    # ---- 入口（SCRATCH_OBF_DEBUG=1 时输出诊断，发布模式静默）----
    add("try:")
    add(f"    {n_sys}.exit({n_ns}[{H(main_name)}]())")
    add("except SystemExit:")
    add("    raise")
    add("except Exception:")
    add(f"    if {n_cf}:")
    add(f"        {n_dbg}()")
    add("    raise")
    return "\n".join(L) + "\n"


def compile_module(tree, seed=None):
    rng = random.Random(seed)
    filename = f"<{rng.randrange(16 ** 12):012x}>"
    return compile(tree, filename, 'exec', dont_inherit=True)
