from __future__ import absolute_import
import collections
import logging
import time
import weakref
import itertools

import numpy

from mceditlib.block_copy import copyBlocksIter
from mceditlib.operations.block_fill import FillBlocksOperation
from mceditlib.blocktypes import pc_blocktypes
from mceditlib.geometry import BoundingBox
from mceditlib import nbt
from mceditlib.findadapter import findAdapter
from mceditlib.levelbase import matchEntityTags
from mceditlib.multi_block import getBlocks, setBlocks
from mceditlib.schematic import SchematicFileAdapter
from mceditlib.util import displayName, chunk_pos, exhaust, matchEntityTags


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
        self.worldEditor.chunkBecameDirty(self)

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
    def Entities(self):
        return self.chunkData.Entities

    @property
    def TileEntities(self):
        return self.chunkData.TileEntities

    @property
    def TerrainPopulated(self):
        return self.chunkData.TerrainPopulated

    @TerrainPopulated.setter
    def TerrainPopulated(self, val):
        self.chunkData.TerrainPopulated = val


class WorldEditor(object):
    def __init__(self, filename=None, create=False, readonly=False, adapterClass=None, adapter=None, resume=None):
        """
        Load a Minecraft level of any format from the given filename.

        If you try to create an existing world, IOError will be raised.

        :type filename: str or unknown or unicode
        :type create: bool
        :type readonly: bool
        :type adapter: unknown or SchematicFileAdapter
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

        # maps (cx, cz, dimName) tuples to WorldEditorChunkData
        self._loadedChunkData = {}

        self._allChunks = None

        self.recentDirtyChunks = collections.defaultdict(set)
        self.recentDirtyFiles = set()

        self.recentDirtySections = collections.defaultdict(set)

        self.dimensions = {}

        self.currentRevision = 0

    def __repr__(self):
        return "WorldEditor(adapter=%r)" % self.adapter

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
        """
        Record all changes since the last call to beginUndo into the adapter's current revision. The revision is closed
        and beginUndo must be called to open the next revision.

        :param revisionInfo: May be supplied to record metadata for this undo
        :type revisionInfo: object | None
        :return:
        :rtype:
        """
        self.adapter.setRevisionInfo(revisionInfo)
        self.syncToDisk()
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
        self.syncToDisk()

        changes = self.adapter.selectRevision(index)
        self.currentRevision = index
        if changes is None:
            return
        log.info("Going to revision %d", index)
        log.debug("Changes: %s", changes)
        for dimName, chunkPositions in changes.chunks.iteritems():
            self.recentDirtyChunks[dimName].update(chunkPositions)
            for cx, cz in chunkPositions:
                self._loadedChunkData.pop((cx, cz, dimName), None)
                self._loadedChunks.pop((cx, cz, dimName), None)

        self.recentDirtyFiles.update(changes.files)
        # xxx unload players, metadata!!

    # --- Save ---

    def syncToDisk(self):
        """
        Write all loaded chunks, player files, etc to disk.

        :return:
        :rtype:
        """
        for player in self.playerCache.itervalues():
            player.save()

        dirtyChunkCount = 0
        for chunk in self._loadedChunkData.itervalues():
            if chunk.dirty:
                dirtyChunkCount += 1
                self.adapter.writeChunk(chunk)
                chunk.dirty = False
        log.info(u"Saved {0} chunks".format(dirtyChunkCount))

    def saveChanges(self):
        if self.readonly:
            raise IOError("World is opened read only.")

        self.syncToDisk()
        self.playerCache.clear()
        self.adapter.saveChanges()

    def close(self):
        """
        Unload all chunks and close all open filehandles.
        """
        self.adapter.close()

        self._allChunks = None
        self._loadedChunks.clear()
        self._loadedChunkData.clear()

    # --- Resource limits ---

    loadedChunkLimit = 400

    # --- Instance variables  ---

    blocktypes = pc_blocktypes

    # --- World limits ---

    @property
    def maxHeight(self):
        return self.adapter.maxHeight

    # --- World info ---

    @property
    def displayName(self):
        return displayName(self.filename)

    # --- Chunk I/O ---

    def preloadChunkPositions(self):
        log.info(u"Scanning for regions in %s...", self.adapter.filename)
        self._allChunks = collections.defaultdict(set)
        for dimName in self.adapter.listDimensions():
            start = time.time()
            chunkPositions = set(self.adapter.chunkPositions(dimName))
            chunkPositions.update((cx, cz) for (cx, cz, d) in self._loadedChunkData if d == dimName)
            log.info("Dim %s: Found %d chunks in %0.2f seconds.",
                     dimName,
                     len(chunkPositions),
                     time.time() -
                     start)
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

    def _getChunkData(self, cx, cz, dimName):
        chunkData = self._loadedChunkData.get((cx, cz, dimName))
        if chunkData is not None:
            log.debug("_getChunkData: Chunk %s is in _loadedChunkData", (cx, cz))
            return chunkData

        chunkData = self.adapter.readChunk(cx, cz, dimName)
        self._storeLoadedChunkData(chunkData)

        return chunkData

    def _storeLoadedChunkData(self, chunkData):
        if len(self._loadedChunkData) > self.loadedChunkLimit:
            # Try to find a chunk to unload. The chunk must not be in _loadedChunks, which contains only chunks that
            # are in use by another object. If the chunk is dirty, save it to the temporary folder.

            for (ocx, ocz, dimName), oldChunkData in self._loadedChunkData.items():
                if (ocx, ocz, dimName) not in self._loadedChunks:  # and (ocx, ocz) not in self._recentLoadedChunks:
                    if oldChunkData.dirty and not self.readonly:
                        self.adapter.writeChunk(oldChunkData)

                    del self._loadedChunkData[ocx, ocz, dimName]
                    break

        self._loadedChunkData[chunkData.cx, chunkData.cz, chunkData.dimName] = chunkData

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
        chunkData = self._getChunkData(cx, cz, dimName)
        chunk = WorldEditorChunk(chunkData, self)

        duration = time.time() - startTime
        if duration > 1:
            log.warn("Chunk %s took %0.2f seconds to load! entities=%s tileentities=%s tileticks=%s",
                     (cx, cz), duration, len(chunk.Entities), len(chunk.TileEntities),
                     len(chunk.rootTag.get("TileTicks", ())))

        self._loadedChunks[cx, cz, dimName] = chunk
        return chunk

    # --- Chunk dirty bit ---

    def listDirtyChunks(self):
        for cPos, chunkData in self._loadedChunkData.iteritems():
            if chunkData.dirty:
                yield cPos

    def chunkBecameDirty(self, chunk):
        self.recentDirtyChunks[chunk.dimName].add((chunk.cx, chunk.cz))

    def getRecentDirtyChunks(self, dimName):
        return self.recentDirtyChunks.pop(dimName, set())

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
        if (cx, cz, dimName) in self._loadedChunkData:
            return True

        return self.adapter.containsChunk(cx, cz, dimName)

    def containsPoint(self, x, y, z, dimName):
        if y < 0 or y > 127:
            return False
        return self.containsChunk(x >> 4, z >> 4, dimName)

    def createChunk(self, cx, cz, dimName):
        if self.containsChunk(cx, cz, dimName):
            raise ValueError("%r:Chunk %s already present in %s!".format(self, (cx, cz), dimName))
        if self._allChunks is not None:
            self._allChunks[dimName].add((cx, cz))

        chunk = self.adapter.createChunk(cx, cz, dimName)
        self._storeLoadedChunkData(chunk)

    def deleteChunk(self, cx, cz, dimName):
        self.adapter.deleteChunk(cx, cz, dimName)
        if self._allChunks is not None:
            self._allChunks[dimName].discard((cx, cz))

    # --- Player and spawn manipulation ---

    def worldSpawnPosition(self):
        """
        Return the world's default spawn position.
        """
        return self.adapter.metadata.worldSpawnPosition()

    def setWorldSpawnPosition(self, pos):
        """
        Change the world's default spawn position.

        :param pos: (x, y, z) coordinates
        """
        self.adapter.metadata.setWorldSpawnPosition(pos)

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

    def getRecentDirtyChunks(self):
        return self.worldEditor.getRecentDirtyChunks(self.dimName)

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

    def addEntity(self, ref):
        x, y, z = ref.Position
        cx, cz = chunk_pos(x, z)
        chunk = self.getChunk(cx, cz, create=True)
        chunk.Entities.append(ref.copy())

    def addTileEntity(self, ref):
        x, y, z = ref.Position
        cx, cz = chunk_pos(x, z)
        chunk = self.getChunk(cx, cz, create=True)
        existing = [old for old in chunk.TileEntities
                    if old.Position == (x, y, z)]
        for e in existing:
            chunk.TileEntities.remove(e)

        chunk.TileEntities.append(ref.copy())

    # --- Import/Export ---

    def copyBlocksIter(self, sourceLevel, sourceSelection, destinationPoint, blocksToCopy=None, entities=True, create=False, biomes=False):
        return copyBlocksIter(self, sourceLevel, sourceSelection, destinationPoint, blocksToCopy, entities, create,
                           biomes)


    def copyBlocks(self, sourceLevel, sourceSelection, destinationPoint, blocksToCopy=None, entities=True, create=False, biomes=False):
        return exhaust(self.copyBlocksIter(sourceLevel, sourceSelection, destinationPoint, blocksToCopy,
                                           entities, create, biomes))

    def exportSchematicIter(self, selection):
        schematicAdapter = SchematicFileAdapter(shape=selection.size, blocktypes=self.blocktypes)
        schematic = WorldEditor(adapter=schematicAdapter)

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

    # --- Blocks by single coordinate ---

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
                array = sec.Data
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
                         updateLights)
