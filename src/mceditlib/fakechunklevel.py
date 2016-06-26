"""
Classes used in implementing adapters for worlds physically stored as a single array.
Slices of this array are presented as virtual chunks.
"""

from __future__ import absolute_import
from collections import namedtuple
import itertools
from logging import getLogger

from numpy import zeros, zeros_like
import numpy

from mceditlib.selection import BoundingBox
from mceditlib import nbt
from mceditlib.exceptions import ChunkNotPresent


log = getLogger(__name__)

GetBlocksResult = namedtuple("GetBlocksResult", ["Blocks", "Data", "BlockLight", "SkyLight", "Biomes"])


class FakeSection(object):
    pass


class FakeChunkData(object):
    dirty = False

    dimension = NotImplemented  #: The parent dimension that this chunk belongs to
    cx = cz = NotImplemented  #: This chunk's position as a tuple (cx, cz)

    Width = Length = 16

    dimName = ""
    HeightMap = None
    Biomes = None

    def sectionPositions(self):
        return self.dimension.bounds.sectionPositions(self.cx, self.cz)

    @property
    def Height(self):
        return self.dimension.Height

    @property
    def bounds(self):
        return BoundingBox((self.cx << 4, 0, self.cz << 4), self.size)

    @property
    def size(self):
        return self.Width, self.Height, self.Length

    def sectionPositions(self):
        return range(0, (self.Height + 15) >> 4)

    def chunkChanged(self, needsLighting=True):
        """
        You are required to call this function after directly modifying any of a chunk's
        arrays or its rootTag. Alternately, just set `chunk.dirty = True`

        needsLighting is deprecated; Use the updateLights= argument
        of setBlocks and other editing functions, or call updateLightsByCoord(level, x, y, z) to
        explicitly update lights yourself.

        """
        self.dirty = True

    @property
    def blocktypes(self):
        return self.dimension.blocktypes

    def getSection(self, cy, create=False):
        y = cy << 4
        if y < self.bounds.miny or y >= self.bounds.maxy:
            return None

        section = FakeSection()
        section.chunk = self
        slices = numpy.s_[:, :, cy << 4:(cy + 1 << 4)]
        if hasattr(self, 'Blocks'):
            section.Blocks = self.Blocks[slices].swapaxes(0, 2)
        else:
            raise NotImplementedError("ChunkBase.getSection is only implemented for chunks providing a Blocks array")
        if hasattr(self, 'Data'):
            section.Data = self.Data[slices].swapaxes(0, 2)
        if hasattr(self, 'BlockLight'):
            section.BlockLight = self.BlockLight[slices].swapaxes(0, 2)
        if hasattr(self, 'SkyLight'):
            section.SkyLight = self.SkyLight[slices].swapaxes(0, 2)

        section.Y = cy

        return section


class FakeChunkedLevelAdapter(object):
    """
    FakeChunkedLevelAdapter is an abstract class for implementing fixed size, non-chunked storage formats.
    Classic, Indev, and Schematic formats inherit from this class.  FakeChunkedLevelAdapter has dummy functions for
    pretending to have Players, Entities and TileEntities. If Entities and TileEntities already present, provides
    a working `getEntities` and `getTileEntities`.

    FakeChunkedLevelAdapter subclasses must have Width, Length, and Height attributes.
    Subclasses must also have Blocks, and optionally Data and BlockLight.

    FakeChunkedLevelAdapter implements IWorld and ISectionWorld.

    Attributes
    ----------

    Height : int
    Length : int
    Width  : int
    Blocks : ndarray of any shape, indexed [x, z, y]
    blocktypes : BlockTypeSet

    Entities     : list or TAG_List
    TileEntities : list or TAG_List
    Data         : ndarray, same shape and indexes as Blocks
    BlockLight   : ndarray, same shape and indexes as Blocks
    SkyLight     : ndarray, same shape and indexes as Blocks
    Biomes       : ndarray, same x and z sizes as Blocks, indexed [x, z]

    """

    Blocks = blocktypes = NotImplemented
    Width = Length = Height = NotImplemented

    hasLights = False

    ChunkDataClass = FakeChunkData

    @property
    def size(self):
        return self.Width, self.Height, self.Length

    @property
    def bounds(self):
        return BoundingBox((0, 0, 0), (self.Width, self.Height, self.Length))

    def readChunk(self, cx, cz, dimName, create=False):
        """
        Creates a FakeChunkData object representing the chunk at the given
        position. Subclasses may choose to override
        fakeBlocksForChunk and fakeDataForChunk to provide block and blockdata arrays.
        They may instead override getChunk and return a ChunkBase subclass.

        By default, returns a chunk whose ``Blocks`` is made from slices of self.Blocks (and
        ``Data`` from self.Data if present)
        """
        if not self.bounds.containsChunk(cx, cz):
            raise ChunkNotPresent((cx, cz))
        chunk = self.ChunkDataClass()
        chunk.dimension = self
        chunk.cx = cx
        chunk.cz = cz
        chunk.dimName = dimName

        chunk.Blocks = self.fakeBlocksForChunk(cx, cz)

        chunk.Data = self.fakeDataForChunk(cx, cz)

        whiteLight = zeros_like(chunk.Blocks)
        whiteLight[:] = 15

        chunk.BlockLight = whiteLight
        chunk.SkyLight = whiteLight

        chunk.Entities, chunk.TileEntities = self.fakeEntitiesForChunk(cx, cz)

        chunk.rootTag = nbt.TAG_Compound()

        return chunk

    def writeChunk(self, chunk):
        """
        Chunks are references to internal Block arrays (xxx someday transform schematic into internal chunked format
        and transform it back before write)
        :param chunk:
        :type chunk:
        :return:
        :rtype:
        """

    def chunkCount(self, _):
        """Computes an artificial chunk count using self.Width and self.Length."""
        return (self.Width + 15 >> 4) * (self.Length + 15 >> 4)

    def chunkPositions(self, _):
        """Returns an artificial list of chunk positions using `self.Width` and `self.Length`"""
        return itertools.product(xrange(0, self.Width + 15 >> 4), xrange(0, self.Length + 15 >> 4))

    def containsChunk(self, cx, cz, _):
        """Returns True if the position is within `self.bounds`."""
        bounds = self.bounds
        return ((bounds.mincx <= cx < bounds.maxcx) and
                (bounds.mincz <= cz < bounds.maxcz))

    def fakeBlocksForChunk(self, cx, cz):
        """
        Return a Blocks array for a fake chunk at the given position.

        By default, returns a slice of self.Blocks.

        :rtype: ndarray(shape=(16, 16, Height))
        """
        cxOff = cx << 4
        czOff = cz << 4
        return self.Blocks[cxOff:cxOff + 16, czOff:czOff + 16, :]

    def fakeDataForChunk(self, cx, cz):
        """
        Return a Data array for a fake chunk at the given position.

        By default, returns a slice of self.Data if it is present, otherwise returns an array of zeros.

        :rtype: ndarray(shape=(16, 16, Height))
        """
        cxOff = cx << 4
        czOff = cz << 4

        if hasattr(self, "Data"):
            return self.Data[cxOff:cxOff + 16, czOff:czOff + 16, :]
        else:
            return zeros(shape=(16, 16, 1 + (self.Height | 0xf)), dtype='uint8')

    def fakeEntitiesForChunk(self, cx, cz):
        """
        Return the Entities and TileEntities for a fake chunk at the given position.

        By default, returns empty lists.

        :rtype: (list, list)
        """
        return [], []

    def addEntity(self, ref):
        if hasattr(self, 'Entities'):
            self.Entities.append(ref.copy())

    def addTileEntity(self, ref):
        if hasattr(self, 'TileEntities'):
            self.TileEntities.append(ref.copy())

    # --- Block accessors ---

    def getBlockID(self, x, y, z):
        if (x, y, z) not in self.bounds:
            return 0
        return self.Blocks[x, z, y]

    def setBlockID(self, x, y, z, blockID):
        if (x, y, z) in self.bounds:
            self.Blocks[x, z, y] = blockID

    def getBlockData(self, x, y, z):
        if (x, y, z) in self.bounds and hasattr(self, 'Data'):
            return self.Data[x, z, y]
        return 0

    def setBlockData(self, x, y, z, data):
        if (x, y, z) in self.bounds and hasattr(self, 'Data'):
            self.Data[x, z, y] = data

    def setBlocks(self, x, y, z,
                  Blocks=None,
                  Data=None,
                  BlockLight=None,
                  SkyLight=None,
                  Biomes=None,
                  updateLights=True,
    ):

        # Note: Single-file blocks are ordered x, z, y and biomes ordered x, z for compatibility? purposes?

        # Eliminate coordinates outside this level's bounds.
        mask = x >= 0
        mask &= x < self.Width
        mask &= y >= 0
        mask &= y < self.Height
        mask &= z >= 0
        mask &= z < self.Length

        if hasattr(x, '__getitem__'):
            x = x[mask]
        if hasattr(y, '__getitem__'):
            y = y[mask]
        if hasattr(z, '__getitem__'):
            z = z[mask]

        if Blocks is not None:
            if hasattr(Blocks, '__getitem__'):
                Blocks = Blocks[mask]
            self.Blocks[x, z, y] = Blocks

        if Data is not None and hasattr(self, 'Data'):
            if hasattr(Data, '__getitem__'):
                Data = Data[mask]
            self.Data[x, z, y] = Data

        if BlockLight is not None and hasattr(self, 'BlockLight'):
            if hasattr(BlockLight, '__getitem__'):
                BlockLight = BlockLight[mask]
            self.BlockLight[x, z, y] = BlockLight

        if SkyLight is not None and hasattr(self, 'SkyLight'):
            if hasattr(SkyLight, '__getitem__'):
                SkyLight = SkyLight[mask]
            self.SkyLight[x, z, y] = SkyLight

        if Biomes is not None and hasattr(self, 'Biomes'):
            if hasattr(Biomes, '__getitem__'):
                Biomes = Biomes[mask]
            self.Biomes[x, z] = Biomes

    def getBlocks(self, x, y, z,
                  return_Blocks=True,
                  return_Data=False,
                  return_BlockLight=False,
                  return_SkyLight=False,
                  return_Biomes=False):

        Blocks = Data = BlockLight = SkyLight = Biomes = None

        # Eliminate coordinates outside this level's bounds.
        x, y, z = numpy.atleast_1d(x, y, z)
        shapes = [a.shape for a in x, y, z]
        max_shape = max(shapes)
        if not all([a.shape in ((1,), max_shape) for a in x, y, z]):
            raise ValueError("All inputs to getBlocks must be the same shape or be a 1-sized array")

        mask = numpy.ones(shape=max_shape, dtype='bool')

        if x.shape == max_shape:
            mask &= x >= 0
            mask &= x < self.Width
        if y.shape == max_shape:
            mask &= y >= 0
            mask &= y < self.Height
        if z.shape == max_shape:
            mask &= z >= 0
            mask &= z < self.Length

        broadcast_shape = numpy.broadcast(x, z, y).shape

        if x.shape == max_shape:
            x = x[mask]
        if y.shape == max_shape:
            y = y[mask]
        if z.shape == max_shape:
            z = z[mask]

        if return_Blocks:
            Blocks = numpy.zeros(broadcast_shape, self.Blocks.dtype)
            Blocks[mask] = self.Blocks[x, z, y]

        if return_Data and hasattr(self, 'Data'):
            Data = numpy.zeros(broadcast_shape, self.Data.dtype)
            Data[mask] = self.Data[x, z, y]

        if return_BlockLight and hasattr(self, 'BlockLight'):
            BlockLight = numpy.zeros(broadcast_shape, self.BlockLight.dtype)
            BlockLight[mask] = self.BlockLight[x, z, y]

        if return_SkyLight and hasattr(self, 'SkyLight'):
            SkyLight = numpy.zeros(broadcast_shape, self.SkyLight.dtype)
            SkyLight[mask] = self.SkyLight[x, z, y]

        if return_Biomes and hasattr(self, 'Biomes'):
            Biomes = numpy.zeros(broadcast_shape, self.Biomes.dtype)
            Biomes[mask] = self.Biomes[x, z]

        return GetBlocksResult(Blocks, Data, BlockLight, SkyLight, Biomes)

    def listDimensions(self):
        return [""]

    def close(self):
        pass



