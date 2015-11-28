"""
    gen_ui
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import os

log = logging.getLogger(__name__)


def compile_ui():
    from mcedit2.util import resources
    if not resources.isSrcCheckout():
        return

    src = resources.getSrcFolder()
    uiDir = os.path.join(src, "mcedit2", "ui")

    from pysideuic import compileUiDir

    compileUiDir(uiDir, recurse=True)

if __name__ == '__main__':
    compile_ui()