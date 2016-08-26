"""
    overhead.py
"""
from __future__ import absolute_import, division, print_function, unicode_literals
from PySide import QtGui
import logging
from mcedit2.worldview.worldview import WorldView
from mcedit2.worldview.viewaction import MoveViewMouseAction, ZoomWheelActions
from mcedit2.worldview import worldruler
from mceditlib.geometry import Vector

log = logging.getLogger(__name__)


def OverheadWorldViewFrame(dimension, textureAtlas, geometryCache, sharedGLWidget):
    overheadView = OverheadWorldView(dimension, textureAtlas, geometryCache, sharedGLWidget)
    rulerSize = 22
    xruler = worldruler.WorldRuler(overheadView, 0)
    xruler.setFixedHeight(rulerSize)

    yruler = worldruler.WorldRuler(overheadView, 2)
    yruler.setFixedWidth(rulerSize)

    grid = QtGui.QGridLayout()
    grid.addWidget(overheadView, 0, 0)
    grid.addWidget(yruler, 0, 1, 0)
    grid.addWidget(xruler, 1, 0, 0)
    grid.addWidget(QtGui.QWidget(), 1, 1)

    widget = QtGui.QWidget()
    widget.setLayout(grid)
    widget.worldView = overheadView
    return widget

class OverheadWorldView(WorldView):
    cameraVector = Vector(0, -1, 0)
    def __init__(self, *a, **kw):
        WorldView.__init__(self, *a, **kw)
        self.scale = 1.
        self.compassNode.yawPitch = 180, 0
        self.viewActions.extend((
            MoveViewMouseAction(),
        ))
        self.viewActions.extend(ZoomWheelActions())
        
        self.worldScene.minlod = 2

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
