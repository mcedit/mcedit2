"""
    library
"""
from __future__ import absolute_import, division, print_function
import logging
import os
from PySide import QtGui, QtCore
from mcedit2.util.directories import getUserFilesDirectory
from mcedit2.widgets.layout import Column

log = logging.getLogger(__name__)

class LibraryTreeModel(QtGui.QFileSystemModel):
    def columnCount(self, *args, **kwargs):
        return 1

class LibraryWidget(QtGui.QWidget):
    def __init__(self):
        super(LibraryWidget, self).__init__()

        self.folderPath = os.path.join(getUserFilesDirectory(), "schematics")
        if not os.path.exists(self.folderPath):
            os.makedirs(self.folderPath)

        self.treeView = QtGui.QTreeView()
        self.model = LibraryTreeModel()
        self.model.setRootPath(self.folderPath)
        self.treeView.setModel(self.model)
        self.treeView.setRootIndex(self.model.index(self.folderPath))

        self.treeView.doubleClicked.connect(self.itemDoubleClicked)

        openLibraryButton = QtGui.QPushButton("Open Schematics Folder")
        openLibraryButton.clicked.connect(self.openFolder)

        self.setLayout(Column(self.treeView, openLibraryButton))

    def openFolder(self):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(self.folderPath))

    def itemDoubleClicked(self, index):
        filename = self.model.filePath(index)
        self.doubleClicked.emit(filename)

    doubleClicked = QtCore.Signal(str)
