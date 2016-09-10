"""
    blockpicker_util
"""
from __future__ import absolute_import, division, print_function, unicode_literals

import logging

from PySide import QtGui, QtCore
from PySide.QtCore import Qt

from mcedit2.widgets.blocktype_list import BlockTypePixmap
from mcedit2.widgets.layout import Column, Row

log = logging.getLogger(__name__)


class BlockTypeIcon(QtGui.QLabel):
    def __init__(self, block=None, textureAtlas=None, *args, **kwargs):
        super(BlockTypeIcon, self).__init__(*args, **kwargs)
        self.setMinimumSize(32, 32)
        self.setBlock(block)
        self.setTextureAtlas(textureAtlas)

    _block = None
    _textureAtlas = None

    def setBlock(self, block):
        self._block = block
        self.setLineWidth(1 if block is not None else 0)
        self.updatePixmap()

    def setTextureAtlas(self, textureAtlas):
        self._textureAtlas = textureAtlas
        self.updatePixmap()

    def updatePixmap(self):
        log.debug("Updating BlockTypeIcon with %s\t%s", self._block, self._textureAtlas)
        if self._textureAtlas is not None and self._block is not None:
            pixmap = BlockTypePixmap(self._block, self._textureAtlas)
            self.setPixmap(pixmap)
        else:
            self.setPixmap(None)


class BlockTypesItemWidget(QtGui.QWidget):
    def __init__(self, parent=None, blocks=None, textureAtlas=None):
        super(BlockTypesItemWidget, self).__init__(parent)
        self.childWidgets = []
        self.mainLayout = QtGui.QStackedLayout()
        self.blocks = blocks
        self.textureAtlas = textureAtlas
        self.setLayout(self.mainLayout)

        # Empty layout
        self.emptyWidget = QtGui.QLabel(self.tr("No blocks selected"))
        self.emptyWidget.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.emptyWidget.setMinimumHeight(60)

        # Single-block layout
        self.singleBlockIcon = BlockTypeIcon(textureAtlas=textureAtlas)

        self.singleNameLabel = QtGui.QLabel("")

        self.singleInternalNameLabel = QtGui.QLabel("", enabled=False)

        self.singleParentTypeLabel = QtGui.QLabel("")

        labelsColumn = Column(Row(self.singleNameLabel, None,
                                  self.singleParentTypeLabel),
                              self.singleInternalNameLabel)

        self.singleBlockLayout = Row(self.singleBlockIcon, (labelsColumn, 1))
        self.singleBlockWidget = QtGui.QFrame()
        self.singleBlockWidget.setLayout(self.singleBlockLayout)

        # Multi-block layout
        multiBlockIcon = QtGui.QFrame()
        vSpace = 4
        frameHeight = 64
        multiBlockIcon.setMinimumSize(64, frameHeight)
        self.iconLimit = int((frameHeight - 32) / vSpace) + 1

        self.multiBlockSubIcons = icons = [BlockTypeIcon(textureAtlas=textureAtlas)
                                           for _ in range(self.iconLimit)]
        x = 0
        y = 0
        for i, icon in enumerate(icons):
            # icon.setMinimumSize(32, 32)
            icon.setParent(multiBlockIcon)
            icon.setGeometry(x, y, 32, 32)
            icon.setFrameStyle(QtGui.QLabel.Box)
            x += 18
            if i % 2:
                x -= 32
            y += vSpace

        self.multiNameLabel = QtGui.QLabel("", wordWrap=True)

        self.multiBlockLayout = Row(multiBlockIcon, (Column(self.multiNameLabel, None), 1))
        self.multiBlockWidget = QtGui.QFrame()
        self.multiBlockWidget.setLayout(self.multiBlockLayout)

        self.updateContents()

    def setBlocks(self, blocks):
        if blocks != self.blocks:
            self.blocks = blocks
            self.updateContents()

    def setTextureAtlas(self, textureAtlas):
        if textureAtlas != self.textureAtlas:
            self.textureAtlas = textureAtlas
            for icon in self.multiBlockSubIcons:
                icon.setTextureAtlas(textureAtlas)

            self.updateContents()

    def updateContents(self):
        if self.blocks is None or self.textureAtlas is None:
            return

        blocks = self.blocks
        while self.mainLayout.count():
            self.mainLayout.takeAt(0)

        if len(blocks) == 0:
            self.mainLayout.addWidget(self.emptyWidget)
            return

        if len(blocks) == 1:
            self.mainLayout.addWidget(self.singleBlockWidget)

            block = blocks[0]
            self.singleBlockIcon.setBlock(block)
            self.singleBlockIcon.setTextureAtlas(self.textureAtlas)
            self.singleNameLabel.setText(block.displayName)

            internalNameLimit = 60
            internalName = block.internalName + block.blockState
            if len(internalName) > internalNameLimit:
                internalName = internalName[:internalNameLimit-3]+"..."
            self.singleInternalNameLabel.setText("(%d:%d) %s" % (block.ID, block.meta, internalName))
            self.singleParentTypeLabel.setText("")

            if block.meta != 0:
                try:
                    parentBlock = block.blocktypeSet[block.internalName]
                    if parentBlock.displayName != block.displayName:
                        self.singleParentTypeLabel.setText("<font color='blue'>%s</font>" % parentBlock.displayName)
                except KeyError:  # no parent block; parent block is not meta=0; block was ID:meta typed in
                    pass
            # row.setSizeConstraint(QtGui.QLayout.SetFixedSize)
        else:
            self.mainLayout.addWidget(self.multiBlockWidget)

            for i in range(self.iconLimit):
                icon = self.multiBlockSubIcons[i]
                if i < len(blocks):
                    icon.setBlock(blocks[i])
                    icon.setLineWidth(1)
                else:
                    icon.setBlock(None)
                    icon.setLineWidth(0)

            nameLimit = 6
            remaining = len(blocks) - nameLimit
            blocksToName = blocks[:nameLimit]
            iconNames = ", ".join(b.displayName for b in blocksToName)
            if remaining > 0:
                iconNames += " and %d more..." % remaining
            self.multiNameLabel.setText(iconNames)


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


