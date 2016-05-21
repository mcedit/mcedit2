"""
    plugins_dialog
"""
from __future__ import absolute_import, division, print_function
import logging
from PySide import QtGui, QtCore
from PySide.QtCore import Qt
from mcedit2 import plugins
from mcedit2.dialogs.error_dialog import showErrorDialog
from mcedit2.ui.dialogs.plugins import Ui_pluginsDialog
from mcedit2.util.resources import resourcePath

log = logging.getLogger(__name__)


class PluginsTableModel(QtCore.QAbstractTableModel):
    def __init__(self, *args, **kwargs):
        super(PluginsTableModel, self).__init__(*args, **kwargs)
        self.pluginRefs = plugins.getAllPlugins()
        log.info("Plugin count: %d", len(self.pluginRefs))
        self.headerTitles = ["", "Plugin Name", "Filename"]
        self.reloadIcon = QtGui.QIcon(resourcePath("mcedit2/assets/mcedit2/reload.png"))

    def rowCount(self, index):
        if index.isValid():
            return 0

        return len(self.pluginRefs)

    def columnCount(self, index):
        return len(self.headerTitles)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Vertical:
            return None

        if role == Qt.DisplayRole:
            return self.headerTitles[section]

    def data(self, index, role=Qt.DisplayRole):
        row = index.row()
        if row >= len(self.pluginRefs):
            return None

        pluginRef = self.pluginRefs[row]

        column = index.column()
        if role == Qt.DisplayRole:
            if column == 1:
                return pluginRef.displayName
            if column == 2:
                return pluginRef.filename
            return ""

        if role == Qt.DecorationRole:
            if column == 0:
                return self.reloadIcon

        if role == Qt.CheckStateRole:
            if column == 1:
                return Qt.Checked if pluginRef.enabled else Qt.Unchecked

        return None

    def setData(self, index, value, role=Qt.DisplayRole):
        if role != Qt.CheckStateRole:
            return
        if index.column() != 1:
            return

        row = index.row()
        if row >= len(self.pluginRefs):
            return False

        value = value == Qt.Checked

        pluginRef = self.pluginRefs[row]
        pluginRef.enabled = value

        if value:
            if not pluginRef.load():
                showErrorDialog("%s while loading plugin \"%s\"" % (pluginRef.loadError[0].__name__, pluginRef.displayName), pluginRef.loadError, False)

        else:
            if not pluginRef.unload():
                showErrorDialog("%s while unloading plugin \"%s\"" % (pluginRef.unloadError[0].__name__, pluginRef.displayName), pluginRef.unloadError, False)

        self.dataChanged.emit(index, index)
        return True

    def flags(self, index):
        column = index.column()
        if column == 1:
            return Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable
        else:
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable


class PluginsDialog(QtGui.QDialog, Ui_pluginsDialog):
    def __init__(self, *args, **kwargs):
        super(PluginsDialog, self).__init__(*args, **kwargs)
        self.setupUi(self)

    def exec_(self):
        self.model = PluginsTableModel()
        self.tableView.setModel(self.model)
        self.tableView.resizeColumnsToContents()
        super(PluginsDialog, self).exec_()
