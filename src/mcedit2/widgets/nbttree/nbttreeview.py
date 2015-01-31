"""
    nbttreewidget
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from PySide import QtGui
from PySide.QtCore import Qt

from mcedit2.widgets.nbttree.nbttreemodel import NBTFilterProxyModel
from mcedit2.util.load_ui import registerCustomWidget
from mcedit2.widgets.layout import Row


log = logging.getLogger(__name__)

@registerCustomWidget
class NBTTreeView(QtGui.QWidget):
    def __init__(self, *args, **kwargs):
        super(NBTTreeView, self).__init__(*args, **kwargs)
        self.treeView = QtGui.QTreeView()
        self.setLayout(Row(self.treeView))

    def setModel(self, model):
        self.model = model

        proxyModel = NBTFilterProxyModel(self)
        proxyModel.setSourceModel(model)
        proxyModel.setDynamicSortFilter(True)

        self.treeView.setModel(proxyModel)

        self.treeView.sortByColumn(0, Qt.AscendingOrder)
        self.treeView.expandToDepth(0)
        self.treeView.resizeColumnToContents(0)
        self.treeView.resizeColumnToContents(1)
