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
        isDouble = kwargs.pop('double', False)
        minimum = kwargs.pop('minimum', None)
        maximum = kwargs.pop('maximum', None)
        value = kwargs.pop('value', 0)
        increment = kwargs.pop('increment', None)
        if increment is None:
            increment = 0.1 if isDouble else 1

        self.isDouble = isDouble

        super(SpinSlider, self).__init__(*args, **kwargs)
        self.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Preferred)

        if isDouble:
            self.spinBox = QtGui.QDoubleSpinBox()
            self.sliderFactor = 100.0
        else:
            self.spinBox = QtGui.QSpinBox()
            self.sliderFactor = 1.0

        self.spinBox.setSingleStep(increment)
        self.slider = QtGui.QSlider()

        self.slider.setOrientation(Qt.Horizontal)
        self._value = 0

        self._minimum = -(2 << 31)
        self._maximum = (2 << 31) - 1

        self.spinBox.valueChanged.connect(self.spinBoxChanged)
        self.slider.valueChanged.connect(self.sliderChanged)

        self.setLayout(Row(self.spinBox, self.slider, margin=0))

        if minimum is not None:
            self.setMinimum(minimum)
        if maximum is not None:
            self.setMaximum(maximum)
        if value is not None:
            self.setValue(value)

    def spinBoxChanged(self, value):
        self._value = value
        self.slider.setValue(value * self.sliderFactor)
        self.valueChanged.emit(value)

    def sliderChanged(self, value):
        value /= self.sliderFactor
        self._value = value
        self.spinBox.setValue(value)
        self.valueChanged.emit(value)

    def value(self):
        return self._value

    def setValue(self, value):
        self._value = value
        self.spinBox.setValue(value)
        self.slider.setValue(value * self.sliderFactor)

    def minimum(self):
        return self._minimum

    def setMinimum(self, value):
        self._minimum = value
        self.slider.setMinimum(value * self.sliderFactor)
        self.spinBox.setMinimum(value)

    def maximum(self):
        return self._maximum

    def setMaximum(self, value):
        self._maximum = value
        self.slider.setMaximum(value * self.sliderFactor)
        self.spinBox.setMaximum(value)


    valueChanged = QtCore.Signal(float)
