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
    return os.path.join(
        getattr(
            sys,
            "_MEIPASS",
            os.path.abspath(".")
        ),
        filename
    )
