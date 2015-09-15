"""
    mcedockwidget
"""
from __future__ import absolute_import, division, print_function, unicode_literals
from PySide import QtGui
import logging

log = logging.getLogger(__name__)


class MCEDockWidget(QtGui.QDockWidget):
    def __init__(self, *a, **kw):
        super(MCEDockWidget, self).__init__(*a, **kw)

        