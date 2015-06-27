"""
    pure_python
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

log = logging.getLogger(__name__)

def updateLightsByCoord(dim, x, y, z):
    for i in range(len(x)):
        updateLights(dim, x[i], y[i], z[i])

def updateLightsInSelection(dim, selection):
    for x, y, z in selection.positions:
        updateLights(dim, x, y, z)

def neighbors(x, y, z):
    yield x-1, y, z
    yield x+1, y, z
    yield x, y-1, z
    yield x, y+1, z
    yield x, y, z-1
    yield x, y, z+1


def updateLights(dim, x, y, z):
    # import pdb; pdb.set_trace()
    previousLight = dim.getBlockLight(x, y, z)
    light = dim.getBlock(x, y, z).brightness
    dim.setBlockLight(x, y, z, light)

    drawLight(dim, x, y, z)

    if previousLight < light:
        spreadLight(dim, x, y, z)

    if previousLight > light:
        fadeLight(dim, x, y, z, previousLight)

def getOpacity(dim, x, y, z):
    return max(1, dim.getBlock(x, y, z).opacity)

def drawLight(dim, x, y, z):
    opacity = getOpacity(dim, x, y, z)

    for nx, ny, nz in neighbors(x, y, z):
        adjacentLight = dim.getBlockLight(nx, ny, nz)
        if adjacentLight - opacity > dim.getBlockLight(x, y, z):
            dim.setBlockLight(x, y, z, adjacentLight - opacity)

def spreadLight(dim, x, y, z):
    light = dim.getBlockLight(x, y, z)
    if light <= 0:
        return

    for nx, ny, nz in neighbors(x, y, z):

        # xxx cast to int because one of these is a numpy.uint8 and
        # light - opacity rolls over to a large number.
        adjacentLight = int(dim.getBlockLight(nx, ny, nz))
        adjacentOpacity = getOpacity(dim, nx, ny, nz)
        newLight = light - adjacentOpacity
        # If the adjacent cell already has the "correct" light value, stop.
        if newLight > adjacentLight:
            dim.setBlockLight(nx, ny, nz, newLight)
            spreadLight(dim, nx, ny, nz)


def fadeLight(dim, x, y, z, previousLight):
    fadedCells = findFadedCells(dim, x, y, z, previousLight)
    for x, y, z in fadedCells:
        dim.setBlockLight(x, y, z, dim.getBlock(x, y, z).brightness)
        # dim.setBlock(x, y, z, "glass")
    for x, y, z in fadedCells:
        drawLight(dim, x, y, z)
    for x, y, z in fadedCells:
        spreadLight(dim, x, y, z)


def relCoords(ox, oy, oz, coords):
    for x, y, z, l in coords:
        yield x - ox, y - oy, z - oz


def findFadedCells(dim, ox, oy, oz, oPreviousLight):
    foundCells = set()
    toScan = [(ox, oy, oz, oPreviousLight)]

    while len(toScan):
        x, y, z, previousLight = toScan.pop(0)
        for nx, ny, nz in neighbors(x, y, z):

            adjacentLight = int(dim.getBlockLight(nx, ny, nz))
            adjacentOpacity = getOpacity(dim, nx, ny, nz)
            if previousLight - adjacentOpacity <= 0:
                continue
            if previousLight - adjacentOpacity == adjacentLight:
                if (nx, ny, nz) not in foundCells:
                    toScan.append((nx, ny, nz, adjacentLight))
                    foundCells.add((nx, ny, nz))

    return foundCells
