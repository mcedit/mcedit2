import os
import sys

def getUserFilesDirectory():
    exe = sys.executable
    if hasattr(sys, 'frozen'):
        folder = os.path.dirname(exe)
    else:
        script = sys.argv[0]
        if exe.endswith("python") or exe.endswith("python.exe"):
            folder = os.path.dirname(os.path.dirname(os.path.dirname(script)))  # from src/mcedit, ../../
        else:
            folder = os.path.dirname(exe)

    dataDir = os.path.join(folder, "MCEdit User Data")

    if not os.path.exists(dataDir):
        os.makedirs(dataDir)
    return dataDir


