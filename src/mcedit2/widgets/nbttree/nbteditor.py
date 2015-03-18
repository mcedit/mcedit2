"""
    nbttreewidget
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from PySide import QtGui, QtCore
from PySide.QtCore import Qt
from mcedit2.command import SimpleRevisionCommand
from mcedit2.util.lazyprop import weakrefprop

from mcedit2.widgets.nbttree.nbttreemodel import NBTFilterProxyModel, NBTPathRole, NBTIcon, NBTTreeModel
from mcedit2.util.load_ui import registerCustomWidget
from mcedit2.widgets.layout import Column


log = logging.getLogger(__name__)


class NBTDataChangeCommand(SimpleRevisionCommand):
    pass

@registerCustomWidget
class NBTEditorWidget(QtGui.QWidget):
    undoCommandPrefixText = ""
    editorSession = weakrefprop()
    proxyModel = None
    rootTag = None

    editMade = QtCore.Signal()  # emitted to allow clients to mark the NBT tree's parent structure as dirty - xxx really??

    def __init__(self, *args, **kwargs):
        super(NBTEditorWidget, self).__init__(*args, **kwargs)
        self.model = None
        self.treeView = QtGui.QTreeView()
        self.treeView.setAlternatingRowColors(True)
        self.treeView.clicked.connect(self.itemClicked)
        self.treeView.expanded.connect(self.itemExpanded)

        self.setLayout(Column(self.treeView))

        self.nbtTypesMenu = QtGui.QMenu()
        self.nbtTypesMenu.addAction(NBTIcon(1), self.tr("Byte"), self.addByte)
        self.nbtTypesMenu.addAction(NBTIcon(2), self.tr("Short"), self.addShort)
        self.nbtTypesMenu.addAction(NBTIcon(3), self.tr("Int"), self.addInt)
        self.nbtTypesMenu.addAction(NBTIcon(4), self.tr("Long"), self.addLong)
        self.nbtTypesMenu.addAction(NBTIcon(5), self.tr("Float"), self.addFloat)
        self.nbtTypesMenu.addAction(NBTIcon(6), self.tr("Double"), self.addDouble)
        self.nbtTypesMenu.addAction(NBTIcon(8), self.tr("String"), self.addString)
        self.nbtTypesMenu.addAction(NBTIcon(9), self.tr("List"), self.addList)
        self.nbtTypesMenu.addAction(NBTIcon(10), self.tr("Compound"), self.addCompound)

        self.nbtTypesMenu.addAction(NBTIcon(7), self.tr("Byte Array"), self.addByteArray)
        self.nbtTypesMenu.addAction(NBTIcon(11), self.tr("Int Array"), self.addIntArray)
        self.nbtTypesMenu.addAction(NBTIcon(12), self.tr("Short Array"), self.addShortArray)


    def setRootTag(self, rootTag, keepExpanded=False):
        if rootTag is self.rootTag:
            return
        self.rootTag = rootTag
        if rootTag is None:
            self.treeView.setModel(None)
            self.model = None
            return

        self.model = NBTTreeModel(rootTag)
        expanded = []
        current = None
        if keepExpanded and self.proxyModel:
            current = self.proxyModel.data(self.treeView.currentIndex(), NBTPathRole)
            def addExpanded(parentIndex):
                for row in range(self.proxyModel.rowCount(parentIndex)):
                    index = self.proxyModel.index(row, 0, parentIndex)
                    if self.treeView.isExpanded(index):
                        expanded.append(self.proxyModel.data(index, NBTPathRole))
                        addExpanded(index)

            addExpanded(QtCore.QModelIndex())


        self.model.dataChanged.connect(self.dataDidChange)
        self.model.rowsInserted.connect(self.rowsDidInsert)
        self.model.rowsRemoved.connect(self.rowsDidRemove)

        self.proxyModel = NBTFilterProxyModel(self)
        self.proxyModel.setSourceModel(self.model)
        # self.proxyModel.setDynamicSortFilter(True)

        self.treeView.setModel(self.model)
        header = self.treeView.header()
        header.setStretchLastSection(False)
        header.setResizeMode(1, header.ResizeMode.Stretch)
        header.setResizeMode(2, header.ResizeMode.Fixed)
        header.setResizeMode(3, header.ResizeMode.Fixed)

        if keepExpanded:
            for path in expanded:
                matches = self.proxyModel.match(self.proxyModel.index(0, 0, QtCore.QModelIndex()),
                                                NBTPathRole, path, flags=Qt.MatchExactly | Qt.MatchRecursive)
                for i in matches:
                    self.treeView.setExpanded(i, True)
            if current is not None:
                matches = self.proxyModel.match(self.proxyModel.index(0, 0, QtCore.QModelIndex()),
                                                NBTPathRole, current, flags=Qt.MatchExactly | Qt.MatchRecursive)
                if len(matches):
                    self.treeView.setCurrentIndex(matches[0])
        else:
            self.treeView.expandToDepth(0)
        self.treeView.sortByColumn(0, Qt.AscendingOrder)
        self.treeView.resizeColumnToContents(0)
        self.treeView.resizeColumnToContents(1)
        self.treeView.resizeColumnToContents(2)
        self.treeView.resizeColumnToContents(3)

    def itemExpanded(self):
        self.treeView.resizeColumnToContents(0)

    indexAddingTo = None

    def itemClicked(self, index):
        #index = self.proxyModel.mapToSource(index)
        item = self.model.getItem(index)
        if index.column() == 2:
            if item.isList and item.tag.list_type:
                row = item.childCount()
                self.model.insertRow(row, index)
                newItemIndex = self.model.index(row, 1, index)
                #self.treeView.setCurrentIndex(self.proxyModel.mapFromSource(newItemIndex))
                #self.treeView.edit(self.proxyModel.mapFromSource(newItemIndex))

            if item.isCompound or (item.isList and not item.tag.list_type):
                self.indexAddingTo = index
                self.nbtTypesMenu.move(QtGui.QCursor.pos())
                self.nbtTypesMenu.show()
        if index.column() == 3:
            parent = self.model.parent(index)
            self.doomedTagName = self.tagNameForUndo(index)
            self.model.removeRow(index.row(), parent)

    def addItemWithType(self, tagID):
        if not self.indexAddingTo:
            return
        item = self.model.getItem(self.indexAddingTo)
        row = item.childCount()
        self.model.insertRow(row, self.indexAddingTo, tagID)
        newItemIndex = self.model.index(row, 0 if item.isCompound else 1, self.indexAddingTo)
        #self.treeView.setCurrentIndex(self.proxyModel.mapFromSource(newItemIndex))
        #self.treeView.edit(self.proxyModel.mapFromSource(newItemIndex))
        self.indexAddingTo = None

    def addByte(self):
        self.addItemWithType(1)

    def addShort(self):
        self.addItemWithType(2)

    def addInt(self):
        self.addItemWithType(3)

    def addLong(self):
        self.addItemWithType(4)

    def addFloat(self):
        self.addItemWithType(5)

    def addDouble(self):
        self.addItemWithType(6)

    def addByteArray(self):
        self.addItemWithType(7)

    def addString(self):
        self.addItemWithType(8)

    def addList(self):
        self.addItemWithType(9)

    def addCompound(self):
        self.addItemWithType(10)

    def addIntArray(self):
        self.addItemWithType(11)

    def addShortArray(self):
        self.addItemWithType(12)



    def tagNameForUndo(self, index):
        parent = self.model.parent(index)
        item = self.model.getItem(index)
        parentItem = self.model.getItem(parent)
        if parentItem is not None and parentItem.isList:
            name = "%s #%d" % (self.tagNameForUndo(parent), parentItem.tag.index(item.tag))
        else:
            name = item.tag.name
        return name

    def dataDidChange(self, index):
        name = self.tagNameForUndo(index)
        if index.column() == 0:
            text = "%sRename NBT tag %s" % (self.undoCommandPrefixText, name)
        elif index.column() == 1:
            text = "%sChange value of NBT tag %s" % (self.undoCommandPrefixText, name)
        else:
            text = "Unknown data changed."

        command = NBTDataChangeCommand(self.editorSession, text)
        with command.begin():
            self.editMade.emit()
            self.editorSession.worldEditor.syncToDisk()
        self.editorSession.pushCommand(command)

    def rowsDidInsert(self, index):
        name = self.tagNameForUndo(index.parent())
        text = "%sInsert NBT tag under %s" % (self.undoCommandPrefixText, name)

        command = NBTDataChangeCommand(self.editorSession, text)
        with command.begin():
            self.editMade.emit()
            self.editorSession.worldEditor.syncToDisk()
        self.editorSession.pushCommand(command)

    doomedTagName = None

    def rowsDidRemove(self, index, start, end):
        name = self.tagNameForUndo(index)
        text = "%sRemove NBT tag %s from %s" % (self.undoCommandPrefixText, self.doomedTagName, name)

        command = NBTDataChangeCommand(self.editorSession, text)
        with command.begin():
            self.editMade.emit()
            self.editorSession.worldEditor.syncToDisk()
        self.editorSession.pushCommand(command)
