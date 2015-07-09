from __future__ import absolute_import
import collections
import logging
import time
import weakref
import itertools

import numpy
import re
from mceditlib import cachefunc

from mceditlib.block_copy import copyBlocksIter
from mceditlib.blocktypes import BlockType
from mceditlib.nbtattr import NBTListProxy
from mceditlib.operations.block_fill import FillBlocksOperation
from mceditlib.operations.analyze import AnalyzeOperation
from mceditlib.selection import BoundingBox
from mceditlib.findadapter import findAdapter
from mceditlib.multi_block import getBlocks, setBlocks
from mceditlib.schematic import createSchematic
from mceditlib.util import displayName, chunk_pos, exhaust, matchEntityTags
from mceditlib.util.lazyprop import weakrefprop
from mceditlib.blocktypes import BlockType

log = logging.getLogger(__name__)

DIM_NETHER = -1
DIM_END = 1

_zeros = {}


def string_func(array):
    numpy.set_string_function(None)
    string = repr(array)
    string = string[:-1] + ", shape=%s)" % (array.shape,)
    numpy.set_string_function(string_func)
    return string


numpy.set_string_function(string_func)


class EntityListProxy(collections.MutableSequence):
    """
    A proxy for the Entities and TileEntities lists of a WorldEditorChunk. Accessing an element returns an EntityRef
    or TileEntityRef wrapping the element of the underlying NBT compound, with a reference to the WorldEditorChunk.

    These Refs cannot be created at load time as they hold a reference to the chunk, preventing the chunk from being
    unloaded when its refcount reaches zero.
    """

    chunk = weakrefprop()

    def __init__(self, chunk, attrName, refClass):
        self.attrName = attrName
        self.refClass = refClass
        self.chunk = chunk

    def __getitem__(self, key):
        return self.refClass(getattr(self.chunk.chunkData, self.attrName)[key], self.chunk)

    def __setitem__(self, key, value):
        tagList = getattr(self.chunk.chunkData, self.attrName)
        if isinstance(key, slice):
            tagList[key] = [v.rootTag for v in value]
        else:
            tagList[key] = value.rootTag

    def __delitem__(self, key):
        del getattr(self.chunk.chunkData, self.attrName)[key]

    def __len__(self):
        return len(getattr(self.chunk.chunkData, self.attrName))

    def insert(self, index, value):
        getattr(self.chunk.chunkData, self.attrName).insert(index, value.rootTag)

class WorldEditorChunk(object):
    """
    This is a 16x16xH chunk in a format-independent world.
    The Blocks, Data, SkyLight, and BlockLight arrays are divided into
    vertical sections of 16x16x16, accessed using the `getSection` method.
    """



    def __init__(self, chunkData, editor):
        self.worldEditor = editor
        self.chunkData = chunkData
        self.cx, self.cz = chunkData.cx, chunkData.cz
        self.dimName = chunkData.dimName
        self.dimension = editor.getDimension(self.dimName)

        self.Entities = EntityListProxy(self, "Entities", editor.adapter.EntityRef)
        self.TileEntities = EntityListProxy(self, "TileEntities", editor.adapter.TileEntityRef)
        #self.Entities = [editor.adapter.EntityRef(tag, self) for tag in chunkData.Entities]
        #self.TileEntities = [editor.adapter.TileEntityRef(tag, self) for tag in chunkData.TileEntities]


    def buildNBTTag(self):
        return self.chunkData.buildNBTTag()

    def __str__(self):
        return u"WorldEditorChunk, coords:{0}, world: {1}, dim: {2} D:{3}".format(
            (self.cx, self.cz),
            self.worldEditor.displayName,
            self.dimName, self.dirty)

    # --- WorldEditorChunkData accessors ---

    @property
    def bounds(self):
        return self.chunkData.bounds

    @property
    def chunkPosition(self):
        return self.cx, self.cz

    @property
    def rootTag(self):
        return self.chunkData.rootTag

    @property
    def dirty(self):
        return self.chunkData.dirty

    @dirty.setter
    def dirty(self, val):
        self.chunkData.dirty = val

    # --- Chunk attributes ---

    def sectionPositions(self):
        return self.chunkData.sectionPositions()

    def getSection(self, cy, create=False):
        return self.chunkData.getSection(cy, create)

    @property
    def blocktypes(self):
        return self.dimension.blocktypes

    @property
    def Biomes(self):
        return self.chunkData.Biomes

    @property
    def HeightMap(self):
        return self.chunkData.HeightMap

    @property
    def TerrainPopulated(self):
        return self.chunkData.TerrainPopulated

    @TerrainPopulated.setter
    def TerrainPopulated(self, val):
        self.chunkData.TerrainPopulated = val

    def addEntity(self, ref):
        if ref.chunk is self:
            return
        self.chunkData.Entities.append(ref.rootTag)
        ref.chunk = self
        self.dirty = True

    def removeEntity(self, ref):
        self.chunkData.Entities.remove(ref.rootTag)
        ref.chunk = None
        self.dirty = True

    def removeEntities(self, entities):
        for ref in entities:  # xxx O(n*m)
            self.removeEntity(ref)

    def addTileEntity(self, ref):
        if ref.chunk is self:
            return
        self.chunkData.TileEntities.append(ref.rootTag)
        ref.chunk = self
        self.dirty = True

    def removeTileEntity(self, ref):
        if ref.chunk is not self:
            return
        self.chunkData.TileEntities.remove(ref.rootTag)
        ref.chunk = None
        ref.rootTag = None
        self.dirty = True

    @property
    def TileTicks(self):
        """
        Directly accesses the TAG_List of TAG_Compounds. Not protected by Refs like Entities and TileEntities are.

        :return:
        :rtype:
        """
        return self.chunkData.TileTicks

class WorldEditor(object):
    def __init__(self, filename=None, create=False, readonly=False, adapterClass=None, adapter=None, resume=None):
        """
        Load a Minecraft level of any format from the given filename.

        If you try to create an existing world, IOError will be raised.

        :type filename: str or unknown or unicode
        :type create: bool
        :type readonly: bool
        :type adapter: unknown or mceditlib.anvil.adapter.AnvilWorldAdapter or mceditlib.schematic.SchematicFileAdapter
        :type adapterClass: class
        :type resume: None or bool
        :return:
        :rtype: WorldEditor
        """
        self.playerCache = {}
        assert not (create and readonly)
        assert not create or adapterClass, "create=True requires an adapterClass"

        if adapter:
            self.adapter = adapter
        elif adapterClass:
            self.adapter = adapterClass(filename, create, readonly, resume=resume)
        else:
            self.adapter = findAdapter(filename, readonly, resume=resume)

        self.filename = filename
        self.readonly = readonly

        # maps (cx, cz, dimName) tuples to WorldEditorChunk
        self._loadedChunks = weakref.WeakValueDictionary()

        # caches ChunkData from adapter
        self._chunkDataCache = cachefunc.lru_cache_object(self._getChunkDataRaw, 1000)
        self._chunkDataCache.should_decache = self._shouldUnloadChunkData
        self._chunkDataCache.will_decache = self._willUnloadChunkData

        # caches recently used WorldEditorChunks
        self.recentChunks = collections.deque(maxlen=100)

        self._allChunks = None

        self.dimensions = {}

        self.currentRevision = 0

    def __repr__(self):
        return "WorldEditor(adapter=%r)" % self.adapter

    # --- Debug ---

    def setCacheLimit(self, size):
        self._chunkDataCache.setCacheLimit(size)

    # --- Undo/redo ---
    def requireRevisions(self):
        self.adapter.requireRevisions()

    def undo(self):
        self.gotoRevision(self.currentRevision - 1)

    def redo(self):
        self.gotoRevision(self.currentRevision + 1)

    def beginUndo(self):
        """
        Begin a new undo revision, creating a new revision in the underlying storage chain if an editable
        revision is not selected.
        :return:
        :rtype:
        """
        self.adapter.createRevision()
        self.currentRevision += 1
        log.info("Opened revision %d", self.currentRevision)

    def commitUndo(self, revisionInfo=None):
        exhaust(self.commitUndoIter(revisionInfo))

    def commitUndoIter(self, revisionInfo=None):
        """
        Record all changes since the last call to beginUndo into the adapter's current revision. The revision is closed
        and beginUndo must be called to open the next revision.

        :param revisionInfo: May be supplied to record metadata for this undo
        :type revisionInfo: object | None
        :return:
        :rtype:
        """
        self.adapter.setRevisionInfo(revisionInfo)
        for status in self.syncToDiskIter():
            yield status

        self.adapter.closeRevision()
        log.info("Closed revision %d", self.currentRevision)

    def undoRevisions(self):
        """
        Iterate through all revisions and return (index, revisionInfo) tuples. revisionInfo is the info stored with
        commitUndo for each revision. Call selectUndoRevision with the index of the desired revision to rewind time.

        :return:
        :rtype:
        """
        for index, revision in self.adapter.listRevisions():
            yield index, revision.revisionInfo()

    def gotoRevision(self, index):
        """

        :param index:
        :type index:
        :return:
        :rtype:
        """
        assert index is not None, "None is not a revision index!"
        self.syncToDisk()
        self.playerCache.clear()

        changes = self.adapter.selectRevision(index)
        self.currentRevision = index
        if changes is None:
            return
        log.info("Going to revision %d", index)
        log.debug("Changes: %s", changes)
        self.recentChunks.clear()
        for dimName, chunkPositions in changes.chunks.iteritems():
            for cx, cz in chunkPositions:
                self._chunkDataCache.decache(cx, cz, dimName)
                self._loadedChunks.pop((cx, cz, dimName), None)

        # xxx slow, scan changes for chunks and check if they are added/removed
        self._allChunks = None

    def getRevisionChanges(self, oldIndex, newIndex):
        return self.adapter.getRevisionChanges(oldIndex, newIndex)

    # --- Save ---
    def syncToDisk(self):
        exhaust(self.syncToDiskIter())

    def syncToDiskIter(self):
        """
        Write all loaded chunks, player files, etc to disk.

        :return:
        :rtype:
        """
        dirtyPlayers = 0
        for player in self.playerCache.itervalues():
            # xxx should be in adapter?
            if player.dirty:
                dirtyPlayers += 1
                player.save()

        dirtyChunkCount = 0
        for i, (cx, cz, dimName) in enumerate(self._chunkDataCache):
            yield i, len(self._chunkDataCache), "Writing modified chunks"

            chunkData = self._chunkDataCache(cx, cz, dimName)
            if chunkData.dirty:
                dirtyChunkCount += 1
                self.adapter.writeChunk(chunkData)
                chunkData.dirty = False
        self.adapter.syncToDisk()
        log.info(u"Saved %d chunks and %d players", dirtyChunkCount, dirtyPlayers)

    def saveChanges(self):
        exhaust(self.saveChangesIter())

    def saveChangesIter(self):
        if self.readonly:
            raise IOError("World is opened read only.")

        self.syncToDisk()
        self.playerCache.clear()
        for status in self.adapter.saveChangesIter():
            yield status

    def saveToFile(self, filename):
        # XXXX only works with .schematics!!!
        self.adapter.saveToFile(filename)

    def close(self):
        """
        Unload all chunks and close all open filehandles.
        """
        self.adapter.close()
        self.recentChunks.clear()

        self._allChunks = None
        self._loadedChunks.clear()
        self._chunkDataCache.clear()

    # --- World limits ---

    @property
    def maxHeight(self):
        return self.adapter.maxHeight

    # --- World info ---

    @property
    def displayName(self):
        return displayName(self.filename)

    @property
    def blocktypes(self):
        return self.adapter.blocktypes

    # --- Chunk I/O ---

    def preloadChunkPositions(self):
        log.info(u"Scanning for regions in %s...", self.adapter.filename)
        self._allChunks = collections.defaultdict(set)
        for dimName in self.adapter.listDimensions():
            start = time.time()
            chunkPositions = set(self.adapter.chunkPositions(dimName))
            chunkPositions.update((cx, cz) for cx, cz, cDimName in self._chunkDataCache if cDimName == dimName)
            log.info("Dim %s: Found %d chunks in %0.2f seconds.",
                     dimName,
                     len(chunkPositions),
                     time.time() - start)
            self._allChunks[dimName] = chunkPositions

    def chunkCount(self, dimName):
        return self.adapter.chunkCount(dimName)

    def chunkPositions(self, dimName):
        """
        Iterates over (xPos, zPos) tuples, one for each chunk in the given dimension.
        May initiate a costly chunk scan.

        :param dimName: Name of dimension
        :type dimName: str
        :return:
        :rtype:
        """
        if self._allChunks is None:
            self.preloadChunkPositions()
        return self._allChunks[dimName].__iter__()

    def _getChunkDataRaw(self, cx, cz, dimName):
        """
        Wrapped by cachefunc.lru_cache in __init__
        """
        return self.adapter.readChunk(cx, cz, dimName)

    def _shouldUnloadChunkData(self, key):
        return key not in self._loadedChunks

    def _willUnloadChunkData(self, chunkData):
        if chunkData.dirty and not self.readonly:
            self.adapter.writeChunk(chunkData)

    def getChunk(self, cx, cz, dimName, create=False):
        """
        :return: Chunk at the given position.
        :rtype: WorldEditorChunk
        """
        if create and not self.containsChunk(cx, cz, dimName):
            self.createChunk(cx, cz, dimName)

        chunk = self._loadedChunks.get((cx, cz, dimName))
        if chunk is not None:
            return chunk

        startTime = time.time()
        chunkData = self._chunkDataCache(cx, cz, dimName)
        chunk = WorldEditorChunk(chunkData, self)

        duration = time.time() - startTime
        if duration > 1:
            log.warn("Chunk %s took %0.2f seconds to load! entities=%s tileentities=%s tileticks=%s",
                     (cx, cz), duration, len(chunk.Entities), len(chunk.TileEntities),
                     len(chunk.rootTag.get("TileTicks", ())))

        self._loadedChunks[cx, cz, dimName] = chunk

        self.recentChunks.append(chunk)
        return chunk

    # --- Chunk dirty bit ---

    def listDirtyChunks(self):
        for cx, cz, dimName in self._chunkDataCache:
            chunkData = self._chunkDataCache(cx, cz, dimName)
            if chunkData.dirty:
                yield cx, cz, dimName

    # --- HeightMaps ---

    def heightMapAt(self, x, z, dimName):
        zc = z >> 4
        xc = x >> 4
        xInChunk = x & 0xf
        zInChunk = z & 0xf

        ch = self.getChunk(xc, zc, dimName)

        heightMap = ch.HeightMap

        return heightMap[zInChunk, xInChunk]  # HeightMap indices are backwards

    # --- Chunk manipulation ---

    def containsChunk(self, cx, cz, dimName):
        if self._allChunks is not None:
            return (cx, cz) in self._allChunks[dimName]
        if (cx, cz, dimName) in self._chunkDataCache:
            return True

        return self.adapter.containsChunk(cx, cz, dimName)

    def containsPoint(self, x, y, z, dimName):
        if y < 0 or y > 127:
            return False
        return self.containsChunk(x >> 4, z >> 4, dimName)

    def createChunk(self, cx, cz, dimName):
        if self.containsChunk(cx, cz, dimName):
            raise ValueError("%r:Chunk %s already present in %s!".format(self, (cx, cz), dimName))

        if hasattr(self.adapter, 'createChunk'):
            if self._allChunks is not None:
                self._allChunks[dimName].add((cx, cz))

            chunk = self.adapter.createChunk(cx, cz, dimName)
            self._chunkDataCache.store(chunk, cx, cz, dimName)

    def deleteChunk(self, cx, cz, dimName):
        self.adapter.deleteChunk(cx, cz, dimName)
        if self._allChunks is not None:
            self._allChunks[dimName].discard((cx, cz))

    # --- World metadata ---

    def getWorldMetadata(self):
        """
        Return an object containing global info about the world.

        Different level formats can return different objects for the world metadata.
        At the very least, you can expect the object to have Spawn and Seed attributes.

        Currently, only AnvilWorldMetadata is ever returned.
        :return:
        """
        return self.adapter.metadata

    # --- Maps ---

    def listMaps(self):
        """
        Return a list of map IDs for this world's map items.

        :return:
        """
        return self.adapter.listMaps()

    def getMap(self, mapID):
        """
        Return a map object for the given map ID

        :param mapID: Map ID returned by listMaps
        :return:
        """
        return self.adapter.getMap(mapID)

    def createMap(self):
        return self.adapter.createMap()

    # --- Players ---

    def listPlayers(self):
        return self.adapter.listPlayers()

    def getPlayer(self, playerUUID=""):
        player = self.playerCache.get(playerUUID)
        if player is None:
            player = self.adapter.getPlayer(playerUUID)
            self.playerCache[playerUUID] = player

        return player

    def createPlayer(self, playerName):
        return self.adapter.createPlayer(playerName)

    # --- Dimensions ---

    def listDimensions(self):
        return self.adapter.listDimensions()

    def getDimension(self, dimName=""):
        """

        :type dimName: str
        :return:
        :rtype: WorldEditorDimension
        """
        dim = self.dimensions.get(dimName)
        if dim is None:
            dim = WorldEditorDimension(self, dimName)
            self.dimensions[dimName] = dim
        return dim

    def dimNameFromNumber(self, dimNo):
        """
        Return the dimension name for the given number, as would be stored in the player's "dimension" tag.

        Handles "DIM1" and "DIM-1" for vanilla dimensions. Most mods add more dimensions similar to "DIM-42", "DIM-100"
        but some mods like Galacticraft use "DIM_SPACESTATION3" so make an educated guess about the dimension's name
        ending with its number.

        :param dimNo:
        :type dimNo:
        :return:
        :rtype:
        """
        dimNoStr = str(dimNo)
        for name in self.listDimensions():
            if name.endswith(dimNoStr):
                return name

    def dimNumberFromName(self, dimName):
        matches = re.findall(r'-[0-9]+', dimName)
        if not len(matches):
            raise ValueError("Could not parse a dimension number from %s", dimName)
        return int(matches[-1])

class WorldEditorDimension(object):
    def __init__(self, worldEditor, dimName):
        self.worldEditor = worldEditor
        self.adapter = worldEditor.adapter
        self.dimName = dimName

    def __repr__(self):
        return "WorldEditorDimension(dimName=%r, adapter=%r)" % (self.dimName, self.adapter)

    # --- Bounds ---

    _bounds = None

    @property
    def bounds(self):
        """

        :return:
        :rtype: BoundingBox
        """
        if self._bounds is None:
            if hasattr(self.adapter, "getDimensionBounds"):
                self._bounds = self.adapter.getDimensionBounds(self.dimName)
            else:
                self._bounds = self.getWorldBounds()
        return self._bounds

    def getWorldBounds(self):
        chunkPositions = list(self.chunkPositions())
        if len(chunkPositions) == 0:
            return BoundingBox((0, 0, 0), (0, 0, 0))

        chunkPositions = numpy.array(chunkPositions)
        mincx = (chunkPositions[:, 0]).min()
        maxcx = (chunkPositions[:, 0]).max()
        mincz = (chunkPositions[:, 1]).min()
        maxcz = (chunkPositions[:, 1]).max()

        origin = (mincx << 4, 0, mincz << 4)
        size = ((maxcx - mincx + 1) << 4, self.worldEditor.maxHeight, (maxcz - mincz + 1) << 4)

        return BoundingBox(origin, size)

    @property
    def size(self):
        return self.bounds.size

    @property
    def blocktypes(self):
        return self.worldEditor.blocktypes

    # --- Chunks ---

    def chunkCount(self):
        return self.worldEditor.chunkCount(self.dimName)

    def chunkPositions(self):
        return self.worldEditor.chunkPositions(self.dimName)

    def containsChunk(self, cx, cz):
        return self.worldEditor.containsChunk(cx, cz, self.dimName)

    def getChunk(self, cx, cz, create=False):
        """

        :type cx: int or dtype
        :type cz: int or dtype
        :type create: bool
        :return:
        :rtype: WorldEditorChunk
        """
        return self.worldEditor.getChunk(cx, cz, self.dimName, create)

    def getChunks(self, chunkPositions=None):
        """
        :type chunkPositions(): iterator
        :rtype: iterator
        """
        if chunkPositions is None:
            chunkPositions = self.chunkPositions()
        for cx, cz in chunkPositions:
            if self.containsChunk(cx, cz):
                yield self.getChunk(cx, cz)

    def createChunk(self, cx, cz):
        return self.worldEditor.createChunk(cx, cz, self.dimName)

    def deleteChunk(self, cx, cz):
        self.worldEditor.deleteChunk(cx, cz, self.dimName)

    # --- Entities and TileEntities ---

    def getEntities(self, selection, **kw):
        for chunk in self.getChunks(selection.chunkPositions()):
            for ref in chunk.Entities:
                if ref.Position in selection:
                    if matchEntityTags(ref, kw):
                        yield ref

    def getTileEntities(self, selection, **kw):
        for chunk in self.getChunks(selection.chunkPositions()):
            for ref in chunk.TileEntities:
                if ref.Position in selection:
                    if matchEntityTags(ref, kw):
                        yield ref

    def getTileEntity(self, pos, **kw):
        cx = pos[0] >> 4
        cz = pos[2] >> 4
        chunk = self.getChunk(cx, cz)
        for ref in chunk.TileEntities:
            if ref.Position == pos:
                if matchEntityTags(ref, kw):
                    return ref

    def addEntity(self, ref):
        x, y, z = ref.Position
        cx, cz = chunk_pos(x, z)
        chunk = self.getChunk(cx, cz, create=True)
        chunk.addEntity(ref.copy())

    def addTileEntity(self, ref):
        x, y, z = ref.Position
        cx, cz = chunk_pos(x, z)
        chunk = self.getChunk(cx, cz, create=True)
        existing = [old for old in chunk.TileEntities
                    if old.Position == (x, y, z)]
        for e in existing:
            chunk.removeTileEntity(e)

        chunk.addTileEntity(ref.copy())

    # --- Import/Export ---

    def copyBlocksIter(self, sourceLevel, sourceSelection, destinationPoint, blocksToCopy=None, entities=True, create=False, biomes=False, updateLights=False):
        return copyBlocksIter(self, sourceLevel, sourceSelection, destinationPoint, blocksToCopy, entities, create,
                              biomes, updateLights)


    def copyBlocks(self, sourceLevel, sourceSelection, destinationPoint, blocksToCopy=None, entities=True, create=False, biomes=False, updateLights=False):
        return exhaust(self.copyBlocksIter(sourceLevel, sourceSelection, destinationPoint, blocksToCopy,
                                           entities, create, biomes, updateLights))

    def exportSchematicIter(self, selection):
        schematic = createSchematic(shape=selection.size, blocktypes=self.blocktypes)

        return itertools.chain(copyBlocksIter(schematic.getDimension(), self, selection, (0, 0, 0)), [schematic])

    def exportSchematic(self, selection):
        """
        :type selection: mceditlib.box.BoundingBox
        :return:
        :rtype: WorldEditor
        """
        return exhaust(self.exportSchematicIter(selection))

    def importSchematicIter(self, schematic, destPoint):
        dim = schematic.getDimension()
        return copyBlocksIter(self, dim, dim.bounds, destPoint, biomes=True, create=True)

    def importSchematic(self, schematic, destPoint):
        return self.importSchematicIter(schematic, destPoint)

    # --- Fill/Replace ---

    def fillBlocksIter(self, box, block, blocksToReplace=(), updateLights=True):
        return FillBlocksOperation(self, box, block, blocksToReplace, updateLights)

    def fillBlocks(self, box, block, blocksToReplace=(), updateLights=True):
        return exhaust(self.fillBlocksIter(box, block, blocksToReplace, updateLights))
    
    # --- Analyze ---   

    def analyzeIter(self, selection):
        return AnalyzeOperation(self, selection)

    # --- Blocks by single coordinate ---

    def getBlock(self, x, y, z):
        ID = self.getBlockID(x, y, z)
        meta = self.getBlockData(x, y, z)
        return self.blocktypes[ID, meta]

    def setBlock(self, x, y, z, blocktype):
        if not isinstance(blocktype, BlockType):
            blocktype = self.blocktypes[blocktype]

        self.setBlockID(x, y, z, blocktype.ID)
        self.setBlockData(x, y, z, blocktype.meta)

    def getBlockID(self, x, y, z, default=0):
        cx = x >> 4
        cy = y >> 4
        cz = z >> 4
        if self.containsChunk(cx, cz):
            chunk = self.getChunk(cx, cz)
            sec = chunk.getSection(cy)
            if sec:
                array = sec.Blocks
                if array is not None:
                    return array[y & 0xf, z & 0xf, x & 0xf]
        return default

    def setBlockID(self, x, y, z, value):
        cx = x >> 4
        cy = y >> 4
        cz = z >> 4
        if self.containsChunk(cx, cz):
            chunk = self.getChunk(cx, cz)
            sec = chunk.getSection(cy, create=True)
            if sec:
                array = sec.Blocks
                assert array is not None
                if array is not None:
                    array[y & 0xf, z & 0xf, x & 0xf] = value
            chunk.dirty = True

    def getBlockData(self, x, y, z, default=0):
        cx = x >> 4
        cy = y >> 4
        cz = z >> 4
        if self.containsChunk(cx, cz):
            chunk = self.getChunk(cx, cz)
            sec = chunk.getSection(cy)
            if sec:
                array = sec.Data
                if array is not None:
                    return array[y & 0xf, z & 0xf, x & 0xf]
        return default

    def setBlockData(self, x, y, z, value):
        cx = x >> 4
        cy = y >> 4
        cz = z >> 4
        if self.containsChunk(cx, cz):
            chunk = self.getChunk(cx, cz)
            sec = chunk.getSection(cy, create=True)
            if sec:
                array = sec.Data
                assert array is not None
                if array is not None:
                    array[y & 0xf, z & 0xf, x & 0xf] = value
            chunk.dirty = True

    def getLight(self, arrayName, x, y, z, default=0):
        cx = x >> 4
        cy = y >> 4
        cz = z >> 4
        if self.containsChunk(cx, cz):
            chunk = self.getChunk(cx, cz)
            sec = chunk.getSection(cy)
            if sec:
                array = getattr(sec, arrayName)
                if array is not None:
                    return array[y & 0xf, z & 0xf, x & 0xf]
        return default

    def setLight(self, arrayName, x, y, z, value):
        cx = x >> 4
        cy = y >> 4
        cz = z >> 4
        if self.containsChunk(cx, cz):
            chunk = self.getChunk(cx, cz)
            sec = chunk.getSection(cy, create=True)
            if sec:
                array = getattr(sec, arrayName)
                if array is not None:
                    array[y & 0xf, z & 0xf, x & 0xf] = value
                chunk.dirty = True

    def getBlockLight(self, x, y, z, default=0):
        return self.getLight("BlockLight", x, y, z, default)

    def setBlockLight(self, x, y, z, value):
        return self.setLight("BlockLight", x, y, z, value)

    def getSkyLight(self, x, y, z, default=0):
        return self.getLight("SkyLight", x, y, z, default)

    def setSkyLight(self, x, y, z, value):
        return self.setLight("SkyLight", x, y, z, value)

    def getBiomeID(self, x, z, default=0):
        cx = x >> 4
        cz = z >> 4
        if self.containsChunk(cx, cz):
            chunk = self.getChunk(cx, cz)
            array = chunk.Biomes
            if array is not None:
                return array[z & 0xf, x & 0xf]
        return default

    def setBiomeID(self, x, z, value):
        cx = x >> 4
        cz = z >> 4
        if self.containsChunk(cx, cz):
            chunk = self.getChunk(cx, cz)
            array = chunk.Biomes
            assert array is not None
            if array is not None:
                array[z & 0xf, x & 0xf] = value
            chunk.dirty = True

    # --- Blocks by coordinate arrays ---

    def getBlocks(self, x, y, z,
                  return_Blocks=True,
                  return_Data=False,
                  return_BlockLight=False,
                  return_SkyLight=False,
                  return_Biomes=False):
        return getBlocks(self, x, y, z,
                         return_Blocks,
                         return_Data,
                         return_BlockLight,
                         return_SkyLight,
                         return_Biomes)

    def setBlocks(self, x, y, z,
                  Blocks=None,
                  Data=None,
                  BlockLight=None,
                  SkyLight=None,
                  Biomes=None,
                  updateLights=True):
        return setBlocks(self, x, y, z,
                         Blocks,
                         Data,
                         BlockLight,
                         SkyLight,
                         Biomes,
                         updateLights and self.adapter.hasLights)
