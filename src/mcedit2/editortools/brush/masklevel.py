"""
    masklevel
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import numpy

from mceditlib.selection import BoundingBox

import logging
log = logging.getLogger(__name__)

NULL_ID = 255  # xxx WHAT IS THIS FOR?


class MaskLevel(object):
    def __init__(self, selection, fillBlock, blocktypes, biomeID=None):
        """
        Dimension emulator to be used for rendering brushes and selections.

        :type selection: mceditlib.selection.ShapeFuncSelection
        :param selection:
        :param fillBlock:
        :param blocktypes:
        """
        self.bounds = self.selection = selection

        self.blocktypes = blocktypes
        self.sectionCache = {}
        self.fillBlock = fillBlock
        self.biomeID = biomeID
        self.filename = "Temporary Level (%s %s %s)" % (selection, fillBlock, blocktypes)

    def chunkPositions(self):
        return self.bounds.chunkPositions()

    def getChunk(self, cx, cz, create=False):
        return FakeBrushChunk(self, cx, cz, self.biomeID)

    def containsChunk(self, cx, cz):
        return self.bounds.containsChunk(cx, cz)


class FakeBrushSection(object):
    BlockLight = numpy.empty((16, 16, 16), dtype=numpy.uint8)
    BlockLight[:] = 15
    SkyLight = numpy.empty((16, 16, 16), dtype=numpy.uint8)
    SkyLight[:] = 15
    pass


class FakeBrushChunk(object):
    Entities = ()
    TileEntities = ()

    def __init__(self, world, cx, cz, biomeID=None):
        """

        :type world: mcedit2.editortools.brush.masklevel.MaskLevel
        """
        self.dimension = world
        self.cx = cx
        self.cz = cz
        self.Biomes = numpy.zeros((16, 16), numpy.uint8)
        if biomeID:
            self.Biomes[:] = biomeID

    @property
    def blocktypes(self):
        return self.dimension.blocktypes

    @property
    def chunkPosition(self):
        return self.cx, self.cz

    def sectionPositions(self):
        return self.dimension.selection.sectionPositions(self.cx, self.cz)

    @property
    def bounds(self):
        return BoundingBox((self.cx << 4, self.dimension.bounds.miny, self.cz << 4),
                           (16, self.dimension.bounds.height, 16))

    _sentinel = object()

    def getSection(self, y, create=False):
        selection = self.dimension.selection
        sectionCache = self.dimension.sectionCache
        fillBlock = self.dimension.fillBlock
        cx, cz = self.chunkPosition

        section = sectionCache.get((cx, y, cz), self._sentinel)
        if section is self._sentinel:
            mask = selection.section_mask(cx, y, cz)
            if mask is None:
                sectionCache[cx, y, cz] = None
                return None

            section = FakeBrushSection()
            section.Y = y
            if fillBlock.ID:
                section.Blocks = numpy.array([0, fillBlock.ID], dtype=numpy.uint16)[mask.astype(numpy.uint8)]
                section.Data = numpy.array([0, fillBlock.meta], dtype=numpy.uint8)[mask.astype(numpy.uint8)]
            else:
                section.Blocks = numpy.array([0, NULL_ID])[mask.astype(numpy.uint8)]

            sectionCache[cx, y, cz] = section

        return section