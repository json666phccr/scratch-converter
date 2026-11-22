# -*- coding: utf-8 -*-
"""ScPython 资产读取：造型/声音元数据与 MD5 命名。

Scratch 的资产文件名是 ``<md5>.<ext>``，角色通过 ``md5ext`` 引用。
本模块把工程 ``assets/`` 下的文件转成 Scratch 需要的元数据，并返回字节内容
供导出 sb3 时写入压缩包。
"""

from __future__ import annotations

import hashlib
import os
import re
import struct
from typing import Dict, Optional, Tuple

from .errors import ScPythonError

_IMAGE_FORMATS = {'svg', 'png', 'jpg', 'jpeg'}
_SOUND_FORMATS = {'wav', 'mp3'}


def _png_size(data: bytes) -> Optional[Tuple[int, int]]:
    if len(data) >= 24 and data[:8] == b'\x89PNG\r\n\x1a\n' \
            and data[12:16] == b'IHDR':
        width, height = struct.unpack('>II', data[16:24])
        return int(width), int(height)
    return None


def _jpeg_size(data: bytes) -> Optional[Tuple[int, int]]:
    if len(data) < 4 or data[:2] != b'\xff\xd8':
        return None
    index = 2
    length = len(data)
    while index + 9 < length:
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        index += 2
        if marker in (0xD8, 0xD9):
            continue
        if index + 2 > length:
            break
        segment_length = struct.unpack('>H', data[index:index + 2])[0]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                      0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            if index + 7 <= length:
                height, width = struct.unpack('>HH', data[index + 3:index + 7])
                return int(width), int(height)
            return None
        index += segment_length
    return None


def _svg_size(data: bytes) -> Optional[Tuple[int, int]]:
    try:
        text = data.decode('utf-8', errors='ignore')
    except Exception:
        return None
    head = text[:4096]
    width = re.search(r'\bwidth\s*=\s*["\']([0-9.]+)', head)
    height = re.search(r'\bheight\s*=\s*["\']([0-9.]+)', head)
    if width and height:
        return int(float(width.group(1))), int(float(height.group(1)))
    viewbox = re.search(
        r'\bviewBox\s*=\s*["\']\s*[-\d.]+\s+[-\d.]+\s+([\d.]+)\s+([\d.]+)',
        head, re.IGNORECASE)
    if viewbox:
        return int(float(viewbox.group(1))), int(float(viewbox.group(2)))
    return None


def image_size(data: bytes, data_format: str) -> Optional[Tuple[int, int]]:
    if data_format == 'png':
        return _png_size(data)
    if data_format in ('jpg', 'jpeg'):
        return _jpeg_size(data)
    if data_format == 'svg':
        return _svg_size(data)
    return None


def _wav_info(data: bytes) -> Tuple[int, int]:
    """返回 (采样率, 采样数)"""
    rate = 44100
    samples = 0
    if len(data) >= 44 and data[:4] == b'RIFF' and data[8:12] == b'WAVE':
        index = 12
        block_align = 2
        data_size = 0
        while index + 8 <= len(data):
            chunk_id = data[index:index + 4]
            chunk_size = struct.unpack('<I', data[index + 4:index + 8])[0]
            body = index + 8
            if chunk_id == b'fmt ' and body + 16 <= len(data):
                rate = struct.unpack('<I', data[body + 4:body + 8])[0]
                block_align = struct.unpack('<H', data[body + 12:body + 14])[0] or 2
            elif chunk_id == b'data':
                data_size = chunk_size
                break
            index = body + chunk_size + (chunk_size & 1)
        if data_size and block_align:
            samples = max(0, data_size // block_align)
    return int(rate), int(samples)


class AssetLibrary:
    """按工程根目录读取 assets/ 下的资源"""

    def __init__(self, project_root: str, assets: Dict[str, bytes],
                 asset_dir: str = 'assets'):
        self.project_root = os.path.abspath(project_root)
        self.assets_root = os.path.abspath(
            os.path.join(self.project_root, asset_dir))
        self.assets = assets

    def resolve(self, reference: str, source_path: str = '') -> str:
        """把角色文件里的资源引用解析成实际路径"""
        text = str(reference).replace('\\', '/').strip()
        if not text:
            raise ScPythonError("资源引用不能为空", path=source_path)
        if text.startswith('assets/'):
            text = text[len('assets/'):]
        if os.path.isabs(text):
            raise ScPythonError(
                f"资源引用必须是 assets/ 下的相对路径: {reference}",
                path=source_path)
        candidate = os.path.abspath(os.path.join(self.assets_root, text))
        if not (candidate == self.assets_root
                or candidate.startswith(self.assets_root + os.sep)):
            raise ScPythonError(
                f"资源路径越界: {reference}", path=source_path)
        if not os.path.isfile(candidate):
            raise ScPythonError(
                f"找不到资源 {reference!r}（应在 {self.assets_root} 下）",
                path=source_path)
        return candidate

    def _load(self, reference: str, source_path: str,
              allowed: set) -> Tuple[str, str, bytes, str]:
        path = self.resolve(reference, source_path)
        extension = os.path.splitext(path)[1].lower().lstrip('.')
        if extension not in allowed:
            raise ScPythonError(
                f"不支持的资源格式 .{extension}: {reference}",
                path=source_path)
        with open(path, 'rb') as handle:
            data = handle.read()
        digest = hashlib.md5(data).hexdigest()
        md5ext = f"{digest}.{extension}"
        self.assets[md5ext] = data
        return path, digest, data, extension

    def costume(self, reference: str, source_path: str = '',
                name: Optional[str] = None) -> dict:
        path, digest, data, extension = self._load(
            reference, source_path, _IMAGE_FORMATS)
        size = image_size(data, extension)
        center_x = size[0] / 2 if size else 0
        center_y = size[1] / 2 if size else 0
        display = name if name is not None else \
            os.path.splitext(os.path.basename(path))[0]
        return {
            'name': display,
            'assetId': digest,
            'md5ext': f"{digest}.{extension}",
            'dataFormat': extension,
            'bitmapResolution': 1,
            'rotationCenterX': center_x,
            'rotationCenterY': center_y,
        }

    def sound(self, reference: str, source_path: str = '',
              name: Optional[str] = None) -> dict:
        path, digest, data, extension = self._load(
            reference, source_path, _SOUND_FORMATS)
        if extension == 'wav':
            rate, samples = _wav_info(data)
        else:
            rate, samples = 44100, 0
        display = name if name is not None else \
            os.path.splitext(os.path.basename(path))[0]
        return {
            'name': display,
            'assetId': digest,
            'md5ext': f"{digest}.{extension}",
            'dataFormat': extension,
            'rate': rate,
            'sampleCount': samples,
        }
