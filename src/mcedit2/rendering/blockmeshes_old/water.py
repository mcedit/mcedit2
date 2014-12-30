"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from mcedit2.rendering import renderstates
from mcedit2.rendering.blockmeshes import registerBlockRenderer, directionOffsets, standardCubeTemplates, makeVertexTemplates
from mcedit2.rendering.blockmeshes.blockmesh import BlockMeshBase
from mcedit2.rendering.vertexarraybuffer import VertexArrayBuffer
from mcedit2.rendering.slices import _XYZ
from mceditlib import faces

log = logging.getLogger(__name__)

waterCubeTemplates = makeVertexTemplates(ymax=0.875)

@registerBlockRenderer("Fluids")
class WaterBlockMesh(BlockMeshBase):
    renderstate = renderstates.RenderstateWaterNode

    def waterVertices(self):
        arrays = []
        renderTypeMask = self.getRenderTypeMask()
        belowDifferentBlock = self.sectionUpdate.areaBlocks[directionOffsets[faces.FaceYIncreasing]] != self.sectionUpdate.Blocks

        for direction, exposedFaceMask in enumerate(self.sectionUpdate.exposedBlockMasks):
            blockIndices = renderTypeMask & exposedFaceMask
            if direction == faces.FaceYIncreasing:
                facingDifferentBlock = belowDifferentBlock
            else:
                facingDifferentBlock = self.sectionUpdate.areaBlocks[directionOffsets[direction]] != self.sectionUpdate.Blocks
            blockIndices &= facingDifferentBlock

            vertexBuffer = VertexArrayBuffer.fromIndices(direction, blockIndices)
            if direction == faces.FaceYIncreasing:
                vertexBuffer.vertex[:] += waterCubeTemplates[direction][_XYZ]
            elif direction != faces.FaceYDecreasing:
                vertexMask = belowDifferentBlock[blockIndices]
                if len(vertexMask):
                    vertexBuffer.vertex[vertexMask] += waterCubeTemplates[direction][_XYZ]
                    vertexBuffer.vertex[~vertexMask] += standardCubeTemplates[direction][_XYZ]
                else:
                    vertexBuffer.vertex[:] += standardCubeTemplates[direction][_XYZ]
            else:
                vertexBuffer.vertex[:] += standardCubeTemplates[direction][_XYZ]

            vertexBuffer.applyTexMap(self.sectionUpdate.lookupTextures(self.sectionUpdate.Blocks[blockIndices], 0, 0))

            vertexBuffer.setLights(self.facingSkyLights(direction)[blockIndices],
                                   self.facingBlockLights(direction)[blockIndices])
            yield
            arrays.append(vertexBuffer)

        self.vertexArrays = arrays


    makeVertices = waterVertices
