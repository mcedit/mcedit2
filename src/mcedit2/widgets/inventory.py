"""
    inventory
"""
from __future__ import absolute_import, division, print_function
import logging
from mceditlib import nbt

from PySide import QtGui, QtCore
from PySide.QtCore import Qt
import itertools

from mcedit2.widgets.itemtype_list import ItemTypeListModel, ItemTypeIcon, ICON_SIZE
from mcedit2.widgets.layout import Row, Column
from mcedit2.widgets.nbttree.nbteditor import NBTEditorWidget


log = logging.getLogger(__name__)


class InventoryItemModel(QtCore.QAbstractListModel):
    ItemIDRole = Qt.UserRole
    ItemRawIDRole = ItemIDRole + 1
    ItemIconRole = ItemRawIDRole + 1
    ItemDamageRole = ItemIconRole + 1
    ItemCountRole = ItemDamageRole + 1

    def __init__(self, itemListRef, slotCount, editorSession):
        super(InventoryItemModel, self).__init__()
        self.editorSession = editorSession
        self.itemListRef = itemListRef
        self.slotCount = slotCount
        self.textureCache = {}


    def rowCount(self, parent):
        if parent.isValid():
            return 0
        return self.slotCount

    def data(self, index, role):
        if not index.isValid():
            return 0

        slot = index.row()
        itemStack = self.itemListRef.getItemInSlot(slot)
        if itemStack is None:
            return None
        itemType = itemStack.itemType

        if role == self.ItemIconRole:
            return ItemTypeIcon(itemType, self.editorSession, itemStack)

        if role == self.ItemIDRole:
            return itemStack.id
        if role == self.ItemRawIDRole:
            return itemStack.raw_id
        if role == self.ItemCountRole:
            return itemStack.Count
        if role == self.ItemDamageRole:
            return itemStack.Damage

        return None

    def setData(self, index, value, role):
        if not index.isValid():
            return 0

        slot = index.row()
        itemStack = self.itemListRef.getItemInSlot(slot)
        if itemStack is None:
            return

        if role == self.ItemIDRole:
            itemStack.id = value
        if role == self.ItemRawIDRole:
            itemStack.raw_id = int(value)
        if role == self.ItemCountRole:
            itemStack.Count = value
        if role == self.ItemDamageRole:
            itemStack.Damage = value



class InventoryItemWidget(QtGui.QPushButton):
    BLANK = None

    def __init__(self, inventoryView, slotNumber):
        super(InventoryItemWidget, self).__init__()
        self.inventoryView = inventoryView
        self.slotNumber = slotNumber
        self.countText = None

        self.setIconSize(QtCore.QSize(ICON_SIZE, ICON_SIZE))

        if InventoryItemWidget.BLANK is None:
            pm = QtGui.QPixmap(ICON_SIZE, ICON_SIZE)
            pm.fill(Qt.transparent)
            InventoryItemWidget.BLANK = QtGui.QIcon(pm)

        self.setIcon(InventoryItemWidget.BLANK)

        self.setSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Fixed)

    def setCount(self, val):
        if val == 1:
            self.countText = None
        else:
            self.countText = str(val)

    def paintEvent(self, event):
        super(InventoryItemWidget, self).paintEvent(event)
        if self.countText is None:
            return
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.TextAntialiasing, True)
        font = QtGui.QFont("Arial", 12, 75)
        outlinePen = QtGui.QPen(Qt.black)
        outlinePen.setWidth(3.0)
        fillBrush = QtGui.QBrush(Qt.white)
        # painter.setFont(font)

        x, y = 0, 0
        path = QtGui.QPainterPath()
        path.addText(x, y, font, self.countText)
        rect = path.boundingRect()
        rect.moveBottomRight(QtCore.QPointF(ICON_SIZE + 3, ICON_SIZE + rect.height()))
        path.translate(rect.topLeft())

        painter.setPen(outlinePen)
        painter.drawPath(path)
        painter.setBrush(fillBrush)
        painter.setPen(None)
        painter.drawPath(path)
        # outlinePen = QtGui.QPen(color=Qt.black, width=4.0)
        # painter.strokePath(path, outlinePen)
        #painter.fillPath(path, fillBrush)


class InventoryView(QtGui.QWidget):
    def __init__(self, slotLayout):
        """
        slotLayout should be a list of (x, y, slotNumber) tuples.

        :param slotLayout:
        :type slotLayout:
        :return:
        :rtype:
        """
        super(InventoryView, self).__init__()
        self.slotWidgets = {}
        gridLayout = QtGui.QGridLayout()
        self.setLayout(gridLayout)

        def _makeClicked(slot):
            def _clicked():
                self.slotClicked.emit(slot)
            return _clicked

        self.slots = []
        for (x, y, slotNumber) in slotLayout:
            itemWidget = InventoryItemWidget(self, slotNumber)
            itemWidget._clicked = _makeClicked(slotNumber)
            self.slotWidgets[slotNumber] = itemWidget
            gridLayout.addWidget(itemWidget, y, x)
            itemWidget.clicked.connect(itemWidget._clicked)
            self.slots.append(slotNumber)

        self.setSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Fixed)

        self.model = None

    slotClicked = QtCore.Signal(int)

    def setModel(self, model):
        assert isinstance(model, InventoryItemModel)
        self.model = model
        self.updateItems()

    def updateItems(self):
        for slot in self.slots:
            index = self.model.index(slot, 0)
            icon = index.data(InventoryItemModel.ItemIconRole)
            slotWidget = self.slotWidgets[slot]
            if icon is not None:
                slotWidget.setIcon(icon)
            else:
                slotWidget.setIcon(InventoryItemWidget.BLANK)

            count = index.data(InventoryItemModel.ItemCountRole)
            if count is None:
                continue

            slotWidget.setCount(count)


class InventoryEditor(QtGui.QWidget):
    def __init__(self):
        super(InventoryEditor, self).__init__()
        # xxx get layout from inventory ref? etc?

        playerSlotLayout = [(x, 0, 100+x) for x in range(4)]  # equipment
        playerSlotLayout += [(x, y+1, x+9*y+9) for x, y in itertools.product(range(9), range(3))]  # inventory
        playerSlotLayout += [(x, 4, x) for x in range(9)]  # hotbar
        playerSlotMax = 104
        self.slotCount = playerSlotMax

        self.inventoryView = InventoryView(playerSlotLayout)
        self.inventoryView.slotClicked.connect(self.slotWasClicked)

        self.itemList = QtGui.QListView()
        self.itemList.setMinimumWidth(200)

        self.inventoryModel = None

        self.internalNameField = QtGui.QLineEdit()
        self.rawIDInput = QtGui.QLineEdit()
        self.rawIDInput.setMaximumWidth(100)

        self.damageInput = QtGui.QSpinBox(minimum=-32768, maximum=32767)
        self.countInput = QtGui.QSpinBox(minimum=-32768, maximum=32767)

        self.rawIDCheckbox = QtGui.QCheckBox("Edit raw ID")

        self.itemNBTEditor = NBTEditorWidget()

        self.setLayout(Column(Row(self.inventoryView, self.itemList),
                              Row(QtGui.QLabel("Internal Name"), self.internalNameField,
                                  self.rawIDCheckbox, self.rawIDInput,
                                  QtGui.QLabel("Damage"), self.damageInput,
                                  QtGui.QLabel("Count"), self.countInput),
                              self.itemNBTEditor))

        self.enableFields(False)

    def enableFields(self, enabled):
        self.internalNameField.setEnabled(enabled)
        self.rawIDInput.setEnabled(enabled)
        self.rawIDCheckbox.setEnabled(enabled)
        self.damageInput.setEnabled(enabled)
        self.countInput.setEnabled(enabled)
        self.itemNBTEditor.setEnabled(enabled)

    def slotWasClicked(self, slotNumber):
        index = self.inventoryModel.index(slotNumber)

        internalName = index.data(InventoryItemModel.ItemIDRole)
        if internalName is None:
            self.enableFields(False)
            self.internalNameField.setText("")
            self.rawIDInput.setText("")
            self.damageInput.setValue(0)
            self.countInput.setValue(0)
            return
        else:
            self.enableFields(True)

        self.internalNameField.setText(internalName)

        rawID = index.data(InventoryItemModel.ItemRawIDRole)
        if rawID != internalName:
            self.rawIDCheckbox.setEnabled(True)
            self.rawIDInput.setEnabled(True)
            self.rawIDInput.setText(rawID)
        else:
            self.rawIDCheckbox.setEnabled(False)
            self.rawIDInput.setEnabled(False)

        damage = index.data(InventoryItemModel.ItemDamageRole)
        self.damageInput.setValue(damage)

        count = index.data(InventoryItemModel.ItemCountRole)
        self.countInput.setValue(count)

        tag = self._itemListRef.getItemInSlot(slotNumber).rootTag
        assert isinstance(tag, nbt.TAG_Compound), "Tag is not a TAG_Compound, it's a %s (%s)" % (type(tag), tag)
        self.itemNBTEditor.setRootTag(tag)


    _editorSession = None
    @property
    def editorSession(self):
        return self._editorSession

    @editorSession.setter
    def editorSession(self, value):
        self._editorSession = value
        self.updateModels()

    _itemListRef = None
    @property
    def inventoryRef(self):
        return self._itemListRef

    @inventoryRef.setter
    def inventoryRef(self, value):
        self._itemListRef = value
        self.updateModels()


    def updateModels(self):
        if self._editorSession is None or self._itemListRef is None:
            return

        self.inventoryModel = InventoryItemModel(self._itemListRef, self.slotCount, self._editorSession)
        self.inventoryView.setModel(self.inventoryModel)

        self.itemListModel = ItemTypeListModel(self._editorSession)
        self.itemList.setModel(self.itemListModel)

        self.itemNBTEditor.editorSession = self._editorSession
