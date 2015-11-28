"""
    coord_widget
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from PySide import QtGui, QtCore

from mcedit2.ui.widgets.coord_widget import Ui_coordWidget
from mceditlib.geometry import Vector
from mceditlib.selection import BoundingBox

log = logging.getLogger(__name__)


class CoordinateWidget(QtGui.QWidget, Ui_coordWidget):
    def __init__(self, *args, **kwargs):
        super(CoordinateWidget, self).__init__(*args, **kwargs)
        self.setupUi(self)

        self.xInput.valueChanged.connect(self.setX)
        self.yInput.valueChanged.connect(self.setY)
        self.zInput.valueChanged.connect(self.setZ)

        self.relativeCheckBox.toggled.connect(self.relativeToggled)

    pointChanged = QtCore.Signal(BoundingBox)

    _point = Vector(0, 0, 0)
    _origin = Vector(0, 0, 0)
    _relative = False

    def relativeToggled(self, enabled):
        self._relative = enabled
        self.updateInputs()

    def updateInputs(self):
        if self._relative:
            displayed = self._point - self._origin
        else:
            displayed = self._point

        x, y, z = displayed
        self.xInput.setValue(x)
        self.yInput.setValue(y)
        self.zInput.setValue(z)

    @property
    def origin(self):
        return self._origin

    @origin.setter
    def origin(self, value):
        value = Vector(*value)
        if value != self._origin:
            self._origin = value

    @property
    def point(self):
        return self._point

    @point.setter
    def point(self, point):
        self.setEnabled(point is not None)
        point = Vector(*point)
        if self._point != point:
            self._point = point
            if point is not None:
                self.updateInputs()

            self.pointChanged.emit(point)

    def setX(self, value):
        self.setCoord(value, 0)

    def setY(self, value):
        self.setCoord(value, 1)

    def setZ(self, value):
        self.setCoord(value, 2)

    def setCoord(self, value, index):
        old = self.point
        if self._relative:
            old = old - self._origin
        new = list(old)
        new[index] = value
        new = Vector(*new)
        if self._relative:
            new = new + self._origin

        self.point = new
