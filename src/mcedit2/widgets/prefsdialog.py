"""
    prefsdialog.py
"""
from __future__ import absolute_import, division, print_function
import logging
from PySide import QtGui
from mcedit2.util.load_ui import load_ui

log = logging.getLogger(__name__)

class PrefsDialog(QtGui.QDialog):
    def __init__(self, parent):
        super(PrefsDialog, self).__init__(parent)
        load_ui("preferences_dialog.ui", baseinstance=self)
        self.okButton.clicked.connect(self.accept)
