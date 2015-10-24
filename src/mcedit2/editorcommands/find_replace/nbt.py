"""
    nbt
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from PySide import QtCore
from PySide.QtCore import Qt

from mcedit2.command import SimpleRevisionCommand
from mcedit2.util import settings
from mcedit2.util.load_ui import load_ui
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
    def __init__(self, model, tagNameIndex, tagName, value, ID, path, position, uuid, resultType):
        self.model = model
        self.tagNameIndex = tagNameIndex  # xxx REALLY SHOULD change model data through the model itself
        self.tagName = tagName
        self.value = value
        self.id = ID
        self.path = path
        self.position = position
        self.uuid = uuid
        self.resultType = resultType

    EntityResult = "ENTITY"
    TileEntityResult = "TILE_ENTITY"
    ItemResult = "ITEM"
    PlayerResult = "PLAYER"
    ChunkResult = "CHUNK"
    FileResult = "FILE"

    def setTagName(self, value):
        self.tagName = value
        self.model.dataChanged.emit(self.tagNameIndex, self.tagNameIndex)

    def getEntity(self, dim):
        assert self.resultType == self.EntityResult
        box = BoundingBox(self.position.intfloor(), (1, 1, 1)).chunkBox(dim)
        entities = dim.getEntities(box, UUID=self.uuid)
        for entity in entities:
            return entity
        return None


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


class FindReplaceNBT(QtCore.QObject):
    def __init__(self, editorSession, dialog):
        super(FindReplaceNBT, self).__init__()
        self.editorSession = editorSession
        self.widget = load_ui("find_replace_nbt.ui")
        self.dialog = dialog

        self.resultsWidget = load_ui("find_replace_nbt_results.ui")
        self.resultsDockWidget = MCEDockWidget("NBT Search", objectName="nbtSearch")
        self.resultsDockWidget.setWidget(self.resultsWidget)
        self.resultsDockWidget.hide()

        self.resultsModel = NBTResultsModel()
        self.resultsWidget.resultsView.setModel(self.resultsModel)
        self.resultsWidget.resultsView.clicked.connect(self.resultsViewIndexClicked)

        # --- Buttons ---
        self.widget.findButton.clicked.connect(self.find)

        self.resultsWidget.stopButton.clicked.connect(self.stop)
        self.resultsWidget.findAgainButton.clicked.connect(dialog.exec_)

        self.resultsWidget.replaceSelectedButton.clicked.connect(self.replaceSelected)
        self.resultsWidget.replaceAllButton.clicked.connect(self.replaceAll)

        self.widget.searchNameCheckbox.toggled.connect(self.searchForToggled)
        self.widget.searchValueCheckbox.toggled.connect(self.searchForToggled)
        self.findTimer = None
        self.finder = None

        # --- Search for... ---
        self.widget.nameField.setText(nbtReplaceSettings.nameField.value(""))
        self.widget.searchNameCheckbox.setChecked(len(self.widget.nameField.text()) > 0)
        self.widget.nameField.textChanged.connect(self.nameFieldChanged)

        self.widget.valueField.setText(nbtReplaceSettings.valueField.value(""))
        self.widget.searchValueCheckbox.setChecked(len(self.widget.valueField.text()) > 0)
        self.widget.valueField.textChanged.connect(self.valueFieldChanged)

        # --- Search in... ---
        self.widget.searchEntitiesCheckbox.setChecked(nbtReplaceSettings.searchEntitiesChecked.value())
        self.widget.searchEntitiesCheckbox.toggled.connect(nbtReplaceSettings.searchEntitiesChecked.setValue)

        self.widget.entityIDField.setText(nbtReplaceSettings.entityIDField.value())
        self.widget.entityIDField.textChanged.connect(self.entityIDFieldChanged)

        self.widget.searchTileEntitiesCheckbox.setChecked(nbtReplaceSettings.searchTileEntitiesChecked.value())
        self.widget.searchTileEntitiesCheckbox.toggled.connect(nbtReplaceSettings.searchTileEntitiesChecked.setValue)

        self.widget.tileEntityIDField.setText(nbtReplaceSettings.tileEntityIDField.value())
        self.widget.tileEntityIDField.textChanged.connect(self.tileEntityIDFieldChanged)

        # --- Replace with... ---
        self.widget.replaceNameField.setText(nbtReplaceSettings.replaceNameField.value())
        self.resultsWidget.replaceNameField.setText(nbtReplaceSettings.replaceNameField.value())
        self.widget.replaceNameField.textChanged.connect(self.replaceNameFieldChanged)

        self.widget.replaceNameCheckbox.setChecked(len(self.widget.replaceNameField.text()))
        self.resultsWidget.replaceNameCheckbox.setChecked(len(self.widget.replaceNameField.text()))

        self.widget.replaceValueField.setText(nbtReplaceSettings.replaceValueField.value())
        self.resultsWidget.replaceValueField.setText(nbtReplaceSettings.replaceValueField.value())
        self.widget.replaceValueField.textChanged.connect(self.replaceValueFieldChanged)

        self.widget.replaceValueCheckbox.setChecked(len(self.widget.replaceValueField.text()))
        self.resultsWidget.replaceValueCheckbox.setChecked(len(self.widget.replaceValueField.text()))

        self.widget.replaceValueTagTypeComboBox.setCurrentIndex(nbtReplaceSettings.replaceValueTagType.value())
        self.widget.replaceValueTagTypeComboBox.currentIndexChanged[int].connect(self.valueTagTypeChanged)

    def dialogOpened(self):
        currentSelection = self.editorSession.currentSelection
        self.widget.inSelectionCheckbox.setChecked(currentSelection is not None and currentSelection.volume > 0)

    def searchForToggled(self):
        #canSearch = self.widget.searchNameCheckbox.isChecked() or self.widget.searchValueCheckbox.isChecked()
        #self.widget.findButton.setEnabled(canSearch)
        pass

    def nameFieldChanged(self, value):
        nbtReplaceSettings.nameField.setValue(value)
        self.widget.searchNameCheckbox.setChecked(len(value) > 0)

    def valueFieldChanged(self, value):
        nbtReplaceSettings.valueField.setValue(value)
        self.widget.searchValueCheckbox.setChecked(len(value) > 0)

    def entityIDFieldChanged(self, value):
        nbtReplaceSettings.entityIDField.setValue(value)
        if len(value):
            self.widget.searchEntitiesCheckbox.setChecked(True)

    def tileEntityIDFieldChanged(self, value):
        nbtReplaceSettings.tileEntityIDField.setValue(value)
        if len(value):
            self.widget.searchTileEntitiesCheckbox.setChecked(True)

    def replaceNameFieldChanged(self, value):
        if value != nbtReplaceSettings.replaceNameField.value():
            nbtReplaceSettings.replaceNameField.setValue(value)

            self.widget.replaceNameCheckbox.setChecked(len(value) > 0)
            self.widget.replaceNameField.setText(value)

            self.resultsWidget.replaceNameCheckbox.setChecked(len(value) > 0)
            self.resultsWidget.replaceNameField.setText(value)

    def replaceValueFieldChanged(self, value):
        if value != nbtReplaceSettings.replaceValueField.value():
            nbtReplaceSettings.replaceValueField.setValue(value)

            self.widget.replaceValueCheckbox.setChecked(len(value) > 0)
            self.widget.replaceValueField.setText(value)

            self.resultsWidget.replaceValueCheckbox.setChecked(len(value) > 0)
            self.resultsWidget.replaceValueField.setText(value)

    def valueTagTypeChanged(self, index):
        if index != nbtReplaceSettings.replaceValueTagType.value():
            nbtReplaceSettings.replaceValueTagType.setValue(index)
            self.widget.replaceValueTagTypeComboBox.setCurrentIndex(index)
            self.resultsWidget.replaceValueTagTypeComboBox.setCurrentIndex(index)

    def resultsViewIndexClicked(self, modelIndex):
        row = modelIndex.row()
        result = self.resultsModel.results[row]
        if result.resultType == result.EntityResult:
            entity = result.getEntity(self.editorSession.currentDimension)
            if entity is not None:
                self.editorSession.zoomAndInspectEntity(entity)  # xxxxxxx!!!
            else:
                log.error("Entity not found for result %s", str(result))
        if result.resultType == result.TileEntityResult:
            self.editorSession.zoomAndInspectBlock(result.position)

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
            targetTileEntityIDs = targetTileEntityIDs.split(';')

        if not any((searchNames, searchValues, searchEntities, searchTileEntities)):
            # Nothing to find
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
                    value = str(tag.value)

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
                                               id=entity.id,
                                               path=[],
                                               position=entity.Position,
                                               uuid=uuid,
                                               resultType=NBTResultsEntry.EntityResult)
                    continue

                tag = entity.raw_tag()

                for name, subtag, path in nbt.walk(tag):
                    result = _findTag(name, subtag, path)
                    if result:
                        name, path, value = result

                        self.resultsModel.addEntry(tagName=name,
                                                   value=value,
                                                   id=entity.id,
                                                   path=path,
                                                   position=entity.Position,
                                                   uuid=uuid,
                                                   resultType=NBTResultsEntry.EntityResult)

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
                                               id=tileEntity.id,
                                               path=[],
                                               position=tileEntity.Position,
                                               uuid=None,
                                               resultType=NBTResultsEntry.TileEntityResult)
                    continue

                tag = tileEntity.raw_tag()
                for name, subtag, path in nbt.walk(tag):
                    result = _findTag(name, subtag, path)
                    if result:
                        name, path, value = result

                        self.resultsModel.addEntry(tagName=name,
                                                   value=value,
                                                   id=tileEntity.id,
                                                   path=path,
                                                   position=tileEntity.Position,
                                                   uuid=None,
                                                   resultType=NBTResultsEntry.TileEntityResult)

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
        self.widget.findButton.setEnabled(True)
        self.resultsWidget.stopButton.setEnabled(False)
        self.resultsWidget.findAgainButton.setEnabled(True)

    def replaceEntries(self, entries):
        shouldReplaceName = self.widget.replaceNameCheckbox.isChecked()
        newName = self.widget.replaceNameField.text()
        shouldReplaceValue = self.widget.replaceValueCheckbox.isChecked()
        newValue = self.widget.replaceValueField.text()
        # newTagType = self.widget.replaceTagTypeComboBox.currentIndex()

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

        def _replace():
            for result in entries:
                if result.resultType == result.TileEntityResult:
                    tileEntity = self.editorSession.currentDimension.getTileEntity(result.position)
                    if tileEntity:
                        tag = tileEntity.raw_tag()
                        _replaceInTag(result, tag)
                        tileEntity.dirty()

                if result.resultType == result.EntityResult:
                    entity = result.getEntity(self.editorSession.currentDimension)  # xxx put dimension in result!!!!
                    if entity:
                        tag = entity.raw_tag()
                        _replaceInTag(result, tag)
                        entity.dirty()

                # if result.resultType == result.ItemResult:  # xxx
                yield

        command = NBTReplaceCommand(self.editorSession, "Replace NBT data")  # xxx replace details
        with command.begin():
            replacer = _replace()
            showProgress("Replacing NBT data...", replacer)

        self.editorSession.pushCommand(command)

    def replaceAll(self):
        self.replaceEntries(self.resultsModel.results)

    def replaceSelected(self):
        pass
