"""
    export.py

    Extracting schematic files of diffeerent formats
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import atexit
import logging
import shutil
import tempfile
from mceditlib.block_copy import copyBlocksIter
from mceditlib.schematic import createSchematic
from mceditlib.selection import BoundingBox
from mceditlib.util import exhaust
from mceditlib.worldeditor import WorldEditor

log = logging.getLogger(__name__)

def extractSchematicFrom(sourceDim, box, entities=True):
    return exhaust(extractSchematicFromIter(sourceDim, box, entities))


def extractSchematicFromIter(sourceDim, box, entities=True):
    p = adjustExtractionParameters(sourceDim, box)
    if p is None:
        yield None
        return
    newbox, destPoint = p

    editor = createSchematic(shape=box.size, blocktypes=sourceDim.blocktypes)
    dim = editor.getDimension()
    for i in copyBlocksIter(dim, sourceDim, newbox, destPoint, entities=entities, biomes=True):
        yield i

    yield editor


def extractZipSchematicFrom(sourceLevel, box, zipfilename=None, entities=True):
    return exhaust(extractZipSchematicFromIter(sourceLevel, box, zipfilename, entities))


def extractZipSchematicFromIter(sourceLevel, box, zipfilename=None, entities=True):
    # converts classic blocks to alpha
    # probably should only apply to alpha levels

    if zipfilename is None:
        zipfilename = tempfile.mktemp("zipschematic.zip")
    atexit.register(shutil.rmtree, zipfilename, True)

    p = adjustExtractionParameters(sourceLevel, box)
    if p is None:
        return
    sourceBox, destPoint = p

    destPoint = (0, 0, 0)

    tempSchematic = mceditlib.schematic.ZipSchematic(zipfilename, create=True)
    tempSchematic.blocktypes = sourceLevel.blocktypes

    for i in copyBlocksIter(tempSchematic, sourceLevel, sourceBox, destPoint, entities=entities, create=True, biomes=True):
        yield i

    tempSchematic.Width, tempSchematic.Height, tempSchematic.Length = sourceBox.size
    tempSchematic.saveChanges()  # lights not needed for this format - crashes minecraft though
    yield tempSchematic


def extractAnySchematic(level, box):
    return exhaust(level.extractAnySchematicIter(box))


def extractAnySchematicIter(level, box):
    if box.chunkCount < mceditlib.schematic.ZipSchematic.loadedChunkLimit:
        for i in level.extractSchematicIter(box):
            yield i
    else:
        for i in level.extractZipSchematicIter(box):
            yield i


def adjustExtractionParameters(dim, box):
    x, y, z = box.origin
    w, h, l = box.size
    destX = destY = destZ = 0
    bounds = dim.bounds

    if y < 0:
        destY -= y
        h += y
        y = 0

    if y >= bounds.maxy:
        return

    if y + h >= bounds.maxy:
        h -= y + h - bounds.maxy
        y = bounds.maxy - h

    if h <= 0:
        return

    #if dim.Width:
    if x < 0:
        w += x
        destX -= x
        x = 0
    if x >= bounds.maxx:
        return

    if x + w >= bounds.maxx:
        w = bounds.maxx - x

    if w <= 0:
        return

    if z < 0:
        l += z
        destZ -= z
        z = 0

    if z >= bounds.maxz:
        return

    if z + l >= bounds.maxz:
        l = bounds.maxz - z

    if l <= 0:
        return

    box = BoundingBox((x, y, z), (w, h, l))

    return box, (destX, destY, destZ)
