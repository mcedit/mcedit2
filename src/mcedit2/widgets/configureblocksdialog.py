"""
    configureblocksdialog.py
"""
from __future__ import absolute_import, division, print_function
import logging
from PySide import QtGui, QtCore
from mcedit2.util.load_ui import load_ui

log = logging.getLogger(__name__)

class ConfigureBlocksItemDelegate(QtGui.QStyledItemDelegate):
    pass

class ConfigureBlocksItemModel(QtCore.QAbstractItemModel):
    def columnCount(self, index):
        return 0

    def rowCount(self, index):
        return 0



class ConfigureBlocksDialog(QtGui.QDialog):
    def __init__(self):
        super(ConfigureBlocksDialog, self).__init__()
        load_ui("configure_blocks_dialog.ui", baseinstance=self)
        self.okButton.clicked.connect(self.accept)

        self.model = ConfigureBlocksItemModel()
        self.itemDelegate = ConfigureBlocksItemDelegate()

        self.blocksView.setModel(self.model)
        self.blocksView.setItemDelegate(self.itemDelegate)


