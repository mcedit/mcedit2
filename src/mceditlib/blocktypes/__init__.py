"""
    Block definitions for all known level formats
    Reader for block definitions stored in .yaml files (based on Minecraft X-Ray)
"""
from __future__ import absolute_import
from logging import getLogger
import os
import traceback
from os.path import join
from collections import defaultdict, namedtuple
import json

import numpy
import re

log = getLogger(__name__)
import logging
logging.basicConfig(level=logging.INFO)

MCYDecreasing = 0
MCYIncreasing = 1
MCZDecreasing = 2 #south
MCZIncreasing = 3 #north
MCXDecreasing = 4 #west
MCXIncreasing = 5 #east


class BlockType(namedtuple("_BlockType", "ID, meta, blocktypeSet")):
    """
    Value object representing an (id, data, blocktypeSet) tuple.
    Accessing its attributes will return the corresponding elements
    of its parent material's json arrays.

    """

    def __repr__(self):
        try:
            names = " (%s (%s%s)" % (self.displayName, self.internalName, self.blockState)
        except:
            names = ""
        return "<BlockType (%d:%d)%s>" % (self.ID, self.meta, names)

    def __str__(self):
        return "%s (%s%s)" % (self.displayName, self.internalName, self.blockState)

    def __cmp__(self, other):
        if not isinstance(other, BlockType):
            return -1
        if None in (self, other):
            return -1

        key = lambda a: (a.internalName, a.blockState)
        return cmp(key(self), key(other))

    def __getattr__(self, attr):
        return self.blocktypeSet.getBlockTypeAttr(self, attr)


id_limit = 4096


def openResource(filename):
    path = join(os.path.dirname(__file__), filename)
    if not os.path.exists(path):
        try:
            # py2exe, .egg
            import pkg_resources
            return pkg_resources.resource_stream(__name__, filename)
        except ImportError as e:
            log.exception("pkg_resources not available")
            raise

    return file(path)


class BlockTypeSet(object):
    defaultColor = (0xc9, 0x77, 0xf0, 0xff)

    def __init__(self, defaultName="Unused Block", idMapping=None):
        object.__init__(self)
        self.allBlocks = []
        self.blockJsons = {}
        self.IDsByState = {}  # internalName[blockstates] -> (id, meta)
        self.statesByID = {}  # (id, meta) -> internalName[blockstates]
        self.defaultBlockstates = {}  # internalName -> [blockstates]

        self.defaults = {
            'displayName': defaultName,
            'opacity': 15,
            'brightness': 0,
            'internalName': 'UNKNOWN_NAME',
            'blockState': '[UNKNOWN_STATE]',
            'unlocalizedName': 'name.unknown',
            'opaqueCube': True,
            'renderType': -1, #xxx unknowns
        }

        self.aka = defaultdict(lambda: "")

        self.brightness = numpy.zeros(id_limit, dtype='uint8')
        self.brightness[:] = self.defaults['brightness']
        self.opacity = numpy.zeros(id_limit, dtype='uint8')
        self.opacity[:] = self.defaults['opacity']
        self.mapColor = numpy.zeros((id_limit, 4), dtype='uint8')
        self.mapColor[:] = self.defaultColor
        self.renderColor = numpy.zeros((id_limit, 16, 3), dtype='uint8')
        self.renderColor[:] = 0xFF
        self.mapColor = numpy.zeros((id_limit, 16, 3), dtype='uint8')
        self.mapColor[:] = 0xFF

        self.opaqueCube = numpy.ones((id_limit, ), dtype='bool')
        self.opaqueCube[0] = 0

        self.name = "Unnamed Set"
        self.namePrefix = "minecraft:"

    def getBlockTypeAttr(self, block, attr):
        """
        Called when accessing an attribute of a BlockType.
        :param block:
        :type block:
        :param attr:
        :type attr:
        :return:
        :rtype:
        """

        nameAndState = self.statesByID.get((block.ID, block.meta))
        if nameAndState is None:
            return self.defaults[attr]

        if attr == "internalName":
            return self._splitInternalName(nameAndState)[0]

        if attr == "blockState":
            return self._splitInternalName(nameAndState)[1]

        blockJson = self.blockJsons[nameAndState]
        if attr == "json":
            return blockJson
        if attr == "resourcePath":
            resourcePath = blockJson.get(attr)
            if resourcePath is None:
                return block.internalName.replace(self.namePrefix, "")

        retval = blockJson.get(attr)
        if retval is None:
            retval = self.defaults[attr]

        return retval

    def __repr__(self):
        return "<BlockTypeSet ({0})>".format(self.name)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __len__(self):
        return len(self.allBlocks)

    def __iter__(self):
        return iter(self.allBlocks)

    def _splitInternalName(self, nameAndState):
        if '[' in nameAndState:
            idx = nameAndState.index('[')
            internalName, blockState = nameAndState[:idx], nameAndState[idx:]
        else:
            internalName = nameAndState
            blockState = ""
        return internalName, blockState

    def __getitem__(self, nameAndState):
        """

        Possible uses:
            # block ID
            level.blocktypes[120]

            # block ID, meta
            level.blocktypes[120, 0]

            # returns Air
            level.blocktypes["air"]

            # returns default state of Powered Rail
            level.blocktypes["golden_rail"]

            # returns Powered Rail with given state
            level.blocktypes["golden_rail[powered=false,shape=north_south]"]

        :type nameAndState: str
        """

        if isinstance(nameAndState, tuple):
            internalName, blockState = nameAndState
            if isinstance(internalName, basestring):
                ID, meta = self.IDsByState[nameAndState]
            else:  # (ID, meta)
                ID, meta = nameAndState

        elif isinstance(nameAndState, basestring):
            if not nameAndState.startswith(self.namePrefix):
                nameAndState = self.namePrefix + nameAndState
            if nameAndState not in self.IDsByState:
                if nameAndState in self.defaultBlockstates:
                    nameAndState += self.defaultBlockstates[nameAndState]
            ID, meta = self.IDsByState[nameAndState]
        else:  # block ID
            ID = nameAndState
            meta = 0

        return BlockType(ID, meta, self)


    def blocksMatching(self, name):
        name = name.lower()
        return [v for v in self.allBlocks if name in v.displayName.lower() or name in v.aka.lower()]

    def addIDMappingFromFile(self, filename):
        f = openResource(filename)
        try:
            s = f.read()
            log.info(u"Loading block ID mapping from (%s) %s", len(s), f)
            entries = json.loads(s)
            self.IDsByState.clear()
            for ID, meta, nameAndState in entries:
                #internalName, blockState = self._splitInternalName(nameAndState)

                self.IDsByState[nameAndState] = ID, meta
            self.statesByID = {v: k for (k, v) in self.IDsByState.iteritems()}
            assert "minecraft:air" in self.IDsByState
            assert (0,0) in self.statesByID
        except EnvironmentError as e:
            log.error(u"Exception while loading block ID mapping from %s: %s", f, e)
            traceback.print_exc()
            raise

    def addJsonBlocksFromFile(self, filename):
        f = openResource(filename)
        try:
            s = f.read()
            log.info(u"Loading block info from (%s) %s", len(s), f)
            self.addJsonBlocks(json.loads(s))

        except EnvironmentError as e:
            log.error(u"Exception while loading block info from %s: %s", f, e)
            traceback.print_exc()

    def addJsonBlocks(self, blockJson):
        for block in blockJson:
            try:
                self.addJsonBlock(block)
            except (KeyError, ValueError) as e:
                log.warn(u"Exception while parsing block: %r", e)
                traceback.print_exc()
                log.warn(u"Block dict: \n%s", block)
                raise

        for block in self.allBlocks:
            if block.internalName not in self.defaultBlockstates:
                self.defaultBlockstates[block.internalName] = block.blockState

    def addJsonBlock(self, blockJson):
        """
        Adds a block to this blockset using the keys and values in `block`.

        Required keys:
            internalName - String used by Minecraft to identify this block

        :type blockJson: dict
        :return:
        :rtype:
        """

        ID = blockJson.get("id")
        internalName = blockJson.get("internalName")
        if ID is None and internalName is None:
            raise ValueError("Block definition must have either `id` or `internalName` attribute.")


        #log.debug("Adding block: \n%s", json.dumps(blockJson, indent=2))
        nameAndState = blockJson.get("blockState", internalName)
        internalName, blockState = self._splitInternalName(nameAndState)

        IDmeta = self.IDsByState.get(nameAndState)
        if IDmeta is None:
            log.info("No ID mapping for %s, skipping...", internalName)
            return
        ID, meta = IDmeta
        self.allBlocks.append(BlockType(ID, meta, self))

        oldJson = self.blockJsons.get(internalName + blockState)
        if oldJson is None:
            oldJson = self.blockJsons[internalName + blockState] = blockJson
        else:
            oldJson.update(blockJson)

        blockJson = oldJson
        del oldJson

        if blockJson.get("defaultState"):
            self.defaultBlockstates[internalName] = blockState


        for key in [
            'opaqueCube',
            'brightness',
            'opacity',
        ]:  # does not have data axis
            if key in blockJson:
                array = getattr(self, key)
                array[ID] = blockJson[key]

        color = blockJson.get('renderColor')
        if color is not None:
            self.renderColor[ID, meta or slice(None)] = ((color >> 16) & 0xff,
                                                              (color >> 8) & 0xff,
                                                              color & 0xff)

        color = blockJson.get('materialMapColor')
        if color is not None:
            self.mapColor[ID, meta or slice(None)] = ((color >> 16) & 0xff,
                                                           (color >> 8) & 0xff,
                                                           color & 0xff)

class PCBlockTypeSet(BlockTypeSet):
    def __init__(self):
        super(PCBlockTypeSet, self).__init__()
        self.name = "Alpha"
        self.addIDMappingFromFile("idmapping.json")
        self.addJsonBlocksFromFile("minecraft_raw.json")
        self.addJsonBlocksFromFile("minecraft.json")

pc_blocktypes = PCBlockTypeSet()

# def printStaticDefs(blocktypes):
#     varNames = set()
#     for block in blocktypes.allBlocks:
#         blockJson = block.json
#         name = blockJson['displayName']
#         #internalName = blockJson['internalName']
#         nameAndState = blockJson['blockState']
#         internalName, blockState = blocktypes._splitInternalName(nameAndState)
#         variableName = re.sub(r"[^\w]", '', name)
#         varName = variableName
#         i=2
#         while varName in varNames:
#             varName = "%s%d" % (variableName, i)
#             i += 1
#         varNames.add(varName)
#         print("self.%s = self['%s', '%s']" % (varName, internalName, blockState))
#     raise SystemExit
# printStaticDefs(pc_blocktypes)

blocktypes_named = {"Alpha": pc_blocktypes}

def convertBlocks(destTypes, sourceTypes, ID, meta):
    return ID, meta  # xxx fixme
