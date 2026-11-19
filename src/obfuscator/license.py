# -*- coding: utf-8 -*-
"""Ed25519 许可证体系（Tier 2，P6）。

无第三方依赖：Ed25519 按 RFC 8032 参考实现（sign + verify，扩展坐标）。

许可证模型：

- 开发者 `keygen` 生成私钥（自留）与公钥（嵌入产物）；
- `issue` 为目标机器签发许可证：
  ``{"product_id", "machine_fp", "expires_at", "features", "nonce"}``
  规范化 JSON + Ed25519 签名，文件格式 ``b64(payload).b64(sig)``；
- 产物构建时传入 ``--license-pubkey`` 与 ``--license-file``，许可证
  **内容（payload+sig）与签发机器指纹一起参与主密钥派生**：
  ``K' = H(K_root || H(payload || sig || fp))``
  ——机器不对 / 许可证被换 / payload 被改，密钥全错 → Silent Corrupt，
  **没有独立的"校验分支"可 patch**（fp 校验即密钥派生本身）。

CLI::

    python -m obfuscator.license keygen --out-dir keys/
    python -m obfuscator.license issue --priv keys/private.key \
        --product mygame [--days 365] [--features a,b] [--fp <hex>] \
        --out license.dat
    python -m obfuscator.license show license.dat
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import secrets
import sys
import time
from typing import Optional, Tuple

# ===================== Ed25519（RFC 8032 参考） =====================

_P = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, _P - 2, _P)) % _P
_I = pow(2, (_P - 1) // 4, _P)


def _recover_x(y: int, sign_bit: int) -> Optional[int]:
    if y >= _P:
        return None
    x2 = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P)
    if x2 == 0:
        if sign_bit:
            return None
        return 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P != 0:
        x = x * _I % _P
    if (x * x - x2) % _P != 0:
        return None
    if (x & 1) != sign_bit:
        x = _P - x
    return x


_GY = 4 * pow(5, _P - 2, _P) % _P
_G = (_recover_x(_GY, 0), _GY, 1, _recover_x(_GY, 0) * _GY % _P)
_NEUTRAL = (0, 1, 1, 0)


def _point_add(P, Q):
    x1, y1, z1, t1 = P
    x2, y2, z2, t2 = Q
    a = (y1 - x1) * (y2 - x2) % _P
    b = (y1 + x1) * (y2 + x2) % _P
    c = 2 * t1 * t2 * _D % _P
    d = 2 * z1 * z2 % _P
    e, f, g, h = b - a, d - c, d + c, b + a
    return (e * f % _P, g * h % _P, f * g % _P, e * h % _P)


def _point_mul(s: int, P):
    Q = _NEUTRAL
    while s > 0:
        if s & 1:
            Q = _point_add(Q, P)
        P = _point_add(P, P)
        s >>= 1
    return Q


def _point_equal(P, Q) -> bool:
    if (P[0] * Q[2] - Q[0] * P[2]) % _P != 0:
        return False
    if (P[1] * Q[2] - Q[1] * P[2]) % _P != 0:
        return False
    return True


def _point_compress(P) -> bytes:
    zinv = pow(P[2], _P - 2, _P)
    x = P[0] * zinv % _P
    y = P[1] * zinv % _P
    return int.to_bytes(y | ((x & 1) << 255), 32, 'little')


def _point_decompress(s: bytes):
    if len(s) != 32:
        return None
    y = int.from_bytes(s, 'little')
    sign_bit = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign_bit)
    if x is None:
        return None
    return (x, y, 1, x * y % _P)


def _sha512_modq(s: bytes) -> int:
    return int.from_bytes(hashlib.sha512(s).digest(), 'little') % _L


def _secret_expand(secret: bytes) -> Tuple[int, bytes]:
    if len(secret) != 32:
        raise ValueError('私钥长度必须为 32 字节')
    h = hashlib.sha512(secret).digest()
    a = int.from_bytes(h[:32], 'little')
    a &= (1 << 254) - 8
    a |= (1 << 254)
    return (a, h[32:])


def publickey(secret: bytes) -> bytes:
    """私钥 32 字节 -> 公钥 32 字节"""
    a, _ = _secret_expand(secret)
    return _point_compress(_point_mul(a, _G))


def sign(secret: bytes, msg: bytes) -> bytes:
    a, prefix = _secret_expand(secret)
    A = _point_compress(_point_mul(a, _G))
    r = _sha512_modq(prefix + msg)
    R = _point_mul(r, _G)
    Rs = _point_compress(R)
    h = _sha512_modq(Rs + A + msg)
    s = (r + h * a) % _L
    return Rs + int.to_bytes(s, 32, 'little')


def verify(public: bytes, msg: bytes, signature: bytes) -> bool:
    if len(public) != 32 or len(signature) != 64:
        return False
    A = _point_decompress(public)
    if A is None:
        return False
    R = _point_decompress(signature[:32])
    if R is None:
        return False
    s = int.from_bytes(signature[32:], 'little')
    if s >= _L:
        return False
    h = _sha512_modq(signature[:32] + public + msg)
    return _point_equal(_point_mul(s, _G),
                        _point_add(R, _point_mul(h, A)))


# ===================== 机器指纹 =====================

def machine_fingerprint() -> bytes:
    """稳定机器指纹：Windows MachineGuid / Linux machine-id，
    兜底 MAC + 平台标识。生成端签发与运行端校验必须一致。"""
    parts = []
    try:
        if sys.platform == 'win32':
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r'SOFTWARE\Microsoft\Cryptography')
            value, _ = winreg.QueryValueEx(key, 'MachineGuid')
            parts.append(value.encode('utf-8'))
        else:
            for path in ('/etc/machine-id', '/var/lib/dbus/machine-id'):
                try:
                    with open(path, encoding='utf-8') as handle:
                        parts.append(handle.read().strip().encode('utf-8'))
                    break
                except OSError:
                    continue
    except OSError:
        pass
    if not parts:
        import uuid
        parts.append(str(uuid.getnode()).encode('utf-8'))
    import platform
    parts.append(platform.machine().encode('utf-8'))
    return hashlib.sha256(b'|'.join(parts)).digest()


# ===================== 许可证 =====================

def license_payload(product_id: str, machine_fp: bytes,
                    expires_at: Optional[int], features: Tuple[str, ...],
                    nonce: str) -> bytes:
    """规范化 JSON payload（排序键 + 紧凑分隔符），签名的对象"""
    data = {
        'product_id': product_id,
        'machine_fp': machine_fp.hex(),
        'features': sorted(features),
        'nonce': nonce,
    }
    if expires_at is not None:
        data['expires_at'] = int(expires_at)
    return json.dumps(data, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False).encode('utf-8')


def issue_license(private_key: bytes, product_id: str,
                  machine_fp: Optional[bytes] = None,
                  expires_at: Optional[int] = None,
                  features: Tuple[str, ...] = ()) -> Tuple[bytes, bytes]:
    """返回 (payload_bytes, sig_bytes)。machine_fp 缺省取本机。"""
    if machine_fp is None:
        machine_fp = machine_fingerprint()
    payload = license_payload(product_id, machine_fp, expires_at,
                              features, secrets.token_hex(8))
    return payload, sign(private_key, payload)


def encode_license(payload: bytes, sig: bytes) -> str:
    """license.dat 文本：b64(payload) + '.' + b64(sig)"""
    return (base64.b64encode(payload).decode('ascii') + '.'
            + base64.b64encode(sig).decode('ascii'))


def decode_license(text: str) -> Tuple[bytes, bytes]:
    payload_b64, _, sig_b64 = text.strip().partition('.')
    return (base64.b64decode(payload_b64),
            base64.b64decode(sig_b64))


def verify_license(public_key: bytes, license_text: str
                   ) -> Tuple[dict, bytes, bytes]:
    """验签并解析。返回 (payload_dict, payload_bytes, sig_bytes)。

    签名无效 / payload 非法 -> LicenseError。
    注意：过期与机器不匹配不在本函数检查——它们由密钥派生兜底
    （错误的 fp / 过期不改变派生正确性，运行时另行处理过期）。
    """
    payload, sig = decode_license(license_text)
    if not verify(public_key, payload, sig):
        raise LicenseError('许可证签名无效（pubkey 不匹配或内容被改）')
    try:
        data = json.loads(payload.decode('utf-8'))
        if not isinstance(data, dict) or 'machine_fp' not in data:
            raise ValueError
    except (ValueError, UnicodeDecodeError) as exc:
        raise LicenseError(f'许可证 payload 非法: {exc}') from exc
    return data, payload, sig


class LicenseError(Exception):
    """许可证错误（生成端清晰报错；运行端走 Silent Corrupt）"""


def check_expiry(payload_dict: dict) -> None:
    expires_at = payload_dict.get('expires_at')
    if expires_at is not None and time.time() > expires_at:
        raise LicenseError('许可证已过期')


# ===================== CLI =====================

def _cli_keygen(args) -> None:
    os.makedirs(args.out_dir, exist_ok=True)
    priv_path = os.path.join(args.out_dir, 'private.key')
    pub_path = os.path.join(args.out_dir, 'public.key')
    priv = secrets.token_bytes(32)
    pub = publickey(priv)
    with open(priv_path, 'w', encoding='ascii') as handle:
        handle.write(priv.hex())
    with open(pub_path, 'w', encoding='ascii') as handle:
        handle.write(pub.hex())
    print(f'私钥（自留，切勿提交仓库）: {priv_path}')
    print(f'公钥（嵌入产物）        : {pub_path}')
    print(f'公钥 hex: {pub.hex()}')


def _cli_issue(args) -> None:
    with open(args.priv, encoding='ascii') as handle:
        priv = bytes.fromhex(handle.read().strip())
    fp = bytes.fromhex(args.fp) if args.fp else machine_fingerprint()
    expires_at = int(time.time() + args.days * 86400) if args.days else None
    features = tuple(f.strip() for f in args.features.split(',')
                     if f.strip()) if args.features else ()
    payload, sig = issue_license(priv, args.product, fp, expires_at,
                                 features)
    data = json.loads(payload.decode('utf-8'))
    text = encode_license(payload, sig)
    if args.out:
        with open(args.out, 'w', encoding='ascii') as handle:
            handle.write(text + '\n')
        print(f'许可证已写入: {args.out}')
    else:
        print(text)
    print(f"  product_id : {data['product_id']}")
    print(f"  machine_fp : {data['machine_fp'][:16]}...")
    print(f"  expires_at : {data.get('expires_at', '永不过期')}")
    print(f"  features   : {data['features']}")


def _cli_show(args) -> None:
    with open(args.license, encoding='ascii') as handle:
        text = handle.read()
    payload, sig = decode_license(text)
    data = json.loads(payload.decode('utf-8'))
    print(f'payload : {payload.decode("utf-8")}')
    print(f'sig     : {sig.hex()[:32]}...')
    try:
        check_expiry(data)
    except LicenseError as exc:
        print(f'状态    : {exc}')
    else:
        print('状态    : 有效期内')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog='obfuscator.license',
        description='Ed25519 许可证工具（无第三方依赖）')
    sub = parser.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('keygen', help='生成签发密钥对')
    p.add_argument('--out-dir', default='license_keys')
    p.set_defaults(func=_cli_keygen)

    p = sub.add_parser('issue', help='为机器签发许可证')
    p.add_argument('--priv', required=True, help='private.key 路径')
    p.add_argument('--product', required=True, help='产品标识')
    p.add_argument('--days', type=int, default=0,
                   help='有效天数（0 = 永不过期）')
    p.add_argument('--features', default='',
                   help='逗号分隔的功能列表')
    p.add_argument('--fp', default=None,
                   help='目标机器指纹 hex（缺省为本机）')
    p.add_argument('--out', default=None, help='license.dat 输出路径')
    p.set_defaults(func=_cli_issue)

    p = sub.add_parser('show', help='查看许可证内容')
    p.add_argument('license')
    p.set_defaults(func=_cli_show)

    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == '__main__':
    sys.exit(main())
