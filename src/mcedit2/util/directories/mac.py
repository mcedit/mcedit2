"""
    mac
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import os
import sys
from mcedit2.util import resources

log = logging.getLogger(__name__)

# no build scripts for OS X yet. assuming py2app or py2installer will be used.
#
# store user files in source checkout folder when checked out, otherwise in Documents folder

def getUserFilesDirectory():

    # TODO if sys.getattr('frozen', False):
    # TODO os.getenv('RESOURCEPATH') or sys.getattr('_MEIPASS'), etc etc...

    # On OS X, the FS encoding is always UTF-8
    # OS X filenames are defined to be UTF-8 encoded.
    # We internally handle filenames as unicode.

    if resources.isSrcCheckout():
        # Source checkouts don't use the same folder as regular installs.
        dataDir = os.path.join(os.path.dirname(resources.getSrcFolder()), "MCEdit 2 Files")
    else:
        dataDir = os.path.expanduser(u"~/Documents/MCEdit 2 Files")

    if not os.path.exists(dataDir):
        os.makedirs(dataDir)

    return dataDir
