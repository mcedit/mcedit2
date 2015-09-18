"""
    screen
"""
from __future__ import absolute_import, division, print_function
import logging
from PySide import QtGui, QtCore

log = logging.getLogger(__name__)

def centerWidgetInScreen(widget, resize=None):
    """

    :param widget:
    :type widget:
    :param resize: Fraction of screen width/height to resize widget to
    :type resize:
    :return:
    :rtype:
    """
    desktop = QtGui.QApplication.desktop()
    parent = widget.parent()
    if parent is not None:
        screenNo = desktop.screenNumber(parent)
    else:
        screenNo = -1
    screen = desktop.availableGeometry(screenNo)
    w = screen.width()
    h = screen.height()
    r = widget.geometry()
    if resize is not None:
        w2 = w * resize * 0.5
        h2 = h * resize * 0.5
    else:
        w2 = r.width() * 0.5
        h2 = r.height() * 0.5
    r = QtCore.QRect(screen.x() + w * 0.5 - w2,
                     screen.y() + h * 0.5 - h2,
                     2 * w2,
                     2 * h2)

    widget.setGeometry(r)
