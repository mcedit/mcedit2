# -*- mode: python -*-
# Build script for pyinstaller. Run using:
# $ pyinstaller mcedit2.spec

a = Analysis(['src/mcedit2/main.py'],
             hiddenimports=['PySide.QtXml', 'zmq'],
             hookspath=['.'],
             runtime_hooks=None,
             excludes=['tkinter', 'tcl', 'tk', 'wx']
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

if onefile:
    a.scripts += a.binaries + a.zipfiles + a.datas

exe = EXE(pyz,
          a.scripts + [('i', '', 'OPTION')],
          exclude_binaries=not onefile,
          name='mcedit2.exe',
          debug=False,
          strip=None,
          upx=True,
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
