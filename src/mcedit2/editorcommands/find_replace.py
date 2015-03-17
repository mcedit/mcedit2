"""
    replace
"""
from __future__ import absolute_import, division, print_function
from collections import namedtuple
from PySide import QtGui, QtCore
import logging
from PySide.QtCore import Qt
from mcedit2.command import SimpleRevisionCommand
from mcedit2.util.load_ui import load_ui
from mcedit2.util.resources import resourcePath
from mcedit2.util.showprogress import showProgress
from mcedit2.widgets.blockpicker import BlockTypeButton
from mcedit2.widgets.layout import Row, Column

log = logging.getLogger(__name__)

NBTResultsEntry = namedtuple("NBTResultsEntry", "displayName path value")

class NBTResultsModel(QtCore.QAbstractItemModel):
    def __init__(self):
        super(NBTResultsModel, self).__init__()
        self.results = []

    # --- Shape ---

    def rowCount(self, parent):
        if parent.isValid():
            return 0

        return len(self.results)

    def columnCount(self, parent):
        return 3

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return ("Name", "Value", "Location")[section]

        return None

    # --- Indexes ---

    def index(self, row, column, parent=QtCore.QModelIndex()):
        if parent.isValid():
            return QtCore.QModelIndex()

        return self.createIndex(row, column, None)

    def parent(self, index):
        return QtCore.QModelIndex()

    # --- Cells ---

    def flags(self, index):
        if not index.isValid():
            return 0

        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        entry = self.results[index.row()]

        if role in (Qt.DisplayRole, Qt.EditRole):
            column = index.column()
            if column == 0:
                return entry.displayName
            elif column == 1:
                return entry.value
            elif column == 2:
                return entry.path
            else:
                return ""
                # value = entry.value
                # if isinstance(entry.valueType, (list, tuple)):
                #     try:
                #         return entry.valueType[value][1]
                #     except IndexError:
                #         return "Unknown value %s" % value
                # else:
                #     return value

    def addResults(self, results):
        size = len(self.results)
        self.beginInsertRows(QtCore.QModelIndex(), size, size + len(results) - 1)
        self.results.extend(results)
        self.endInsertRows()


    # def setData(self, index, value, role=Qt.EditRole):
    #     row = index.row()
    #     entry = self.properties[row]
    #     if self.rootTag[entry.tagName].value != value:
    #         self.rootTag[entry.tagName].value = value
    #         self.propertyChanged.emit(entry.tagName, value)
    #         self.dataChanged.emit(index, index)

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
        leftButton.textureAtlas = self.editorSession.textureAtlas
        leftButton.blocks = oldBlocks
        leftFramedButton = frameButton(leftButton)
        left.setSizeHint(leftFramedButton.sizeHint())
        log.info("Left button")

        rightButton = BlockTypeButton(flat=True)
        rightButton.textureAtlas = self.editorSession.textureAtlas
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
        selection = self.editorSession.currentDimension.bounds
        # selection = self.editorSession.currentSelection
        with command.begin():
            task = self.editorSession.currentDimension.fillBlocksIter(selection, replacements, updateLights=False)
            showProgress("Replacing...", task)
        self.editorSession.pushCommand(command)


class FindReplaceNBT(QtCore.QObject):
    def __init__(self, editorSession):
        super(FindReplaceNBT, self).__init__()
        self.editorSession = editorSession
        self.widget = load_ui("find_replace_nbt.ui")
        self.resultsModel = NBTResultsModel()
        self.widget.resultsView.setModel(self.resultsModel)
        self.widget.findButton.clicked.connect(self.find)
        self.widget.stopButton.clicked.connect(self.stop)
        self.widget.stopButton.setVisible(False)

        self.widget.searchNameCheckbox.toggled.connect(self.searchForToggled)
        self.widget.searchValueCheckbox.toggled.connect(self.searchForToggled)
        self.findTimer = None
        self.finder = None

    def searchForToggled(self):
        canSearch = self.widget.searchNameCheckbox.isChecked() or self.widget.searchValueCheckbox.isChecked()
        self.widget.findButton.setEnabled(canSearch)

    def find(self):
        searchNames = self.widget.searchNameCheckbox.isChecked()
        targetName = self.widget.nameField.text()
        searchValues = self.widget.searchValueCheckbox.isChecked()
        targetValue = self.widget.valueField.text()

        searchEntities = self.widget.searchEntitiesCheckbox.isChecked()
        targetEntityIDs = self.widget.entityIDField.text()
        if len(targetEntityIDs):
            targetEntityIDs = targetEntityIDs.split(';')

        searchTileEntities = self.widget.searchTileEntitiesCheckbox.isChecked()
        targetTileEntityIDs = self.widget.tileEntityIDField.text()
        if len(targetTileEntityIDs):
            targetTileEntityIDs = targetEntityIDs.split(';')


        if not searchNames and not searchValues:
            return

        dim = self.editorSession.currentDimension
        inSelection = self.widget.inSelectionCheckbox.isChecked()
        if inSelection:
            selection = self.editorSession.currentSelection
            if selection is None:
                return
        else:
            selection = dim.bounds

        def _matchTag(name_or_index, tag):
            if not tag.isCompound() and not tag.isList() and searchValues and targetValue in tag.value:
                return True
            if searchNames and targetName in name_or_index:
                return True
            return False

        def _findTag(name_or_index, tag, path):
            if _matchTag(name_or_index, tag):
                if tag.isCompound():
                    value = "Compound"
                elif tag.isList():
                    value = "List"
                else:
                    value = str(tag.value)

                return str(name_or_index), path, value

        def _findEntitiesInChunk(chunk):
            results = []
            for entity in chunk.Entities:
                if entity.Position not in selection:
                    continue
                if len(targetEntityIDs) and entity.id not in targetEntityIDs:
                    continue

                tag = entity.raw_tag()
                for name, subtag, path in walkNBT(tag):
                    result = _findTag(name, subtag, path)
                    if result:
                        name, path, value = result
                        path = "%s@%s/%s" % (entity.id, entity.Position, path)

                        results.append(NBTResultsEntry(name, path, value))

            self.resultsModel.addResults(results)

        def _findTileEntitiesInChunk(chunk):
            results = []
            for entity in chunk.TileEntities:
                if entity.Position not in selection:
                    continue
                if len(targetTileEntityIDs) and entity.id not in targetTileEntityIDs:
                    continue

                tag = entity.raw_tag()
                for name, subtag, path in walkNBT(tag):
                    result = _findTag(name, subtag, path)
                    if result:
                        name, path, value = result
                        path = "%s@%s/%s" % (entity.id, entity.Position, path)

                        results.append(NBTResultsEntry(name, path, value))

            self.resultsModel.addResults(results)


        def _find():
            self.widget.progressBar.setMaximum(selection.chunkCount)
            for i, cPos in enumerate(selection.chunkPositions()):
                if dim.containsChunk(*cPos):
                    chunk = dim.getChunk(*cPos)
                    if searchEntities:
                        _findEntitiesInChunk(chunk)
                    if searchTileEntities:
                        _findTileEntitiesInChunk(chunk)

                    self.widget.progressBar.setValue(i)
                    yield

            self.stop()

        finder = _find()

        def find():
            try:
                finder.next()
            except StopIteration:
                pass

        self.findTimer = QtCore.QTimer(timeout=find, interval=1.0)
        self.findTimer.start()
        self.widget.findButton.setVisible(False)
        self.widget.stopButton.setVisible(True)

    def stop(self):
        if self.findTimer:
            self.findTimer.stop()
        self.widget.findButton.setVisible(True)
        self.widget.stopButton.setVisible(False)
        self.widget.progressBar.setValue(0)

def walkNBT(tag, path=""):
    if tag.isCompound():
        for name, subtag in tag.iteritems():
            yield (name, subtag, path)
            walkNBT(subtag, path + "/" + name)

    if tag.isList():
        for i, subtag in enumerate(tag):
            yield (i, subtag, path)
            walkNBT(subtag, path + "/" + str(i))


class FindReplaceDialog(QtGui.QDialog):
    def __init__(self, editorSession, *args, **kwargs):
        super(FindReplaceDialog, self).__init__(*args, **kwargs)
        self.editorSession = editorSession
        self.blocktypes = editorSession.worldEditor.blocktypes
        load_ui("find_replace.ui", baseinstance=self)

        self.findReplaceBlocks = FindReplaceBlocks(editorSession, self)

        self.findReplaceNBT = FindReplaceNBT(editorSession)
        self.nbtTab.setLayout(Column(self.findReplaceNBT.widget, margin=0))





