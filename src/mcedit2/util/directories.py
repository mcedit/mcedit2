import os
import sys
import win32api


def getUserFilesDirectory():
    if sys.platform == "win32":
        # On Windows, sys.executable is codepage-encoded.
        # It cannot represent all possible filenames, so get the exe filename
        # using this wide-character API, which returns a `unicode`
        exe = win32api.GetModuleFileNameW(None)
    else:
        # On OS X, the FS encoding is always UTF-8
        # OS X filenames are defined to be UTF-8 encoded.
        # On Linux, the FS encoding is given by the current locale
        # Linux filenames are defined to be bytestrings.
        exe = sys.executable.decode(sys.getfilesystemencoding())

    assert os.path.exists(exe), "%r does not exist" % exe
    if hasattr(sys, 'frozen'):
        folder = os.path.dirname(exe)
    else:
        if exe.endswith("python") or exe.endswith("python.exe"):
            script = sys.argv[0]
            # assert the source checkout is not in a non-representable path...
            assert os.path.exists(script), "Source checkout path cannot be represented with 'mbcs' encoding. Put the source checkout somewhere else."
            folder = os.path.dirname(os.path.dirname(os.path.dirname(script)))  # from src/mcedit, ../../
        else:
            folder = os.path.dirname(exe)

    dataDir = os.path.join(folder, "MCEdit User Data")

    if not os.path.exists(dataDir):
        os.makedirs(dataDir)
    return dataDir

def getUserSchematicsDirectory():
    return os.path.join(getUserFilesDirectory(), "schematics")

def getUserPluginsDirectory():
    return os.path.join(getUserFilesDirectory(), "plugins")
