"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from OpenGL import GL
import numpy

from mcedit2.rendering import renderstates
from mcedit2.rendering.scenegraph import scenenode
from mcedit2.rendering.blockmeshes import standardCubeTemplates
from mcedit2.rendering.blockmeshes import ChunkMeshBase
from mcedit2.rendering.chunkmeshes.entity import models
from mcedit2.rendering.layers import Layer
from mcedit2.rendering.scenegraph.scenenode import PolygonModeNode, DepthFuncNode
from mcedit2.rendering.slices import _XYZ
from mcedit2.rendering.vertexarraybuffer import QuadVertexArrayBuffer
from mceditlib.anvil.entities import PCPaintingEntityRefBase

log = logging.getLogger(__name__)


class EntityMeshBase(ChunkMeshBase):
    renderstate = renderstates.RenderstateEntityNode
    detailLevels = (0, 1, 2)

    def _computeVertices(self, positions, colors, offset=False, chunkPosition=(0, 0)):
        cx, cz = chunkPosition
        x = cx << 4
        z = cz << 4

        bounds = self.chunkUpdate.updateTask.worldScene.bounds
        if bounds:
            positions = [p for p in positions if p in bounds]

        vertexBuffer = QuadVertexArrayBuffer(len(positions) * 6, lights=False, textures=False)
        vertexBuffer.buffer.shape = (len(positions), 6) + vertexBuffer.buffer.shape[-2:]
        if len(positions):
            positions = numpy.array(positions, dtype=float)
            positions[:, (0, 2)] -= (x, z)
            if offset:
                positions -= (0.5, 0.0, 0.5)

            vertexBuffer.rgba[:] = colors
            vertexBuffer.vertex[:] = positions[:, numpy.newaxis, numpy.newaxis, :]
            vertexBuffer.vertex[:] += standardCubeTemplates[_XYZ]

        vertexBuffer.buffer.shape = (len(positions) * 6, ) + vertexBuffer.buffer.shape[-2:]
        return vertexBuffer


class TileEntityMesh(EntityMeshBase):
    layer = Layer.TileEntities

    def makeChunkVertices(self, chunk, limitBox):
        tilePositions = []
        for i, ref in enumerate(chunk.TileEntities):
            if i % 10 == 0:
                yield

            if limitBox and ref.Position not in limitBox:
                continue
            tilePositions.append(ref.Position)

        tiles = self._computeVertices(tilePositions, (0xff, 0xff, 0x33, 0x44), chunkPosition=chunk.chunkPosition)
        yield
        self.sceneNode = scenenode.VertexNode(tiles)



class ItemFrameMesh(EntityMeshBase):
    layer = Layer.ItemFrames

    def makeChunkVertices(self, chunk, limitBox):
        mapTiles = []
        for i, ref in enumerate(chunk.Entities):
            if ref.id != "ItemFrame":
                continue

            if i % 10 == 0:
                yield

            if limitBox and ref.Position not in limitBox:
                continue

            item = ref.Item
            if item.itemType.internalName != "minecraft:filled_map":
                continue

            mapID = item.Damage

            mapTex = self.chunkUpdate.updateTask.getMapTexture(mapID)
            # xxx if mapTex is None: mapTex = missingNoTex

            # xxxx assumes 1.8 TilePos - fix this in ref??
            mapTiles.append((mapTex, ref.TilePos, ref.Facing))

        nodes = []

        for mapTex, (x, y, z), facing in mapTiles:
            vertexBuffer = QuadVertexArrayBuffer(1, lights=False, textures=True)

            # chunk is already translated - why?
            x -= chunk.cx << 4
            z -= chunk.cz << 4

            vertexBuffer.vertex[:] = x, y, z
            corners = self.faceCorners[facing]
            vertexBuffer.vertex[:] += corners
            texCorners = [(1, 1), (1, 0), (0, 0), (0, 1)]
            vertexBuffer.texcoord[:] += texCorners

            vertexNode = scenenode.VertexNode([vertexBuffer])
            if mapTex is not None:
                bindTexNode = scenenode.BindTextureNode(mapTex)
                bindTexNode.addChild(vertexNode)
                nodes.append(bindTexNode)
            else:
                nodes.append(vertexNode)

        self.sceneNode = scenenode.Node()
        for node in nodes:
            self.sceneNode.addChild(node)

    faceCorners = {  # xxx polygon offset?
        PCPaintingEntityRefBase.SouthFacing: ((1, 0, 0.01), (1, 1, 0.01), (0, 1, 0.01), (0, 0, 0.01)),
        PCPaintingEntityRefBase.WestFacing: ((0.99, 0, 1), (0.99, 1, 1), (0.99, 1, 0), (0.99, 0, 0)),
        PCPaintingEntityRefBase.NorthFacing: ((0, 0, 0.99), (0, 1, 0.99), (1, 1, 0.99), (1, 0, 0.99)),
        PCPaintingEntityRefBase.EastFacing: ((0.01, 0, 0), (0.01, 1, 0), (0.01, 1, 1), (0.01, 0, 1)),
    }


class MonsterModelRenderer(ChunkMeshBase):
    def makeChunkVertices(self, chunk, limitBox):
        sceneNode = scenenode.Node()
        for i, ref in enumerate(chunk.Entities):
            ID = ref.id
            if ID not in models.cookedModels:
                assert ID != "Zombie"
                ID = "Creeper"

            model = models.cookedModels[ID]

            modelVerts = numpy.array(model)
            modelVerts.shape = modelVerts.shape[0]/4, 4, modelVerts.shape[1]
            # scale down
            modelVerts[..., :3] *= 1/16.
            modelVerts[..., 1] = -modelVerts[..., 1] + 1.5 + 1/64.
            modelVerts[..., 0] = -modelVerts[..., 0]

            vertexBuffer = QuadVertexArrayBuffer(len(modelVerts), lights=False, textures=True)
            vertexBuffer.vertex[:] = modelVerts[..., :3]
            vertexBuffer.texcoord[:] = modelVerts[..., 3:5]

            node = scenenode.VertexNode(vertexBuffer)
            rotateNode = scenenode.RotateNode(ref.Rotation[0], (0., 1., 0.))
            rotateNode.addChild(node)
            translateNode = scenenode.TranslateNode((ref.Position - (chunk.cx << 4, 0, chunk.cz << 4)))
            translateNode.addChild(rotateNode)

            modelTex = self.chunkUpdate.updateTask.getModelTexture(models.textures[ID])

            textureNode = scenenode.BindTextureNode(modelTex, (1./modelTex.w, 1./modelTex.h, 1))
            textureNode.addChild(translateNode)
            sceneNode.addChild(textureNode)

            yield

        self.sceneNode = sceneNode


class MonsterRenderer(EntityMeshBase):
    layer = Layer.Entities  # xxx Monsters
    notMonsters = {"Item", "XPOrb", "Painting", "ItemFrame"}

    def makeChunkVertices(self, chunk, limitBox):
        monsterPositions = []
        for i, entityRef in enumerate(chunk.Entities):
            if i % 10 == 0:
                yield
            ID = entityRef.id

            if ID in self.notMonsters:
                continue
            pos = entityRef.Position
            if limitBox and pos not in limitBox:
                continue
            monsterPositions.append(pos)

        monsters = self._computeVertices(monsterPositions,
                                         (0xff, 0x22, 0x22, 0x44),
                                         offset=True,
                                         chunkPosition=chunk.chunkPosition)
        yield

        vertexNode = scenenode.VertexNode(monsters)
        polyNode = PolygonModeNode(GL.GL_FRONT_AND_BACK, GL.GL_LINE)
        polyNode.addChild(vertexNode)
        depthNode = DepthFuncNode(GL.GL_ALWAYS)
        depthNode.addChild(polyNode)

        self.sceneNode = depthNode



class ItemRenderer(EntityMeshBase):
    layer = Layer.Items

    def makeChunkVertices(self, chunk, limitBox):
        entityPositions = []
        entityColors = []
        colorMap = {
            "Item": (0x22, 0xff, 0x22, 0x5f),
            "XPOrb": (0x88, 0xff, 0x88, 0x5f),
            "Painting": (134, 96, 67, 0x5f),
        }
        for i, entityRef in enumerate(chunk.Entities):
            if i % 10 == 0:
                yield
            color = colorMap.get(entityRef.id)
            if color is None:
                continue
            pos = entityRef.Position
            if limitBox and pos not in limitBox:
                continue

            entityPositions.append(pos)
            entityColors.append(color)

        items = self._computeVertices(entityPositions,
                                         numpy.array(entityColors, dtype='uint8')[:, numpy.newaxis, numpy.newaxis],
                                         offset=True, chunkPosition=chunk.chunkPosition)
        yield
        self.sceneNode = scenenode.VertexNode(items)

