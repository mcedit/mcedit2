"""
    blockpicker
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import re

from PySide import QtGui, QtCore
from PySide.QtCore import Qt

from mcedit2.util.load_ui import registerCustomWidget, load_ui
from mcedit2.widgets.blocktype_list import BlockTypePixmap
from mcedit2.widgets.layout import Row, Column
#from mcedit2.worldview.iso import IsoWorldView
from mceditlib.blocktypes import BlockType
#from mceditlib.schematic import createSchematic

log = logging.getLogger(__name__)
#
# @registerCustomWidget
# class BlockThumbView(QtGui.QWidget):
#     def __init__(self, *a, **kw):
#         super(BlockThumbView, self).__init__(minimumWidth=48, minimumHeight=48, *a, **kw)
#         self.worldView = None
#
#     _textureAtlas = None
#     @property
#     def textureAtlas(self):
#         return self._textureAtlas
#
#     @textureAtlas.setter
#     def textureAtlas(self, textureAtlas):
#         self._textureAtlas = textureAtlas
#         self.updateView()
#
#     _block = None
#     @property
#     def block(self):
#         return self._block
#
#     @block.setter
#     def block(self, value):
#         self._block = value
#         self.updateView()
#
#     def updateView(self):
#         if None in (self.block, self.textureAtlas):
#             return
#
#         editor = createSchematic((1, 1, 1), blocktypes=self.textureAtlas.blocktypes)
#         dim = editor.getDimension()
#         dim.setBlocks(0, 0, 0, self.block)
#         self.worldView = IsoWorldView(dim, self.textureAtlas, sharedGLWidget=self.editorSession.editorTab.miniMap)
#
#         self.setLayout(Row(self.worldView))


class BlockTypeIcon(QtGui.QLabel):
    def __init__(self, block, textureAtlas, *args, **kwargs):
        super(BlockTypeIcon, self).__init__(*args, **kwargs)
        pixmap = BlockTypePixmap(block, textureAtlas)
        self.setMinimumSize(32, 32)
        self.setPixmap(pixmap)


@registerCustomWidget
class BlockTypesItemWidget(QtGui.QWidget):
    def __init__(self, parent=None, blocks=None, textureAtlas=None):
        super(BlockTypesItemWidget, self).__init__(parent)
        self.childWidgets = []
        self.mainLayout = None
        self.blocks = blocks
        self.textureAtlas = textureAtlas
        self.setLayout(Column())
        self.updateContents()

    def setBlocks(self, blocks):
        if blocks != self.blocks:
            self.blocks = blocks
            self.updateContents()

    def setTextureAtlas(self, textureAtlas):
        if textureAtlas != self.textureAtlas:
            self.textureAtlas = textureAtlas
            self.updateContents()

    def updateContents(self):
        if self.blocks is None or self.textureAtlas is None:
            return

        for child in self.childWidgets:
            child.setParent(None)
        self.childWidgets = []
        if self.mainLayout:
            self.layout().takeAt(0)
        blocks = self.blocks
        textureAtlas = self.textureAtlas

        if len(blocks) == 0:
            return

        if len(blocks) == 1:
            block = blocks[0]
            blockIcon = BlockTypeIcon(block, textureAtlas)
            self.childWidgets.append(blockIcon)

            nameLabel = QtGui.QLabel(block.displayName)
            self.childWidgets.append(nameLabel)

            internalNameLimit = 60
            internalName = block.internalName + block.blockState
            if len(internalName) > internalNameLimit:
                internalName = internalName[:internalNameLimit-3]+"..."

            internalNameLabel = QtGui.QLabel("(%d:%d) %s" % (block.ID, block.meta, internalName), enabled=False)
            self.childWidgets.append(internalNameLabel)

            parentTypeLabel = QtGui.QLabel("")
            self.childWidgets.append(parentTypeLabel)

            if block.meta != 0:
                try:
                    parentBlock = block.blocktypeSet[block.internalName]
                    if parentBlock.displayName != block.displayName:
                        parentTypeLabel.setText("<font color='blue'>%s</font>" % parentBlock.displayName)
                except KeyError:  # no parent block; parent block is not meta=0; block was ID:meta typed in
                    pass

            labelsColumn = Column(Row(nameLabel, None, parentTypeLabel),
                                  internalNameLabel)

            self.mainLayout = Row(blockIcon, (labelsColumn, 1))
            self.layout().addLayout(self.mainLayout)

            # row.setSizeConstraint(QtGui.QLayout.SetFixedSize)
        else:
            frame = QtGui.QFrame()
            self.childWidgets.append(frame)
            vSpace = 4
            frameHeight = 64
            frame.setMinimumSize(64, frameHeight)
            iconLimit = int((frameHeight - 32) / vSpace) + 1

            blocksToIcon = blocks[:iconLimit]
            icons = [BlockTypeIcon(b, textureAtlas) for b in blocksToIcon]
            self.childWidgets.extend(icons)
            x = 0
            y = 0
            for i, icon in enumerate(icons):
                # icon.setMinimumSize(32, 32)
                icon.setParent(frame)
                icon.setGeometry(x, y, 32, 32)
                icon.setFrameStyle(icon.Box)
                icon.setLineWidth(1)
                x += 18
                if i % 2:
                    x -= 32
                y += vSpace

            nameLimit = 6
            remaining = len(blocks) - nameLimit
            blocksToName = blocks[:nameLimit]
            iconNames = ", ".join(b.displayName for b in blocksToName)
            if remaining > 0:
                iconNames += " and %d more..." % remaining

            namesLabel = QtGui.QLabel(iconNames, wordWrap=True)
            self.childWidgets.append(namesLabel)

            self.mainLayout = Row(frame, (Column(namesLabel, None), 1))
            self.layout().addLayout(self.mainLayout)

        self.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)


class BlockTypeListFilterModel(QtGui.QSortFilterProxyModel):
    def __init__(self, sourceModel):
        super(BlockTypeListFilterModel, self).__init__()
        self.setSourceModel(sourceModel)
        self.setFilterKeyColumn(0)
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.searchID = None
        self.searchMeta = None

    def setSearchString(self, val):
        self.searchID = None
        self.searchMeta = None
        self.setFilterRegExp(val)

    def setSearchIdMeta(self, ID, meta):
        self.searchID = ID
        self.searchMeta = meta
        self.setFilterRegExp(None)

    def filterAcceptsRow(self, row, parentIndex):
        if self.searchID is None:
            return super(BlockTypeListFilterModel, self).filterAcceptsRow(row, parentIndex)
        else:
            child = self.sourceModel().index(row, 0, parentIndex)
            ID, meta = child.data(Qt.UserRole)
            return ID == self.searchID and meta == self.searchMeta

    @property
    def textureAtlas(self):
        return self.sourceModel().textureAtlas

    @property
    def blocktypes(self):
        return self.sourceModel().blocktypes


class SelectedBlockTypesProxyModel(QtGui.QSortFilterProxyModel):
    def __init__(self, sourceModel):
        super(SelectedBlockTypesProxyModel, self).__init__()
        self.setSourceModel(sourceModel)
        self._selectedBlocks = []

    def filterAcceptsRow(self, row, parentIndex):
        child = self.sourceModel().index(row, 0, parentIndex)
        ID, meta = child.data(Qt.UserRole)
        return (ID, meta) in self._selectedBlocks

    def addBlocks(self, blocks):
        for block in blocks:
            self._selectedBlocks.append((block.ID, block.meta))
        self.reset()

    def removeBlocks(self, blocks):
        for block in blocks:
            self._selectedBlocks.remove((block.ID, block.meta))
        self.reset()

    def selectedBlocks(self):
        return [self.sourceModel().blocktypes[ID, meta] for ID, meta in self._selectedBlocks]

    def setSelectedBlocks(self, blocks):
        self._selectedBlocks = [(block.ID, block.meta) for block in blocks]
        self.reset()

    @property
    def textureAtlas(self):
        return self.sourceModel().textureAtlas

    @property
    def blocktypes(self):
        return self.sourceModel().blocktypes


class BlockTypeListModel(QtCore.QAbstractListModel):
    def __init__(self, textureAtlas):
        super(BlockTypeListModel, self).__init__()
        self.textureAtlas = textureAtlas
        self.blocktypesList = list(self.blocktypes)
        self.customBlocks = []

    @property
    def blocktypes(self):
        return self.textureAtlas.blocktypes

    def rowCount(self, index):
        return len(self.blocktypes) + len(self.customBlocks)

    def data(self, index, role):
        row = index.row()
        if row >= len(self.blocktypes):
            block = self.customBlocks[row - len(self.blocktypes)]
        else:
            block = self.blocktypesList[index.row()]

        if role == Qt.DisplayRole:
            return block.displayName
        if role == Qt.UserRole:
            return block.ID, block.meta

    def addCustomBlock(self, block):
        if block in self.customBlocks:
            return
        index = len(self.blocktypes) + len(self.customBlocks)
        self.beginInsertRows(QtCore.QModelIndex(), index, index)
        self.customBlocks.append(block)
        self.endInsertRows()

    def removeCustomBlocks(self):
        self.beginRemoveRows(QtCore.QModelIndex(),
                             len(self.blocktypes),
                             len(self.blocktypes) + len(self.customBlocks) - 1)
        self.customBlocks = []
        self.endRemoveRows()


class BlockTypeListItemDelegate(QtGui.QAbstractItemDelegate):
    def __init__(self):
        super(BlockTypeListItemDelegate, self).__init__()
        self.itemWidget = BlockTypesItemWidget()

    def paint(self, painter, option, index):
        """

        :param painter:
        :type painter: QtGui.QPainter
        :param option:
        :type option:
        :param index:
        :type index:
        :return:
        :rtype:
        """
        model = index.model()
        ID, meta = index.data(Qt.UserRole)
        block = model.blocktypes[ID, meta]
        if option.state & QtGui.QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        self.itemWidget.setGeometry(option.rect)
        self.itemWidget.setBlocks([block])
        self.itemWidget.setTextureAtlas(model.textureAtlas)
        self.itemWidget.render(painter,
                               painter.deviceTransform().map(option.rect.topLeft()),  # QTBUG-26694
                               renderFlags=QtGui.QWidget.DrawChildren)

    def sizeHint(self, option, index):
        # log.info("Getting sizeHint for block list widget item")
        # model = index.model()
        # block = index.data()
        # self.itemWidget.blocks = [block]
        # self.itemWidget.textureAtlas = model.textureAtlas
        return QtCore.QSize(200, 72)


@registerCustomWidget
class BlockTypeListWidget(QtGui.QListView):

    def __init__(self, *args, **kwargs):
        super(BlockTypeListWidget, self).__init__(*args, **kwargs)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setItemDelegate(BlockTypeListItemDelegate())

    blockSelectionChanged = QtCore.Signal(list, list)

    def selectionChanged(self, selected, deselected):
        model = self.model()
        if model is None:
            return
        selectedBlocks = [model.blocktypes[tuple(model.data(index, Qt.UserRole))] for index in selected.indexes()]
        deselectedBlocks = [model.blocktypes[tuple(model.data(index, Qt.UserRole))] for index in deselected.indexes()]

        self.blockSelectionChanged.emit(selectedBlocks, deselectedBlocks)

    def selectedBlocks(self):
        model = self.model()
        if model is None:
            return
        selectionModel = self.selectionModel()

        return [model.blocktypes[tuple(model.data(index, Qt.UserRole))]
                for index in selectionModel.selectedIndexes()]

    def setSelectedBlocks(self, blocks):
        model = self.model()
        if model is None:
            return []

        selectionModel = self.selectionModel()
        selectionModel.clear()

        root = QtCore.QModelIndex()
        keySet = {(block.ID, block.meta) for block in blocks}
        for row in range(model.rowCount()):
            index = model.index(row, 0, root)
            key = tuple(model.data(index, Qt.UserRole))
            if key in keySet:
                selectionModel.select(index, QtGui.QItemSelectionModel.Select)

    def clearSelection(self):
        self.selectionModel().clear()


class BlockTypePicker(QtGui.QDialog):
    def __init__(self, multipleSelect=False):
        super(BlockTypePicker, self).__init__()

        self.multipleSelect = multipleSelect
        if self.multipleSelect:
            load_ui("block_picker_multiple.ui", baseinstance=self)
        else:
            load_ui("block_picker.ui", baseinstance=self)

        self.selectButton.clicked.connect(self.accept)
        self.cancelButton.clicked.connect(self.reject)
        self.searchField.editTextChanged.connect(self.setSearchString)
        self.listWidget.blockSelectionChanged.connect(self.selectionDidChange)

        if not self.multipleSelect:
            self.listWidget.doubleClicked.connect(self.accept)
        else:
            self.listWidget.multipleSelect = True

        self.setSizeGripEnabled(True)
        self.listModel = None
        self.filterModel = None
        self.selectedTypesModel = None

    def exec_(self):
        self.searchField.setFocus()
        return super(BlockTypePicker, self).exec_()

    def selectionDidChange(self, selectedBlocks, deselectedBlocks):
        if self.multipleSelect:
            self.selectedTypesModel.addBlocks(selectedBlocks)
            self.selectedTypesModel.removeBlocks(deselectedBlocks)
        else:
            self.selectedTypesModel.setSelectedBlocks(selectedBlocks[:1])
        blocks = self.selectedTypesModel.selectedBlocks()

        self.selectedBlockTypesWidget.setBlocks(blocks)

    _textureAtlas = None

    @property
    def textureAtlas(self):
        return self._textureAtlas

    @textureAtlas.setter
    def textureAtlas(self, textureAtlas):
        """

        :type textureAtlas: mcedit2.rendering.textureatlas.TextureAtlas
        """
        self._textureAtlas = textureAtlas
        self.updatePicker()

    @property
    def blocktypes(self):
        return self.textureAtlas.blocktypes

    def updatePicker(self):
        if self.textureAtlas is not None:
            log.info("Updating blocktype list widget (multiple=%s) for %s",
                     self.multipleSelect, self.blocktypes)

            self.selectedBlockTypesWidget.setTextureAtlas(self.textureAtlas)

            self.listModel = BlockTypeListModel(self.textureAtlas)
            self.filterModel = BlockTypeListFilterModel(self.listModel)
            self.listWidget.setModel(self.filterModel)
            self.selectedTypesModel = SelectedBlockTypesProxyModel(self.listModel)
            if self.multipleSelect:
                self.selectedBlockList.setModel(self.selectedTypesModel)

            self.searchField.clearEditText()

    @property
    def selectedBlocks(self):
        return self.selectedTypesModel.selectedBlocks()

    @selectedBlocks.setter
    def selectedBlocks(self, val):
        self.listWidget.setSelectedBlocks(val)
        self.selectedTypesModel.setSelectedBlocks(val)

    def setSearchString(self, val):
        # Changing the filterModel's search settings clears listWidget's selection
        # So we have to work around it by disconnecting from the selection change, and then
        # restoring the selection after changing the settings.

        self.listWidget.blockSelectionChanged.disconnect(self.selectionDidChange)
        selectedBlocks = self.selectedBlocks

        match = re.match(r'([0-9]+)(?::([0-9]+))?', val)
        if match:
            ID = int(match.group(1))
            meta = int(match.group(2) or 0)

            block = self.blocktypes[ID, meta]
            if block not in self.blocktypes:
                log.info("Adding custom block %s", block)
                self.listModel.addCustomBlock(block)

            self.filterModel.setSearchIdMeta(ID, meta)
        else:
            self.filterModel.setSearchString(val)

        self.listWidget.blockSelectionChanged.connect(self.selectionDidChange)
        self.selectedBlocks = selectedBlocks


@registerCustomWidget
class BlockTypeButton(QtGui.QPushButton):
    def __init__(self, *args, **kwargs):
        self.multipleSelect = kwargs.pop('multipleSelect', False)
        super(BlockTypeButton, self).__init__(*args, **kwargs)

        self._blocks = []
        self.clicked.connect(self.showPicker)
        self.picker = BlockTypePicker(self.multipleSelect)
        self.setLayout(QtGui.QStackedLayout())
        self._viewWidget = None
        self.setSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Fixed)

    blocksChanged = QtCore.Signal(list)

    _editorSession = None

    @property
    def editorSession(self):
        return self._editorSession

    @editorSession.setter
    def editorSession(self, editorSession):
        """

        :type editorSession: mcedit2.editorsession.EditorSession
        """
        self._editorSession = editorSession
        self.picker.textureAtlas = editorSession.textureAtlas
        editorSession.configuredBlocksChanged.connect(self.configuredBlocksDidChange)
        self.updateView()

    def configuredBlocksDidChange(self):
        self.picker.textureAtlas = self.editorSession.textureAtlas
        self.updateView()

    def updateView(self):
        if self.editorSession and self.blocks:
            log.info("Updating button with %s", self.blocks)

            layout = self.layout()
            if self._viewWidget:
                layout.removeWidget(self._viewWidget)
            self._viewWidget = BlockTypesItemWidget(self, self.blocks, self.editorSession.textureAtlas)
            layout.addWidget(self._viewWidget)

            assert isinstance(layout, QtGui.QLayout)
            self.setMinimumHeight(self._viewWidget.sizeHint().height())

    @property
    def block(self):
        return self._blocks[0] if len(self._blocks) else None

    @block.setter
    def block(self, value):
        self.blocks = [value]

    @property
    def blocks(self):
        return self._blocks

    @blocks.setter
    def blocks(self, value):
        value = [self.editorSession.worldEditor.blocktypes[block]
                 if not isinstance(block, BlockType)
                 else block
                 for block in value]

        old = self._blocks
        self._blocks = value
        if old != value:
            self.blocksChanged.emit(value)
        self.updateView()

    def showPicker(self):
        self.picker.selectedBlocks = self.blocks
        if self.picker.exec_():
            self.blocks = self.picker.selectedBlocks
            log.info("Picked block %s", self.block)
