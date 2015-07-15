"""
    mac
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import os
import sys

log = logging.getLogger(__name__)

# no build scripts for OS X yet. assuming py2app or py2installer will be used.
#
# store user files in source checkout folder

def getUserFilesDirectory():

    # TODO if sys.getattr('frozen', False):
    # TODO os.getenv('RESOURCEPATH') or sys.getattr('_MEIPASS'), etc etc...

    # On OS X, the FS encoding is always UTF-8
    # OS X filenames are defined to be UTF-8 encoded.
    # We internally handle filenames as unicode.

    script = sys.argv[0].decode(sys.getfilesystemencoding())

    folder = os.path.dirname(os.path.dirname(os.path.dirname(script)))  # main script is src/mcedit/main.py, so, ../../
    dataDir = os.path.join(folder, "MCEdit User Data")

    if not os.path.exists(dataDir):
        os.makedirs(dataDir)

    return dataDir
