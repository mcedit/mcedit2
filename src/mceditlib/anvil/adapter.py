"""
    adapter
"""
from __future__ import absolute_import, division, print_function
import logging
import sys
import os
import random
import re
import struct
import traceback
import collections
import weakref

import numpy
import zlib
import time

from mceditlib import nbt
from mceditlib.anvil import entities
from mceditlib.anvil.entities import PCEntityRef, PCTileEntityRef, ItemStackRef
from mceditlib.anvil.worldfolder import AnvilWorldFolder
from mceditlib.blocktypes import PCBlockTypeSet, BlockType, VERSION_1_8, VERSION_1_7
from mceditlib.geometry import Vector
from mceditlib.nbt import NBTFormatError
from mceditlib.nbtattr import NBTCompoundRef
from mceditlib.selection import BoundingBox
from mceditlib import nbtattr
from mceditlib.exceptions import PlayerNotFound, ChunkNotPresent, LevelFormatError
from mceditlib.revisionhistory import RevisionHistory
from mceditlib.util import exhaust, displayName, WorldInfo

log = logging.getLogger(__name__)

# --- Constants ---

GAMETYPE_SURVIVAL = 0
GAMETYPE_CREATIVE = 1

VERSION_MCR = 19132
VERSION_ANVIL = 19133

# --- Exceptions ---


class AnvilChunkFormatError(IOError):
    """
    Raised when an Anvil chunk's data is not as expected
    """


class SessionLockLost(IOError):
    """
    Raised when the session lock is lost because another program (Minecraft) opened the level
    while we were editing it.
    """

# --- Helper functions ---


def unpackNibbleArray(dataArray):
    s = dataArray.shape
    unpackedData = numpy.empty((s[0], s[1], s[2] * 2), dtype='uint8')

    unpackedData[:, :, ::2] = dataArray
    unpackedData[:, :, ::2] &= 0xf
    unpackedData[:, :, 1::2] = dataArray
    unpackedData[:, :, 1::2] >>= 4
    return unpackedData


def packNibbleArray(unpackedData):
    packedData = numpy.array(unpackedData.reshape(16, 16, unpackedData.shape[2] // 2, 2))
    packedData[..., 1] <<= 4
    packedData[..., 1] |= packedData[..., 0]
    return numpy.array(packedData[:, :, :, 1])


def deflate(data):
    # zobj = zlib.compressobj(6,zlib.DEFLATED,-zlib.MAX_WBITS,zlib.DEF_MEM_LEVEL,0)
    # zdata = zobj.compress(data)
    # zdata += zobj.flush()
    # return zdata
    return zlib.compress(data)


def inflate(data):
    return zlib.decompress(data)


def sanitizeBlocks(section, blocktypes):
    return
    # # change grass to dirt where needed so Minecraft doesn't flip out and die
    # grass = section.Blocks == blocktypes.Grass.ID
    # grass |= section.Blocks == blocktypes.Dirt.ID
    # badgrass = grass[1:, :, :] & grass[:-1, :, :]
    #
    # section.Blocks[:-1, :, :][badgrass] = blocktypes.Dirt.ID
    #
    # # remove any thin snow layers immediately above other thin snow layers.
    # # minecraft doesn't flip out, but it's almost never intended
    # if hasattr(blocktypes, "SnowLayer"):
    #     snowlayer = section.Blocks == blocktypes.SnowLayer.ID
    #     badsnow = snowlayer[:, :, 1:] & snowlayer[:, :, :-1]
    #
    #     section.Blocks[:, :, 1:][badsnow] = 0

# --- Sections and chunks ---


class AnvilSection(object):
    """
    Internal representation of a 16x16x16 chunk section. Arrays are indexed YZX.

    4-bit arrays are unpacked to byte arrays to make them work with numpy's array routines.

    To create the full 12-bit block ID, the Blocks array is extended to 16 bits and the Add array is merged into
    the high bits of the Blocks array.

    :ivar Y: section's Y value [0..(world.Height+15) >> 4]
    :ivar Blocks: Block IDs [0..4095]
    :ivar Data: Block sub-data [0..15]
    :ivar BlockLight: Light emitted by blocks [0..15]
    :ivar SkyLight: Light emitted by the sun/moon [0..15]
    """

    def __init__(self, section_tag=None):
        if section_tag:
            self._load(section_tag)
        else:
            self._create()

    def _load(self, section_tag):
        self.Y = section_tag.pop("Y").value
        self.Blocks = section_tag.pop("Blocks").value.astype("uint16")
        self.Blocks.shape = 16, 16, 16

        for name in "Data", "SkyLight", "BlockLight":
            section_array = section_tag.pop(name).value
            section_array.shape = 16, 16, 8
            setattr(self, name, unpackNibbleArray(section_array))

        tag = section_tag.pop("Add", None)
        if tag is not None:
            tag.value.shape = 16, 16, 8
            add = unpackNibbleArray(tag.value)
            self.Blocks |= numpy.array(add, 'uint16') << 8

        self.old_section_tag = section_tag

    def _create(self):
        shape = 16, 16, 16
        self.Y = 0

        self.Blocks = numpy.zeros(shape, 'uint16')
        self.Data = numpy.zeros(shape, 'uint8')
        self.SkyLight = numpy.zeros(shape, 'uint8')
        self.SkyLight[:] = 15
        self.BlockLight = numpy.zeros(shape, 'uint8')
        self.old_section_tag = nbt.TAG_Compound()

    def buildNBTTag(self):
        """
        Return a TAG_Compound for saving this section to a chunk.
        """
        section_tag = self.old_section_tag

        Blocks = self.Blocks
        Data = packNibbleArray(self.Data)
        BlockLight = packNibbleArray(self.BlockLight)
        SkyLight = packNibbleArray(self.SkyLight)

        add = Blocks >> 8
        if add.any():
            section_tag["Add"] = nbt.TAG_Byte_Array(packNibbleArray(add).astype('uint8'))

        section_tag['Blocks'] = nbt.TAG_Byte_Array(numpy.array(Blocks, 'uint8'))
        section_tag['Data'] = nbt.TAG_Byte_Array(Data)
        section_tag['BlockLight'] = nbt.TAG_Byte_Array(BlockLight)
        section_tag['SkyLight'] = nbt.TAG_Byte_Array(SkyLight)

        section_tag["Y"] = nbt.TAG_Byte(self.Y)
        return section_tag


class AnvilChunkData(object):
    """ This is the chunk data backing a WorldEditorChunk. Chunk data is retained by the WorldEditor until its
    WorldEditorChunk is no longer used, then it is either cached in memory, discarded, or written to disk according to
    resource limits.
    """

    def __init__(self, adapter, cx, cz, dimName, rootTag=None, create=False):
        """

        :type adapter: mceditlib.anvil.adapter.AnvilWorldAdapter
        :type cx: int
        :type cz: int
        :type dimName: str
        :type rootTag: mceditlib.nbt.TAG_Compound
        :type create: bool
        :return:
        :rtype: AnvilChunkData
        """
        self.cx = cx
        self.cz = cz
        self.dimName = dimName
        self.adapter = adapter
        self.rootTag = rootTag
        self.dirty = False
        self._sections = {}

        if create:
            self._create()
        else:
            self._load(rootTag)

        levelTag = self.rootTag["Level"]
        if "Biomes" not in levelTag:
            levelTag["Biomes"] = nbt.TAG_Byte_Array(numpy.empty((16, 16), 'uint8'))
            levelTag["Biomes"].value[:] = -1

        if "TileTicks" not in levelTag:
            levelTag["TileTicks"] = nbt.TAG_List()

    def _create(self):
        chunkTag = nbt.TAG_Compound()
        chunkTag.name = ""

        levelTag = nbt.TAG_Compound()
        chunkTag["Level"] = levelTag

        levelTag["HeightMap"] = nbt.TAG_Int_Array(numpy.zeros((16, 16), 'uint32').newbyteorder())
        levelTag["TerrainPopulated"] = nbt.TAG_Byte(1)
        levelTag["xPos"] = nbt.TAG_Int(self.cx)
        levelTag["zPos"] = nbt.TAG_Int(self.cz)

        levelTag["LastUpdate"] = nbt.TAG_Long(0)

        levelTag["Entities"] = nbt.TAG_List()
        levelTag["TileEntities"] = nbt.TAG_List()
        levelTag["TileTicks"] = nbt.TAG_List()

        self.rootTag = chunkTag
        self.dirty = True

    def _load(self, rootTag):
        self.rootTag = rootTag

        for sec in self.rootTag["Level"].pop("Sections", []):
            y = sec["Y"].value
            self._sections[y] = AnvilSection(sec)


    def buildNBTTag(self):
        """ does not recalculate any data or light """

        log.debug(u"Saving chunk: {0}".format(self))

        chunkTag = self.rootTag.copy()

        sections = nbt.TAG_List()
        for _, section in self._sections.iteritems():

            if (not section.Blocks.any() and
                    not section.BlockLight.any() and
                    (section.SkyLight == 15).all()):
                continue

            sanitizeBlocks(section, self.adapter.blocktypes)
            sections.append(section.buildNBTTag())

        chunkTag["Level"]["Sections"] = sections

        if len(self.TileTicks) == 0:
            del chunkTag["Level"]["TileTicks"]

        log.debug(u"Saved chunk {0}".format(self))
        return chunkTag

    def sectionPositions(self):
        return self._sections.keys()

    def getSection(self, cy, create=False):
        """

        :param cy: Section number (y coordinate >> 4)
        :param create: If False, returns None if the section is not present or could not
            be created, otherwise creates the section.
        :returns: The requested section, or None if it wasn't created.
        :rtype: AnvilSection
        """
        if (cy << 4) >= self.adapter.maxHeight or cy < 0:
            return None

        section = self._sections.get(cy)
        if not section:
            if not create:
                return None
            else:
                section = AnvilSection()
                section.Y = cy
                self._sections[cy] = section

        return section

    @property
    def bounds(self):
        return BoundingBox((self.cx << 4, self.adapter.minHeight, self.cz << 4),
                           (16, self.adapter.maxHeight - self.adapter.minHeight, 16))

    @property
    def blocktypes(self):
        return self.adapter.blocktypes

    @property
    def Entities(self):
        return self.rootTag["Level"]["Entities"]

    @property
    def TileEntities(self):
        return self.rootTag["Level"]["TileEntities"]

    @property
    def TileTicks(self):
        return self.rootTag["Level"]["TileTicks"]

    @property
    def Biomes(self):
        return self.rootTag["Level"]["Biomes"].value.reshape((16, 16))

    @property
    def HeightMap(self):
        # z, x order in save file
        return self.rootTag["Level"]["HeightMap"].value.reshape((16, 16))

    @property
    def TerrainPopulated(self):
        return self.rootTag["Level"]["TerrainPopulated"].value

    @TerrainPopulated.setter
    def TerrainPopulated(self, val):
        """True or False. If False, the game will populate the chunk with
        ores and vegetation on next load"""
        self.rootTag["Level"]["TerrainPopulated"].value = val
        self.dirty = True

# --- World info ---

class WorldVersionRef(nbtattr.NBTCompoundRef):
    Id = nbtattr.NBTAttr('Id', 'i')
    Name = nbtattr.NBTAttr('Name', 's')
    Snapshot = nbtattr.NBTAttr('Snapshot', 'b')


class AnvilWorldMetadata(object):

    def __init__(self, metadataTag):
        self.metadataTag = metadataTag
        self.rootTag = metadataTag["Data"]
        self.dirty = False

    # --- NBT Tag variables ---

    SizeOnDisk = nbtattr.NBTAttr('SizeOnDisk', nbt.TAG_Long, 0)
    RandomSeed = nbtattr.NBTAttr('RandomSeed', nbt.TAG_Long, 0)
    Time = nbtattr.NBTAttr('Time', nbt.TAG_Long, 0)  # Age of the world in ticks. 20 ticks per second; 24000 ticks per day.
    DayTime = nbtattr.NBTAttr('DayTime', nbt.TAG_Long, 0)  # Amount of ticks since Day 1, 6:00
    LastPlayed = nbtattr.NBTAttr('LastPlayed', nbt.TAG_Long, time.time() * 1000)
    Difficulty = nbtattr.NBTAttr('Difficulty', nbt.TAG_Byte, 0)
    LevelName = nbtattr.NBTAttr('LevelName', nbt.TAG_String, "Untitled World")
    hardcore = nbtattr.NBTAttr('hardcore', nbt.TAG_Byte, False)
    allowCommands = nbtattr.NBTAttr('allowCommands', nbt.TAG_Byte, False)
    DifficultyLocked = nbtattr.NBTAttr('DifficultyLocked', nbt.TAG_Byte, False)

    generatorName = nbtattr.NBTAttr('generatorName', nbt.TAG_String, "default")
    generatorOptions = nbtattr.NBTAttr('generatorOptions', nbt.TAG_String, "") #Default is different for every generatorType

    MapFeatures = nbtattr.NBTAttr('MapFeatures', nbt.TAG_Byte, 1)

    GameType = nbtattr.NBTAttr('GameType', nbt.TAG_Int, 0)  # 0 for survival, 1 for creative

    version = nbtattr.NBTAttr('version', nbt.TAG_Int, VERSION_ANVIL)

    Spawn = nbtattr.KeyedVectorAttr('SpawnX', 'SpawnY', 'SpawnZ', nbt.TAG_Int)

    Version = nbtattr.NBTCompoundAttr('Version', WorldVersionRef)

    def is1_8World(self):
        # Minecraft 1.8 adds a dozen tags to level.dat/Data. These tags are removed if
        # the world is played in 1.7 (and all of the items are removed too!)
        # Use some of these tags to decide whether to use 1.7 format ItemStacks or 1.8 format ones.
        # In 1.8, the stack's "id" is a TAG_String, but in 1.7 it is a TAG_Short.
        tags = (
            'BorderCenterX', 'BorderCenterZ',
            'BorderDamagePerBlock',
            'BorderSafeZone',
            'BorderSize'
        )
        return any(tag in self.rootTag for tag in tags)

class AnvilWorldAdapter(object):
    """
    Provides an interface to AnvilWorldFolder/RevisionHistory that is usable by WorldEditor

    This interface is the base used for all adapter classes. When writing a new adapter, make sure to
    implement all required methods and attributes. Required methods and attrs are the ones with docstrings.
    """

    minHeight = 0
    maxHeight = 256
    hasLights = True

    def __init__(self, filename=None, create=False, readonly=False, resume=None):
        """
        Load a Minecraft for PC level (Anvil format) from the given filename. It can point to either
        a level.dat or a folder containing one. If create is True, it will
        also create the world using a randomly selected seed.

        If you try to create an existing world, IOError will be raised.

        Uses a RevisionHistory to manage undo history. Upon creation, the world is read-only until createRevision() is
        called. Call createRevision() to create a new revision, or selectRevision() to revert to an earlier
        revision. Older revisions are read-only, so createRevision() must be called again to make further changes.

        Call writeAllChanges() to write all changes into the original world.

        :type filename: str or unicode
        :type create: bool
        :type readonly: bool
        :rtype: AnvilWorldAdapter
        """
        self.lockTime = 0

        self.EntityRef = PCEntityRef
        self.TileEntityRef = PCTileEntityRef

        assert not (create and readonly)

        if os.path.basename(filename) in ("level.dat", "level.dat_old"):
            filename = os.path.dirname(filename)

        if not os.path.exists(filename):
            if not create:
                raise IOError('File not found')

            os.mkdir(filename)
        else:
            if create:
                if not os.path.isdir(filename) or os.path.exists(os.path.join(filename, "level.dat")):
                    raise IOError('File exists!')

        if not os.path.isdir(filename):
            raise IOError('File is not a Minecraft Anvil world')

        if readonly:
            self.revisionHistory = AnvilWorldFolder(filename, readonly=True)
            self.selectedRevision = self.revisionHistory
        else:
            self.revisionHistory = RevisionHistory(filename, resume)
            self.selectedRevision = self.revisionHistory.getHead()

        self.filename = filename
        self.readonly = readonly
        if not readonly:
            self.acquireSessionLock()

        if create:
            self._createMetadataTag()
            self.selectedRevision.writeFile("level.dat", self.metadata.metadataTag.save())

        else:
            self.loadMetadata()

        self.loadBlockMapping()

    def __repr__(self):
        return "AnvilWorldAdapter(%r)" % self.filename

    # --- Summary info ---

    @classmethod
    def getWorldInfo(cls, filename, displayNameLimit=40):
        try:
            if os.path.isdir(filename):
                folderName = os.path.basename(filename)
                levelDat = os.path.join(filename, "level.dat")
            else:
                folderName = os.path.basename(os.path.dirname(filename))
                levelDat = filename

            levelTag = nbt.load(levelDat)
            try:
                displayName = levelTag['Data']['LevelName'].value

                if len(displayName) > displayNameLimit:
                    displayName = displayName[:displayNameLimit] + "..."
                if len(folderName) > displayNameLimit:
                    folderName = folderName[:displayNameLimit] + "..."

                if folderName != displayName:
                    displayName = "%s (%s)" % (displayName, folderName)
            except Exception as e:
                log.warn("Failed to get display name for level.", exc_info=1)
                displayName = folderName

            try:
                lastPlayedTime = levelTag['Data']['LastPlayed'].value
            except Exception as e:
                log.warn("Failed to get last-played time for level.", exc_info=1)
                lastPlayedTime = 0

            version = "Unknown Version"
            try:
                try:
                    metadata = AnvilWorldMetadata(levelTag)
                    versionTag = metadata.Version
                    if versionTag.Snapshot:
                        version = "Minecraft Snapshot " + versionTag.Name
                    else:
                        version = "Minecraft " + versionTag.Name

                except Exception as e:

                    stackVersion = VERSION_1_8 if metadata.is1_8World() else VERSION_1_7

                    if stackVersion == VERSION_1_7:
                        version = "Minecraft 1.7"
                        if "FML" in metadata.metadataTag:
                            version = "MinecraftForge 1.7"

                    if stackVersion == VERSION_1_8:
                        version = "Minecraft 1.8+"

            except Exception as e:
                log.warn("Failed to get version info for %s: %r", filename, e, exc_info=1)

            return WorldInfo(displayName, lastPlayedTime, version)

        except Exception as e:
            log.error("Failed getting world info for %s: %r", filename, e)
            return WorldInfo(str(e), 0, "")


    # --- Create, save, close ---

    def loadMetadata(self):
        try:
            metadataTag = nbt.load(buf=self.selectedRevision.readFile("level.dat"))
            self.metadata = AnvilWorldMetadata(metadataTag)
        except (EnvironmentError, zlib.error, NBTFormatError) as e:
            log.info("Error loading level.dat, trying level.dat_old ({0})".format(e))
            try:
                metadataTag = nbt.load(buf=self.selectedRevision.readFile("level.dat_old"))
                self.metadata = AnvilWorldMetadata(metadataTag)
                self.metadata.dirty = True
                log.info("level.dat restored from backup.")
            except Exception as e:
                traceback.print_exc()
                log.info("%r while loading level.dat_old. Initializing with defaults.", e)
                self._createMetadataTag()

        if self.metadata.version != VERSION_ANVIL:
            raise LevelFormatError("Pre-Anvil world formats are not supported (for now)")

    def loadBlockMapping(self):
        if self.metadata.is1_8World():
            itemStackVersion = VERSION_1_8
        else:
            itemStackVersion = VERSION_1_7

        blocktypes = PCBlockTypeSet(itemStackVersion)
        self.blocktypes = blocktypes

        metadataTag = self.metadata.metadataTag
        fml = metadataTag.get('FML')
        if fml is None:
            return

        itemTypes = blocktypes.itemTypes

        itemdata = fml.get('ItemData')  # MC 1.7
        if itemdata is not None:
            count = 0
            log.info("Adding block IDs from FML for MC 1.7")
            replacedIDs = []
            for entry in itemdata:
                ID = entry['V'].value
                name = entry['K'].value
                magic, name = name[0], name[1:]
                if magic == u'\x01':  # 0x01 = blocks

                    if not name.startswith("minecraft:"):
                        # we load 1.9 block IDs and mappings by default
                        # FML IDs should be allowed to override some of them for 1.8 blocks not in 1.7.
                        count += 1
                        replacedIDs.append(ID)
                        fakeState = '[meta=0]'
                        nameAndState = name + fakeState
                        log.debug("FML1.7: Adding %s = %d", name, ID)


                        for vanillaMeta in range(15):
                            # Remove existing Vanilla defs
                            vanillaNameAndState = blocktypes.statesByID.get((ID, vanillaMeta))
                            blocktypes.blockJsons.pop(vanillaNameAndState, None)

                            # Also remove Vanilla name<->state mapping
                            blocktypes.IDsByState.pop(vanillaNameAndState, None)
                            vanillaName = blocktypes.namesByID.get(ID)
                            blocktypes.IDsByName.pop(vanillaName, None)
                            blocktypes.defaultBlockstates.pop(vanillaName, None)

                        blocktypes.IDsByState[nameAndState] = ID, 0
                        blocktypes.statesByID[ID, 0] = nameAndState
                        blocktypes.IDsByName[name] = ID
                        blocktypes.namesByID[ID] = name
                        blocktypes.defaultBlockstates[name] = fakeState

                        blocktypes.blockJsons[nameAndState] = {
                            'displayName': name,
                            'internalName': name,
                            'blockState': '[meta=0]',
                            'unknown': True,
                        }

                if magic == u'\x02':  # 0x02 = items
                    if not name.startswith("minecraft:"):
                        itemTypes.addFMLIDMapping(name, ID)

            replacedIDsSet = set(replacedIDs)
            blocktypes.discardIDs(replacedIDsSet)
            blocktypes.addBlocktypes(BlockType(newID, 0, blocktypes) for newID in replacedIDs)

            log.info("Added %d blocks.", count)



    def _createMetadataTag(self, random_seed=None):
        """
        Create a level.dat for a newly created world or a world found with damaged level.dat/.dat_old (xxx repair in
        WorldEditor?)
        :param random_seed:
        :type random_seed:
        :return:
        :rtype:
        """
        metadataTag = nbt.TAG_Compound()
        metadataTag["Data"] = nbt.TAG_Compound()
        metadataTag["Data"]["SpawnX"] = nbt.TAG_Int(0)
        metadataTag["Data"]["SpawnY"] = nbt.TAG_Int(2)
        metadataTag["Data"]["SpawnZ"] = nbt.TAG_Int(0)

        last_played = long(time.time() * 1000)
        if random_seed is None:
            random_seed = long(random.random() * 0xffffffffffffffffL) - 0x8000000000000000L

        metadataTag["Data"]['version'] = nbt.TAG_Int(VERSION_ANVIL)

        self.metadata = AnvilWorldMetadata(metadataTag)

        self.metadata.LastPlayed = long(last_played)
        self.metadata.RandomSeed = long(random_seed)
        self.metadata.SizeOnDisk = 0
        self.metadata.Time = 1
        self.metadata.LevelName = os.path.basename(self.filename)

    def syncToDisk(self):
        """
        Write cached items (metadata from level.dat and players in players/ folder) to the current revision.
        :return:
        :rtype:
        """
        if self.metadata.dirty:
            self.selectedRevision.writeFile("level.dat", self.metadata.metadataTag.save())
            self.metadata.dirty = False

    def saveChanges(self):
        exhaust(self.saveChangesIter())

    def saveChangesIter(self):
        """
        Write all changes from all revisions into the world folder.

        :return:
        :rtype: None
        """
        if self.readonly:
            raise IOError("World is opened read only.")

        self.checkSessionLock()
        index = self.revisionHistory.nodes.index(self.selectedRevision)
        for status in self.revisionHistory.writeAllChangesIter(self.selectedRevision):
            yield status

        self.selectedRevision = self.revisionHistory.nodes[index]
        yield

    def close(self):
        """
        Close the world, deleting temporary files and freeing resources. Operations on a closed world are undefined.

        :return:
        :rtype: None
        """
        self.revisionHistory.close()
        pass  # do what here???

    # --- Undo revisions ---

    def requireRevisions(self):
        """
        Enforce the creation of new revisions by making the world folder's revision read-only.
        :return:
        :rtype:
        """
        self.revisionHistory.rootNode.readOnly = True

    def createRevision(self):
        """
        Create a new undo revision. Subsequent changes should be stored in the new revision.

        :return:
        :rtype:
        """
        self.selectedRevision = self.revisionHistory.createRevision(self.selectedRevision)

    def closeRevision(self):
        """
        Close the current revision and mark it read-only. Subsequent edits will not be possible until createRevision
        is called.

        :return:
        :rtype:
        """
        self.revisionHistory.closeRevision()

    def setRevisionInfo(self, info):
        """
        Attach some arbitrary JSON-serializable data to the current revision

        :param info: JSON-serializable data
        :type info: list | dict | str | unicode | int
        """
        self.selectedRevision.setRevisionInfo(info)

    def getRevisionInfo(self):
        """
        Return JSON-serializable data attached previously to the current revision via setRevisionInfo, or None if
        no data is attached.

        :return:
        :rtype: list | dict | str | unicode | int | None
        """
        return self.selectedRevision.getRevisionInfo()

    def selectRevision(self, index):
        """
        Select the current revision by index. Return changes between the previous revision and this one. If
         the index is invalid, returns None and does nothing.

         (XXX use an ID instead of index?)

        :param index:
        :type index:
        :return:
        :rtype: RevisionChanges
        """
        if index < 0 or index >= len(self.revisionHistory.nodes):
            return None
        newRevision = self.revisionHistory.getRevision(index)
        changes = self.revisionHistory.getRevisionChanges(self.selectedRevision, newRevision)
        self.selectedRevision = newRevision
        self.loadMetadata()
        return changes

    def listRevisions(self):
        """
        List the revision indexes and infos as (index, info) tuples. Info is JSON-serializable data previously attached
        with setRevisionInfo, or None.

        :return:
        :rtype: iterator[(int, list | dict | str | unicode | int)]
        """
        for ID, node in enumerate(self.revisionHistory.nodes):
            yield ID, node.getRevisionInfo()

    def getRevisionChanges(self, oldRevision, newRevision):
        return self.revisionHistory.getRevisionChanges(oldRevision, newRevision)

    # --- Session lock ---

    def acquireSessionLock(self):
        """
        Acquire the world's session.lock. Formats without this file may do nothing.

        :return:
        :rtype:
        """

        lockfile = self.revisionHistory.rootFolder.getFilePath("session.lock")
        self.lockTime = int(time.time() * 1000)
        with open(lockfile, "wb") as f:
            f.write(struct.pack(">q", self.lockTime))
            f.flush()
            os.fsync(f.fileno())

    def checkSessionLock(self):
        """
        Make sure the lock previously acquired by acquireSessionLock is still valid. Raise SessionLockLost if it is
        not. Raising the exception will abort any writes done to the main world folder.

        :return:
        :rtype:
        """
        if self.readonly:
            raise SessionLockLost("World is opened read only.")

        lockfile = self.revisionHistory.rootFolder.getFilePath("session.lock")
        try:
            (lock, ) = struct.unpack(">q", open(lockfile, "rb").read())
        except struct.error:
            lock = -1
        if lock != self.lockTime:
            raise SessionLockLost("Session lock lost. This world is being accessed from another location.")

    def stealSessionLock(self):
        if self.readonly:
            raise IOError("World is opened read only.")
        self.acquireSessionLock()

    # --- Format detection ---

    @classmethod
    def canOpenFile(cls, filename):
        """
        Ask this adapter if it can open the given file.

        :param filename: File to identify
        :type filename: str | unicode
        :return:
        :rtype: boolean
        """
        if os.path.exists(os.path.join(filename, "chunks.dat")):
            return False  # exclude Pocket Edition folders

        if not os.path.isdir(filename):
            f = os.path.basename(filename)
            if f not in ("level.dat", "level.dat_old"):
                return False
            filename = os.path.dirname(filename)

        files = os.listdir(filename)
        if "level.dat" in files or "level.dat_old" in files:
            return True

        return False

    # --- Dimensions ---

    def listDimensions(self):
        """
        List the names of all dimensions in this world.

        :return:
        :rtype: iterator of str
        """
        return self.selectedRevision.listDimensions()

    # --- Chunks ---

    def chunkCount(self, dimName):
        """
        Count the chunks in the given dimension

        :param dimName:
        :type dimName: str
        :return:
        :rtype: int
        """
        return self.selectedRevision.chunkCount(dimName)

    def chunkPositions(self, dimName):
        """
        List the chunk positions (cx, cz) in the given dimension.

        :type dimName: unicode or str
        :return:
        :rtype: Iterator of (int, int)
        """
        return iter(self.selectedRevision.chunkPositions(dimName))

    def containsChunk(self, cx, cz, dimName):
        """
        Return whether the given chunk is present in the given dimension

        :type cx: int or dtype
        :type cz: int or dtype
        :type dimName: str
        :return:
        :rtype: bool
        """
        return self.selectedRevision.containsChunk(cx, cz, dimName)

    def readChunk(self, cx, cz, dimName):
        """
        Return chunk (cx, cz) in the given dimension as an AnvilChunkData. Raise ChunkNotPresent if not found.

        :type cx: int or dtype
        :type cz: int or dtype
        :type dimName: str
        :return:
        :rtype: AnvilChunkData
        """
        try:
            data = self.selectedRevision.readChunkBytes(cx, cz, dimName)
            chunkTag = nbt.load(buf=data)
            log.debug("_getChunkData: Chunk %s loaded (%s bytes)", (cx, cz), len(data))
            chunkData = AnvilChunkData(self, cx, cz, dimName, chunkTag)
        except ChunkNotPresent:
            raise
        except (KeyError, IndexError, zlib.error, UnicodeError) as e:  # Missing nbt keys, lists too short, decompression failure, unknown NBT tags
            raise AnvilChunkFormatError("Error loading chunk: %r" % e, None, sys.exc_info()[2])

        return chunkData

    def writeChunk(self, chunk):
        """
        Write the given AnvilChunkData to the current revision.

        :type chunk: mceditlib.anvil.adapter.AnvilChunkData
        """
        tag = chunk.buildNBTTag()
        self.selectedRevision.writeChunkBytes(chunk.cx, chunk.cz, chunk.dimName, tag.save(compressed=False))

    def createChunk(self, cx, cz, dimName):
        """
        Create a new empty chunk at the given position in the given dimension.

        :type cx: int
        :type cz: int
        :type dimName: str
        :return:
        :rtype: AnvilChunkData
        """
        if self.selectedRevision.containsChunk(cx, cz, dimName):
            raise ValueError("Chunk %s already exists in dim %r" % ((cx, cz), dimName))
        chunk = AnvilChunkData(self, cx, cz, dimName, create=True)
        self.selectedRevision.writeChunkBytes(cx, cz, dimName, chunk.buildNBTTag().save(compressed=False))
        return chunk

    def deleteChunk(self, cx, cz, dimName):
        """
        Delete the chunk at the given position in the given dimension.

        :type cx: int
        :type cz: int
        :type dimName: str
        """
        self.selectedRevision.deleteChunk(cx, cz, dimName)

    # --- Players ---

    def listPlayers(self):
        """
        List the names/UUIDs of all players in this world
        (XXX players folder in dimension folders??)

        :return:
        :rtype: Iterator of unicode
        """
        for f in self.selectedRevision.listFolder("playerdata"):
            if f.endswith(".dat"):
                yield f[11:-4]

        if "Player" in self.metadata.rootTag:
            yield ""

    def getPlayer(self, playerUUID=""):
        return AnvilPlayerRef(self, playerUUID)

    def getPlayerTag(self, playerUUID=""):
        """
        Return the root NBT tag for the named player. Raise PlayerNotFound if not present.

        Parameters
        ----------
        playerUUID : unicode
            The player ID returned from :ref:`listPlayers`

        Returns
        -------
        player : AnvilPlayerRef
        """
        if playerUUID == "":
            if "Player" in self.metadata.rootTag:
                # single-player world
                playerTag = self.metadata.rootTag["Player"]
                return playerTag
            raise PlayerNotFound(playerUUID)
        else:
            playerFilePath = "playerdata/%s.dat" % playerUUID
            if self.selectedRevision.containsFile(playerFilePath):
                # multiplayer world, found this player
                playerTag = nbt.load(buf=self.selectedRevision.readFile(playerFilePath))
                return playerTag
            else:
                raise PlayerNotFound(playerUUID)

    def savePlayerTag(self, tag, playerUUID):
        if playerUUID == "":
            # sync metadata?
            self.metadata.dirty = True
        else:
            self.selectedRevision.writeFile("playerdata/%s.dat" % playerUUID, tag.save())

    def createPlayer(self, playerUUID=""):
        """
        Create a new player with the given name and return the PlayerRef. Raises some kind of IOError if the player
         could not be created.

        :param playerUUID:
        :type playerUUID: str
        :return:
        :rtype: PCPlayer
        """
        if self.readonly:
            raise IOError("World is opened read only.")

        playerFilePath = "playerdata/%s.dat" % playerUUID

        if playerUUID == "":
            if "Player" in self.metadata.rootTag["Data"]:
                raise IOError("Single-player player already exists.")
            playerTag = nbt.TAG_Compound()
            self.metadata.rootTag["Data"]["Player"] = playerTag
        else:
            if self.selectedRevision.containsFile(playerFilePath):
                raise ValueError("Cannot create player %s: already exists.")

            playerTag = nbt.TAG_Compound()

        player = AnvilPlayerRef(playerTag, self)
        nbtattr.SetNBTDefaults(player)

        if playerUUID != "Player":
            self.checkSessionLock()
            self.selectedRevision.writeFile(playerFilePath, playerTag.save())

        return self.getPlayer(playerUUID)

    # --- Maps ---

    def listMaps(self):
        """
        Return a list of map IDs for this world's map items.

        :return: list[object]
        """
        mapRE = re.compile(r'map_(\d+)\.dat')
        for filename in self.selectedRevision.listFolder("data"):
            basename = filename.split("/")[-1]
            match = mapRE.match(basename)
            if match is None or len(match.groups()) == 0:
                continue

            mapID = match.group(1)
            yield int(mapID)

    def getMap(self, mapID):
        return AnvilMapData(self.getMapTag(mapID), mapID, self)

    def _getMapPath(self, mapID):
        return "data/map_%s.dat" % mapID

    def getMapTag(self, mapID):
        mapPath = self._getMapPath(mapID)
        if not self.selectedRevision.containsFile(mapPath):
            raise KeyError("Map %s not found" % mapID)

        mapData = self.selectedRevision.readFile(mapPath)
        mapNBT = nbt.load(buf=mapData)
        return mapNBT

    def saveMapTag(self, mapID, mapTag):
        self.selectedRevision.writeFile(self._getMapPath(mapID), mapTag.save())

    def createMap(self):
        # idcounts.dat should hold the ID number of the last created map
        # but we can't trust it because of bugs in the old map import filters
        mapIDs = list(self.listMaps())
        if len(mapIDs):
            maximumID = max(mapIDs)
            mapID = maximumID + 1
        else:
            mapID = 0

        idcountsTag = nbt.TAG_Compound()
        idcountsTag["map"] = nbt.TAG_Short(mapID)

        # idcounts.dat is not compressed.
        self.selectedRevision.writeFile("data/idcounts.dat", idcountsTag.save(compressed=False))

        mapData = AnvilMapData.create(mapID, self)

        mapData.save()
        return mapData

    def deleteMap(self, mapID):
        self.selectedRevision.deleteFile(self._getMapPath(mapID))

    # --- Metadata ---

    def getWorldVersionInfo(self):
        versionTag = self.metadata.Version
        return VersionInfo('java', versionTag.Id, versionTag.Name, versionTag.Snapshot)


VersionInfo = collections.namedtuple('VersionInfo', 'format id name snapshot')

class AnvilMapData(NBTCompoundRef):
    def __init__(self, mapTag, mapID, adapter):
        if "data" not in mapTag:
            raise LevelFormatError("Map NBT is missing required tag 'data'")
        super(AnvilMapData, self).__init__(mapTag["data"], adapter)
        self.mapTag = mapTag
        if self._colors.shape[0] != self.width * self.height:
            raise LevelFormatError("Map colors array does not match map size. (%dx%d != %d)"
                                   % (self.width, self.height, self.colors.shape[0]))

        self.mapID = mapID
        self.adapter = adapter

    @classmethod
    def create(cls, mapID, adapter, width=128, height=128):
        mapTag = nbt.TAG_Compound()
        mapDataTag = nbt.TAG_Compound()
        mapTag["data"] = mapDataTag
        mapDataTag["colors"] = nbt.TAG_Byte_Array(numpy.zeros((width * height,), dtype=numpy.uint8))
        mapData = cls(mapTag, mapID, adapter)
        mapData.dimension = 0
        mapData.width = width
        mapData.height = height
        mapData.scale = 1
        mapData.xCenter = -1 << 30
        mapData.zCenter = -1 << 30
        return mapData

    def save(self):
        self.adapter.saveMapTag(self.mapID, self.mapTag)

    dimension = nbtattr.NBTAttr('dimension', nbt.TAG_Byte)
    height = nbtattr.NBTAttr('height', nbt.TAG_Short, 128)
    width = nbtattr.NBTAttr('width', nbt.TAG_Short, 128)
    scale = nbtattr.NBTAttr('scale', nbt.TAG_Byte)
    xCenter = nbtattr.NBTAttr('xCenter', nbt.TAG_Int, 0)
    zCenter = nbtattr.NBTAttr('zCenter', nbt.TAG_Int, 0)
    _colors = nbtattr.NBTAttr('colors', nbt.TAG_Byte_Array)

    @property
    def colors(self):
        return self._colors.reshape((self.height, self.width))

    def getColorsAsRGBA(self):
        # Note: on little endian systems, with relation to 32-bit values this is ABGR.

        return self.colorTable[self.colors]

    _colorTable = [
        (0, 0, 0, 0),
        (0, 0, 0, 0),
        (0, 0, 0, 0),
        (0, 0, 0, 0),
        (88, 124, 39, 255),
        (108, 151, 47, 255),
        (125, 176, 55, 255),
        (66, 93, 29, 255),
        (172, 162, 114, 255),
        (210, 199, 138, 255),
        (244, 230, 161, 255),
        (128, 122, 85, 255),
        (138, 138, 138, 255),
        (169, 169, 169, 255),
        (197, 197, 197, 255),
        (104, 104, 104, 255),
        (178, 0, 0, 255),
        (217, 0, 0, 255),
        (252, 0, 0, 255),
        (133, 0, 0, 255),
        (111, 111, 178, 255),
        (136, 136, 217, 255),
        (158, 158, 252, 255),
        (83, 83, 133, 255),
        (116, 116, 116, 255),
        (142, 142, 142, 255),
        (165, 165, 165, 255),
        (87, 87, 87, 255),
        (0, 86, 0, 255),
        (0, 105, 0, 255),
        (0, 123, 0, 255),
        (0, 64, 0, 255),
        (178, 178, 178, 255),
        (217, 217, 217, 255),
        (252, 252, 252, 255),
        (133, 133, 133, 255),
        (114, 117, 127, 255),
        (139, 142, 156, 255),
        (162, 166, 182, 255),
        (85, 87, 96, 255),
        (105, 75, 53, 255),
        (128, 93, 65, 255),
        (149, 108, 76, 255),
        (78, 56, 39, 255),
        (78, 78, 78, 255),
        (95, 95, 95, 255),
        (111, 111, 111, 255),
        (58, 58, 58, 255),
        (44, 44, 178, 255),
        (54, 54, 217, 255),
        (63, 63, 252, 255),
        (33, 33, 133, 255),
        (99, 83, 49, 255),
        (122, 101, 61, 255),
        (141, 118, 71, 255),
        (74, 62, 38, 255),
        (178, 175, 170, 255),
        (217, 214, 208, 255),
        (252, 249, 242, 255),
        (133, 131, 127, 255),
        (150, 88, 36, 255),
        (184, 108, 43, 255),
        (213, 125, 50, 255),
        (113, 66, 27, 255),
        (124, 52, 150, 255),
        (151, 64, 184, 255),
        (176, 75, 213, 255),
        (93, 39, 113, 255),
        (71, 107, 150, 255),
        (87, 130, 184, 255),
        (101, 151, 213, 255),
        (53, 80, 113, 255),
        (159, 159, 36, 255),
        (195, 195, 43, 255),
        (226, 226, 50, 255),
        (120, 120, 27, 255),
        (88, 142, 17, 255),
        (108, 174, 21, 255),
        (125, 202, 25, 255),
        (66, 107, 13, 255),
        (168, 88, 115, 255),
        (206, 108, 140, 255),
        (239, 125, 163, 255),
        (126, 66, 86, 255),
        (52, 52, 52, 255),
        (64, 64, 64, 255),
        (75, 75, 75, 255),
        (39, 39, 39, 255),
        (107, 107, 107, 255),
        (130, 130, 130, 255),
        (151, 151, 151, 255),
        (80, 80, 80, 255),
        (52, 88, 107, 255),
        (64, 108, 130, 255),
        (75, 125, 151, 255),
        (39, 66, 80, 255),
        (88, 43, 124, 255),
        (108, 53, 151, 255),
        (125, 62, 176, 255),
        (66, 33, 93, 255),
        (36, 52, 124, 255),
        (43, 64, 151, 255),
        (50, 75, 176, 255),
        (27, 39, 93, 255),
        (71, 52, 36, 255),
        (87, 64, 43, 255),
        (101, 75, 50, 255),
        (53, 39, 27, 255),
        (71, 88, 36, 255),
        (87, 108, 43, 255),
        (101, 125, 50, 255),
        (53, 66, 27, 255),
        (107, 36, 36, 255),
        (130, 43, 43, 255),
        (151, 50, 50, 255),
        (80, 27, 27, 255),
        (17, 17, 17, 255),
        (21, 21, 21, 255),
        (25, 25, 25, 255),
        (13, 13, 13, 255),
        (174, 166, 53, 255),
        (212, 203, 65, 255),
        (247, 235, 76, 255),
        (130, 125, 39, 255),
        (63, 152, 148, 255),
        (78, 186, 181, 255),
        (91, 216, 210, 255),
        (47, 114, 111, 255),
        (51, 89, 178, 255),
        (62, 109, 217, 255),
        (73, 129, 252, 255),
        (39, 66, 133, 255),
        (0, 151, 39, 255),
        (0, 185, 49, 255),
        (0, 214, 57, 255),
        (0, 113, 30, 255),
        (90, 59, 34, 255),
        (110, 73, 41, 255),
        (127, 85, 48, 255),
        (67, 44, 25, 255),
        (78, 1, 0, 255),
        (95, 1, 0, 255),
        (111, 2, 0, 255),
        (58, 1, 0, 255),
        (147, 124, 113, 0),
        (180, 152, 138, 0),
        (209, 177, 161, 0),
        (110, 93, 85, 0),
        (112, 57, 25, 0),
        (137, 70, 31, 0),
        (159, 82, 36, 0),
        (84, 43, 19, 0),
        (105, 61, 76, 0),
        (128, 75, 93, 0),
        (149, 87, 108, 0),
        (78, 46, 57, 0),
        (79, 76, 97, 0),
        (96, 93, 119, 0),
        (112, 108, 138, 0),
        (59, 57, 73, 0),
        (131, 93, 25, 0),
        (160, 114, 31, 0),
        (186, 133, 36, 0),
        (98, 70, 19, 0),
        (72, 82, 37, 0),
        (88, 100, 45, 0),
        (103, 117, 53, 0),
        (54, 61, 28, 0),
        (112, 54, 55, 0),
        (138, 66, 67, 0),
        (160, 77, 78, 0),
        (84, 40, 41, 0),
        (40, 28, 24, 0),
        (49, 35, 30, 0),
        (57, 41, 35, 0),
        (30, 21, 18, 0),
        (95, 75, 69, 0),
        (116, 92, 84, 0),
        (135, 107, 98, 0),
        (71, 56, 51, 0),
        (61, 64, 64, 0),
        (75, 79, 79, 0),
        (87, 92, 92, 0),
        (46, 48, 48, 0),
        (86, 51, 62, 0),
        (105, 62, 75, 0),
        (122, 73, 88, 0),
        (64, 38, 46, 0),
        (53, 43, 64, 0),
        (65, 53, 79, 0),
        (76, 62, 92, 0),
        (40, 32, 48, 0),
        (53, 35, 24, 0),
        (65, 43, 30, 0),
        (76, 50, 35, 0),
        (40, 26, 18, 0),
        (53, 57, 29, 0),
        (65, 70, 36, 0),
        (76, 82, 42, 0),
        (40, 43, 22, 0),
        (100, 42, 32, 0),
        (122, 51, 39, 0),
        (142, 60, 46, 0),
        (75, 31, 24, 0),
        (26, 15, 11, 0),
        (31, 18, 13, 0),
        (37, 22, 16, 0),
        (19, 11, 8, 0)
    ]

    _colorTable += [(0, 0, 0, 0)] * (256 - len(_colorTable))

    colorTable = numpy.array(_colorTable, dtype=numpy.uint8)


class PlayerAbilitiesRef(nbtattr.NBTCompoundRef):
    mayBuild = nbtattr.NBTAttr('mayBuild', nbt.TAG_Byte, 0)
    instabuild = nbtattr.NBTAttr('instabuild', nbt.TAG_Byte, 0)
    flying = nbtattr.NBTAttr('flying', nbt.TAG_Byte, 0)
    mayfly = nbtattr.NBTAttr('mayfly', nbt.TAG_Byte, 0)
    invulnerable = nbtattr.NBTAttr('invulnerable', nbt.TAG_Byte, 0)


class AnvilPlayerRef(object):
    # xxx inherit from PCEntityMobRefBase?
    def __init__(self, adapter, playerUUID):
        self.playerUUID = playerUUID
        self.adapter = adapter
        self.rootTag = adapter.getPlayerTag(playerUUID)
        self.dirty = False

    @property
    def blockTypes(self):
        return self.adapter.blocktypes

    UUID = nbtattr.NBTUUIDAttr()

    id = nbtattr.NBTAttr("id", nbt.TAG_String)
    Position = nbtattr.NBTVectorAttr("Pos", nbt.TAG_Double)
    Motion = nbtattr.NBTVectorAttr("Motion", nbt.TAG_Double)
    Rotation = nbtattr.NBTListAttr("Rotation", nbt.TAG_Float)

    Air = nbtattr.NBTAttr('Air', nbt.TAG_Short, 300)
    AttackTime = nbtattr.NBTAttr('AttackTime', nbt.TAG_Short, 0)
    DeathTime = nbtattr.NBTAttr('DeathTime', nbt.TAG_Short, 0)
    Fire = nbtattr.NBTAttr('Fire', nbt.TAG_Short, -20)
    Health = nbtattr.NBTAttr('Health', nbt.TAG_Short, 20)
    HurtTime = nbtattr.NBTAttr('HurtTime', nbt.TAG_Short, 0)
    Score = nbtattr.NBTAttr('Score', nbt.TAG_Int, 0)
    FallDistance = nbtattr.NBTAttr('FallDistance', nbt.TAG_Float, 0)
    OnGround = nbtattr.NBTAttr('OnGround', nbt.TAG_Byte, 0)
    Dimension = nbtattr.NBTAttr('Dimension', nbt.TAG_Int, 0)

    Inventory = entities.SlottedInventoryAttr('Inventory')

    GAMETYPE_SURVIVAL = 0
    GAMETYPE_CREATIVE = 1
    GAMETYPE_ADVENTURE = 2
    GameType = nbtattr.NBTAttr('playerGameType', nbt.TAG_Int, GAMETYPE_SURVIVAL)

    abilities = nbtattr.NBTCompoundAttr("abilities", PlayerAbilitiesRef)

    def setAbilities(self, gametype):
        # Assumes GAMETYPE_CREATIVE is the only mode with these abilities set,
        # which is true for now.  Future game modes may not hold this to be
        # true, however.
        if gametype == self.GAMETYPE_CREATIVE:
            self.abilities.instabuild = True
            self.abilities.mayfly = True
            self.abilities.invulnerable = True
        else:
            self.abilities.flying = True
            self.abilities.instabuild = True
            self.abilities.mayfly = True
            self.abilities.invulnerable = True

    def setGameType(self, gametype):
        self.GameType = gametype
        self.setAbilities(gametype)

    @property
    def Spawn(self):
        return [self.rootTag[i].value for i in ("SpawnX", "SpawnY", "SpawnZ")]

    @Spawn.setter
    def Spawn(self, pos):
        for name, val in zip(("SpawnX", "SpawnY", "SpawnZ"), pos):
            self.rootTag[name] = nbt.TAG_Int(val)

    def save(self):
        if self.dirty:
            self.adapter.savePlayerTag(self.rootTag, self.playerUUID)
            self.dirty = False

    _dimNames = {
        -1:"DIM-1",
        0:"",
        1:"DIM1",
        }

    _dimNumbers = {v:k for k, v in _dimNames.iteritems()}

    @property
    def dimName(self):
        return self._dimNames.get(self.Dimension, "Unknown dimension %s" % self.Dimension)  # xxx ask adapter

    @dimName.setter
    def dimName(self, name):
        self.Dimension = self._dimNumbers[name]
