"""
    screen
"""
from __future__ import absolute_import, division, print_function
import logging
from PySide import QtGui, QtCore

log = logging.getLogger(__name__)

def centerWidgetInScreen(widget):
    screen = QtGui.QApplication.desktop().availableGeometry()
    w = screen.width()
    h = screen.height()
    margin = 0.125
    r = QtCore.QRect(screen.x() + margin * w,
                     screen.y() + margin * h,
                     w - w * 2 * margin,
                     h - h * 2 * margin)

    widget.setGeometry(r)
