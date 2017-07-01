"""
    camera.py
"""
from __future__ import absolute_import, division, print_function, unicode_literals

import logging
import math
from math import degrees, atan, tan, radians, cos, sin

import numpy
import time
from PySide.QtCore import Qt
from PySide import QtGui, QtCore
from mcedit2.rendering.workplane import WorkplaneNode

from mcedit2.util import profiler
from mcedit2.util.settings import Settings
from mcedit2.widgets.layout import Column, Row
from mcedit2.widgets.spinslider import SpinSlider
from mceditlib import faces
from mceditlib.geometry import Vector
from mceditlib.util.lazyprop import lazyprop
from mcedit2.worldview.viewcontrols import ViewControls
from mcedit2.worldview.worldview import WorldView, iterateChunks, anglesToVector
from mcedit2.worldview.viewaction import ViewAction


log = logging.getLogger(__name__)

settings = Settings().getNamespace("worldview/camera")
ViewDistanceSetting = settings.getOption("view_distance", int, 12)
MaxViewDistanceSetting = settings.getOption("max_view_distance", int, 64)

PerspectiveSetting = settings.getOption("perspective", bool, True)
StickyMouselookSetting = settings.getOption("sticky_mouselook", bool, True)


class CameraWorldViewFrame(QtGui.QWidget):
    def __init__(self, dimension, textureAtlas, geometryCache, shareGLWidget, *args, **kwargs):
        super(CameraWorldViewFrame, self).__init__(*args, **kwargs)

        self.worldView = view = CameraWorldView(dimension, textureAtlas, geometryCache, shareGLWidget)

        auxControlWidget = QtGui.QWidget()
        
        StickyMouselookSetting.connectAndCall(view.setStickyMouselook)
        
        stickyCheckbox = QtGui.QCheckBox(self.tr("Sticky Mouselook"))
        stickyCheckbox.setChecked(StickyMouselookSetting.value())
        stickyCheckbox.toggled.connect(StickyMouselookSetting.setValue)

        auxControlWidget.setLayout(Column(stickyCheckbox))

        self.viewControls = ViewControls(view, auxControlWidget)

        ViewDistanceSetting.connectAndCall(view.setViewDistance)

        viewDistanceInput = QtGui.QSpinBox(minimum=2, maximum=64, singleStep=2)
        viewDistanceInput.setValue(self.worldView.viewDistance)
        viewDistanceInput.valueChanged.connect(ViewDistanceSetting.setValue)
        
        MaxViewDistanceSetting.connectAndCall(viewDistanceInput.setMaximum)
        
        PerspectiveSetting.connectAndCall(view.setPerspective)

        perspectiveInput = QtGui.QCheckBox(self.tr("Perspective"))
        perspectiveInput.setChecked(view.perspective)
        perspectiveInput.toggled.connect(PerspectiveSetting.setValue)

        showButton = QtGui.QPushButton(self.tr("Show..."))
        showButton.setMenu(view.layerToggleGroup.menu)

        workplaneCheckbox = QtGui.QCheckBox(self.tr("Work Plane"))
        workplaneSpinSlider = SpinSlider()
        workplaneSpinSlider.setValue(64)
        workplaneSpinSlider.setMinimum(dimension.bounds.miny)
        workplaneSpinSlider.setMaximum(dimension.bounds.maxy)

        workplaneCheckbox.toggled.connect(view.toggleWorkplane)

        workplaneSpinSlider.valueChanged.connect(view.setWorkplaneLevel)

        self.setLayout(Column(Row(None,
                                  workplaneCheckbox,
                                  workplaneSpinSlider,
                                  showButton,
                                  perspectiveInput,
                                  QtGui.QLabel(self.tr("View Distance:")),
                                  viewDistanceInput,
                                  self.viewControls.getShowHideButton(), margin=0),
                              view, margin=0))




class CameraKeyControls(object):
    def __init__(self, worldView):
        """

        :param worldView:
        :type worldView: CameraWorldView
        :return:
        :rtype:
        """
        self.worldView = worldView
        self.forwardAction = self.Forward(self)
        self.backwardAction = self.Backward(self)
        self.leftAction = self.Left(self)
        self.rightAction = self.Right(self)
        self.upAction = self.Up(self)
        self.downAction = self.Down(self)
        self.viewActions = [
            self.forwardAction,
            self.backwardAction,
            self.leftAction,
            self.rightAction,
            self.upAction,
            self.downAction,
        ]
        self.forward = 0
        self.backward = 0
        self.left = 0
        self.right = 0
        self.up = 0
        self.down = 0

        # Speeds in blocks per second
        self.speed = 0
        self.maxSpeed = 50
        self.minSpeed = 16

        self.accelUp = 0.1

        self.lastTickTime = None
        self.tickInterval = 0.015
        self.tickTimer = QtCore.QTimer(interval=1000 * self.tickInterval, timeout=self.tickCamera)
        self.tickTimer.start()

    def anyKey(self):
        return any([self.forward, self.backward,
                    self.left, self.right,
                    self.up, self.down])

    def tickCamera(self):
        if self.lastTickTime is None:
            ticks = 1
            self.lastTickTime = time.time()
        else:
            t = time.time()
            tickInterval = t - self.lastTickTime
            self.lastTickTime = t
            ticks, remainder = divmod(tickInterval, self.tickInterval)
            self.lastTickTime -= remainder
            ticks = int(ticks)

        vector = self.worldView.cameraVector
        point = self.worldView.centerPoint
        up = Vector(0, 1, 0)
        left = vector.cross(up).normalize()

        for _ in range(ticks):
            if self.anyKey():
                self.speed += self.accelUp
                self.speed = max(self.speed, self.minSpeed)
            else:
                self.speed = 0
                break

            self.speed = max(0, min(self.maxSpeed, self.speed))
            speed = self.speed * self.tickInterval

            vector = vector * speed
            up = up * speed
            left = left * speed

            if self.forward:
                point += vector
            if self.backward:
                point -= vector
            if self.left:
                point -= left
            if self.right:
                point += left
            if self.up:
                point += up
            if self.down:
                point -= up

        self.worldView.centerPoint = point


    class CameraAction(ViewAction):
        def __init__(self, controls):
            super(CameraKeyControls.CameraAction, self).__init__()
            self.controls = controls

    class Forward(CameraAction):
        key = Qt.Key_W
        labelText = "Move Forward"
        settingsKey = "worldview/camera/move/forward"

        def keyPressEvent(self, event):
            self.controls.forward = 1
            self.controls.backward = 0

        def keyReleaseEvent(self, event):
            self.controls.forward = 0

    class Backward(CameraAction):
        key = Qt.Key_S
        labelText = "Move Backward"
        settingsKey = "worldview/camera/move/backward"

        def keyPressEvent(self, event):
            self.controls.backward = 1
            self.controls.forward = 0

        def keyReleaseEvent(self, event):
            self.controls.backward = 0

    class Left(CameraAction):
        key = Qt.Key_A
        labelText = "Move Left"
        settingsKey = "worldview/camera/move/left"

        def keyPressEvent(self, event):
            self.controls.left = 1
            self.controls.right = 0

        def keyReleaseEvent(self, event):
            self.controls.left = 0

    class Right(CameraAction):
        key = Qt.Key_D
        labelText = "Move Right"
        settingsKey = "worldview/camera/move/right"

        def keyPressEvent(self, event):
            self.controls.right = 1
            self.controls.left = 0

        def keyReleaseEvent(self, event):
            self.controls.right = 0

    class Up(CameraAction):
        key = Qt.Key_Space
        labelText = "Move Up"
        settingsKey = "worldview/camera/move/up"

        def keyPressEvent(self, event):
            self.controls.up = 1
            self.controls.down = 0

        def keyReleaseEvent(self, event):
            self.controls.up = 0

    class Down(CameraAction):
        key = Qt.Key_C
        labelText = "Move Down"
        settingsKey = "worldview/camera/move/down"

        def keyPressEvent(self, event):
            self.controls.down = 1
            self.controls.up = 0

        def keyReleaseEvent(self, event):
            self.controls.down = 0


class CameraWorldView(WorldView):
    def __init__(self, *a, **kw):
        self.fov = 70.0  # needed by updateMatrices called from WorldView.__init__
        self._yawPitch = -45., 25.
        self.viewDistance = 32
        
        self.stickyMouselook = False

        self.workplaneNode = WorkplaneNode()
        self.workplaneNode.visible = False

        WorldView.__init__(self, *a, **kw)
        self.compassNode.yawPitch = self._yawPitch

        stickyPanAction = CameraStickyPanMouseAction()
        panAction = CameraPanMouseAction(stickyPanAction)

        self.viewActions = [CameraMoveMouseAction(),
                            panAction, stickyPanAction]

        self.cameraControls = CameraKeyControls(self)
        self.viewActions.extend(self.cameraControls.viewActions)

        self.discardTimer = QtCore.QTimer()
        self.discardTimer.timeout.connect(self.discardChunksOutsideViewDistance)
        self.discardTimer.setInterval(1000)
        self.discardTimer.start()

        self.workplaneLevel = 0
        self.workplaneEnabled = False
        self.viewportMoved.connect(self.updateWorkplane)

        self.forceMouseCenter = False

    def updateWorkplane(self):
        distance = 40
        pos = self.centerPoint + self.cameraVector * distance
        pos = pos.intfloor()

        self.workplaneNode.position = Vector(pos[0], self.workplaneLevel, pos[2])

    def toggleWorkplane(self, enabled):
        self.workplaneNode.visible = enabled
        self.workplaneEnabled = enabled

    def setWorkplaneLevel(self, level):
        self.workplaneLevel = level
        self.updateWorkplane()
        self.update()

    def createSceneGraph(self):
        scenegraph = super(CameraWorldView, self).createSceneGraph()
        self.worldNode.addChild(self.workplaneNode)
        return scenegraph

    def augmentEvent(self, x, y, event):
        if self.forceMouseCenter:
            x = self.width() / 2
            y = self.height() / 2

        super(CameraWorldView, self).augmentEvent(x, y, event)
        if not self.workplaneEnabled:
            return

        point = event.ray.atHeight(self.workplaneLevel)
        if point != event.ray.point:
            direction = point - event.ray.point
            if direction.length() >= (event.blockPosition - event.ray.point).length():
                return

            event.blockPosition = point.intfloor()
            if direction.y >= 0:
                event.blockFace = faces.FaceDown
            else:
                event.blockFace = faces.FaceUp

    def setViewDistance(self, val):
        self.viewDistance = val
        self._chunkIter = None
        self.discardChunksOutsideViewDistance()
        self.update()
        
    def setStickyMouselook(self, val):
        self.stickyMouselook = val

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

        self.updateModelviewMatrix()

    def updateModelviewMatrix(self):
        modelview = QtGui.QMatrix4x4()
        modelview.lookAt(QtGui.QVector3D(*self.centerPoint),
                         QtGui.QVector3D(*(self.centerPoint + self.cameraVector)),
                         QtGui.QVector3D(0, 1, 0))
        self.matrixState.modelview = modelview

    def updateOrthoMatrices(self):
        w, h = self.width(), self.height()
        w *= self.scale * math.sqrt(2)
        h *= self.scale * math.sqrt(2)

        projection = QtGui.QMatrix4x4()
        projection.ortho(-w/2, w/2, -h/2, h/2, -2000, 2000)
        self.matrixState.projection = projection

    def updatePerspectiveMatrices(self):
        w, h = self.width(), self.height()
        if h == 0:
            return

        fovy = degrees(atan(w / h * tan(radians(self.fov) * 0.5)))

        projection = QtGui.QMatrix4x4()
        projection.perspective(fovy, w / h, 0.05, 2048)
        self.matrixState.projection = projection

    @lazyprop
    def cameraVector(self):
        return anglesToVector(*self.yawPitch)

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
    def discardChunksOutsideViewDistance(self):
        positions = list(self.worldScene.chunkPositions())  # xxxx
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
        self.worldScene.discardChunks(chunks)

    def recieveChunk(self, chunk):
        cx, cz = chunk.chunkPosition
        x, y, z = self.viewCenter().chunkPos()
        dx = abs(cx - x)
        dz = abs(cz - z)
        if dx > self.viewDistance or dz > self.viewDistance:
            return iter([])
        return super(CameraWorldView, self).recieveChunk(chunk)


class CameraStickyPanMouseAction(ViewAction):
    button = Qt.NoButton
    modifiers = Qt.NoModifier
    labelText = "Sticky Pan (Don't Edit)"
    hidden = True
    settingsKey = None

    sticking = False
    mouseDragStart = None

    def toggleSticky(self, event):
        view = event.view
        if not self.sticking:
            self.sticking = True
            cursor = view.cursor()
            self._oldPos = cursor.pos()
            self._oldShape = cursor.shape()
            cursor.setShape(Qt.BlankCursor)
            view.setCursor(cursor)
            #view.grabMouse()
            view.forceMouseCenter = True

            self.mouseDragStart = event.x(), event.y()

        else:
            self.sticking = False
            cursor = view.cursor()
            cursor.setPos(self._oldPos)
            cursor.setShape(self._oldShape)
            view.setCursor(cursor)
            #view.releaseMouse()
            view.forceMouseCenter = False

            self.mouseDragStart = None

    sensitivity = .15

    _last_dx = _last_dy = 0

    def mouseMoveEvent(self, event):
        if not self.sticking:
            return

        x = event.x()
        y = event.y()
        if self.mouseDragStart:
            oldx, oldy = self.mouseDragStart
            yaw, pitch = event.view.yawPitch
            dx = (oldx - x)
            dy = (oldy - y)

            yaw -= dx * self.sensitivity
            pitch -= dy * self.sensitivity

            event.view.yawPitch = yaw, pitch

            self.mouseDragStart = (x, y)

            # If the (invisible) cursor goes out of the widget's bounds,
            # move it back to the center so it doesn't stop at the screen's edge
            margin = 10

            w = event.view.width()
            h = event.view.height()
            if (x < margin
                or y < margin
                or x >= w - margin
                or y >= h - margin):

                # Disable camera movement while the cursor is repositioned
                # since QCursor.setPos emits a mouseMoved event

                self.sticking = False

                self.mouseDragStart = (w / 2, h / 2)

                pos = QtCore.QPoint(*self.mouseDragStart)
                pos = event.view.mapToGlobal(pos)
                QtGui.QCursor.setPos(pos)

                def resumeSticking():
                    self.sticking = True

                QtCore.QTimer.singleShot(0, resumeSticking)


class CameraPanMouseAction(ViewAction):
    button = Qt.RightButton
    modifiers = Qt.NoModifier
    labelText = "Turn Camera"
    settingsKey = "worldview/camera/holdToTurn"

    _stickyAction = None
    mouseDragStart = None

    _stickyThreshold = 0.25

    downTime = None

    def __init__(self, stickyAction):
        super(CameraPanMouseAction, self).__init__()
        self._stickyAction = stickyAction

    def buttonPressEvent(self, event):
        self.downTime = time.time()

        if self._stickyAction.sticking:
            return

        x = event.x()
        y = event.y()
        self.mouseDragStart = x, y

    def buttonReleaseEvent(self, event):
        if self.downTime is None:
            return

        if self._stickyAction.sticking or (event.view.stickyMouselook and  time.time() - self.downTime < self._stickyThreshold):
            self._stickyAction.toggleSticky(event)

        self.mouseDragStart = None
        self.downTime = None

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


class CameraMoveMouseAction(ViewAction):
    button = Qt.MiddleButton
    mouseDragStart = None
    labelText = "Move Camera"
    settingsKey = "worldview/camera/holdToMove"

    def buttonPressEvent(self, event):
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

    def buttonReleaseEvent(self, event):
        self.mouseDragStart = None
