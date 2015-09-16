"""
    __init__
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

log = logging.getLogger(__name__)

updateLightsByCoord = updateLightsInSelection = NotImplemented


def setMethod(name):
    if name == "pure":
        from mceditlib.relight import pure_python
        setModule(pure_python)
    if name == "cython":
        from mceditlib.relight import with_cython
        setModule(with_cython)
    if name == "setBlocks":
        from mceditlib.relight import with_setblocks
        setModule(with_setblocks)
    if name == "sections":
        from mceditlib.relight import with_sections
        setModule(with_sections)


def setModule(mod):
    global updateLightsByCoord, updateLightsInSelection
    updateLightsByCoord = mod.updateLightsByCoord
    updateLightsInSelection = mod.updateLightsInSelection

setMethod("cython")
