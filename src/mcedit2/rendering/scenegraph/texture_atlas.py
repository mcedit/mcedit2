"""
    texture_atlas
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from OpenGL import GL

from mcedit2.rendering.scenegraph.scenenode import Node
from mcedit2.rendering.scenegraph.states import SceneNodeState
from mcedit2.util import glutils

log = logging.getLogger(__name__)


class TextureAtlasState(SceneNodeState):
    def enter(self):
        if self.textureAtlas is None:
            return

        GL.glColor(1., 1., 1., 1.)
        textureAtlas = self.textureAtlas
        glutils.glActiveTexture(GL.GL_TEXTURE0)
        GL.glEnable(GL.GL_TEXTURE_2D)
        textureAtlas.bindTerrain()

        GL.glMatrixMode(GL.GL_TEXTURE)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GL.glScale(1. / textureAtlas.width, 1. / textureAtlas.height, 1.)

        glutils.glActiveTexture(GL.GL_TEXTURE1)
        GL.glEnable(GL.GL_TEXTURE_2D)
        textureAtlas.bindLight()

        GL.glMatrixMode(GL.GL_TEXTURE)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GL.glScale(1. / 16, 1. / 16, 1.)

        glutils.glActiveTexture(GL.GL_TEXTURE0)
        GL.glEnable(GL.GL_CULL_FACE)

    def exit(self):
        if self.textureAtlas is None:
            return

        GL.glDisable(GL.GL_CULL_FACE)
        glutils.glActiveTexture(GL.GL_TEXTURE1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        GL.glDisable(GL.GL_TEXTURE_2D)
        GL.glMatrixMode(GL.GL_TEXTURE)
        GL.glPopMatrix()

        glutils.glActiveTexture(GL.GL_TEXTURE0)
        GL.glDisable(GL.GL_TEXTURE_2D)
        GL.glMatrixMode(GL.GL_TEXTURE)
        GL.glPopMatrix()

    def __init__(self, textureAtlas=None):
        super(TextureAtlasState, self).__init__()
        self.textureAtlas = textureAtlas

    @property
    def textureAtlas(self):
        return self._textureAtlas

    @textureAtlas.setter
    def textureAtlas(self, value):
        self._textureAtlas = value
        self.dirty = True