"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

import numpy

from mcedit2.rendering import layers
from mcedit2.rendering.chunkmeshes.entitymesh import TileEntityMesh, MonsterRenderer, ItemRenderer
from mcedit2.rendering.chunkmeshes.lowdetail import LowDetailBlockMesh, OverheadBlockMesh
from mcedit2.rendering.chunkmeshes.terrainpop import TerrainPopulatedRenderer
from mcedit2.rendering.chunkmeshes.tileticks import TileTicksRenderer
from mcedit2.rendering.modelmesh import BlockModelMesh
from mcedit2.util import profiler
from mcedit2.util.lazyprop import lazyprop
from mceditlib import faces
from mceditlib import exceptions
from mceditlib.selection import BoundingBox, SectionBox


log = logging.getLogger(__name__)


class ChunkUpdate(object):
    def __init__(self, updateTask, chunkInfo, chunk):
        """
        :type updateTask: mcedit2.rendering.worldscene.SceneUpdateTask
        :type chunkInfo: mcedit2.rendering.chunknode.ChunkRenderInfo
        :type chunk: AnvilChunk
        :rtype: ChunkUpdate
        """
        self.updateTask = updateTask
        self.chunkInfo = chunkInfo
        self.chunk = chunk
        self.blockMeshes = []  # return value

        #
        # minlod = chunkNode.worldScene.minlod
        # minlod = min(minlod, chunkNode.maxlod)
        #
        # if chunkInfo.detailLevel != minlod:
        #     chunkInfo.detailLevel = minlod
        #     chunkInfo.invalidLayers.add(layers.Layer.Blocks)
        #
        #     # discard too-detailed meshes
        #     if minlod > 0:
        #         lowDetailMeshes = [mesh for mesh in chunkNode.blockMeshes if mesh.detailLevels != (0,)]
        #
        #         chunkNode.blockMeshes = lowDetailMeshes

    @lazyprop
    @profiler.function
    def neighboringChunks(self):
        chunk = self.chunk
        cx = chunk.cx
        cz = chunk.cz
        dim = chunk.dimension

        neighboringChunks = {}
        for face, dx, dz in ((faces.FaceXDecreasing, -1, 0),
                             (faces.FaceXIncreasing, 1, 0),
                             (faces.FaceZDecreasing, 0, -1),
                             (faces.FaceZIncreasing, 0, 1)):
            if dim.containsChunk(cx + dx, cz + dz):
                try:
                    neighboringChunks[face] = dim.getChunk(cx + dx, cz + dz)
                except (EnvironmentError, exceptions.LevelFormatError):
                    pass
        return neighboringChunks

    @property
    def textureAtlas(self):
        return self.chunkInfo.worldScene.textureAtlas

    @property
    def fastLeaves(self):
        return self.chunkInfo.worldScene.fastLeaves

    @property
    def roughGraphics(self):
        return self.chunkInfo.worldScene.roughGraphics

    wholeChunkMeshClasses = [
        TileEntityMesh,
        MonsterRenderer,
        ItemRenderer,
        TileTicksRenderer,
        TerrainPopulatedRenderer,
        LowDetailBlockMesh,
        OverheadBlockMesh,
    ]

    def __iter__(self):

        chunkInfo = self.chunkInfo
        if 0 == len(chunkInfo.invalidLayers):
            yield
            return

        existingBlockVertexNodes = sum([list(node.children) for node in chunkInfo.getChunkVertexNodes()], [])
        blockMeshes = self.blockMeshes

        # Recalculate the classes which render the entire chunk from top to bottom
        for cls in self.wholeChunkMeshClasses:
            if chunkInfo.detailLevel not in cls.detailLevels:
                #log.info("%s (%s) not in detail levels (%s)", cls.__name__, self.chunkMeshGroup.detailLevel, cls.detailLevels)
                continue
            if cls.layer not in chunkInfo.visibleLayers:
                continue
            if cls.layer not in chunkInfo.invalidLayers:
                for vertexNode in existingBlockVertexNodes:
                    if vertexNode.meshClass is cls:  # xxxxx
                        blockMeshes.append(existingBlockVertexNodes[cls])

                continue

            chunkMesh = cls(self)
            chunkMesh.detailLevel = chunkMesh.detailLevel

            name = cls.__name__
            worker = chunkMesh.makeChunkVertices(self.chunk, chunkInfo.worldScene.bounds)
            for _ in profiler.iterate(worker, name):
                yield

            blockMeshes.append(chunkMesh)
            chunkMesh.chunkUpdate = None

        #log.info("Calculated %d full-chunk meshes for chunk %s", len(blockMeshes), chunkNode.chunkPosition)

        highDetailBlocks = []

        # Recalculate section block meshes if needed, otherwise retain them
        if chunkInfo.detailLevel == 0 and layers.Layer.Blocks in chunkInfo.invalidLayers:
            #log.info("Recalculating chunk %s (%s)", chunkNode.chunkPosition, chunkNode)
            for _ in self.calcSectionFaces(highDetailBlocks):
                yield

        blockMeshes.extend(highDetailBlocks)

        #log.info("Calculated %d meshes for chunk %s", len(highDetailBlocks), chunkNode.chunkPosition)
        # else:
        #     highDetailBlocks.extend(mesh
        #                             for mesh in chunkNode.blockMeshes
        #                             if type(mesh) not in self.chunkMeshClasses)

        # Add the layer renderers

        # time.sleep(0.5) #xxxxxxxxxxxxx
        raise StopIteration


    def calcSectionFaces(self, blockMeshes):  # ForChunk(self, chunkPosition = (0,0), level = None, alpha = 1.0):
        """
        Creates a SectionUpdate instance for each section found in this ChunkUpdate's chunk and iterates it.

        Returns an iterator.
        """
        chunk = self.chunk
        bounds = self.chunkInfo.worldScene.bounds
        if bounds:
            if chunk.bounds.intersect(bounds).volume == 0:
                yield
                return
            sections = bounds.sectionPositions(*chunk.chunkPosition)
        else:
            sections = chunk.sectionPositions()

        for cy in sections:
            chunkSection = chunk.getSection(cy, False)
            if chunkSection:
                sectionUpdate = SectionUpdate(self, chunkSection, blockMeshes)
                for _i in sectionUpdate:
                    yield


class SectionUpdate(object):
    def __init__(self, chunkUpdate, chunkSection, blockMeshes):
        """
        Create an iterable object. When iterated, scans the list of blockMeshes, creates any
        meshes that are not present and adds them to blockMeshes, and recreates any meshes that are dirty.


        :type chunkSection: AnvilSection
        :type chunkUpdate: ChunkUpdate
        :type blockMeshes: list
        :rtype: SectionUpdate
        """
        self.chunkUpdate = chunkUpdate
        self.chunkSection = chunkSection
        self.cy = chunkSection.Y
        self.y = chunkSection.Y << 4

        self.blockMeshes = blockMeshes
        # new rendertypes:
        # 0: ??
        # 1. lava/water
        # 2: item?
        # 3: block model

        self.renderType = numpy.zeros((256*256,), 'uint8')
        for block in self.blocktypes:
            self.renderType[block.ID] = block.renderType



    @property
    def fastLeaves(self):
        return self.chunkUpdate.fastLeaves

    @property
    def roughGraphics(self):
        return self.chunkUpdate.roughGraphics

    @lazyprop
    def areaBlocks(self):
        """
        Return the blocks in an 18-wide cube centered on this section. Only retrieves blocks from the
        6 sections neighboring this one along a major axis, so the corners are empty. That's fine since they
        aren't needed for any calculation we do.

        :return: Array of blocks in this chunk and six of its neighbors.
        :rtype: numpy.ndarray(shape=(18, 18, 18), dtype='uint16')
        """
        chunk = self.chunkUpdate.chunk

        chunkWidth, chunkLength, chunkHeight = self.chunkSection.Blocks.shape
        cy = self.chunkSection.Y

        areaBlocks = numpy.empty((chunkWidth + 2, chunkLength + 2, chunkHeight + 2), numpy.uint16)
        areaBlocks[(0, -1), :, :] = 0
        areaBlocks[:, (0, -1)] = 0
        areaBlocks[:, :, (0, -1)] = 0

        mask = None
        bounds = self.chunkUpdate.chunkInfo.worldScene.bounds
        if bounds:
            cx, cz = self.chunkUpdate.chunk.chunkPosition
            sectionBox = SectionBox(cx, cy, cz).expand(1)
            areaBox = BoundingBox(sectionBox.origin, (chunkWidth + 2, chunkHeight + 2, chunkLength + 2))

            mask = bounds.box_mask(areaBox)
            if mask is None:
                return areaBlocks

        areaBlocks[1:-1, 1:-1, 1:-1] = self.chunkSection.Blocks
        neighboringChunks = self.chunkUpdate.neighboringChunks

        if faces.FaceXDecreasing in neighboringChunks:
            ncs = neighboringChunks[faces.FaceXDecreasing].getSection(cy)
            if ncs:
                areaBlocks[1:-1, 1:-1, :1] = ncs.Blocks[:, :, -1:]

        if faces.FaceXIncreasing in neighboringChunks:
            ncs = neighboringChunks[faces.FaceXIncreasing].getSection(cy)
            if ncs:
                areaBlocks[1:-1, 1:-1, -1:] = ncs.Blocks[:, :, :1]

        if faces.FaceZDecreasing in neighboringChunks:
            ncs = neighboringChunks[faces.FaceZDecreasing].getSection(cy)
            if ncs:
                areaBlocks[1:-1, :1, 1:-1] = ncs.Blocks[:chunkWidth, -1:, :chunkHeight]

        if faces.FaceZIncreasing in neighboringChunks:
            ncs = neighboringChunks[faces.FaceZIncreasing].getSection(cy)
            if ncs:
                areaBlocks[1:-1, -1:, 1:-1] = ncs.Blocks[:chunkWidth, :1, :chunkHeight]

        aboveSection = chunk.getSection(self.chunkSection.Y + 1)
        if aboveSection:
            areaBlocks[-1:, 1:-1, 1:-1] = aboveSection.Blocks[:1, :, :]

        belowSection = chunk.getSection(self.chunkSection.Y - 1)
        if belowSection:
            areaBlocks[:1, 1:-1, 1:-1] = belowSection.Blocks[-1:, :, :]


        if mask is not None:
            areaBlocks[~mask] = 0

        return areaBlocks

    @property
    def blocktypes(self):
        return self.chunkUpdate.chunk.blocktypes

    @lazyprop
    def blockRenderTypes(self):
        blockRenderTypes = self.renderType[self.Blocks]
        return blockRenderTypes

    @lazyprop
    def exposedBlockMasks(self):
        """
        Return a list of six boolean arrays, one for each block face direction. Values in the array
          indicate whether the corresponding side of that block is exposed. Improved to do a single
          isOpaque lookup as is done in Minecraft.

        :return: [ndarray(shape=(16, 16, 16), dtype=bool)] * 6
        """
        areaIsExposed = ~self.chunkUpdate.chunk.blocktypes.opaqueCube[self.areaBlocks]
        exposedBlockMasks = [None] * 6

        exposedBlockMasks[faces.FaceXDecreasing] = areaIsExposed[1:-1, 1:-1, :-2]
        exposedBlockMasks[faces.FaceXIncreasing] = areaIsExposed[1:-1, 1:-1, 2:]

        exposedBlockMasks[faces.FaceZDecreasing] = areaIsExposed[1:-1, :-2, 1:-1]
        exposedBlockMasks[faces.FaceZIncreasing] = areaIsExposed[1:-1, 2:, 1:-1]

        exposedBlockMasks[faces.FaceYDecreasing] = areaIsExposed[:-2, 1:-1, 1:-1]
        exposedBlockMasks[faces.FaceYIncreasing] = areaIsExposed[2:, 1:-1, 1:-1]

        return exposedBlockMasks

    def areaLights(self, lightName):
        chunkSection = self.chunkSection
        if not hasattr(chunkSection, lightName):
            return numpy.array([[[15]]], numpy.uint8)

        def Light(cs):
            return getattr(cs, lightName)

        neighboringChunks = self.chunkUpdate.neighboringChunks

        chunkWidth, chunkLength, chunkHeight = self.Blocks.shape

        areaLights = numpy.empty((chunkWidth + 2, chunkLength + 2, chunkHeight + 2), numpy.uint8)
        if lightName == "SkyLight":
            default = 15
        else:
            default = 0

        areaLights[(0, -1), :, :] = default
        areaLights[:, (0, -1), :] = default
        areaLights[:, :, (0, -1)] = default

        areaLights[1:-1, 1:-1, 1:-1] = Light(chunkSection)

        y = chunkSection.Y

        if faces.FaceXDecreasing in neighboringChunks:
            ncs = neighboringChunks[faces.FaceXDecreasing].getSection(y)
            if ncs:
                areaLights[1:-1, 1:-1, :1] = Light(ncs)[:, :, -1:]

        if faces.FaceXIncreasing in neighboringChunks:
            ncs = neighboringChunks[faces.FaceXIncreasing].getSection(y)
            if ncs:
                areaLights[1:-1, 1:-1, -1:] = Light(ncs)[:, :, :1]

        if faces.FaceZDecreasing in neighboringChunks:
            ncs = neighboringChunks[faces.FaceZDecreasing].getSection(y)
            if ncs:
                areaLights[1:-1, :1, 1:-1] = Light(ncs)[:, -1:, :]

        if faces.FaceZIncreasing in neighboringChunks:
            ncs = neighboringChunks[faces.FaceZIncreasing].getSection(y)
            if ncs:
                areaLights[1:-1, -1:, 1:-1] = Light(ncs)[:, :1, :]

        above = self.chunkUpdate.chunk.getSection(y + 1)
        if above:
            areaLights[-1:, 1:-1, 1:-1] = Light(above)[:1, :, :]

        below = self.chunkUpdate.chunk.getSection(y + 1)
        if below:
            areaLights[:1, 1:-1, 1:-1, ] = Light(below)[-1:, :, :]

        return areaLights

    @lazyprop
    def areaBlockLights(self):
        return self.areaLights("BlockLight")

    @lazyprop
    def areaSkyLights(self):
        return self.areaLights("SkyLight")

    @property
    def Blocks(self):
        return self.areaBlocks[1:-1, 1:-1, 1:-1]

    @property
    def Data(self):
        return self.chunkSection.Data

    @profiler.iterator("SectionUpdate")
    def __iter__(self):
        renderTypeCounts = numpy.bincount(self.blockRenderTypes.ravel())

        cx, cz = self.chunkUpdate.chunk.chunkPosition
        cache = self.chunkUpdate.chunkInfo.worldScene.geometryCache

        sectionBounds = SectionBox(cx, self.y, cz)
        bounds = self.chunkUpdate.chunkInfo.worldScene.bounds
        if bounds:
            sectionBounds = sectionBounds.intersect(bounds)

        modelMesh = BlockModelMesh(self)
        worker = modelMesh.createVertexArrays()
        if worker:
            for _ in worker:
                yield
        self.blockMeshes.append(modelMesh)
        yield

