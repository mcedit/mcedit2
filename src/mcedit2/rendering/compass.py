"""
    compass
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from OpenGL import GL

from mcedit2.rendering.scenegraph import scenenode, rendernode
from mcedit2.rendering.scenegraph.bind_texture import BindTexture
from mcedit2.rendering.scenegraph.matrix import Rotate, Identity, Translate
from mcedit2.rendering.scenegraph.misc import Disable, Enable
from mcedit2.rendering.scenegraph.vertex_array import VertexNode
from mcedit2.rendering.vertexarraybuffer import QuadVertexArrayBuffer
from mcedit2.util.glutils import gl
from mcedit2.util.load_png import loadPNGTexture

log = logging.getLogger(__name__)


def makeQuad(minx, miny, width, height):
    return [[minx, miny], [minx+width, miny], [minx+width, miny+height], [minx, miny + height]]


class CompassNode(scenenode.Node):
    _yawPitch = (0., 0.)

    def __init__(self, small=False):
        super(CompassNode, self).__init__()
        self.small = small
        v = QuadVertexArrayBuffer(1, textures=True)
        v.vertex[..., :2] = makeQuad(-.1, -.1, 0.2, 0.2)
        v.texcoord[:] = makeQuad(0, 0, 1, 1)
        v.rgba[:] = 0xff

        self.vertexNode = VertexNode([v])
        self.pitchState = Rotate(0, (1., 0., 0.))
        self.yawState = Rotate(0, (0., 0., 1.))

        self.addState(Identity())
        self.addState(Translate((0.9, 0.1, 0.0)))
        self.addState(self.pitchState)
        self.addState(self.yawState)
        self.addState(Disable(GL.GL_DEPTH_TEST))
        self.addState(Enable(GL.GL_BLEND, GL.GL_TEXTURE_2D))

        if small:
            filename = "compass_small.png"
        else:
            filename = "compass.png"

        self._tex = loadPNGTexture(filename, minFilter=GL.GL_LINEAR, magFilter=GL.GL_LINEAR)
        self.textureState = BindTexture(self._tex)
        self.addState(self.textureState)

        self.addChild(self.vertexNode)

    @property
    def yawPitch(self):
        return self._yawPitch

    @yawPitch.setter
    def yawPitch(self, value):
        y, p = self._yawPitch = value
        self.yawState.degrees = y - 180
        self.pitchState.degrees = p

