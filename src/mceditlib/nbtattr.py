"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from mceditlib import nbt
from mceditlib.geometry import Vector

log = logging.getLogger(__name__)


class NBTAttr(object):
    def __repr__(self):
        return "NBTAttr('%s', %s, %r)" % (self.name, self.tagType, self.default)

    def __init__(self, name, tagType, default=None):
        self.name = name
        self.tagType = tagType
        self.default = default

    def __get__(self, instance, owner):
        tag = instance.rootTag
        if self.name not in tag:
            tag[self.name] = self.tagType(value=self.default)
        return tag[self.name].value

    def __set__(self, instance, value):
        tag = instance.rootTag
        if self.name not in tag:
            tag[self.name] = self.tagType(value)
        else:
            tag[self.name].value = value
        instance.dirty = True


class NBTCompoundListAttr(object):
    def __repr__(self):
        return "NBTListAttr(%s, %s)" % (self.name, self.compoundAttrsClass)

    def __init__(self, name, compoundAttrsClass):
        self.name = name
        self.compoundAttrsClass = compoundAttrsClass

    def __get__(self, instance, owner):
        tag = instance.rootTag
        if self.name not in tag:
            tag[self.name] = nbt.TAG_List()
        return [self.compoundAttrsClass(subTag) for subTag in tag[self.name]]  # xxxxx insert/delete via list proxy


class NBTListAttr(object):
    def __repr__(self):
        return "NBTListAttr(%s, %s, %s)" % (self.name, self.listType, self.default)

    def __init__(self, name, listType, default=()):
        self.name = name
        self.listType = listType
        self.default = default

    def __get__(self, instance, owner):
        tag = instance.rootTag
        if self.name not in tag:
            tag[self.name] = nbt.TAG_List()
        return [i.value for i in tag[self.name]]  # xxxxx insert/delete via list proxy

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


class CompoundAttrs(object):
    def __init__(self, rootTag):
        super(CompoundAttrs, self).__init__()
        self.rootTag = rootTag
        # xxx parent instance.dirty


class NBTCompoundAttr(NBTAttr):
    def __repr__(self):
        return "NBTCompoundAttr(%s, %s)" % (self.name, self.attrsClass)

    def __init__(self, name, attrsClass):
        super(NBTCompoundAttr, self).__init__(name, nbt.TAG_Compound)
        self.attrsClass = attrsClass

    def __get__(self, instance, owner):
        tag = instance.rootTag
        if self.name not in tag:
            tag[self.name] = self.tagType(value=self.default)
        return self.attrsClass(tag[self.name])

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
        val = super(NBTVectorAttr, self).__get__(instance, owner)
        return Vector(*val)


def SetNBTDefaults(ref):
    """
    Given an object whose class has several members of type `NBT[*]Attr`,
    sets those attributes to their default values.
    """
    cls = ref.__class__
    for k, v in cls.__dict__.iteritems():
        if isinstance(v, (NBTAttr, NBTListAttr)):
            setattr(ref, k, v.default)
