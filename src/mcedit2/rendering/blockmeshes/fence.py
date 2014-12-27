"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import numpy
from mcedit2.rendering.blockmeshes import registerBlockRenderer, BlockMeshBase, makeVertexTemplates
from mcedit2.rendering.vertexarraybuffer import VertexArrayBuffer
import mceditlib

log = logging.getLogger(__name__)


@registerBlockRenderer("Fence")
class FenceBlockMesh(BlockMeshBase):

    fenceTemplates = makeVertexTemplates(3 / 8., 0, 3 / 8., 5 / 8., 1, 5 / 8.)

    def fenceVertices(self):
        fenceMask = self.getRenderTypeMask()
        fenceIndices = fenceMask.nonzero()
        yield
        vertexArrays = []
        blockLight = self.sectionUpdate.chunkSection.BlockLight[fenceIndices]
        skyLight = self.sectionUpdate.chunkSection.SkyLight[fenceIndices]

        y, z, x = fenceIndices
        #woodTex = self.sectionUpdate.chunkUpdate.updateTask.textureAtlas.texCoordsByName["planks_oak"]

        for face in range(6):
            vertexBuffer = VertexArrayBuffer(len(fenceIndices[0]))
            for i in range(3):
                vertexBuffer.buffer[..., i] = (x, y, z)[i][:, numpy.newaxis]

            vertexBuffer.buffer[..., 0:5] += self.fenceTemplates[face, ..., 0:5]
            vertexBuffer.applyTexMap(self.sectionUpdate.lookupTextures(self.sectionUpdate.Blocks[fenceIndices], 0, face))

            vertexBuffer.setLights(skyLight, blockLight)

            yield
            vertexArrays.append(vertexBuffer)

        self.vertexArrays = vertexArrays

    makeVertices = fenceVertices
