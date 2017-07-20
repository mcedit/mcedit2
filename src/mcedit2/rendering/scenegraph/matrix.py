"""
    matrix
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from OpenGL import GL
from mcedit2.rendering.scenegraph import states
from mceditlib.geometry import Vector

log = logging.getLogger(__name__)


class Identity(states.SceneNodeState):
    def enter(self):
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPushMatrix()
        GL.glLoadIdentity()

    def exit(self):
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPopMatrix()


class Rotate(states.SceneNodeState):
    def __repr__(self):
        return "Rotate(%s, %s)" % (self.degrees, self.axis)

    def enter(self):
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPushMatrix()
        GL.glRotate(self.degrees, *self.axis)

    def exit(self):
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPopMatrix()

    def __init__(self, degrees=0, axis=(0, 1, 0)):
        super(Rotate, self).__init__()
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


class Translate(states.SceneNodeState):
    def __repr__(self):
        return "Translate(%s)" % (self.translateOffset,)

    def enter(self):
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPushMatrix()
        GL.glTranslate(*self.translateOffset)

    def exit(self):
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPopMatrix()

    def __init__(self, translateOffset=Vector(0., 0., 0.)):
        super(Translate, self).__init__()
        self.translateOffset = translateOffset

    @property
    def translateOffset(self):
        return self._translateOffset

    @translateOffset.setter
    def translateOffset(self, value):
        self._translateOffset = Vector(*value)
        self.dirty = True


class Scale(states.SceneNodeState):
    def __repr__(self):
        return "Scale(%s)" % (self.scale,)

    def enter(self):
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPushMatrix()
        GL.glScale(*self.scale)

    def exit(self):
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPopMatrix()

    def __init__(self, scale=(1.0, 1.0, 1.0)):
        super(Scale, self).__init__()
        self.scale = scale
    
    _scale = (1.0, 1.0, 1.0)
    
    @property
    def scale(self):
        return self._scale

    @scale.setter
    def scale(self, value):
        self._scale = value
        self.dirty = True


class MatrixState(states.SceneNodeState):
    def enter(self):
        projection = self.projection
        if projection is not None:
            GL.glMatrixMode(GL.GL_PROJECTION)
            GL.glPushMatrix()
            GL.glLoadMatrixd(projection.data())

        modelview = self.modelview
        if modelview is not None:
            GL.glMatrixMode(GL.GL_MODELVIEW)
            GL.glPushMatrix()
            GL.glLoadMatrixd(modelview.data())

    def exit(self):
        if self.projection is not None:
            GL.glMatrixMode(GL.GL_PROJECTION)
            GL.glPopMatrix()
        if self.modelview is not None:
            GL.glMatrixMode(GL.GL_MODELVIEW)
            GL.glPopMatrix()

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


class Ortho(states.SceneNodeState):
    def enter(self):
        w, h = self.size
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GL.glOrtho(0., w, 0., h, -200, 200)

    def exit(self):
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPopMatrix()

    def __init__(self, size=(1, 1)):
        super(Ortho, self).__init__()
        self._size = size

    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, value):
        self._size = value
        self.dirty = True