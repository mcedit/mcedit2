"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import numpy
from mcedit2.rendering.blockmeshes import registerBlockRenderer, BlockMeshBase
from mcedit2.rendering.vertexarraybuffer import VertexArrayBuffer
from mceditlib import faces

log = logging.getLogger(__name__)


@registerBlockRenderer("Ladder")
class LadderBlockMesh(BlockMeshBase):
    ladderOffsets = numpy.array([
                                    [(0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0)],
                                    [(0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0)],

                                    [(0, -1, 0.9), (0, 0, -0.1), (0, 0, -0.1), (0, -1, 0.9)], # facing east
                                    [(0, 0, 0.1), (0, -1, -.9), (0, -1, -.9), (0, 0, 0.1)], # facing west
                                    [(.9, -1, 0), (.9, -1, 0), (-.1, 0, 0), (-.1, 0, 0)], # north
                                    [(0.1, 0, 0), (0.1, 0, 0), (-.9, -1, 0), (-.9, -1, 0)], # south

                                ] + [[(0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0)]] * 10, dtype='float32')

    ladderTextures = numpy.array([
                                     [(0, 0), (0, 0), (0, 0), (0, 0)], # unknown
                                     [(0, 0), (0, 0), (0, 0), (0, 0)], # unknown

                                     [(16, 16), (16, 0), (0, 0), (0, 16), ], # e
                                     [(0, 0), (0, 16), (16, 16), (16, 0), ], # w
                                     [(0, 16), (16, 16), (16, 0), (0, 0), ], # n
                                     [(16, 0), (0, 0), (0, 16), (16, 16), ], # s

                                 ] + [[(0, 0), (0, 0), (0, 0), (0, 0)]] * 10, dtype='float32')

    def ladderVertices(self):
        blockIndices = self.getRenderTypeMask()
        yield
        bdata = self.sectionUpdate.Data[blockIndices]

        vertexBuffer = VertexArrayBuffer.fromIndices(faces.FaceYIncreasing, blockIndices)
        if not len(vertexBuffer):
            return

        ladderTex = self.sectionUpdate.lookupTextures(self.sectionUpdate.Blocks[blockIndices], 0, 0)
        vertexBuffer.applyTexMap(ladderTex)
        vertexBuffer.texcoord[:] += self.ladderTextures[bdata]
        vertexBuffer.vertex[:] += self.ladderOffsets[bdata]

        BlockLight = self.sectionUpdate.chunkSection.BlockLight
        SkyLight = self.sectionUpdate.chunkSection.SkyLight

        vertexBuffer.setLights(SkyLight[blockIndices], BlockLight[blockIndices])

        yield
        self.vertexArrays = [vertexBuffer]

    makeVertices = ladderVertices

