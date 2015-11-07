"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

import numpy

from mcedit2.rendering import renderstates
from mcedit2.rendering.scenegraph import scenenode
from mcedit2.rendering.blockmeshes import standardCubeTemplates
from mcedit2.rendering.blockmeshes import ChunkMeshBase
from mcedit2.rendering.scenegraph.vertex_array import VertexNode
from mcedit2.rendering.vertexarraybuffer import QuadVertexArrayBuffer
from mceditlib import faces

log = logging.getLogger(__name__)


class LowDetailBlockMesh(ChunkMeshBase):
    renderstate = renderstates.RenderstateLowDetail
    detailLevels = (1,)
    #
    #    def drawFaceVertices(self, buf):
    #        if not len(buf):
    #            return
    #        stride = 16
    #
    #        GL.glVertexPointer(3, GL.GL_FLOAT, stride, numpy.ravel(buf.ravel()))
    #        GL.glColorPointer(4, GL.GL_UNSIGNED_BYTE, stride, (buf.view(dtype='uint8').ravel()[12:]))
    #
    #        GL.glDisableClientState(GL.GL_TEXTURE_COORD_ARRAY)
    #        GL.glDrawArrays(GL.GL_QUADS, 0, len(buf) * 4)
    #        GL.glEnableClientState(GL.GL_TEXTURE_COORD_ARRAY)

    def makeChunkVertices(self, chunk, limitBox):
        """

        :param chunk:
        :type chunk: WorldEditorChunk
        :param limitBox:
        :return: :raise:
        """
        dim = chunk.dimension
        cx, cz = chunk.chunkPosition

        if not hasattr(chunk, 'HeightMap') or chunk.HeightMap is None:
            return

        heightMap = chunk.HeightMap
        chunkWidth = chunkLength = 16
        chunkHeight = chunk.dimension.bounds.height

        z, x = list(numpy.indices((chunkLength, chunkWidth)))
        y = (heightMap - 1)[:chunkLength, :chunkWidth]
        numpy.clip(y, 0, chunkHeight - 1, y)

        nonZeroHeights = y > 0
        heights = y.reshape((16, 16))

        x = x[nonZeroHeights]
        if not len(x):
            return

        z = z[nonZeroHeights]
        y = y[nonZeroHeights]

        # Get the top block in each column
        blockResult = dim.getBlocks(x + (cx * 16), y, z + (cz * 16), return_Data=True)
        topBlocks = blockResult.Blocks
        topBlockData = blockResult.Data

        # Get the block above each column top. We'll recolor the top face of the column if a flower or another
        # transparent block is on top.

        aboveY = y + 1
        numpy.clip(aboveY, 0, chunkHeight - 1, aboveY)
        blocksAbove = dim.getBlocks(x + (cx * 16), aboveY, z + (cz * 16)).Blocks

        flatcolors = dim.blocktypes.mapColor[topBlocks, topBlockData][:, numpy.newaxis, :]

        yield
        vertexBuffer = QuadVertexArrayBuffer(len(x), textures=False, lights=False)

        vertexBuffer.vertex[..., 0] = x[:, numpy.newaxis]
        vertexBuffer.vertex[..., 1] = y[:, numpy.newaxis]
        vertexBuffer.vertex[..., 2] = z[:, numpy.newaxis]

        va0 = vertexBuffer.copy()

        va0.vertex[:] += standardCubeTemplates[faces.FaceYIncreasing, ..., :3]

        overmask = blocksAbove > 0
        colors = dim.blocktypes.mapColor[:, 0][blocksAbove[overmask]][:, numpy.newaxis]
        flatcolors[overmask] = colors

        if self.detailLevel == 2:
            heightfactor = (y / float(chunk.dimension.bounds.height)) * 0.33 + 0.66
            flatcolors[..., :3] *= heightfactor[:, numpy.newaxis, numpy.newaxis]  # xxx implicit cast from byte to float and back

        va0.rgb[:] = flatcolors

        yield
        if self.detailLevel == 2:
            self.sceneNode = VertexNode(va0)
            return

        # Calculate how deep each column needs to go to be flush with the adjacent column;
        # If columns extend all the way down, performance suffers due to fill rate.

        depths = numpy.zeros((chunkWidth, chunkLength), dtype='uint16')
        depths[1:-1, 1:-1] = reduce(numpy.minimum,
                                    (heights[1:-1, :-2],
                                     heights[1:-1, 2:],
                                     heights[:-2, 1:-1],
                                     heights[2:, 1:-1]))
        depths = depths[nonZeroHeights]
        yield

        va1 = vertexBuffer.copy()
        va1.vertex[..., :3] += standardCubeTemplates[faces.FaceXIncreasing, ..., :3]

        va1.vertex[:, 0, 1] = depths
        va1.vertex[:, 0, 1] = depths  # stretch to floor
        va1.vertex[:, (2, 3), 1] -= 0.5  # drop down to prevent intersection pixels

        numpy.multiply(flatcolors, 0.8, out=flatcolors, casting='unsafe')
        #flatcolors *= 0.8

        va1.rgb[:] = flatcolors
        grassmask = topBlocks == 2
        # color grass sides with dirt's color
        va1.rgb[grassmask] = dim.blocktypes.mapColor[:, 0][[3]][:, numpy.newaxis]

        va2 = va1.copy()
        va1.vertex[:, (1, 2), 0] -= 1.0  # turn diagonally
        va2.vertex[:, (0, 3), 0] -= 1.0  # turn diagonally


        nodes = [VertexNode(v) for v in (va1, va2, va0)]

        self.sceneNode = scenenode.Node("lowDetail")
        for node in nodes:
            self.sceneNode.addChild(node)



class OverheadBlockMesh(LowDetailBlockMesh):
    detailLevels = (2,)
