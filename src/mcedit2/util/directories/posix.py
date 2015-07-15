"""
    posix
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import os
import sys

log = logging.getLogger(__name__)

# no build scripts for linux yet. no idea if frozen apps will be built for linux.
# assume always running from source checkout and put user files in source checkout.

# xxx for .whl or distro-specific distrib, put user files in ~/.mcedit2

def getUserFilesDirectory():
    # On Linux, the FS encoding is given by the current locale
    # Linux filenames are defined to be bytestrings.

    # TODO: if not os.path.exists(os.path.join(mumble_mumble, ".git")):

    # We handle filenames internally as 'unicode', so decode 'sys.argv[0]'
    # If a linux filename cannot be decoded with the current locale, ignore it.
    # If this filename is the script filename, you lose.
    try:
        # assert the source checkout is not in a non-representable path...
        script = sys.argv[0].decode(sys.getfilesystemencoding())
    except UnicodeDecodeError:
        print("Script filename %r cannot be decoded with the current locale %s! Please use sensible filenames." % (
            sys.argv[0], sys.getfilesystemencoding()))
        raise

    folder = os.path.dirname(os.path.dirname(os.path.dirname(script)))  # main script is src/mcedit/main.py, so, ../../
    dataDir = os.path.join(folder, "MCEdit User Data")

    if not os.path.exists(dataDir):
        os.makedirs(dataDir)

    return dataDir
