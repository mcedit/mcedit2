"""
    renderstates
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from OpenGL import GL

from mcedit2.rendering.scenegraph import states
from mcedit2.rendering.depths import DepthOffsets

log = logging.getLogger(__name__)


class RenderstatePlain(states.SceneNodeState):
    def enter(self):
        pass

    def exit(self):
        pass


class RenderstateVines(states.SceneNodeState):
    def enter(self):
        GL.glPushAttrib(GL.GL_ENABLE_BIT)
        GL.glDisable(GL.GL_CULL_FACE)
        GL.glEnable(GL.GL_ALPHA_TEST)

    def exit(self):
        GL.glPopAttrib()


class RenderstateLowDetail(states.SceneNodeState):
    def enter(self):
        GL.glPushAttrib(GL.GL_ENABLE_BIT)
        GL.glDisable(GL.GL_CULL_FACE)
        GL.glDisable(GL.GL_TEXTURE_2D)

    def exit(self):
        GL.glPopAttrib()


class RenderstateHeightLevel(states.SceneNodeState):
    def enter(self):
        GL.glPushAttrib(GL.GL_ENABLE_BIT | GL.GL_POLYGON_BIT)
        GL.glDisable(GL.GL_CULL_FACE)
        GL.glDisable(GL.GL_TEXTURE_2D)
        GL.glEnable(GL.GL_BLEND)
        GL.glPolygonOffset(-1, -1)
        GL.glEnable(GL.GL_POLYGON_OFFSET_FILL)

    def exit(self):
        GL.glPopAttrib()


class RenderstateAlphaTest(states.SceneNodeState):
    def enter(self):
        GL.glPushAttrib(GL.GL_ENABLE_BIT)
        GL.glEnable(GL.GL_ALPHA_TEST)

    def exit(self):
        GL.glPopAttrib()


class _RenderstateAlphaBlend(states.SceneNodeState):
    def enter(self):
        GL.glPushAttrib(GL.GL_ENABLE_BIT)
        GL.glEnable(GL.GL_BLEND)

    def exit(self):
        GL.glPopAttrib()


class RenderstateWater(_RenderstateAlphaBlend):
    pass


class RenderstateIce(_RenderstateAlphaBlend):
    pass


class RenderstateEntity(states.SceneNodeState):
    def enter(self):
        GL.glPushAttrib(GL.GL_ENABLE_BIT | GL.GL_POLYGON_BIT)
        GL.glPolygonOffset(DepthOffsets.Renderer - 1, DepthOffsets.Renderer - 1)
        GL.glEnable(GL.GL_POLYGON_OFFSET_FILL)
        GL.glDisable(GL.GL_TEXTURE_2D)
        GL.glEnable(GL.GL_BLEND)

    def exit(self):
        GL.glPopAttrib()

allRenderstates = (
    RenderstateLowDetail,
    RenderstatePlain,
    RenderstateVines,
    RenderstateAlphaTest,
    RenderstateWater,
    RenderstateIce,
    RenderstateEntity,
    RenderstateHeightLevel,
)
