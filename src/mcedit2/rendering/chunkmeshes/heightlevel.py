"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

import numpy

from mcedit2.rendering import renderstates
from mcedit2.rendering.blockmeshes import standardCubeTemplates
from mcedit2.rendering.blockmeshes import ChunkMeshBase
from mcedit2.rendering.layers import Layer
from mcedit2.rendering.scenegraph.vertex_array import VertexNode
from mcedit2.rendering.vertexarraybuffer import QuadVertexArrayBuffer
from mceditlib import faces

log = logging.getLogger(__name__)


class HeightLevelBlockMesh(ChunkMeshBase):
    renderstate = renderstates.RenderstateHeightLevel
    layer = Layer.HeightMap
    def makeChunkVertices(self, chunk, limitBox):
        """

        :param chunk:
        :type chunk: WorldEditorChunk
        :param limitBox:
        :return: :raise:
        """

        if not hasattr(chunk, 'HeightMap') or chunk.HeightMap is None:
            return

        heightMap = chunk.HeightMap
        chunkWidth = chunkLength = 16
        chunkHeight = chunk.dimension.bounds.height

        z, x = list(numpy.indices((chunkLength, chunkWidth)))
        y = (heightMap - 1)[:chunkLength, :chunkWidth]
        numpy.clip(y, 0, chunkHeight - 1, y)

        nonZeroHeights = y > 0

        x = x[nonZeroHeights]
        if not len(x):
            return

        z = z[nonZeroHeights]
        y = y[nonZeroHeights]

        yield
        vertexBuffer = QuadVertexArrayBuffer(len(x), textures=False, lights=False)

        vertexBuffer.vertex[..., 0] = x[:, numpy.newaxis]
        vertexBuffer.vertex[..., 1] = y[:, numpy.newaxis]
        vertexBuffer.vertex[..., 2] = z[:, numpy.newaxis]


        vertexBuffer.vertex[:] += standardCubeTemplates[faces.FaceYIncreasing, ..., :3]

        vertexBuffer.rgba[:] = (0xff, 0x00, 0xff, 0x9f)
        self.sceneNode = VertexNode(vertexBuffer)

        yield


