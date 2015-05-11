"""
   block_fill.py

   Optimized functions for mass-replacing blocks in a world.
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
        Analyze all blocks in a selection.

        If blocksToReplace is given, it may be a list or tuple of blocktypes to replace with the given blocktype.

        Additionally, blockType may be given as a list of (oldBlockType, newBlockType) pairs
        to perform multiple replacements.

        If updateLights is True, also checks to see if block changes require lighting updates and performs them.

        :type dimension: WorldEditorDimension
        :type selection: `~.BoundingBox`
        """
        super(AnalyzeOperation, self).__init__(dimension, selection)

        self.createSections = False
        self.blocks = numpy.zeros(65536, dtype='uint32')
        self.selection = selection
        self.entityCounts = defaultdict(int)
        self.tileEntityCounts = defaultdict(int)
        
        self.chunkCount = 0
        self.skipped = 0
        self.sections = 0
        log.info("Analyzing %s blocks", selection.volume)

    def done(self):
        log.info(u"Analyze: Skipped {0}/{1} sections".format(self.skipped, self.sections))
        self.dimension.worldEditor.analyzeBlockOutput = self.blocks
        self.dimension.worldEditor.analyzeEntityOutput = self.entityCounts
        self.dimension.worldEditor.analyzeTileEntityOutput = self.tileEntityCounts

    def operateOnChunk(self, chunk):
        self.chunkCount += 1
        
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
            
            for ref in chunk.Entities:
                if ref.Position in self.selection:
                    self.entityCounts[ref.rootTag["id"].value] += 1
           
            for ref in chunk.TileEntities:
                if ref.Position in self.selection:
                    self.tileEntityCounts[ref.rootTag["id"].value] += 1

            
            blocks = numpy.array(section.Blocks[sectionMask], dtype='uint16')
            blocks |= (numpy.array(section.Data[sectionMask], dtype='uint16') << 12)
            b = numpy.bincount(blocks.ravel())
            self.blocks[:b.shape[0]] += b



