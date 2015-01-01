"""
    blockpicker
"""
from __future__ import absolute_import, division, print_function, unicode_literals
from PySide import QtGui, QtCore
import logging
from PySide.QtCore import Qt
from PySide.QtGui import QPixmap
from mcedit2.util.load_ui import registerCustomWidget, load_ui
from mcedit2.widgets.blocktype_list import BlockTypePixmap
from mcedit2.widgets.layout import Row, Column
from mcedit2.worldview.iso import IsoWorldView
from mceditlib.blocktypes import BlockType
from mceditlib.schematic import SchematicFileAdapter
from mceditlib.worldeditor import WorldEditor

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

        blockworld = SchematicFileAdapter((1, 1, 1), blocktypes=self.editorSession.worldEditor.blocktypes)
        editor = WorldEditor(adapter=blockworld)
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
    def __init__(self, blocks, textureAtlas):
        super(BlockTypesItemWidget, self).__init__()
        if len(blocks) == 1:
            block = blocks[0]
            self.blockIcon = BlockTypeIcon(block, textureAtlas)

            nameLabel = QtGui.QLabel(block.displayName)

            internalNameLimit = 60
            internalName = block.internalName + block.blockState
            if len(internalName) > internalNameLimit:
                internalName = internalName[:internalNameLimit-3]+"..."

            internalNameLabel = QtGui.QLabel("(%d:%d) %s" % (block.ID, block.meta, internalName), enabled=False)

            parentTypeLabel = QtGui.QLabel("")
            if block.meta != 0:
                parentBlock = block.blocktypeSet[block.internalName]
                if parentBlock.displayName != block.displayName:
                    parentTypeLabel.setText("<font color='blue'>%s</font>" % parentBlock.displayName)

            labelsColumn = Column(Row(nameLabel, None, parentTypeLabel),
                                  internalNameLabel)

            row = Row(self.blockIcon, (labelsColumn, 1))
            self.setLayout(row)

            # row.setSizeConstraint(QtGui.QLayout.SetFixedSize)
        else:
            frame = QtGui.QFrame()
            frame.setMinimumSize(64, 64)
            iconLimit = 16

            blocksToIcon = blocks[:iconLimit]
            icons = [BlockTypeIcon(b, textureAtlas) for b in blocksToIcon]
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
            self.setLayout(Row(frame, QtGui.QLabel(iconNames, wordWrap=True)))

        self.setSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Minimum)
        self.adjustSize()

@registerCustomWidget
class BlockTypeListWidget(QtGui.QListWidget):

    def __init__(self, *args, **kwargs):
        super(BlockTypeListWidget, self).__init__(*args, **kwargs)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

    _textureAtlas = None

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
        for item in self.findItems("", Qt.MatchContains):
            item.setHidden(val.lower() not in item.block.displayName.lower())

    def updateList(self):
        if self.textureAtlas is None:
            return
        if self.blocktypes is None:
            return

        self.clear()

        for block in self.blocktypes:
            if self._searchValue:
                for s in block.displayName, block.internalName:
                    if self._searchValue not in s:
                        continue

            item = QtGui.QListWidgetItem()
            itemWidget = BlockTypesItemWidget([block], self.textureAtlas)
            item.setSizeHint(itemWidget.sizeHint())
            item.block = block
            item.widget = itemWidget

            self.addItem(item)
            self.setItemWidget(item, itemWidget)

        self.setMinimumWidth(self.sizeHintForColumn(0)+self.autoScrollMargin())


class BlockTypePicker(QtGui.QDialog):
    def __init__(self, *args, **kwargs):
        super(BlockTypePicker, self).__init__(*args, **kwargs)
        self._editorSession = None

        load_ui("block_picker.ui", baseinstance=self)
        self.selectButton.clicked.connect(self.accept)
        self.cancelButton.clicked.connect(self.reject)
        self.searchField.editTextChanged.connect(self.setSearchString)
        assert isinstance(self.listWidget, QtGui.QListWidget)
        self.listWidget.itemSelectionChanged.connect(self.selectionDidChange)
        self.listWidget.doubleClicked.connect(self.accept)
        self.setSizeGripEnabled(True)

    def selectionDidChange(self):
        if not self.multipleSelect:
            if len(self.selectedBlocks):
                block = self.selectedBlocks[0]
                self.nameLabel.setText("%s" % block.displayName)
                self.internalNameLabel.setText("(%d:%d) %s" % (block.ID, block.meta, block.internalName))
                self.brightnessLabel.setText("Brightness: %d" % block.brightness)
                self.opacityLabel.setText("Opacity: %d" % block.opacity)
                self.rendertypeLabel.setText("Render: %d" % block.renderType)
                pixmap = BlockTypePixmap(block, self.editorSession.textureAtlas)
                self.blockThumb.setPixmap(pixmap)
            else:
                self.nameLabel.setText("")
                self.idLabel.setText("")
                self.internalNameLabel.setText("")
                self.brightnessLabel.setText("")
                self.opacityLabel.setText("")
                self.rendertypeLabel.setText("")

    @property
    def multipleSelect(self):
        return self.listWidget.selectionMode() == self.listWidget.MultiSelection

    @multipleSelect.setter
    def multipleSelect(self, value):
        if value:
            self.listWidget.setSelectionMode(self.listWidget.MultiSelection)
        else:
            self.listWidget.setSelectionMode(self.listWidget.SingleSelection)

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

    @property
    def selectedBlocks(self):
        return [i.block for i in self.listWidget.selectedItems()]

    @selectedBlocks.setter
    def selectedBlocks(self, val):
        self.listWidget.clearSelection()
        found = False
        for item in self.listWidget.findItems("", Qt.MatchContains):
            if item.block in val:
                if self.multipleSelect:
                    self.listWidget.setCurrentItem(item, QtGui.QItemSelectionModel.Current)
                else:
                    self.listWidget.setCurrentItem(item)
                found = True
        if found:
            self.selectionDidChange()

    def setSearchString(self, val):
        self.listWidget.setSearchString(val)

_sharedPicker = None

def getBlockTypePicker():
    global _sharedPicker
    if _sharedPicker is None:
        _sharedPicker = BlockTypePicker()
    return _sharedPicker

@registerCustomWidget
class BlockTypeButton(QtGui.QPushButton):
    def __init__(self, *args, **kwargs):
        super(BlockTypeButton, self).__init__(*args, **kwargs)
        self._blocks = []
        self.clicked.connect(self.showPicker)
        self.picker = getBlockTypePicker()
        self.setLayout(QtGui.QStackedLayout())
        self._viewWidget = None
        self.setSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Minimum)

    blocksChanged = QtCore.Signal(list)

    @property
    def multipleSelect(self):
        return self.picker.multipleSelect

    @multipleSelect.setter
    def multipleSelect(self, value):
        self.picker.multipleSelect = value

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
