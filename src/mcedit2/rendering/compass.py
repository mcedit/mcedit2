"""
    compass
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from OpenGL import GL

from mcedit2.rendering.scenegraph import scenenode, rendernode
from mcedit2.util.glutils import gl
from mcedit2.util.load_png import loadPNGTexture

log = logging.getLogger(__name__)


def makeQuad(minx, miny, width, height):
    return [minx, miny, minx+width, miny, minx+width, miny+height, minx, miny + height]

class CompassRenderNode(rendernode.RenderNode):
    _tex = None

    def compile(self):
        if self._tex is None:
            if self.sceneNode.small:
                filename = "compass_small.png"
            else:
                filename = "compass.png"

            self._tex = loadPNGTexture(filename, minFilter=GL.GL_LINEAR, magFilter=GL.GL_LINEAR)
            self._tex.load()
        super(CompassRenderNode, self).compile()

    def drawSelf(self):

        self._tex.bind()

        with gl.glPushMatrix(GL.GL_MODELVIEW):
            GL.glLoadIdentity()
            yaw, pitch = self.sceneNode.yawPitch
            GL.glTranslatef(0.9, 0.1, 0.0)  # position on lower right corner
            GL.glRotatef(pitch, 1., 0., 0.)  # Tilt upward a bit if the view is pitched
            GL.glRotatef(yaw - 180, 0., 0., 1.)  # adjust to north
            GL.glColor4f(1., 1., 1., 1.)

            with gl.glPushAttrib(GL.GL_ENABLE_BIT):
                GL.glDisable(GL.GL_DEPTH_TEST)
                with gl.glEnableClientState(GL.GL_TEXTURE_COORD_ARRAY):
                    GL.glVertexPointer(2, GL.GL_FLOAT, 0, makeQuad(-.1, -.1, 0.2, 0.2))
                    GL.glTexCoordPointer(2, GL.GL_FLOAT, 0, makeQuad(0, 0, 1, 1))

                    with gl.glEnable(GL.GL_BLEND, GL.GL_TEXTURE_2D):
                        GL.glDrawArrays(GL.GL_QUADS, 0, 4)


class CompassNode(scenenode.Node):
    _yawPitch = (0., 0.)
    RenderNodeClass = CompassRenderNode

    def __init__(self, small=False):
        super(CompassNode, self).__init__()
        self.small = small

    @property
    def yawPitch(self):
        return self._yawPitch

    @yawPitch.setter
    def yawPitch(self, value):
        self._yawPitch = value
        self.dirty = True
