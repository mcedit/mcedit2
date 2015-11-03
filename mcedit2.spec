# -*- mode: python -*-
# Build script for pyinstaller. Run using:
# $ pyinstaller mcedit2.spec

import fnmatch
import os
import itertools

try:
    from PyInstaller.utils.hooks import collect_data_files
except ImportError:
    from PyInstaller.hooks.hookutils import collect_data_files

# Files under mcedit2.synth are used only by plugins and not internally. (just import them?)
support_modules = []
for root, dirnames, filenames in itertools.chain(os.walk(os.path.join('src', 'mcedit2', 'synth'))):
    for filename in fnmatch.filter(filenames, '*.py'):
        if filename == "__init__.py":
            filepath = root
        else:
            filepath = os.path.join(root, filename)
            filepath = filepath[:-3]  # discard ".py"

        components = filepath.split(os.path.sep)
        components = components[1:]  # discard 'src/'

        if "test" in components or components == ["mcedit2", "main"]:
            continue

        modulename = ".".join(components)  # dotted modulename
        support_modules.append(modulename)

a = Analysis(['src/mcedit2/main.py'],
             hiddenimports=['PySide.QtXml'] + support_modules,
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

onefile = True

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
          [('i', '', 'OPTION')],
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
