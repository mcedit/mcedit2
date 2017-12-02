"""
    mcedockwidget
"""
from __future__ import absolute_import, division, print_function, unicode_literals
from PySide import QtGui, QtCore
import logging

log = logging.getLogger(__name__)


class MCEDockWidget(QtGui.QDockWidget):
    wasVisible = None

    def __init__(self, *a, **kw):
        super(MCEDockWidget, self).__init__(*a, **kw)
        self._unfocusedOpacity = 1.0

    def setUnfocusedOpacity(self, value):
        self._unfocusedOpacity = value

    def animate(self, value):
        self.setWindowOpacity(value)

    def enterEvent(self, event):
        if self._unfocusedOpacity == 1.0:
           return
        self.animation = animation = QtCore.QPropertyAnimation(self, 'windowOpacity')
        animation.setDuration(100)
        animation.setStartValue(self.windowOpacity())
        animation.setEndValue(1.0)
        animation.valueChanged.connect(self.animate)
        animation.start()

    def leaveEvent(self, event):
        if self._unfocusedOpacity == 1.0:
           return
        self.animation = animation = QtCore.QPropertyAnimation(self, 'windowOpacity')
        animation.setDuration(250)
        animation.setStartValue(self.windowOpacity())
        animation.setEndValue(self._unfocusedOpacity)
        animation.valueChanged.connect(self.animate)
        animation.start()
