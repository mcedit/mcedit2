"""
    analyze
"""
from __future__ import absolute_import
from PySide import QtGui, QtCore
import logging
import operator
import arrow

from mcedit2.ui.analyze import Ui_analyzeDialog
from mcedit2.util.directories import getUserFilesDirectory

log = logging.getLogger(__name__)


class AnalyzeOutputDialog(QtGui.QDialog, Ui_analyzeDialog):
    def __init__(self, editorSession, blockCount, entityCount, tileEntityCount, worldName, parent=None, *args,
                 **kwargs):
        super(AnalyzeOutputDialog, self).__init__(parent, *args, **kwargs)
        self.setupUi(self)

        self.editorSession = editorSession
        self.blocktypes = editorSession.worldEditor.blocktypes
        self.worldName = worldName

        self.setupTables(blockCount, entityCount, tileEntityCount)
        self.txtButton.clicked.connect(self.export_txt)
        self.csvButton.clicked.connect(self.export_csv)

    def setupTables(self, blockCount, entityCount, tileEntityCount):
        blockTableView = self.blockOutputTableView
        blockCounts = sorted([(self.editorSession.worldEditor.blocktypes[i & 0xfff, i >> 12], blockCount[i])
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

    def setupTable(self, arraydata, headerdata, tableView):
        tableModel = CustomTableModel(arraydata, headerdata)

        tableView.setModel(tableModel)
        tableView.verticalHeader().setVisible(False)
        tableView.horizontalHeader().setStretchLastSection(True)
        tableView.resizeColumnsToContents()
        tableView.resizeRowsToContents()
        tableView.setSortingEnabled(True)

    # -- Exporting stuff --

    def export_csv(self):
        startingDir = getUserFilesDirectory()
        name = self.worldName + "_" + arrow.now().format('DD_MM_YYYY_HH_mm_ss')
        result = QtGui.QFileDialog.getSaveFileName(QtGui.qApp.mainWindow,
                                                   self.tr("Export as .csv"),
                                                   startingDir + "\\" + name,
                                                   "Comma Separated Values (*.csv);;Semicolon Separated Values (*.csv)")
        if result and result[0]:
            """
            Depending on your region, your OS uses ";" or "," as a seperator in .csv files.
            (Some countries write 0.5 as 0,5; so they use ; to separate values).
            If the user selects Semicolon Separated Values, we separate with ";" instead of ","
            """
            sep = (";" if (result[1] == "Semicolon Separated Values (*.csv)") else ",")
            self.writeFile(result[0], sep)

    def export_txt(self):
        startingDir = getUserFilesDirectory()
        name = self.worldName + "_" + arrow.now().format('DD_MM_YYYY_HH_mm_ss')
        result = QtGui.QFileDialog.getSaveFileName(QtGui.qApp.mainWindow,
                                                   self.tr("Export as .txt"),
                                                   startingDir + "\\" + name,
                                                   "Text File (*.txt)")
        if result and result[0]:
            sep = "\t"
            self.writeFile(result[0], sep)

    def writeFile(self, filename, sep):
        with open(filename, 'w') as f:
            f.write("Blocks:\n")
            f.write("Name" + sep + "Id" + sep + "Data" + sep + "Count\n")
            for b in self.blockArrayData:
                string = b[0] + unicode(sep + str(b[1]) + sep + str(b[2]) + sep + str(b[3]) + "\n",
                                        encoding="utf-8")  # xxx Unrolled loop
                f.write(string.encode('utf8'))
            f.write("\nEntities:\n")
            f.write("Name" + sep + "Count\n")
            for e in self.entityArrayData:
                string = e[0] + unicode(sep + str(e[1]) + "\n", encoding='utf-8')  # xxx Unrolled loop
                f.write(string.encode('utf8'))


class CustomTableModel(QtCore.QAbstractTableModel):
    def __init__(self, arraydata, headerdata, parent=None, *args, **kwargs):
        QtCore.QAbstractTableModel.__init__(self, parent, *args, **kwargs)
        self.arraydata = arraydata
        self.headerdata = headerdata

    def rowCount(self, parent):
        return len(self.arraydata)

    def columnCount(self, parent):
        return len(self.headerdata)

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
        self.layoutAboutToBeChanged.emit()
        self.arraydata = sorted(self.arraydata, key=operator.itemgetter(Ncol))
        if order == QtCore.Qt.DescendingOrder:
            self.arraydata.reverse()
        self.layoutChanged.emit()



