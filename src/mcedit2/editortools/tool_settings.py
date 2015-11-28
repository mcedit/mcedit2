"""
    settings
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from mcedit2.util.settings import Settings

log = logging.getLogger(__name__)

BrushModeSetting = Settings().getOption("editortools/brush/mode", default="fill")
BrushShapeSetting = Settings().getOption("editortools/brush/shape")
BrushSizeSetting = Settings().getOption("editortools/brush/size")
