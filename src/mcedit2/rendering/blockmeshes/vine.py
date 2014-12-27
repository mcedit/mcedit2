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


@registerBlockRenderer("Vine")
class VineBlockMesh(BlockMeshBase):
    SouthBit = 1 #FaceZIncreasing
    WestBit = 2 #FaceXDecreasing
    NorthBit = 4 #FaceZDecreasing
    EastBit = 8 #FaceXIncreasing

    renderstate = renderstates.RenderstateVinesNode

    def vineFaceVertices(self, direction, blockIndices, exposedFaceMask):
        bdata = self.sectionUpdate.Data[blockIndices]
        blockIndices = numpy.array(blockIndices)
        if direction == faces.FaceZIncreasing:
            blockIndices[blockIndices] = (bdata & 1).astype(bool)
        elif direction == faces.FaceXDecreasing:
            blockIndices[blockIndices] = (bdata & 2).astype(bool)
        elif direction == faces.FaceZDecreasing:
            blockIndices[blockIndices] = (bdata & 4).astype(bool)
        elif direction == faces.FaceXIncreasing:
            blockIndices[blockIndices] = (bdata & 8).astype(bool)
        else:
            return []
        vertexBuffer = VertexArrayBuffer.fromIndices(direction, blockIndices)
        if not len(vertexBuffer):
            return vertexBuffer

        vertexBuffer.applyTexMap(self.sectionUpdate.lookupTextures(self.sectionUpdate.Blocks[blockIndices], [0], direction))

        vertexBuffer.setLights(self.sectionUpdate.chunkSection.SkyLight[blockIndices],
                               self.sectionUpdate.chunkSection.BlockLight[blockIndices])

        #vertexBuffer.rgb[:] *= LeafBlockMesh.leafColor

        if direction == faces.FaceZIncreasing:
            vertexBuffer.vertex[..., 2] -= 0.0625
        if direction == faces.FaceXDecreasing:
            vertexBuffer.vertex[..., 0] += 0.0625
        if direction == faces.FaceZDecreasing:
            vertexBuffer.vertex[..., 2] += 0.0625
        if direction == faces.FaceXIncreasing:
            vertexBuffer.vertex[..., 0] -= 0.0625

        return vertexBuffer

    makeFaceVertices = vineFaceVertices
