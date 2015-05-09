"""
    spinslider
"""
from __future__ import absolute_import, division, print_function
import logging
from PySide import QtGui, QtCore
from PySide.QtCore import Qt
from mcedit2.util.load_ui import registerCustomWidget
from mcedit2.widgets.layout import Row

log = logging.getLogger(__name__)


@registerCustomWidget
class SpinSlider(QtGui.QWidget):
    def __init__(self, *args, **kwargs):
        super(SpinSlider, self).__init__(*args, **kwargs)
        self.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Preferred)

        self.spinBox = QtGui.QSpinBox()
        self.slider = QtGui.QSlider()
        self.slider.setOrientation(Qt.Horizontal)
        self._value = 0

        self._minimum = -(2 << 31)
        self._maximum = (2 << 31) - 1

        self.spinBox.valueChanged.connect(self.spinBoxChanged)
        self.slider.valueChanged.connect(self.sliderChanged)

        self.setLayout(Row(self.spinBox, self.slider, margin=0))

    def spinBoxChanged(self, value):
        self._value = value
        self.slider.setValue(value)
        self.valueChanged.emit(value)

    def sliderChanged(self, value):
        self._value = value
        self.spinBox.setValue(value)
        self.valueChanged.emit(value)

    def value(self):
        return self._value

    def setValue(self, value):
        self._value = value
        self.spinBox.setValue(value)
        self.slider.setValue(value)

    def minimum(self):
        return self._minimum

    def setMinimum(self, value):
        self._minimum = value
        self.slider.setMinimum(value)
        self.spinBox.setMinimum(value)

    def maximum(self):
        return self._maximum

    def setMaximum(self, value):
        self._maximum = value
        self.slider.setMaximum(value)
        self.spinBox.setMaximum(value)


    valueChanged = QtCore.Signal(float)
