"""
    matrix
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from OpenGL import GL
from mcedit2.rendering.scenegraph.rendernode import RenderstateRenderNode
from mcedit2.rendering.scenegraph.scenenode import Node

log = logging.getLogger(__name__)


class RotateRenderNode(RenderstateRenderNode):
    def __init__(self, sceneNode):
        """

        :type sceneNode: TranslateNode
        """
        super(RotateRenderNode, self).__init__(sceneNode)

    def __repr__(self):
        return "RotateRenderNode(%s, %s)" % (self.sceneNode.degrees, self.sceneNode.axis)

    def enter(self):
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPushMatrix()
        GL.glRotate(self.sceneNode.degrees, *self.sceneNode.axis)

    def exit(self):
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPopMatrix()


class RotateNode(Node):
    RenderNodeClass = RotateRenderNode

    def __init__(self, degrees=0, axis=(0, 1, 0)):
        super(RotateNode, self).__init__()
        self.degrees = degrees
        self.axis = axis

    _degrees = 0
    _axis = (0, 1, 0)

    @property
    def degrees(self):
        return self._degrees

    @degrees.setter
    def degrees(self, value):
        self._degrees = value
        self.dirty = True

    @property
    def axis(self):
        return self._axis

    @axis.setter
    def axis(self, value):
        self._axis = value
        self.dirty = True

class TranslateRenderNode(RenderstateRenderNode):
    def __init__(self, sceneNode):
        """

        :type sceneNode: TranslateNode
        """
        super(TranslateRenderNode, self).__init__(sceneNode)

    def __repr__(self):
        return "TranslateRenderNode(%s)" % (self.sceneNode.translateOffset,)

    def enter(self):
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPushMatrix()
        GL.glTranslate(*self.sceneNode.translateOffset)

    def exit(self):
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPopMatrix()


class TranslateNode(Node):
    RenderNodeClass = TranslateRenderNode

    def __init__(self, translateOffset=(0., 0., 0.)):
        super(TranslateNode, self).__init__()
        self._translateOffset = translateOffset

    @property
    def translateOffset(self):
        return self._translateOffset

    @translateOffset.setter
    def translateOffset(self, value):
        self._translateOffset = value
        self.dirty = True


class ScaleRenderNode(RenderstateRenderNode):
    def __init__(self, sceneNode):
        """

        :type sceneNode: TranslateNode
        """
        super(ScaleRenderNode, self).__init__(sceneNode)

    def __repr__(self):
        return "RotateRenderNode(%s, %s)" % (self.sceneNode.degrees, self.sceneNode.axis)

    def enter(self):
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPushMatrix()
        GL.glScale(*self.sceneNode.scale)

    def exit(self):
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPopMatrix()


class ScaleNode(Node):
    RenderNodeClass = ScaleRenderNode

    def __init__(self, scale):
        super(ScaleNode, self).__init__()
        self.scale = scale


class MatrixRenderNode(RenderstateRenderNode):
    def enter(self):
        projection = self.sceneNode.projection
        if projection is not None:
            GL.glMatrixMode(GL.GL_PROJECTION)
            GL.glPushMatrix()
            GL.glLoadMatrixd(projection.data())

        modelview = self.sceneNode.modelview
        if modelview is not None:
            GL.glMatrixMode(GL.GL_MODELVIEW)
            GL.glPushMatrix()
            GL.glLoadMatrixd(modelview.data())

    def exit(self):
        if self.sceneNode.projection is not None:
            GL.glMatrixMode(GL.GL_PROJECTION)
            GL.glPopMatrix()
        if self.sceneNode.modelview is not None:
            GL.glMatrixMode(GL.GL_MODELVIEW)
            GL.glPopMatrix()


class MatrixNode(Node):
    RenderNodeClass = MatrixRenderNode

    _projection = None

    @property
    def projection(self):
        """

        :return:
        :rtype: QMatrix4x4
        """
        return self._projection

    @projection.setter
    def projection(self, value):
        """

        :type value: QMatrix4x4
        """
        self._projection = value
        self.dirty = True

    _modelview = None
    @property
    def modelview(self):
        """

        :return:
        :rtype: QMatrix4x4
        """
        return self._modelview

    @modelview.setter
    def modelview(self, value):
        """

        :type value: QMatrix4x4
        """
        self._modelview = value
        self.dirty = True


class OrthoRenderNode(RenderstateRenderNode):
    def enter(self):
        w, h = self.sceneNode.size
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GL.glOrtho(0., w, 0., h, -200, 200)

    def exit(self):
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPopMatrix()


class OrthoNode(Node):
    RenderNodeClass = OrthoRenderNode

    def __init__(self, size=(1, 1)):
        super(OrthoNode, self).__init__()
        self._size = size

    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, value):
        self._size = value
        self.dirty = True