"""
    block_replacements
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from PySide import QtCore, QtGui

from mcedit2.ui.block_replacements import Ui_BlockReplacements
from mcedit2.util.resources import resourcePath
from mcedit2.widgets.blockpicker import BlockTypeButton
from mcedit2.widgets.layout import Row, Column

log = logging.getLogger(__name__)


class BlockReplacementButton(QtGui.QWidget):
    def __init__(self, parent=None):
        super(BlockReplacementButton, self).__init__()

        self.replacementList = BlockReplacementList()
        self.replacementDialog = QtGui.QDialog()

        self.replacementOk = QtGui.QPushButton(self.tr("OK"))
        self.replacementOk.clicked.connect(self.replacementDialog.accept)

        self.replacementDialog.setWindowTitle(self.tr("Choose blocks to replace"))
        self.replacementDialog.setLayout(Column(self.replacementList,
                                                Row(None, self.replacementOk)))

        self.oldBlockButton = BlockTypeButton(multipleSelect=True)
        self.newBlockButton = BlockTypeButton()
        self.advancedButton = QtGui.QPushButton(self.tr("Advanced..."))

        self.simpleButton = QtGui.QPushButton(self.tr("No, simple!"))
        self.simpleButton.setVisible(False)
        self.simpleButton.clicked.connect(self.goSimple)

        self.setLayout(Column(self.oldBlockButton,
                              self.newBlockButton,
                              self.advancedButton,
                              self.simpleButton,
                              margin=0))

        self.oldBlockButton.blocksChanged.connect(self.simpleBlocksChanged)
        self.newBlockButton.blocksChanged.connect(self.simpleBlocksChanged)
        self.advancedButton.clicked.connect(self.displayDialog)

    replacementsChanged = QtCore.Signal()

    _editorSession = None

    @property
    def editorSession(self):
        return self._editorSession

    @editorSession.setter
    def editorSession(self, session):
        self._editorSession = session
        self.oldBlockButton.editorSession = session
        self.newBlockButton.editorSession = session
        self.replacementList.editorSession = session

    def displayDialog(self):
        self.replacementDialog.exec_()
        replacements = self.replacementList.getReplacements()
        if len(replacements) == 0:
            self.oldBlockButton.blocks = []
            self.newBlockButton.blocks = []
        elif len(replacements) == 1:
            old, new = replacements[0]
            self.oldBlockButton.blocks = old
            self.newBlockButton.block = new

        if len(replacements) > 1:
            self.oldBlockButton.blocks = []
            self.newBlockButton.blocks = []
            self.oldBlockButton.setEnabled(False)
            self.newBlockButton.setEnabled(False)
            self.simpleButton.setVisible(True)
        else:
            self.oldBlockButton.setEnabled(True)
            self.newBlockButton.setEnabled(True)
            self.simpleButton.setVisible(False)

        self.replacementsChanged.emit()

    def goSimple(self):
        self.oldBlockButton.blocks = []
        self.newBlockButton.blocks = []
        self.simpleButton.setVisible(False)

    def simpleBlocksChanged(self):
        old = self.oldBlockButton.blocks
        new = self.newBlockButton.block
        if new is not None:
            replacements = [(old, new)]
        else:
            replacements = []
        log.info("Replacements button: %s", replacements)
        self.replacementList.setReplacements(replacements)
        self.replacementsChanged.emit()

    def getReplacements(self):
        return self.replacementList.getReplacements()


class BlockReplacementList(QtGui.QWidget, Ui_BlockReplacements):
    def __init__(self, parent=None):
        super(BlockReplacementList, self).__init__(parent)
        self.setupUi(self)

        header = self.findReplaceTable.horizontalHeader()
        header.setResizeMode(0, QtGui.QHeaderView.Stretch)
        header.setResizeMode(1, QtGui.QHeaderView.Stretch)

        self.editorSession = None

        self.clearTable()

    def clearTable(self):
        addButton = QtGui.QPushButton("Add...", flat=True, clicked=self.addNewRow)
        addButton.setIcon(QtGui.QIcon(resourcePath("mcedit2/assets/mcedit2/icons/add.png")))
        addButton.setMinimumHeight(48)
        addButton.setIconSize(QtCore.QSize(32, 32))

        addItem = QtGui.QTableWidgetItem(text="Add...")
        addItem.setSizeHint(addButton.sizeHint())

        self.findReplaceTable.clear()
        self.findReplaceTable.setRowCount(1)
        self.findReplaceTable.setItem(0, 0, addItem)
        self.findReplaceTable.setSpan(0, 0, 1, 2)
        self.findReplaceTable.setCellWidget(0, 0, addButton)
        self.findReplaceTable.resizeRowsToContents()
        self.findReplaceTable.resizeColumnsToContents()


    @property
    def blocktypes(self):
        return self.editorSession.worldEditor.blocktypes if self.editorSession else None

    def addNewRow(self):
        self.addRow([], self.blocktypes["air"])

    def addRow(self, oldBlocks, newBlock):
        assert self.editorSession is not None, "Must set BlockReplacementList.editorSession before using"

        row = self.findReplaceTable.rowCount() - 1

        self.findReplaceTable.insertRow(row)
        log.info("Row inserted")

        left = QtGui.QTableWidgetItem()
        right = QtGui.QTableWidgetItem()
        log.info("Items created")

        def frameButton(button, withRemove=False):
            frame = QtGui.QFrame()
            frame.button = button
            layout = QtGui.QVBoxLayout()
            layout.addStretch(1)
            if withRemove:
                removeButton = QtGui.QPushButton("", flat=True)
                removeButton.setIcon(QtGui.QIcon(resourcePath("mcedit2/assets/mcedit2/icons/remove.png")))
                removeButton.setIconSize(QtCore.QSize(24, 24))

                def _clicked():
                    self.removeRow(self.findReplaceTable.row(left))
                removeButton.__clicked = _clicked
                removeButton.clicked.connect(_clicked)
                layout.addLayout(Row((button, 1), removeButton))
            else:
                layout.addWidget(button)
            layout.addStretch(1)
            frame.setLayout(layout)
            return frame

        leftButton = BlockTypeButton(flat=True, multipleSelect=True)
        leftButton.editorSession = self.editorSession
        leftButton.blocks = oldBlocks
        leftFramedButton = frameButton(leftButton)
        left.setSizeHint(leftFramedButton.sizeHint())
        log.info("Left button")

        rightButton = BlockTypeButton(flat=True)
        rightButton.editorSession = self.editorSession
        rightButton.block = newBlock
        rightFramedButton = frameButton(rightButton, True)
        right.setSizeHint(rightFramedButton.sizeHint())
        log.info("Right button")
        self.findReplaceTable.setItem(row, 0, left)
        self.findReplaceTable.setItem(row, 1, right)
        self.findReplaceTable.setCellWidget(row, 0, leftFramedButton)
        self.findReplaceTable.setCellWidget(row, 1, rightFramedButton)
        self.findReplaceTable.resizeRowsToContents()
        #self.findReplaceTable.resizeColumnsToContents()
        log.info("Done")

    def removeRow(self, row):
        self.findReplaceTable.removeRow(row)

    def getReplacements(self):
        def _get():
            for row in range(self.findReplaceTable.rowCount()-1):
                left = self.findReplaceTable.cellWidget(row, 0).button
                right = self.findReplaceTable.cellWidget(row, 1).button
                yield left.blocks, right.block

        return list(_get())

    def setReplacements(self, replacements):
        if replacements == self.getReplacements():
            return

        self.clearTable()
        for old, new in replacements:
            self.addRow(old, new)

