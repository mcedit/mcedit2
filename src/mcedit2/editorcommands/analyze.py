"""
    analyze
"""
from __future__ import absolute_import
from PySide import QtGui, QtCore
import logging

from mcedit2.util.load_ui import load_ui

log = logging.getLogger(__name__)

class AnalyzeOutputDialog(QtGui.QDialog):
    def __init__(self, editorSession, blockCount, entityCount, tileEntityCount, *args, **kwargs):
        super(AnalyzeOutputDialog, self).__init__(*args, **kwargs)
        self.editorSession = editorSession
        self.blocktypes = editorSession.worldEditor.blocktypes
        
        load_ui("analyze.ui", baseinstance=self)
        blockTable = self.blockOutputTable
        self.setupBlockTable(blockCount, blockTable)
        
        entityTable = self.entityOutputTable
        self.setupEntityTable(entityCount, tileEntityCount, entityTable)

        self.sizeHint()
        self.exec_()



    def setupBlockTable(self, blockCount, table):
        blockCounts = sorted([(self.editorSession.worldEditor.blocktypes[ i & 0xfff, i >> 12], blockCount[i])
                         for i in blockCount.nonzero()[0]])
        table.setRowCount(len(blockCounts))
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(['Name', 'ID', 'Data', 'Count'])

        for n, output in enumerate(blockCounts):
            nameItem = QtGui.QTableWidgetItem(output[0].displayName)
            idItem = QtGui.QTableWidgetItem(str(output[0].ID))
            dataItem = QtGui.QTableWidgetItem(str(output[0].meta))
            countItem = QtGui.QTableWidgetItem(str(output[1]))
            table.setItem(n, 0, nameItem)
            table.setItem(n, 1, idItem)
            table.setItem(n, 2, dataItem)
            table.setItem(n, 3, countItem)
            
        table.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        
    def setupEntityTable(self, entityCount, tileEntityCount, table):
        table.setRowCount(len(entityCount.items())+len(tileEntityCount.items()))
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(['Name', 'Count'])
        
        for c in (entityCount, tileEntityCount):
            for n, (id, count) in enumerate(sorted(c.iteritems())):
                idItem = QtGui.QTableWidgetItem(str(id))
                countItem = QtGui.QTableWidgetItem(str(count))
                table.setItem(n, 0, idItem)
                table.setItem(n, 1, countItem)
        
        table.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)