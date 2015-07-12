"""
    renderstates
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from OpenGL import GL

from mcedit2.rendering.scenegraph import rendernode
from mcedit2.rendering.depths import DepthOffset

log = logging.getLogger(__name__)



class RenderstatePlainNode(rendernode.RenderstateRenderNode):
    def enter(self):
        pass

    def exit(self):
        pass

class RenderstateVinesNode(rendernode.RenderstateRenderNode):
    def enter(self):
        GL.glPushAttrib(GL.GL_ENABLE_BIT)
        GL.glDisable(GL.GL_CULL_FACE)
        GL.glEnable(GL.GL_ALPHA_TEST)

    def exit(self):
        GL.glPopAttrib()

class RenderstateLowDetailNode(rendernode.RenderstateRenderNode):
    def enter(self):
        GL.glPushAttrib(GL.GL_ENABLE_BIT)
        GL.glDisable(GL.GL_CULL_FACE)
        GL.glDisable(GL.GL_TEXTURE_2D)

    def exit(self):
        GL.glPopAttrib()

class RenderstateAlphaTestNode(rendernode.RenderstateRenderNode):
    def enter(self):
        GL.glPushAttrib(GL.GL_ENABLE_BIT)
        GL.glEnable(GL.GL_ALPHA_TEST)

    def exit(self):
        GL.glPopAttrib()

class _RenderstateAlphaBlendNode(rendernode.RenderstateRenderNode):
    def enter(self):
        GL.glPushAttrib(GL.GL_ENABLE_BIT)
        GL.glEnable(GL.GL_BLEND)

    def exit(self):
        GL.glPopAttrib()

class RenderstateWaterNode(_RenderstateAlphaBlendNode):
    pass

class RenderstateIceNode(_RenderstateAlphaBlendNode):
    pass

class RenderstateEntityNode(rendernode.RenderstateRenderNode):
    def enter(self):
        GL.glPushAttrib(GL.GL_ENABLE_BIT | GL.GL_POLYGON_BIT)
        GL.glPolygonOffset(DepthOffset.Renderer-1, DepthOffset.Renderer-1)
        GL.glEnable(GL.GL_POLYGON_OFFSET_FILL)
        #GL.glDisable(GL.GL_DEPTH_TEST)
        # GL.glDisable(GL.GL_CULL_FACE)
        GL.glDisable(GL.GL_TEXTURE_2D)
        GL.glEnable(GL.GL_BLEND)

    def exit(self):
        GL.glPopAttrib()

allRenderstates = (
    RenderstateLowDetailNode,
    RenderstatePlainNode,
    RenderstateVinesNode,
    RenderstateAlphaTestNode,
    RenderstateWaterNode,
    RenderstateIceNode,
    RenderstateEntityNode,
)
