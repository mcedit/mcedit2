"""
    Block definitions for all known level formats
    Reader for block definitions stored in .yaml files (based on Minecraft X-Ray)
"""
from __future__ import absolute_import
from logging import getLogger
import traceback
from collections import defaultdict, namedtuple, MutableSet
import bisect

import numpy
from mceditlib.blocktypes import itemtypes

from mceditlib.blocktypes.json_resources import openResource, getJsonFile


log = getLogger(__name__)

MCYDecreasing = 0
MCYIncreasing = 1
MCZDecreasing = 2 #south
MCZIncreasing = 3 #north
MCXDecreasing = 4 #west
MCXIncreasing = 5 #east



def parseBlockstate(state):
    assert state[0] == '[' and state[-1] == ']'
    state = state[1:-1]
    return dict(pair.split('=') for pair in state.split(','))


def joinBlockstate(stateDict):
    return '[' + ','.join(k + '=' + v for k, v in stateDict.items()) + ']'


def splitInternalName(nameAndState):
    if '[' in nameAndState:
        idx = nameAndState.index('[')
        internalName, blockState = nameAndState[:idx], nameAndState[idx:]
    else:
        internalName = nameAndState
        blockState = ""
    return internalName, blockState


class BlockType(namedtuple("_BlockType", "ID meta blocktypeSet")):
    """
    Value object representing an (id, data, blocktypeSet) tuple.
    Accessing its attributes will return the corresponding elements
    of its parent set's json arrays.

    A blocktype set is initialized with one BlockType for each known
    ID/meta combination. BlockTypes are also created as needed when the
    set is asked for an unknown combination.

    """

    def __repr__(self):
        try:
            names = " (%s (%s%s)" % (self.displayName, self.internalName, self.blockState)
        except:
            names = ""
        return "<BlockType (%d:%d)%s>" % (self.ID, self.meta, names)

    def __str__(self):
        return "%s (%s%s) [%s:%s]" % (self.displayName, self.internalName, self.blockState, self.ID, self.meta)

    def __cmp__(self, other):
        if not isinstance(other, BlockType):
            return -1
        if None in (self, other):
            return -1

        key = lambda a: (a.internalName, a.blockState)
        return cmp(key(self), key(other))

    def __getattr__(self, attr):

        if attr == "stateDict":
            if attr in self.__dict__:
                return self.__dict__[attr]
            blockState = self.blockState
            if not len(blockState):
                self.__dict__[attr] = {}
            else:
                self.__dict__[attr] = parseBlockstate(blockState)

            return self.__dict__[attr]

        return self.blocktypeSet.getBlockTypeAttr(self, attr)
    
    def __nonzero__(self):
        return int(self.ID) != 0  # self.ID is a numpy.int

id_limit = 4096


class SortedSet(MutableSet):

    def __iter__(self):
        return iter(self._sorted)

    def discard(self, value):
        self._set.discard(value)
        self._sorted.remove(value)

    def add(self, value):
        if value in self._set:
            return
        self._set.add(value)
        bisect.insort(self._sorted, value)

    def __contains__(self, x):
        return x in self._set

    def __len__(self):
        return len(self._set)

    def __init__(self):
        self._sorted = []
        self._set = set()


class BlockTypeSet(object):
    defaultColor = (0xc9, 0x77, 0xf0, 0xff)

    def __init__(self, defaultName="Unused Block", idMapping=None):
        object.__init__(self)
        self.allBlocks = SortedSet()

        self.blockJsons = {}
        self.IDsByState = {}  # "internalName[blockstates]" -> (id, meta)
        self.statesByID = {}  # (id, meta) -> "internalName[blockstates]"

        self.IDsByName = {}  # internalName -> id
        self.namesByID = {}  # id -> internalName

        self.defaultBlockstates = {}  # internalName -> "[blockstates]"

        self.defaults = {
            'displayName': defaultName,
            'opacity': 15,
            'brightness': 0,
            'internalName': 'UNKNOWN_NAME',
            'blockState': '',
            'unlocalizedName': 'name.unknown',
            'opaqueCube': True,
            'resourcePath': None,  # Name of states file in assets/minecraft/blockstates/
            'resourceVariant': None,  # Name of variant from above file to use for this block type
            'forcedModel': None,  # Name of model file in assets/minecraft/models/block, forced by user configured blocks
            'forcedModelTextures': None,  # Mapping of texture variables to full texture paths, forced by user configured blocks
            'forcedModelRotation': None,  # Mapping of 'x', 'y', to 0, 90, 180 etc to rotate model. for non-forced blocks this is specified in the states file.
            'forcedRotationFlags': None,  # One or more of 'north', 'south' etc to use when rotating this block
            'renderType': 3,  # Model block - defaults to question mark box
            'unknown': False,  # False for blocks loaded from builtin .json, True for FML IDs, False for blocks configured in editor
            'color': 0xffffff,
            'biomeTintType': None,  # "grass", "leaves", or None
            'useNeighborBrightness': False,
            'normalCube': True,
            'materialLiquid': False,
        }

        self.aka = defaultdict(lambda: "")

        self.useNeighborBrightness = numpy.zeros(id_limit, dtype='uint8')
        self.useNeighborBrightness[:] = self.defaults['useNeighborBrightness']

        self.brightness = numpy.zeros(id_limit, dtype='uint8')
        self.brightness[:] = self.defaults['brightness']

        self.opacity = numpy.zeros(id_limit, dtype='uint8')
        self.opacity[:] = self.defaults['opacity']

        self.renderColor = numpy.zeros((id_limit, 16, 3), dtype='uint8')
        self.renderColor[:] = 0xFF

        self.mapColor = numpy.zeros((id_limit, 16, 3), dtype='uint8')
        self.mapColor[:] = 0xFF

        self.opaqueCube = numpy.ones((id_limit, ), dtype='uint8')
        self.opaqueCube[0] = 0

        self.normalCube = numpy.ones((id_limit, ), dtype='uint8')
        self.normalCube[0] = 0

        self.materialLiquid = numpy.zeros((id_limit, ), dtype='uint8')

        self.name = "Unnamed Set"
        self.namePrefix = "minecraft:"

    def getBlockTypeAttr(self, block, attr):
        """
        Return an attribute from the given block's json dict.

        :param block:
        :type block:
        :param attr:
        :type attr:
        :return:
        :rtype:
        """

        nameAndState = self.statesByID.get((block.ID, block.meta))
        if nameAndState is None:
            nameAndState = self.statesByID.get((block.ID, 0))
        if nameAndState is None:
            return self.defaults[attr]

        if attr == "nameAndState":
            return nameAndState

        try:
            blockJson = self.blockJsons[nameAndState]
        except KeyError:
            return self.defaults[attr]

        if attr == "json":
            return blockJson

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
                if ":" not in internalName:
                    internalName = self.namePrefix + internalName
                try:
                    ID, meta = self.IDsByState[internalName + blockState]
                except KeyError:
                    raise KeyError("No block found for name and state: %s%s" % (internalName, blockState))
            else:  # (ID, meta)
                ID, meta = nameAndState

        elif isinstance(nameAndState, basestring):
            if ":" not in nameAndState:
                nameAndState = self.namePrefix + nameAndState
            if nameAndState not in self.IDsByState:
                if nameAndState in self.defaultBlockstates:
                    nameAndState += self.defaultBlockstates[nameAndState]
            try:
                ID, meta = self.IDsByState[nameAndState]
            except KeyError:
                raise KeyError("No block found for name and state: %s" % (nameAndState,))
        else:  # block ID
            ID = nameAndState
            meta = 0

        return BlockType(ID, meta, self)

    def discardIDs(self, blockIDs):
        blockIDs = set(blockIDs)
        blocktypes = [b for b in self.allBlocks if b.ID in blockIDs]
        for b in blocktypes:
            self.allBlocks.discard(b)

    def discardInternalNameMetas(self, nameMetas):
        nameMetas = set(nameMetas)

        blocktypes = [bt for bt in self.allBlocks
                      if (bt.internalName, bt.meta) in nameMetas]

        for b in blocktypes:
            self.allBlocks.discard(b)

    def addBlocktypes(self, blocktypes):
        for b in blocktypes:
            self.allBlocks.add(b)

    def blocksMatching(self, name):
        name = name.lower()
        return [v for v in self.allBlocks if name in v.displayName.lower() or name in v.aka.lower()]

    def addIDMappingFromJSON(self, entries):
        for ID, meta, nameAndState in entries:
            internalName, blockState = splitInternalName(nameAndState)
            self.IDsByState[nameAndState] = ID, meta
            self.IDsByName[internalName] = ID
        self.statesByID = {v: k for (k, v) in self.IDsByState.iteritems()}
        self.namesByID = {v: k for (k, v) in self.IDsByName.iteritems()}

    def addBlockIDsFromSchematicTag(self, mapping):
        for ID, tag in mapping.iteritems():
            try:
                ID = int(ID)
            except ValueError:
                log.error("Can't parse %s as an integer.")
                continue

            name = tag.value
            if name not in self.IDsByName:
                self.IDsByName[name] = ID
                self.namesByID[ID] = name

    def addItemIDsFromSchematicTag(self, mapping):
        pass

    def addBlocksFromJSON(self, blockJson):
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
        blockState = blockJson.get("blockState", internalName)
        _, blockState = splitInternalName(blockState)

        # XXX raw jsons are created with 'blockState': <nameAndState>
        blockJson['blockState'] = blockState
        nameAndState = internalName + blockState

        IDmeta = self.IDsByState.get(nameAndState)
        if IDmeta is None:
            log.info("No ID mapping for %s, skipping...", internalName)
            return
        ID, meta = IDmeta
        self.allBlocks.add(BlockType(ID, meta, self))

        oldJson = self.blockJsons.get(nameAndState)
        if oldJson is None:
            oldJson = self.blockJsons[nameAndState] = blockJson
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
            'useNeighborBrightness',
            'normalCube',
            'materialLiquid',
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
    def __init__(self, itemStackVersion=None):
        super(PCBlockTypeSet, self).__init__()
        self.itemStackVersion = itemStackVersion or VERSION_1_7
        self.name = "Alpha"
        self.addIDMappingFromJSON(getJsonFile("idmapping_raw_1_11.json"))
        self.addIDMappingFromJSON(getJsonFile("idmapping.json"))
        self.addBlocksFromJSON(getJsonFile("minecraft_raw_1_11.json"))
        self.addBlocksFromJSON(getJsonFile("minecraft.json"))

        self.itemTypes = itemtypes.PCItemTypeSet()


VERSION_1_7 = 17
VERSION_1_8 = 18


def blocktypeConverter(destTypes, sourceTypes, replaceUnknownWith=None):
    """

    :param destTypes:
    :type destTypes: BlockTypeSet
    :param sourceTypes:
    :type sourceTypes: BlockTypeSet
    :return:
    :rtype:
    """
    idTable = numpy.arange(0, id_limit, dtype=numpy.uint16)
    for name, ID in sourceTypes.IDsByName.iteritems():
        if name in destTypes.IDsByName:
            try:
                idTable[ID] = destTypes.IDsByName[name]
            except IndexError:
                log.error("Can't insert %s->%s into %s (%s???) ??", ID, destTypes.IDsByName[name], idTable.shape, type(ID))
                raise
        elif replaceUnknownWith is not None:
            idTable[ID] = replaceUnknownWith

    def _convert(ID, meta):
        return idTable[ID], meta

    return _convert

