import os
import sys

def getUserFilesDirectory():
    exe = sys.executable
    assert os.path.exists(exe), "%r does not exist" % exe
    if hasattr(sys, 'frozen'):
        folder = os.path.dirname(exe)
    else:
        if exe.endswith("python") or exe.endswith("python.exe"):
            script = sys.argv[0]
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
