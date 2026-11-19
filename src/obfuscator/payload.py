# -*- coding: utf-8 -*-
"""混淆载荷与加载器生成 v2。

安全结构：

- **密钥分裂**：主密钥 = SHA256(8 个散布的 64 位片段)，文件中不存在完整密钥；
- **分段 HMAC**：每个段（主程序/函数簇/字符串表/资产）独立 salt + HMAC-SHA256
  完整性标签，篡改任意字节即解密失败；
- **Silent Corrupt**：校验失败 / 检测到调试器 / 解释器版本不符时不报清晰错误，
  而是翻转密钥字节继续解密，让垃圾数据在远离检测点的地方自然崩溃；
- **函数簇懒加载**：顶层函数拆分为独立加密的簇，由 trampoline 首次调用时解密；
- **虚拟资产文件系统**：内嵌资产不落盘，通过包装 open/exists/pygame 加载接口
  按需解密；
- **周期性反调试探针**：运行中检测 trace/调试器，命中后腐蚀字符串表。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import marshal
import os
import random
import sys
import zlib
from dataclasses import dataclass
from typing import Dict, List, Tuple

_SEG_MAIN = 'main'
_SEG_STR = 'str'
_DEBUG_MODULES = ('pdb', 'pydevd', 'ptvsd', 'debugpy', 'frida')
_INJECTED_MODULES = (
    'math', 'time', 'random', 're', 'array', 'decimal', 'os', 'io',
    'base64', 'argparse', 'threading', 'json', 'functools', 'heapq',
    '_thread', 'pygame',
)


def _keystream(key: bytes, length: int) -> bytes:
    output = bytearray()
    counter = 0
    while len(output) < length:
        output.extend(
            hashlib.sha256(key + counter.to_bytes(4, 'big')).digest())
        counter += 1
    return bytes(output[:length])


def _xor(data: bytes, key: bytes) -> bytes:
    return bytes(byte ^ key[index % len(key)]
                 for index, byte in enumerate(data))


@dataclass
class PayloadSpec:
    fragments: List[int]
    segments: Dict[str, Tuple[bytes, bytes, bytes]]  # sid -> (salt, tag, ct)
    version: Tuple[int, int]


def build_payload(stage1_code, cluster_sources: List[str],
                  str_entries: List[str], assets: Dict[str, bytes],
                  seed=None) -> PayloadSpec:
    rng = random.Random(seed)
    fragments = [rng.getrandbits(64) for _ in range(8)]
    kroot = hashlib.sha256(b''.join(
        fragment.to_bytes(8, 'big') for fragment in fragments)).digest()

    segments: Dict[str, Tuple[bytes, bytes, bytes]] = {}

    def encrypt(sid: str, plain: bytes, prev_digest: bytes) -> bytes:
        """链式段加密：段密钥 = HMAC(prev_digest, sid)。

        返回明文摘要，作为下一段密钥派生的输入——批量解密必须按
        链条顺序进行，无法乱序/并行静态求解。
        """
        salt = os.urandom(16)
        key = hmac.new(prev_digest, sid.encode(), hashlib.sha256).digest()
        compressed = zlib.compress(plain, 9)
        ciphertext = _xor(compressed, _keystream(key + salt, len(compressed)))
        tag = hmac.new(key, ciphertext, hashlib.sha256).digest()
        segments[sid] = (salt, tag, ciphertext)
        return hashlib.sha256(plain).digest()

    # 链条：K_root -> str -> main -> {簇, 资产}
    digest_str = encrypt(_SEG_STR, marshal.dumps(_encode_chain(
        str_entries, hmac.new(kroot, _SEG_STR.encode(),
                              hashlib.sha256).digest())), kroot)
    digest_main = encrypt(_SEG_MAIN, marshal.dumps({'c': stage1_code}),
                          digest_str)

    cluster_codes = []
    for index, source in enumerate(cluster_sources):
        code = compile(source, f"<{rng.randrange(16 ** 12):012x}>",
                       'exec', dont_inherit=True)
        cluster_codes.append(code)
        encrypt(f'c{index}', marshal.dumps(code), digest_main)

    for name, data in assets.items():
        encrypt('a:' + name, data, digest_main)

    return PayloadSpec(
        fragments=fragments,
        segments=segments,
        version=tuple(sys.version_info[:2]),
    )


def _encode_chain(str_entries: List[str], str_key: bytes) -> List[bytes]:
    """链式字符串表：条目密钥依赖前一条明文摘要。"""
    chain = b''
    entry_cts = []
    for entry in str_entries:
        raw = entry.encode('utf-8')
        ks = _keystream(str_key + chain, len(raw))
        entry_cts.append(_xor(raw, ks))
        chain = hashlib.sha256(raw).digest()
    return entry_cts


def _chunks(data: bytes, size: int = 2048) -> List[str]:
    encoded = base64.b85encode(data).decode('ascii')
    return [encoded[i:i + size] for i in range(0, len(encoded), size)]


def _sid_hex(sid: str) -> str:
    return sid.encode().hex()


def loader_source(spec: PayloadSpec, *, main_name: str,
                  strtable_name: str, cluster_helper: str,
                  asset_helper: str, embed_assets: bool,
                  asset_dir: str = 'assets', seed=None) -> str:
    rng = random.Random(seed)
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
                 ('os', 'sys', 'hashlib', 'hmac', 'marshal', 'zlib',
                  'base64', 'threading', 'io')}
    n_os = mod_names['os']
    n_sys = mod_names['sys']
    n_hash = mod_names['hashlib']
    n_hmac = mod_names['hmac']
    n_mar = mod_names['marshal']
    n_zlib = mod_names['zlib']
    n_b85 = mod_names['base64']
    n_thr = mod_names['threading']
    n_io = mod_names['io']
    n_bi = name('b')
    n_ex = name('e')
    n_k = name('k')
    n_segs = name('s')
    n_ksf = name('k')
    n_dec = name('d')
    n_pd = name('p')
    n_cr = name('c')
    n_L = name('s')
    n_sk = name('k')
    n_ns = name('n')
    n_clh = name('c')
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
    frag_names = [name('f') for _ in spec.fragments]

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
    add()

    # ---- 密钥分裂片段 ----
    for index, (fname, fragment) in enumerate(
            zip(frag_names, spec.fragments)):
        add(f"{fname} = 0x{fragment:016X}")
    add(f"{n_k} = bytearray({n_hash}.sha256(b''.join(")
    add("    t.to_bytes(8, 'big') for t in ("
        + ", ".join(frag_names) + "))).digest())")
    add()

    # ---- 反调试探针 ----
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
    add("    return False")
    add(f"def {n_cr}():")
    add(f"    {n_k}[13] ^= 0x5A")
    add(f"if {n_pd}():")
    add(f"    {n_cr}()")
    add(f"if {n_sys}.version_info[:2] != {spec.version!r}:")
    add(f"    {n_cr}()")
    add()

    # ---- 分段表 ----
    add(f"{n_segs} = {{")
    for sid, (salt, tag, ct) in spec.segments.items():
        parts = ", ".join(repr(chunk) for chunk in _chunks(ct))
        add(f"    {_sid_hex(sid)!r}: ({salt!r}, {tag!r}, [{parts}]),")
    add("}")
    add(f"def {n_ksf}(key, n):")
    add("    out = bytearray()")
    add("    c = 0")
    add("    while len(out) < n:")
    add(f"        out.extend({n_hash}.sha256("
        "key + c.to_bytes(4, 'big')).digest())")
    add("        c += 1")
    add("    return bytes(out[:n])")
    add(f"def {n_dec}(sidhex, prev):")
    add(f"    fr = {n_sys}._getframe(1)")
    add("    if fr is None or " +
        f"{n_os}.path.abspath(__file__) != fr.f_code.co_filename:")
    add(f"        {n_cr}()")
    add(f"    salt, tag, parts = {n_segs}[sidhex]")
    add(f"    ct = {n_b85}.b85decode(''.join(parts))")
    add(f"    k2 = bytearray({n_hmac}.new(bytes(prev), "
        f"{n_hex}(sidhex), {n_hash}.sha256).digest())")
    add("    if not " + f"{n_hmac}.compare_digest(")
    add(f"            {n_hmac}.new(bytes(k2), ct, "
        f"{n_hash}.sha256).digest(), tag):")
    add("        k2[9] ^= 0x37")
    add(f"    ks = {n_ksf}(bytes(k2) + salt, len(ct))")
    add("    plain = bytes(a ^ b for a, b in zip(ct, ks))")
    add(f"    return {n_zlib}.decompress(plain)")
    add()

    # ---- 字符串表（链式解码，一次性展开）----
    add(f"{n_L} = []")
    add(f"{n_sk} = {n_hmac}.new(bytes({n_k}), {H(_SEG_STR)}.encode(), "
        f"{n_hash}.sha256).digest()")
    add(f"{n_sp} = {n_dec}({_sid_hex(_SEG_STR)!r}, bytes({n_k}))")
    add("prev = b''")
    add(f"for ect in {n_mar}.loads({n_sp}):")
    add("    raw = bytes(a ^ b for a, b in zip(")
    add(f"        ect, {n_ksf}({n_sk} + prev, len(ect))))")
    add("    try:")
    add(f"        {n_L}.append(raw.decode('utf-8'))")
    add("    except Exception:")
    add(f"        {n_cr}()")
    add(f"        {n_L}.append('')")
    add(f"    prev = {n_hash}.sha256(raw).digest()")
    add(f"{n_pd2} = {n_hash}.sha256({n_sp}).digest()")
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
    add(f"{n_ns}[{H(strtable_name)}] = {n_L}")
    add()

    # ---- 函数簇懒加载 ----
    add(f"def {n_clh}(cid, g):")
    add("    " + f"{n_ex}({n_mar}.loads({n_dec}("
        f"'63' + str(cid).encode().hex(), {n_md})), g)")
    add(f"{n_ns}[{H(cluster_helper)}] = {n_clh}")
    add()

    # ---- 主程序 ----
    add(f"{n_mp} = {n_dec}({_sid_hex(_SEG_MAIN)!r}, {n_pd2})")
    add(f"{n_mainc} = {n_mar}.loads({n_mp})[{H('c')}]")
    add(f"{n_md} = {n_hash}.sha256({n_mp}).digest()")
    add(f"{n_ex}({n_mainc}, {n_ns})")
    add()

    # ---- 资产：内嵌虚拟 FS / 外部目录 ----
    if embed_assets:
        asset_map = {
            sid[2:]: _sid_hex(sid)
            for sid in spec.segments if sid.startswith('a:')
        }
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
