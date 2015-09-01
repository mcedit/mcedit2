"""
    util.py
"""
from __future__ import absolute_import
import collections
from contextlib import contextmanager
from math import floor
import os
import sys

WorldInfo = collections.namedtuple("WorldInfo", "displayName lastPlayedTime versionInfo")

@contextmanager
def notclosing(f):
    yield f

def chunk_pos(x, z):
    return int(floor(x)) >> 4, int(floor(z)) >> 4

def exhaust(_iter):
    """
    Functions named ending in "Iter" return an iterable object that does
    long-running work and yields progress information on each call. exhaust()
    is used to implement the non-Iter equivalents

    :type _iter: Iterable
    """
    i = None
    for i in _iter:
        pass
    return i

def displayName(filename):
    shortname = os.path.basename(filename)
    if shortname == "level.dat":
        shortname = os.path.basename(os.path.dirname(filename))

    return shortname

def win32_appdata():
    """
    Try to use win32 api to get the AppData folder since python doesn't populate os.environ with unicode strings.
    """
    try:
        import win32com.client
        objShell = win32com.client.Dispatch("WScript.Shell")
        return objShell.SpecialFolders("AppData")
    except Exception as e:
        print "Error while getting AppData folder using WScript.Shell.SpecialFolders: {0!r}".format(e)
        try:
            from win32com.shell import shell, shellcon
            return shell.SHGetPathFromIDListEx(
                shell.SHGetSpecialFolderLocation(0, shellcon.CSIDL_APPDATA)
            )
        except Exception as e:
            print "Error while getting AppData folder using SHGetSpecialFolderLocation: {0!r}".format(e)

            return os.environ['APPDATA'].decode(sys.getfilesystemencoding())


def matchEntityTags(ref, kw):
    tag = ref.rootTag  # xxx getattr ref?
    for k in kw:
        if k == 'UUID':
            value = ref.UUID
        else:
            value = tag[k].value
        if value != kw[k]:
            return False

    return True
