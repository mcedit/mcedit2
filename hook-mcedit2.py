"""
    hook-mcedit2.py
    Hook for pyinstaller to collect MCEdit's data files
"""
from __future__ import absolute_import, division, print_function#, unicode_literals
import glob
import logging
import os
from PyInstaller.hooks.hookutils import collect_data_files

log = logging.getLogger(__name__)

datas = collect_data_files('mceditlib') + collect_data_files('mcedit2')

