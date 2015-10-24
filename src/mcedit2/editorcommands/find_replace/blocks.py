"""
    blocks
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from PySide import QtCore, QtGui

from mcedit2.command import SimpleRevisionCommand
from mcedit2.util.resources import resourcePath
from mcedit2.util.showprogress import showProgress
from mcedit2.widgets.blockpicker import BlockTypeButton
from mcedit2.widgets.layout import Row

log = logging.getLogger(__name__)


class FindReplaceBlocks(QtCore.QObject):
    def __init__(self, editorSession, dialog, *args, **kwargs):
        super(FindReplaceBlocks, self).__init__(*args, **kwargs)
        self.editorSession = editorSession
        self.dialog = dialog

        header = dialog.findReplaceTable.horizontalHeader()
        header.setResizeMode(0, QtGui.QHeaderView.Stretch)
        header.setResizeMode(1, QtGui.QHeaderView.Stretch)
        dialog.findReplaceTable.setRowCount(1)
        addButton = QtGui.QPushButton("Add...", flat=True, clicked=self.addNewRow)
        addButton.setIcon(QtGui.QIcon(resourcePath("mcedit2/assets/mcedit2/icons/add.png")))
        addButton.setMinimumHeight(48)
        addButton.setIconSize(QtCore.QSize(32, 32))
        addItem = QtGui.QTableWidgetItem(text="Add...")
        addItem.setSizeHint(addButton.sizeHint())
        dialog.findReplaceTable.setItem(0, 0, addItem)
        dialog.findReplaceTable.setSpan(0, 0, 1, 2)
        dialog.findReplaceTable.setCellWidget(0, 0, addButton)
        dialog.findReplaceTable.resizeRowsToContents()
        dialog.findReplaceTable.resizeColumnsToContents()
        dialog.blocksReplaceButton.clicked.connect(self.doReplace)

    @property
    def blocktypes(self):
        return self.editorSession.worldEditor.blocktypes

    def addNewRow(self):
        self.addRow([self.blocktypes["air"]], self.blocktypes["air"])

    def addRow(self, oldBlocks, newBlock):
        row = self.dialog.findReplaceTable.rowCount() - 1

        self.dialog.findReplaceTable.insertRow(row)
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
                    self.removeRow(self.dialog.findReplaceTable.row(left))
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
        self.dialog.findReplaceTable.setItem(row, 0, left)
        self.dialog.findReplaceTable.setItem(row, 1, right)
        self.dialog.findReplaceTable.setCellWidget(row, 0, leftFramedButton)
        self.dialog.findReplaceTable.setCellWidget(row, 1, rightFramedButton)
        self.dialog.findReplaceTable.resizeRowsToContents()
        #self.findReplaceTable.resizeColumnsToContents()
        log.info("Done")

    def removeRow(self, row):
        self.dialog.findReplaceTable.removeRow(row)

    def getReplacements(self):
        def _get():
            for row in range(self.dialog.findReplaceTable.rowCount()-1):
                left = self.dialog.findReplaceTable.cellWidget(row, 0).button
                right = self.dialog.findReplaceTable.cellWidget(row, 1).button
                yield left.blocks, right.block

        return list(_get())

    def doReplace(self):
        replacements = self.getReplacements()
        command = SimpleRevisionCommand(self.editorSession, "Replace")
        if self.dialog.replaceBlocksInSelectionCheckbox.isChecked():
            selection = self.editorSession.currentSelection
        else:
            selection = self.editorSession.currentDimension.bounds
        with command.begin():
            task = self.editorSession.currentDimension.fillBlocksIter(selection, replacements, updateLights=False)
            showProgress("Replacing...", task)
        self.editorSession.pushCommand(command)