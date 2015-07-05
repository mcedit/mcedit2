"""
    map
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from PySide import QtGui, QtCore
from PySide.QtCore import Qt
import numpy
from mcedit2.util.load_ui import load_ui
from mcedit2.util.screen import centerWidgetInScreen

log = logging.getLogger(__name__)


class MapListModel(QtCore.QAbstractListModel):
    def __init__(self, editorSession):
        super(MapListModel, self).__init__()
        self.editorSession = editorSession
        self.mapIDs = list(self.editorSession.worldEditor.listMaps())

    def rowCount(self, index):
        return len(self.mapIDs)

    def data(self, index, role=Qt.DisplayRole):
        row = index.row()
        if not 0 <= row < len(self.mapIDs):
            return None

        mapID = self.mapIDs[row]
        if role == Qt.DisplayRole:
            return "Map #%s" % mapID
        if role == Qt.DecorationRole:
            map = self.editorSession.worldEditor.getMap(mapID)
            colorsRGBA = map.getColorsAsRGBA()
            colorsBGRA = numpy.ascontiguousarray(numpy.roll(colorsRGBA, 1, -1)[..., ::-1])
            image = QtGui.QImage(colorsBGRA, map.width, map.height, QtGui.QImage.Format_ARGB32)
            return image

class MapPanel(QtGui.QWidget):
    def __init__(self, editorSession):
        """

        :type editorSession: mcedit2.editorsession.EditorSession
        :rtype: MapPanel
        """
        super(MapPanel, self).__init__(QtGui.qApp.mainWindow, f=Qt.Tool)

        self.editorSession = editorSession
        self.selectedUUID = None

        load_ui("panels/map.ui", baseinstance=self)

        #icon = QtGui.QIcon(resourcePath("mcedit2/assets/mcedit2/icons/edit_maps.png"))
        action = QtGui.QAction("Edit Maps", self)
        action.setCheckable(True)
        action.triggered.connect(self.toggleView)
        self._toggleViewAction = action

        self.mapListModel = MapListModel(self.editorSession)

        self.mapListView.setModel(self.mapListModel)

        centerWidgetInScreen(self)

    def closeEvent(self, event):
        self.toggleView()

    def toggleViewAction(self):
        return self._toggleViewAction

    def toggleView(self):
        if self.isHidden():
            self.show()
            self._toggleViewAction.setChecked(True)
        else:
            self.hide()
            self._toggleViewAction.setChecked(False)
