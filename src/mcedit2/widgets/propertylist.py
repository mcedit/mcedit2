"""
    propertylist
"""
from __future__ import absolute_import, division, print_function
from collections import namedtuple
import logging
from PySide.QtCore import Qt
from mceditlib import nbt
from PySide import QtGui, QtCore
from mcedit2.util.load_ui import registerCustomWidget

log = logging.getLogger(__name__)

class PropertyListItemDelegate(QtGui.QStyledItemDelegate):

    def __init__(self, *args, **kwargs):
        super(PropertyListItemDelegate, self).__init__(*args, **kwargs)

    def createEditor(self, parent, option, index):
        model = index.model()
        tagName, displayName, valueType, min, max = model.properties[index.row()]

        if valueType is int:
            valueWidget = QtGui.QSpinBox()
            valueWidget.setMinimum(min)
            valueWidget.setMaximum(max)

        elif valueType is float:
            valueWidget = QtGui.QDoubleSpinBox()
            valueWidget.setMinimum(min)
            valueWidget.setMaximum(max)

        elif valueType is bool:
            valueWidget = QtGui.QCheckBox()

        elif isinstance(valueType, list):  # Choice list
            valueWidget = QtGui.QComboBox()
            for value, name in valueType:
                valueWidget.addItem(name, value)

        elif valueType is unicode:
            valueWidget = QtGui.QPlainTextEdit()

        else:
            raise TypeError("Can't create attribute widgets for %s yet" % valueType)

        valueWidget.setParent(parent)
        return valueWidget

    def setEditorData(self, editor, index):
        model = index.model()
        rootTag = model.rootTag
        tagName, displayName, valueType, min, max = model.properties[index.row()]

        if valueType is int:
            editor.setValue(rootTag[tagName].value)
        elif valueType is float:
            editor.setValue(rootTag[tagName].value)
        elif valueType is bool:
            editor.setChecked(rootTag[tagName].value)
        elif isinstance(valueType, list):  # Choice list
            currentValue = rootTag[tagName].value
            try:
                currentIndex = [v for v, n in valueType].index(currentValue)
                editor.setCurrentIndex(currentIndex)
            except ValueError:
                editor.addItem("Unknown value %s" % currentValue, currentValue)
        elif valueType is unicode:
            editor.setPlainText(rootTag[tagName].value)
        else:
            raise TypeError("Unknown valueType in setEditorData (check this in addNBTProperty, dummy)")

    def setModelData(self, editor, model, index):
        tagName, displayName, valueType, min, max = model.properties[index.row()]
        rootTag = model.rootTag
        if valueType is int:
            value = int(editor.value())
        elif valueType is float:
            value = float(editor.value())
        elif valueType is bool:
            value = editor.isChecked()
        elif isinstance(valueType, list):  # Choice list
            value = valueType[editor.currentIndex()][0]
        elif valueType is unicode:
            value = editor.plainText()
        else:
            raise TypeError("Unknown valueType in setModelData (check this in addNBTProperty, dummy)")

        model.setData(index, value)



class PropertyListEntry(namedtuple('PropertyListEntry', 'tagName displayName valueType min max')):
    pass

class PropertyListModel(QtCore.QAbstractItemModel):
    propertyChanged = QtCore.Signal(unicode, object)

    def __init__(self, rootTag):
        super(PropertyListModel, self).__init__()
        self.rootTag = rootTag
        self.properties = []

    def addNBTProperty(self, tagName, valueType=None, min=None, max=None, displayName=None):
        if displayName is None:
            displayName = tagName
        if valueType is None:
            valueType = int

        if tagName not in self.rootTag:
            return

        tag = self.rootTag[tagName]
        if tag.tagID == nbt.ID_BYTE:
            tagMin = -(1 << 7)
            tagMax = (1 << 7) - 1
        elif tag.tagID == nbt.ID_SHORT:
            tagMin = -(1 << 15)
            tagMax = (1 << 15) - 1
        elif tag.tagID == nbt.ID_INT:
            tagMin = -(1 << 31)
            tagMax = (1 << 31) - 1
        else:  # tag.tagID == nbt.ID_LONG, ID_FLOAT, ID_DOUBLE
            # tagMin = -(1 << 63)  # xxxx 64-bit spinbox
            # tagMax = (1 << 63) - 1
            tagMin = -(1 << 31)
            tagMax = (1 << 31) - 1

        if min is None:
            min = tagMin
        if max is None:
            max = tagMax

        self.properties.append(PropertyListEntry(tagName, displayName, valueType, min, max))

    def columnCount(self, index):
        return 2

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        entry = self.properties[index.row()]

        if role in (Qt.DisplayRole, Qt.EditRole):
            if index.column() == 0:
                return entry.displayName
            else:
                value = self.rootTag[entry.tagName].value
                if isinstance(entry.valueType, (list, tuple)):
                    try:
                        return entry.valueType[value][1]
                    except IndexError:
                        return "Unknown value %s" % value
                else:
                    return value
        # if role == Qt.CheckStateRole:
        #     if entry.valueType is not bool:
        #         return -1
        #     value = self.rootTag[entry.tagName].value
        #     return bool(value)


    def flags(self, index):
        if not index.isValid():
            return 0

        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if index.column() == 1:
            flags |= Qt.ItemIsEditable
            entry = self.properties[index.row()]
            #if entry.valueType is bool:
            #    flags |= Qt.ItemIsUserCheckable
        return flags

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return ("Name", "Value")[section]

        return None

    def index(self, row, column, parent=QtCore.QModelIndex()):
        if parent.isValid():
            return QtCore.QModelIndex()

        return self.createIndex(row, column, None)

    def parent(self, index):
        return QtCore.QModelIndex()

    def rowCount(self, parent=QtCore.QModelIndex()):
        if parent.isValid():
            return 0
        return len(self.properties)

    def setData(self, index, value, role=Qt.EditRole):
        row = index.row()
        entry = self.properties[row]
        if self.rootTag[entry.tagName].value != value:
            self.rootTag[entry.tagName].value = value
            self.propertyChanged.emit(entry.tagName, value)
            self.dataChanged.emit(index, index)

@registerCustomWidget
class PropertyListWidget(QtGui.QTreeView):

    def __init__(self, *args, **kwargs):
        super(PropertyListWidget, self).__init__(*args, **kwargs)
        delegate = PropertyListItemDelegate()
        self.setItemDelegate(delegate)
        self.setEditTriggers(self.CurrentChanged | self.editTriggers())


