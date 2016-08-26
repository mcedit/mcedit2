"""
    prefsdialog
"""
from __future__ import absolute_import, division, print_function
import logging
from PySide import QtCore

from PySide import QtGui

from mcedit2.ui.dialogs.preferences import Ui_preferencesDialog

log = logging.getLogger(__name__)

from .camera import CameraPrefs

class PrefsDialog(QtGui.QDialog, Ui_preferencesDialog):
    def __init__(self, parent):
        super(PrefsDialog, self).__init__(parent)
        self.setupUi(self)
        self.okButton.clicked.connect(self.accept)
        
        self.frames = [
            CameraPrefs()
        ]
        
        for i, frame in enumerate(self.frames):
            item = QtGui.QListWidgetItem(frame.labelText)
            item.setData(QtCore.Qt.UserRole, i)
            self.categoryList.addItem(item)
            
        self.categoryList.itemClicked.connect(self.itemWasClicked)
        
        self.frameStack.addWidget(self.frames[0])
        
    def itemWasClicked(self, item):
        idx = item.data(QtCore.Qt.UserRole)
        
        self.frameStack.removeWidget(self.frameStack.widget(0))
        self.frameStack.addWidget(self.frames[idx])
