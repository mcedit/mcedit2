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
    path = os.path.join(
        getattr(
            sys,
            "_MEIPASS",  # if pyinstaller'd
            os.path.abspath("src")  # if running from source
        ),
        filename
    )
    if not os.path.exists(path):
        raise RuntimeError("Could not get resource path for %s\n(Tried %s which does not exist)" % (filename, path))

    return path
