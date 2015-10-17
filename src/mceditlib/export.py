"""
    export.py

    Extracting schematic files of different formats
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

log = logging.getLogger(__name__)


def extractSchematicFrom(sourceDim, box, *a, **kw):
    """
    Extract a schematic from the given dimension within the given selection box. The
    minimum corner of the given box becomes the schematic's (0,0,0) coordinate.

    Parameters
    ----------
    sourceDim : WorldEditorDimension
    box : SelectionBox
    a :
    kw :

    Returns
    -------
    WorldEditor

    """
    return exhaust(extractSchematicFromIter(sourceDim, box, *a, **kw))


def extractSchematicFromIter(sourceDim, box, *a, **kw):
    editor = createSchematic(shape=box.size, blocktypes=sourceDim.blocktypes)
    dim = editor.getDimension()
    for i in copyBlocksIter(dim, sourceDim, box, (0, 0, 0), *a, **kw):
        yield i

    yield editor

#
# def extractZipSchematicFrom(sourceLevel, box, zipfilename=None, entities=True):
#     return exhaust(extractZipSchematicFromIter(sourceLevel, box, zipfilename, entities))
#
#
# def extractZipSchematicFromIter(sourceLevel, box, zipfilename=None, entities=True):
#     # converts classic blocks to alpha
#     # probably should only apply to alpha levels
#
#     if zipfilename is None:
#         zipfilename = tempfile.mktemp("zipschematic.zip")
#     atexit.register(shutil.rmtree, zipfilename, True)
#
#     p = adjustExtractionParameters(sourceLevel, box)
#     if p is None:
#         return
#     sourceBox, destPoint = p
#
#     destPoint = (0, 0, 0)
#
#     tempSchematic = ZipSchematic(zipfilename, create=True)
#     tempSchematic.blocktypes = sourceLevel.blocktypes
#
#     for i in copyBlocksIter(tempSchematic, sourceLevel, sourceBox, destPoint, entities=entities, create=True, biomes=True):
#         yield i
#
#     tempSchematic.Width, tempSchematic.Height, tempSchematic.Length = sourceBox.size
#     tempSchematic.saveChanges()  # lights not needed for this format - crashes minecraft though
#     yield tempSchematic
#
#
# def extractAnySchematic(level, box):
#     return exhaust(level.extractAnySchematicIter(box))
#
#
# def extractAnySchematicIter(level, box):
#     if box.chunkCount < ZipSchematic.loadedChunkLimit:
#         for i in level.extractSchematicIter(box):
#             yield i
#     else:
#         for i in level.extractZipSchematicIter(box):
#             yield i

