"""
    with_sections
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import numpy
from mceditlib.exceptions import ChunkNotPresent

log = logging.getLogger(__name__)

def updateLightsInSelection(dim, selection):
    for cx, cz in selection.chunkPositions():
        for cy in selection.sectionPositions(cx, cz):
            updateLightsInSection(dim, cx, cy, cz)

def updateLightsByCoord(dim, x, y, z):
    """

    :param dim:
    :param x:
    :param y:
    :param z:
    :return:
    """

    # gross.
    cx = numpy.asanyarray(x) >> 4
    cy = numpy.asanyarray(y) >> 4
    cz = numpy.asanyarray(z) >> 4

    cx = numpy.unique(cx)
    cy = numpy.unique(cy)
    cz = numpy.unique(cz)

    for i in range(len(cx)):
        updateLightsInSection(dim, cx[i], cy[i], cz[i])


def updateLightsInSection(dim, cx, cy, cz):
    try:
        chunk = dim.getChunk(cx, cz)
    except ChunkNotPresent:
        return

    section = chunk.getSection(cy)
    if section is None:
        return

    light = section.BlockLight
    blocks = section.Blocks

    # Reset all lights to block brightness values
    # xxx if BlockLight
    light[:] = dim.blocktypes.brightness[blocks]

    # Get all block opacities only once
    opacity = dim.blocktypes.opacity[blocks]

    directions = ((0, -1),
                  (0, 1),
                  (1, -1),
                  (1, 1),
                  (2, -1),
                  (2, 1))

    for axis, direction in directions:
        leftSlices = [None, None, None]
        rightSlices = [None, None, None]
        if direction == 1:
            leftSlices[axis] = slice(None, -1)
            rightSlices[axis] = slice(1, None)
        else:
            leftSlices[axis] = slice(1, None)
            rightSlices[axis] = slice(None, -1)

        leftLight = light[leftSlices]
        rightOpacity = opacity[rightSlices]

        newRightLight = leftLight - rightOpacity
        # BlockLight is unsigned. Lights that were zero or less are now huge, so clip light values
        newRightLight.view('int8').clip(0, 15, newRightLight)

        changed = newRightLight != leftLight





