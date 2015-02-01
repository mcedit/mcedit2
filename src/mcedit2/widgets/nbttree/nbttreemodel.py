"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import os
from PySide import QtCore, QtGui
from mcedit2.util.resources import resourcePath
from mceditlib import nbt

log = logging.getLogger(__name__)

_nbtIcons = {}

_iconTypes = [
    "",
    "byte.png", # 1 - byte
    "short.png", # 2 - short
    "int.png", # 3 - int
    "long.png", # 4 - long
    "float.png", # 5 - float
    "double.png", # 6 - double
    "array.png", # 7 - bytearray
    "text.png", # 8 - string
    "list.png", # 9 - list
    "compound.png", # 10 - compound
    "array.png", # 11 - intarray
    "array.png", # 12 - shortarray
]


def NBTIcon(type):
    icon = _nbtIcons.get(type)
    if icon:
        return icon

    name = _iconTypes[type]
    path = resourcePath("mcedit2/assets/mcedit2/nbticons/" + name)
    assert os.path.exists(path), "%s does not exist" % path
    icon = QtGui.QIcon(path)
    assert icon is not None
    _nbtIcons[type] = icon
    return icon


def MakeNBTTreeItem(tag, parent):
    if isinstance(tag, nbt.TAG_Compound):
        return NBTTreeCompound(tag, parent)
    if isinstance(tag, nbt.TAG_List):
        return NBTTreeList(tag, parent)
    return NBTTreeItem(tag, parent)


class NBTTreeCompound(object):
    def __init__(self, tag, parent=None):
        self.parentItem = parent
        self.tag = tag
        self.childItems = [MakeNBTTreeItem(self.tag[name], self) for name in self.tag]

    def child(self, row):
        return self.childItems[row]

    def childCount(self):
        return len(self.childItems)

    def childNumber(self):
        if self.parentItem is not None:
            return self.parentItem.childItems.index(self)
        return 0

    def columnCount(self):
        return 2

    def data(self, column):
        if column == 0:
            return self.tag.name or self.tagCompoundName()
        if column == 1:
            return self.tagCompoundSummary()

    def tagCompoundName(self):
        tag = self.tag
        if "id" in tag:
            return str(tag["id"].value)

        return "Compound"

    def tagCompoundSummary(self):
        tag = self.tag
        summary = ""

        if "id" in tag:
            summary += str(tag["id"].value)
            if "Pos" in tag:
                x, y, z = tag["Pos"]
                summary += " at %0.3f, %0.3f, %0.3f" % (x.value, y.value, z.value)

        if not summary:
            return "%s items" % len(tag)
        return summary

    def insertChildren(self, position, count, columns):
        if position < 0 or position > len(self.childItems):
            return False

        for row in range(count):
            data = nbt.TAG_Byte()
            self.tag.insert(position, data)

            item = NBTTreeItem(data, self)
            self.childItems.insert(position, item)

        return True

    def parent(self):
        return self.parentItem

    def removeChildren(self, position, count):
        if position < 0 or position + count > len(self.childItems):
            return False

        for row in range(count):
            self.childItems.pop(position)

        return True

    def setValue(self, value):
        return False


class NBTTreeList(object):
    def __init__(self, tag, parent=None):
        self.parentItem = parent
        self.tag = tag
        self.childItems = [MakeNBTTreeItem(t, self) for t in self.tag]

    def child(self, row):
        return self.childItems[row]

    def childCount(self):
        return len(self.childItems)

    def childNumber(self):
        if self.parentItem is not None:
            return self.parentItem.childItems.index(self)
        return 0

    def columnCount(self):
        return 2

    def data(self, column):
        if column == 0:
            return self.tag.name
        if column == 1:
            tagID = self.tag.list_type

            if tagID in (nbt.ID_COMPOUND, nbt.ID_LIST):
                return "%d %ss" % (len(self.tag), nbt.tag_classes[tagID].__name__)

            if tagID in (nbt.ID_FLOAT, nbt.ID_DOUBLE):
                fmt = "%.03f"
            else:
                fmt = "%s"

            return ", ".join((fmt % i.value) for i in self.tag)

    def insertChildren(self, position, count, columns):
        if position < 0 or position > len(self.childItems):
            return False

        for row in range(count):
            data = self.tag.list_type()
            self.tag.insert(position, data)
            item = NBTTreeItem(data, self)
            self.childItems.insert(position, item)

        return True

    def parent(self):
        return self.parentItem

    def removeChildren(self, position, count):
        if position < 0 or position + count > len(self.childItems):
            return False

        for row in range(count):
            self.childItems.pop(position)

        return True

    def setValue(self, value):
        return False


class NBTTreeItem(object):
    def __init__(self, tag, parent=None):
        self.parentItem = parent
        self.tag = tag

    def __str__(self):
        s = self.tag.__class__.__name__
        if self.tag.name:
            s += " '%s'" % self.tag.name
        elif self.childNumber():
            s += " #%d" % self.childNumber()
        if self.parentItem:
            s += " of %s" % self.parentItem

    def childCount(self):
        return 0

    def childNumber(self):
        if self.parentItem is not None:
            return self.parentItem.childItems.index(self)
        return 0

    def columnCount(self):
        return 2

    def data(self, column):
        if column == 0:
            return self.tag.name or str(self.childNumber())
        if column == 1:
            return self.tag.value

    def parent(self):
        return self.parentItem

    def setValue(self, value):
        self.tag.value = value
        return True

class NBTTreeModel(QtCore.QAbstractItemModel):
    def __init__(self, rootTag, parent=None):
        super(NBTTreeModel, self).__init__(parent)

        self.rootItem = MakeNBTTreeItem(rootTag, self)
        self.rootTag = rootTag
        self.allowNameChanges = True

    def columnCount(self, parent=QtCore.QModelIndex()):
        return self.rootItem.columnCount()

    def tagID(self, index):
        if not index.isValid():
            return None
        return self.getItem(index).tag.tagID

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None

        item = self.getItem(index)
        column = index.column()

        if role == QtCore.Qt.DecorationRole and column == 0:
            return NBTIcon(item.tag.tagID)

        if role in (QtCore.Qt.DisplayRole, QtCore.Qt.EditRole):
            return item.data(column)

    def flags(self, index):
        if not index.isValid():
            return 0

        flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        item = self.getItem(index)
        parent = self.parent(index)
        parentItem = self.getItem(parent) if parent else None

        if index.column() == 1 or (self.allowNameChanges and isinstance(parentItem, NBTTreeCompound)):
            flags |= QtCore.Qt.ItemIsEditable
        return flags


    def getItem(self, index):
        if index.isValid():
            item = index.internalPointer()
            if item:
                return item

        return self.rootItem

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return ("Name", "Value")[section]

        return None

    def index(self, row, column, parent=QtCore.QModelIndex()):
        if parent.isValid() and parent.column() != 0:
            return QtCore.QModelIndex()

        parentItem = self.getItem(parent)
        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QtCore.QModelIndex()

    def insertRows(self, position, rows, parent=QtCore.QModelIndex()):
        parentItem = self.getItem(parent)
        self.beginInsertRows(parent, position, position + rows - 1)
        success = parentItem.insertChildren(position, rows,
                                            self.rootItem.columnCount())
        self.endInsertRows()

        return success

    def parent(self, index):
        if not index.isValid():
            return QtCore.QModelIndex()

        childItem = self.getItem(index)
        parentItem = childItem.parent()

        if parentItem == self.rootItem:
            return QtCore.QModelIndex()

        return self.createIndex(parentItem.childNumber(), 0, parentItem)

    def removeRows(self, position, rows, parent=QtCore.QModelIndex()):
        parentItem = self.getItem(parent)

        self.beginRemoveRows(parent, position, position + rows - 1)
        success = parentItem.removeChildren(position, rows)
        self.endRemoveRows()

        return success

    def rowCount(self, parent=QtCore.QModelIndex()):
        parentItem = self.getItem(parent)

        return parentItem.childCount()

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        if role != QtCore.Qt.EditRole:
            return False

        item = self.getItem(index)
        column = index.column()
        if column == 0:
            if item.parentItem.tag.tagID == nbt.ID_COMPOUND:
                item.parentItem.tag[value] = item.tag
                item.tag.name = value
                result = True
            else:
                result = False
        elif column == 1:
            result = item.setValue(value)
        else:
            return False

        if result:
            self.dataChanged.emit(index, index)

        return result


_NBTTagTypeSortOrder = [
    'TAG_Compound',
    'TAG_List',
    'TAG_Int_Array',
    'TAG_Short_Array',
    'TAG_Byte_Array',
    'TAG_String',
    'TAG_Double',
    'TAG_Float',
    'TAG_Long',
    'TAG_Int',
    'TAG_Short',
    'TAG_Byte',
]

class NBTFilterProxyModel(QtGui.QSortFilterProxyModel):
    def lessThan(self, left, right):
        leftData = self.sourceModel().data(left)
        rightData = self.sourceModel().data(right)
        column = left.column()

        if column == 0:
            leftTag = self.sourceModel().tagID(left)
            rightTag = self.sourceModel().tagID(right)
            leftTuple = (leftTag not in (nbt.ID_COMPOUND, nbt.ID_LIST), leftData and leftData.lower())
            rightTuple = (rightTag not in (nbt.ID_COMPOUND, nbt.ID_LIST), rightData and rightData.lower())

            return leftTuple < rightTuple
        if column == 1:
            leftIndex = _NBTTagTypeSortOrder.index(leftData.split("(")[0])
            rightIndex = _NBTTagTypeSortOrder.index(rightData.split("(")[0])
            return leftIndex < rightIndex

        return super(NBTFilterProxyModel, self).lessThan(left, right)
