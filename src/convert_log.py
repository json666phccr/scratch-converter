#!/usr/bin/env python3
"""转换日志

用于记录 Scratch <-> Python 转换的各个阶段、中间状态与异常位置。

用法：
    from convert_log import LOG
    LOG.configure(level='debug')          # 或环境变量 SCRATCH_LOG_LEVEL
    with LOG.stage('解析 IR'):
        ...
"""

import os
import sys
import time
import traceback
from contextlib import contextmanager

LEVELS = {
    'debug': 10,
    'info': 20,
    'warning': 30,
    'error': 40,
    'quiet': 100,
}


class ConversionLog:
    """带阶段上下文的转换日志"""

    def __init__(self):
        self.level = LEVELS.get(
            os.environ.get('SCRATCH_LOG_LEVEL', 'info').lower(), LEVELS['info'])
        self.stream = sys.stdout
        self.path = None
        self._file = None
        self.timestamps = False
        self.stage_name = None

    def configure(self, level=None, path=None, timestamps=None, stream=None):
        """调整日志输出级别/目标文件"""
        if level:
            key = str(level).lower()
            if key not in LEVELS:
                raise ValueError('未知日志级别: %s（可选 %s）'
                                 % (level, '/'.join(LEVELS)))
            self.level = LEVELS[key]
        if path is not None:
            self._close_file()
            self.path = path or None
            if self.path:
                directory = os.path.dirname(os.path.abspath(self.path))
                if directory:
                    os.makedirs(directory, exist_ok=True)
                self._file = open(self.path, 'w', encoding='utf-8')
        if timestamps is not None:
            self.timestamps = bool(timestamps)
        if stream is not None:
            self.stream = stream

    @property
    def debug_enabled(self):
        return self.level <= LEVELS['debug']

    def _write(self, text):
        if self._file is not None:
            self._file.write(text + '\n')
            self._file.flush()
        else:
            print(text, file=self.stream)
            self.stream.flush()

    def _emit(self, level, message):
        if LEVELS[level] < self.level:
            return
        parts = []
        if self.timestamps:
            parts.append(time.strftime('%H:%M:%S'))
        if self.stage_name:
            parts.append('[%s]' % self.stage_name)
        if level not in ('info',):
            parts.append(level.upper())
        parts.append(str(message))
        self._write(' '.join(parts))

    def debug(self, message):
        self._emit('debug', message)

    def info(self, message):
        self._emit('info', message)

    def warning(self, message):
        self._emit('warning', message)

    def error(self, message):
        self._emit('error', message)

    @contextmanager
    def stage(self, name, **details):
        """进入一个转换阶段；发生异常时记录阶段名和源码位置"""
        previous = self.stage_name
        self.stage_name = name
        started = time.time()
        if details:
            self.debug('开始: %s %s' % (name, _format_details(details)))
        else:
            self.debug('开始: %s' % name)
        try:
            yield
        except Exception as error:
            self.error('阶段失败: %s -> %s: %s'
                       % (name, type(error).__name__, error))
            self._log_location(error)
            raise
        else:
            self.debug('完成: %s（%.3fs）' % (name, time.time() - started))
        finally:
            self.stage_name = previous

    def exception(self, error, message=None):
        """记录异常，并输出转换器源码中的具体位置"""
        if message:
            self.error(message)
        self._log_location(error)

    def _log_location(self, error):
        """输出报错在转换器源码中的具体位置"""
        frames = traceback.extract_tb(error.__traceback__)
        project_frames = [frame for frame in frames
                          if _is_project_source(frame.filename)]
        targets = project_frames or frames
        for frame in targets[-3:]:
            self.error('  at %s:%s in %s'
                       % (_short_path(frame.filename), frame.lineno, frame.name))
            if frame.line:
                self.error('     %s' % frame.line.strip())
        if self.debug_enabled:
            traceback.print_exception(
                type(error), error, error.__traceback__, file=self.stream)

    def close(self):
        self._close_file()

    def _close_file(self):
        if self._file is not None:
            try:
                self._file.close()
            except OSError:
                pass
            self._file = None


def _format_details(details):
    return ', '.join('%s=%s' % (key, value) for key, value in details.items())


def _is_project_source(filename):
    if not filename:
        return False
    normalized = filename.replace('\\', '/')
    return '/src/' in normalized or normalized.endswith('/src')


def _short_path(filename):
    """尽量显示相对项目根目录的路径"""
    try:
        relative = os.path.relpath(filename, os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
    except (OSError, ValueError):
        return filename
    return relative.replace('\\', '/')


LOG = ConversionLog()
