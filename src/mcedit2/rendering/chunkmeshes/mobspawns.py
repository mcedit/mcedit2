"""
    mobspawns
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from mcedit2.rendering import renderstates
from mcedit2.rendering.blockmeshes import ChunkMeshBase, standardCubeTemplates
from mcedit2.rendering.layers import Layer
from mcedit2.rendering.scenegraph.vertex_array import VertexNode
from mcedit2.rendering.vertexarraybuffer import QuadVertexArrayBuffer
from mceditlib import faces

log = logging.getLogger(__name__)


class MobSpawnsBlockMesh(ChunkMeshBase):
    renderstate = renderstates.RenderstateHeightLevel
    layer = Layer.MobSpawns

    def makeChunkVertices(self, chunk, limitBox):
        """

        :param chunk:
        :type chunk: WorldEditorChunk
        :param limitBox:
        :return: :raise:
        """

        vertexes = []

        for cy in chunk.sectionPositions():
            section = chunk.getSection(cy)
            if section is None:
                continue

            blockLight = section.BlockLight
            skyLight = section.SkyLight
            blocks = section.Blocks

            # A block can spawn monsters if it is air, and the block above it is air,
            # and the block below it is solid, and the light level is < 8.
            # blocks with blockLight < 8 AND skyLight < 8 will always spawn monsters
            # blocks with blockLight < 8 AND skyLight >= 8 will only spawn monsters at night

            lowBlockLight = blockLight < 8
            lowNightLight = lowBlockLight & (skyLight < 8)
            lowDayLight = lowBlockLight & (skyLight >= 8)

            validBlocks = blocks == 0                  # block is air
            validBlocks[:-1] &= blocks[1:] == 0   # block above is air
            validBlocks[1:] &= blocks[:-1] != 0   # block below is not air

            belowSection = chunk.getSection(cy-1)
            if belowSection:
                validBlocks[:1] &= belowSection.Blocks[-1:] != 0
            else:
                validBlocks[:1] = 0
            aboveSection = chunk.getSection(cy+1)

            if aboveSection:
                validBlocks[-1:] &= aboveSection.Blocks[:1] == 0

            def getVertexes(mask, color):
                y, z, x = mask.nonzero()
                vertexBuffer = QuadVertexArrayBuffer(len(x), textures=False, lights=False)
                vertexBuffer.vertex[..., 0] = x[:, None]
                vertexBuffer.vertex[..., 1] = y[:, None]
                vertexBuffer.vertex[..., 2] = z[:, None]

                vertexBuffer.vertex[:] += (0, (cy << 4), 0)

                vertexBuffer.vertex[:] += standardCubeTemplates[faces.FaceYDecreasing, ..., :3]

                vertexBuffer.rgba[:] = color
                return vertexBuffer

            nightVertexes = getVertexes(lowNightLight & validBlocks, (0xff, 0x00, 0x00, 0x3f))
            dayVertexes = getVertexes(lowDayLight & validBlocks, (0xff, 0xFF, 0x00, 0x3f))

            vertexes.append(dayVertexes)
            vertexes.append(nightVertexes)

        self.sceneNode = VertexNode(vertexes)

        yield
