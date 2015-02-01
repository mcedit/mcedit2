"""
    nbttreewidget
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from PySide import QtGui, QtCore
from PySide.QtCore import Qt
from mcedit2.util.resources import resourcePath

from mcedit2.widgets.nbttree.nbttreemodel import NBTFilterProxyModel
from mcedit2.util.load_ui import registerCustomWidget
from mcedit2.widgets.layout import Row, Column


log = logging.getLogger(__name__)

@registerCustomWidget
class NBTEditorWidget(QtGui.QWidget):
    def __init__(self, *args, **kwargs):
        super(NBTEditorWidget, self).__init__(*args, **kwargs)
        self.model = None
        self.treeView = QtGui.QTreeView()
        self.treeView.setAlternatingRowColors(True)
        self.treeView.clicked.connect(self.itemClicked)
        self.treeView.expanded.connect(self.itemExpanded)

        self.setLayout(Column(self.treeView))

    def setModel(self, model):
        self.model = model
        self.proxyModel = proxyModel = NBTFilterProxyModel(self)
        proxyModel.setSourceModel(model)
        proxyModel.setDynamicSortFilter(True)

        self.treeView.setModel(proxyModel)
        header = self.treeView.header()
        header.setStretchLastSection(False)
        header.setResizeMode(1, header.ResizeMode.Stretch)
        header.setResizeMode(2, header.ResizeMode.Fixed)
        header.setResizeMode(3, header.ResizeMode.Fixed)

        self.treeView.sortByColumn(0, Qt.AscendingOrder)
        self.treeView.resizeColumnToContents(0)
        self.treeView.resizeColumnToContents(1)
        self.treeView.resizeColumnToContents(2)
        self.treeView.resizeColumnToContents(3)

    def itemExpanded(self, index):
        self.treeView.resizeColumnToContents(0)


    def itemClicked(self, index):
        index = self.proxyModel.mapToSource(index)
        item = self.model.getItem(index)
        if index.column() == 2:
            if item.isList:
                self.model.insertRow(item.childCount(), index)
            elif item.isCompound:
                """ show tag type menu """
        if index.column() == 3:
            parent = self.model.parent(index)
            self.model.removeRow(index.row(), parent)
