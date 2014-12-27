"""
   block_copy.py

   Optimized functions for copying all world data (blocks, tile entities, entities, biomes) from
   one world or schematic file to another.
"""
from datetime import datetime
import logging
from mceditlib.geometry import SectionBox, BoundingBox

log = logging.getLogger(__name__)

import numpy
import mceditlib.blocktypes as blocktypes


def convertBlocks(destLevel, sourceLevel, blocks, blockData):
    return blocktypes.convertBlocks(destLevel.blocktypes, sourceLevel.blocktypes, blocks, blockData)

def sourceMaskFunc(blocksToCopy):
    if blocksToCopy is not None:
        typemask = numpy.zeros(blocktypes.id_limit, dtype='bool')
        typemask[blocksToCopy] = 1

        def maskedSourceMask(sourceBlocks):
            return typemask[sourceBlocks]

        return maskedSourceMask

    def unmaskedSourceMask(_sourceBlocks):
        return numpy.ones((1,), bool)

    return unmaskedSourceMask


def copyBlocksIter(destLevel, sourceLevel, sourceSelection, destinationPoint, blocksToCopy=None, entities=True, create=False, biomes=False):
    """
    Copy blocks and entities from the `sourceBox` area of `sourceLevel` to `destLevel` starting at `destinationPoint`.

    :param sourceLevel: ISectionWorld
    :param destLevel: ISectionWorld

    Optional parameters:
      - `blocksToCopy`: list of blockIDs to copy.
      - `entities`: True to copy Entities and TileEntities, False otherwise.
      - `create`: True to create new chunks in destLevel, False otherwise.
      - `biomes`: True to copy biome data, False otherwise.
    """

    (lx, ly, lz) = sourceSelection.size

    # needs work xxx
    log.info(u"Copying {0} blocks from {1} to {2}" .format(ly * lz * lx, sourceSelection, destinationPoint))
    startTime = datetime.now()

    destBox = BoundingBox(destinationPoint, sourceSelection.size)
    chunkCount = destBox.chunkCount
    i = 0
    e = 0
    t = 0

    makeSourceMask = sourceMaskFunc(blocksToCopy)

    copyOffset = destBox.origin - sourceSelection.origin

    # Visit each chunk in the source area
    #   Visit each section in this chunk
    #      Find the chunks and sections of the destination area corresponding to this section
    #          Compute slices for Blocks array and mask
    #          Use slices and mask to copy Blocks and Data
    #   Copy entities and tile entities from this chunk.
    sourceBiomeMask = None

    for sourceCpos in sourceSelection.chunkPositions():
        # Visit each chunk
        if not sourceLevel.containsChunk(*sourceCpos):
            continue

        sourceChunk = sourceLevel.getChunk(*sourceCpos)

        i += 1
        yield (i, chunkCount)
        if i % 100 == 0:
            log.info("Copying: Chunk {0}...".format(i))

        # Use sourceBiomeMask to accumulate a list of columns over all sections whose biomes should be copied.
        sourceBiomes = None
        if biomes and hasattr(sourceChunk, 'Biomes'):
            sourceBiomes = sourceChunk.Biomes
            sourceBiomeMask = numpy.zeros_like(sourceBiomes)

        for sourceCy in sourceChunk.sectionPositions():
            # Visit each section
            sourceSection = sourceChunk.getSection(sourceCy)
            if sourceSection is None:
                continue

            selectionMask = sourceSelection.section_mask(sourceCpos[0], sourceCy, sourceCpos[1])
            if selectionMask is None:
                continue

            typeMask = makeSourceMask(sourceSection.Blocks)
            sourceMask = selectionMask & typeMask

            # Update sourceBiomeMask
            if sourceBiomes is not None:
                sourceBiomeMask |= sourceMask.any(axis=0)

            # Find corresponding destination area(s)
            sectionBox = SectionBox(sourceCpos[0], sourceCy, sourceCpos[1], sourceSection)
            destBox = BoundingBox(sectionBox.origin + copyOffset, sectionBox.size)

            for destCpos in destBox.chunkPositions():
                if not create and not destLevel.containsChunk(*destCpos):
                    continue
                destChunk = destLevel.getChunk(*destCpos, create=True)

                for destCy in destBox.sectionPositions(*destCpos):
                    # Compute slices for source and dest arrays
                    destSectionBox = SectionBox(destCpos[0], destCy, destCpos[1])
                    intersect = destSectionBox.intersect(destBox)
                    if intersect.volume == 0:
                        continue

                    destSection = destChunk.getSection(destCy, create=True)
                    if destSection is None:
                        continue

                    # Recompute destSectionBox and intersect using the shape of destSection.Blocks
                    # after destChunk is loaded to work with odd shaped FakeChunks XXXXXXXXXXXX
                    destSectionBox = SectionBox(destCpos[0], destCy, destCpos[1], destSection)
                    intersect = destSectionBox.intersect(destBox)
                    if intersect.volume == 0:
                        continue

                    destSlices = (
                        slice(intersect.miny - (destCy << 4), intersect.maxy - (destCy << 4)),
                        slice(intersect.minz - (destCpos[1] << 4), intersect.maxz - (destCpos[1] << 4)),
                        slice(intersect.minx - (destCpos[0] << 4), intersect.maxx - (destCpos[0] << 4)),
                    )

                    sourceIntersect = BoundingBox(intersect.origin - copyOffset, intersect.size)
                    sourceSlices = (
                        slice(sourceIntersect.miny - (sourceCy << 4), sourceIntersect.maxy - (sourceCy << 4)),
                        slice(sourceIntersect.minz - (sourceCpos[1] << 4), sourceIntersect.maxz - (sourceCpos[1] << 4)),
                        slice(sourceIntersect.minx - (sourceCpos[0] << 4), sourceIntersect.maxx - (sourceCpos[0] << 4)),
                    )
                    # Read blocks
                    sourceBlocks = sourceSection.Blocks[sourceSlices]
                    sourceData = sourceSection.Data[sourceSlices]
                    sourceMaskPart = sourceMask[sourceSlices]

                    # Convert blocks
                    convertedSourceBlocks, convertedSourceData = convertBlocks(destLevel, sourceLevel, sourceBlocks, sourceData)

                    # Write blocks
                    destSection.Blocks[destSlices][sourceMaskPart] = convertedSourceBlocks[sourceMaskPart]
                    destSection.Data[destSlices][sourceMaskPart] = convertedSourceData[sourceMaskPart]

                destChunk.dirty = True

        # Copy biomes
        if sourceBiomes is not None:
            bx, bz = sourceBiomeMask.nonzero()
            wbx = bx + (sourceCpos[0] << 4)
            wbz = bz + (sourceCpos[1] << 4)
            destLevel.setBlocks(wbx, 1, wbz, Biomes=sourceBiomes[bx, bz])

        # Copy entities and tile entities
        if entities:
            for entity in sourceChunk.Entities:
                if entity.Position in sourceSelection:
                    newEntity = entity.copyWithOffset(copyOffset)
                    destLevel.addEntity(newEntity)

        for tileEntity in sourceChunk.TileEntities:
            if tileEntity.Position in sourceSelection:
                newEntity = tileEntity.copyWithOffset(copyOffset)
                destLevel.addTileEntity(newEntity)

    log.info("Duration: {0}".format(datetime.now() - startTime))
    log.info("Copied {0} entities and {1} tile entities".format(e, t))





