"""
    entities
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from mceditlib import nbt
from mceditlib.blocktypes.itemtypes import ItemType
from mceditlib.geometry import Vector
from mceditlib import nbtattr

log = logging.getLogger(__name__)

def PCEntityRef(rootTag, chunk=None):
    # xxx dispatch on rootTag["id"]
    return PCEntityRefBase(rootTag, chunk)

class PCEntityRefBase(object):
    def __init__(self, rootTag, chunk=None):
        self.rootTag = rootTag
        self.chunk = chunk

    def raw_tag(self):
        return self.rootTag

    id = nbtattr.NBTAttr("id", nbt.TAG_String)
    Position = nbtattr.NBTVectorAttr("Pos", nbt.TAG_Double)
    Motion = nbtattr.NBTVectorAttr("Motion", nbt.TAG_Double)
    Rotation = nbtattr.NBTListAttr("Rotation", nbt.TAG_Float)
    UUID = nbtattr.NBTUUIDAttr()

    def copy(self):
        return self.copyWithOffset(Vector(0, 0, 0))

    def copyWithOffset(self, copyOffset, newEntityClass=None):
        if newEntityClass is None:
            newEntityClass = self.__class__
        tag = self.rootTag.copy()
        entity = newEntityClass(tag)
        entity.Position = self.Position + copyOffset

        return self.__class__(tag)

    def dirty(self):
        self.chunk.dirty = True

    @property
    def blockTypes(self):
        return self.chunk.blocktypes

def PCTileEntityRef(rootTag, chunk=None):
    id = rootTag["id"].value
    cls = _tileEntityClasses.get(id, PCTileEntityRefBase)
    return cls(rootTag, chunk)


class PCTileEntityRefBase(object):
    def __init__(self, rootTag, chunk=None):
        self.rootTag = rootTag
        self.chunk = chunk

    def raw_tag(self):
        return self.rootTag

    id = nbtattr.NBTAttr("id", nbt.TAG_String)

    @property
    def Position(self):
        return Vector(*[self.rootTag[c].value for c in 'xyz'])

    @Position.setter
    def Position(self, pos):
        for a, p in zip('xyz', pos):
            self.rootTag[a] = nbt.TAG_Int(p)

    def copy(self):
        return self.copyWithOffset(Vector(0, 0, 0))

    def copyWithOffset(self, copyOffset, newEntityClass=None):
        if newEntityClass is None:
            newEntityClass = self.__class__
        tag = self.rootTag.copy()
        entity = newEntityClass(tag)
        entity.Position = self.Position + copyOffset

        if tag["id"].value in ("Painting", "ItemFrame"):
            tag["TileX"].value += copyOffset[0]
            tag["TileY"].value += copyOffset[1]
            tag["TileZ"].value += copyOffset[2]

        return self.__class__(tag)

    def dirty(self):
        self.chunk.dirty = True

    @property
    def blockTypes(self):
        return self.chunk.blocktypes

class ItemStackRef(nbtattr.NBTCompoundRef):
    def __init__(self, rootTag=None, parent=None):
        if rootTag is None:
            rootTag = nbt.TAG_Compound()
            nbtattr.SetNBTDefaults(self)
        super(ItemStackRef, self).__init__(rootTag, parent)

    Damage = nbtattr.NBTAttr("Damage", nbt.TAG_Short, 0)
    Count = nbtattr.NBTAttr("Count", nbt.TAG_Byte, 1)
    Slot = nbtattr.NBTAttr("Slot", nbt.TAG_Byte)

    @property
    def id(self):
        if self.rootTag["id"].tagID == nbt.TAG_Short:
            if self.blockTypes is None:
                log.warn("No blocktypes available, returning id")
                return self.rootTag["id"].value
            try:
                itemType = self.blockTypes.itemTypes[self.rootTag["id"].value]
                return itemType.internalName
            except KeyError:
                log.warn("No ItemType defined for %s, returning id" % self.rootTag["id"].value)
                return self.rootTag["id"].value

        return self.rootTag["id"].value

    @id.setter
    def id(self, value):
        if isinstance(value, ItemType):
            self.rootTag["id"] = nbt.TAG_String(value.internalName)
            if value.meta is not None:
                self.Damage = value.meta
        elif isinstance(value, int):
            self.rootTag["id"] = nbt.TAG_Short(value)
        elif isinstance(value, basestring):
            self.rootTag["id"] = nbt.TAG_String(value)
        else:
            raise TypeError("Invalid type for ItemStackRef.id: %r", type(value))

        self.dirty = True

    @property
    def itemType(self):
        if self.blockTypes is None:
            raise ValueError("Cannot get itemType for this item. BlockTypes not set. ")
        try:
            itemType = self.blockTypes.itemTypes[self.rootTag["id"].value, self.Damage]
            return itemType
        except KeyError:
            raise ValueError("Cannot get itemType for this item. BlockTypes has no item for %s." % self.rootTag["id"].value)

    @itemType.setter
    def itemType(self, value):
        if not isinstance(value, ItemType):
            raise TypeError("Expected ItemType, got %r", type(value))
        self.id = value


    @property
    def raw_id(self):
        return self.rootTag["id"].value

    @raw_id.setter
    def raw_id(self, value):
        if isinstance(value, int):
            self.rootTag["id"] = nbt.TAG_Short(value)
        elif isinstance(value, basestring):
            self.rootTag["id"] = nbt.TAG_String(value)
        else:
            raise TypeError("Invalid type for ItemStack.id: %r", type(value))

        self.dirty = True

    @staticmethod
    def tagIsItemStack(tag):
        if tag.tagID != nbt.ID_COMPOUND:
            return False
        return "id" in tag and "Damage" in tag and "Count" in tag


class SlotsListProxy(nbtattr.NBTListProxy):
    def putItemInSlot(self, item, slot):
        existing = [stack for stack in self if stack.Slot == slot]
        for stack in existing:
            self.remove(stack)

        item.Slot = slot
        self.append(item)

    def getItemInSlot(self, slot):
        for stack in self:
            if stack.Slot == slot:
                return stack

        return None


class SlottedInventoryAttr(nbtattr.NBTCompoundListAttr):
    def __init__(self, name):
        super(SlottedInventoryAttr, self).__init__(name, ItemStackRef)
        self.listProxyClass = SlotsListProxy


class PCTileEntityChestRef(PCTileEntityRefBase):
    Items = SlottedInventoryAttr("Items")

    def __init__(self, rootTag, chunk=None):
        super(PCTileEntityChestRef, self).__init__(rootTag, chunk)

    def putItemInSlot(self, item, slot):
        self.Items.putItemInSlot(item, slot)

    def getItemInSlot(self, slot):
        return self.Items.getItemInSlot(slot)

_tileEntityClasses = {
    "Chest": PCTileEntityChestRef,
    "Trap": PCTileEntityChestRef,
    "Hopper": PCTileEntityChestRef,
}

def registerTileEntityRefClass(ID, refClass):
    _tileEntityClasses[ID] = refClass

"""

    ItemStack usage:

Manipulating items in MCEdit is made easier by the ItemStack and ItemType classes.

An ItemStack is a reference to a single stack of items. It can either be located in a world, such as in a chest or as
a dropped item entity or in the player's inventory, or it can be unconnected to any world. For unconnected items,
which are always those created directly rather than loaded from a world, the `itemType` pseudo-attribute is
unavailable and the item ID may be returned numerically in some cases.

An ItemStack has four attributes: `ID`, `Damage`, `Count` and `tag`.

  `ID`

`ID` accepts either strings, numeric values, or ItemType objects; when the world data is saved, the `ID` is converted
to the correct format. If the ItemType's damage value forms part of the item's identity, the ItemStack's Damage is
also set. If the item is unconnected and the item is in 1.7 format or has previously been given a numeric ID, its
numeric ID will be returned. To ensure that `ID` always returns a string, either connect the world by adding it to
a container that is itself connected to the world, or always assign the item ID as a string.

  `Damage`

For some item types such as wool, dye, and stained clay, the `Damage` value forms part of its identity. For other items
such as tools and fishing rods, `Damage` is the actual amount of damage the item has sustained - an undamaged item has
a value of zero.

  `Count`

The number of items in this stack. For each item type, Minecraft has a maximum number of items that can be stacked
(usually 64, 16, or 1). There is no protection against creating stacks larger than Minecraft's limit, and large stacks
are actually usable in-game; you simply cannot re-stack them that large while playing.

Another pseudo-attribute `itemType` is also provided. Accessing this attribute always returns an ItemType object from
the ItemStack's parent world's ItemTypeSet. If no ItemType is found or the ItemStack is not parented to a world,
ValueError is raised.

An ItemStack sometimes has an attribute `Slot` which is only used when the item is contained by an ordered inventory,
such as a chest or a player's inventory. The `Slot` value is generally managed by the object containing the
ItemStacks; assigning the same `Slot` value to two ItemStacks in the same container has undefined behavior.


A newly created ItemStack has Damage=0 and Count=1.

An ItemType is a value type that corresponds one-to-one with a numeric item ID (for Minecraft 1.7)
and a textual internalName (for Forge 1.7 and Minecraft 1.8). Each ItemType uniquely identifies an item
and can be used to find the item's icon, localized name, maximum stack size, and whether the item's
damage value is treated as an ID number (such as for colored wool and clay) or is treated as an actual
amount of damage the item has suffered. Since the id<->internalName mapping is defined in the world file for
Forge 1.7, ItemTypes are specific to a world.

For items which use the damage value as an ID number, ItemTypes for each unique damage value are present
in the world's ItemTypeSet. You can use the set to look up an ItemType and get its display name and other attributes.

    Examples:

  Creating a new chest, then creating a new item stack and adding it to the chest:

world = load_my_world()  # defined elsewhere

chest = PCTileEntityChestRef()

diamondAxe = ItemStackRef()
diamondAxe.id = "diamond_axe"

chest.putItemInSlot(diamondAxe, 0)

chest.Position = (10, 64, 0)

world.setBlock(10, 64, 0, "chest[facing=north]")
world.addTileEntity(chest)

  Searching a chest for iron tools and upgrading them to diamond:

chest = find_my_chest()  # defined elsewhere

for stack in chest.Items:
    if stack.id in ("iron_pickaxe", "iron_axe", "iron_sword", "iron_shovel", "iron_hoe"):
        stack.id = stack.id.replace("iron", "diamond")

"""
