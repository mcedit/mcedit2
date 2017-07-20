"""
    misc
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from OpenGL import GL
from mcedit2.rendering.scenegraph import states, rendernode
from mcedit2.rendering.scenegraph.scenenode import Node

log = logging.getLogger(__name__)


class PolygonMode(states.SceneNodeState):
    def enter(self):
        GL.glPushAttrib(GL.GL_POLYGON_BIT)
        GL.glPolygonMode(self.face, self.mode)

    def exit(self):
        GL.glPopAttrib()

    def __init__(self, face, mode):
        super(PolygonMode, self).__init__()
        self.face = face
        self.mode = mode


class LineWidth(states.SceneNodeState):
    def enter(self):
        GL.glPushAttrib(GL.GL_LINE_BIT)
        GL.glLineWidth(self.lineWidth)

    def exit(self):
        GL.glPopAttrib()

    def __init__(self, lineWidth):
        super(LineWidth, self).__init__()
        self.lineWidth = lineWidth


class Enable(states.SceneNodeState):
    def enter(self):
        GL.glPushAttrib(GL.GL_ENABLE_BIT)
        for e in self.enables:
            GL.glEnable(e)

    def exit(self):
        GL.glPopAttrib()

    def __init__(self, *enables):
        super(Enable, self).__init__()
        self.enables = enables


class Disable(states.SceneNodeState):
    def enter(self):
        GL.glPushAttrib(GL.GL_ENABLE_BIT)
        for e in self.enables:
            GL.glDisable(e)

    def exit(self):
        GL.glPopAttrib()

    def __init__(self, *enables):
        super(Disable, self).__init__()
        self.enables = enables


class ClearRenderNode(rendernode.RenderNode):
    def drawSelf(self):
        color = self.sceneNode.clearColor
        if color is None:
            GL.glClear(GL.GL_DEPTH_BUFFER_BIT)
        else:
            GL.glClearColor(*color)
            GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)


class ClearNode(Node):
    RenderNodeClass = ClearRenderNode

    def __init__(self, clearColor=(0, 0, 0, 1)):
        super(ClearNode, self).__init__()
        self.clearColor = clearColor
