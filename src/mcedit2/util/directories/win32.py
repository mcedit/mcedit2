import os
import sys

# when running from source, put the user files in the source checkout
# when running from a built app ("frozen"), decide from install mode

# TODO how to do install mode?
# 1. two different downloads
#    - .exe installer for system-wide/per-user install
#    - .zip for self-contained/portable install
# 2. one download. prompt on first app startup for install mode. create INSTALL_MODE file in
#    exe folder. check contents of file for install mode and prompt if file is missing.
# 3. like MCEdit1. option in app to change install mode and move user folder into app or docs folder
#    check for presence of user folder in app folder on startup to decide install mode.
# 4. ALWAYS self-contained/portable install. same as MultiMC.
#
# ... also, get auto updater working. manually updating a self-contained install may be weird.

# I think 4 is the best.
from mcedit2.util import resources

_userFilesDirectory = None
def getUserFilesDirectory():
    global _userFilesDirectory
    if _userFilesDirectory is not None:
        return _userFilesDirectory

    if hasattr(sys, 'frozen'):
        # On Windows, filenames are UTF-16 encoded.
        # Filenames are defined as UTF-16.
        #
        # However, sys.executable is codepage-encoded. Codepages cannot represent all possible
        # filenames, so we must get the exe filename using this wide-character API.
        # Wide-character APIs in pywin32 always return a `unicode`.
        #
        # Filenames must be passed to Python's filesystem functions as `unicode` to call the
        # wide-character forms of the underlying Win32 APIs.
        #
        # We take care not to store filenames as `bytes`, as this causes the filesystem functions
        # to use the legacy codepage APIs.

        import win32api
        exe = win32api.GetModuleFileNameW(None)
        assert os.path.exists(exe), "MCEdit executable %r does not exist! Something is very wrong." % exe
        folder = os.path.dirname(exe)
        dataDir = os.path.join(folder, "MCEdit 2 Files")

    else:
        folder = os.path.dirname(resources.getSrcFolder())
        dataDir = os.path.join(folder, "MCEdit 2 Files")

    if not os.path.exists(dataDir):
        os.makedirs(dataDir)

    _userFilesDirectory = dataDir
    return dataDir
