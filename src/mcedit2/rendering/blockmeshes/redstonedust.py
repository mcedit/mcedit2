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


@registerBlockRenderer("RedstoneWire")
class RedstoneDustBlockMesh(BlockMeshBase):
    def redstoneVertices(self):
        blockIndices = self.getRenderTypeMask()
        yield
        vertexBuffer = VertexArrayBuffer.fromIndices(faces.FaceYIncreasing, blockIndices, lights=False)
        if not len(vertexBuffer):
            return

        vertexBuffer.applyTexMap(self.sectionUpdate.lookupTextures(self.sectionUpdate.Blocks[blockIndices], 0, 0))
        vertexBuffer.vertex[..., 1] -= 0.9

        bdata = self.sectionUpdate.Data[blockIndices]

        # bdata range is 0-15; shift it to 127-255 and put it in the red channel
        bdata <<= 3
        bdata[bdata > 0] |= 0x80

        vertexBuffer.rgba[..., 0] = bdata[..., numpy.newaxis]
        vertexBuffer.rgba[..., 1:3] = 0

        yield
        self.vertexArrays = [vertexBuffer]

    makeVertices = redstoneVertices

