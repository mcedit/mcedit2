"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import os
import sys

log = logging.getLogger(__name__)


def resourcePath(filename):
    filename = filename.replace('/', os.path.sep)
    basedir = getattr(sys, "_MEIPASS", None)  # if pyinstaller'd
    if basedir is None:
        import mcedit2
        mod = mcedit2.__file__
        basedir = os.path.dirname(mod) + "/.."
        basedir = os.path.normpath(basedir)
    path = os.path.join(basedir, filename)
    if not os.path.exists(path):
        raise RuntimeError("Could not get resource path for %s\n(Tried %s which does not exist)" % (filename, path))

    return path
