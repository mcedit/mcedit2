"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from mcedit2.rendering import renderstates
from mcedit2.rendering.blockmeshes import registerBlockRenderer, standardCubeTemplates
from mcedit2.rendering.slices import _XYZST
from mcedit2.rendering.blockmeshes.blockmesh import BlockMeshBase
from mcedit2.rendering.vertexarraybuffer import VertexArrayBuffer
from mceditlib import faces

log = logging.getLogger(__name__)


@registerBlockRenderer("CrossedSquares")
class CrossedSquaresMesh(BlockMeshBase):
    renderstate = renderstates.RenderstateAlphaTestNode

    def makeCrossedSquaresVertices(self):
        arrays = []
        blockIndices = self.getRenderTypeMask()
        yield

        theseBlocks = self.sectionUpdate.Blocks[blockIndices]

        bdata = self.sectionUpdate.Data[blockIndices]
        bdata[theseBlocks == self.sectionUpdate.chunkUpdate.chunk.blocktypes.Sapling.ID] &= 0x3  # xxx saplings only
        texes = self.sectionUpdate.lookupTextures(self.sectionUpdate.Blocks[blockIndices], bdata, 0)

        blockLight = self.sectionUpdate.areaBlockLights[1:-1, 1:-1, 1:-1]
        skyLight = self.sectionUpdate.areaSkyLights[1:-1, 1:-1, 1:-1]

        #colorize = None
        #if self.blocktypes.name == "Alpha":
        #    colorize = (theseBlocks == mceditlib.blocktypes.pc_blocktypes.TallGrass.ID) & (bdata != 0)

        for direction in (faces.FaceXIncreasing,
                          faces.FaceXDecreasing,
                          faces.FaceZIncreasing,
                          faces.FaceZDecreasing):
            vertexBuffer = VertexArrayBuffer.fromIndices(direction, blockIndices)
            if not len(vertexBuffer):
                return
            vertexBuffer.buffer[_XYZST] += standardCubeTemplates[direction]

            if direction == faces.FaceXIncreasing:
                vertexBuffer.vertex[..., 1:3, 0] -= 1
            if direction == faces.FaceXDecreasing:
                vertexBuffer.vertex[..., 1:3, 0] += 1
            if direction == faces.FaceZIncreasing:
                vertexBuffer.vertex[..., 1:3, 2] -= 1
            if direction == faces.FaceZDecreasing:
                vertexBuffer.vertex[..., 1:3, 2] += 1

            vertexBuffer.applyTexMap(texes)

            vertexBuffer.rgba[:] = 0xff  # ignore precomputed directional light
            vertexBuffer.setLights(skyLight[blockIndices], blockLight[blockIndices])
            #
            #if colorize is not None:
            #    vertexBuffer.rgb[colorize] *= LeafBlockMesh.leafColor

            arrays.append(vertexBuffer)
            yield

        self.vertexArrays = arrays

    makeVertices = makeCrossedSquaresVertices
