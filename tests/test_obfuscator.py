# -*- coding: utf-8 -*-
"""SB3 -> 混淆 Python 单向转换测试。"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _support import *  # noqa: F401,F403

_SRC_DIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from ir import BlockType, ExprType
from obfuscator import obfuscate_sb3
from obfuscator.folding import fold_expression, fold_project

_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="80">'
    '<circle cx="50" cy="40" r="30" fill="#fc9"/></svg>'
)


def _stage_target():
    return {
        "isStage": True,
        "name": "Stage",
        "variables": {},
        "lists": {},
        "broadcasts": {},
        "blocks": {},
        "comments": {},
        "currentCostume": 0,
        "costumes": [],
        "sounds": [],
        "volume": 100,
        "layerOrder": 0,
        "tempo": 60,
        "videoTransparency": 50,
        "videoState": "on",
        "textToSpeechLanguage": None,
    }


def _write_sb3(folder, project_json, assets=None):
    path = os.path.join(folder, "input.sb3")
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "project.json", json.dumps(project_json, ensure_ascii=False))
        for name, content in (assets or {}).items():
            archive.writestr(name, content)
    return path


def _fold_project():
    blocks = {
        "hat": block("event_whenflagclicked", "set", None, top_level=True),
        "set": block("data_setvariableto", "if1", "hat",
                     {"VALUE": [3, "add", [10, ""]]},
                     {"VARIABLE": ["result", "v1"]}),
        "add": block("operator_add", None, "set", {
            "NUM1": [1, [4, "20"]], "NUM2": [1, [4, "22"]]}),
        "if1": block("control_if", "if2", "set",
                     {"CONDITION": [2, "eq1"], "SUBSTACK": [2, "change1"]}),
        "eq1": block("operator_equals", None, "if1", {
            "OPERAND1": [1, [4, "1"]], "OPERAND2": [1, [4, "1"]]}),
        "change1": block("data_changevariableby", None, "if1",
                         {"VALUE": [1, [4, "5"]]},
                         {"VARIABLE": ["result", "v1"]}),
        "if2": block("control_if", "repeat0", "if1",
                     {"CONDITION": [2, "eq2"], "SUBSTACK": [2, "change2"]}),
        "eq2": block("operator_equals", None, "if2", {
            "OPERAND1": [1, [4, "1"]], "OPERAND2": [1, [4, "2"]]}),
        "change2": block("data_changevariableby", None, "if2",
                         {"VALUE": [1, [4, "100"]]},
                         {"VARIABLE": ["result", "v1"]}),
        "repeat0": block("control_repeat", "say", "if2",
                         {"TIMES": [1, [4, "0"]],
                          "SUBSTACK": [2, "change3"]}),
        "change3": block("data_changevariableby", None, "repeat0",
                         {"VALUE": [1, [4, "1000"]]},
                         {"VARIABLE": ["result", "v1"]}),
        "say": block("looks_say", None, "repeat0",
                     {"MESSAGE": [3, "var", [10, ""]]}),
        "var": block("data_variable", None, "say", {},
                     {"VARIABLE": ["result", "v1"]}),
    }
    project_json = make_project(blocks, name="Secret")
    project_json["targets"][0]["variables"] = {"v1": ["result", 0]}
    project_json["targets"].insert(0, _stage_target())
    project = parse_scratch_project(project_json)
    fold_project(project)
    return project


def _walk_chain(stmt):
    seen = set()
    while stmt is not None and id(stmt) not in seen:
        seen.add(id(stmt))
        yield stmt
        stmt = stmt.next


def _all_statements(project):
    for sprite in project.sprites:
        stack = list(sprite.statements)
        seen = set()
        while stack:
            stmt = stack.pop()
            if stmt is None or id(stmt) in seen:
                continue
            seen.add(id(stmt))
            yield stmt
            stack.extend(stmt.body)
            stack.extend(stmt.else_body)
            if stmt.next is not None:
                stack.append(stmt.next)


def test_obfuscator_constant_folding():
    """OBF-1 常量表达式、恒定 if、0 次循环被简化"""
    print("[测试104] 混淆器常量折叠")

    project = _fold_project()
    statements = list(_all_statements(project))
    assert not [stmt for stmt in statements if stmt.type == BlockType.IF], \
        "恒定条件 if 应被简化"
    assert not [stmt for stmt in statements if stmt.type == BlockType.REPEAT], \
        "0 次循环应被删除"

    sets = [stmt for stmt in statements
            if stmt.type == BlockType.SET_VARIABLE]
    assert sets and sets[0].value.type == ExprType.NUMBER
    assert sets[0].value.value == 42

    expr = fold_expression(Expr(ExprType.JOIN, left=make_string("a"),
                                right=make_number(5)))
    assert expr.type == ExprType.STRING and expr.value == "a5"

    print("  [PASS] 常量折叠通过")
    return True


def test_obfuscator_end_to_end():
    """OBF-2 混淆导出、资产内嵌、源码信息不泄露且可运行"""
    print("[测试105] 混淆器端到端")

    with tempfile.TemporaryDirectory() as folder:
        project_json = make_project({
            "hat": block("event_whenflagclicked", "set", None, top_level=True),
            "set": block("data_setvariableto", "say", "hat",
                         {"VALUE": [3, "add", [10, ""]]},
                         {"VARIABLE": ["secret_value", "v1"]}),
            "add": block("operator_add", None, "set", {
                "NUM1": [1, [4, "20"]], "NUM2": [1, [4, "22"]]}),
            "say": block("looks_say", None, "set",
                         {"MESSAGE": [1, [10, "hello secret"]]}),
        }, name="SecretSprite")
        project_json["targets"][0]["variables"] = {
            "v1": ["secret_value", 0]}
        digest = hashlib.md5(_SVG.encode('utf-8')).hexdigest()
        md5ext = digest + ".svg"
        project_json["targets"][0]["costumes"] = [{
            "name": "cat",
            "assetId": digest,
            "md5ext": md5ext,
            "dataFormat": "svg",
            "rotationCenterX": 50,
            "rotationCenterY": 40,
        }]
        project_json["targets"].insert(0, _stage_target())
        sb3 = _write_sb3(folder, project_json, {md5ext: _SVG})
        output = os.path.join(folder, "protected.py")

        result = obfuscate_sb3(sb3, output, embed_assets=True, seed=7)
        assert os.path.exists(result.output)
        assert result.embedded_assets is True
        assert result.asset_count == 1
        assert result.clusters > 0
        assert not os.path.exists(os.path.join(folder, "protected_assets"))

        source = open(output, encoding="utf-8").read()
        for text in ("ScratchRuntime", "ScratchSprite", "motion_movesteps",
                     "event_whenflagclicked", "secret_value",
                     "hello secret", "SecretSprite", "import pygame",
                     "import marshal", "import zlib"):
            assert text not in source, text

        proc = subprocess.run(
            [sys.executable, output, "--headless", "--frames", "30",
             "--no-audio"],
            capture_output=True, text=True, timeout=90,
            stdin=subprocess.DEVNULL)
        assert proc.returncode == 0, proc.stderr
        assert "Traceback" not in proc.stderr

    print("  [PASS] 混淆器端到端通过")
    return True


def _dump_code_names(obf_path: str, names_path: str) -> None:
    """在子进程里运行混淆产物，dump 所有 code object 的名字集合。

    通过包装 zlib/bz2/lzma 的 decompress 拦截解密结果（不触碰
    builtins/marshal，避免触发 builtins 完整性探针）。
    """
    wrapper = os.path.join(os.path.dirname(obf_path), "_dump_wrapper.py")
    with open(wrapper, "w", encoding="utf-8") as handle:
        handle.write(
            "import marshal, sys, runpy, zlib, bz2, lzma\n"
            "path = sys.argv[1]\n"
            "out = sys.argv[2]\n"
            "# 让混淆产物以正确的 argv 运行（main 才会触发簇懒加载）\n"
            "sys.argv = [path] + sys.argv[3:]\n"
            "names = set()\n"
            "seen = set()\n"
            "def walk(code):\n"
            "    if id(code) in seen: return\n"
            "    seen.add(id(code))\n"
            "    names.update(code.co_names)\n"
            "    names.update(code.co_varnames)\n"
            "    for c in code.co_consts:\n"
            "        if hasattr(c, 'co_code'):\n"
            "            walk(c)\n"
            "def inspect_plain(plain):\n"
            "    try:\n"
            "        obj = marshal.loads(plain)\n"
            "    except Exception:\n"
            "        return\n"
            "    if hasattr(obj, 'co_code'):\n"
            "        if obj.co_filename.startswith('<'):\n"
            "            walk(obj)\n"
            "    elif hasattr(obj, 'get'):\n"
            "        c = obj.get('c')\n"
            "        if c is not None and hasattr(c, 'co_code')\\\n"
            "                and c.co_filename.startswith('<'):\n"
            "            walk(c)\n"
            "def wrap(mod):\n"
            "    real = mod.decompress\n"
            "    def d(data, *a, **k):\n"
            "        r = real(data, *a, **k)\n"
            "        inspect_plain(r)\n"
            "        return r\n"
            "    mod.decompress = d\n"
            "wrap(zlib)\n"
            "wrap(bz2)\n"
            "wrap(lzma)\n"
            "try:\n"
            "    runpy.run_path(path, run_name='__main__')\n"
            "except SystemExit:\n"
            "    pass\n"
            "with open(out, 'w', encoding='utf-8') as f:\n"
            "    f.write('\\n'.join(sorted(names)))\n"
        )
    result = subprocess.run(
        [sys.executable, wrapper, obf_path, names_path, "--headless",
         "--frames", "10", "--no-audio"],
        capture_output=True, text=True, timeout=90,
        stdin=subprocess.DEVNULL)
    assert os.path.exists(names_path), result.stderr
    # 至少要扫到一些 code object 名字，否则 wrapper 没有生效
    assert open(names_path, encoding="utf-8").read().strip(), result.stderr


def test_obfuscator_no_source_leak_in_bytecode():
    """OBF-2b 字节码 co_names/co_varnames 不含 Scratch 积木与原始标识"""
    print("[测试105b] 混淆器字节码名字扫描")

    with tempfile.TemporaryDirectory() as folder:
        project_json = make_project({
            "hat": block("event_whenflagclicked", "set", None, top_level=True),
            "set": block("motion_movesteps", "say", "hat",
                         {"STEPS": [1, [4, "10"]]}),
            "say": block("looks_say", None, "set",
                         {"MESSAGE": [1, [10, "top secret words"]]}),
        }, name="LeakSprite")
        project_json["targets"].insert(0, _stage_target())
        sb3 = _write_sb3(folder, project_json)
        output = os.path.join(folder, "protected.py")
        obfuscate_sb3(sb3, output, embed_assets=True, seed=5)

        names_path = os.path.join(folder, "names.txt")
        _dump_code_names(output, names_path)
        names = open(names_path, encoding="utf-8").read().splitlines()
        leaked = [n for n in (
            "motion_movesteps", "event_whenflagclicked", "looks_say",
            "ScratchRuntime", "ScratchSprite", "LeakSprite", "main",
            "when_green_flag") if n in names]
        assert not leaked, leaked

    print("  [PASS] 字节码名字扫描通过")
    return True


def test_obfuscator_tamper_detected():
    """OBF-2c 篡改载荷后 Silent Corrupt：非零退出且无明文校验提示"""
    print("[测试105c] 混淆器防篡改")

    with tempfile.TemporaryDirectory() as folder:
        project_json = make_project({
            "hat": block("event_whenflagclicked", None, None, top_level=True),
        }, name="TamperSprite")
        project_json["targets"].insert(0, _stage_target())
        sb3 = _write_sb3(folder, project_json)
        output = os.path.join(folder, "protected.py")
        obfuscate_sb3(sb3, output, embed_assets=True, seed=3)

        source = open(output, encoding="utf-8").read()
        # 定位一个段表数据行（密文块），翻转其中间一个字符
        lines = source.splitlines()
        target = None
        for index, line in enumerate(lines):
            if len(line) > 500 and "', '" in line:
                target = index
                break
        assert target is not None, "未找到密文数据行"
        line = lines[target]
        middle = len(line) // 2
        original = line[middle]
        replacement = 'A' if original != 'A' else 'B'
        lines[target] = line[:middle] + replacement + line[middle + 1:]
        tampered = os.path.join(folder, "tampered.py")
        with open(tampered, "w", encoding="utf-8", newline='\n') as handle:
            handle.write("\n".join(lines) + "\n")

        proc = subprocess.run(
            [sys.executable, tampered, "--headless", "--frames", "10",
             "--no-audio"],
            capture_output=True, text=True, timeout=90,
            stdin=subprocess.DEVNULL)
        assert proc.returncode != 0, "篡改后应非零退出"
        combined = (proc.stdout or '') + (proc.stderr or '')
        assert 'integrity' not in combined.lower()
        assert '校验' not in combined

    print("  [PASS] 防篡改通过")
    return True


def test_obfuscator_antidebug_detected():
    """OBF-2d 挂 sys.settrace 运行混淆产物应 Silent Corrupt"""
    print("[测试105d] 混淆器反调试")

    with tempfile.TemporaryDirectory() as folder:
        project_json = make_project({
            "hat": block("event_whenflagclicked", None, None, top_level=True),
        }, name="TraceSprite")
        project_json["targets"].insert(0, _stage_target())
        sb3 = _write_sb3(folder, project_json)
        output = os.path.join(folder, "protected.py")
        obfuscate_sb3(sb3, output, embed_assets=True, seed=11)

        wrapper = os.path.join(folder, "_trace_wrapper.py")
        with open(wrapper, "w", encoding="utf-8") as handle:
            handle.write(
                "import sys\n"
                "sys.settrace(lambda frame, event, arg: None)\n"
                "import runpy\n"
                "try:\n"
                "    runpy.run_path(sys.argv[1], run_name='__main__')\n"
                "except SystemExit as e:\n"
                "    sys.exit(e.code if isinstance(e.code, int) else 0)\n"
            )
        proc = subprocess.run(
            [sys.executable, wrapper, output, "--headless", "--frames", "10",
             "--no-audio"],
            capture_output=True, text=True, timeout=90,
            stdin=subprocess.DEVNULL)
        assert proc.returncode != 0, "调试器环境下应 Silent Corrupt"
        combined = (proc.stdout or '') + (proc.stderr or '')
        assert 'debugger' not in combined.lower()

        # 对照：不挂 trace 时正常
        proc = subprocess.run(
            [sys.executable, output, "--headless", "--frames", "10",
             "--no-audio"],
            capture_output=True, text=True, timeout=90,
            stdin=subprocess.DEVNULL)
        assert proc.returncode == 0, proc.stderr

    print("  [PASS] 反调试通过")
    return True


def test_obfuscator_external_assets():
    """OBF-3 关闭内嵌资产时导出独立资产目录并可运行"""
    print("[测试106] 混淆器外部资产")

    with tempfile.TemporaryDirectory() as folder:
        project_json = make_project({
            "hat": block("event_whenflagclicked", None, None, top_level=True),
        }, name="AssetSprite")
        digest = hashlib.md5(_SVG.encode('utf-8')).hexdigest()
        md5ext = digest + ".svg"
        project_json["targets"][0]["costumes"] = [{
            "name": "cat",
            "assetId": digest,
            "md5ext": md5ext,
            "dataFormat": "svg",
            "rotationCenterX": 50,
            "rotationCenterY": 40,
        }]
        project_json["targets"].insert(0, _stage_target())
        sb3 = _write_sb3(folder, project_json, {md5ext: _SVG})
        output = os.path.join(folder, "protected.py")

        result = obfuscate_sb3(sb3, output, embed_assets=False, seed=3)
        assert result.embedded_assets is False
        asset_dir = os.path.join(folder, "protected_assets")
        assert os.path.isfile(os.path.join(asset_dir, md5ext))

        proc = subprocess.run(
            [sys.executable, output, "--headless", "--frames", "20",
             "--no-audio"],
            capture_output=True, text=True, timeout=90,
            stdin=subprocess.DEVNULL)
        assert proc.returncode == 0, proc.stderr

    print("  [PASS] 混淆器外部资产通过")
    return True


def test_obfuscator_no_static_anchors():
    """OBF-2e 通用静态解包依赖的结构特征不复存在：
    无固定 sid 锚点、含算术派生片段、含 builtins 完整性探针"""
    print("[测试105e] 静态结构锚点清除")

    with tempfile.TemporaryDirectory() as folder:
        project_json = make_project({
            "hat": block("event_whenflagclicked", None, None, top_level=True),
        }, name="AnchorSprite")
        project_json["targets"].insert(0, _stage_target())
        sb3 = _write_sb3(folder, project_json)
        output = os.path.join(folder, "protected.py")
        obfuscate_sb3(sb3, output, embed_assets=True, seed=13)

        source = open(output, encoding="utf-8").read()
        # 固定段标识锚点（'str'/'main' 的 hex）必须不存在
        assert "'737472'" not in source, "存在 'str' 锚点"
        assert "'6d61696e'" not in source, "存在 'main' 锚点"
        # 至少一个片段由算术派生（非常量），通用解包器的常量假设失效
        assert "& 0xFFFFFFFFFFFFFFFF" in source, "缺少算术派生片段"
        # builtins 完整性探针存在（堵 exec/marshal.loads hook）
        assert "is not type(" in source, "缺少 builtins 完整性探针"

    print("  [PASS] 静态结构锚点清除通过")
    return True


def test_obfuscator_resists_exec_hook():
    """OBF-2f 纯 Python 替换 builtins.exec 截获 code object 的手法
    应被 builtins 完整性探针识别并 Silent Corrupt"""
    print("[测试105f] exec hook 抵抗")

    with tempfile.TemporaryDirectory() as folder:
        project_json = make_project({
            "hat": block("event_whenflagclicked", "set", None,
                         top_level=True),
            "set": block("looks_say", None, "hat",
                         {"MESSAGE": [1, [10, "hook bait"]]}),
        }, name="HookSprite")
        project_json["targets"].insert(0, _stage_target())
        sb3 = _write_sb3(folder, project_json)
        output = os.path.join(folder, "protected.py")
        obfuscate_sb3(sb3, output, embed_assets=True, seed=17)

        wrapper = os.path.join(folder, "_exec_hook.py")
        with open(wrapper, "w", encoding="utf-8") as handle:
            handle.write(
                "import builtins, runpy, sys, types\n"
                "captured = []\n"
                "orig = builtins.exec\n"
                "def hook(obj, gl=None, loc=None):\n"
                "    if (isinstance(obj, types.CodeType)\n"
                "            and obj.co_filename.startswith('<')):\n"
                "        captured.append(1)\n"
                "        raise SystemExit(0x51B3)\n"
                "    return orig(obj, gl, loc)\n"
                "builtins.exec = hook\n"
                "try:\n"
                "    runpy.run_path(sys.argv[1], run_name='__main__')\n"
                "except SystemExit as e:\n"
                "    if e.code == 0x51B3:\n"
                "        sys.stderr.write('SENTINEL-CAPTURED\\n')\n"
                "finally:\n"
                "    builtins.exec = orig\n"
            )
        proc = subprocess.run(
            [sys.executable, wrapper, output],
            capture_output=True, text=True, timeout=90,
            stdin=subprocess.DEVNULL)
        assert "SENTINEL-CAPTURED" not in proc.stderr, \
            "exec hook 成功截获 code object（探针未生效）"
        assert proc.returncode != 0, "hook 环境下应 Silent Corrupt 非零退出"

        # 对照：不挂 hook 时正常
        proc = subprocess.run(
            [sys.executable, output, "--headless", "--frames", "10",
             "--no-audio"],
            capture_output=True, text=True, timeout=90,
            stdin=subprocess.DEVNULL)
        assert proc.returncode == 0, proc.stderr

    print("  [PASS] exec hook 抵抗通过")
    return True


def test_license_binding():
    """OBF-T2a Ed25519 许可证参与密钥派生（指纹不进入分发物）：
    本机指纹构建可运行；错误指纹 Silent Corrupt；指纹哈希两端一致
    （多 seed 回归，覆盖随机配方与 sha256 指纹的组合）"""
    print("[测试T2a] 许可证绑定")

    with tempfile.TemporaryDirectory() as folder:
        project_json = make_project({
            "hat": block("event_whenflagclicked", "set", None,
                         top_level=True),
            "set": block("looks_say", None, "hat",
                         {"MESSAGE": [1, [10, "licensed"]]}),
        }, name="LicSprite")
        project_json["targets"].insert(0, _stage_target())
        sb3 = _write_sb3(folder, project_json)

        env = {**os.environ, "PYTHONPATH": _SRC_DIR}
        pub_path = os.path.join(folder, "public.key")
        priv_path = os.path.join(folder, "private.key")
        proc = subprocess.run(
            [sys.executable, "-m", "obfuscator.license", "keygen",
             "--out-dir", folder],
            capture_output=True, text=True, timeout=120, env=env,
            stdin=subprocess.DEVNULL)
        assert proc.returncode == 0, proc.stderr
        pub = open(pub_path, encoding="ascii").read().strip()

        lic_path = os.path.join(folder, "license.dat")
        proc = subprocess.run(
            [sys.executable, "-m", "obfuscator.license", "issue",
             "--priv", priv_path, "--product", "test-game",
             "--days", "30", "--out", lic_path],
            capture_output=True, text=True, timeout=120, env=env,
            stdin=subprocess.DEVNULL)
        assert proc.returncode == 0, proc.stderr

        proc = subprocess.run(
            [sys.executable, "-m", "obfuscator.license", "fingerprint"],
            capture_output=True, text=True, timeout=120, env=env,
            stdin=subprocess.DEVNULL)
        assert proc.returncode == 0, proc.stderr
        real_fp = proc.stdout.strip().splitlines()[-1].strip()

        # 许可证文件与产物均不含指纹（离线复算 K' 不可行的前提）
        lic_text = open(lic_path, encoding="ascii").read()
        assert real_fp not in lic_text and 'machine_fp' not in lic_text

        # F1 回归：6 个随机 seed（不同配方）+ 本机指纹 -> 全部可运行
        # （0.13.3 曾因指纹哈希两端不一致 5/6 概率自砖）
        for seed in (2, 3, 5, 8, 13, 21):
            output = os.path.join(folder, f"protected_s{seed}.py")
            proc = subprocess.run(
                [sys.executable, "-m", "obfuscator", sb3, output,
                 "--license-pubkey", pub, "--license-file", lic_path,
                 "--license-fp", real_fp, "--seed", str(seed)],
                capture_output=True, text=True, timeout=300, env=env,
                stdin=subprocess.DEVNULL)
            assert proc.returncode == 0, proc.stderr
            proc = subprocess.run(
                [sys.executable, output, "--headless", "--frames", "15",
                 "--no-audio"],
                capture_output=True, text=True, timeout=90,
                stdin=subprocess.DEVNULL)
            assert proc.returncode == 0, \
                f"seed={seed} 许可证产物应可运行: {proc.stderr[-400:]}"
            src = open(output, encoding="utf-8").read()
            assert real_fp not in src

        # 错误指纹 -> Silent Corrupt（非零退出且无明文提示）
        output_bad = os.path.join(folder, "protected_bad.py")
        proc = subprocess.run(
            [sys.executable, "-m", "obfuscator", sb3, output_bad,
             "--license-pubkey", pub, "--license-file", lic_path,
             "--license-fp", "ab" * 32, "--seed", "19"],
            capture_output=True, text=True, timeout=300, env=env,
            stdin=subprocess.DEVNULL)
        assert proc.returncode == 0, proc.stderr
        proc = subprocess.run(
            [sys.executable, output_bad, "--headless", "--frames", "15",
             "--no-audio"],
            capture_output=True, text=True, timeout=90,
            stdin=subprocess.DEVNULL)
        assert proc.returncode != 0, "错误指纹应 Silent Corrupt"
        combined = (proc.stdout or '') + (proc.stderr or '')
        assert 'license' not in combined.lower()

        # SCRATCH_OBF_DEBUG=1 时输出诊断（区分工具故障与静默腐蚀）
        proc = subprocess.run(
            [sys.executable, output_bad, "--headless", "--frames", "15",
             "--no-audio"],
            capture_output=True, text=True, timeout=90,
            stdin=subprocess.DEVNULL,
            env={**env, "SCRATCH_OBF_DEBUG": "1"})
        assert 'integrity' in (proc.stderr or '')

        # 篡改许可证签名 -> 生成端清晰报错
        bad_sig = open(lic_path, encoding="ascii").read().rstrip()
        tampered = lic_path + ".tampered"
        with open(tampered, "w", encoding="ascii") as handle:
            handle.write(bad_sig[:-4] + "AAAA\n")
        proc = subprocess.run(
            [sys.executable, "-m", "obfuscator", sb3, output,
             "--license-pubkey", pub, "--license-file", tampered,
             "--license-fp", real_fp],
            capture_output=True, text=True, timeout=120, env=env,
            stdin=subprocess.DEVNULL)
        assert proc.returncode != 0
        assert "许可证无效" in (proc.stderr or '')

    print("  [PASS] 许可证绑定通过")
    return True


def _has_native_compiler() -> bool:
    import shutil
    return shutil.which('gcc') is not None or shutil.which('cl') is not None


def test_native_build():
    """OBF-T2b Tier 2 原生编译：loader 编译为 .pyd，产物可运行且
    目录中不含解密器 Python 源码（无编译器时跳过）"""
    print("[测试T2b] native 原生编译")

    if not _has_native_compiler():
        print("  [SKIP] 未找到 C 编译器（gcc/cl），跳过 native 测试")
        return True

    try:
        import Cython  # noqa: F401
    except ImportError:
        print("  [SKIP] 未安装 Cython，跳过 native 测试")
        return True

    with tempfile.TemporaryDirectory() as folder:
        project_json = make_project({
            "hat": block("event_whenflagclicked", "set", None,
                         top_level=True),
            "set": block("looks_say", None, "hat",
                         {"MESSAGE": [1, [10, "native"]]}),
        }, name="NatSprite")
        project_json["targets"].insert(0, _stage_target())
        sb3 = _write_sb3(folder, project_json)

        env = {**os.environ, "PYTHONPATH": _SRC_DIR}
        out_dir = os.path.join(folder, "protected_native")
        proc = subprocess.run(
            [sys.executable, "-m", "obfuscator", sb3, out_dir,
             "--native", "--seed", "23"],
            capture_output=True, text=True, timeout=600, env=env,
            stdin=subprocess.DEVNULL)
        assert proc.returncode == 0, proc.stderr
        entries = os.listdir(out_dir)
        assert any(e.startswith('core.') and e.endswith(
            ('.pyd', '.so')) for e in entries), entries
        assert 'main.py' in entries
        # 解密器必须是原生扩展：目录里没有含分段表的 Python 源码
        loader_like = [e for e in entries if e.endswith('.py')
                       and e != 'main.py']
        assert not loader_like, loader_like

        proc = subprocess.run(
            [sys.executable, os.path.join(out_dir, 'main.py'),
             "--headless", "--frames", "15", "--no-audio"],
            capture_output=True, text=True, timeout=120,
            stdin=subprocess.DEVNULL)
        assert proc.returncode == 0, proc.stderr

    print("  [PASS] native 原生编译通过")
    return True


def test_obfuscator_tail_patch_resisted():
    """OBF-2g 源码完整性覆盖 EOF：尾部追加 / 删行 / 改行均应 Silent
    Corrupt（v2.5 曾只覆盖前缀，追加 164 字节静默通过）"""
    print("[测试105g] 尾部 patch 抵抗")

    with tempfile.TemporaryDirectory() as folder:
        project_json = make_project({
            "hat": block("event_whenflagclicked", None, None, top_level=True),
        }, name="PatchSprite")
        project_json["targets"].insert(0, _stage_target())
        sb3 = _write_sb3(folder, project_json)
        output = os.path.join(folder, "protected.py")
        obfuscate_sb3(sb3, output, embed_assets=True, seed=29)

        # 对照：不 patch 正常
        proc = subprocess.run(
            [sys.executable, output, "--headless", "--frames", "10",
             "--no-audio"],
            capture_output=True, text=True, timeout=90,
            stdin=subprocess.DEVNULL)
        assert proc.returncode == 0, proc.stderr

        source = open(output, encoding="utf-8").read()
        lines = source.splitlines()

        variants = {
            "tail-append": source + "\nprint('INJECTED-OK')\n",
            "tail-delete": "\n".join(lines[:-1]) + "\n",
            "probe-nop": source.replace(
                "    return False", "    return False\ndef _zz(): pass", 1),
        }
        for name, mutated in variants.items():
            path = os.path.join(folder, f"p_{name}.py")
            with open(path, "w", encoding="utf-8", newline='\n') as handle:
                handle.write(mutated)
            proc = subprocess.run(
                [sys.executable, path, "--headless", "--frames", "10",
                 "--no-audio"],
                capture_output=True, text=True, timeout=90,
                stdin=subprocess.DEVNULL)
            assert proc.returncode != 0, f"{name} 应 Silent Corrupt"
            combined = (proc.stdout or '') + (proc.stderr or '')
            assert 'INJECTED-OK' not in combined, name

            # DEBUG 诊断可见
            proc = subprocess.run(
                [sys.executable, path, "--headless", "--frames", "10",
                 "--no-audio"],
                capture_output=True, text=True, timeout=90,
                stdin=subprocess.DEVNULL,
                env={**os.environ, "SCRATCH_OBF_DEBUG": "1"})
            assert 'integrity' in (proc.stderr or ''), name

    print("  [PASS] 尾部 patch 抵抗通过")
    return True


TESTS = [
    test_obfuscator_constant_folding,
    test_obfuscator_end_to_end,
    test_obfuscator_no_source_leak_in_bytecode,
    test_obfuscator_tamper_detected,
    test_obfuscator_antidebug_detected,
    test_obfuscator_external_assets,
    test_obfuscator_no_static_anchors,
    test_obfuscator_resists_exec_hook,
    test_license_binding,
    test_native_build,
    test_obfuscator_tail_patch_resisted,
]
