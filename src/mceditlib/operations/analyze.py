"""
   analyze.py

   Get counts of blocks, entities, and tile entities in a selection.
"""
from __future__ import absolute_import
import logging

import numpy
from collections import defaultdict
from mceditlib.operations import Operation

log = logging.getLogger(__name__)


class AnalyzeOperation(Operation):
    def __init__(self, dimension, selection):
        """
        Analyze all blocks in a selection and return counts of block types, entity IDs and tile entity IDs.

        Counts are returned in `self.blocks`, `self.entityCounts` and `self.tileEntityCounts`

        :type dimension: WorldEditorDimension
        :type selection: `~.BoundingBox`
        """
        super(AnalyzeOperation, self).__init__(dimension, selection)

        self.createSections = False
        self.blocks = numpy.zeros(65536, dtype='intp')
        self.selection = selection
        self.entityCounts = defaultdict(int)
        self.tileEntityCounts = defaultdict(int)

        self.skipped = 0
        self.sections = 0
        log.info("Analyzing %s blocks", selection.volume)

    def done(self):
        log.info(u"Analyze: Skipped {0}/{1} sections".format(self.skipped, self.sections))

    def operateOnChunk(self, chunk):
        cx, cz = chunk.cx, chunk.cz
        
        for cy in chunk.bounds.sectionPositions(cx, cz):
            section = chunk.getSection(cy, create=False)

            if section is None:
                continue
            self.sections += 1

            sectionMask = self.selection.section_mask(cx, cy, cz)
            if sectionMask is None:
                self.skipped += 1
                continue

            maskSize = sectionMask.sum()
            if maskSize == 0:
                self.skipped += 1
                continue

            blocks = numpy.array(section.Blocks[sectionMask], dtype='uint16')
            blocks |= (numpy.array(section.Data[sectionMask], dtype='uint16') << 12)
            b = numpy.bincount(blocks.ravel())

            self.blocks[:b.shape[0]] += b

        for ref in chunk.Entities:
            if ref.Position in self.selection:
                self.entityCounts[ref.id] += 1

        for ref in chunk.TileEntities:
            if ref.Position in self.selection:
                self.tileEntityCounts[ref.id] += 1




