"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import numpy
from mcedit2.rendering.blockmeshes import registerBlockRenderer, BlockMeshBase, makeVertexTemplates
from mcedit2.rendering.blockmeshes.standard import directionalBrightness
from mcedit2.rendering.slices import _XYZST
from mcedit2.rendering.vertexarraybuffer import VertexArrayBuffer

log = logging.getLogger(__name__)


@registerBlockRenderer("Stairs")
class StairBlockMesh(BlockMeshBase):
    # South - FaceXIncreasing
    # North - FaceXDecreasing
    # West - FaceZIncreasing
    # East - FaceZDecreasing
    stairTemplates = numpy.array([makeVertexTemplates(**kw) for kw in [
        # South - FaceXIncreasing
        {"xmin": 0.5},
        # North - FaceXDecreasing
        {"xmax": 0.5},
        # West - FaceZIncreasing
        {"zmin": 0.5},
        # East - FaceZDecreasing
        {"zmax": 0.5},
        # Slabtype
        {"ymax": 0.5},
    ]
    ])

    def stairVertices(self):
        arrays = []
        renderTypeMask = self.getRenderTypeMask()
        yield
        stairBlocks = self.sectionUpdate.Blocks[renderTypeMask]
        stairData = self.sectionUpdate.Data[renderTypeMask]
        stairTop = (stairData >> 2).astype(bool)
        stairData &= 3

        blockLight = self.sectionUpdate.chunkSection.BlockLight
        skyLight = self.sectionUpdate.chunkSection.SkyLight

        y, z, x = renderTypeMask.nonzero()

        for _ in ("slab", "step"):
            for face in range(6):
                vertexBuffer = VertexArrayBuffer(len(x))
                for i in range(3):
                    vertexBuffer.vertex[..., i] = (x, y, z)[i][:, numpy.newaxis]

                if _ == "step":
                    vertexBuffer.buffer[_XYZST] += self.stairTemplates[4, face, ..., :5]
                    vertexBuffer.vertex[..., 1][stairTop] += 0.5
                else:
                    vertexBuffer.buffer[_XYZST] += self.stairTemplates[stairData, face, ..., :5]

                vertexBuffer.applyTexMap(self.sectionUpdate.lookupTextures(stairBlocks, 0, face))

                vertexBuffer.setLights(skyLight[renderTypeMask], blockLight[renderTypeMask])
                vertexBuffer.rgb[:] *= directionalBrightness[face]

                yield
                arrays.append(vertexBuffer)

        self.vertexArrays = arrays

    makeVertices = stairVertices
