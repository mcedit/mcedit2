# -*- mode: python -*-
# Build script for pyinstaller. Run using:
# $ pyinstaller mcedit2.spec

a = Analysis(['src/mcedit2/main.py'],
             hiddenimports=['PySide.QtXml', 'zmq'],
             hookspath=['.'],
             runtime_hooks=None,
             excludes=['Tkinter', 'Tcl', 'Tk', 'wx',
                       'IPython.sphinxext', 'IPython.nbconvert',
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

a.binaries = a.binaries - TOC([
    ('sqlite3.dll', '', ''),
    ('_sqlite3', '', ''),
    ('tcl85.dll', '', ''),
    ('tk85.dll', '', ''),
    ('_tkinter', '', ''),
])

pyz = PYZ(a.pure)

onefile = True

# Remove IPython html assets, saving 1.5MB.
# Disables using the embedded IPython for notebooks
# Anyone who wants this can run from source!
def ipy_filter(filename):
    return not (
        filename.startswith("IPython\\html") or
        filename.startswith("IPython\\nbconvert") or
        filename.startswith("IPython\\nbformat") or
        filename.startswith("IPython\\testing")
    )

a.datas = [(filename, path, filetype)
           for filename, path, filetype in a.datas
           if ipy_filter(filename)]

if onefile:
    a.scripts += a.binaries + a.zipfiles + a.datas

exe = EXE(pyz,
          a.scripts + [('i', '', 'OPTION')],
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
