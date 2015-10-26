"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from OpenGL import GL
import numpy

from mcedit2.rendering import renderstates
from mcedit2.rendering.blockmeshes import standardCubeTemplates
from mcedit2.rendering.blockmeshes import ChunkMeshBase
from mcedit2.rendering.layers import Layer
from mcedit2.rendering.scenegraph.vertex_array import VertexNode
from mcedit2.rendering.slices import _XYZ, _RGBA
from mcedit2.rendering.vertexarraybuffer import VertexArrayBuffer

log = logging.getLogger(__name__)

class ChunkSectionsRenderer(ChunkMeshBase):
    layer = Layer.ChunkSections
    renderstate = renderstates.RenderstateEntity
    color = (255, 200, 255)

    vertexTemplate = numpy.zeros((6, 4, 4), 'float32')
    vertexTemplate[_XYZ] = standardCubeTemplates[_XYZ]
    vertexTemplate[_XYZ] *= (16, 16, 16)
    vertexTemplate.view('uint8')[_RGBA] = color + (72,)

    def makeChunkVertices(self, chunk, _limitBox):
        positions = chunk.sectionPositions()

        buffer = VertexArrayBuffer((len(positions), 6, 4), GL.GL_LINE_STRIP, textures=False, lights=False)
        for i, cy in enumerate(positions):
            buffer.buffer[i, :] = self.vertexTemplate
            buffer.vertex[i, ..., 1] += cy * 16

        self.sceneNode = VertexNode(buffer)

        yield
