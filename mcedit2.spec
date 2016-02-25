# -*- mode: python -*-
# Build script for pyinstaller. Run using:
# $ pyinstaller mcedit2.spec


import os
import sys
import platform

import subprocess

import shutil
from os import path

try:
    from PyInstaller.utils.hooks import collect_data_files
except ImportError:
    from PyInstaller.hooks.hookutils import collect_data_files


# --- Configurations ---

onefile = True  # if False, also skips the distribution packaging

SEVENZIP = r"C:\Program Files\7-Zip\7z.exe"

if 'APPVEYOR_BUILD_FOLDER' in os.environ:
    SEVENZIP = '7z'

# --- Get build parameters and environment ---

arch_plat = os.environ.get('PYTHON_ARCH_PLAT')
if arch_plat is None:
    _arch = platform.architecture()[0][:2]
    _plat = "win" if os.name == 'nt' else os.name
    
    arch_plat = _plat + _arch


# --- Get version number and write to _version.py ---

def get_git_version():
    """
    Get the version from git.
    """

    return subprocess.check_output('git describe --tags'.split()).strip()

build_version = os.environ.get('MCEDIT_BUILD_VERSION')
if build_version is None:
    build_version = "HOMEBAKED-" + get_git_version()

version_src = """
__version__ = %r
""" % (build_version,)

with file("src/mcedit2/_version.py", "w") as f:
    f.write(version_src)

# --- Distribution settings ---

dist_folder_name = "mcedit2-%s-%s" % (arch_plat, build_version)
sfx_exe_name = dist_folder_name + ".exe"

# --- Install mcedit2 in develop-mode and rebuild extensions ---

subprocess.check_call([sys.executable, 'setup.py', 'develop'])

# --- Rebuild UI files

subprocess.check_call([sys.executable, '-m', 'mcedit2.util.gen_ui'])


# --- Call PyInstaller to perform build ---

a = Analysis(['src/mcedit2/main.py'],
             hiddenimports=['PySide.QtXml'],
             hookspath=['.'],
             runtime_hooks=None,
             excludes=['Tkinter', 'Tcl', 'Tk', 'wx',
                       'IPython.sphinxext', 'IPython.nbconvert',
                       'IPython.nbformat',
                       'IPython.lib.editorhooks', 'IPython.core.tests',
                       'IPython.extensions.cythonmagic',
                       'jinja2',
                       ]
             )

# Suppress pyconfig.h warning
for d in a.datas:
    if 'pyconfig' in d[0]:
        a.datas.remove(d)
        break

def ext_filter(source):
    base = os.path.basename(source)
    if base == '.coverage':
        return False
    name, ext = os.path.splitext(base)
    return ext not in ('.c', '.html')

mceditlib_datas = collect_data_files('mceditlib')
mceditlib_datas = [(os.path.join(dest, os.path.basename(source)), source, 'DATA')
                   for source, dest in mceditlib_datas
                   if ext_filter(source)]

mcedit2_datas = collect_data_files('mcedit2')
mcedit2_datas = [(os.path.join(dest, os.path.basename(source)), source, 'DATA')
                 for source, dest in mcedit2_datas
                 if ext_filter(source)]

a.datas.extend(mcedit2_datas)
a.datas.extend(mceditlib_datas)

a.binaries = a.binaries - TOC([
    ('sqlite3.dll', '', ''),
    ('_sqlite3', '', ''),
    ('tcl85.dll', '', ''),
    ('tk85.dll', '', ''),
    ('_tkinter', '', ''),
])

pyz = PYZ(a.pure)

def data_filter(filename):
    return not (
        # Remove IPython html assets, saving 1.5MB.
        # Disables using the embedded IPython for notebooks
        # Anyone who wants this can run from source!
        filename.startswith("IPython\\html") or
        filename.startswith("IPython\\nbconvert") or
        filename.startswith("IPython\\nbformat") or
        filename.startswith("IPython\\testing") or
        # pywin32 manual (?)
        "win32com\\html" in filename or
        "win32com\\demos" in filename or
        "win32comext\\axscript\\demos" in filename or
        "pywin32.chm" in filename or
        # qt3 support
        "qt3support4.dll" in filename or
        # mcedit egg-infos
        "mcedit2.egg-info" in filename or
        "mceditlib.egg-info" in filename
    )


def apply_filter(toc):
    return [(filename, path, filetype)
            for filename, path, filetype in toc
            if data_filter(filename)]

a.datas = apply_filter(a.datas)
a.binaries = apply_filter(a.binaries)

if onefile:
    a.scripts += a.binaries + a.zipfiles + a.datas + a.zipped_data

exe = EXE(pyz,
          a.scripts,
          exclude_binaries=not onefile,
          name='mcedit2.exe',
          debug=True,
          strip=None,
          upx=False,
          console=True,
          icon="mcediticon.ico")

if not onefile:
    coll = COLLECT(exe,
                   a.binaries,
                   a.zipfiles,
                   a.datas,
                   strip=None,
                   upx=True,
                   name='mcedit2')
    
# --- Distribution packaging ---

if onefile:
    dist_folder_path = path.join("dist", dist_folder_name)
    os.makedirs(dist_folder_path)
    shutil.copy(path.join("dist", "mcedit2.exe"), dist_folder_path)
    
    userdata_path = path.join(dist_folder_path, "MCEdit 2 Files")
    plugins_path = path.join(userdata_path, "plugins")
    
    os.makedirs(userdata_path)
    
    shutil.copytree(path.join('src', 'plugins'), plugins_path)
    
    sfx_exe_path = path.join("dist", sfx_exe_name)
    
    subprocess.check_call(
        [
            SEVENZIP, "a", "-sfx7z.sfx",
            sfx_exe_name,
            dist_folder_name,
            "-m0=Copy",  # STORE compression mode
        ],
        cwd="dist")

