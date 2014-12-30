"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from OpenGL import GL
import numpy
from mcedit2.rendering import renderstates
from mcedit2.rendering.blockmeshes import standardCubeTemplates
from mcedit2.rendering.blockmeshes.blockmesh import ChunkMeshBase
from mcedit2.rendering.layers import Layer
from mcedit2.rendering.slices import _XYZ, _RGBA
from mcedit2.rendering.vertexarraybuffer import VertexArrayBuffer

log = logging.getLogger(__name__)

class EmptySectionsRenderer(ChunkMeshBase):
    layer = Layer.Entities
    renderstate = renderstates.RenderstateWaterNode
    color = (255, 0, 0)

    vertexTemplate = numpy.zeros((6, 4, 4), 'float32')
    vertexTemplate[_XYZ] = standardCubeTemplates[_XYZ]
    vertexTemplate[_XYZ] *= (16, 16, 16)
    vertexTemplate.view('uint8')[_RGBA] = color + (120,)


    def makeChunkVertices(self, chunk, _limitBox):
        sections = [y for y in chunk.bounds.sectionPositions()
                    if chunk.getSection(y) is not None and (chunk.getSection(y).Blocks == 0).all()]
        if not len(sections):
            return

        buffer = VertexArrayBuffer(len(sections) * 6, textures=False, lights=False)
        for i, y in enumerate(sections):
            i = i * 6

            buffer.vertex[i:i+6] = self.vertexTemplate[_XYZ]
            buffer.vertex[i:i+6][..., 1] += y << 4

        buffer.rgba[:] = 255, 0, 0, 255
        buffer.gl_type = GL.GL_LINES
        self.vertexArrays.append(buffer)

        yield
