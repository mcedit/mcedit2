"""
    fourup.py
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from PySide import QtGui, QtCore
from PySide.QtCore import Qt

from mcedit2.widgets.layout import Column, Row
from mceditlib.geometry import Ray
from mcedit2.worldview import worldruler
from mcedit2.worldview.cutaway import CutawayWorldView
from mcedit2.worldview.iso import IsoWorldView
import mceditlib
from mceditlib.geometry import Vector, Ray


log = logging.getLogger(__name__)


def FourUpWorldViewFrame(dimension, textureAtlas, geometryCache, sharedGLWidget):
    view = FourUpWorldView(dimension, textureAtlas, geometryCache, sharedGLWidget)

    widget = QtGui.QWidget()
    widget.setLayout(Column(view, margin=0))
    widget.worldView = view

    return widget


class FourUpWorldView(QtGui.QWidget):

    def __init__(self, *args, **kwargs):
        QtGui.QWidget.__init__(self)

        self.xView = CutawayWorldView(axis="x", *args, **kwargs)
        self.yView = CutawayWorldView(axis="y", *args, **kwargs)
        self.zView = CutawayWorldView(axis="z", *args, **kwargs)
        self.isoView = IsoWorldView(*args, **kwargs)
        self.allViews = [self.xView, self.yView, self.zView, self.isoView]

        self.xView.viewportMoved.connect(self.subViewMoved)
        self.yView.viewportMoved.connect(self.subViewMoved)
        self.zView.viewportMoved.connect(self.subViewMoved)
        self.isoView.viewportMoved.connect(self.subViewMoved)

        self.viewActions = []

        for view in self.allViews:
            #view.viewportMoved.connect(lambda:self.centerOnView(view))
            view.cursorMoved.connect(self.cursorMoved.emit)

        xBox = worldruler.WorldViewRulerGrid(self.xView)
        yBox = worldruler.WorldViewRulerGrid(self.yView)
        zBox = worldruler.WorldViewRulerGrid(self.zView)

        def widgetize(box):
            widget = QtGui.QWidget()
            widget.setLayout(box)
            return widget

        left = QtGui.QSplitter(Qt.Vertical)
        left.addWidget(self.isoView)
        left.addWidget(widgetize(xBox))

        right = QtGui.QSplitter(Qt.Vertical)
        right.addWidget(widgetize(yBox))
        right.addWidget(widgetize(zBox))

        box = QtGui.QSplitter()
        box.addWidget(left)
        box.addWidget(right)

        self.setLayout(Row(box))

    def requestChunk(self):
        for view in self.allViews:
            c = view.requestChunk()
            if c is not None: return c

    def wantsChunk(self, c):
        return any(view.wantsChunk(c) for view in self.allViews)

    def recieveChunk(self, chunk):
        for view in self.allViews:
            for _ in view.recieveChunk(chunk):
                yield

    def invalidateChunk(self, (cx, cz)):
        for view in self.allViews:
            view.invalidateChunk((cx, cz))

    mouseBlockPos = Vector(0, 0, 0)
    mouseRay = Ray(Vector(0, 1, 0), Vector(0, -1, 0))
    mouseBlockFace = mceditlib.faces.FaceYIncreasing

    viewportMoved = QtCore.Signal(object)
    @property
    def centerPoint(self):
        return self.xView.centerPoint

    @centerPoint.setter
    def centerPoint(self, value):
        pass


    def subViewMoved(self, view):
        blocked = [view.blockSignals(True) for view in self.allViews]
        self.centerOnPoint(view.viewCenter())
        for b, view in zip(blocked, self.allViews):
            view.blockSignals(b)

        self.viewportMoved.emit(self)

    def viewCenter(self):
        return self.xView.viewCenter()

    def centerOnPoint(self, point, distance=None):
        for view in self.allViews:
            view.centerOnPoint(point)

    def centerOnView(self, centerView):
        point = centerView.viewCenter()
        for view in self.allViews:
            if view is not centerView:
                view.centerOnPoint(point)

    cursorMoved = QtCore.Signal()
