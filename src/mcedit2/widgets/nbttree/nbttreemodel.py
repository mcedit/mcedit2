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
    isCompound = True
    isList = False

    def __init__(self, tag, parent=None):
        self.parentItem = parent
        self.tag = tag
        self.childItems = [MakeNBTTreeItem(self.tag[name], self) for name in self.tag]

    def child(self, row):
        if row >= len(self.childItems):
            return None
        return self.childItems[row]

    def childCount(self):
        return len(self.childItems)

    def childNumber(self):
        if self.parentItem is not None:
            return self.parentItem.childItems.index(self)
        return 0

    def data(self, column):
        if column == 0:
            return self.tag.name or self.childNumber()
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

        # Entity?
        if "Pos" in tag:
            x, y, z = tag["Pos"]
            summary = "%0.3f, %0.3f, %0.3f" % (x.value, y.value, z.value)
            if "id" in tag:
                summary = str(tag["id"].value) + " at " + summary

        if not summary:
            return "%s items" % len(tag)

        return summary

    def insertChildren(self, position, count, tagID):
        if position < 0 or position > len(self.childItems):
            return False

        for row in range(count):
            name = "Unnamed"
            i = 0
            while name in self.tag:
                i += 1
                name = "Unnamed %d" % i

            tag = nbt.tag_classes[tagID]()
            self.tag[name] = tag

            item = NBTTreeItem(tag, self)
            self.childItems.insert(position + row, item)

        return True

    def parent(self):
        return self.parentItem

    def removeChildren(self, position, count):
        if position < 0 or position + count > len(self.childItems):
            return False

        for row in range(count):
            name = self.childItems.pop(position).tag.name
            del self.tag[name]

        return True

    def setValue(self, value):
        return False

    def nbtPath(self, child=None):
        if self.parentItem is None:
            path = []
        else:
            path = self.parentItem.nbtPath(self)
        if child:
            path.append(child.tag.name)
        return path


class NBTTreeList(object):
    isCompound = False
    isList = True

    def __init__(self, tag, parent=None):
        self.parentItem = parent
        self.tag = tag
        self.childItems = [MakeNBTTreeItem(t, self) for t in self.tag]

    def child(self, row):
        if row >= len(self.childItems):
            return None
        return self.childItems[row]

    def childCount(self):
        return len(self.childItems)

    def childNumber(self):
        if self.parentItem is not None:
            return self.parentItem.childItems.index(self)
        return 0

    def data(self, column):
        if column == 0:
            return self.tag.name or self.childNumber()
        if column == 1:
            tagID = self.tag.list_type

            if tagID in (nbt.ID_COMPOUND, nbt.ID_LIST):
                return "%d %ss" % (len(self.tag), nbt.tag_classes[tagID].__name__)

            if tagID in (nbt.ID_FLOAT, nbt.ID_DOUBLE):
                fmt = "%.03f"
            else:
                fmt = "%s"

            return ", ".join((fmt % i.value) for i in self.tag)

    def insertChildren(self, position, count, tagID):
        if position < 0 or position > len(self.childItems):
            return False

        for row in range(count):
            tag = nbt.tag_classes[self.tag.list_type or tagID]()
            self.tag.insert(position + row, tag)
            item = NBTTreeItem(tag, self)
            self.childItems.insert(position + row, item)

        return True

    def parent(self):
        return self.parentItem

    def removeChildren(self, position, count):
        if position < 0 or position + count > len(self.childItems):
            return False

        for row in range(count):
            self.childItems.pop(position)
            self.tag.pop(position)

        return True

    def setValue(self, value):
        return False

    def nbtPath(self, child=None):
        if self.parentItem is None:
            path = []
        else:
            path = self.parentItem.nbtPath(self)
        if child:
            row = self.childItems.index(child)
            path.append(row)

        return path


class NBTTreeItem(object):
    isCompound = False
    isList = False

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

    def data(self, column):
        if column == 0:
            return self.tag.name or self.childNumber()
        if column == 1:
            if self.tag.tagID in (nbt.ID_BYTE_ARRAY, nbt.ID_LONG_ARRAY, nbt.ID_INT_ARRAY):
                size = self.tag.value.size
                maxsize = min(8, size)
                hexchars = self.tag.value.dtype.itemsize * 2
                fmt = "%%0%dx" % hexchars
                hexdata = " ".join(fmt % d for d in self.tag.value[:maxsize])
                if size > maxsize:
                    hexdata += "..."
                return "(size=%d) %s" % (size, hexdata)
            if self.tag.tagID == nbt.ID_LONG:
                # Workaround for OverflowError on Linux
                return str(self.tag.value)
            return self.tag.value

    def parent(self):
        return self.parentItem

    def setValue(self, value):
        if self.tag.tagID == nbt.ID_LONG:
            value = long(value)
        if self.tag.tagID == nbt.ID_INT:
            value = min(0x7FFFFFFF, max(-0x80000000, value))
        if self.tag.tagID == nbt.ID_SHORT:
            value = min(0x7FFF, max(-0x8000, value))
        if self.tag.tagID == nbt.ID_BYTE:
            value = min(0x7F, max(-0x80, value))

        if value != self.tag.value:
            log.info("Changing NBT tag %s because old %s != new %s", self.nbtPath, self.tag.value, value)
            self.tag.value = value
            return True
        else:
            return False

    def nbtPath(self):
        if self.parentItem is None:
            return []
        return self.parentItem.nbtPath(self)


class NBTTreeModel(QtCore.QAbstractItemModel):
    NBTPathRole = QtCore.Qt.UserRole + 1
    NBTTagTypeRole = NBTPathRole + 1

    def __init__(self, rootTag, blocktypes, editable):
        """

        Parameters
        ----------
        rootTag : mceditlib.nbt.TAG_Compound
        blocktypes : mceditlib.blocktypes.BlockTypeSet

        """
        super(NBTTreeModel, self).__init__()
        self.blocktypes = blocktypes
        self.rootItem = MakeNBTTreeItem(rootTag, None)
        self.rootTag = rootTag
        self.editable = editable
        self.allowNameChanges = True
        self.addIcon = QtGui.QIcon(resourcePath("mcedit2/assets/mcedit2/icons/add.png"))
        self.removeIcon = QtGui.QIcon(resourcePath("mcedit2/assets/mcedit2/icons/remove.png"))

    def columnCount(self, parent=QtCore.QModelIndex()):
        return 4

    def tagID(self, index):
        return self.getItem(index).tag.tagID

    # --- Data ---

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return ("Name", "Value", "", "")[section]

        return None

    def flags(self, index):
        flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        parent = self.parent(index)
        parentItem = self.getItem(parent) if parent else None

        if (self.editable
            and (
                    (index.column() == 1
                     and self.tagID(index) not in (nbt.ID_BYTE_ARRAY,
                                                   nbt.ID_INT_ARRAY,
                                                   nbt.ID_LONG_ARRAY,
                                                   nbt.ID_LIST,
                                                   nbt.ID_COMPOUND))
                 or (index.column() == 0
                     and self.allowNameChanges
                     and parentItem
                     and parentItem.isCompound))):
            flags |= QtCore.Qt.ItemIsEditable
        return flags

    def data(self, index, role=QtCore.Qt.DisplayRole):
        item = self.getItem(index)
        column = index.column()

        if role == QtCore.Qt.DecorationRole:
            if column == 0:
                return NBTIcon(item.tag.tagID)
            if column == 2:
                return self.addIcon if item.isList or item.isCompound else None
            if column == 3:
                return self.removeIcon if item is not self.rootItem else None

        if role in (QtCore.Qt.DisplayRole, QtCore.Qt.EditRole):
            if column == 1:
                summary = None
                if item.tag.tagID == nbt.ID_COMPOUND:
                    if "id" in item.tag:
                        nameTag = item.tag["id"]
                        if nameTag.tagID == nbt.ID_SHORT:
                            # Item ID?
                            itemTypes = self.blocktypes.itemTypes
                            try:
                                itemType = itemTypes[nameTag.value]
                                summary = itemType.internalName
                            except KeyError:
                                pass
                            
                        elif nameTag.tagID == nbt.ID_STRING:
                            summary = nameTag.value
                        
                        if summary and "Count" in item.tag:
                            summary += " (x%s)" % (item.tag['Count'].value,)
                
                if summary:
                    return summary

            return item.data(column)

        if role == self.NBTPathRole:
            return item.nbtPath()
        if role == self.NBTTagTypeRole:
            return item.tag.tagID

    # --- Structure ---

    def getItem(self, index):
        if index.isValid():
            item = index.internalPointer()
            if item:
                return item
        else:
            return None

    def rowCount(self, parent=QtCore.QModelIndex()):
        if not parent.isValid():
            return 1
        parentItem = self.getItem(parent)

        return parentItem.childCount()

    def index(self, row, column, parent=QtCore.QModelIndex()):
        if not parent.isValid():
            assert row == 0
            return self.createIndex(row, column, self.rootItem)

        parentItem = self.getItem(parent)
        if parentItem is None:
            return QtCore.QModelIndex()

        childItem = parentItem.child(row)
        if childItem is None:
            return QtCore.QModelIndex()

        return self.createIndex(row, column, childItem)

    def parent(self, index):
        if not index.isValid():
            return QtCore.QModelIndex()

        item = self.getItem(index)
        parentItem = item.parent()

        if parentItem is None:  # item is self.rootItem
            return QtCore.QModelIndex()

        return self.createIndex(parentItem.childNumber(), 0, parentItem)

    # --- Editing ---

    def insertRow(self, position, parent=QtCore.QModelIndex(), tagID=None):
        return self.insertRows(position, 1, parent, tagID)

    def insertRows(self, row, count, parent=QtCore.QModelIndex(), tagID=None):
        parentItem = self.getItem(parent)

        # the index passed to beginInsertRows should have .column() == 0. passing the index that was clicked in
        # QTreeView.clicked causes the view to fail to update after the rows are added.
        realParent = self.createIndex(parent.row(), 0, parentItem)
        self.beginInsertRows(realParent, row, row + count - 1)
        success = parentItem.insertChildren(row, count, tagID)
        self.endInsertRows()

        return success

    def removeRow(self, position, parent=QtCore.QModelIndex()):
        self.removeRows(position, 1, parent)

    def removeRows(self, position, rows, parent=QtCore.QModelIndex()):
        parentItem = self.getItem(parent)

        self.beginRemoveRows(parent, position, position + rows - 1)
        success = parentItem.removeChildren(position, rows)
        self.endRemoveRows()

        return success

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        if role != QtCore.Qt.EditRole:
            return False

        item = self.getItem(index)
        column = index.column()
        if column == 0:
            if item.parentItem.tag.tagID == nbt.ID_COMPOUND and item.tag.name != value:
                del item.parentItem.tag[item.tag.name]
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
    'TAG_Long_Array',
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
            leftTuple = (leftTag not in (nbt.ID_COMPOUND, nbt.ID_LIST), leftData.lower() if isinstance(leftData, basestring) else leftData)
            rightTuple = (rightTag not in (nbt.ID_COMPOUND, nbt.ID_LIST), rightData.lower() if isinstance(rightData, basestring) else rightData)

            return leftTuple < rightTuple
        if column == 1:
            leftIndex = _NBTTagTypeSortOrder.index(leftData.split("(")[0])
            rightIndex = _NBTTagTypeSortOrder.index(rightData.split("(")[0])
            return leftIndex < rightIndex

        return super(NBTFilterProxyModel, self).lessThan(left, right)

    def sort(self, column, order):
        if column > 1:
            return
        super(NBTFilterProxyModel, self).sort(column, order)
