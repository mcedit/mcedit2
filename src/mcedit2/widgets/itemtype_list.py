"""
    itemtype_list
"""
from __future__ import absolute_import, division, print_function
import json
from PySide import QtCore, QtGui
import logging
from PySide.QtCore import Qt
from mcedit2.util.mimeformats import MimeFormats
from mcedit2.util.resources import resourcePath
from mcedit2.widgets.blocktype_list import BlockTypePixmap

log = logging.getLogger(__name__)

ICON_SIZE = 48

class ItemTypeListModel(QtCore.QAbstractListModel):
    InternalNameRole = Qt.UserRole
    DamageRole = InternalNameRole + 1

    def __init__(self, editorSession):
        super(ItemTypeListModel, self).__init__()
        assert editorSession is not None
        self.editorSession = editorSession
        self.itemTypes = self.editorSession.worldEditor.blocktypes.itemTypes
        self.allItems = sorted(self.itemTypes, key=lambda i: i.ID)

    def rowCount(self, parent):
        if parent.isValid():
            return 0

        return len(self.itemTypes)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        itemType = self.allItems[row]
        if role == Qt.DisplayRole:
            return itemType.displayName
        if role == Qt.DecorationRole:
            return ItemTypeIcon(itemType, self.editorSession)
        if role == self.InternalNameRole:
            return itemType.internalName
        if role == self.DamageRole:
            return itemType.meta

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        return super(ItemTypeListModel, self).flags(index) | Qt.ItemIsDragEnabled

    def mimeTypes(self):
        return [MimeFormats.ItemType]

    def mimeData(self, indexes):
        mimeData = QtCore.QMimeData()
        itemData = [(index.data(self.InternalNameRole), index.data(self.DamageRole))
                    for index in indexes]
        mapItemData = json.dumps(itemData)
        mimeData.setData(MimeFormats.ItemType,
                         mapItemData)

        return mimeData


def ItemTypeIcon(itemType, editorSession, itemStack=None):
    textureName = itemType.texture
    if textureName is None:
        try:
            if itemType.damage is not None:
                if itemStack is not None:
                    damage = itemStack.Damage
                else:
                    damage = itemType.damage
                block = editorSession.worldEditor.blocktypes[itemType.ID, damage]
            else:
                block = editorSession.worldEditor.blocktypes[itemType.ID]
            pixmap = BlockTypePixmap(block, editorSession.textureAtlas, 48)
            return QtGui.QIcon(pixmap)
        except Exception as e:
            log.exception("Failed to load block texture for item icon %s: %s", itemType, e)
            return None
    try:
        textureFile = editorSession.resourceLoader.openStream("assets/minecraft/textures/items/%s" % textureName)
        data = textureFile.read()
        image = QtGui.QImage.fromData(data).scaled(ICON_SIZE, ICON_SIZE)
        return QtGui.QIcon(QtGui.QPixmap.fromImage(image))
    except Exception as e:
        log.exception("Failed to load texture %s: %s", textureName, e)
        return getDefaultIcon()

_defaultIcon = None


def getDefaultIcon():
    global _defaultIcon
    if _defaultIcon is None:
        texturePath = resourcePath("mcedit2/assets/mcedit2/block_unknown.png")
        with open(texturePath, "rb") as f:
            data = f.read()

        image = QtGui.QImage.fromData(data).scaled(ICON_SIZE, ICON_SIZE)
        _defaultIcon = QtGui.QIcon(QtGui.QPixmap.fromImage(image))

    return _defaultIcon
