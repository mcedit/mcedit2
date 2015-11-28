"""
    prefsdialog.py
"""
from __future__ import absolute_import, division, print_function
import logging
from PySide import QtGui

from mcedit2.ui.preferences_dialog import Ui_preferencesDialog

log = logging.getLogger(__name__)

class PrefsDialog(QtGui.QDialog, Ui_preferencesDialog):
    def __init__(self, parent):
        super(PrefsDialog, self).__init__(parent)
        self.setupUi(self)
        self.okButton.clicked.connect(self.accept)
