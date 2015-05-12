"""
    analyze
"""
from __future__ import absolute_import
from PySide import QtGui, QtCore
import logging
import operator

from mcedit2.util.load_ui import load_ui

log = logging.getLogger(__name__)

class AnalyzeOutputDialog(QtGui.QDialog):
    def __init__(self, editorSession, blockCount, entityCount, tileEntityCount, *args, **kwargs):
        super(AnalyzeOutputDialog, self).__init__(*args, **kwargs)
        self.editorSession = editorSession
        self.blocktypes = editorSession.worldEditor.blocktypes
        
        load_ui("analyze.ui", baseinstance=self)
        
        
        blockTableView = self.blockOutputTableView
        blockCounts = sorted([(self.editorSession.worldEditor.blocktypes[ i & 0xfff, i >> 12], blockCount[i])
                         for i in blockCount.nonzero()[0]])
        self.blockArrayData = [(output[0].displayName, output[0].ID,
                                output[0].meta, output[1])
                               for n, output in enumerate(blockCounts)]
        blockArrayHeaders = ['Name', 'ID', 'Data', 'Count']
        self.setupTable(self.blockArrayData, blockArrayHeaders, blockTableView)
        
        
        entityTableView = self.entityOutputTableView
        self.entityArrayData = []
        for c in entityCount, tileEntityCount:
            for (id, count) in sorted(c.items()):
                self.entityArrayData.append((id, count,))
        entityArrayHeaders = ['Name', 'Count']
        self.setupTable(self.entityArrayData, entityArrayHeaders, entityTableView)
        
        
        self.adjustSize()
        self.exec_()       
        
    def setupTable(self, arraydata, headerdata, tableView):
        tableModel = CustomTableModel(arraydata, headerdata)
        
        tableView.setModel(tableModel)
        tableView.verticalHeader().setVisible(False)
        tableView.horizontalHeader().setStretchLastSection(True)
        tableView.resizeColumnsToContents()
        tableView.resizeRowsToContents()        
        tableView.setSortingEnabled(True)

                        
class CustomTableModel(QtCore.QAbstractTableModel):
    def __init__(self, arraydata, headerdata, parent=None, *args, **kwargs):
        QtCore.QAbstractTableModel.__init__(self, parent, *args, **kwargs)
        self.arraydata = arraydata
        self.headerdata = ['Name', 'ID', 'Data', 'Count']
        
    def rowCount(self, parent):
        return len(self.arraydata)
    
    def columnCount(self, parent):
        return len(self.arraydata[0])
    
    def data(self, index, role):
        if not index.isValid(): 
            return None
        elif role != QtCore.Qt.DisplayRole: 
            return None
        return str(self.arraydata[index.row()][index.column()])
    
    def headerData(self, col, orientation, role):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return str(self.headerdata[col])
        return None
    
    def sort(self, Ncol, order):
        """
        Sort table by given column number.
        """
        self.emit(QtCore.SIGNAL("layoutAboutToBeChanged()"))
        self.arraydata = sorted(self.arraydata, key=operator.itemgetter(Ncol))        
        if order == QtCore.Qt.DescendingOrder:
            self.arraydata.reverse()
        self.emit(QtCore.SIGNAL("layoutChanged()"))
           
        
        
        