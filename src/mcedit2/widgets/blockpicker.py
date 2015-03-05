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
#
#class BlockTypeItemDelegate(QtGui.QStyledItemDelegate):
#    def __init__(self, model, listView, *args, **kwargs):
#        """
#
#        :type listView: QListView
#        """
#        super(BlockTypeItemDelegate, self).__init__(*args, **kwargs)
#        self.listView = listView
#        self.model = model
#        self.textureAtlas = model.editor.textureAtlas
#
#    def xpaint(self, painter, option, index):
#        """
#
#        :type painter: QtGui.QPainter
#        :type option: QStyleOptionViewItem
#        :type index: QModelIndex
#        """
#        #super(BlockTypeItemDelegate, self).paint(painter, option, index)
#        QtGui.QStyledItemDelegate.paint(self, painter, option, index)
#        #self.listWidget.style().drawPrimitive(QtGui.QStyle.PE_PanelItemViewItem, option, painter, None)
#        return
#
#        if False and option.state & QtGui.QStyle.State_Enabled:
#            widget = BlockTypesItemWidget(self.listView.model().data(index, role=Qt.UserRole), self.textureAtlas)
#            widget.setGeometry(option.rect)
#            widget.setMinimumSize(self.model.baseSize)
#            widget.setBackgroundRole(QtGui.QPalette.NoRole)
#            widget.setAutoFillBackground(False)
#            #painter.drawRoundedRect(option.rect, 0, 0)
#            img = QPixmap(option.rect.size())
#            img.fill(QtGui.QColor(0, 0, 0, 0))
#            #log.info("Paint: Active")
#
#            widget.render(img, renderFlags=widget.DrawChildren)
#
#            #if option.state & QtGui.QStyle.State_Selected:
#            #    brush = option.palette.highlight()
#            #    painter.fillRect(option.rect, brush)
#
#            painter.drawPixmap(option.rect.topLeft(), img)
#            #style = self.listWidget.style()
#            #style.drawPrimitive(style.PE_PanelItemViewItem, option, painter, widget)
#            #style.drawControl(style.CE_ItemViewItem, option, painter)
#
#
#
#    def sizeHint(self, option, index):
#        return QtCore.QSize(self.listView.width(), self.model.baseSize.height())
#
#_widgetWidth = 400
#
#class BlockTypeSetModel(QtCore.QAbstractListModel):
#
#    def __init__(self, editor, *args, **kwargs):
#        super(BlockTypeSetModel, self).__init__(*args, **kwargs)
#        self.allBlocks = list(editor.world.blocktypes)
#        self.editor = editor
#        widget = BlockTypesItemWidget(editor.world.blocktypes.Stone, editor.textureAtlas)
#        self.baseSize = QtCore.QSize(widget.sizeHint().width(), widget.sizeHint().height())
#
#    def rowCount(self, parent=QtCore.QModelIndex()):
#        return len(self.allBlocks)
#
#    def data(self, index, role=Qt.DisplayRole):
#        if role == Qt.DisplayRole:
#            return self.allBlocks[index.row()].displayName
#            #return self.makeIcon(index)
#        elif role == Qt.UserRole:
#            return self.allBlocks[index.row()]
#        else:
#            return None
#
#    def makeIcon(self, index):
#        widget = BlockTypesItemWidget(self.data(index, role=Qt.UserRole), self.editor.textureAtlas)
#        widget.setMinimumSize(self.baseSize)
#        widget.setBackgroundRole(QtGui.QPalette.NoRole)
#        widget.setAutoFillBackground(False)
#        #painter.drawRoundedRect(option.rect, 0, 0)
#        img = QPixmap(self.baseSize)
#        img.fill(QtGui.QColor(0, 0, 0, 0))
#        #log.info("Paint: Active")
#
#        widget.render(img, renderFlags=widget.DrawChildren)
#        return img
#        #icon = QtGui.QIcon(img)
#        #return icon

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

class BlockTypeListModel(QtCore.QAbstractListModel):
    def __init__(self, blocktypes, textureAtlas):
        super(BlockTypeListModel, self).__init__()
        self.blocktypes = blocktypes
        self.blocktypesList = list(blocktypes)
        self.textureAtlas = textureAtlas

    def rowCount(self, index):
        return len(self.blocktypes)

    def data(self, index, role):
        block = self.blocktypesList[index.row()]
        if role == Qt.DisplayRole:
            return block.displayName
        if role == Qt.UserRole:
            return block

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
        block = model.data(index, Qt.UserRole)  # index.data doesn't work because the BlockType doesn't survive the trip through Qt(?)
        log.info("Painting block list widget item in %s with %s", str(option.rect), block.displayName)
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
        self.specifiedItems = []
        self.multipleSelect = False
        self.setItemDelegate(BlockTypeListItemDelegate())

    _textureAtlas = None

    itemSelectionChanged = QtCore.Signal()

    def selectionChanged(self, selected, deselected):
        self.itemSelectionChanged.emit()

    @property
    def textureAtlas(self):
        return self._textureAtlas

    @textureAtlas.setter
    def textureAtlas(self, value):
        oldVal = self._textureAtlas
        self._textureAtlas = value
        if oldVal != value:
            self.updateList()

    _blocktypes = None

    @property
    def blocktypes(self):
        return self._blocktypes

    @blocktypes.setter
    def blocktypes(self, value):
        oldVal = self._blocktypes
        self._blocktypes = value
        if oldVal != value:
            self.updateList()

    _searchValue = None

    def setSearchString(self, val):
        self._searchValue = val
        ID = None
        meta = None
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
            for item in [i for i in self.specifiedItems if not i.isSelected()]:
                self.removeItemWidget(item)
                self.takeItem(self.row(item))
                self.specifiedItems.remove(item)

            block = self.blocktypes[ID, meta]
            if block not in self.blocktypes:
                item, itemWidget = self.createItem(block)

                self.addItem(item)
                self.setItemWidget(item, itemWidget)
                self.specifiedItems.append(item)

        for item in self.findItems("", Qt.MatchContains):
            matched = val.lower() in item.block.displayName.lower()
            matched |= val in item.block.internalName + item.block.blockState
            if ID is not None:
                matched |= (item.block.ID == ID and item.block.meta == meta)

            item.setHidden(not matched)

    def createItem(self, block):
        item = QtGui.QListWidgetItem()
        itemWidget = BlockTypesItemWidget([block], self.textureAtlas)
        item.setSizeHint(itemWidget.sizeHint())
        item.block = block
        item.widget = itemWidget
        if self.multipleSelect:
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
        return item, itemWidget

    def updateList(self):
        if self.textureAtlas is None:
            return
        if self.blocktypes is None:
            return

        log.info("Updating blocktype list widget (multiple=%s) for %s", self.multipleSelect, self.blocktypes)
        self.specifiedItems = []
        self.setModel(BlockTypeListModel(self.blocktypes, self.textureAtlas))

        # for block in self.blocktypes:
        #
        #     item, itemWidget = self.createItem(block)
        #
        #     self.addItem(item)
        #     self.setItemWidget(item, itemWidget)
        #
        # self.setMinimumWidth(self.sizeHintForColumn(0)+self.autoScrollMargin())
        # if self._searchValue:
        #     self.setSearchString(self._searchValue)


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
            self.listWidget.textureAtlas = self.editorSession.textureAtlas
            self.listWidget.blocktypes = self.editorSession.worldEditor.blocktypes
            if self.multipleSelect:
                self.selectedBlockList.textureAtlas = self.editorSession.textureAtlas

            self.searchField.clearEditText()

    @property
    def selectedBlocks(self):
        return [i.block for i in self.listWidget.selectedItems()]

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
