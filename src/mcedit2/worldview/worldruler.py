"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from PySide import QtGui, QtCore
from PySide.QtCore import Qt

log = logging.getLogger(__name__)

class WorldRuler(QtGui.QWidget):

    def __init__(self, worldView, dimName):
        QtGui.QWidget.__init__(self)
        self.scale = 1.0
        self.dimName = dimName

        self.label = QtGui.QLabel("xxx")
        #self.setLayout(Row(self.label))

        worldView.viewportMoved.connect(self.offsetChanged)
        self.offsetChanged(worldView)
        worldView.scaleChanged.connect(self.setScale)
        self.setScale(worldView.scale)

    def paintEvent(self, event):

        painter = QtGui.QPainter()
        painter.begin(self)

        painter.fillRect(event.rect(), QtCore.Qt.white)
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        w, h = self.width(), self.height()
        if h > w:
            painter.rotate(90)
            painter.translate(0, -w)
            w, h = h, w

        intervals = [1, 5, 10, 50, 100, 500, 1000, 5000]
        for bigInterval in intervals:
            if bigInterval / self.scale > 50:
                break
        smallInterval = intervals[(intervals.index(bigInterval) or 1) - 1]

        left = self.centerPoint
        first = int(left // bigInterval) * bigInterval

        def widget2world(pos):
            return int(pos * self.scale + left)

        def world2widget(pos):
            return (pos - left) / self.scale

        def tick(pos, d):
            pos = world2widget(pos)
            painter.drawLine(pos, 0, pos, h / d)

        def smallTicks(pos, d):
            for i in range(bigInterval // smallInterval):
                pos += smallInterval
                tick(pos, d)


        for pos in range(first, widget2world(w), bigInterval):
            tick(pos, 1)
            smallTicks(pos, 2)


            painter.drawText(world2widget(pos) + 2, 0, 150, h, Qt.AlignVCenter, "%s" % (pos))

        labels = ["X - EAST", "Y - UP", "Z - SOUTH"]
        labelRect = painter.boundingRect(4, 0, 150, h, Qt.AlignVCenter, labels[self.dimName])
        painter.fillRect(labelRect, QtCore.Qt.white)
        painter.drawText(4, 0, 150, h, Qt.AlignVCenter, labels[self.dimName])

        painter.end()

    def offsetChanged(self, view):
        self.centerPoint = view.centerPoint[self.dimName]

    _centerPoint = 0
    @property
    def centerPoint(self):
        return self._centerPoint

    @centerPoint.setter
    def centerPoint(self, value):
        self._centerPoint = value
        self.label.setText("%s" % value)
        self.update()

    _scale = 1.0
    @property
    def scale(self):
        return self._scale

    @scale.setter
    def scale(self, value):
        self._scale = value
        self.update()

    setScale = scale.fset


def WorldViewRulerGrid(view, rulerSize = 22):
    xruler = WorldRuler(view, 0)
    xruler.setFixedHeight(rulerSize)

    xrulerdims = {
        "x": 2,
        "y": 0,
        "z": 0,
        }
    def updatexdim():
        xruler.dimName = xrulerdims[view.axis]

    view.viewportMoved.connect(updatexdim)

    yruler = WorldRuler(view, 1)
    yruler.setFixedWidth(rulerSize)

    yrulerdims = {
        "x": 1,
        "y": 2,
        "z": 1,
        }
    def updateydim():
        yruler.dimName = yrulerdims[view.axis]

    view.viewportMoved.connect(updateydim)

    grid = QtGui.QGridLayout()
    grid.addWidget(view, 0, 0)
    grid.addWidget(yruler, 0, 1, 0)
    grid.addWidget(xruler, 1, 0, 0)
    grid.addWidget(QtGui.QWidget(), 1, 1)
    return grid
