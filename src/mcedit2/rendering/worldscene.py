"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import sys
import collections
import itertools

import numpy

from mcedit2.rendering.layers import Layer
from mcedit2.rendering import chunkupdate
from mcedit2.rendering.players import PlayersNode
from mcedit2.rendering.scenegraph import scenenode
from mcedit2.rendering import renderstates
from mcedit2.rendering.chunknode import ChunkNode, ChunkGroupNode
from mcedit2.rendering.chunkupdate import ChunkRenderInfo
from mcedit2.rendering.depths import DepthOffsets
from mcedit2.rendering.geometrycache import GeometryCache
from mcedit2.rendering.scenegraph.depth_test import DepthOffset
from mcedit2.rendering.scenegraph.scenenode import Node
from mcedit2.rendering.scenegraph.texture_atlas import TextureAtlasState
from mcedit2.util.glutils import Texture
from mcedit2.util.load_png import loadPNGData
from mceditlib.anvil.biome_types import BiomeTypes

log = logging.getLogger(__name__)



def layerProperty(layer, default=True):
    attr = intern(str("_draw" + layer))

    def _get(self):
        return getattr(self, attr, default)

    def _set(self, val):
        if val != _get(self):
            setattr(self, attr, val)
            self.toggleLayer(val, layer)

    return property(_get, _set)


class SceneUpdateTask(object):
    showRedraw = True
    showHiddenOres = False
    showChunkRedraw = True

    spaceHeight = 64
    targetFPS = 30

    def __init__(self, worldScene, textureAtlas):
        """

        Parameters
        ----------

        worldScene : WorldScene
        textureAtlas : TextureAtlas
        """
        self.worldScene = worldScene

        self.render = True
        self.rotation = 0

        self.alpha = 255

        self.textureAtlas = textureAtlas

        self.mapTextures = {}
        self.modelTextures = {}

        self.renderType = numpy.zeros((256*256,), 'uint8')
        self.renderType[:] = 3
        for block in self.worldScene.dimension.blocktypes:
            self.renderType[block.ID] = block.renderType

        biomeTypes = BiomeTypes()
        self.biomeRain = numpy.zeros((256*256,), numpy.float32)
        self.biomeTemp = numpy.zeros((256*256,), numpy.float32)

        for biome in biomeTypes.types.itervalues():
            self.biomeRain[biome.ID] = biome.rainfall
            self.biomeTemp[biome.ID] = biome.temperature

    overheadMode = False

    maxWorkFactor = 64
    minWorkFactor = 1
    workFactor = 2

    def wantsChunk(self, cPos):
        if self.worldScene.bounds is not None:
            if not self.worldScene.bounds.containsChunk(*cPos):
                return False

        chunkInfo = self.worldScene.chunkRenderInfo.get(cPos)
        if chunkInfo is None:
            return True

        return bool(chunkInfo.layersToRender)

    def workOnChunk(self, chunk, visibleSections=None):
        work = 0
        cPos = chunk.chunkPosition

        log.debug("Working on chunk %s sections %s", cPos, visibleSections)
        chunkInfo = self.worldScene.getChunkRenderInfo(cPos)

        chunkInfo.visibleSections = visibleSections  # currently unused

        try:
            chunkUpdate = chunkupdate.ChunkUpdate(self, chunkInfo, chunk)
            for _ in chunkUpdate:
                work += 1
                if (work % SceneUpdateTask.workFactor) == 0:
                    yield

            meshesByRS = collections.defaultdict(list)
            for mesh in chunkUpdate.blockMeshes:
                meshesByRS[mesh.renderstate].append(mesh)

            # Create one ChunkNode for each renderstate group, if needed
            for renderstate in renderstates.allRenderstates:
                groupNode = self.worldScene.getRenderstateGroup(renderstate)
                if groupNode.containsChunkNode(cPos):
                    chunkNode = groupNode.getChunkNode(cPos)
                else:
                    chunkNode = ChunkNode(cPos)
                    groupNode.addChunkNode(chunkNode)

                meshes = meshesByRS[renderstate]
                if len(meshes):
                    meshes = sorted(meshes, key=lambda m: m.layer)
                    log.debug("Updating chunk node for renderstate %s, mesh count %d", renderstate, len(meshes))
                    for layer, layerMeshes in itertools.groupby(meshes, lambda m: m.layer):
                        if layer not in self.worldScene.visibleLayers:
                            continue
                        layerMeshes = list(layerMeshes)

                        # Check if the mesh was re-rendered and remove the old mesh
                        meshTypes = set(type(m) for m in layerMeshes)
                        for arrayNode in list(chunkNode.children):
                            if arrayNode.meshType in meshTypes:
                                chunkNode.removeChild(arrayNode)

                        # Add the scene nodes created by each mesh builder
                        for mesh in layerMeshes:
                            if mesh.sceneNode:
                                mesh.sceneNode.layerName = layer
                                mesh.sceneNode.meshType = type(mesh)
                                chunkNode.addChild(mesh.sceneNode)

                        chunkInfo.renderedLayers.add(layer)

                if chunkNode.childCount() == 0:
                    groupNode.discardChunkNode(*cPos)

        except Exception as e:
            log.exception(u"Rendering chunk %s failed: %r", cPos, e)

    def chunkNotPresent(self, (cx, cz)):
        # Assume chunk was deleted by the user
        for renderstate in renderstates.allRenderstates:
            groupNode = self.worldScene.getRenderstateGroup(renderstate)
            groupNode.discardChunkNode(cx, cz)

    def getMapTexture(self, mapID):

        if mapID in self.mapTextures:
            return self.mapTextures[mapID]
        try:
            mapData = self.worldScene.dimension.worldEditor.getMap(mapID)
        except Exception as e:
            log.exception("Map %s could not be loaded (while loading GL texture)", mapID)
        else:
            colors = mapData.getColorsAsRGBA()

            mapTex = Texture(image=colors.ravel(),
                             width=colors.shape[1],
                             height=colors.shape[0])
            self.mapTextures[mapID] = mapTex
            return mapTex

    def getModelTexture(self, texturePath):
        if texturePath in self.modelTextures:
            return self.modelTextures[texturePath]

        try:
            w, h, rgba = loadPNGData(self.textureAtlas.resourceLoader.openStream(texturePath).read())
        except Exception as e:
            log.exception("Model texture %s could not be loaded", texturePath)
        else:
            modelTex = Texture(image=rgba[::-1], width=w, height=h)
            self.modelTextures[texturePath] = modelTex
            return modelTex


class WorldScene(scenenode.Node):
    def __init__(self, dimension, textureAtlas=None, geometryCache=None, bounds=None):
        super(WorldScene, self).__init__()

        self.dimension = dimension
        self.textureAtlas = textureAtlas
        self.depthOffset = DepthOffset(DepthOffsets.Renderer)
        self.addState(self.depthOffset)

        self.textureAtlasState = TextureAtlasState(textureAtlas)
        self.addState(self.textureAtlasState)

        self.renderstateNodes = {}
        for rsClass in renderstates.allRenderstates:
            groupNode = ChunkGroupNode()
            groupNode.name = rsClass.__name__
            groupNode.addState(rsClass())
            self.addChild(groupNode)
            self.renderstateNodes[rsClass] = groupNode

        self.chunkRenderInfo = {}
        self.visibleLayers = set(Layer.DefaultVisibleLayers)

        self.updateTask = SceneUpdateTask(self, textureAtlas)

        if geometryCache is None:
            geometryCache = GeometryCache()
        self.geometryCache = geometryCache

        self.showRedraw = False

        self.minlod = 0
        self.bounds = bounds

        self.playersNode = PlayersNode(dimension)
        self.addChild(self.playersNode)

    def setTextureAtlas(self, textureAtlas):
        if textureAtlas is not self.textureAtlas:
            self.textureAtlas = textureAtlas
            self.textureAtlasState.textureAtlas = textureAtlas
            self.updateTask.textureAtlas = textureAtlas
            self.discardAllChunks()

    def chunkPositions(self):
        return self.chunkRenderInfo.iterkeys()

    def getRenderstateGroup(self, rsClass):
        groupNode = self.renderstateNodes.get(rsClass)

        return groupNode

    def discardChunk(self, cx, cz):
        """
        Discard the chunk at the given position from the scene
        """
        for groupNode in self.renderstateNodes.itervalues():
            groupNode.discardChunkNode(cx, cz)
        self.chunkRenderInfo.pop((cx, cz), None)

    def discardChunks(self, chunks):
        for cx, cz in chunks:
            self.discardChunk(cx, cz)

    def discardAllChunks(self):
        for groupNode in self.renderstateNodes.itervalues():
            groupNode.clear()
        self.chunkRenderInfo.clear()

    def invalidateChunk(self, cx, cz, invalidLayers=None):
        """
        Mark the chunk for regenerating vertex data
        """
        if invalidLayers is None:
            invalidLayers = Layer.AllLayers

        node = self.chunkRenderInfo.get((cx, cz))
        if node:
            node.invalidLayers.update(invalidLayers)

    _fastLeaves = False

    @property
    def fastLeaves(self):
        return self._fastLeaves

    @fastLeaves.setter
    def fastLeaves(self, val):
        if self._fastLeaves != bool(val):
            self.discardAllChunks()

        self._fastLeaves = bool(val)

    _roughGraphics = False

    @property
    def roughGraphics(self):
        return self._roughGraphics

    @roughGraphics.setter
    def roughGraphics(self, val):
        if self._roughGraphics != bool(val):
            self.discardAllChunks()

        self._roughGraphics = bool(val)

    _showHiddenOres = False

    @property
    def showHiddenOres(self):
        return self._showHiddenOres

    @showHiddenOres.setter
    def showHiddenOres(self, val):
        if self._showHiddenOres != bool(val):
            self.discardAllChunks()

        self._showHiddenOres = bool(val)

    def wantsChunk(self, cPos):
        return self.updateTask.wantsChunk(cPos)

    def workOnChunk(self, chunk, visibleSections=None):
        return self.updateTask.workOnChunk(chunk, visibleSections)

    def chunkNotPresent(self, cPos):
        self.updateTask.chunkNotPresent(cPos)

    def getChunkRenderInfo(self, cPos):
        chunkInfo = self.chunkRenderInfo.get(cPos)
        if chunkInfo is None:
            #log.info("Creating ChunkRenderInfo %s in %s", cPos, self.worldScene)
            chunkInfo = ChunkRenderInfo(self, cPos)
            self.chunkRenderInfo[cPos] = chunkInfo

        return chunkInfo

    def setLayerVisible(self, layerName, visible):
        if visible:
            self.visibleLayers.add(layerName)
        else:
            self.visibleLayers.discard(layerName)

        for groupNode in self.renderstateNodes.itervalues():
            groupNode.setLayerVisible(layerName, visible)

    def setVisibleLayers(self, layerNames):
        self.visibleLayers = set(layerNames)
