"""
    prefswindow
"""
from __future__ import absolute_import, division, print_function, unicode_literals
from PySide import QtGui
import logging

log = logging.getLogger(__name__)

class PrefsWindow(QtGui.QWidget):
    def __init__(self, *args, **kwargs):
        super(PrefsWindow, self).__init__(*args, **kwargs)

