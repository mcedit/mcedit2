"""
    entities
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import uuid

from mceditlib import nbt
from mceditlib.blocktypes import VERSION_1_7, VERSION_1_8
from mceditlib.blocktypes.itemtypes import ItemType
from mceditlib.geometry import Vector
from mceditlib import faces
from mceditlib import nbtattr
from mceditlib.selection import BoundingBox

log = logging.getLogger(__name__)


class NoParentError(RuntimeError):
    """
    Raised when setting the `id` of an ItemStack with no parent.
    """

class ItemRef(nbtattr.NBTCompoundRef):
    def __init__(self, rootTag=None, parent=None):
        if rootTag is None:
            rootTag = nbt.TAG_Compound()
            nbtattr.SetNBTDefaults(self)

        super(ItemRef, self).__init__(rootTag, parent)

    Damage = nbtattr.NBTAttr("Damage", 's', 0)
    Count = nbtattr.NBTAttr("Count", 'b', 1)
    tag = nbtattr.NBTAttr("tag", nbt.TAG_Compound)

    @property
    def id(self):
        idTag = self.rootTag["id"]
        if idTag.tagID == nbt.ID_SHORT:
            if self.blockTypes is None:
                log.warn("No blocktypes available, returning id")
                return idTag.value
            try:
                itemType = self.blockTypes.itemTypes[idTag.value]
                return itemType.internalName
            except KeyError:
                log.warn("No ItemType defined for %s, returning id" % idTag.value)
                return idTag.value
        else:
            return idTag.value

    @id.setter
    def id(self, value):
        if "id" not in self.rootTag:
            # no id tag - freshly minted item tag
            # get proper tag type from blocktypes
            if self.blockTypes is None:
                raise NoParentError("ItemRef must be parented to a world before assigning id for the first time.")
            if self.blockTypes.itemStackVersion == VERSION_1_7:
                self.rootTag["id"] = nbt.TAG_Short(0)
            elif self.blockTypes.itemStackVersion == VERSION_1_8:
                self.rootTag["id"] = nbt.TAG_String("minecraft:air")
            else:
                raise AssertionError("Unexpected itemStackVersion: %s", self.blockTypes.itemStackVersion)

        idTag = self.rootTag["id"]
        if isinstance(value, ItemType):
            if idTag.tagID == nbt.ID_STRING:
                idTag.value = value.internalName
            else:
                idTag.value = value.ID
            if value.meta is not None:
                self.Damage = value.meta
        elif isinstance(value, int):
            if idTag.tagID == nbt.ID_SHORT:
                self.rootTag["id"].value = value
            elif idTag.tagID == nbt.ID_STRING:
                if self.blockTypes is None:
                    raise NoParentError("ItemRef must be parented to a world before assigning numeric IDs to an 1.8 ItemStack.")

                itemType = self.blockTypes.itemTypes[value]
                self.rootTag["id"].value = itemType.internalName
        elif isinstance(value, basestring):
            if idTag.tagID == nbt.ID_STRING:
                self.rootTag["id"].value = value
            elif idTag.tagID == nbt.ID_SHORT:
                if self.blockTypes is None:
                    raise NoParentError("ItemRef must be parented to a world before assigning textual IDs to an 1.7 ItemStack.")

                itemType = self.blockTypes.itemTypes[value]
                self.rootTag["id"].value = itemType.ID
        else:
            raise TypeError("Invalid type for ItemRef.id: %r", type(value))

        self.dirty = True

    @property
    def itemType(self):
        ID = self.rootTag["id"].value
        if self.blockTypes is None:
            raise ValueError("Cannot get itemType for this item. BlockTypes not set. ")
        try:
            itemType = self.blockTypes.itemTypes[ID, self.Damage]
            return itemType
        except KeyError:
            raise ValueError("Cannot get itemType for this item. BlockTypes has no item for %s." % ID)

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
            raise TypeError("Invalid type for ItemRef.id: %r", type(value))

        self.dirty = True

    @staticmethod
    def tagIsItem(tag):
        if tag.tagID != nbt.ID_COMPOUND:
            return False
        return "id" in tag and "Damage" in tag and "Count" in tag


class ItemStackRef(ItemRef):
    Slot = nbtattr.NBTAttr("Slot", 'b')


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

    def createItemInSlot(self, slot):
        for stack in self:
            if stack.Slot == slot:
                raise KeyError("Slot %d already occupied." % slot)
        ref = ItemStackRef(None, self)
        ref.Slot = slot
        self.append(ref.rootTag)
        return ref


class SlottedInventoryAttr(nbtattr.NBTCompoundListAttr):
    def __init__(self, name):
        super(SlottedInventoryAttr, self).__init__(name, ItemStackRef)
        self.listProxyClass = SlotsListProxy


class _PCEntityRef(object):

    def create(self, entityID):
        cls = _entityClasses.get(entityID)
        if cls is None:
            log.info("No PC entity ref class found for %s", entityID)
            cls = PCEntityRefBase
        ref = cls.create()
        ref.id = entityID
        return ref

    def __call__(self, rootTag, chunk=None):
        id = rootTag["id"].value
        cls = _entityClasses.get(id, PCEntityRefBase)
        return cls(rootTag, chunk)

PCEntityRef = _PCEntityRef()


class EntityPtr(object):
    def __init__(self, dim, box, uuid):
        self.dim = dim
        self.box = box
        self.uuid = uuid

    def get(self):
        entities = self.dim.getEntities(self.box, UUID=self.uuid)
        for entity in entities:
            return entity

    @staticmethod
    def create(entity):
        box = BoundingBox(entity.Position.intfloor(), (1, 1, 1)).chunkBox(entity.chunk.dimension)
        return EntityPtr(entity.chunk.dimension, box, entity.UUID)


class CommandStatsRef(nbtattr.NBTCompoundRef):
    SuccessCountObjective = nbtattr.NBTAttr('SuccessCountObjective', 't')
    SuccessCountName = nbtattr.NBTAttr('SuccessCountName', 't')
    AffectedBlocksObjective = nbtattr.NBTAttr('AffectedBlocksObjective', 't')
    AffectedBlocksName = nbtattr.NBTAttr('AffectedBlocksName', 't')
    AffectedEntitiesObjective = nbtattr.NBTAttr('AffectedEntitiesObjective', 't')
    AffectedEntitiesName = nbtattr.NBTAttr('AffectedEntitiesName', 't')
    AffectedItemsObjective = nbtattr.NBTAttr('AffectedItemsObjective', 't')
    AffectedItemsName = nbtattr.NBTAttr('AffectedItemsName', 't')
    QueryResultObjective = nbtattr.NBTAttr('QueryResultObjective', 't')
    QueryResultName = nbtattr.NBTAttr('QueryResultName', 't')


class PCEntityRefBase(object):
    def __init__(self, rootTag, chunk=None):
        self.rootTag = rootTag
        self.chunk = chunk
        self.parent = None  # xxx used by WorldEditor for newly created, non-chunked refs

    def raw_tag(self):
        return self.rootTag

    @classmethod
    def create(cls):
        rootTag = nbt.TAG_Compound()
        ref = cls(rootTag)
        nbtattr.SetNBTDefaults(ref)
        return ref

    entityID = NotImplemented

    id = nbtattr.NBTAttr("id", 't')
    Position = nbtattr.NBTVectorAttr("Pos", 'd')
    Motion = nbtattr.NBTVectorAttr("Motion", 'd')
    Rotation = nbtattr.NBTListAttr("Rotation", 'f')

    FallDistance = nbtattr.NBTAttr("FallDistance", 'f')
    Fire = nbtattr.NBTAttr("Fire", 's')
    Air = nbtattr.NBTAttr("Air", 's')
    OnGround = nbtattr.NBTAttr("OnGround", 'b')
    Dimension = nbtattr.NBTAttr("Dimension", 'i')
    Invulnerable = nbtattr.NBTAttr("Invulnerable", 'b')
    PortalCooldown = nbtattr.NBTAttr("PortalCooldown", 'i')
    CustomName = nbtattr.NBTAttr("CustomName", 't')
    CustomNameVisible = nbtattr.NBTAttr("CustomNameVisible", 'b')
    Silent = nbtattr.NBTAttr("Silent", 'b')

    Passengers = nbtattr.NBTCompoundListAttr("Passengers", PCEntityRef)

    Glowing = nbtattr.NBTAttr("Glowing", 'b')
    Tags = nbtattr.NBTListAttr("Tags", 's')

    CommandStats = nbtattr.NBTCompoundAttr('CommandStats', CommandStatsRef)

    UUID = nbtattr.NBTUUIDAttr()

    def copy(self):
        return self.copyWithOffset(Vector(0, 0, 0))

    def copyWithOffset(self, copyOffset, newEntityClass=None):
        if newEntityClass is None:
            newEntityClass = self.__class__
        tag = self.rootTag.copy()
        entity = newEntityClass(tag)
        entity.Position = self.Position + copyOffset
        entity.UUID = uuid.uuid1()

        return self.__class__(tag)

    @property
    def dirty(self):
        if self.chunk:
            return self.chunk.dirty
        return True

    @dirty.setter
    def dirty(self, value):
        if self.chunk:
            self.chunk.dirty = value

    @property
    def blockTypes(self):
        if self.chunk:
            return self.chunk.blocktypes
        if self.parent:
            return self.parent.blocktypes
        return None


class MobAttributeModifierRef(nbtattr.NBTCompoundRef):
    Name = nbtattr.NBTAttr('Name', 't')
    Amount = nbtattr.NBTAttr('Amount', 'd')
    Operation = nbtattr.NBTAttr('Operation', 'i')

    UUID = nbtattr.NBTUUIDAttr()


class MobAttributeRef(nbtattr.NBTCompoundRef):
    Name = nbtattr.NBTAttr('Name', 't')
    Base = nbtattr.NBTAttr('Base', 'd')
    Modifiers = nbtattr.NBTCompoundListAttr('Modifiers', MobAttributeModifierRef)


class MobPotionEffectRef(nbtattr.NBTCompoundRef):
    Id = nbtattr.NBTAttr('Id', 'b')
    Amplifier = nbtattr.NBTAttr('Amplifier', 'b')
    Duration = nbtattr.NBTAttr('Duration', 'i')
    Ambient = nbtattr.NBTAttr('Ambient', 'b')
    ShowParticles = nbtattr.NBTAttr('ShowParticles', 'b')


class PCEntityMobRefBase(PCEntityRefBase):

    # xxx add rootTag[Health] as Short (1.8) or Float(1.9)?
    @property
    def Health(self):
        if 'HealF' in self.rootTag:
            return self.rootTag['HealF'].value
        elif 'Health' in self.rootTag:
            return self.rootTag['Health'].value
        else:
            self.rootTag['Health'] = nbt.TAG_Short(0.)
            self.rootTag['HealF'] = nbt.TAG_Float(0.)
            return 0

    @Health.setter
    def Health(self, val):
        if 'HealF' in self.rootTag:
            self.rootTag['HealF'].value = val
        elif 'Health' in self.rootTag:
            self.rootTag['Health'].value = val
        else:
            self.rootTag['Health'] = nbt.TAG_Short(val)
            self.rootTag['HealF'] = nbt.TAG_Float(val)

    AbsorptionAmount = nbtattr.NBTAttr('AbsorptionAmount', 'f')
    HurtTime = nbtattr.NBTAttr('HurtTime', 's')
    HurtByTimestamp = nbtattr.NBTAttr('HurtByTimestamp', 'i')
    DeathTime = nbtattr.NBTAttr('DeathTime', 's')

    Attributes = nbtattr.NBTCompoundListAttr('Attributes', MobAttributeRef)
    ActiveEffects = nbtattr.NBTCompoundListAttr('ActiveEffects', MobPotionEffectRef)


class PCPaintingEntityRefBase(PCEntityRefBase):
    # XXXXXXXXX
    # in 1.8, TilePos is the block the painting is IN
    # in 1.7, TilePos is the block the painting is ON
    TilePos = nbtattr.KeyedVectorAttr('TileX', 'TileY', 'TileZ', nbt.TAG_Int, (0, 0, 0))

    # XXXXXXXXXXX
    # in 1.7 and before, this tag is called "Direction"
    # in some version before that, it is called "Dir" and its enums are different!
    Facing = nbtattr.NBTAttr('Facing', 'b', 0)

    SouthFacing = 0
    WestFacing = 1
    NorthFacing = 2
    EastFacing = 3

    _mceditFacings = {
        faces.FaceSouth: SouthFacing,
        faces.FaceWest: WestFacing,
        faces.FaceNorth: NorthFacing,
        faces.FaceEast: EastFacing,

    }

    def copyWithOffset(self, copyOffset, newEntityClass=None):
        ref = super(PCPaintingEntityRefBase, self).copyWithOffset(copyOffset)

        ref.TilePos += copyOffset

        return ref

    def facingForMCEditFace(self, face):
        return self._mceditFacings.get(face, None)


class PCPaintingEntityRef(PCPaintingEntityRefBase):
    Motive = nbtattr.NBTAttr("Motive", 't')


class PCItemFrameEntityRef(PCPaintingEntityRefBase):
    Item = nbtattr.NBTCompoundAttr("Item", ItemRef)


class PCBatEntityRef(PCEntityMobRefBase):
    BatFlags = nbtattr.NBTAttr("BatFlags", 'b', 0)


class PCChickenEntityRef(PCEntityMobRefBase):
    IsChickenJockey = nbtattr.NBTAttr("IsChickenJockey", 'b', 0)
    EggLayTime = nbtattr.NBTAttr("EggLayTime", 'i', 0)


class PCPigEntityRef(PCEntityMobRefBase):
    Saddle = nbtattr.NBTAttr("Saddle", 'b', 0)


class PCRabbitEntityRef(PCEntityMobRefBase):
    # Possible values:
    # 0: Brown
    # 1: White
    # 2: Black
    # 3: Black&White
    # 4: Gold
    # 5: Salt&Pepper
    # 99: Killer
    RabbitType = nbtattr.NBTAttr("RabbitType", 'i', 0)
    MoreCarrotTicks = nbtattr.NBTAttr("MoreCarrotTicks", 'i', 0)


class PCSheepEntityRef(PCEntityMobRefBase):
    Sheared = nbtattr.NBTAttr("Sheared", 'b', 0)

    # Same values as wool colors
    Color = nbtattr.NBTAttr("Color", 'b', 0)


class PCVillagerEntityRef(PCEntityMobRefBase):
    Profession = nbtattr.NBTAttr("Profession", 'i', 0)


_entityClasses = {
    # - Passive -
    "Bat": PCBatEntityRef,
    "Chicken": PCChickenEntityRef,
    "Cow": PCEntityMobRefBase,
    "MushroomCow": PCEntityMobRefBase,
    "Pig": PCPigEntityRef,
    "Rabbit": PCRabbitEntityRef,
    "Sheep": PCSheepEntityRef,
    "Squid": PCEntityMobRefBase,
    "Villager": PCVillagerEntityRef,
    "ItemFrame": PCItemFrameEntityRef,
}



class _PCTileEntityRef(object):

    def create(self, entityID):
        cls = _tileEntityClasses.get(entityID)
        if cls is None:
            log.info("No PC tile entity ref class found for %s", entityID)
            cls = PCTileEntityRefBase
        ref = cls.create()
        ref.id = entityID
        return ref

    def __call__(self, rootTag, chunk=None):
        id = rootTag["id"].value
        cls = _tileEntityClasses.get(id, PCTileEntityRefBase)
        return cls(rootTag, chunk)

PCTileEntityRef = _PCTileEntityRef()


class PCTileEntityRefBase(object):
    def __init__(self, rootTag, chunk=None):
        self.rootTag = rootTag
        self.chunk = chunk

    def raw_tag(self):
        return self.rootTag

    @classmethod
    def create(cls):
        rootTag = nbt.TAG_Compound()
        ref = cls(rootTag)
        nbtattr.SetNBTDefaults(ref)
        return ref

    tileEntityID = NotImplemented

    id = nbtattr.NBTAttr("id", 't')
    Position = nbtattr.KeyedVectorAttr('x', 'y', 'z', nbt.TAG_Int, 0)

    def copy(self):
        return self.copyWithOffset(Vector(0, 0, 0))

    def copyWithOffset(self, copyOffset, newEntityClass=None):
        if newEntityClass is None:
            newEntityClass = self.__class__
        tag = self.rootTag.copy()
        entity = newEntityClass(tag)
        entity.Position = self.Position + copyOffset

        return self.__class__(tag)

    @property
    def dirty(self):
        if self.chunk:
            return self.chunk.dirty
        return True

    @dirty.setter
    def dirty(self, value):
        if self.chunk:
            self.chunk.dirty = value

    @property
    def blockTypes(self):
        return self.chunk.blocktypes


class PCTileEntityControlRef(PCTileEntityRefBase):
    tileEntityID = "Control"

    Command = nbtattr.NBTAttr("Command", 't', "")
    CustomName = nbtattr.NBTAttr("CustomName", 't', "")
    SuccessCount = nbtattr.NBTAttr("SuccessCount", 'i', 0)
    TrackOutput = nbtattr.NBTAttr("TrackOutput", 'b', 1)


class PCTileEntitySignRef(PCTileEntityRefBase):
    tileEntityID = "Sign"

    Text1 = nbtattr.NBTAttr("Text1", 't', "")
    Text2 = nbtattr.NBTAttr("Text2", 't', "")
    Text3 = nbtattr.NBTAttr("Text3", 't', "")
    Text4 = nbtattr.NBTAttr("Text4", 't', "")


def convertStackTo17(stack, blocktypes):
    if stack["id"].tagID == nbt.ID_STRING:
        stack["id"] = nbt.TAG_Short(blocktypes.itemTypes.internalNamesByID[stack["id"].value])


def convertStackTo18(stack, blocktypes):
    if stack["id"].tagID == nbt.ID_SHORT:
        stack["id"] = nbt.TAG_Short(blocktypes.itemTypes[stack["id"].value].ID)


def convertAllStacks(tags, blocktypes, version):
    if version == VERSION_1_7:
        convertStack = convertStackTo17
    elif version == VERSION_1_8:
        convertStack = convertStackTo18
    else:
        raise ValueError("Unknown item stack version %d" % version)

    for tag in tags:
        if ItemRef.tagIsItem(tag):
            convertStack(tag)
        if tag.tagID == nbt.ID_COMPOUND:
            convertAllStacks(tag.itervalues(), blocktypes, version)
        if tag.tagID == nbt.ID_LIST and tag.list_type in (nbt.ID_LIST, nbt.ID_COMPOUND):
            convertAllStacks(tag, blocktypes, version)


class PCTileEntityChestRef(PCTileEntityRefBase):
    Items = SlottedInventoryAttr("Items")

    def __init__(self, rootTag, chunk=None):
        super(PCTileEntityChestRef, self).__init__(rootTag, chunk)

    def putItemInSlot(self, item, slot):
        self.Items.putItemInSlot(item, slot)

    def getItemInSlot(self, slot):
        return self.Items.getItemInSlot(slot)

    def createItemInSlot(self, slot):
        return self.Items.createItemInSlot(slot)

_tileEntityClasses = {
    "Chest": PCTileEntityChestRef,
    "Trap": PCTileEntityChestRef,
    "Hopper": PCTileEntityChestRef,
    "Control": PCTileEntityControlRef,
    "Sign": PCTileEntitySignRef,

}

def validate(ref):
    """
    xxx search attributes of ref.__class__ for NBTAttrs, check ref's tag contains a tag
    for that attr is present and matches the tag type
    :param ref: nbtattr.NBTCompoundRef
    :return:
    """
    raise NotImplementedError

def registerTileEntityRefClass(ID, refClass):
    _tileEntityClasses[ID] = refClass

def unregisterTileEntityRefClass(cls):
    dead = [k for k, v in _tileEntityClasses.iteritems() if v == cls]
    for k in dead:
        _tileEntityClasses.pop(k, None)

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
