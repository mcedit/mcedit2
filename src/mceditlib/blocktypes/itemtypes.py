"""
    itemtypes
"""
from __future__ import absolute_import, division, print_function
import collections
import logging

from mceditlib.blocktypes.json_resources import getJsonFile

log = logging.getLogger(__name__)

_ItemType = collections.namedtuple("ItemType", "ID meta itemtypeSet")

class ItemType(_ItemType):
    """
    Value object representing an (id, meta, itemtypeSet) tuple.
    Accessing its attributes will return the corresponding elements
    of its parent set's json arrays.

    """

    def __repr__(self):
        try:
            names = " (%s (%s)" % (self.name, self.internalName)
        except:
            names = ""
        return "<ItemType (%d:%d)%s>" % (self.ID, self.meta, names)

    def __str__(self):
        return "%s (%s%s) [%s:%s]" % (self.displayName, self.internalName, self.blockState, self.ID, self.meta)

    def __cmp__(self, other):
        if not isinstance(other, ItemType):
            return -1
        if None in (self, other):
            return -1

        key = lambda a: (a.internalName, a.meta)
        return cmp(key(self), key(other))

    def __getattr__(self, attr):
        return self.itemtypeSet.getItemTypeAttr(self, attr)

class ItemTypeSet(object):
    def __init__(self):
        self.itemJsons = {}
        self.allItems = []

        self.IDsByInternalName = {}

        self.defaults = {

        }

    def getItemTypeAttr(self, itemType, attr):
        """
        Return an attribute from the given itemType's json dict.

        :param itemType:
        :type itemType:
        :param attr:
        :type attr:
        :return:
        :rtype:
        """

        if attr == "damage":
            return itemType.meta

        itemJson = self.itemJsons[itemType.ID]
        if attr == "json":
            return itemJson

        retval = itemJson.get(attr)
        if retval is None:
            if attr not in self.defaults:
                raise AttributeError
            retval = self.defaults[attr]

        return retval

    def loadItemsFromJson(self, json):
        for jsonName, item in json.iteritems():
            try:
                internalName = "minecraft:" + jsonName
                ID = int(item["id"])
                name = item["name"]
                item["internalName"] = internalName

                self.IDsByInternalName[internalName] = ID
                self.itemJsons[ID] = item

                if isinstance(name, list):
                    # damage is meta value
                    for meta, metaName in enumerate(name):
                        self.allItems.append(ItemType(ID, meta, self))
                else:
                    # damage is item damage
                    self.allItems.append(ItemType(ID, None, self))
            except Exception as e:
                log.exception("Error while parsing item %s: %r. \nItem JSON:\n%s", internalName, e, item)
                raise

    def __iter__(self):
        return iter(self.allItems)

    def __getitem__(self, key):
        """
        Return an ItemType for the given ID, internalName, (ID, meta), or (internalName, meta) key. If internalName
        is not prefixed, i.e. does not contain a colon, "minecraft:" is prepended automatically.

        Examples:

        >>> dirt = itemtypeSet["minecraft:dirt"]
        >>> grass = itemtypeSet[2]
        >>> podzol = itemtypeSet["dirt", 2]
        >>> junglePlanks = itemtypeSet[5, 3]

        Writing numeric IDs is discouraged. For clarity, use textual IDs and only pass numeric IDs when they are
        obtained from another source such as NBT structures.

        If the item is not present in this set, raises KeyError.

        :param key:
        :type key:
        :return:
        :rtype:
        """

        if not isinstance(key, (list, tuple)):
            ID = key
            meta = None
        else:
            ID, meta = key

        if isinstance(ID, basestring):
            ID = self.IDsByInternalName[ID]

        if ID not in self.itemJsons:
            raise KeyError

        return ItemType(ID, meta, self)

class PCItemTypeSet(ItemTypeSet):
    def __init__(self):
        super(PCItemTypeSet, self).__init__()

        self.loadItemsFromJson(getJsonFile("tmp_itemblocks.json"))
        self.loadItemsFromJson(getJsonFile("tmp_items.json"))

