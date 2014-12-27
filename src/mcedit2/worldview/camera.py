"""
    camera.py
"""
from __future__ import absolute_import, division, print_function, unicode_literals

import logging
import math
from math import degrees, atan, tan, radians, cos, sin

import numpy

from PySide.QtCore import Qt
from PySide import QtGui, QtCore
from mcedit2.util import profiler

from mcedit2.widgets.layout import Column, Row
from mcedit2.util.lazyprop import lazyprop
from mcedit2.worldview.viewcontrols import ViewControls
from mcedit2.worldview.worldview import WorldView, iterateChunks, ViewMouseAction
from mceditlib.geometry import Vector

log = logging.getLogger(__name__)


class CameraWorldViewFrame(QtGui.QWidget):
    def __init__(self, dimension, geometryCache, resourceLoader, shareGLWidget, *args, **kwargs):
        super(CameraWorldViewFrame, self).__init__(*args, **kwargs)

        self.worldView = view = CameraWorldView(dimension, geometryCache, resourceLoader, shareGLWidget)

        self.viewControls = ViewControls(view)

        viewDistanceInput = QtGui.QSpinBox(minimum=2, maximum=24, singleStep=2)
        viewDistanceInput.setValue(self.worldView.viewDistance)
        viewDistanceInput.valueChanged.connect(view.setViewDistance)

        perspectiveInput = QtGui.QCheckBox("Perspective")
        perspectiveInput.toggle()
        perspectiveInput.toggled.connect(view.setPerspective)

        self.setLayout(Column(Row((QtGui.QWidget(), 1),
                                  perspectiveInput,
                                  QtGui.QLabel("View Distance:"),
                                  viewDistanceInput,
                                  self.viewControls.getShowHideButton(), margin=0),
                              view, margin=0))




class CameraWorldView(WorldView):
    def __init__(self, *a, **kw):
        self.fov = 70.0  # needed by updateMatrices called from WorldView.__init__
        self._yawPitch = -45., 25.
        WorldView.__init__(self, *a, **kw)
        self.compassNode.yawPitch = self._yawPitch
        self.viewDistance = 16
        self.mouseActions = [CameraMoveMouseAction(),
                             CameraPanMouseAction(),
                             CameraElevateMouseAction()]

        self.discardTimer = QtCore.QTimer()
        self.discardTimer.timeout.connect(self.discardChunksOutsideViewDistance)
        self.discardTimer.setInterval(1000)
        self.discardTimer.start()

    def setViewDistance(self, val):
        self.viewDistance = val

    def centerOnPoint(self, pos, distance=20):
        awayVector = self.cameraVector * -distance
        newPos = awayVector + pos
        log.info("Camera: centering on %s (moving to %s)", pos, newPos)
        self.centerPoint = newPos

    perspective = True

    def setPerspective(self, val):
        if val != self.perspective:
            self.perspective = val
            self._updateMatrices()

    def updateMatrices(self):
        if self.perspective:
            self.updatePerspectiveMatrices()
        else:
            self.updateOrthoMatrices()

        modelview = QtGui.QMatrix4x4()
        modelview.lookAt(QtGui.QVector3D(*self.centerPoint),
                         QtGui.QVector3D(*(self.centerPoint + self.cameraVector)),
                         QtGui.QVector3D(0, 1, 0))
        self.matrixNode.modelview = modelview

    def updateOrthoMatrices(self):
        w, h = self.width(), self.height()
        w *= self.scale * math.sqrt(2)
        h *= self.scale * math.sqrt(2)

        projection = QtGui.QMatrix4x4()
        projection.ortho(-w/2, w/2, -h/2, h/2, -2000, 2000)
        self.matrixNode.projection = projection

    def updatePerspectiveMatrices(self):
        w, h = self.width(), self.height()
        if h == 0:
            return

        fovy = degrees(atan(w / h * tan(radians(self.fov) * 0.5)))

        projection = QtGui.QMatrix4x4()
        projection.perspective(fovy, w / h, 1, 1000)
        self.matrixNode.projection = projection

    @lazyprop
    def cameraVector(self):
        return self._anglesToVector(*self.yawPitch)


    def makeChunkIter(self):
        radius = self.viewDistance

        # If the focal point of the camera is less than twice the view distance away, load
        # chunks around that point. Otherwise, load chunks around the camera's position.
        vc = self.viewCenter()
        if max(abs(a) for a in (vc - self.centerPoint)) < radius * 2 * 16:
            x, y, z = vc
        else:
            x, y, z = self.centerPoint

        return iterateChunks(x, z, radius)

    @property
    def yawPitch(self):
        return self._yawPitch

    @yawPitch.setter
    def yawPitch(self, yawPitch):
        yaw, pitch = yawPitch
        yaw %= 360
        pitch = max(-89, min(89, pitch))
        self._yawPitch = yaw, pitch
        del self.cameraVector
        self.resetLoadOrder()
        self._updateMatrices()

        self.compassNode.yawPitch = yaw, min(90 - max(pitch, 0), 45)
        self.viewportMoved.emit(self)

    @profiler.function("discardChunks")
    def discardChunksOutsideViewDistance(self, worldScene=None):
        if worldScene is None:
            worldScene = self.worldScene

        positions = list(worldScene.chunkPositions())  # xxxx
        if not len(positions):
            return

        viewDistance = int(self.viewDistance * 1.4) # fudge it a little. Discard chunks in a wider area than they are loaded.

        def chunkPosition((x, y, z)):
            return int(math.floor(x)) >> 4, int(math.floor(z)) >> 4

        chunks = numpy.fromiter(positions, dtype='i,i', count=len(positions))
        chunks.dtype = 'int32'
        chunks.shape = len(positions), 2

        def outsideBox(cx, cz, distance):
            ox = cx - distance
            oz = cz - distance
            size = distance * 2
            outsideChunks = chunks[:, 0] < ox - 1
            outsideChunks |= chunks[:, 0] > ox + size
            outsideChunks |= chunks[:, 1] < oz - 1
            outsideChunks |= chunks[:, 1] > oz + size
            return outsideChunks

        cx, cz = chunkPosition(self.centerPoint)
        outsideCenter = outsideBox(cx, cz, viewDistance)

        cx, cz = chunkPosition(self.viewCenter())
        outsideFocus = outsideBox(cx, cz, viewDistance)

        chunks = chunks[outsideCenter & outsideFocus]

        log.debug("Discarding %d chunks...", len(chunks))
        worldScene.discardChunks(chunks)


class CameraElevateMouseAction(ViewMouseAction):
    labelText = "Wheel Controls Camera Elevation"

    def wheelEvent(self, event):
        d = event.delta()
        event.view.centerPoint += (0, d / 32, 0)


class CameraPanMouseAction(ViewMouseAction):
    button = Qt.RightButton
    mouseDragStart = None
    modifiers = Qt.NoModifier
    labelText = "Turn Camera"

    def mousePressEvent(self, event):
        x = event.x()
        y = event.y()
        self.mouseDragStart = x, y

    sensitivity = .15

    def mouseMoveEvent(self, event):
        x = event.x()
        y = event.y()
        if self.mouseDragStart:
            oldx, oldy = self.mouseDragStart
            yaw, pitch = event.view.yawPitch

            yaw -= (oldx - x) * self.sensitivity
            pitch -= (oldy - y) * self.sensitivity

            event.view.yawPitch = yaw, pitch

            self.mouseDragStart = (x, y)


    def mouseReleaseEvent(self, event):
        self.mouseDragStart = None


class CameraMoveMouseAction(ViewMouseAction):
    button = Qt.MiddleButton
    mouseDragStart = None
    labelText = "Move Camera"

    def mousePressEvent(self, event):
        x = event.x()
        y = event.y()
        self.mouseDragStart = x, y

    sensitivity = .15

    def mouseMoveEvent(self, event):
        x = event.x()
        y = event.y()
        if self.mouseDragStart:
            oldx, oldy = self.mouseDragStart
            yaw, pitch = event.view.yawPitch

            mx, mz = oldx - x, oldy - y
            mx = -mx

            yaw = radians(yaw)
            dx = mx * cos(yaw) + mz * sin(yaw)
            dz = -mz * cos(yaw) + mx * sin(yaw)

            event.view.centerPoint += (dx / 4, 0, dz / 4)

            self.mouseDragStart = (x, y)


    def mouseReleaseEvent(self, event):
        self.mouseDragStart = None
