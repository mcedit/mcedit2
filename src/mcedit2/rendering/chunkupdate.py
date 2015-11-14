"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

import numpy
from mcedit2.rendering.modelmesh import BlockModelMesh

from mcedit2.rendering import layers
from mcedit2.rendering.chunkmeshes.chunksections import ChunkSectionsRenderer
from mcedit2.rendering.chunkmeshes.entitymesh import TileEntityLocationMesh, MonsterLocationRenderer, ItemRenderer, \
    ItemFrameMesh, MonsterModelRenderer, CommandBlockColorsMesh, CommandBlockLocationMesh, \
    TileEntityModelRenderer
from mcedit2.rendering.chunkmeshes.heightlevel import HeightLevelBlockMesh
from mcedit2.rendering.chunkmeshes.lowdetail import LowDetailBlockMesh, OverheadBlockMesh
from mcedit2.rendering.chunkmeshes.mobspawns import MobSpawnsBlockMesh
from mcedit2.rendering.chunkmeshes.terrainpop import TerrainPopulatedRenderer
from mcedit2.rendering.chunkmeshes.tileticks import TileTicksRenderer
from mcedit2.util import profiler
from mceditlib.util.lazyprop import lazyprop
from mceditlib import faces
from mceditlib import exceptions
from mceditlib.selection import BoundingBox, SectionBox


log = logging.getLogger(__name__)


class ChunkRenderInfo(object):
    maxlod = 2
    minlod = 0

    def __init__(self, worldScene, chunkPosition):
        """

        :param worldScene:
        :type worldScene: mcedit2.rendering.worldscene.WorldScene
        :param chunkPosition:
        :type chunkPosition: (int, int)
        :return:
        :rtype:
        """
        super(ChunkRenderInfo, self).__init__()
        self.worldScene = worldScene
        self.detailLevel = worldScene.minlod
        self.invalidLayers = set(layers.Layer.AllLayers)
        self.renderedLayers = set()

        self.chunkPosition = chunkPosition
        self.bufferSize = 0
        self.vertexNodes = []
        cx, cz = chunkPosition
        self.translateOffset = (cx << 4, 0, cz << 4)

    def getChunkVertexNodes(self):
        return iter(self.vertexNodes)

    @property
    def visibleLayers(self):
        return self.worldScene.visibleLayers #xxxx

    @property
    def layersToRender(self):
        return len(self.invalidLayers) + len(self.visibleLayers - self.renderedLayers)


class ChunkUpdate(object):
    def __init__(self, updateTask, chunkInfo, chunk):
        """
        :type updateTask: mcedit2.rendering.worldscene.SceneUpdateTask
        :type chunkInfo: mcedit2.rendering.chunkupdate.ChunkRenderInfo
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
        CommandBlockLocationMesh,
        CommandBlockColorsMesh,
        TileEntityLocationMesh,
        TileEntityModelRenderer,
        ItemFrameMesh,
        MonsterLocationRenderer,
        MonsterModelRenderer,
        ItemRenderer,
        TileTicksRenderer,
        TerrainPopulatedRenderer,
        ChunkSectionsRenderer,
        LowDetailBlockMesh,
        OverheadBlockMesh,
        HeightLevelBlockMesh,
        MobSpawnsBlockMesh,
    ]

    @profiler.iterator("ChunkUpdate")
    def __iter__(self):

        chunkInfo = self.chunkInfo
        if 0 == chunkInfo.layersToRender:
            yield
            return

        for _ in self.buildChunkMeshes():
            yield _

        highDetailBlocks = []

        if chunkInfo.detailLevel == 0 and layers.Layer.Blocks in chunkInfo.invalidLayers:
            for _ in self.buildSectionMeshes(highDetailBlocks):
                yield

        self.blockMeshes.extend(highDetailBlocks)
        chunkInfo.invalidLayers.clear()

        raise StopIteration

    @profiler.iterator
    def buildChunkMeshes(self):
        """
        Rebuild the meshes which render the entire chunk from top to bottom

        :return:
        :rtype:
        """
        chunkInfo = self.chunkInfo
        blockMeshes = self.blockMeshes

        for cls in self.wholeChunkMeshClasses:
            if chunkInfo.detailLevel not in cls.detailLevels:
                #log.info("%s (%s) not in detail levels (%s)", cls.__name__, self.chunkMeshGroup.detailLevel, cls.detailLevels)
                continue
            if cls.layer not in chunkInfo.visibleLayers:
                continue
            if cls.layer not in chunkInfo.invalidLayers and cls.layer in chunkInfo.renderedLayers:
                continue

            chunkMesh = cls(self)
            chunkMesh.detailLevel = chunkMesh.detailLevel

            name = cls.__name__
            try:
                worker = chunkMesh.makeChunkVertices(self.chunk, chunkInfo.worldScene.bounds)
                for _ in profiler.iterate(worker, name):
                    yield
            except Exception as e:
                log.exception("Failed rendering for mesh class %s: %s", cls, e)
                continue

            blockMeshes.append(chunkMesh)
            chunkMesh.chunkUpdate = None

    @profiler.iterator
    def buildSectionMeshes(self, blockMeshes):
        """
        Rebuild the section meshes.

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
        # 2: entity/chest/banner/sign/etc
        # 3: block model

    @property
    def fastLeaves(self):
        return self.chunkUpdate.fastLeaves

    @property
    def roughGraphics(self):
        return self.chunkUpdate.roughGraphics

    @lazyprop
    def areaBlocks(self):
        return self.areaBlocksOrData("Blocks")

    @lazyprop
    def areaData(self):
        return self.areaBlocksOrData("Data")

    @lazyprop
    def areaBiomes(self):
        if self.chunkUpdate.chunk.Biomes is None:
            return None
        chunkWidth, chunkLength, chunkHeight = self.chunkSection.Blocks.shape
        areaBiomes = numpy.zeros((chunkWidth+2, chunkLength+2), numpy.uint8)
        # need neighbors later to blend biome colors
        areaBiomes[1:-1, 1:-1] = self.chunkUpdate.chunk.Biomes
        return areaBiomes

    def areaBlocksOrData(self, arrayName):
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

        areaBlocks = numpy.empty((chunkWidth + 2, chunkLength + 2, chunkHeight + 2), numpy.uint16 if arrayName == "Blocks" else numpy.uint8)
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

        areaBlocks[1:-1, 1:-1, 1:-1] = getattr(self.chunkSection, arrayName)
        neighboringChunks = self.chunkUpdate.neighboringChunks

        if faces.FaceXDecreasing in neighboringChunks:
            ncs = neighboringChunks[faces.FaceXDecreasing].getSection(cy)
            if ncs:
                areaBlocks[1:-1, 1:-1, :1] = getattr(ncs, arrayName)[:, :, -1:]

        if faces.FaceXIncreasing in neighboringChunks:
            ncs = neighboringChunks[faces.FaceXIncreasing].getSection(cy)
            if ncs:
                areaBlocks[1:-1, 1:-1, -1:] = getattr(ncs, arrayName)[:, :, :1]

        if faces.FaceZDecreasing in neighboringChunks:
            ncs = neighboringChunks[faces.FaceZDecreasing].getSection(cy)
            if ncs:
                areaBlocks[1:-1, :1, 1:-1] = getattr(ncs, arrayName)[:chunkWidth, -1:, :chunkHeight]

        if faces.FaceZIncreasing in neighboringChunks:
            ncs = neighboringChunks[faces.FaceZIncreasing].getSection(cy)
            if ncs:
                areaBlocks[1:-1, -1:, 1:-1] = getattr(ncs, arrayName)[:chunkWidth, :1, :chunkHeight]

        aboveSection = chunk.getSection(self.chunkSection.Y + 1)
        if aboveSection:
            areaBlocks[-1:, 1:-1, 1:-1] = getattr(aboveSection, arrayName)[:1, :, :]

        belowSection = chunk.getSection(self.chunkSection.Y - 1)
        if belowSection:
            areaBlocks[:1, 1:-1, 1:-1] = getattr(belowSection, arrayName)[-1:, :, :]


        if mask is not None:
            areaBlocks[~mask] = 0

        return areaBlocks

    @property
    def blocktypes(self):
        return self.chunkUpdate.chunk.blocktypes

    @property
    def renderType(self):
        return self.chunkUpdate.updateTask.renderType

    @property
    def biomeTemp(self):
        return self.chunkUpdate.updateTask.biomeTemp

    @property
    def biomeRain(self):
        return self.chunkUpdate.updateTask.biomeRain

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
        chunkWidth, chunkLength, chunkHeight = self.Blocks.shape
        shape = (chunkWidth + 4, chunkLength + 4, chunkHeight + 4)

        if not hasattr(chunkSection, lightName):
            ret = numpy.zeros(shape, numpy.uint8)
            ret[:] = 15
            return ret

        def Light(cs):
            return getattr(cs, lightName)

        neighboringChunks = self.chunkUpdate.neighboringChunks


        areaLights = numpy.empty(shape, numpy.uint8)
        if lightName == "SkyLight":
            default = 15
        else:
            default = 0

        areaLights[:, :, :] = default

        areaLights[2:-2, 2:-2, 2:-2] = Light(chunkSection)

        y = chunkSection.Y

        if faces.FaceXDecreasing in neighboringChunks:
            ncs = neighboringChunks[faces.FaceXDecreasing].getSection(y)
            if ncs:
                areaLights[2:-2, 2:-2, :2] = Light(ncs)[:, :, -2:]

        if faces.FaceXIncreasing in neighboringChunks:
            ncs = neighboringChunks[faces.FaceXIncreasing].getSection(y)
            if ncs:
                areaLights[2:-2, 2:-2, -2:] = Light(ncs)[:, :, :2]

        if faces.FaceZDecreasing in neighboringChunks:
            ncs = neighboringChunks[faces.FaceZDecreasing].getSection(y)
            if ncs:
                areaLights[2:-2, :2, 2:-2] = Light(ncs)[:, -2:, :]

        if faces.FaceZIncreasing in neighboringChunks:
            ncs = neighboringChunks[faces.FaceZIncreasing].getSection(y)
            if ncs:
                areaLights[2:-2, -2:, 2:-2] = Light(ncs)[:, :2, :]

        above = self.chunkUpdate.chunk.getSection(y + 1)
        if above:
            areaLights[-2:, 2:-2, 2:-2] = Light(above)[:2, :, :]

        below = self.chunkUpdate.chunk.getSection(y - 1)
        if below:
            areaLights[:2, 2:-2, 2:-2, ] = Light(below)[-2:, :, :]

        nx, ny, nz = self.blocktypes.useNeighborBrightness[self.areaBlocks].nonzero()
        nxd = nx
        nx = nx + 1
        nxi = nx + 1
        nyd = ny
        ny = ny + 1
        nyi = ny + 1
        nzd = nz
        nz = nz + 1
        nzi = nz + 1
        
        neighborBrightness = [
            areaLights[nxi, ny, nz],
            areaLights[nxd, ny, nz],
            areaLights[nx, nyi, nz],
            areaLights[nx, nyd, nz],
            areaLights[nx, ny, nzi],
            areaLights[nx, ny, nzd],
        ]
        neighborBrightness = numpy.amax(neighborBrightness, 0)

        areaLights[nx, ny, nz] = neighborBrightness

        return areaLights[1:-1, 1:-1, 1:-1]

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
        cx, cz = self.chunkUpdate.chunk.chunkPosition

        sectionBounds = SectionBox(cx, self.y, cz)
        bounds = self.chunkUpdate.chunkInfo.worldScene.bounds
        if bounds:
            sectionBounds = sectionBounds.intersect(bounds)

        modelMesh = BlockModelMesh(self)
        with profiler.context("BlockModelMesh"):
            modelMesh.createVertexArrays()
        self.blockMeshes.append(modelMesh)
        yield
