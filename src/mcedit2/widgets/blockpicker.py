"""
    blockpicker
"""
from __future__ import absolute_import, division, print_function, unicode_literals
from PySide import QtGui, QtCore
import logging
from PySide.QtCore import Qt
from mcedit2.util.load_ui import registerCustomWidget, load_ui
from mcedit2.widgets.blocktype_list import BlockTypePixmap
from mcedit2.widgets.layout import Row, Column
from mcedit2.worldview.iso import IsoWorldView
from mceditlib.blocktypes import BlockType
from mceditlib.schematic import createSchematic

log = logging.getLogger(__name__)

@registerCustomWidget
class BlockThumbView(QtGui.QWidget):
    def __init__(self, *a, **kw):
        super(BlockThumbView, self).__init__(minimumWidth=48, minimumHeight=48, *a, **kw)
        self.worldView = None

    _editorSession = None
    @property
    def editorSession(self):
        return self._editorSession

    @editorSession.setter
    def editorSession(self, editorSession):
        self._editorSession = editorSession
        self.updateView()

    _block = None
    @property
    def block(self):
        return self._block

    @block.setter
    def block(self, value):
        self._block = value
        self.updateView()

    def updateView(self):
        if None in (self.block, self.editorSession):
            return

        editor = createSchematic((1, 1, 1), blocktypes=self.editorSession.worldEditor.blocktypes)
        dim = editor.getDimension()
        dim.setBlocks(0, 0, 0, self.block)
        self.worldView = IsoWorldView(dim, self.editorSession.textureAtlas, sharedGLWidget=self.editorSession.editorTab.miniMap)

        self.setLayout(Row(self.worldView))

class BlockTypeIcon(QtGui.QLabel):
    def __init__(self, block, textureAtlas, *args, **kwargs):
        super(BlockTypeIcon, self).__init__(*args, **kwargs)
        pixmap = BlockTypePixmap(block, textureAtlas)
        self.setMinimumSize(32, 32)
        self.setPixmap(pixmap)

class BlockTypesItemWidget(QtGui.QWidget):
    def __init__(self, blocks=None, textureAtlas=None):
        super(BlockTypesItemWidget, self).__init__()
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
            frame.setMinimumSize(64, 64)
            iconLimit = 16

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
                y += 4

            nameLimit = 6
            remaining = len(blocks) - nameLimit
            blocksToName = blocks[:nameLimit]
            iconNames = ", ".join(b.displayName for b in blocksToName)
            if remaining > 0:
                iconNames += " and %d more..." % remaining

            namesLabel = QtGui.QLabel(iconNames, wordWrap=True)
            self.childWidgets.append(namesLabel)

            self.mainLayout = Row(frame, namesLabel)
            self.layout().addLayout(self.mainLayout)

        self.setSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Minimum)


class BlockTypeListFilterModel(QtGui.QSortFilterProxyModel):
    def __init__(self, sourceModel):
        super(BlockTypeListFilterModel, self).__init__()
        self.setSourceModel(sourceModel)
        self.setFilterKeyColumn(0)
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)

    def setSearchString(self, val):
        self.setFilterRegExp(val)

    @property
    def textureAtlas(self):
        return self.sourceModel().textureAtlas

    @property
    def blocktypes(self):
        return self.sourceModel().blocktypes

class BlockTypeListModel(QtCore.QAbstractListModel):
    def __init__(self, blocktypes, textureAtlas):
        super(BlockTypeListModel, self).__init__()
        self.blocktypes = blocktypes
        self.blocktypesList = list(blocktypes)
        self.textureAtlas = textureAtlas
        self.customBlocks = []

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
            return block.internalName, block.blockState

    def addCustomBlock(self, block):
        index = len(self.blocktypes) + len(self.customBlocks)
        self.beginInsertRows(QtCore.QModelIndex(), index, index)
        self.customBlocks.append(block)
        self.endInsertRows()

    def removeCustomBlocks(self):
        self.beginRemoveRows(QtCore.QModelIndex(), len(self.blocktypes), len(self.blocktypes) + len(self.customBlocks) - 1)
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
        internalName, blockState = index.data(Qt.UserRole)
        block = model.blocktypes[internalName, blockState]
        if option.state & QtGui.QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        self.itemWidget.setGeometry(option.rect)
        self.itemWidget.setBlocks([block])
        self.itemWidget.setTextureAtlas(model.textureAtlas)
        self.itemWidget.render(painter,
                               painter.deviceTransform().map(option.rect.topLeft()), # QTBUG-26694
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
        self.multipleSelect = False
        self.setItemDelegate(BlockTypeListItemDelegate())

    itemSelectionChanged = QtCore.Signal()

    def selectionChanged(self, selected, deselected):
        self.itemSelectionChanged.emit()

    def selectedBlocks(self):
        model = self.model()
        if model is None:
            return []

        selectionModel = self.selectionModel()
        indexes = selectionModel.selectedIndexes()
        blocks = [model.blocktypes[tuple(model.data(idx, Qt.UserRole))] for idx in indexes]
        return blocks

    def clearSelection(self):
        self.selectionModel().clear()


class BlockTypePicker(QtGui.QDialog):
    def __init__(self, *args, **kwargs):
        self.multipleSelect = kwargs.pop('multipleSelect', False)
        super(BlockTypePicker, self).__init__(*args, **kwargs)
        self._editorSession = None

        if self.multipleSelect:
            load_ui("block_picker_multiple.ui", baseinstance=self)
        else:
            load_ui("block_picker.ui", baseinstance=self)

        self.selectButton.clicked.connect(self.accept)
        self.cancelButton.clicked.connect(self.reject)
        self.searchField.editTextChanged.connect(self.setSearchString)
        assert isinstance(self.listWidget, QtGui.QListView)
        self.listWidget.itemSelectionChanged.connect(self.selectionDidChange)
        if not self.multipleSelect:
            self.listWidget.doubleClicked.connect(self.accept)
        else:
            self.listWidget.multipleSelect = True

        self.setSizeGripEnabled(True)
        self.listModel = None
        self.filterModel = None


    def exec_(self):
        self.searchField.setFocus()
        return super(BlockTypePicker, self).exec_()

    def selectionDidChange(self):
        if len(self.selectedBlocks) == 0:
            self.nameLabel.setText("[No selection]")
            self.idLabel.setText("")
            self.internalNameLabel.setText("")
            self.brightnessLabel.setText("")
            self.opacityLabel.setText("")
            self.rendertypeLabel.setText("")
        elif len(self.selectedBlocks) == 1:
            block = self.selectedBlocks[0]
            log.info("Block=%s", (block.ID, block.meta))
            self.nameLabel.setText("%s" % block.displayName)
            self.internalNameLabel.setText("(%d:%d) %s" % (block.ID, block.meta, block.internalName))
            self.brightnessLabel.setText("Brightness: %d" % block.brightness)
            self.opacityLabel.setText("Opacity: %d" % block.opacity)
            self.rendertypeLabel.setText("Render: %d" % block.renderType)
            pixmap = BlockTypePixmap(block, self.editorSession.textureAtlas)
            self.blockThumb.setPixmap(pixmap)
        else:
            self.nameLabel.setText("[Multiple selection]")
            self.idLabel.setText("")
            self.internalNameLabel.setText("")
            self.brightnessLabel.setText("")
            self.opacityLabel.setText("")
            self.rendertypeLabel.setText("")

        if self.multipleSelect:
            self.selectedBlockList.blocktypes = self.selectedBlocks

    @property
    def editorSession(self):
        return self._editorSession

    @editorSession.setter
    def editorSession(self, editorSession):
        """

        :type editorSession: EditorSession
        """
        self._editorSession = editorSession
        if self.editorSession:

            log.info("Updating blocktype list widget (multiple=%s) for %s", self.listWidget.multipleSelect, editorSession.worldEditor.blocktypes)
            self.listWidget.specifiedItems = []
            self.listModel = BlockTypeListModel(editorSession.worldEditor.blocktypes, editorSession.textureAtlas)
            self.filterModel = BlockTypeListFilterModel(self.listModel)
            self.listWidget.setModel(self.filterModel)

            # if self.multipleSelect:
            #     self.selectedBlockList.textureAtlas = self.editorSession.textureAtlas

            self.searchField.clearEditText()

    @property
    def blocktypes(self):
        return self.editorSession.worldEditor.blocktypes

    @property
    def selectedBlocks(self):
        return self.listWidget.selectedBlocks()

    @selectedBlocks.setter
    def selectedBlocks(self, val):
        self.listWidget.clearSelection()
        found = False
        # for i in range(self.listWidget.count()):
        #     item = self.listWidget.item(i)
        #     if item.block in val:
        #         if self.multipleSelect:
        #             self.listWidget.setCurrentItem(item, QtGui.QItemSelectionModel.Toggle)
        #         else:
        #             self.listWidget.setCurrentItem(item)
        #         found = True
        # if found:
        #     self.selectionDidChange()

    def setSearchString(self, val):
        self.listWidget.setSearchString(val)

    _searchString = None

    def setSearchString(self, val):
        self._searchString = val
        try:
            if ":" in val:
                ID, meta = val.split(":")
            else:
                ID = val
                meta = 0

            ID = int(ID)
            meta = int(meta)

        except ValueError:
            pass
        else:
            self.listModel.removeCustomBlocks()

            block = self.blocktypes[ID, meta]
            if block not in self.blocktypes:
                self.listModel.addCustomBlock(block)

        self.filterModel.setSearchString(val)


_sharedPicker = None
_sharedMultiPicker = None


def getBlockTypePicker(multipleSelect):
    global _sharedPicker, _sharedMultiPicker
    if multipleSelect:
        if _sharedMultiPicker is None:
            _sharedMultiPicker = BlockTypePicker(multipleSelect=True)
        return _sharedMultiPicker

    else:
        if _sharedPicker is None:
            _sharedPicker = BlockTypePicker()
        return _sharedPicker

@registerCustomWidget
class BlockTypeButton(QtGui.QPushButton):
    def __init__(self, *args, **kwargs):
        self.multipleSelect = kwargs.pop('multipleSelect', False)
        super(BlockTypeButton, self).__init__(*args, **kwargs)

        self._blocks = []
        self.clicked.connect(self.showPicker)
        self.picker = getBlockTypePicker(self.multipleSelect)
        self.setLayout(QtGui.QStackedLayout())
        self._viewWidget = None
        self.setSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Fixed)

    blocksChanged = QtCore.Signal(list)

    _editor = None

    @property
    def editorSession(self):
        return self._editor

    @editorSession.setter
    def editorSession(self, editorSession):
        """

        :type editorSession: EditorSession
        """
        self._editor = editorSession
        self.picker.editorSession = editorSession
        self.updateView()

    def updateView(self):
        if self.editorSession and self.blocks:
            log.info("Updating button with %s", self.blocks)

            layout = self.layout()
            if self._viewWidget:
                layout.removeWidget(self._viewWidget)
            self._viewWidget = BlockTypesItemWidget(self.blocks, self.editorSession.textureAtlas)
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

        if self._blocks != value:
            self.blocksChanged.emit(value)
        self._blocks = value
        self.updateView()

    def showPicker(self):
        self.picker.selectedBlocks = self.blocks
        if self.picker.exec_():
            self.blocks = self.picker.selectedBlocks
            log.info("Picked block %s", self.block)
