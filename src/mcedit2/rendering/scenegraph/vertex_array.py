"""
    vertex_array
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from OpenGL import GL
import numpy

from mcedit2.rendering.scenegraph.rendernode import RenderNode
from mcedit2.rendering.scenegraph.scenenode import Node
from mcedit2.util import glutils
from mcedit2.util.glutils import gl

log = logging.getLogger(__name__)


class VertexRenderNode(RenderNode):
    def __init__(self, sceneNode):
        """

        :type sceneNode: VertexNode
        """
        super(VertexRenderNode, self).__init__(sceneNode)

        self.didDraw = False

    def invalidate(self):
        if self.didDraw:
            assert False
        super(VertexRenderNode, self).invalidate()

    def drawSelf(self):
        self.didDraw = True
        bare = []
        withTex = []
        withLights = []
        for array in self.sceneNode.vertexArrays:
            if array.lights:
                withLights.append(array)
            elif array.textures:
                withTex.append(array)
            else:
                bare.append(array)

        with gl.glPushAttrib(GL.GL_ENABLE_BIT):
            if len(bare):
                glutils.glActiveTexture(GL.GL_TEXTURE0)
                GL.glDisable(GL.GL_TEXTURE_2D)
                glutils.glActiveTexture(GL.GL_TEXTURE1)
                GL.glDisable(GL.GL_TEXTURE_2D)
                glutils.glActiveTexture(GL.GL_TEXTURE0)
                self.drawArrays(bare, False, False)

            if len(withTex) or len(withLights):
                glutils.glActiveTexture(GL.GL_TEXTURE0)
                GL.glEnable(GL.GL_TEXTURE_2D)

            if len(withTex):
                self.drawArrays(withTex, True, False)

            if len(withLights):
                glutils.glActiveTexture(GL.GL_TEXTURE1)
                GL.glEnable(GL.GL_TEXTURE_2D)
                glutils.glActiveTexture(GL.GL_TEXTURE0)
                self.drawArrays(withLights, True, True)

    def drawArrays(self, vertexArrays, textures, lights):
        if textures:
            GL.glClientActiveTexture(GL.GL_TEXTURE0)
            GL.glEnableClientState(GL.GL_TEXTURE_COORD_ARRAY)
        if lights:
            GL.glClientActiveTexture(GL.GL_TEXTURE1)
            GL.glEnableClientState(GL.GL_TEXTURE_COORD_ARRAY)
        else:
            GL.glMultiTexCoord2d(GL.GL_TEXTURE1, 15, 15)

        GL.glEnableClientState(GL.GL_COLOR_ARRAY)

        for array in vertexArrays:
            if 0 == len(array.buffer):
                continue
            stride = 4 * array.elements

            buf = array.buffer.ravel()

            GL.glVertexPointer(3, GL.GL_FLOAT, stride, buf)
            if textures:
                GL.glClientActiveTexture(GL.GL_TEXTURE0)
                GL.glTexCoordPointer(2, GL.GL_FLOAT, stride, (buf[array.texOffset:]))
            if lights:
                GL.glClientActiveTexture(GL.GL_TEXTURE1)
                GL.glTexCoordPointer(2, GL.GL_FLOAT, stride, (buf[array.lightOffset:]))
            GL.glColorPointer(4, GL.GL_UNSIGNED_BYTE, stride, (buf.view(dtype=numpy.uint8)[array.rgbaOffset*4:]))

            vertexCount = int(array.buffer.size / array.elements)
            GL.glDrawArrays(array.gl_type, 0, vertexCount)

        GL.glDisableClientState(GL.GL_COLOR_ARRAY)

        if lights:
            GL.glDisableClientState(GL.GL_TEXTURE_COORD_ARRAY)

        if textures:
            GL.glClientActiveTexture(GL.GL_TEXTURE0)
            GL.glDisableClientState(GL.GL_TEXTURE_COORD_ARRAY)


class VertexNode(Node):
    RenderNodeClass = VertexRenderNode

    def __init__(self, vertexArrays):
        """

        Parameters
        ----------
        vertexArrays : Union[List[mcedit2.rendering.vertexarraybuffer.QuadVertexArrayBuffer], mcedit2.rendering.vertexarraybuffer.VertexArrayBuffer]
        """
        super(VertexNode, self).__init__()
        if not isinstance(vertexArrays, (list, tuple)):
            vertexArrays = [vertexArrays]
        self.vertexArrays = vertexArrays
