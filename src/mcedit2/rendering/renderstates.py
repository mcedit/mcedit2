"""
    renderstates
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from OpenGL import GL

from mcedit2.rendering import rendergraph

log = logging.getLogger(__name__)



class RenderstatePlainNode(rendergraph.RenderstateRenderNode):
    def enter(self):
        pass

    def exit(self):
        pass

class RenderstateVinesNode(rendergraph.RenderstateRenderNode):
    def enter(self):
        GL.glPushAttrib(GL.GL_ENABLE_BIT)
        GL.glDisable(GL.GL_CULL_FACE)
        GL.glEnable(GL.GL_ALPHA_TEST)

    def exit(self):
        GL.glPopAttrib()

class RenderstateLowDetailNode(rendergraph.RenderstateRenderNode):
    def enter(self):
        GL.glPushAttrib(GL.GL_ENABLE_BIT)
        GL.glDisable(GL.GL_CULL_FACE)
        GL.glDisable(GL.GL_TEXTURE_2D)

    def exit(self):
        GL.glPopAttrib()

class RenderstateAlphaTestNode(rendergraph.RenderstateRenderNode):
    def enter(self):
        GL.glPushAttrib(GL.GL_ENABLE_BIT)
        GL.glEnable(GL.GL_ALPHA_TEST)

    def exit(self):
        GL.glPopAttrib()

class _RenderstateAlphaBlendNode(rendergraph.RenderstateRenderNode):
    def enter(self):
        GL.glPushAttrib(GL.GL_ENABLE_BIT)
        GL.glEnable(GL.GL_BLEND)

    def exit(self):
        GL.glPopAttrib()

class RenderstateWaterNode(_RenderstateAlphaBlendNode):
    pass

class RenderstateIceNode(_RenderstateAlphaBlendNode):
    pass

class RenderstateEntityNode(rendergraph.RenderstateRenderNode):
    def enter(self):
        GL.glPushAttrib(GL.GL_ENABLE_BIT)
        GL.glDisable(GL.GL_DEPTH_TEST)
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
