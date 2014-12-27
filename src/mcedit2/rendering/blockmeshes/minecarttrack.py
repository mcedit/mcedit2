"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import numpy
from mcedit2.rendering import renderstates
from mcedit2.rendering.blockmeshes import registerBlockRenderer, BlockMeshBase
from mcedit2.rendering.vertexarraybuffer import VertexArrayBuffer
from mceditlib import faces

log = logging.getLogger(__name__)


#@registerBlockRenderer("MinecartTrack")
class MinecartTrackBlockMesh(BlockMeshBase):
    renderstate = renderstates.RenderstateAlphaTestNode

    railTextures = numpy.array([
                                   [(0, 0), (0, 16), (16, 16), (16, 0)], # east-west
                                   [(0, 0), (16, 0), (16, 16), (0, 16)], # north-south
                                   [(0, 0), (16, 0), (16, 16), (0, 16)], # south-ascending
                                   [(0, 0), (16, 0), (16, 16), (0, 16)], # north-ascending
                                   [(0, 0), (0, 16), (16, 16), (16, 0)], # east-ascending
                                   [(0, 0), (0, 16), (16, 16), (16, 0)], # west-ascending

                                   [(0, 0), (0, 16), (16, 16), (16, 0)], # northeast corner
                                   [(0, 16), (16, 16), (16, 0), (0, 0)], # southeast corner
                                   [(16, 16), (16, 0), (0, 0), (0, 16)], # southwest corner
                                   [(16, 0), (0, 0), (0, 16), (16, 16)], # northwest corner

                                   [(0, 0), (0, 16), (16, 16), (16, 0)], # unknown
                                   [(0, 0), (0, 16), (16, 16), (16, 0)], # unknown
                                   [(0, 0), (0, 16), (16, 16), (16, 0)], # unknown
                                   [(0, 0), (0, 16), (16, 16), (16, 0)], # unknown
                                   [(0, 0), (0, 16), (16, 16), (16, 0)], # unknown
                                   [(0, 0), (0, 16), (16, 16), (16, 0)], # unknown

                               ], dtype='float32')
    #railTextures -= mceditlib.blocktypes.pc_blocktypes.blockTextures[mceditlib.blocktypes.pc_blocktypes.Rail.ID, 0, 0]

    railOffsets = numpy.array([
                                  [0, 0, 0, 0],
                                  [0, 0, 0, 0],

                                  [0, 0, 1, 1], # south-ascending
                                  [1, 1, 0, 0], # north-ascending
                                  [1, 0, 0, 1], # east-ascending
                                  [0, 1, 1, 0], # west-ascending

                                  [0, 0, 0, 0],
                                  [0, 0, 0, 0],
                                  [0, 0, 0, 0],
                                  [0, 0, 0, 0],

                                  [0, 0, 0, 0],
                                  [0, 0, 0, 0],
                                  [0, 0, 0, 0],
                                  [0, 0, 0, 0],
                                  [0, 0, 0, 0],
                                  [0, 0, 0, 0],

                              ], dtype='float32')

    def makeMinecartTrackVertices(self):
        direction = faces.FaceYIncreasing
        blockIndices = self.getRenderTypeMask()
        yield

        bdata = self.sectionUpdate.Data[blockIndices]
        railBlocks = self.sectionUpdate.Blocks[blockIndices]
        tex = self.sectionUpdate.lookupTextures(railBlocks, bdata, faces.FaceYIncreasing)[:, numpy.newaxis, :]

        # disable 'powered' or 'pressed' bit for powered and detector rails
        bdata[railBlocks != self.sectionUpdate.blocktypes.Rail.ID] &= ~0x8

        vertexBuffer = VertexArrayBuffer.fromIndices(direction, blockIndices)
        if not len(vertexBuffer):
            return

        vertexBuffer.applyTexMap(tex)
        vertexBuffer.texcoord[:] += self.railTextures[bdata]

        vertexBuffer.vertex[..., 1] -= 0.9
        vertexBuffer.vertex[..., 1] += self.railOffsets[bdata]

        BlockLight = self.sectionUpdate.chunkSection.BlockLight
        SkyLight = self.sectionUpdate.chunkSection.SkyLight

        vertexBuffer.setLights(SkyLight[blockIndices], BlockLight[blockIndices])

        yield
        self.vertexArrays = [vertexBuffer]

    makeVertices = makeMinecartTrackVertices
