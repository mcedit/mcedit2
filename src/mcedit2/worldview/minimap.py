"""
    minimap.py
"""
from __future__ import absolute_import, division, print_function, unicode_literals
from OpenGL import GL
from PySide import QtCore, QtGui
import logging
import numpy
from mcedit2.rendering import compass, scenegraph, rendergraph
from mcedit2.util import raycast
from mcedit2.util.glutils import gl
from mcedit2.util.raycast import rayCastInBounds
from mcedit2.worldview.worldview import WorldView
from mceditlib.geometry import Vector, Ray

log = logging.getLogger(__name__)

class ViewCornersRenderNode(rendergraph.RenderNode):
    # bottom left, near
    # bottom left, far
    # top left, near
    # top left, far
    # bottom right, near
    # bottom right, far
    # top right, near
    # top right, far

    def drawSelf(self):
        if self.sceneNode.corners is None or self.sceneNode.dimension is None:
            return
        corners = self.sceneNode.corners
        dimension = self.sceneNode.dimension
        corners = corners[:2], corners[2:4], corners[6:8], corners[4:6]

        def rayCastCorner(near, far):
            ray = Ray.fromPoints(near, far)
            if not any(ray.vector):
                return far
            try:
                #point = rayCastInBounds(ray, dimension, 50)[0]
                #return point or far
                return near + (near - far) / 4
            except raycast.MaxDistanceError:
                return ray.atHeight(0)

        # Average nearby height values or something to suppress jitter??
        corners = [rayCastCorner(near, far) for near, far in corners]
        corners.append(corners[0])

        with gl.glPushAttrib(GL.GL_DEPTH_BUFFER_BIT, GL.GL_COLOR_BUFFER_BIT):
            GL.glDepthMask(False)
            GL.glEnable(GL.GL_BLEND)
            GL.glVertexPointer(3, GL.GL_FLOAT, 0, numpy.array(corners).ravel())

            GL.glLineWidth(3.0)

            GL.glColor(1, 1, .1, 0.5)
            GL.glDisable(GL.GL_DEPTH_TEST)
            GL.glDrawArrays(GL.GL_LINE_STRIP, 0, 5)




class ViewCornersNode(scenegraph.Node):
    RenderNodeClass = ViewCornersRenderNode

    _corners = None

    @property
    def corners(self):
        return self._corners

    @corners.setter
    def corners(self, value):
        self._corners = value
        self.dirty = True

    _dimension = None

    @property
    def dimension(self):
        return self._dimension

    @dimension.setter
    def dimension(self, value):
        self._dimension = value
        self.dirty = True


class MinimapWorldView(WorldView):
    minScale = 1.
    def __init__(self, *a, **kw):
        WorldView.__init__(self, *a, **kw)
        self.setSizePolicy(QtGui.QSizePolicy.Policy.Minimum, QtGui.QSizePolicy.Policy.Minimum)
        self.scale = 1.0
        self.worldScene.minlod = 2
        self.viewCornersNode = ViewCornersNode()
        self.viewCornersNode.dimension = self.dimension
        self.matrixNode.addChild(self.viewCornersNode)

    def createCompass(self):
        compassNode = compass.CompassNode(small=True)
        compassNode.yawPitch = 180, 0
        return compassNode

    def updateMatrices(self):
        w, h = self.width(), self.height()
        w *= self.scale
        h *= self.scale

        projection = QtGui.QMatrix4x4()
        projection.ortho(-w/2, w/2, -h/2, h/2, -1000, 2000)
        self.matrixNode.projection = projection

        modelview = QtGui.QMatrix4x4()
        modelview.rotate(90., 1., 0., 0.)
        modelview.translate(-self.centerPoint[0], 0, -self.centerPoint[2])
        self.matrixNode.modelview = modelview

    def currentViewMatrixChanged(self, currentView):
        self.viewCornersNode.corners = currentView.getViewBounds()

    def zoom(self, scale, (mx, my)):

        # Get mouse position in world coordinates
        worldPos = self.unprojectAtHeight(self.width()/2, self.height()/2, 0)

        if scale != self.scale:
            self.scale = scale

            # Get the new position under the mouse, find its distance from the old position,
            # and shift the centerPoint by that amount.

            newWorldPos = self.unprojectAtHeight(self.width()/2, self.height()/2, 0)
            delta = newWorldPos - worldPos
            self.centerPoint = self.centerPoint - delta

    def sizeHint(self):
        return QtCore.QSize(192, 192)

    def mousePressEvent(self, event):
        event.ignore()

    def mouseMoveEvent(self, event):
        event.ignore()

    def mouseReleaseEvent(self, event):
        event.ignore()

