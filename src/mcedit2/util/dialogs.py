"""
    dialogs
"""
from __future__ import absolute_import, division, print_function
from PySide import QtGui
import logging

log = logging.getLogger(__name__)

def NotImplementedYet():
    QtGui.QMessageBox.information(None, "Not Implemented Yet!", "Not Implemented Yet!")
