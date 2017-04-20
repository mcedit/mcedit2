"""
    nbt
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from PySide import QtCore, QtGui
from PySide.QtCore import Qt

from mcedit2.command import SimpleRevisionCommand
from mcedit2.ui.find_replace_nbt import Ui_findNBTWidget
from mcedit2.ui.find_replace_nbt_results import Ui_findNBTResults
from mcedit2.util import settings
from mcedit2.util.showprogress import showProgress
from mcedit2.widgets.mcedockwidget import MCEDockWidget
from mceditlib import nbt
from mceditlib.selection import BoundingBox

log = logging.getLogger(__name__)

nbtReplaceSettings = settings.Settings().getNamespace("findreplace/nbt")
nbtReplaceSettings.nameField = nbtReplaceSettings.getOption("nameField", unicode, "")
nbtReplaceSettings.valueField = nbtReplaceSettings.getOption("valueField", unicode, "")

nbtReplaceSettings.entityIDField = nbtReplaceSettings.getOption("entityIDField", unicode, "")
nbtReplaceSettings.searchEntitiesChecked = nbtReplaceSettings.getOption("searchEntitiesChecked", bool, False)

nbtReplaceSettings.tileEntityIDField = nbtReplaceSettings.getOption("tileEntityIDField", unicode, "")
nbtReplaceSettings.searchTileEntitiesChecked = nbtReplaceSettings.getOption("searchTileEntitiesChecked", bool, False)

nbtReplaceSettings.replaceNameField = nbtReplaceSettings.getOption("replaceNameField", unicode, "")
nbtReplaceSettings.replaceValueField = nbtReplaceSettings.getOption("replaceValueField", unicode, "")
nbtReplaceSettings.replaceValueTagType = nbtReplaceSettings.getOption("replaceValueTagType", int, 0)


class NBTResultsEntry(object):
    # namedtuple("NBTResultsEntry", "tagName value id path position uuid resultType")):
    def __init__(self, model, tagNameIndex, tagName, value, ID, path, position, uuid, resultType, dimension):
        self.model = model
        self.tagNameIndex = tagNameIndex  # xxx REALLY SHOULD change model data through the model itself
        self.tagName = tagName
        self.value = value
        self.id = ID
        self.path = path
        self.position = position
        self.uuid = uuid
        self.resultType = resultType
        self.dimension = dimension

    EntityResult = "ENTITY"
    TileEntityResult = "TILE_ENTITY"
    ItemResult = "ITEM"
    PlayerResult = "PLAYER"
    ChunkResult = "CHUNK"
    FileResult = "FILE"

    def setTagName(self, value):
        self.tagName = value
        self.model.dataChanged.emit(self.tagNameIndex, self.tagNameIndex)

    def getEntity(self):
        assert self.resultType == self.EntityResult
        dim = self.dimension

        box = BoundingBox(self.position, (1, 1, 1)).chunkBox(dim)
        entities = dim.getEntities(box, UUID=self.uuid)
        for entity in entities:
            return entity
        return None

    def getTargetRef(self):
        dim = self.dimension
        if self.resultType == self.TileEntityResult:
            return dim.getTileEntity(self.position)

        if self.resultType == self.EntityResult:
            return self.getEntity()

        # if result.resultType == result.ItemResult:  # xxx



class NBTResultsModel(QtCore.QAbstractItemModel):
    def __init__(self):
        super(NBTResultsModel, self).__init__()
        self.results = []

    def addEntry(self, *a, **kw):
        index = self.index(len(self.results), 0)
        entry = NBTResultsEntry(self, index, *a, **kw)
        self.beginInsertRows(QtCore.QModelIndex(), len(self.results), len(self.results))
        self.results.append(entry)
        self.endInsertRows()
        return entry

    def removeEntries(self, entries):
        self.beginResetModel()
        self.results = [r for r in self.results if r not in entries]
        self.endResetModel()

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
                return entry.tagName
            elif column == 1:
                return entry.value
            elif column == 2:
                path = "/".join(str(p) for p in entry.path)

                if entry.resultType == entry.EntityResult:
                    return "%s@%s/%s (%s)" % (entry.id, entry.position, path, entry.uuid)
                elif entry.resultType == entry.TileEntityResult:
                    return "%s@%s/%s" % (entry.id, entry.position, path)
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

        if role == Qt.UserRole:
            return entry

    def addResults(self, results):
        size = len(self.results)
        self.beginInsertRows(QtCore.QModelIndex(), size, size + len(results) - 1)
        self.results.extend(results)
        self.endInsertRows()

    def clear(self):
        size = len(self.results)
        self.beginRemoveRows(QtCore.QModelIndex(), 0, size - 1)
        self.results[:] = []
        self.endRemoveRows()

    # def setData(self, index, value, role=Qt.EditRole):
    #     row = index.row()
    #     entry = self.properties[row]
    #     if self.rootTag[entry.tagName].value != value:
    #         self.rootTag[entry.tagName].value = value
    #         self.propertyChanged.emit(entry.tagName, value)
    #         self.dataChanged.emit(index, index)


class ReplaceValueTagType(object):
    """
    duplicated from find_replace_nbt.ui
    """
    EXISTING = 0
    STRING = 1
    BYTE = 2
    SHORT = 3
    INT = 4
    LONG = 5
    FLOAT = 6
    DOUBLE = 7


class NBTReplaceCommand(SimpleRevisionCommand):
    pass


class FindReplaceNBTResults(QtGui.QWidget, Ui_findNBTResults):
    pass


class FindReplaceNBT(QtGui.QWidget, Ui_findNBTWidget):
    def __init__(self, editorSession, dialog):
        super(FindReplaceNBT, self).__init__()
        self.editorSession = editorSession
        self.setupUi(self)
        self.dialog = dialog

        self.resultsWidget = FindReplaceNBTResults()
        self.resultsWidget.setupUi(self.resultsWidget)

        self.resultsDockWidget = MCEDockWidget("NBT Search", objectName="nbtSearch")
        self.resultsDockWidget.setWidget(self.resultsWidget)
        self.resultsDockWidget.hide()

        self.resultsModel = NBTResultsModel()
        self.resultsWidget.resultsView.setModel(self.resultsModel)
        self.resultsWidget.resultsView.clicked.connect(self.resultsViewIndexClicked)

        # --- Buttons ---
        self.findButton.clicked.connect(self.find)

        self.resultsWidget.stopButton.clicked.connect(self.stop)
        self.resultsWidget.findAgainButton.clicked.connect(dialog.exec_)

        self.resultsWidget.replaceSelectedButton.clicked.connect(self.replaceSelected)
        self.resultsWidget.replaceAllButton.clicked.connect(self.replaceAll)

        self.resultsWidget.removeSelectedButton.clicked.connect(self.removeSelected)
        self.resultsWidget.removeAllButton.clicked.connect(self.removeAll)

        self.searchNameCheckbox.toggled.connect(self.searchForToggled)
        self.searchValueCheckbox.toggled.connect(self.searchForToggled)
        self.findTimer = None
        self.finder = None

        # --- Search for... ---
        self.nameField.setText(nbtReplaceSettings.nameField.value(""))
        self.searchNameCheckbox.setChecked(len(self.nameField.text()) > 0)
        self.nameField.textChanged.connect(self.nameFieldChanged)

        self.valueField.setText(nbtReplaceSettings.valueField.value(""))
        self.searchValueCheckbox.setChecked(len(self.valueField.text()) > 0)
        self.valueField.textChanged.connect(self.valueFieldChanged)

        # --- Search in... ---
        self.searchEntitiesCheckbox.setChecked(nbtReplaceSettings.searchEntitiesChecked.value())
        self.searchEntitiesCheckbox.toggled.connect(nbtReplaceSettings.searchEntitiesChecked.setValue)

        self.entityIDField.setText(nbtReplaceSettings.entityIDField.value())
        self.entityIDField.textChanged.connect(self.entityIDFieldChanged)

        self.searchTileEntitiesCheckbox.setChecked(nbtReplaceSettings.searchTileEntitiesChecked.value())
        self.searchTileEntitiesCheckbox.toggled.connect(nbtReplaceSettings.searchTileEntitiesChecked.setValue)

        self.tileEntityIDField.setText(nbtReplaceSettings.tileEntityIDField.value())
        self.tileEntityIDField.textChanged.connect(self.tileEntityIDFieldChanged)

        # --- Replace with... ---
        self.replaceNameField.setText(nbtReplaceSettings.replaceNameField.value())
        self.replaceNameField.setText(nbtReplaceSettings.replaceNameField.value())
        self.replaceNameField.textChanged.connect(self.replaceNameFieldChanged)

        self.replaceNameCheckbox.setChecked(len(self.replaceNameField.text()))
        self.replaceNameCheckbox.setChecked(len(self.replaceNameField.text()))

        self.replaceValueField.setText(nbtReplaceSettings.replaceValueField.value())
        self.replaceValueField.setText(nbtReplaceSettings.replaceValueField.value())
        self.replaceValueField.textChanged.connect(self.replaceValueFieldChanged)

        self.replaceValueCheckbox.setChecked(len(self.replaceValueField.text()))
        self.replaceValueCheckbox.setChecked(len(self.replaceValueField.text()))

        self.replaceValueTagTypeComboBox.setCurrentIndex(nbtReplaceSettings.replaceValueTagType.value())
        self.replaceValueTagTypeComboBox.currentIndexChanged[int].connect(self.valueTagTypeChanged)

    def dialogOpened(self):
        currentSelection = self.editorSession.currentSelection
        self.inSelectionCheckbox.setChecked(currentSelection is not None and currentSelection.volume > 0)

    def searchForToggled(self):
        #canSearch = self.searchNameCheckbox.isChecked() or self.searchValueCheckbox.isChecked()
        #self.findButton.setEnabled(canSearch)
        pass

    def nameFieldChanged(self, value):
        nbtReplaceSettings.nameField.setValue(value)
        self.searchNameCheckbox.setChecked(len(value) > 0)

    def valueFieldChanged(self, value):
        nbtReplaceSettings.valueField.setValue(value)
        self.searchValueCheckbox.setChecked(len(value) > 0)

    def entityIDFieldChanged(self, value):
        nbtReplaceSettings.entityIDField.setValue(value)
        if len(value):
            self.searchEntitiesCheckbox.setChecked(True)

    def tileEntityIDFieldChanged(self, value):
        nbtReplaceSettings.tileEntityIDField.setValue(value)
        if len(value):
            self.searchTileEntitiesCheckbox.setChecked(True)

    def replaceNameFieldChanged(self, value):
        if value != nbtReplaceSettings.replaceNameField.value():
            nbtReplaceSettings.replaceNameField.setValue(value)

            self.replaceNameCheckbox.setChecked(len(value) > 0)
            self.replaceNameField.setText(value)

            self.replaceNameCheckbox.setChecked(len(value) > 0)
            self.replaceNameField.setText(value)

    def replaceValueFieldChanged(self, value):
        if value != nbtReplaceSettings.replaceValueField.value():
            nbtReplaceSettings.replaceValueField.setValue(value)

            self.replaceValueCheckbox.setChecked(len(value) > 0)
            self.replaceValueField.setText(value)

            self.replaceValueCheckbox.setChecked(len(value) > 0)
            self.replaceValueField.setText(value)

    def valueTagTypeChanged(self, index):
        if index != nbtReplaceSettings.replaceValueTagType.value():
            nbtReplaceSettings.replaceValueTagType.setValue(index)
            self.replaceValueTagTypeComboBox.setCurrentIndex(index)
            self.replaceValueTagTypeComboBox.setCurrentIndex(index)

    def resultsViewIndexClicked(self, modelIndex):
        row = modelIndex.row()
        result = self.resultsModel.results[row]
        if result.resultType == result.EntityResult:
            entity = result.getEntity()
            if entity is not None:
                self.editorSession.zoomAndInspectEntity(entity)  # xxxxxxx!!!
            else:
                log.error("Entity not found for result %s", str(result))
        if result.resultType == result.TileEntityResult:
            self.editorSession.zoomAndInspectBlock(result.position)

    def find(self):
        searchNames = self.searchNameCheckbox.isChecked()
        targetName = self.nameField.text()
        searchValues = self.searchValueCheckbox.isChecked()
        targetValue = self.valueField.text()

        searchEntities = self.searchEntitiesCheckbox.isChecked()
        targetEntityIDs = self.entityIDField.text()
        if len(targetEntityIDs):
            targetEntityIDs = targetEntityIDs.split(';')

        searchTileEntities = self.searchTileEntitiesCheckbox.isChecked()
        targetTileEntityIDs = self.tileEntityIDField.text()
        if len(targetTileEntityIDs):
            targetTileEntityIDs = targetTileEntityIDs.split(';')

        if not any((searchNames, searchValues, searchEntities, searchTileEntities)):
            # Nothing to find
            return

        dim = self.editorSession.currentDimension
        inSelection = self.inSelectionCheckbox.isChecked()
        if inSelection:
            selection = self.editorSession.currentSelection
            if selection is None:
                return
        else:
            selection = dim.bounds

        def _matchTag(name_or_index, tag):
            if searchValues and not tag.isCompound() and not tag.isList():
                if tag.tagID == nbt.ID_STRING and targetValue in tag.value:
                    return True
                elif targetValue == tag.value:
                    return True
            if searchNames and isinstance(name_or_index, basestring) and targetName in name_or_index:
                return True
            return False

        def _findTag(name_or_index, tag, path):
            if _matchTag(name_or_index, tag):
                if tag.isCompound():
                    value = "Compound"  # describeCompound
                elif tag.isList():
                    value = "List"  # describeList
                else:
                    value = unicode(tag.value)

                return str(name_or_index), path, value

        def _findEntitiesInChunk(chunk):
            for entity in chunk.Entities:
                if entity.Position not in selection:
                    continue
                if len(targetEntityIDs) and entity.id not in targetEntityIDs:
                    continue

                try:
                    uuid = entity.UUID
                except KeyError:
                    uuid = None  # Don't want to use find/replace on entities without UUIDs

                if not searchNames and not searchValues:
                    # Finding entities only
                    self.resultsModel.addEntry(tagName="id",
                                               value=entity.id,
                                               ID=entity.id,
                                               path=[],
                                               position=entity.Position,
                                               uuid=uuid,
                                               resultType=NBTResultsEntry.EntityResult,
                                               dimension=self.editorSession.currentDimension)
                    continue

                tag = entity.raw_tag()

                for name, subtag, path in nbt.walk(tag):
                    result = _findTag(name, subtag, path)
                    if result:
                        name, path, value = result

                        self.resultsModel.addEntry(tagName=name,
                                                   value=value,
                                                   ID=entity.id,
                                                   path=path,
                                                   position=entity.Position,
                                                   uuid=uuid,
                                                   resultType=NBTResultsEntry.EntityResult,
                                                   dimension=self.editorSession.currentDimension)

        def _findTileEntitiesInChunk(chunk):
            for tileEntity in chunk.TileEntities:
                if tileEntity.Position not in selection:
                    continue
                if len(targetTileEntityIDs) and tileEntity.id not in targetTileEntityIDs:
                    continue

                if not searchNames and not searchValues:
                    # Finding tile entities only
                    self.resultsModel.addEntry(tagName="id",
                                               value=tileEntity.id,
                                               ID=tileEntity.id,
                                               path=[],
                                               position=tileEntity.Position,
                                               uuid=None,
                                               resultType=NBTResultsEntry.TileEntityResult,
                                               dimension=self.editorSession.currentDimension)
                    continue

                tag = tileEntity.raw_tag()
                for name, subtag, path in nbt.walk(tag):
                    result = _findTag(name, subtag, path)
                    if result:
                        name, path, value = result

                        self.resultsModel.addEntry(tagName=name,
                                                   value=value,
                                                   ID=tileEntity.id,
                                                   path=path,
                                                   position=tileEntity.Position,
                                                   uuid=None,
                                                   resultType=NBTResultsEntry.TileEntityResult,
                                                   dimension=self.editorSession.currentDimension)

        def _find():
            self.resultsDockWidget.show()
            self.resultsModel.clear()
            self.dialog.accept()
            self.resultsWidget.findAgainButton.setEnabled(False)

            self.resultsWidget.progressBar.setMaximum(selection.chunkCount-1)
            for i, cPos in enumerate(selection.chunkPositions()):
                if dim.containsChunk(*cPos):
                    chunk = dim.getChunk(*cPos)
                    if searchEntities:
                        _findEntitiesInChunk(chunk)
                    if searchTileEntities:
                        _findTileEntitiesInChunk(chunk)

                    yield
                self.resultsWidget.progressBar.setValue(i)

            self.stop()

        finder = _find()

        def find():
            try:
                finder.next()
            except StopIteration:
                pass

        self.findTimer = QtCore.QTimer(timeout=find, interval=1.0)
        self.findTimer.start()
        self.resultsWidget.stopButton.setEnabled(True)

    def stop(self):
        if self.findTimer:
            self.findTimer.stop()
        self.findButton.setEnabled(True)
        self.resultsWidget.stopButton.setEnabled(False)
        self.resultsWidget.findAgainButton.setEnabled(True)

    def replaceEntries(self, entries):
        shouldReplaceName = self.replaceNameCheckbox.isChecked()
        newName = self.replaceNameField.text()
        shouldReplaceValue = self.replaceValueCheckbox.isChecked()
        newValue = self.replaceValueField.text()
        # newTagType = self.replaceTagTypeComboBox.currentIndex()

        def _replaceInTag(result, tag):
            for component in result.path:
                tag = tag[component]

            if shouldReplaceName:
                subtag = tag.pop(result.tagName)
                tag[newName] = subtag
                result.setTagName(newName)

            if shouldReplaceValue:
                subtag = tag[result.tagName]
                # xxx newTagType
                if subtag.tagID in (nbt.ID_BYTE, nbt.ID_SHORT, nbt.ID_INT, nbt.ID_LONG):
                    try:
                        value = int(newValue)
                    except ValueError:
                        log.warn("Could not assign value %s to tag %s (could not convert to int)", newValue, subtag)
                        return
                elif subtag.tagID in (nbt.ID_FLOAT, nbt.ID_DOUBLE):
                    try:
                        value = float(newValue)
                    except ValueError:
                        log.warn("Could not assign value %s to tag %s (could not convert to float)", newValue, subtag)
                        return
                else:
                    value = newValue
                subtag.value = value
                result.value = value

        def _replace():
            for result in entries:
                ref = result.getTargetRef()

                tag = ref.raw_tag()
                _replaceInTag(result, tag)
                ref.dirty = True

                yield

        command = NBTReplaceCommand(self.editorSession, "Replace NBT data")  # xxx replace details
        with command.begin():
            showProgress("Replacing NBT data...", _replace())

        self.editorSession.pushCommand(command)

    def replaceAll(self):
        self.replaceEntries(self.resultsModel.results)

    def replaceSelected(self):
        entries = []
        for index in self.resultsWidget.resultsView.selectedIndices():
            entries.append(self.resultsModel.data(index, role=Qt.UserRole))

        self.replaceEntries(entries)

    def removeEntries(self, entries):
        def _remove():
            for result in entries:
                ref = result.getTargetRef()
                tag = ref.raw_tag()

                for component in result.path[:-1]:
                    tag = tag[component]

                del tag[result.tagName]
                ref.dirty = True

                yield

            self.resultsModel.removeEntries(entries)

        command = NBTReplaceCommand(self.editorSession, "Remove NBT tags")
        with command.begin():
            showProgress("Removing NBT tags...", _remove())

        self.editorSession.pushCommand(command)

    def removeAll(self):
        self.removeEntries(self.resultsModel.results)

    def removeSelected(self):
        entries = []
        for index in self.resultsWidget.resultsView.selectedIndices():
            entries.append(self.resultsModel.data(index, role=Qt.UserRole))

        self.removeEntries(entries)
