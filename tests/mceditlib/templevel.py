import atexit
import os
from os.path import join, dirname
import shutil
import tempfile
from mceditlib.worldeditor import WorldEditor

__author__ = 'Rio'

_TEST_FILES_DIR = "test_files"

# from $PROJECT/src/mceditlib/test/templevel.py, get to $PROJECT/test_files

_PROJECT = dirname(dirname(dirname(dirname(__file__))))
TEST_FILES_DIR = join(_PROJECT, _TEST_FILES_DIR)

tempdir = os.path.join(tempfile.gettempdir(), "mceditlib_test")
def killtemp():
    shutil.rmtree(tempdir, ignore_errors=True)

atexit.register(killtemp)

if not os.path.exists(tempdir):
    os.mkdir(tempdir)

def mktemp(suffix):
    td = tempfile.mkdtemp(suffix, dir=tempdir)
    os.rmdir(td)
    return td

def TempFile(filename):
    """
    Create a temporary copy of 'filename'.

    'filename' must be a path relative to the 'test_files' folder
    """
    assert not os.path.isabs(filename), "TempFile filename must be a relative path."
    filename = join(TEST_FILES_DIR, filename)
    tmpname = mktemp(os.path.basename(filename))
    if not os.path.exists(filename):
        raise IOError("File not found")

    if os.path.isdir(filename):
        shutil.copytree(filename, tmpname)
    else:
        shutil.copy(filename, tmpname)

    def removeTemp():
        if tmpname:
            filename = tmpname

            if os.path.isdir(filename):
                shutil.rmtree(filename)
            else:
                os.unlink(filename)

    atexit.register(removeTemp)

    return tmpname

def TempLevel(filename, createFunc=None):
    if not os.path.exists(filename):
        filename = join(TEST_FILES_DIR, filename)

    result = None
    tmpname = mktemp(os.path.basename(filename))
    if os.path.exists(filename):
        if os.path.isdir(filename):
            shutil.copytree(filename, tmpname)
        else:
            shutil.copy(filename, tmpname)

    elif createFunc:
        result = createFunc(tmpname)

    else:
        raise IOError, "File %s not found." % filename

    def removeTemp():
        if tmpname:
            filename = tmpname

            if os.path.isdir(filename):
                shutil.rmtree(filename)
            else:
                os.unlink(filename)

    atexit.register(removeTemp)

    if result:
        return result
    else:
        return WorldEditor(tmpname)
