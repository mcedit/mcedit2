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

# Remove cython and coverage byproducts
def ext_filter(source):
    base = os.path.basename(source)
    if base == '.coverage':
        return False
    name, ext = os.path.splitext(base)
    return ext not in ('.c', '.html')

mceditlib_datas = collect_data_files('mceditlib')
mceditlib_datas = [(source, dest)
                   for source, dest in mceditlib_datas
                   if ext_filter(source)]

mcedit2_datas = collect_data_files('mcedit2')
mcedit2_datas = [(source, dest)
                 for source, dest in mcedit2_datas
                 if ext_filter(source)]

datas = mceditlib_datas + mcedit2_datas

