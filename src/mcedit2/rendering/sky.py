"""
    sky
"""
from __future__ import absolute_import, division, print_function
import logging

from OpenGL import GL
import numpy

from mcedit2.rendering.scenegraph import scenenode, rendernode
from mcedit2.util.glutils import gl

log = logging.getLogger(__name__)


class SkyRenderNode(rendernode.RenderNode):
    def drawSelf(self):
        with gl.glPushMatrix(GL.GL_MODELVIEW):
            GL.glLoadIdentity()
            with gl.glPushMatrix(GL.GL_PROJECTION):
                GL.glLoadIdentity()
                GL.glClear(GL.GL_COLOR_BUFFER_BIT)
                GL.glEnableClientState(GL.GL_COLOR_ARRAY)
                quad = numpy.array([-1, -1, -1, 1, 1, 1, 1, -1], dtype='float32')
                colors = numpy.array([0x48, 0x49, 0xBA, 0xff,
                                      0x8a, 0xaf, 0xff, 0xff,
                                      0x8a, 0xaf, 0xff, 0xff,
                                      0x48, 0x49, 0xBA, 0xff, ], dtype='uint8')
                numpy.multiply(colors, self.sceneNode.dayTime, out=colors, casting='unsafe')

                with gl.glPushAttrib(GL.GL_DEPTH_BUFFER_BIT):
                    GL.glDepthMask(False)
                    GL.glVertexPointer(2, GL.GL_FLOAT, 0, quad)
                    GL.glColorPointer(4, GL.GL_UNSIGNED_BYTE, 0, colors)
                    GL.glDrawArrays(GL.GL_QUADS, 0, 4)
                GL.glDisableClientState(GL.GL_COLOR_ARRAY)


class SkyNode(scenenode.Node):
    RenderNodeClass = SkyRenderNode

    dayTime = 1.0

    def setDayTime(self, value):
        self.dayTime = value
        self.dirty = True
