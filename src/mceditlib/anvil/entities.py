"""
    entities
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from mceditlib import nbt
from mceditlib.geometry import Vector
from mceditlib.nbtattr import NBTAttr, NBTVectorAttr, NBTListAttr

log = logging.getLogger(__name__)


class PCEntityRef(object):
    def __init__(self, rootTag, chunk=None):
        self.rootTag = rootTag
        self.chunk = chunk

    def raw_tag(self):
        return self.rootTag

    id = NBTAttr("id", nbt.TAG_String)
    Position = NBTVectorAttr("Pos", nbt.TAG_Double)
    Motion = NBTVectorAttr("Motion", nbt.TAG_Double)
    Rotation = NBTListAttr("Rotation", nbt.TAG_Float)

    def copy(self):
        return self.copyWithOffset(Vector(0, 0, 0))

    def copyWithOffset(self, copyOffset, newEntityClass=None):
        if newEntityClass is None:
            newEntityClass = self.__class__
        tag = self.rootTag.copy()
        entity = newEntityClass(tag)
        entity.Position = self.Position + copyOffset

        return PCEntityRef(tag, None)


class PCTileEntityRef(object):
    def __init__(self, rootTag, chunk=None):
        self.rootTag = rootTag
        self.chunk = chunk

    def raw_tag(self):
        return self.rootTag

    id = NBTAttr("id", nbt.TAG_String)

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

        return PCTileEntityRef(tag)
