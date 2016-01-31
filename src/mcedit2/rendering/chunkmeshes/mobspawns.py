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
        blocktypes = chunk.blocktypes

        for cy in chunk.sectionPositions():
            section = chunk.getSection(cy)
            if section is None:
                continue

            blockLight = section.BlockLight
            skyLight = section.SkyLight
            blocks = section.Blocks

            # This `!= 0` is weird. blocktypes.normalCube has dtype 'uint8'; numpy 1.10
            # refuses to perform an `&` between a 'uint8' and a 'bool'; so we use `!= 0`
            # to coerce the 'uint8' to a 'bool'
            #
            # If blocktypes.normalCube and other arrays on blocktypes were changed to
            # 'bool', Cython will refuse to coerce the arrays to typed memoryviews,
            # claiming the array format string '?' is not understood.

            normalCube = blocktypes.normalCube[blocks] != 0
            materialLiquid = blocktypes.materialLiquid[blocks] != 0

            # A block can spawn monsters if:
            #   the block is not a normal cube
            #   the block is not a liquid
            #   the block above is not a normal cube
            #   the block below has a solid top surface
            #   the block below is not bedrock or barrier
            # And the block's light level:
            #   blockLight < 8 AND skyLight < 8 will always spawn monsters
            #   blockLight < 8 AND skyLight >= 8 will only spawn monsters at night

            # A block "has a solid top surface" if:
            #   it is opaque and is a full cube OR
            #   it is a stairs of type "half=top" OR
            #   it is a slab of type "half=top" OR
            #   it is a hopper OR
            #   it is a snow layer of type "level==7"

            # fuck it
            validBelowBlocks = normalCube & (blocks != blocktypes['minecraft:bedrock'].ID)
            if 'minecraft:barrier' in blocktypes:
                validBelowBlocks &= (blocks != blocktypes['minecraft:barrier'].ID)

            lowBlockLight = blockLight < 8
            lowNightLight = lowBlockLight & (skyLight < 8)
            lowDayLight = lowBlockLight & (skyLight >= 8)

            validBlocks = normalCube == 0                  # block is not normal
            validBlocks &= materialLiquid == 0             # block is not liquid
            validBlocks[:-1] &= normalCube[1:] == 0        # block above is not normal
            validBlocks[1:] &= validBelowBlocks[:-1]       # block below has solid top surface

            belowSection = chunk.getSection(cy-1)
            if belowSection:
                belowSectionBlocks = belowSection.Blocks[-1:]
                validBlocks[:1] &= blocktypes.normalCube[belowSectionBlocks] != 0
            else:
                validBlocks[:1] = 0

            aboveSection = chunk.getSection(cy+1)
            if aboveSection:
                validBlocks[-1:] &= blocktypes.normalCube[aboveSection.Blocks[:1]] == 0

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

            nightVertexes = getVertexes(lowNightLight & validBlocks, (0xff, 0x00, 0x00, 0x6f))
            dayVertexes = getVertexes(lowDayLight & validBlocks, (0xff, 0xFF, 0x00, 0x6f))

            vertexes.append(dayVertexes)
            vertexes.append(nightVertexes)

        self.sceneNode = VertexNode(vertexes)

        yield
