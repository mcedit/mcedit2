"""
    rotation_widget
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from PySide import QtGui, QtCore

from mcedit2.ui.scale_widget import Ui_scaleWidget
from mcedit2.util.resources import resourcePath

log = logging.getLogger(__name__)


class ScaleWidget(QtGui.QWidget, Ui_scaleWidget):
    def __init__(self):
        super(ScaleWidget, self).__init__()
        self.setupUi(self)

        self.xScaleSpinSlider.valueChanged.connect(self.setXScale)
        self.yScaleSpinSlider.valueChanged.connect(self.setYScale)
        self.zScaleSpinSlider.valueChanged.connect(self.setZScale)

        icon = QtGui.QIcon(resourcePath("mcedit2/assets/mcedit2/icons/mirror.png"))
        self.xFlipButton.setIcon(icon)
        self.yFlipButton.setIcon(icon)
        self.zFlipButton.setIcon(icon)

        self.xFlipButton.clicked.connect(self.xFlipClicked)
        self.yFlipButton.clicked.connect(self.yFlipClicked)
        self.zFlipButton.clicked.connect(self.zFlipClicked)

        self.xScale = self.yScale = self.zScale = 1.0

    def xFlipClicked(self):
        x, y, z = self.scale
        self.scale = -x, y, z

    def yFlipClicked(self):
        x, y, z = self.scale
        self.scale = x, -y, z

    def zFlipClicked(self):
        x, y, z = self.scale
        self.scale = x, y, -z

    scaleChanged = QtCore.Signal(object, bool)

    @property
    def scale(self):
        return self.xScale, self.yScale, self.zScale

    @scale.setter
    def scale(self, value):
        if value == self.scale:
            return
        
        xScale, yScale, zScale = value
        self.xScale, self.yScale, self.zScale = value
        
        self.xScaleSpinSlider.setValue(xScale)
        self.yScaleSpinSlider.setValue(yScale)
        self.zScaleSpinSlider.setValue(zScale)
        
        self.emitScaleChanged(False)

    def emitScaleChanged(self, live):
        log.info("emitScaleChanged %s %s", self.scale, live)
        self.scaleChanged.emit(self.scale, live)
        
    def setXScale(self, value, live):
        log.info("setXScale %s %s", value, live)
        if self.xScale == value and live:
            return

        self.xScale = value
        self.emitScaleChanged(live)

    def setYScale(self, value, live):
        if self.yScale == value and live:
            return

        self.yScale = value
        self.emitScaleChanged(live)

    def setZScale(self, value, live):
        if self.zScale == value and live:
            return

        self.zScale = value
        self.emitScaleChanged(live)
        