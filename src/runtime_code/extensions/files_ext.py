# -*- coding: utf-8 -*-
"""files 文件扩展（选择并读取文件、下载文本/URL）"""

def _files_download_dir():
    """下载目录：默认系统“下载”文件夹，可用 SCRATCH_DOWNLOAD_DIR 覆盖"""
    import os
    path = os.environ.get('SCRATCH_DOWNLOAD_DIR') \
        or os.path.join(os.path.expanduser('~'), 'Downloads')
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        return os.getcwd()
    return path


def _files_save(data, filename, directory=None):
    """把字节写入下载目录，返回实际路径（失败时为空字符串）"""
    import os
    name = os.path.basename(_sc_str(filename).replace('\\', '/')).strip()
    if not name:
        name = 'download.txt'
    folder = directory or _files_download_dir()
    try:
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, name)
        with open(path, 'wb') as handle:
            handle.write(data)
    except OSError:
        return ''
    return path


def _files_decode_data_url(url):
    """解析 data: URL；不是 data URL 时返回 None"""
    import base64
    text = _sc_str(url)
    if not text.lower().startswith('data:'):
        return None
    header, _, payload = text[5:].partition(',')
    try:
        if ';base64' in header.lower():
            return base64.b64decode(payload)
        from urllib.parse import unquote_to_bytes
        return unquote_to_bytes(payload)
    except Exception:
        return None


def _files_fetch(url):
    """读取 URL 内容；支持 data: URL 与 http(s)"""
    data = _files_decode_data_url(url)
    if data is not None:
        return data
    try:
        import urllib.request
        with urllib.request.urlopen(_sc_str(url), timeout=20) as response:
            return response.read()
    except Exception:
        return None


def _files_pick_file(extension, as_mode):
    """弹出系统文件选择框；取消或没有图形界面时返回空字符串"""
    extension = _sc_str(extension).strip()
    try:
        import tkinter
        from tkinter import filedialog
    except Exception:
        return ''
    try:
        root = tkinter.Tk()
        root.withdraw()
        try:
            root.attributes('-topmost', True)
        except Exception:
            pass
        pattern = '*' + extension if extension else '*.*'
        path = filedialog.askopenfilename(
            filetypes=[('Files', pattern), ('All files', '*.*')])
        root.destroy()
    except Exception:
        return ''
    if not path:
        return ''
    try:
        if _sc_str(as_mode).strip().lower() == 'url':
            import base64
            import mimetypes
            mime = mimetypes.guess_type(path)[0] or 'application/octet-stream'
            with open(path, 'rb') as handle:
                payload = handle.read()
            return ('data:%s;base64,%s'
                    % (mime, base64.b64encode(payload).decode('ascii')))
        with open(path, 'r', encoding='utf-8', errors='replace') as handle:
            return handle.read()
    except OSError:
        return ''


def _extension_files(runtime, sprite, opcode, inputs, fields):
    """files：读取本地文件、下载文本/URL"""
    key = str(opcode).lower().replace('_', '')
    if key.endswith('setopenmode'):
        runtime._files_open_mode = _sc_str(
            _ext_input(inputs, fields, 'MODE', 'mode', default='modal'))
        return 0
    if 'showpicker' in key:
        # 有 as 参数的积木才有这个输入，没有时按文本读取
        as_mode = _ext_input(inputs, fields, 'AS', 'as', default='text')
        extension = _sc_str(
            _ext_input(inputs, fields, 'EXTENSION', 'extension', default=''))
        if getattr(runtime, 'headless', False):
            return ''
        return _files_pick_file(extension, as_mode)
    if key.endswith('downloadurl'):
        url = _sc_str(_ext_input(inputs, fields, 'URL', 'url', default=''))
        name = _sc_str(
            _ext_input(inputs, fields, 'FILE', 'file', default='download.txt'))
        data = _files_fetch(url)
        if data is not None:
            _files_save(data, name, getattr(runtime, '_files_download_dir', None))
        return 0
    if key.endswith('download'):
        text = _sc_str(_ext_input(inputs, fields, 'TEXT', 'text', default=''))
        name = _sc_str(
            _ext_input(inputs, fields, 'FILE', 'file', default='save.txt'))
        _files_save(text.encode('utf-8'), name,
                    getattr(runtime, '_files_download_dir', None))
        return 0
    return 0
