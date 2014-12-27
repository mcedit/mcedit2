"""
    sky
"""
from __future__ import absolute_import, division, print_function
import logging

from OpenGL import GL
import numpy

from mcedit2.rendering import scenegraph, rendergraph
from mcedit2.util.glutils import gl

log = logging.getLogger(__name__)


class SkyRenderNode(rendergraph.RenderNode):
    def drawSelf(self):
        with gl.glPushMatrix(GL.GL_MODELVIEW):
            GL.glLoadIdentity()
            with gl.glPushMatrix(GL.GL_PROJECTION):
                GL.glLoadIdentity()
                with gl.glPushClientAttrib(GL.GL_CLIENT_VERTEX_ARRAY_BIT):
                    GL.glClear(GL.GL_COLOR_BUFFER_BIT)
                    GL.glEnableClientState(GL.GL_COLOR_ARRAY)
                    quad = numpy.array([-1, -1, -1, 1, 1, 1, 1, -1], dtype='float32')
                    colors = numpy.array([0x48, 0x49, 0xBA, 0xff,
                                          0x8a, 0xaf, 0xff, 0xff,
                                          0x8a, 0xaf, 0xff, 0xff,
                                          0x48, 0x49, 0xBA, 0xff, ], dtype='uint8')

                    with gl.glPushAttrib(GL.GL_DEPTH_BUFFER_BIT):
                        GL.glDepthMask(False)
                        GL.glVertexPointer(2, GL.GL_FLOAT, 0, quad)
                        GL.glColorPointer(4, GL.GL_UNSIGNED_BYTE, 0, colors)
                        GL.glDrawArrays(GL.GL_QUADS, 0, 4)


class SkyNode(scenegraph.Node):
    RenderNodeClass = SkyRenderNode
