"""
    __init__.py
"""
from __future__ import absolute_import, division, print_function, unicode_literals

import atexit
import logging

import shutil

import py

from mceditlib.worldeditor import WorldEditor
from tests.test_mceditlib.conftest import copy_temp_file

log = logging.getLogger(__name__)

tmpdir = None


def remove_temp():
    if tmpdir:
        tmpdir.remove(rec=1)

atexit.register(remove_temp)


def bench_temp_file(filename):
    global tmpdir
    if tmpdir is None:
        tmpdir = py.path.local.mkdtemp()

    return copy_temp_file(tmpdir, filename)


def bench_temp_level(filename):
    path = bench_temp_file(filename)
    return WorldEditor(path.strpath)
