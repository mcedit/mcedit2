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
from mcedit2.rendering.layers import Layer
from mcedit2.rendering.scenegraph.vertex_array import VertexNode
from mcedit2.rendering.slices import _XYZ, _RGBA
from mcedit2.rendering.vertexarraybuffer import QuadVertexArrayBuffer
from mceditlib import faces

log = logging.getLogger(__name__)

class TerrainPopulatedRenderer(ChunkMeshBase):
    layer = Layer.TerrainPopulated
    renderstate = renderstates.RenderstateEntity
    color = (255, 200, 155)

    vertexTemplate = numpy.zeros((6, 4, 4), 'float32')
    vertexTemplate[_XYZ] = standardCubeTemplates[_XYZ]
    vertexTemplate[_XYZ] *= (16, 256, 16)
    vertexTemplate.view('uint8')[_RGBA] = color + (72,)
    #
    #    def drawFaceVertices(self, buf):
    #        if 0 == len(buf):
    #            return
    #
    #        stride = 24
    #        GL.glVertexPointer(3, GL.GL_FLOAT, stride, (buf.ravel()))
    #        GL.glColorPointer(4, GL.GL_UNSIGNED_BYTE, stride, (buf.view(dtype=numpy.uint8).ravel()[20:]))
    #
    #        GL.glDepthMask(False)
    #
    #        # GL.glDrawArrays(GL.GL_QUADS, 0, len(buf) * 4)
    #        GL.glDisable(GL.GL_CULL_FACE)
    #
    #        with gl.glEnable(GL.GL_DEPTH_TEST):
    #            GL.glDrawArrays(GL.GL_QUADS, 0, len(buf) * 4)
    #
    #        GL.glEnable(GL.GL_CULL_FACE)
    #
    #        GL.glPolygonMode(GL.GL_FRONT_AND_BACK, GL.GL_LINE)
    #
    #        GL.glLineWidth(1.0)
    #        GL.glDrawArrays(GL.GL_QUADS, 0, len(buf) * 4)
    #        GL.glLineWidth(2.0)
    #        with gl.glEnable(GL.GL_DEPTH_TEST):
    #            GL.glDrawArrays(GL.GL_QUADS, 0, len(buf) * 4)
    #        GL.glLineWidth(1.0)
    #
    #        GL.glPolygonMode(GL.GL_FRONT_AND_BACK, GL.GL_FILL)
    #        GL.glDepthMask(True)

    #        GL.glPolygonOffset(DepthOffset.TerrainWire, DepthOffset.TerrainWire)
    #        with gl.glEnable(GL.GL_POLYGON_OFFSET_FILL, GL.GL_DEPTH_TEST):
    #            GL.glDrawArrays(GL.GL_QUADS, 0, len(buf) * 4)
    #

    def makeChunkVertices(self, chunk, _limitBox):
        neighbors = self.chunkUpdate.neighboringChunks

        def getpop(face):
            ch = neighbors.get(face)
            if ch:
                return getattr(ch, "TerrainPopulated", True)
            else:
                return True

        pop = getattr(chunk, "TerrainPopulated", True)
        yield
        if pop:
            return

        visibleFaces = [
            getpop(faces.FaceXIncreasing),
            getpop(faces.FaceXDecreasing),
            True,
            True,
            getpop(faces.FaceZIncreasing),
            getpop(faces.FaceZDecreasing),
        ]
        visibleFaces = numpy.array(visibleFaces, dtype='bool')
        verts = self.vertexTemplate[visibleFaces]
        buffer = QuadVertexArrayBuffer(0, textures=False, lights=False)
        buffer.buffer = verts
        self.sceneNode = VertexNode(buffer)

        yield
