"""
    library
"""
from __future__ import absolute_import, division, print_function
import logging
import os
from PySide import QtGui, QtCore
from PySide.QtCore import Qt
from mcedit2.panels.map import MapListModel
from mcedit2.ui.library import Ui_library
from mcedit2.util.directories import getUserSchematicsDirectory
from mcedit2.util.mimeformats import MimeFormats
from mceditlib.util.lazyprop import weakrefprop

log = logging.getLogger(__name__)


class LibraryMapListModel(MapListModel):
    def flags(self, index):
        return super(LibraryMapListModel, self).flags(index) | Qt.ItemIsDragEnabled

    def mimeData(self, indices):
        mimeData = QtCore.QMimeData()
        mapItemData = ", ".join(str(index.data(self.MapIDRole)) for index in indices)
        mimeData.setData(MimeFormats.MapItem,
                         mapItemData)
        return mimeData


class LibrarySchematicsTreeModel(QtGui.QFileSystemModel):
    def columnCount(self, *args, **kwargs):
        return 1

    def mimeData(self, indices):
        mimeData = QtCore.QMimeData()
        mimeData.setUrls([QtCore.QUrl.fromLocalFile(self.filePath(index)) for index in indices])
        return mimeData

    def mimeTypes(self):
        return ["text/uri-list"]

class LibraryWidget(QtGui.QWidget, Ui_library):
    editorSession = weakrefprop()

    def __init__(self):
        super(LibraryWidget, self).__init__()
        self.setupUi(self)

        self.folderPath = getUserSchematicsDirectory()
        if not os.path.exists(self.folderPath):
            os.makedirs(self.folderPath)

        self.schematicsModel = LibrarySchematicsTreeModel()
        self.schematicsModel.setRootPath(self.folderPath)
        self.schematicsModel.setNameFilters(["*.schematic"])
        self.schematicsTreeView.setModel(self.schematicsModel)
        self.schematicsTreeView.setRootIndex(self.schematicsModel.index(self.folderPath))

        self.schematicsTreeView.doubleClicked.connect(self.itemDoubleClicked)

        self.mapListModel = None
        self.editorSession = None

        self.openLibraryButton.clicked.connect(self.openFolder)

    def openFolder(self):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(self.folderPath))

    def itemDoubleClicked(self, index):
        filename = self.schematicsModel.filePath(index)
        self.doubleClicked.emit(filename)

    doubleClicked = QtCore.Signal(unicode)

    def sessionDidChange(self, session):
        self.editorSession = session
        if session is None:
            self.mapListView.setModel(None)
            self.mapListModel = None

        else:
            self.mapListModel = LibraryMapListModel(session)
            self.mapListView.setModel(self.mapListModel)
            session.revisionChanged.connect(self.revisionDidChange)

    def revisionDidChange(self, revisionChanges):
        # xxxx inspect revisionChanges! in fact, create AnvilRevisionChanges so
        # we don't have to match `data/map_\d+.dat`!!
        session = self.editorSession
        if session:
            self.mapListModel = LibraryMapListModel(session)
            self.mapListView.setModel(self.mapListModel)
