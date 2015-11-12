"""
    iso.py
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import math
from PySide import QtGui
from PySide.QtCore import Qt
from mcedit2.widgets.layout import Row, Column
from mcedit2.worldview.worldview import WorldView, iterateChunks, anglesToVector
from mcedit2.worldview.viewaction import ViewAction, MoveViewMouseAction, ZoomWheelAction
from mceditlib.geometry import Ray

log = logging.getLogger(__name__)
#
#def ScaleSlider(view):
#
#    scaleSlider = QtGui.QSlider(QtCore.Qt.Horizontal)
#    log2 = math.log(2)
#    scaleMinExp = math.log(view.minScale)/log2
#    scaleMaxExp = math.log(view.maxScale)/log2
#
#    scaleSlider.setMinimum(scaleMinExp)
#    scaleSlider.setMaximum(scaleMaxExp)
#
#    scaleLabel = QtGui.QLabel()
#
#    def _scaleSliderChanged(value):
#        view.scale = 2 ** value
#
#    scaleSlider.valueChanged.connect(_scaleSliderChanged)
#
#    def _scaleChanged(value):
#        if value >= 1.0:
#            scaleLabel.setText("%d blocks/pixel" % value)
#        else:
#            scaleLabel.setText("%d pixels/block" % (1.0 / value))
#        scaleSlider.setValue(math.log(value)/log2)
#
#    view.scaleChanged.connect(_scaleChanged)
#    _scaleChanged(view.scale)
#
#    widget = QtGui.QWidget()
#    widget.setLayout(Row(scaleLabel, scaleSlider))
#    return widget

def IsoWorldViewFrame(world, geometryCache, resourceLoader, sharedGLWidget):
    isoView = IsoWorldView(world, geometryCache, resourceLoader, sharedGLWidget)

    widget = QtGui.QWidget()
    widget.setLayout(
        Column(
            Row((None, 1),
                #ScaleSlider(isoView),
                ),
            isoView,
            ))
    widget.worldView = isoView

    return widget


class IsoWorldView(WorldView):

    def __init__(self, *a, **kw):
        self.xrot = math.degrees(math.atan(1/math.sqrt(2)))
        self.yrot = 45.
        self.hoverHeight = 1024
        super(IsoWorldView, self).__init__(*a, **kw)
        self.compassNode.yawPitch = self.yrot, 90 - self.xrot
        self.viewActions.extend((
            MoveViewMouseAction(),
            ZoomWheelAction(),
            RotateMouseAction()
        ))

    def cameraVector(self):
        return anglesToVector(self.yrot, self.xrot)

    def centerOnPoint(self, pos, distance=None):
        #self.rotateView(45., math.degrees(math.atan(1/math.sqrt(2))))
        vec = self.cameraVector()
        ray = Ray(pos, -vec)
        newPos = ray.atHeight(self.hoverHeight)

        log.info("Iso: centering on %s (moving to %s)", pos, newPos)
        self.centerPoint = newPos

    def makeChunkIter(self):
        bottomRight = self.unprojectAtHeight(self.width(), self.height(), self.dimension.bounds.maxy)
        topLeft = self.unprojectAtHeight(0, 0, self.dimension.bounds.miny)
        center = self.unprojectAtHeight(self.width()/2, self.height()/2, 0)  # xxx
        # self.dimension.bounds.miny + self.dimension.bounds.height / 4


        br = bottomRight.chunkPos()
        tl = topLeft.chunkPos()

        w = abs(br[0] - tl[0])
        h = abs(br[1] - tl[1])

        d = max(w, h) + 2
        return iterateChunks(center[0], center[2], d / 2)

    def rotateView(self, yrot, xrot):
        self.yrot = yrot
        self.xrot = max(-90, min(90, xrot))
        #center = self.viewCenter()
        self._updateMatrices()
        #self.center(center)
        self.compassNode.yawPitch = self.yrot, 90 - self.xrot
        self.viewportMoved.emit(self)

    def updateMatrices(self):
        w, h = self.width(), self.height()
        w *= self.scale * math.sqrt(2)
        h *= self.scale * math.sqrt(2)

        projection = QtGui.QMatrix4x4()
        projection.ortho(-w/2, w/2, -h/2, h/2, -2000, 8000)
        self.matrixState.projection = projection

        modelview = QtGui.QMatrix4x4()
        #modelview.rotate(self.xrot, 1., 0., 0.)
        #modelview.rotate(self.yrot, 0., 1., 0.)
        #modelview.translate(-self.centerPoint[0], -self.centerPoint[1], -self.centerPoint[2])
        modelview.lookAt(QtGui.QVector3D(*(self.centerPoint - self.cameraVector() * 100)),
                         QtGui.QVector3D(*self.centerPoint),
                         QtGui.QVector3D(0, 1, 0),
                         )
        self.matrixState.modelview = modelview

class RotateMouseAction(ViewAction):
    button = Qt.MiddleButton
    startx = starty = None

    def mousePressEvent(self, event):
        self.startx = event.x()
        self.starty = event.y()

        self.yrot = event.view.yrot
        self.xrot = event.view.xrot
        self.center = event.view.viewCenter()

    def mouseMoveEvent(self, event):
        if self.startx is None:
            return
        xdelta = event.x() - self.startx
        ydelta = event.y() - self.starty
        self.startx = event.x()
        self.starty = event.y()
        event.view.rotateView(self.yrot + xdelta, self.xrot + ydelta)
        event.view.centerOnPoint(self.center)
        self.yrot = event.view.yrot
        self.xrot = event.view.xrot

    def mouseReleaseEvent(self, event):
        self.startx = None
        self.starty = None
