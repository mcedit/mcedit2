"""
    configureblocksdialog.py
"""
from __future__ import absolute_import, division, print_function
import json
import logging
import os
from PySide import QtGui, QtCore
from PySide.QtCore import Qt

from mcedit2.ui.dialogs.configure_blocks import Ui_configureBlocks
from mcedit2.util.directories import getUserFilesDirectory
from mcedit2.widgets.blocktype_list import TexturePixmap

log = logging.getLogger(__name__)


class BlockDefinition(object):
    def __init__(self, internalName=None, defJson=None):
        super(BlockDefinition, self).__init__()
        assert internalName or defJson, "Need at least one of internalName or defJson to create BlockDefinition"
        if defJson is None:
            defJson = {}
        self.internalName = internalName or defJson['internalName']
        self.rotationFlags = defJson.get('rotationFlags', [])
        self.meta = defJson.get('meta', 0)
        self.opacity = defJson.get('opacity', 15)
        self.brightness = defJson.get('brightness', 0)
        self.unlocalizedName = defJson.get('unlocalizedName', internalName)
        self.englishName = defJson.get('englishName', internalName)
        self.modelPath = defJson.get('modelPath', None)
        self.modelRotations = defJson.get('modelRotations', [0, 0])
        self.modelTextures = defJson.get('modelTextures', {})

    def exportAsJson(self):
        keys = ['internalName',
                'rotationFlags',
                'meta',
                'opacity',
                'brightness',
                'unlocalizedName',
                'englishName',
                'modelPath',
                'modelRotations',
                'modelTextures']

        d = {}
        for key in keys:
            d[key] = getattr(self, key)

        return d


class ConfigureBlocksItemDelegate(QtGui.QStyledItemDelegate):
    pass

class TextureListModel(QtCore.QAbstractListModel):
    def __init__(self, resourceLoader):
        super(TextureListModel, self).__init__()
        self.resourceLoader = resourceLoader
        self.textureNames = list(resourceLoader.blockTexturePaths())
        self.texturePixmaps = {}

    def zipfilePaths(self):
        zips = set()
        for zipFilename, _ in self.textureNames:
            if zipFilename in zips:
                continue
            zips.add(zipFilename)
            yield zipFilename

    def rowCount(self, parent):
        if parent.isValid():
            return 0
        return len(self.textureNames)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return

        row = index.row()
        zipFilename, texturePath = self.textureNames[row]
        if role == Qt.DisplayRole:
            return texturePath.rsplit("/", 1)[-1]
        if role == Qt.DecorationRole:
            pixmap = self.texturePixmaps.get(texturePath)
            if pixmap:
                return pixmap

            f = self.resourceLoader.openStream(texturePath)
            pixmap = TexturePixmap(f, 48, texturePath)
            self.texturePixmaps[texturePath] = pixmap
            return pixmap
        if role == self.TexturePathRole:
            return texturePath
        if role == self.ZipfilePathRole:
            return zipFilename

    TexturePathRole = Qt.UserRole
    ZipfilePathRole = Qt.UserRole + 1


class ConfigureBlocksItemModel(QtCore.QAbstractItemModel):

    def __init__(self, *args, **kwargs):
        super(ConfigureBlocksItemModel, self).__init__(*args, **kwargs)
        self.headerTitles = ["Icon",
                             "Block ID",
                             "Rotation Flags",
                             "Meta",
                             "Opacity",
                             "Brightness",
                             "Unlocalized Name",
                             "Name"]

        definedBlocksFilename = "defined_blocks.json"
        self.definedBlocksFilePath = os.path.join(getUserFilesDirectory(), definedBlocksFilename)
        try:
            definedBlocks = json.load(file(self.definedBlocksFilePath, "r"))
        except (ValueError, EnvironmentError) as e:
            log.warn("Failed to read definitions file %s", definedBlocksFilename)
            definedBlocks = []
        if not isinstance(definedBlocks, list):
            definedBlocks = []
        self.definedBlocks = []

        for defJson in definedBlocks:
            try:
                self.definedBlocks.append(BlockDefinition(defJson=defJson))
            except (KeyError, ValueError) as e:
                log.warn("Failed to load a definition from %s: %r", definedBlocksFilename, e)

    def exportAsJson(self):
        defs = []
        for blockDef in self.definedBlocks:
            defs.append(blockDef.exportAsJson())
        return defs

    def writeToJson(self):
        json.dump(self.exportAsJson(), file(self.definedBlocksFilePath, "w"))

    def headerData(self, column, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Vertical:
            return None
        if role == Qt.DisplayRole:
            return self.headerTitles[column]

    def columnCount(self, index):
        return len(self.headerTitles)

    def rowCount(self, index):
        if index.isValid():
            return 0
        return len(self.definedBlocks)

    def index(self, row, column, parent=QtCore.QModelIndex()):
        if parent.isValid():
            return QtCore.QModelIndex()

        return self.createIndex(row, column, None)

    def parent(self, index):
        return QtCore.QModelIndex()

    COL_ICON = 0
    COL_ID = 1
    COL_ROTATION = 2
    COL_META = 3
    COL_OPACITY = 4
    COL_BRIGHTNESS = 5
    COL_UNLOCALIZED = 6
    COL_ENGLISH = 7

    def flags(self, index):
        if not index.isValid():
            return 0

        flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        if index.column() in (self.COL_ID,
                              self.COL_META,
                              self.COL_OPACITY,
                              self.COL_BRIGHTNESS,
                              self.COL_UNLOCALIZED,
                              self.COL_ENGLISH,
                              ):
            flags |= Qt.ItemIsEditable

        return flags

    def data(self, index, role=Qt.DisplayRole):
        row = index.row()
        column = index.column()
        blockDef = self.definedBlocks[row]
        if role == Qt.DisplayRole:
            if column == self.COL_ICON:
                return None
            if column == self.COL_ID:
                return blockDef.internalName
            if column == self.COL_ROTATION:
                return blockDef.rotationFlags
            if column == self.COL_META:
                return blockDef.meta
            if column == self.COL_OPACITY:
                return blockDef.opacity
            if column == self.COL_BRIGHTNESS:
                return blockDef.brightness
            if column == self.COL_UNLOCALIZED:
                return blockDef.unlocalizedName
            if column == self.COL_ENGLISH:
                return blockDef.englishName

    def setData(self, index, value, role=Qt.DisplayRole):
        row = index.row()
        column = index.column()
        blockDef = self.definedBlocks[row]
        if role == Qt.EditRole:
            try:
                if column == self.COL_ID:
                    blockDef.internalName = value
                if column == self.COL_META:
                    blockDef.meta = int(value)
                if column == self.COL_OPACITY:
                    blockDef.opacity = int(value)
                if column == self.COL_BRIGHTNESS:
                    blockDef.brightness = int(value)
                if column == self.COL_UNLOCALIZED:
                    blockDef.unlocalizedName = value
                if column == self.COL_ENGLISH:
                    blockDef.englishName = value
            except ValueError:
                log.exception("ValueError in setData")
                return False

            self.dataChanged.emit(index, index)
            return True

        return False

    def addBlock(self, internalName):
        log.info("Adding block %s", internalName)
        blockDef = BlockDefinition(internalName)
        self.beginInsertRows(QtCore.QModelIndex(), len(self.definedBlocks), len(self.definedBlocks))
        self.definedBlocks.append(blockDef)
        log.info("Appended")
        self.endInsertRows()

    def removeBlock(self, row):
        if row >= len(self.definedBlocks):
            return
        self.beginRemoveRows(QtCore.QModelIndex(), row, row)
        del self.definedBlocks[row]
        self.endRemoveRows()

    def setBlockModelPath(self, row, modelPath):
        blockDef = self.definedBlocks[row]
        blockDef.modelPath = modelPath


class ConfigureBlocksDialog(QtGui.QDialog, Ui_configureBlocks):
    def __init__(self, parent):
        super(ConfigureBlocksDialog, self).__init__(parent)
        self.setupUi(self)
        self.okButton.clicked.connect(self.accept)

        self.texListNameProxyModel = None
        self.texListZipProxyModel = None

        self.model = ConfigureBlocksItemModel()
        self.itemDelegate = ConfigureBlocksItemDelegate()

        self.blocksView.setModel(self.model)
        self.blocksView.setItemDelegate(self.itemDelegate)

        self.blocksView.clicked.connect(self.currentBlockClicked)

        self.internalNameBox.editTextChanged.connect(self.nameTextChanged)

        self.addBlockButton.clicked.connect(self.addBlock)
        self.removeBlockButton.clicked.connect(self.removeBlock)

        headerWidths = [
            48,
            200,
            75,
            60,
            60,
            75,
            180,
            180,
        ]
        for i, w in enumerate(headerWidths):
            self.blocksView.setColumnWidth(i, w)

        self.setModelControlsEnabled(False)
        self.modelNameBox.activated.connect(self.modelNameChanged)

        header = self.modelTexturesTable.horizontalHeader()
        header.resizeSection(0, 50)
        header.resizeSection(2, 40)
        header.setResizeMode(2, QtGui.QHeaderView.Fixed)
        header.setResizeMode(1, QtGui.QHeaderView.Stretch)

        self.textureList.clicked.connect(self.textureClicked)

        self.textureSearchBox.editTextChanged.connect(self.textureSearched)
        self.textureZipBox.activated[int].connect(self.textureZipChanged)

    def textureZipChanged(self, row):
        if self.texListZipProxyModel is None:
            return

        zipFilename = self.textureZipBox.itemData(row)
        self.texListZipProxyModel.setFilterFixedString(zipFilename)

    def textureSearched(self, value):
        if self.texListNameProxyModel is None:
            return

        self.texListNameProxyModel.setFilterRegExp(value)

    def getConfiguredBlocks(self):
        return self.model.definedBlocks

    def setModelControlsEnabled(self, enabled):
        self.modelNameBox.setEnabled(enabled)
        self.xRotationBox.setEnabled(enabled)
        self.yRotationBox.setEnabled(enabled)
        self.zRotationBox.setEnabled(enabled)
        self.modelTexturesTable.setEnabled(enabled)

    def currentBlockClicked(self, index):
        """
        Block in the top block list was clicked. Set up the model list,

        :param index:
        :type index:
        :return:
        :rtype:
        """
        if index.isValid():
            self.setModelControlsEnabled(True)
            modelPath = self.model.definedBlocks[index.row()].modelPath
            row = self.modelNameBox.findData(modelPath, Qt.UserRole)
            if row == -1:
                row = 0
            self.modelNameBox.setCurrentIndex(row)
            self.modelNameChanged(row)

    def nameTextChanged(self, text):
        self.addBlockButton.setEnabled(len(text) > 0)

    def modelNameChanged(self, row):
        blockIndex = self.blocksView.currentIndex()
        if not blockIndex.isValid():
            return

        modelPath = self.modelNameBox.itemData(row, Qt.UserRole)
        if modelPath is None:  # modelNameBox is empty?
            return
        self.model.setBlockModelPath(blockIndex.row(), modelPath)

        modelJson = json.load(self.session.resourceLoader.openStream(modelPath))

        # Parse block model and its parents and look for unbound textures
        elements = []
        textures = {}
        while modelJson is not None:
            if 'textures' in modelJson:
                textures.update(modelJson['textures'])
            if 'elements' in modelJson:
                elements.extend(modelJson['elements'])
            if 'parent' in modelJson:
                modelPath = "assets/minecraft/models/%s.json" % modelJson['parent']
                modelJson = json.load(self.session.resourceLoader.openStream(modelPath))
            else:
                modelJson = None

        unboundTextures = set()
        for element in elements:
            if 'faces' not in element:
                continue
            faces = element['faces']
            for side, face in faces.iteritems():
                if 'texture' in face:
                    texture = face['texture']
                    lasttex = texture
                    for i in range(30):
                        if texture.startswith("#"):
                            lasttex = texture
                            texture = textures.get(texture[1:], texture)
                        else:
                            break
                        if lasttex == texture:
                            break
                    if texture.startswith("#"):
                        unboundTextures.add(texture)

        self.modelTexturesTable.clearContents()
        self.modelTexturesTable.setRowCount(len(unboundTextures))
        blockDef = self.model.definedBlocks[blockIndex.row()]
        boundTextures = blockDef.modelTextures

        for row, texture in enumerate(sorted(unboundTextures)):

            texVarItem = QtGui.QTableWidgetItem(texture)
            texVarItem.setData(Qt.UserRole, texture)

            texturePath = boundTextures.get(texture, "Unbound")
            displayName = texturePath.rsplit("/", 1)[-1]
            texPathItem = QtGui.QTableWidgetItem(displayName)
            texPathItem.setData(Qt.UserRole, texturePath)

            self.modelTexturesTable.setItem(row, 0, texVarItem)
            self.modelTexturesTable.setItem(row, 1, texPathItem)

    def currentBlockDef(self):
        blockIndex = self.blocksView.currentIndex()
        if not blockIndex.isValid():
            return None
        return self.model.definedBlocks[blockIndex.row()]

    def textureClicked(self, index):
        blockDef = self.currentBlockDef()
        if blockDef is None:
            return

        textureRow = self.modelTexturesTable.currentRow()
        selectedItem = self.modelTexturesTable.item(textureRow, 0)
        if selectedItem is None:
            return

        texVar = selectedItem.data(Qt.UserRole)

        texturePath = index.data(Qt.UserRole)
        blockDef.modelTextures[texVar] = texturePath

        displayName = texturePath.rsplit("/", 1)[-1]
        texPathItem = QtGui.QTableWidgetItem(displayName)
        texPathItem.setData(Qt.UserRole, texturePath)
        self.modelTexturesTable.setItem(textureRow, 1, texPathItem)

    def showWithSession(self, session):
        self.session = session

        self.internalNameBox.clear()
        for internalName in session.unknownBlocks():
            self.internalNameBox.addItem(internalName, internalName)

        firstModels = []
        models = []
        self.modelNameBox.clear()
        for modelPath in session.resourceLoader.blockModelPaths():
            displayName = modelPath.replace("assets/minecraft/models/block/", "")
            displayName = displayName.replace(".json", "")

            # List commonly used models first
            if displayName == "cube_all":
                firstModels.insert(0, (displayName, modelPath))
            if displayName.startswith("cube"):
                firstModels.append((displayName, modelPath))
            else:
                models.append((displayName, modelPath))

        for displayName, modelPath in firstModels + models:
            self.modelNameBox.addItem(displayName, modelPath)

        texListModel = TextureListModel(session.resourceLoader)
        self.texListNameProxyModel = QtGui.QSortFilterProxyModel()
        self.texListNameProxyModel.setSourceModel(texListModel)
        self.texListNameProxyModel.setFilterCaseSensitivity(Qt.CaseInsensitive)

        self.texListZipProxyModel = QtGui.QSortFilterProxyModel()
        self.texListZipProxyModel.setSourceModel(self.texListNameProxyModel)
        self.texListZipProxyModel.setFilterRole(TextureListModel.ZipfilePathRole)

        self.textureList.setModel(self.texListZipProxyModel)

        self.textureZipBox.clear()
        self.textureZipBox.addItem("[All files]", "")
        for zipFilename in texListModel.zipfilePaths():
            self.textureZipBox.addItem(os.path.basename(zipFilename), zipFilename)

        self.show()

    def addBlock(self):
        internalName = self.internalNameBox.currentText()
        # index = self.internalNameBox.findText(internalName)
        # if index != -1:
        #     self.internalNameBox.removeItem(index)
        self.model.addBlock(internalName)

    def removeBlock(self):
        index = self.blocksView.currentIndex()
        if not index.isValid():
            return

        row = index.row()
        self.model.removeBlock(row)


    def done(self, result):
        self.model.writeToJson()
        super(ConfigureBlocksDialog, self).done(result)

    def close(self):
        self.model.writeToJson()
        super(ConfigureBlocksDialog, self).close()



