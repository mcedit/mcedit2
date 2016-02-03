"""
   block_fill.py

   Optimized functions for mass-replacing blocks in a world.
"""
from __future__ import absolute_import

import logging

import numpy

import mceditlib
from mceditlib import blocktypes
from mceditlib.blocktypes import BlockType
from mceditlib.operations import Operation

log = logging.getLogger(__name__)


def blockReplaceTable(blockReplacements):
    blockTable = numpy.rollaxis(numpy.indices((blocktypes.id_limit, 16), dtype='u2'), 0, 3)

    for old, new in blockReplacements:
        blockTable[old.ID, old.meta] = [new.ID, new.meta]

    return blockTable


class FillBlocksOperation(Operation):
    def __init__(self, dimension, selection, blockType_or_list, blocksToReplace=(), updateLights=True):
        """
        Fill all blocks in the selected area with blockType.

        If blocksToReplace is given, it may be a list or tuple of blocktypes to replace with the given blocktype.

        Additionally, blockType may be given as a list of (oldBlockType, newBlockType) pairs
        to perform multiple replacements.

        If updateLights is True, also checks to see if block changes require lighting updates and performs them.

        :type dimension: WorldEditorDimension
        :type selection: `~.BoundingBox`
        """
        super(FillBlocksOperation, self).__init__(dimension, selection)

        blockReplacements = []
        if isinstance(blockType_or_list, list):
            for old, new in blockType_or_list:
                if isinstance(old, BlockType) or not isinstance(old, (list, tuple)):
                    old = [old]
                for oldBlock in old:
                    blockReplacements.append((oldBlock, new))

            self.blockType = "Multiple"
        elif isinstance(blockType_or_list, basestring):
            self.blockType = dimension.blocktypes[blockType_or_list]
        else:
            self.blockType = blockType_or_list

        self.changesLighting = True
        self.replaceTable = None
        if len(blocksToReplace):
            for old in blocksToReplace:
                blockReplacements.append((old, self.blockType))
        self.blockReplacements = blockReplacements

        if len(blockReplacements):
            self.replaceTable = blockReplaceTable(blockReplacements)
            if updateLights:
                self.changesLighting = False
                for old, new in blockReplacements:
                    newAbsorption = dimension.blocktypes.opacity[old.ID]
                    oldAbsorption = dimension.blocktypes.opacity[new.ID]
                    if oldAbsorption != newAbsorption:
                        self.changesLighting = True

                    newEmission = dimension.blocktypes.brightness[old.ID]
                    oldEmission = dimension.blocktypes.brightness[new.ID]
                    if oldEmission != newEmission:
                        self.changesLighting = True

        self.createSections = True
        if self.replaceTable is not None:
            if self.replaceTable[0, 0].any():  # xxx hardcoded air ID
                self.createSections = True  # Replacing air with something else
            else:
                self.createSections = False

        self.updateLights = updateLights and self.changesLighting
        self.chunkCount = 0
        self.skipped = 0
        self.sections = 0
        log.info("Replacing with selection:\n%s Mapping:\n %s\n "
                 "(creating chunks/sections? %s updating lights? %s)",
                 selection, self.blockReplacements,
                 self.createSections, self.updateLights)

    def done(self):
        log.info(u"Fill/Replace: Skipped {0}/{1} sections".format(self.skipped, self.sections))

    def operateOnChunk(self, chunk):

        self.chunkCount += 1

        cx, cz = chunk.cx, chunk.cz

        secPos = self.selection.sectionPositions(cx, cz)

        for cy in chunk.bounds.sectionPositions(cx, cz):
            if cy not in secPos:
                continue

            section = chunk.getSection(cy, create=self.createSections)
            if section is None:
                continue
            self.sections += 1

            mask = self.selection.section_mask(cx, cy, cz)
            if mask is None:
                self.skipped += 1
                continue

            # don't waste time relighting and copying if the mask is empty
            if not mask.any():
                self.skipped += 1
                continue

            Blocks = section.Blocks
            Data = section.Data

            if self.replaceTable is not None:
                newBlocks = self.replaceTable[Blocks[mask], Data[mask]]
                Blocks[mask] = newBlocks[..., 0]
                Data[mask] = newBlocks[..., 1]

            else:
                Blocks[mask] = self.blockType.ID
                Data[mask] = self.blockType.meta

            if self.changesLighting and self.updateLights:
                import mceditlib.relight

                coords = mask.nonzero()
                y = coords[0] + (cy << 4)
                z = coords[1] + (cz << 4)
                x = coords[2] + (cx << 4)

                mceditlib.relight.updateLightsByCoord(self.dimension, x, y, z)

        # xxx need finer control over removing tile entities - for replacing with
        # blocks with the same entity ID
        # def include(ref):
        #     return ref.Position not in self.selection
        #
        # chunk.TileEntities[:] = filter(include, chunk.TileEntities)
        chunk.dirty = True



