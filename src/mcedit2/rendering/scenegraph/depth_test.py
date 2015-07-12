"""
    depth_test
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from OpenGL import GL
from mcedit2.rendering.scenegraph.rendernode import RenderstateRenderNode
from mcedit2.rendering.scenegraph.scenenode import Node

log = logging.getLogger(__name__)


class DepthMaskRenderNode(RenderstateRenderNode):
    def enter(self):
        GL.glPushAttrib(GL.GL_DEPTH_BUFFER_BIT)
        GL.glDepthMask(self.sceneNode.mask)

    def exit(self):
        GL.glPopAttrib()


class DepthMaskNode(Node):
    RenderNodeClass = DepthMaskRenderNode
    mask = False


class DepthFuncRenderNode(RenderstateRenderNode):
    def enter(self):
        GL.glPushAttrib(GL.GL_DEPTH_BUFFER_BIT)
        GL.glDepthFunc(self.sceneNode.func)

    def exit(self):
        GL.glPopAttrib()


class DepthFuncNode(Node):
    RenderNodeClass = DepthFuncRenderNode

    def __init__(self, func=GL.GL_LESS):
        super(DepthFuncNode, self).__init__()
        self.func = func


class DepthOffsetRenderNode(RenderstateRenderNode):
    def enter(self):
        GL.glPushAttrib(GL.GL_POLYGON_BIT)
        GL.glPolygonOffset(self.sceneNode.depthOffset, self.sceneNode.depthOffset)
        GL.glEnable(GL.GL_POLYGON_OFFSET_FILL)

    def exit(self):
        GL.glPopAttrib()


class DepthOffsetNode(Node):
    RenderNodeClass = DepthOffsetRenderNode

    def __init__(self, depthOffset):
        super(DepthOffsetNode, self).__init__()
        self.depthOffset = depthOffset
