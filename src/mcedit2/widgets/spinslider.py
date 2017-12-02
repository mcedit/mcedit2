"""
    spinslider
"""
from __future__ import absolute_import, division, print_function
import logging
from contextlib import contextmanager

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
        
        self._changing = False
        
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
        self.slider.sliderReleased.connect(self.sliderReleased)

        self.setLayout(Row(self.spinBox, self.slider, margin=0))
        
        if minimum is not None:
            self.setMinimum(minimum)
        if maximum is not None:
            self.setMaximum(maximum)
        if value is not None:
            self.setValue(value)
            
    @contextmanager
    def suppressChanges(self):
        try:
            self._changing = True
            yield
        finally:
            self._changing = False
        
    def toSlider(self, value):
        return value * self.sliderFactor
        
    def fromSlider(self, value):
        result = value / self.sliderFactor
        if self.isDouble:
            return result

        return int(result)
        
    def spinBoxChanged(self, value):
        if self._changing:
            return
        
        self._value = value
        
        with self.suppressChanges():
            self.slider.setValue(self.toSlider(value))
            
        self.valueChanged.emit(value, False)

    def sliderChanged(self, value):
        if self._changing:
            return
        
        value = self.fromSlider(value)
        self._value = value
        
        with self.suppressChanges():
            self.spinBox.setValue(value)
            
        self.valueChanged.emit(value, self.slider.isSliderDown())
    
    def sliderReleased(self):
        self.valueChanged.emit(self._value, False)

    def value(self):
        return self._value

    def setValue(self, value):
        self._value = value
        self.spinBox.setValue(value)
        # if value is not None:
        #     value *= self.sliderFactor
        # self.slider.setValue(value)

    def minimum(self):
        return self._minimum

    def setMinimum(self, value):
        self._minimum = value
        self.spinBox.setMinimum(value)
        if value is not None:
            value = self.toSlider(value)
        self.slider.setMinimum(value)

    def maximum(self):
        return self._maximum

    def setMaximum(self, value):
        self._maximum = value
        self.spinBox.setMaximum(value)
        if value is not None:
            value = self.toSlider(value)
        self.slider.setMaximum(value)

    valueChanged = QtCore.Signal(float, bool)

@registerCustomWidget
class DoubleSpinSlider(SpinSlider):
    def __init__(self, *a, **kw):
        kw['double'] = True
        super(DoubleSpinSlider, self).__init__(*a, **kw)
        
@registerCustomWidget
class ScaleSpinSlider(DoubleSpinSlider):
    def __init__(self, *a, **kw):
        kw['minimum'] = -20
        kw['maximum'] = 20
        kw['value'] = 1
        
        super(ScaleSpinSlider, self).__init__(*a, **kw)
        
    def toSlider(self, value):
        if value < -1.0:
            return (value * 50) - 1000
        if value > 1.0:
            return (value * 50) + 1000
        
        return value * 1000
        
    def fromSlider(self, value):
        if value < -1000:
            return ((value + 1000) * 2) / 100.
        if value > 1000:
            return ((value - 1000) * 2) / 100.
        return value / 1000.