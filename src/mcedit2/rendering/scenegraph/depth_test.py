"""
    depth_test
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from OpenGL import GL
from mcedit2.rendering.scenegraph import states

log = logging.getLogger(__name__)


class DepthMask(states.SceneNodeState):
    def enter(self):
        GL.glPushAttrib(GL.GL_DEPTH_BUFFER_BIT)
        GL.glDepthMask(self.mask)

    def exit(self):
        GL.glPopAttrib()

    mask = False


class DepthFunc(states.SceneNodeState):
    def enter(self):
        GL.glPushAttrib(GL.GL_DEPTH_BUFFER_BIT)
        GL.glDepthFunc(self.func)

    def exit(self):
        GL.glPopAttrib()

    def __init__(self, func=GL.GL_LESS):
        super(DepthFunc, self).__init__()
        self.func = func


class DepthOffset(states.SceneNodeState):
    def enter(self):
        GL.glPushAttrib(GL.GL_POLYGON_BIT)
        GL.glPolygonOffset(self.depthOffset, self.depthOffset)
        GL.glEnable(GL.GL_POLYGON_OFFSET_FILL)

    def exit(self):
        GL.glPopAttrib()

    def __init__(self, depthOffset):
        super(DepthOffset, self).__init__()
        self.depthOffset = depthOffset
