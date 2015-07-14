"""
    storagedrawers
"""
from __future__ import absolute_import, division, print_function
import logging

from mcedit2.widgets.inspector.tileentities.chest import GenericContainerEditorWidget
from mcedit2.plugins import registerBlockInspectorWidget
from mceditlib import nbtattr, nbt
from mceditlib.anvil.entities import PCTileEntityRefBase, registerTileEntityRefClass
from mceditlib.blocktypes.itemtypes import ItemType

log = logging.getLogger(__name__)


class DrawerItemStackRef(nbtattr.NBTCompoundRef):
    def __init__(self, rootTag=None, parent=None):
        if rootTag is None:
            rootTag = nbt.TAG_Compound()
            nbtattr.SetNBTDefaults(self)
        super(DrawerItemStackRef, self).__init__(rootTag, parent)

    Damage = nbtattr.NBTAttr("Meta", nbt.TAG_Short, 0)
    Count = nbtattr.NBTAttr("Count", nbt.TAG_Int, 1)

    @property
    def id(self):
        if self.blockTypes is None:
            log.warn("No blocktypes available, returning id")
            return self.rootTag["Item"].value
        try:
            itemType = self.blockTypes.itemTypes[self.rootTag["Item"].value]
            return itemType.internalName
        except KeyError:
            log.warn("No ItemType defined for %s, returning id" % self.rootTag["Item"].value)
            return self.rootTag["Item"].value

    @id.setter
    def id(self, value):
        if isinstance(value, ItemType):
            self.rootTag["Item"] = nbt.TAG_Short(value.ID)
            if value.meta is not None:
                self.Damage = value.meta
        elif isinstance(value, int):
            self.rootTag["Item"] = nbt.TAG_Short(value)
        elif isinstance(value, basestring):
            if self.blockTypes is None:
                raise ValueError("DrawerItemStackRef must be parented to assign string IDs")
            self.rootTag["Item"] = nbt.TAG_Short(self.blockTypes.itemTypes[value].ID)
        else:
            raise TypeError("Invalid type for ItemStackRef.id: %r", type(value))

        self.dirty = True

    @property
    def itemType(self):
        if self.blockTypes is None:
            raise ValueError("Cannot get itemType for this item. BlockTypes not set. ")
        try:
            itemType = self.blockTypes.itemTypes[self.rootTag["Item"].value, self.Damage]
            return itemType
        except KeyError:
            raise ValueError("Cannot get itemType for this item. BlockTypes has no item for %s." % self.rootTag["Item"].value)

    @itemType.setter
    def itemType(self, value):
        if not isinstance(value, ItemType):
            raise TypeError("Expected ItemType, got %r", type(value))
        self.id = value

    @property
    def raw_id(self):
        return self.rootTag["Item"].value

    @raw_id.setter
    def raw_id(self, value):
        if isinstance(value, int):
            self.rootTag["Item"] = nbt.TAG_Short(value)
        elif isinstance(value, basestring):
            if self.blockTypes is None:
                raise ValueError("DrawerItemStackRef must be parented to assign string IDs")
            self.rootTag["Item"] = nbt.TAG_Short(self.blockTypes.itemTypes[value].ID)
        else:
            raise TypeError("Invalid type for ItemStack.id: %r", type(value))

        self.dirty = True

    @staticmethod
    def tagIsItem(tag):
        if tag.tagID != nbt.ID_COMPOUND:
            return False
        return "Item" in tag and "Meta" in tag and "Count" in tag


class DrawerSlotsListProxy(nbtattr.NBTListProxy):
    def putItemInSlot(self, item, slot):
        # extend self?
        self[slot] = item

    def getItemInSlot(self, slot):
        if slot >= len(self):
            return None
        return self[slot]

class DrawerInventoryAttr(nbtattr.NBTCompoundListAttr):
    def __init__(self, name="Slots"):
        super(DrawerInventoryAttr, self).__init__(name, DrawerItemStackRef)
        self.listProxyClass = DrawerSlotsListProxy


class StorageDrawerRef(PCTileEntityRefBase):
    Slots = DrawerInventoryAttr()

    def __init__(self, rootTag, chunk=None):
        super(StorageDrawerRef, self).__init__(rootTag, chunk)

DRAWERS4_SLOT_LAYOUT = [(s % 2, s // 2, s) for s in range(4)]
DRAWERS2_SLOT_LAYOUT = [(s, 0, s) for s in range(2)]
DRAWERS1_SLOT_LAYOUT = [(1, 0, 0)]

class StorageDrawers4EditorWidget(GenericContainerEditorWidget):
    tileEntityID = "StorageDrawers:halfDrawers4"

    def __init__(self, editorSession, tileEntityRef):
        super(StorageDrawers4EditorWidget, self).__init__("StorageDrawers:halfDrawers4", DRAWERS4_SLOT_LAYOUT, editorSession, tileEntityRef)

    def getItemsRef(self):
        return self.tileEntityRef.Slots

registerTileEntityRefClass("StorageDrawers:halfDrawers4", StorageDrawerRef)
registerBlockInspectorWidget(StorageDrawers4EditorWidget)
