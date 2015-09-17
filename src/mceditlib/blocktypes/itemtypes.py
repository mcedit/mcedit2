"""
    itemtypes
"""
from __future__ import absolute_import, division, print_function
import collections
import logging
import warnings

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
            names = " (%s (%s)" % (self.displayName, self.internalName)
        except:
            names = ""
        return "<ItemType (%d:%s)%s>" % (self.ID, self.meta, names)

    def __str__(self):
        return "%s (%s) [%s:%s]" % (self.displayName, self.internalName, self.ID, self.meta)

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
            "texture": None
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

        if attr in ("displayName", "texture"):
            if isinstance(retval, list):
                assert itemType.meta is not None, "ItemType %s: Got a list %s for attr %s but meta is None" % (
                    itemType.internalName, retval, attr
                )
                if itemType.meta >= len(retval):
                    warnings.warn(
                        "ItemType %s: Got meta %d but no item in list %s" % (
                            itemType.internalName, itemType.meta, retval
                        ))
                    return retval[0] + ("(Unknown meta)")

                return retval[itemType.meta]

        if retval is None:
            if attr == "displayName":
                try:
                    return itemType.internalName
                except AttributeError:
                    return "Unknown item %d" % itemType.ID

            if attr not in self.defaults:
                raise AttributeError(attr)
            retval = self.defaults[attr]

        return retval

    def loadItemsFromJson(self, json):
        # loading JSON taken from MCEdit-Unified
        # xxx make the ItemDumper already
        for jsonName, item in json.iteritems():
            internalName = "minecraft:" + jsonName
            try:
                ID = int(item["id"])
                displayName = item["displayName"]

                item["internalName"] = internalName

                self.IDsByInternalName[internalName] = ID
                self.itemJsons[ID] = item

                texture = item.get("texture")

                if isinstance(displayName, list):
                    # damage is meta value
                    for meta, _ in enumerate(displayName):
                        self.allItems.append(ItemType(ID, meta, self))

                elif isinstance(texture, list):
                    for meta, _ in enumerate(texture):
                        self.allItems.append(ItemType(ID, meta, self))
                else:
                    # damage is item damage
                    self.allItems.append(ItemType(ID, None, self))
            except Exception as e:
                log.exception("Error while parsing item %s: %r. \nItem JSON:\n%s", internalName, e, item)
                raise

    def __iter__(self):
        return iter(self.allItems)

    def __len__(self):
        return len(self.allItems)

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

        If the itemtype is not present in this set, raises KeyError.

        In contrast to BlockTypeSet, KeyError is always raised for unknown itemtypes.

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

    def addFMLIDMapping(self, internalName, ID):
        item = {"internalName": internalName,
                "name": internalName}
        self.IDsByInternalName[internalName] = ID
        self.itemJsons[ID] = item


class PCItemTypeSet(ItemTypeSet):
    def __init__(self):
        super(PCItemTypeSet, self).__init__()

        self.loadItemsFromJson(getJsonFile("tmp_itemblocks.json"))
        self.loadItemsFromJson(getJsonFile("tmp_items.json"))

