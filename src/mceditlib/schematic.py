'''
Created on Jul 22, 2011

@author: Rio
'''
from __future__ import absolute_import
from collections import defaultdict
import os

from logging import getLogger
import itertools

from numpy import swapaxes, uint8, zeros
import numpy

from mceditlib.anvil.adapter import VERSION_1_7, VERSION_1_8
from mceditlib.anvil.entities import PCEntityRef, PCTileEntityRef, \
    ItemStackRef, ItemRef
from mceditlib.exceptions import PlayerNotFound, LevelFormatError
from mceditlib.selection import BoundingBox
from mceditlib.fakechunklevel import FakeChunkedLevelAdapter, FakeChunkData
from mceditlib.blocktypes import BlockTypeSet, PCBlockTypeSet
from mceditlib import nbt

log = getLogger(__name__)


blocktypeClassesByName = {"Alpha": PCBlockTypeSet}


def createSchematic(shape, blocktypes='Alpha'):
    """
    Create a new .schematic of the given shape and blocktypes and return a WorldEditor.

    Parameters
    ----------
    shape : tuple of int
    blocktypes : BlockTypeSet or str

    Returns
    -------
    WorldEditor
    """
    from mceditlib.worldeditor import WorldEditor

    adapter = SchematicFileAdapter(shape=shape, blocktypes=blocktypes)
    editor = WorldEditor(adapter=adapter)
    return editor


def blockIDMapping(blocktypes):
    mapping = nbt.TAG_Compound()
    for name, ID in blocktypes.IDsByName.iteritems():
        mapping[str(ID)] = nbt.TAG_String(name)

    return mapping


def itemIDMapping(blocktypes):
    mapping = nbt.TAG_Compound()
    for name, ID in blocktypes.itemTypes.IDsByInternalName.iteritems():
        mapping[str(ID)] = nbt.TAG_String(name)
    return mapping


class SchematicChunkData(FakeChunkData):
    def addEntity(self, entity):
        self.dimension.addEntity(entity)

    def addTileEntity(self, tileEntity):
        self.dimension.addTileEntity(tileEntity)


class SchematicFileAdapter(FakeChunkedLevelAdapter):
    """

    """
    # XXX use abstract entity ref or select correct ref for contained level format

    ChunkDataClass = SchematicChunkData

    def __init__(self, shape=None, filename=None, blocktypes='Alpha', readonly=False, resume=False):
        """
        Creates an object which stores a section of a Minecraft world as an
        NBT structure. The order of the coordinates for the block arrays in
        the file is y,z,x. This is the same order used in Minecraft 1.4's
        chunk sections.

        Parameters
        ----------
        shape: tuple of int
            The shape of the schematic as (x, y, z)
        filename: basestring
            Path to a file to load a saved schematic from.
        blocktypes: basestring or BlockTypeSet
            The name of a builtin blocktypes set (one of
            "Classic", "Alpha", "Pocket") to indicate allowable blocks. The default
            is Alpha. An instance of BlockTypeSet may be passed instead.

        Returns
        ----------
        SchematicFileAdapter

        """
        self.EntityRef = PCEntityRef
        self.TileEntityRef = PCTileEntityRef

        if filename is None and shape is None:
            raise ValueError("shape or filename required to create %s" % self.__class__.__name__)

        if filename:
            self.filename = filename
            if os.path.exists(filename):
                rootTag = nbt.load(filename)
            else:
                rootTag = None
        else:
            self.filename = None
            rootTag = None

        if blocktypes in blocktypeClassesByName:
            self.blocktypes = blocktypeClassesByName[blocktypes]()
        else:
            if not isinstance(blocktypes, BlockTypeSet):
                raise ValueError("%s is not a recognized BlockTypeSet", blocktypes)
            self.blocktypes = blocktypes

        if rootTag:
            self.rootTag = rootTag
            if "Materials" in rootTag:
                self.blocktypes = blocktypeClassesByName[self.Materials]()
            else:
                rootTag["Materials"] = nbt.TAG_String(self.blocktypes.name)

            w = self.rootTag["Width"].value
            l = self.rootTag["Length"].value
            h = self.rootTag["Height"].value

            assert self.rootTag["Blocks"].value.size == w * l * h
            self._Blocks = self.rootTag["Blocks"].value.astype('uint16').reshape(h, l, w) # _Blocks is y, z, x

            del self.rootTag["Blocks"]
            if "AddBlocks" in self.rootTag:
                # Use WorldEdit's "AddBlocks" array to load and store the 4 high bits of a block ID.
                # Unlike Minecraft's NibbleArrays, this array stores the first block's bits in the
                # 4 high bits of the first byte.

                size = (h * l * w)

                # If odd, add one to the size to make sure the adjacent slices line up.
                add = numpy.empty(size + (size & 1), 'uint16')

                # Fill the even bytes with data
                add[::2] = self.rootTag["AddBlocks"].value

                # Copy the low 4 bits to the odd bytes
                add[1::2] = add[::2] & 0xf

                # Shift the even bytes down
                add[::2] >>= 4

                # Shift every byte up before merging it with Blocks
                add <<= 8
                self._Blocks |= add[:size].reshape(h, l, w)
                del self.rootTag["AddBlocks"]

            self.rootTag["Data"].value = self.rootTag["Data"].value.reshape(h, l, w)

            if "Biomes" in self.rootTag:
                self.rootTag["Biomes"].value.shape = (l, w)

            # If BlockIDs is present, it contains an ID->internalName mapping
            # from the source level's FML tag.

            if "BlockIDs" in self.rootTag:
                self.blocktypes.addBlockIDsFromSchematicTag(self.rootTag["BlockIDs"])

            # If itemStackVersion is present, it was exported from MCEdit 2.0.
            # Its value is either 17 or 18, the values of the version constants.
            # ItemIDs will also be present.

            # If itemStackVersion is not present, this schematic was exported from
            # WorldEdit or MCEdit 1.0. The itemStackVersion cannot be determined
            # without searching the entities for an itemStack and checking
            # the type of its `id` tag. If no itemStacks are found, the
            # version defaults to 1.8 which does not need an ItemIDs tag.

            if "itemStackVersion" in self.rootTag:
                itemStackVersion = self.rootTag["itemStackVersion"].value
                if itemStackVersion not in (VERSION_1_7, VERSION_1_8):
                    raise LevelFormatError("Unknown item stack version %d" % itemStackVersion)
                if itemStackVersion == VERSION_1_7:
                    itemIDs = self.rootTag.get("ItemIDs")
                    if itemIDs is not None:
                        self.blocktypes.addItemIDsFromSchematicTag(itemIDs)

                self.blocktypes.itemStackVersion = itemStackVersion
            else:
                self.blocktypes.itemStackVersion = self.getItemStackVersionFromEntities()

        else:
            rootTag = nbt.TAG_Compound(name="Schematic")
            rootTag["Height"] = nbt.TAG_Short(shape[1])
            rootTag["Length"] = nbt.TAG_Short(shape[2])
            rootTag["Width"] = nbt.TAG_Short(shape[0])

            rootTag["Entities"] = nbt.TAG_List()
            rootTag["TileEntities"] = nbt.TAG_List()
            rootTag["Materials"] = nbt.TAG_String(self.blocktypes.name)
            rootTag["itemStackVersion"] = nbt.TAG_Byte(self.blocktypes.itemStackVersion)


            self._Blocks = zeros((shape[1], shape[2], shape[0]), 'uint16')
            rootTag["Data"] = nbt.TAG_Byte_Array(zeros((shape[1], shape[2], shape[0]), uint8))

            rootTag["Biomes"] = nbt.TAG_Byte_Array(zeros((shape[2], shape[0]), uint8))

            self.rootTag = rootTag

            self.rootTag["BlockIDs"] = blockIDMapping(self.blocktypes)
            itemMapping = itemIDMapping(self.blocktypes)
            if itemMapping is not None:
                self.rootTag["ItemIDs"] = itemMapping  # Only present for Forge 1.7

        # Expand blocks and data to chunk edges
        h16 = (self.Height + 15) & ~0xf
        l16 = (self.Length + 15) & ~0xf
        w16 = (self.Width + 15) & ~0xf

        blocks = self._Blocks
        self._Blocks = numpy.zeros((h16, l16, w16), blocks.dtype)
        self._Blocks[:blocks.shape[0], :blocks.shape[1], :blocks.shape[2]] = blocks

        data = self.rootTag["Data"].value
        self.rootTag["Data"].value = numpy.zeros((h16, l16, w16), data.dtype)
        self.rootTag["Data"].value[:data.shape[0], :data.shape[1], :data.shape[2]] = data

        self.rootTag["Data"].value &= 0xF  # discard high bits

        self.entitiesByChunk = defaultdict(list)
        for tag in self.rootTag["Entities"]:
            ref = self.EntityRef(tag)
            pos = ref.Position
            cx, cy, cz = pos.chunkPos()
            self.entitiesByChunk[cx, cz].append(tag)

        self.tileEntitiesByChunk = defaultdict(list)
        for tag in self.rootTag["TileEntities"]:
            ref = self.TileEntityRef(tag)
            pos = ref.Position
            cx, cy, cz = pos.chunkPos()
            self.tileEntitiesByChunk[cx, cz].append(tag)

    def getItemStackVersionFromEntities(self):
        for listTag in self.rootTag["Entities"], self.rootTag["TileEntities"]:
            for name, tag, path in nbt.walk(listTag):
                if ItemRef.tagIsItem(tag):
                    if tag["id"].tagID == nbt.ID_STRING:
                        return VERSION_1_8
                    if tag["id"].tagID == nbt.ID_SHORT:
                        return VERSION_1_7

        # No itemstacks - use version 1.8 since ItemIDs won't need to
        # be added to the root tag.
        return VERSION_1_8

    def fakeEntitiesForChunk(self, cx, cz):
        return self.entitiesByChunk[cx, cz], self.tileEntitiesByChunk[cx, cz]

    def syncToDisk(self):
        """
        Ugh... reimplement this class in a way that uses a RevisionHistory?
        """
        pass

    def saveChanges(self):
        return self.saveToFile(self.filename)

    def saveChangesIter(self):
        self.saveChanges()
        yield 100, 100, "Done"

    def saveToFile(self, filename):
        """ save to file named filename."""

        self.Materials = self.blocktypes.name

        self.rootTag["Blocks"] = nbt.TAG_Byte_Array(self._Blocks[:self.Height, :self.Length, :self.Width].astype('uint8'))
        self.rootTag["Data"].value = self.rootTag["Data"].value[:self.Height, :self.Length, :self.Width]

        add = self._Blocks >> 8
        if add.any():
            add = add[:self.Height, :self.Length, :self.Width]
            # WorldEdit AddBlocks compatibility.
            # The first 4-bit value is stored in the high bits of the first byte.

            # Increase odd size by one to align slices.
            packed_add = zeros(add.size + (add.size & 1), 'uint8')
            packed_add[:add.size] = add.ravel()

            # Shift even bytes to the left
            packed_add[::2] <<= 4

            # Merge odd bytes into even bytes
            packed_add[::2] |= packed_add[1::2]

            # Save only the even bytes, now that they contain the odd bytes in their lower bits.
            packed_add = packed_add[0::2]
            self.rootTag["AddBlocks"] = nbt.TAG_Byte_Array(packed_add)

        entities = []
        for e in self.entitiesByChunk.values():
            entities.extend(e)

        tileEntities = []
        for te in self.tileEntitiesByChunk.values():
            tileEntities.extend(te)

        self.rootTag["Entities"] = nbt.TAG_List(entities)
        self.rootTag["TileEntities"] = nbt.TAG_List(tileEntities)

        log.info("Saving schematic %s with %d blocks, %d Entities and %d TileEntities",
                 os.path.basename(filename),
                 self.rootTag["Blocks"].value.size,
                 len(self.rootTag["Entities"]),
                 len(self.rootTag["TileEntities"]),
                 )

        with open(filename, 'wb') as chunkfh:
            self.rootTag.save(chunkfh)

        del self.rootTag["Blocks"]
        self.rootTag.pop("AddBlocks", None)

    def __repr__(self):
        return u"SchematicFileAdapter(shape={0}, blocktypes={2}, filename=\"{1}\")".format(self.size, self.filename or u"", self.Materials)

    minHeight = 0

    def getDimensionBounds(self, dimName=""):
        return BoundingBox((0, 0, 0), (self.Width, self.Height, self.Length))

    @property
    def maxHeight(self):
        return self.Height

    @property
    def Length(self):
        return self.rootTag["Length"].value

    @property
    def Width(self):
        return self.rootTag["Width"].value

    @property
    def Height(self):
        return self.rootTag["Height"].value

    @property
    def Blocks(self):
        return swapaxes(self._Blocks, 0, 2)

    @property
    def Data(self):
        return swapaxes(self.rootTag["Data"].value, 0, 2)

    @property
    def Materials(self):
        return self.rootTag["Materials"].value

    @Materials.setter
    def Materials(self, val):
        if "Materials" not in self.rootTag:
            self.rootTag["Materials"] = nbt.TAG_String()
        self.rootTag["Materials"].value = val

    @property
    def Biomes(self):
        return swapaxes(self.rootTag["Biomes"].value, 0, 1)

    def getPlayer(self, *a, **kw):
        raise PlayerNotFound

    def playerNames(self):
        return ()

    @classmethod
    def _isTagLevel(cls, rootTag):
        return "Schematic" == rootTag.name

    def _update_shape(self):
        rootTag = self.rootTag
        shape = self.Blocks.shape
        rootTag["Height"] = nbt.TAG_Short(shape[2])
        rootTag["Length"] = nbt.TAG_Short(shape[1])
        rootTag["Width"] = nbt.TAG_Short(shape[0])

    #
    # def rotateLeft(self):
    #     """
    #     Rotate the schematic to the left (when looking down).
    #
    #     Transform this schematic in place by rotating 90 degrees counterclockwise around the vertical axis.
    #
    #     By default, rotateLeft and the other transformation functions use swapaxes
    #     and reversed slice to modify the indexing properties of self.Blocks without copying any data.
    #     """
    #
    #     self._fakeEntities = None
    #     self._Blocks = swapaxes(self._Blocks, 1, 2)[:, ::-1, :]  # x=z; z=-x
    #     if "Biomes" in self.rootTag:
    #         self.rootTag["Biomes"].value = swapaxes(self.rootTag["Biomes"].value, 0, 1)[::-1, :]
    #
    #     self.rootTag["Data"].value   = swapaxes(self.rootTag["Data"].value, 1, 2)[:, ::-1, :]  # x=z; z=-x
    #     self._update_shape()
    #
    #     blockrotation.RotateLeft(self.Blocks, self.Data)
    #
    #     log.info(u"Relocating entities...")
    #     for entity in self.Entities:
    #         for p in "Pos", "Motion":
    #             if p == "Pos":
    #                 zBase = self.Length
    #             else:
    #                 zBase = 0.0
    #             newX = entity[p][2].value
    #             newZ = zBase - entity[p][0].value
    #
    #             entity[p][0].value = newX
    #             entity[p][2].value = newZ
    #         entity["Rotation"][0].value -= 90.0
    #         if entity["id"].value in ("Painting", "ItemFrame"):
    #             x, z = entity["TileX"].value, entity["TileZ"].value
    #             newx = z
    #             newz = self.Length - x - 1
    #
    #             entity["TileX"].value, entity["TileZ"].value = newx, newz
    #             entity["Dir"].value = (entity["Dir"].value + 1) % 4
    #
    #     for tileEntity in self.TileEntities:
    #         if not 'x' in tileEntity:
    #             continue
    #
    #         newX = tileEntity["z"].value
    #         newZ = self.Length - tileEntity["x"].value - 1
    #
    #         tileEntity["x"].value = newX
    #         tileEntity["z"].value = newZ
    #
    # def roll(self):
    #     """
    #     Roll the level toward sunrise.
    #
    #     Transform this level in place by rotating 90 degrees counterclockwise around the distal axis. Rolls cannot
    #     preserve all blocks as there are no wall-mounted versions of many floor-mounted objects. Unattached blocks
    #     will become items on the next play. Rolls also cannot preserve biome data.
    #     """
    #     self.rootTag.pop('Biomes', None)
    #     self._fakeEntities = None
    #
    #     self._Blocks = swapaxes(self._Blocks, 2, 0)[:, :, ::-1]  # x=y; y=-x
    #     self.rootTag["Data"].value = swapaxes(self.rootTag["Data"].value, 2, 0)[:, :, ::-1]
    #     self._update_shape()
    #
    # def flipVertical(self):
    #     """
    #     Flip the schematic top to bottom.
    #
    #     Transform this schematic in place by inverting it vertically. Vertical flips cannot preserve all blocks
    #     as there are no wall-mounted versions of many floor-mounted objects. Unattached blocks will become
    #     items on the next play.
    #     """
    #     self._fakeEntities = None
    #
    #     blockrotation.FlipVertical(self.Blocks, self.Data)
    #     self._Blocks = self._Blocks[::-1, :, :]  # y=-y
    #     self.rootTag["Data"].value = self.rootTag["Data"].value[::-1, :, :]
    #
    # def flipNorthSouth(self):
    #     """
    #     Flip the schematic north to south.
    #
    #     Transform this schematic in place by inverting it latitudinally.
    #     """
    #     if "Biomes" in self.rootTag:
    #         self.rootTag["Biomes"].value = self.rootTag["Biomes"].value[::-1, :]
    #
    #     self._fakeEntities = None
    #
    #     blockrotation.FlipNorthSouth(self.Blocks, self.Data)
    #     self._Blocks = self._Blocks[:, :, ::-1]  # x=-x
    #     self.rootTag["Data"].value = self.rootTag["Data"].value[:, :, ::-1]
    #
    #     northSouthPaintingMap = [0, 3, 2, 1]
    #
    #     log.info(u"N/S Flip: Relocating entities...")
    #     for entity in self.Entities:
    #
    #         entity["Pos"][0].value = self.Width - entity["Pos"][0].value
    #         entity["Motion"][0].value = -entity["Motion"][0].value
    #
    #         entity["Rotation"][0].value -= 180.0
    #
    #         if entity["id"].value in ("Painting", "ItemFrame"):
    #             entity["TileX"].value = self.Width - entity["TileX"].value
    #             entity["Dir"].value = northSouthPaintingMap[entity["Dir"].value]
    #
    #     for tileEntity in self.TileEntities:
    #         if not 'x' in tileEntity:
    #             continue
    #
    #         tileEntity["x"].value = self.Width - tileEntity["x"].value - 1
    #
    # def flipEastWest(self):
    #     """
    #     Flip the schematic east to west.
    #
    #     Transform this schematic in place by inverting it longitudinally.
    #     """
    #     if "Biomes" in self.rootTag:
    #         self.rootTag["Biomes"].value = self.rootTag["Biomes"].value[:, ::-1]
    #
    #     self._fakeEntities = None
    #
    #     blockrotation.FlipEastWest(self.Blocks, self.Data)
    #     self._Blocks = self._Blocks[:, ::-1, :]  # z=-z
    #     self.rootTag["Data"].value = self.rootTag["Data"].value[:, ::-1, :]
    #
    #     eastWestPaintingMap = [2, 1, 0, 3]
    #
    #     log.info(u"E/W Flip: Relocating entities...")
    #     for entity in self.Entities:
    #
    #         entity["Pos"][2].value = self.Length - entity["Pos"][2].value
    #         entity["Motion"][2].value = -entity["Motion"][2].value
    #
    #         entity["Rotation"][0].value -= 180.0
    #
    #         if entity["id"].value in ("Painting", "ItemFrame"):
    #             entity["TileZ"].value = self.Length - entity["TileZ"].value
    #             entity["Dir"].value = eastWestPaintingMap[entity["Dir"].value]
    #
    #     for tileEntity in self.TileEntities:
    #         tileEntity["z"].value = self.Length - tileEntity["z"].value - 1

    def setBlockData(self, x, y, z, newdata):
        if x < 0 or y < 0 or z < 0:
            return 0
        if x >= self.Width or y >= self.Height or z >= self.Length:
            return 0
        self.Data[x, z, y] = (newdata & 0xf)

    def getBlockData(self, x, y, z):
        if x < 0 or y < 0 or z < 0:
            return 0
        if x >= self.Width or y >= self.Height or z >= self.Length:
            return 0
        return self.Data[x, z, y]

    def readChunk(self, cx, cz, dimName, create=False):
        chunk = super(SchematicFileAdapter, self).readChunk(cx, cz, dimName, create)
        if "Biomes" in self.rootTag:
            x = cx << 4
            z = cz << 4
            chunk.Biomes = numpy.zeros((16, 16), dtype=numpy.uint8)
            srcBiomes = self.Biomes[x:x + 16, z:z + 16]
            chunk.Biomes[0:srcBiomes.shape[0], 0:srcBiomes.shape[1]] = srcBiomes
        return chunk
