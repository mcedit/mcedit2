"""
    minimap.py
"""
from __future__ import absolute_import, division, print_function, unicode_literals
from collections import namedtuple
import logging

from OpenGL import GL

from PySide import QtCore, QtGui
import numpy

from mcedit2.rendering import compass
from mcedit2.rendering.scenegraph import scenenode, rendernode
from mcedit2.rendering.layers import Layer
from mcedit2.util.glutils import gl
from mcedit2.util.raycast import rayCastInBounds, MaxDistanceError
from mcedit2.worldview.worldview import WorldView
from mceditlib.geometry import Ray

log = logging.getLogger(__name__)

class LineSegment(namedtuple("LineSegment", "p1 p2")):
    def atHeight(self, y):
        p1 = self.p1
        p2 = self.p2
        if not (p1.y < y < p2.y or p1.y > y > p2.y):
            return None

        r = Ray.fromPoints(p1, p2)
        return r.atHeight(y)


class ViewCornersRenderNode(rendernode.RenderNode):

    #
    # Renders the intersection of a horizontal plane with the view frustum
    # We only check the four vertical segments (with respect to the view angle)
    # and the four segments pointing outward from the viewer.
    # The four outward segments are checked first, if all four intersect they are used
    # as the corners. If only two outwards segments intersect, the two furthest
    # verticals are intersected and used as the last two corners.
    # If no outward segments intersect (rare) then all four verticals are used.

    # 0: bottom left, near
    # 1: bottom left, far
    # 2: top left, near
    # 3: top left, far
    # 4: bottom right, near
    # 5: bottom right, far
    # 6: top right, near
    # 7: top right, far

    verticalIndices = [
        (1, 3),
        (5, 7),
        (0, 2),
        (4, 6),
    ]
    outwardIndices = [
        (0, 1),
        (2, 3),
        (4, 5),
        (6, 7),
    ]

    def drawSelf(self):
        if self.sceneNode.corners is None or self.sceneNode.dimension is None:
            return
        corners = self.sceneNode.corners

        outwardSegments = [LineSegment(corners[i], corners[j]) for i, j in self.outwardIndices]
        verticalSegments = [LineSegment(corners[i], corners[j]) for i, j in self.verticalIndices]
        points = []

        for segment in outwardSegments:
            p = segment.atHeight(self.sceneNode.planeHeight)
            if p is not None:
                points.append(p)

        if len(points) < 4:
            # only intersected two outward segments. check the far verticals.
            for segment in verticalSegments[:2]:
                r = Ray.fromPoints(*segment)
                points.append(r.atHeight(self.sceneNode.planeHeight))

        if len(points) < 4:
            # intersected zero outward segments!
            # rarely occurs, the near verticals are 1/10 of a block tall
            for segment in verticalSegments[2:]:
                r = Ray.fromPoints(*segment)
                points.append(r.atHeight(self.sceneNode.planeHeight))

        if len(points) < 4:
            return

        p1, p2, p3, p4 = points[:4]
        points = [p1, p2, p4, p3, p1]

        with gl.glPushAttrib(GL.GL_DEPTH_BUFFER_BIT, GL.GL_COLOR_BUFFER_BIT):
            GL.glDepthMask(False)
            GL.glEnable(GL.GL_BLEND)
            GL.glVertexPointer(3, GL.GL_FLOAT, 0, numpy.array(points).ravel())

            GL.glLineWidth(3.0)

            GL.glColor(1, 1, .1, 0.5)
            GL.glDisable(GL.GL_DEPTH_TEST)
            GL.glDrawArrays(GL.GL_LINE_STRIP, 0, len(points))


class ViewCornersNode(scenenode.Node):
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
        
    _planeHeight = None

    @property
    def planeHeight(self):
        return self._planeHeight

    @planeHeight.setter
    def planeHeight(self, value):
        self._planeHeight = value
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
        self.worldNode.addChild(self.viewCornersNode)

    def createWorldScene(self):
        scene = super(MinimapWorldView, self).createWorldScene()
        self.layerToggleGroup.setVisibleLayers([Layer.Blocks])
        return scene

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
        self.matrixState.projection = projection

        modelview = QtGui.QMatrix4x4()
        modelview.rotate(90., 1., 0., 0.)
        modelview.translate(-self.centerPoint[0], 0, -self.centerPoint[2])
        self.matrixState.modelview = modelview

    def currentViewMatrixChanged(self, currentView):
        self.viewCornersNode.corners = currentView.getViewCorners()
        try:
            targetPoint, face = rayCastInBounds(Ray(currentView.centerPoint, currentView.cameraVector), self.dimension, 100)
            if targetPoint is None:
                raise MaxDistanceError
            planeHeight = targetPoint.y
            
        except MaxDistanceError:
            planeDistance = 20
            planeHeight = (currentView.centerPoint + currentView.cameraVector * planeDistance).y

        self.viewCornersNode.planeHeight = planeHeight

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

