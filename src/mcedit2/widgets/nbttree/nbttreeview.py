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
class NBTTreeView(QtGui.QTreeView):
    def setModel(self, model):
        proxyModel = NBTFilterProxyModel(self)
        proxyModel.setSourceModel(model)
        proxyModel.setDynamicSortFilter(True)

        super(NBTTreeView, self).setModel(proxyModel)

        self.sortByColumn(0, Qt.AscendingOrder)
        self.resizeColumnToContents(0)
        self.resizeColumnToContents(1)
