"""
    nbtattr
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import collections
import logging
import uuid
from mceditlib import nbt
from mceditlib.geometry import Vector

log = logging.getLogger(__name__)


_tagTypes = {
    'b': nbt.TAG_Byte,
    's': nbt.TAG_Short,
    'i': nbt.TAG_Int,
    'l': nbt.TAG_Long,
    'f': nbt.TAG_Float,
    'd': nbt.TAG_Double,
    't': nbt.TAG_String,
}

class NBTAttr(object):
    """
    NBT Attributes can be added to any class whose instances have a 'rootTag' attribute, usually an EntityRef
    or TileEntityRef. Adding the attribute exposes one subtag of the rootTag as an attribute of the instance,
    allowing you to use shorter code for accessing the subtag's value. The attribute accepts a tag type
    and default value to use for creating the tag if it is not found.

    Changing the attribute's values sets the 'dirty' attribute of the instance to True. This is used by EntityRef
    and TileEntityRef to mark the containing chunk dirty.

    Specialized NBT Attributes are also provided for UUIDs (`NBTUUIDAttr`), Vectors such as an entity's Position
    (`NBTVectorAttr`), lists with a fixed type (`NBTListAttr`), and lists of compounds (`NBTCompoundListAttr`).

    The function SetNBTDefaults can be used to initialize all subtags of an instance's rootTag to their defaults,
    creating them if needed.

    Without NBTAttr::

        # getting
        if "Dimension" not in rootTag:
            return 0
        return rootTag["Dimension"].value

        # setting
        if "Dimension" not in rootTag:
            rootTag["Dimension"] = nbt.TAG_Int()
        rootTag["Dimension"].value = 1

    With NBTAttr::

        class PlayerRef(object):
            Dimension = NBTAttr("Dimension", nbt.TAG_Int, 0)

        ref = PlayerRef()
        ref.rootTag = rootTag

        # getting
        return ref.Dimension

        # setting
        ref.Dimension = 1


    """

    def __repr__(self):
        return "NBTAttr('%s', %s, %r)" % (self.name, self.tagType, self.default)

    def __init__(self, name, tagType, default=None, doc=""):
        self.name = name
        self.tagType = _tagTypes.get(tagType, tagType)
        self.default = default
        self.__doc__ = doc

    def __get__(self, instance, owner):
        if instance is None:
            return self  # attribute access on class returns the NBTAttr, like property()
        tag = instance.rootTag
        if self.name not in tag:
            if self.default is None:
                raise ValueError("No default value set for tag %r.", self.name)
            tag[self.name] = self.tagType(value=self.default)
        return tag[self.name].value

    def __set__(self, instance, value):
        tag = instance.rootTag
        if self.name not in tag:
            tag[self.name] = self.tagType(value)
        else:
            tag[self.name].value = value
        instance.dirty = True


class NBTUUIDAttr(object):
    """
    This attribute gets the entity's UUID from its `UUIDLeast` and `UUIDMost` tags and
    returns it as a `uuid.UUID`
    """
    def __repr__(self):
        return "NBTUUIDAttr()"

    def __get__(self, instance, owner):
        if instance is None:
            return self
        tag = instance.rootTag
        if 'UUIDLeast' not in tag or 'UUIDMost' not in tag:
            return None
        least = tag["UUIDLeast"].value & 0xffffffffffffffffL
        most = tag["UUIDMost"].value & 0xffffffffffffffffL
        uuidInt = (most << 64 | least) & 0xffffffffffffffffffffffffffffffffL
        UUID = uuid.UUID(int=uuidInt)
        return UUID

    def __set__(self, instance, value):
        uuidInt = value.int
        least = uuidInt & 0xffffffffffffffffL
        most = (uuidInt >> 64) & 0xffffffffffffffffL
        tag = instance.rootTag
        tag["UUIDLeast"] = nbt.TAG_Long(_signed(least))
        tag["UUIDMost"] = nbt.TAG_Long(_signed(most))
        instance.dirty = True


def _signed(bits):
    if bits >= (1 << 63):
        bits -= (1 << 64)
    return bits

class NBTCompoundRef(object):
    def __init__(self, rootTag, parent):
        """
        A reference object wrapping a TAG_Compound, with a pointer back to the parent reference object. Intended
        to be subclassed and used with NBTAttrs.

        The `dirty` and `blockTypes` attributes on an NBTCompoundRef are aliases for the parent object's attribute.

        :param rootTag:
        :type rootTag: nbt.TAG_Compound
        :param parent:
        :type parent: NBTCompoundRef | WorldEditorChunk
        :return:
        :rtype:
        """
        super(NBTCompoundRef, self).__init__()
        self.parent = parent
        self.rootTag = rootTag

    @property
    def dirty(self):
        if self.parent:
            return self.parent.dirty
        return True

    @dirty.setter
    def dirty(self, value):
        if self.parent:
            self.parent.dirty = value

    @property
    def blockTypes(self):
        return self.parent.blockTypes

    def copy(self):
        tag = self.rootTag.copy()
        return self.__class__(tag, None)


class NBTListProxy(collections.MutableSequence):
    """
    A proxy returned by NBTListAttr and NBTCompoundListAttr that allows the elements of a TAG_List to be accessed as
    instances of its refClass, or as plain values if refClass is not given (in the case of a list containing tags
    other than TAG_List or TAG_Compound).

    If refClass is given, objects inserted into a list are checked for a rootTag attribute, which is inserted into
    the list if present. Otherwise, the object itself is inserted, possibly raising a TypeError if it is not an NBT
    tag or not the proper tag type for the list.
    """

    def __init__(self, parent, tagName, refClass=None):
        self.tagName = tagName
        self.refClass = refClass
        self.parent = parent

    def __getitem__(self, key):
        if self.refClass:
            return self.refClass(self.parent.rootTag[self.tagName][key], self.parent)
        else:
            return self.parent.rootTag[self.tagName][key].value

    def __setitem__(self, key, value):
        if getattr(value, 'parent') is not None:
            raise ValueError("Adding a ref that has a parent (use ref.copy() to make a new ref)")
        if hasattr(value, 'rootTag'):
            tag = value.rootTag
        elif isinstance(value, nbt.TAG_Value):
            tag = value
        else:
            tag = self.parent
        self.parent.rootTag[self.tagName][key] = tag

    def __delitem__(self, key):
        del self.parent.rootTag[self.tagName][key]

    def __len__(self):
        return len(self.parent.rootTag[self.tagName])

    def insert(self, index, value):
        if hasattr(value, 'rootTag'):
            tag = value.rootTag
        else:
            tag = value
        self.parent.rootTag[self.tagName].insert(index, tag)

    @property
    def blockTypes(self):
        return self.parent.blockTypes

class NBTCompoundListAttr(object):
    """
    An attribute for accessing a list of compound tags, possibly wrapped by a subclass of NBTCompoundRef passed
    to the constructor.
    """

    def __init__(self, name, compoundRefClass, doc=""):
        self.name = name
        self.compoundRefClass = compoundRefClass
        self.listProxyClass = NBTListProxy
        self.__doc__ = doc

    def __repr__(self):
        return "NBTListAttr(%s, %s)" % (self.name, self.compoundRefClass)

    def __get__(self, instance, owner):
        if instance is None:
            return self
        tag = instance.rootTag
        if self.name not in tag:
            tag[self.name] = nbt.TAG_List()

        return self.listProxyClass(instance, self.name, self.compoundRefClass)


class NBTListAttr(object):
    def __repr__(self):
        return "NBTListAttr(%s, %s, %s)" % (self.name, self.listType, self.default)

    def __init__(self, name, listType, default=(), doc=""):
        self.name = name
        self.listType = _tagTypes.get(listType, listType)
        self.default = default
        self.__doc__ = doc

    def __get__(self, instance, owner):
        if instance is None:
            return self
        tag = instance.rootTag
        if self.name not in tag:
            tag[self.name] = nbt.TAG_List()
        return NBTListProxy(instance, self.name)

    def __set__(self, instance, value):
        rootTag = instance.rootTag
        if self.name not in rootTag:
            if self.listType is None:
                raise ValueError("Tried to initialize list with values without setting listType first!")
            rootTag[self.name] = nbt.TAG_List([self.listType(i) for i in value])
        else:
            tag = rootTag[self.name]
            for i, v in enumerate(tag):
                v.value = value[i]

        instance.dirty = True


class NBTCompoundAttr(NBTAttr):
    def __repr__(self):
        return "NBTCompoundAttr(%s, %s)" % (self.name, self.compoundRefClass)

    def __init__(self, name, compoundRefClass, doc=""):
        super(NBTCompoundAttr, self).__init__(name, nbt.TAG_Compound, doc=doc)
        self.compoundRefClass = compoundRefClass

    def __get__(self, instance, owner):
        if instance is None:
            return self
        tag = instance.rootTag
        if self.name not in tag:
            tag[self.name] = self.tagType(value=self.default)
        return self.compoundRefClass(tag[self.name], instance)

    def __set__(self, instance, value):
        """
        Should accept a dict of name:value pairs
        """
        raise NotImplementedError("Cannot replace entire compound through NBTCompoundAttr (yet)")
        # tag = instance.rootTag
        # if self.name not in tag:
        #     tag[self.name] = self.tagType(value)
        # else:
        #     tag[self.name].value = value


class NBTVectorAttr(NBTListAttr):
    def __get__(self, instance, owner):
        if instance is None:
            return self

        val = super(NBTVectorAttr, self).__get__(instance, owner)
        try:
            return Vector(*val)
        except TypeError:
            raise TypeError("NBT list too short for Vector: %s" % list(val))


class KeyedVectorAttr(object):
    """
    This attr is useful when a Vector is represented as a trio of named tags in a compound
    instead of as a list of tags. For example, the world spawn position (SpawnX, SpawnY,
    SpawnZ) and a TileEntity's position (x, y, z).
    """
    def __init__(self, xKey, yKey, zKey, tagType, default=None, doc=""):
        self.tagType = tagType
        self.default = default
        self.keys = xKey, yKey, zKey
        self.__doc__ = doc

    def __get__(self, instance, owner):
        if instance is None:
            return self
        tag = instance.rootTag
        for key in self.keys:
            if key not in tag:
                tag[key] = self.tagType(value=self.default)

        return Vector(*[tag[k].value for k in self.keys])

    def __set__(self, instance, value):
        tag = instance.rootTag
        for key, val in zip(self.keys, value):
            if key not in tag:
                tag[key] = self.tagType(val)
            else:
                tag[key].value = val

        instance.dirty = True



def SetNBTDefaults(ref):
    """
    Given an object whose class has several members of type `NBT[*]Attr`,
    sets those attributes to their default values.
    """
    cls = ref.__class__
    for k, v in cls.__dict__.iteritems():
        if isinstance(v, NBTCompoundAttr):
            ref.rootTag[k] = nbt.TAG_Compound()
            SetNBTDefaults(getattr(ref, k))
        elif isinstance(v, (NBTAttr, NBTListAttr)):
            if v.default is not None:
                setattr(ref, k, v.default)
