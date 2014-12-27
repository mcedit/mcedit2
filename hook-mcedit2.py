"""
    hook-mcedit2.py
    Hook for pyinstaller to collect MCEdit's data files
"""
from __future__ import absolute_import, division, print_function#, unicode_literals
import glob
import logging
import os
from PyInstaller.hooks.hookutils import collect_submodules, collect_data_files

log = logging.getLogger(__name__)

# Builtin plugin folders
modules = collect_submodules('mcedit2.rendering.blockmeshes')

# Stick them in hiddenimports so the analyzer finds their deps
hiddenimports = modules

# Then, mangle the names and shove them into datas so they wind up in the temporary unzipped data folder
# This will cause pkgutil.iter_modules to find them because the plugin folder modules have a synthesized
# __file__ attribute which points into the data folder

modules = (m.replace(".", os.path.sep) + ".py" for m in modules)
modules = [(os.path.abspath(os.path.join("src", m)), os.path.dirname(m)) for m in modules]
datas = modules + collect_data_files('mceditlib.blocktypes') + collect_data_files('mcedit2')

