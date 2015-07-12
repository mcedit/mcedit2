"""
    bind_texture
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from OpenGL import GL
from mcedit2.rendering.scenegraph import rendernode
from mcedit2.rendering.scenegraph.rendernode import RenderstateRenderNode
from mcedit2.rendering.scenegraph.scenenode import Node
from mcedit2.util import glutils

log = logging.getLogger(__name__)


class BindTextureRenderNode(RenderstateRenderNode):
    def enter(self):
        GL.glPushAttrib(GL.GL_ENABLE_BIT | GL.GL_TEXTURE_BIT)
        GL.glMatrixMode(GL.GL_TEXTURE)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        scale = self.sceneNode.scale
        if scale is not None:
            GL.glScale(*scale)
        glutils.glActiveTexture(GL.GL_TEXTURE0)
        GL.glEnable(GL.GL_TEXTURE_2D)
        self.sceneNode.texture.bind()

    def exit(self):
        GL.glMatrixMode(GL.GL_TEXTURE)
        GL.glPopMatrix()
        GL.glPopAttrib()


class BindTextureNode(Node):
    RenderNodeClass = BindTextureRenderNode

    def __init__(self, texture, scale=None):
        """

        :type texture: glutils.Texture
        """
        super(BindTextureNode, self).__init__()
        self.texture = texture
        self.scale = scale
