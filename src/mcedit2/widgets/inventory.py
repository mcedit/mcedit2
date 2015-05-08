"""
    inventory
"""
from __future__ import absolute_import, division, print_function
import contextlib
import logging
from mcedit2.command import SimpleRevisionCommand
from mceditlib import nbt

from PySide import QtGui, QtCore
from PySide.QtCore import Qt
import itertools

from mcedit2.widgets.itemtype_list import ItemTypeListModel, ItemTypeIcon, ICON_SIZE
from mcedit2.widgets.layout import Row, Column
from mcedit2.widgets.nbttree.nbteditor import NBTEditorWidget
from mceditlib.blocktypes import VERSION_1_7, VERSION_1_8


log = logging.getLogger(__name__)


class InventoryItemModel(QtCore.QAbstractItemModel):
    ItemIDRole = Qt.UserRole
    ItemRawIDRole = ItemIDRole + 1
    ItemIconRole = ItemRawIDRole + 1
    ItemDamageRole = ItemIconRole + 1
    ItemCountRole = ItemDamageRole + 1

    def __init__(self, itemListRef, editorSession):
        super(InventoryItemModel, self).__init__()
        assert editorSession is not None
        self.editorSession = editorSession
        self.itemListRef = itemListRef
        self.textureCache = {}

    def index(self, slot, parentIndex=QtCore.QModelIndex()):
        if parentIndex.isValid():
            return QtCore.QModelIndex()
        return self.createIndex(slot, 0)

    def rowCount(self, parent):
        # slot numbers are defined by the view's slotLayout
        # maybe that should be the model's slotLayout instead
        return 0

    def data(self, index, role):
        if not index.isValid():
            return 0

        slot = index.row()
        itemStack = self.itemListRef.getItemInSlot(slot)
        if itemStack is None:
            return None
        try:
            itemType = itemStack.itemType
        except ValueError as e:  # itemType not mapped
            return None
        except KeyError as e:  # missing NBT tag?
            log.exception("Error while reading item data: %r", e)
            return None

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
        elif role == self.ItemRawIDRole:
            itemStack.raw_id = int(value)
        elif role == self.ItemCountRole:
            itemStack.Count = value
        elif role == self.ItemDamageRole:
            itemStack.Damage = value
        else:
            return

        self.dataChanged.emit(index, index)


class InventoryItemWidget(QtGui.QPushButton):
    BLANK = None

    def __init__(self, inventoryView, slotNumber):
        super(InventoryItemWidget, self).__init__()
        self.inventoryView = inventoryView
        self.slotNumber = slotNumber
        self.countText = None

        self.setIconSize(QtCore.QSize(ICON_SIZE, ICON_SIZE))
        self.setCheckable(True)

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
    def __init__(self, slotLayout, rows=None, columns=None):
        """
        slotLayout should be a list of (x, y, slotNumber) tuples.

        rows and columns are optional. Pass them if you need the grid to be larger than the slotLayout.

        :param slotLayout:
        :type slotLayout: list[tuple(int, int, int)]
        :type rows: int | None
        :type columns: int | None
        :return:
        :rtype:
        """
        super(InventoryView, self).__init__()
        self.slotWidgets = {}
        gridLayout = QtGui.QGridLayout()
        self.setLayout(gridLayout)

        # Add placeholders to stretch grid - QGridLayout has no setRow/ColumnCount
        if rows:
            gridLayout.addWidget(QtGui.QWidget(), rows-1, 0)
        if columns:
            gridLayout.addWidget(QtGui.QWidget(), 0, columns-1)


        def _makeClicked(slot):
            def _clicked():
                self.slotClicked.emit(slot)
            return _clicked

        self.slots = []
        self.buttonGroup = QtGui.QButtonGroup()

        for (x, y, slotNumber) in slotLayout:
            itemWidget = InventoryItemWidget(self, slotNumber)
            itemWidget._clicked = _makeClicked(slotNumber)
            self.slotWidgets[slotNumber] = itemWidget
            gridLayout.addWidget(itemWidget, y, x)
            itemWidget.clicked.connect(itemWidget._clicked)
            self.slots.append(slotNumber)
            self.buttonGroup.addButton(itemWidget)

        self.setSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Fixed)

        self.model = None

        self.slotClicked.connect(self.slotWasClicked)

    slotClicked = QtCore.Signal(int)

    def slotWasClicked(self, slotNumber):
        self.slotWidgets[slotNumber].setChecked(True)

    def setModel(self, model):
        assert isinstance(model, InventoryItemModel)
        self.model = model
        self.model.dataChanged.connect(self.dataChanged)
        self.updateItems()

    def dataChanged(self, topLeft, bottomRight):
        self.updateSlot(topLeft)

    def updateItems(self):
        for slot in self.slots:
            index = self.model.index(slot)
            self.updateSlot(index)

    def updateSlot(self, index):
        slot = index.row()
        icon = index.data(InventoryItemModel.ItemIconRole)
        slotWidget = self.slotWidgets[slot]
        if icon is not None:
            slotWidget.setIcon(icon)
        else:
            slotWidget.setIcon(InventoryItemWidget.BLANK)

        count = index.data(InventoryItemModel.ItemCountRole)
        if count is None:
            return

        slotWidget.setCount(count)


class InventoryEditor(QtGui.QWidget):
    def __init__(self, slotLayout, rows=None, columns=None):
        """
        slotLayout should be a list of (x, y, slotNumber) tuples.

        rows and columns are optional. Pass them if you need the grid to be larger than the slotLayout.

        :param slotLayout:
        :type slotLayout: list[tuple(int, int, int)]
        :type rows: int | None
        :type columns: int | None
        :return:
        :rtype:
        """

        super(InventoryEditor, self).__init__()

        self.inventoryView = InventoryView(slotLayout, rows, columns)
        self.inventoryView.slotClicked.connect(self.slotWasClicked)

        self.itemList = QtGui.QListView()
        self.itemList.setMinimumWidth(200)
        self.itemList.clicked.connect(self.itemTypeChanged)
        self.itemListModel = None

        self.itemListSearchBox = QtGui.QComboBox()
        self.itemListSearchBox.textChanged.connect(self.searchTextChanged)
        self.itemListSearchBox.setEditable(True)

        self.inventoryModel = None

        self.internalNameField = QtGui.QLineEdit()
        self.internalNameField.textChanged.connect(self.internalNameChanged)

        self.rawIDInput = QtGui.QLineEdit()
        self.rawIDInput.setMaximumWidth(100)
        self.rawIDInput.textChanged.connect(self.rawIDChanged)

        self.damageInput = QtGui.QSpinBox(minimum=-32768, maximum=32767)
        self.damageInput.valueChanged.connect(self.damageChanged)

        self.countInput = QtGui.QSpinBox(minimum=-32768, maximum=32767)
        self.countInput.valueChanged.connect(self.countChanged)

        self.rawIDCheckbox = QtGui.QCheckBox("Edit raw ID")
        self.rawIDCheckbox.toggled.connect(self.rawIDInput.setEnabled)

        self.itemNBTEditor = NBTEditorWidget()

        self.currentIndex = None

        self.setLayout(Column(Row(self.inventoryView,
                                  Column(self.itemListSearchBox, self.itemList)),
                              Row(QtGui.QLabel("Internal Name"), self.internalNameField,
                                  self.rawIDCheckbox, self.rawIDInput,
                                  QtGui.QLabel("Damage"), self.damageInput,
                                  QtGui.QLabel("Count"), self.countInput),
                              (self.itemNBTEditor, 1)))

        self.enableFields(False)

    def enableFields(self, enabled):
        self.internalNameField.setEnabled(enabled)
        self.rawIDInput.setEnabled(enabled)
        self.rawIDCheckbox.setEnabled(enabled)
        self.damageInput.setEnabled(enabled)
        self.countInput.setEnabled(enabled)
        self.itemNBTEditor.setEnabled(enabled)

    def showFieldsForVersion(self, version):
        oneSeven = version == VERSION_1_7

        self.rawIDCheckbox.setVisible(oneSeven)
        self.rawIDInput.setVisible(oneSeven)


    editsDisabled = False

    @contextlib.contextmanager
    def disableEdits(self):
        self.editsDisabled = True
        yield
        self.editsDisabled = False

    def slotWasClicked(self, slotNumber):
        with self.disableEdits():
            self._slotWasClicked(slotNumber)

    def _slotWasClicked(self, slotNumber):
        self.currentIndex = index = self.inventoryModel.index(slotNumber)

        version = self._itemListRef.blockTypes.itemStackVersion
        self.showFieldsForVersion(version)

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
            self.rawIDInput.setEnabled(self.rawIDCheckbox.isChecked())
            self.rawIDInput.setText(str(rawID))
        else:
            self.rawIDCheckbox.setEnabled(False)
            self.rawIDInput.setEnabled(False)

        damage = index.data(InventoryItemModel.ItemDamageRole)
        self.damageInput.setValue(damage)

        count = index.data(InventoryItemModel.ItemCountRole)
        self.countInput.setValue(count)

        tagRef = self._itemListRef.getItemInSlot(slotNumber)
        self.itemNBTEditor.setRootTagRef(tagRef)

    def searchTextChanged(self, value):
        self.proxyModel = QtGui.QSortFilterProxyModel()
        self.proxyModel.setSourceModel(self.itemListModel)
        self.proxyModel.setFilterFixedString(value)
        self.proxyModel.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.itemList.setModel(self.proxyModel)

    def itemTypeChanged(self, index):
        if self.currentIndex is None or self.itemListModel is None:
            return
        if self.editsDisabled:
            return

        internalName = index.data(ItemTypeListModel.InternalNameRole)
        damage = index.data(ItemTypeListModel.DamageRole)

        command = InventoryEditCommand(self.editorSession, self.tr("Change item type"))
        with command.begin():
            self.inventoryModel.setData(self.currentIndex, internalName, InventoryItemModel.ItemIDRole)
            if damage is not None:
                self.inventoryModel.setData(self.currentIndex, damage, InventoryItemModel.ItemDamageRole)

        self.editorSession.pushCommand(command)

    def internalNameChanged(self, value):
        if self.currentIndex is None:
            return
        if self.editsDisabled:
            return

        command = InventoryEditCommand(self.editorSession, self.tr("Change item type"))
        with command.begin():
            self.inventoryModel.setData(self.currentIndex, value, InventoryItemModel.ItemIDRole)
        self.editorSession.pushCommand(command)

    def rawIDChanged(self, value):
        if self.currentIndex is None:
            return
        if self.editsDisabled:
            return

        command = InventoryEditCommand(self.editorSession, self.tr("Change item's raw ID"))
        with command.begin():
            self.inventoryModel.setData(self.currentIndex, value, InventoryItemModel.ItemRawIDRole)
        self.editorSession.pushCommand(command)

    def damageChanged(self, value):
        if self.currentIndex is None:
            return
        if self.editsDisabled:
            return

        command = InventoryEditCommand(self.editorSession, self.tr("Change item damage"))
        with command.begin():
            self.inventoryModel.setData(self.currentIndex, value, InventoryItemModel.ItemDamageRole)
        self.editorSession.pushCommand(command)

    def countChanged(self, value):
        if self.currentIndex is None:
            return
        if self.editsDisabled:
            return

        command = InventoryEditCommand(self.editorSession, self.tr("Change item count"))
        with command.begin():
            self.inventoryModel.setData(self.currentIndex, value, InventoryItemModel.ItemCountRole)
        self.editorSession.pushCommand(command)

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

        self.currentIndex = None
        self.enableFields(False)

        self.inventoryModel = InventoryItemModel(self._itemListRef, self._editorSession)
        self.inventoryView.setModel(self.inventoryModel)

        self.itemListModel = ItemTypeListModel(self._editorSession)
        self.itemList.setModel(self.itemListModel)

        self.itemNBTEditor.editorSession = self._editorSession

class InventoryEditCommand(SimpleRevisionCommand):
    pass
