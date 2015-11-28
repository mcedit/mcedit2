"""
    rotation_widget
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from PySide import QtGui, QtCore

from mcedit2.ui.rotation_widget import Ui_rotationWidget
from mcedit2.util.resources import resourcePath

log = logging.getLogger(__name__)


class RotationWidget(QtGui.QWidget, Ui_rotationWidget):
    def __init__(self):
        super(RotationWidget, self).__init__()
        self.setupUi(self)

        self.xRotSlider.valueChanged.connect(self.setXRot)
        self.yRotSlider.valueChanged.connect(self.setYRot)
        self.zRotSlider.valueChanged.connect(self.setZRot)

        self.xRotSlider.sliderReleased.connect(self.sliderReleased)
        self.yRotSlider.sliderReleased.connect(self.sliderReleased)
        self.zRotSlider.sliderReleased.connect(self.sliderReleased)

        self.xRotSpinBox.valueChanged.connect(self.setXRot)
        self.yRotSpinBox.valueChanged.connect(self.setYRot)
        self.zRotSpinBox.valueChanged.connect(self.setZRot)

        icon = QtGui.QIcon(resourcePath("mcedit2/assets/mcedit2/icons/right_angle.png"))
        self.xRot90Button.setIcon(icon)
        self.yRot90Button.setIcon(icon)
        self.zRot90Button.setIcon(icon)

        self.xRot90Button.clicked.connect(self.xRot90Clicked)
        self.yRot90Button.clicked.connect(self.yRot90Clicked)
        self.zRot90Button.clicked.connect(self.zRot90Clicked)

        self.xRot = self.yRot = self.zRot = 0

    def rot90(self, angle):
        if angle < 90:
            angle = 90
        elif angle < 180:
            angle = 180
        elif angle < 270:
            angle = 270
        else:
            angle = 0

        return angle

    def xRot90Clicked(self):
        self.setXRot(self.rot90(self.xRot))

    def yRot90Clicked(self):
        self.setYRot(self.rot90(self.yRot))

    def zRot90Clicked(self):
        self.setZRot(self.rot90(self.zRot))

    rotationChanged = QtCore.Signal(object, bool)

    @property
    def rotation(self):
        return self.xRot, self.yRot, self.zRot

    @rotation.setter
    def rotation(self, value):
        if value == self.rotation:
            return
        xRot, yRot, zRot = value
        self.setXRot(xRot)
        self.setYRot(yRot)
        self.setZRot(zRot)

    def emitRotationChanged(self, live):
        self.rotationChanged.emit((self.xRot, self.yRot, self.zRot), live)

    def sliderReleased(self):
        self.emitRotationChanged(False)

    def setXRot(self, value):
        if self.xRot == value:
            return

        self.xRot = value
        self.xRotSlider.setValue(value)
        self.xRotSpinBox.setValue(value)

        self.emitRotationChanged(self.xRotSlider.isSliderDown())

    def setYRot(self, value):
        if self.yRot == value:
            return

        self.yRot = value
        self.yRotSlider.setValue(value)
        self.yRotSpinBox.setValue(value)

        self.emitRotationChanged(self.yRotSlider.isSliderDown())

    def setZRot(self, value):
        if self.zRot == value:
            return

        self.zRot = value
        self.zRotSlider.setValue(value)
        self.zRotSpinBox.setValue(value)

        self.emitRotationChanged(self.zRotSlider.isSliderDown())