# -*- coding: utf-8 -*-
"""Files / Clipping & Blending / Asset Manager 扩展测试"""

import base64
import io
import json
import os
import sys
import tempfile

import pygame

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import *


def _tiny_png(color=(255, 0, 0, 255), size=(40, 40)):
    """生成一张纯色 PNG 字节（测试用）"""
    image = pygame.Surface(size, pygame.SRCALPHA)
    image.fill(color)
    buffer = io.BytesIO()
    # 保存到内存流时必须给 namehint，否则 pygame 会写成 TGA
    pygame.image.save(image, buffer, 'box.png')
    return buffer.getvalue()


def test_files_extension():
    """Files 扩展：下载文本 / data URL，打开模式与无头模式选择文件"""
    print("[测试84] Files 文件扩展")

    project = make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("files_download", None, "b1",
                    inputs={"TEXT": [1, [10, "hello"]],
                            "FILE": [1, [10, "note.txt"]]}),
    }, name="FilesSprite")
    project["extensions"] = ["files"]

    code = generate_python(parse_scratch_project(project))
    assert "_extension_files" in code, "应拼装 files 扩展源码"
    assert "self.extension('files', 'files_download'" in code

    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](headless=True, audio=False)
    sprite = namespace["FilesSprite"]()
    runtime.add_sprite(sprite)
    download_dir = tempfile.mkdtemp()
    runtime._files_download_dir = download_dir
    try:
        def call(opcode, inputs=None):
            return sprite.extension('files', opcode, inputs or {}, {})

        call('files_download', {'TEXT': '你好，世界', 'FILE': 'note.txt'})
        path = os.path.join(download_dir, 'note.txt')
        assert os.path.exists(path)
        with open(path, encoding='utf-8') as handle:
            assert handle.read() == '你好，世界'

        payload = base64.b64encode(b'url-bytes').decode('ascii')
        call('files_downloadURL',
             {'URL': 'data:application/octet-stream;base64,' + payload,
              'FILE': 'from_url.bin'})
        with open(os.path.join(download_dir, 'from_url.bin'), 'rb') as handle:
            assert handle.read() == b'url-bytes'

        # 无头模式没有文件选择框，直接返回空字符串
        assert call('files_showPickerAs', {'as': 'text'}) == ''
        assert call('files_showPickerExtensions',
                    {'extension': '.txt'}) == ''

        call('files_setOpenMode', {'mode': 'selector'})
        assert runtime._files_open_mode == 'selector'
    finally:
        runtime.running = False
        runtime.shutdown()

    print("  [PASS] Files 文件扩展通过")
    return True


def test_clipping_blending_extension():
    """Clipping & Blending：裁剪框、混合模式与停止时重置"""
    print("[测试85] Clipping & Blending 裁剪与颜色混合")

    assets = tempfile.mkdtemp()
    with open(os.path.join(assets, 'box.png'), 'wb') as handle:
        handle.write(_tiny_png())

    project = make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("xeltallivclipblend_setClipbox", "b3", "b1",
                    inputs={"X1": [1, [4, "0"]], "Y1": [1, [4, "0"]],
                            "X2": [1, [4, "100"]], "Y2": [1, [4, "100"]]}),
        "b3": block("xeltallivclipblend_setBlend2", None, "b2",
                    inputs={"BLENDMODE": [1, [10, "additive"]]}),
    }, name="ClipSprite")
    project["extensions"] = ["xeltallivclipblend"]
    project["targets"][0]["costumes"] = [{
        "name": "box", "md5ext": "box.png", "dataFormat": "png",
        "rotationCenterX": None, "rotationCenterY": None,
    }]

    code = generate_python(parse_scratch_project(project))
    assert "_extension_clipping_blending" in code
    assert "_blend_blit" in code, "应拼装混合渲染辅助函数"
    assert ("self.extension('xeltallivclipblend', "
            "'xeltallivclipblend_setClipbox'") in code
    assert ("self.extension('xeltallivclipblend', "
            "'xeltallivclipblend_setBlend2'") in code

    written = write_scratch_project(parse_scratch_project(project))
    opcodes = [item.get("opcode") for target in written["targets"]
               for item in target["blocks"].values()]
    assert "xeltallivclipblend_setClipbox" in opcodes
    assert "xeltallivclipblend" in written.get("extensions", [])

    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](
        headless=True, audio=False, assets_dir=assets)
    sprite = namespace["ClipSprite"]()
    runtime.add_sprite(sprite)
    try:
        def call(opcode, inputs=None):
            return sprite.extension('xeltallivclipblend', opcode,
                                    inputs or {}, {})

        assert call('xeltallivclipblend_getClipbox',
                    {'PROP': 'width'}) == ''
        call('xeltallivclipblend_setClipbox',
             {'X1': 20, 'Y1': 20, 'X2': 0, 'Y2': -20})
        assert sprite._clipbox == {
            'x_min': 0, 'y_min': -20, 'x_max': 20, 'y_max': 20}
        assert call('xeltallivclipblend_getClipbox',
                    {'PROP': 'width'}) == 20
        assert call('xeltallivclipblend_getClipbox',
                    {'PROP': 'min y'}) == -20

        # 裁剪框之外的像素不应被角色覆盖
        surface = runtime.stage_surface
        surface.fill((0, 0, 0))
        sprite.costume_number = 1
        sprite.costume_name = 'box'
        sprite._draw(surface, runtime._ui_font())
        center_x = runtime.stage_width // 2
        center_y = runtime.stage_height // 2
        assert surface.get_at((center_x - 10, center_y))[:3] == (0, 0, 0), \
            "裁剪框左侧不应绘制"
        assert surface.get_at((center_x + 10, center_y))[:3] == (255, 0, 0), \
            "裁剪框内部应绘制"

        # additive 混合：在深灰背景上直接相加
        call('xeltallivclipblend_setClipbox',
             {'X1': 0, 'Y1': 0, 'X2': 0, 'Y2': 0})
        call('xeltallivclipblend_clearClipbox')
        call('xeltallivclipblend_setBlend2', {'BLENDMODE': 'additive'})
        assert call('xeltallivclipblend_getBlend') == 'additive'
        assert call('xeltallivclipblend_getAdditiveBlend') is True
        surface.fill((10, 10, 10))
        sprite._draw(surface, runtime._ui_font())
        assert surface.get_at((center_x, center_y))[:3] == (255, 10, 10), \
            "additive 混合应把颜色相加"

        # 旧版 additive 积木映射到 additive legacy，getBlend 仍报告 additive
        call('xeltallivclipblend_setBlend', {'BLENDMODE': 'additive'})
        assert sprite._blend_mode == 'additive legacy'
        assert call('xeltallivclipblend_getBlend') == 'additive'
        call('xeltallivclipblend_setAdditiveBlend', {'STATE': 'off'})
        assert sprite._blend_mode == 'default'
        assert call('xeltallivclipblend_getAdditiveBlend') is False

        # 图章也遵守裁剪框
        call('xeltallivclipblend_setClipbox',
             {'X1': 0, 'Y1': -20, 'X2': 20, 'Y2': 20})
        runtime.pen_clear()
        runtime.pen_stamp(sprite)
        pen = runtime.pen_layer
        assert pen.get_at((center_x + 10, center_y))[3] > 0
        assert pen.get_at((center_x - 10, center_y))[3] == 0, \
            "画笔图章应受裁剪框限制"

        # 停止全部时清除扩展状态
        sprite._blend_mode = 'multiply'
        runtime.stop_all_scripts()
        assert sprite._clipbox is None
        assert sprite._blend_mode == 'default'
    finally:
        runtime.running = False
        runtime.shutdown()

    print("  [PASS] Clipping & Blending 裁剪与颜色混合通过")
    return True


def test_asset_manager_extension():
    """Asset Manager：造型/声音增删改名排序与数据查询"""
    print("[测试86] Asset Manager 资源管理")

    assets = tempfile.mkdtemp()
    wav_url = 'data:audio/wav;base64,' + base64.b64encode(
        b'RIFF\x24\x00\x00\x00WAVEfmt ').decode()
    project = make_project({
        "b1": block("event_whenflagclicked", "b2", None, top_level=True),
        "b2": block("lmsAssets_addSound", "b3", "b1",
                    inputs={"URL": [1, [10, wav_url]],
                            "NAME": [1, [10, "startup"]]}),
        "b3": block("lmsAssets_renameSound", None, "b2",
                    inputs={"NAME": [1, [10, "renamed"]]},
                    fields={"SOUND": ["startup", None]}),
    }, name="AssetSprite")
    project["extensions"] = ["lmsAssets"]
    project["targets"][0]["costumes"] = [{
        "name": "original", "md5ext": "original.png", "dataFormat": "png",
        "rotationCenterX": None, "rotationCenterY": None,
    }]
    with open(os.path.join(assets, 'original.png'), 'wb') as handle:
        handle.write(_tiny_png((0, 128, 255, 255)))

    code = generate_python(parse_scratch_project(project))
    assert "_extension_asset_manager" in code
    assert "self.extension('lmsAssets', 'lmsAssets_addSound'" in code
    assert "self.extension('lmsAssets', 'lmsAssets_renameSound'" in code
    assert "'SOUND': 'startup'" in code, "声音菜单字段应保留"

    written = write_scratch_project(parse_scratch_project(project))
    opcodes = [item.get("opcode") for target in written["targets"]
               for item in target["blocks"].values()]
    assert "lmsAssets_addSound" in opcodes
    assert "lmsAssets" in written.get("extensions", [])

    namespace = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    runtime = namespace["ScratchRuntime"](
        headless=True, audio=False, assets_dir=assets)
    sprite = namespace["AssetSprite"]()
    runtime.add_sprite(sprite)
    try:
        def call(opcode, inputs=None):
            return sprite.extension('lmsAssets', opcode, inputs or {}, {})

        png_url = ('data:image/png;base64,'
                   + base64.b64encode(_tiny_png((0, 255, 0, 255))).decode())
        call('lmsAssets_addCostume', {'URL': png_url, 'NAME': 'added'})
        assert [c['name'] for c in sprite.costumes] == ['original', 'added']
        assert json.loads(call('lmsAssets_getAllCostumes')) == [
            'original', 'added']
        assert call('lmsAssets_getCostumeAtIndex', {'INDEX': 2}) == 'added'

        assert call('lmsAssets_getCostumeData',
                    {'ATTRIBUTE': 'index', 'COSTUME': 'added'}) == 2
        assert call('lmsAssets_getCostumeData',
                    {'ATTRIBUTE': 'format', 'COSTUME': 'added'}) == 'png'
        assert call('lmsAssets_getCostumeData',
                    {'ATTRIBUTE': 'header', 'COSTUME': 'added'}) == 'image/png'
        asset_id = call('lmsAssets_getCostumeData',
                        {'ATTRIBUTE': 'asset ID', 'COSTUME': 'added'})
        assert len(asset_id) == 32, "asset ID 应是内容哈希"
        assert call('lmsAssets_getCostumeData',
                    {'ATTRIBUTE': 'dataURI', 'COSTUME': 'added'}
                    ).startswith('data:image/png;base64,')
        assert call('lmsAssets_getCostumeData',
                    {'ATTRIBUTE': 'index', 'COSTUME': 'missing'}) == ''

        call('lmsAssets_renameCostume',
             {'COSTUME': 'added', 'NAME': 'renamed'})
        assert call('lmsAssets_getCostumeAtIndex', {'INDEX': 2}) == 'renamed'

        # 当前造型保持不变；重排后仍指向同一个造型
        sprite.costume_number = 2
        sprite.costume_name = 'renamed'
        call('lmsAssets_reorderCostume', {'INDEX1': 2, 'INDEX2': 1})
        assert [c['name'] for c in sprite.costumes] == ['renamed', 'original']
        assert sprite.costume_name == 'renamed'
        assert sprite.costume_number == 1

        call('lmsAssets_deleteCostume', {'COSTUME': 'original'})
        assert [c['name'] for c in sprite.costumes] == ['renamed']
        assert sprite.costume_number == 1

        wav_url = 'data:audio/wav;base64,' + base64.b64encode(
            b'RIFF\x24\x00\x00\x00WAVEfmt ').decode()
        call('lmsAssets_addSound', {'URL': wav_url, 'NAME': 'beep'})
        assert json.loads(call('lmsAssets_getAllSounds')) == ['beep']
        assert call('lmsAssets_getSoundAtIndex', {'INDEX': 1}) == 'beep'
        assert call('lmsAssets_getSoundData',
                    {'ATTRIBUTE': 'format', 'SOUND': 'beep'}) == 'wav'
        assert call('lmsAssets_getSoundData',
                    {'ATTRIBUTE': 'header', 'SOUND': 'beep'}) == 'audio/wav'
        call('lmsAssets_renameSound', {'SOUND': 'beep', 'NAME': 'ding'})
        assert json.loads(call('lmsAssets_getAllSounds')) == ['ding']
        call('lmsAssets_deleteSound', {'SOUND': 'ding'})
        assert json.loads(call('lmsAssets_getAllSounds')) == []

        assert json.loads(call('lmsAssets_getAllSprites')) == ['AssetSprite']
        assert call('lmsAssets_getSpriteValue2',
                    {'TARGET': '_myself_', 'EXPORT': 'name'}) == 'AssetSprite'
        assert call('lmsAssets_getSpriteValue',
                    {'EXPORT': 'dataURI'}) == ''
        loaded = json.loads(call('lmsAssets_getLoadedExtensions'))
        assert 'lmsassets' in loaded

        call('lmsAssets_renameSprite',
             {'TARGET': '_myself_', 'NAME': 'RenamedSprite'})
        assert sprite.name == 'RenamedSprite'
        assert runtime.find_sprite('RenamedSprite') is sprite

        call('lmsAssets_deleteSprite', {'TARGET': '_myself_'})
        assert sprite not in runtime.sprites
    finally:
        runtime.running = False
        runtime.shutdown()

    print("  [PASS] Asset Manager 资源管理通过")
    return True


TESTS = [
    test_files_extension,
    test_clipping_blending_extension,
    test_asset_manager_extension,
]
