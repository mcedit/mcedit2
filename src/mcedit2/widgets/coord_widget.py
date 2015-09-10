"""
    coord_widget
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from PySide import QtGui, QtCore
from mcedit2.util.load_ui import load_ui
from mceditlib.geometry import Vector
from mceditlib.selection import BoundingBox

log = logging.getLogger(__name__)


class CoordinateWidget(QtGui.QWidget):
    def __init__(self, *args, **kwargs):
        super(CoordinateWidget, self).__init__(*args, **kwargs)
        load_ui("coord_widget.ui", baseinstance=self)

        self.xInput.valueChanged.connect(self.setX)
        self.yInput.valueChanged.connect(self.setY)
        self.zInput.valueChanged.connect(self.setZ)

    pointChanged = QtCore.Signal(BoundingBox)

    _point = Vector(0, 0, 0)

    @property
    def point(self):
        return self._point

    @point.setter
    def point(self, point):
        self.setEnabled(point is not None)
        self._point = point
        if point is not None:
            x, y, z = point
            self.xInput.setValue(x)
            self.yInput.setValue(y)
            self.zInput.setValue(z)

        self.pointChanged.emit(point)

    def setX(self, value):
        x, y, z = self.point
        self.point = Vector(value, y, z)

    def setY(self, value):
        x, y, z = self.point
        self.point = Vector(x, value, z)

    def setZ(self, value):
        x, y, z = self.point
        self.point = Vector(x, y, value)