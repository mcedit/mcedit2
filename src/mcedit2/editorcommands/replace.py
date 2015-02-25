"""
    replace
"""
from __future__ import absolute_import, division, print_function
from PySide import QtGui, QtCore
import logging
from mcedit2.command import SimpleRevisionCommand
from mcedit2.util.load_ui import load_ui
from mcedit2.util.resources import resourcePath
from mcedit2.util.showprogress import showProgress
from mcedit2.widgets.blockpicker import BlockTypeButton
from mcedit2.widgets.layout import Row

log = logging.getLogger(__name__)


class ReplaceDialog(QtGui.QDialog):
    def __init__(self, editorSession, *args, **kwargs):
        super(ReplaceDialog, self).__init__(*args, **kwargs)
        self.editorSession = editorSession
        self.blocktypes = editorSession.worldEditor.blocktypes
        load_ui("replace.ui", baseinstance=self)
        header = self.tableWidget.horizontalHeader()
        header.setResizeMode(0, QtGui.QHeaderView.Stretch)
        header.setResizeMode(1, QtGui.QHeaderView.Stretch)

        self.tableWidget.setRowCount(1)
        addButton = QtGui.QPushButton("Add...", flat=True, clicked=self.addNewRow)
        addButton.setIcon(QtGui.QIcon(resourcePath("mcedit2/assets/mcedit2/icons/add.png")))
        addButton.setMinimumHeight(48)
        addButton.setIconSize(QtCore.QSize(32, 32))
        addItem = QtGui.QTableWidgetItem(text="Add...")
        addItem.setSizeHint(addButton.sizeHint())
        self.tableWidget.setItem(0, 0, addItem)
        self.tableWidget.setSpan(0, 0, 1, 2)
        self.tableWidget.setCellWidget(0, 0, addButton)

        self.tableWidget.resizeRowsToContents()
        self.tableWidget.resizeColumnsToContents()


    def addNewRow(self):
        self.addRow([self.blocktypes["air"]], self.blocktypes["air"])

    def addRow(self, oldBlocks, newBlock):
        row = self.tableWidget.rowCount() - 1

        self.tableWidget.insertRow(row)
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
                    self.removeRow(self.tableWidget.row(left))
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
        self.tableWidget.setItem(row, 0, left)
        self.tableWidget.setItem(row, 1, right)
        self.tableWidget.setCellWidget(row, 0, leftFramedButton)
        self.tableWidget.setCellWidget(row, 1, rightFramedButton)
        self.tableWidget.resizeRowsToContents()
        #self.tableWidget.resizeColumnsToContents()
        log.info("Done")

    def removeRow(self, row):
        self.tableWidget.removeRow(row)

    def getReplacements(self):
        def _get():
            for row in range(self.tableWidget.rowCount()-1):
                left = self.tableWidget.cellWidget(row, 0).button
                right = self.tableWidget.cellWidget(row, 1).button
                yield left.blocks, right.block

        return list(_get())


def replaceCommand(editorSession):
    dialog = ReplaceDialog(editorSession)
    if dialog.exec_():
        replacements = dialog.getReplacements()
        command = SimpleRevisionCommand(editorSession, "Replace")
        with command.begin():
            task = editorSession.currentDimension.fillBlocksIter(editorSession.currentSelection, replacements, updateLights=False)
            showProgress("Replacing...", task)
        editorSession.pushCommand(command)
