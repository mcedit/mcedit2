'''
Created on Jul 22, 2011

@author: Rio
'''
from __future__ import absolute_import
import atexit
from contextlib import closing
import os
import shutil
import tempfile
import zipfile
from logging import getLogger

from numpy import array, swapaxes, uint8, zeros
import numpy

from mceditlib.anvil.adapter import AnvilWorldAdapter
from mceditlib.anvil.entities import PCEntityRef
from mceditlib.anvil.entities import PCTileEntityRef
from mceditlib.exceptions import PlayerNotFound
from mceditlib.selection import BoundingBox
from mceditlib.levelbase import FakeChunkedLevelAdapter
from mceditlib.blocktypes import pc_blocktypes, BlockTypeSet, blocktypes_named
from mceditlib import nbt

log = getLogger(__name__)

def createSchematic(shape, blocktypes='Alpha'):
    from mceditlib.worldeditor import WorldEditor

    adapter = SchematicFileAdapter(shape=shape, blocktypes=blocktypes)
    editor = WorldEditor(adapter=adapter)
    return editor

class SchematicFileAdapter(FakeChunkedLevelAdapter):
    """

    """
    blocktypes = pc_blocktypes

    # XXX use abstract entity ref or select correct ref for contained level format
    EntityRef = PCEntityRef
    TileEntityRef = PCTileEntityRef

    def __init__(self, shape=None, filename=None, blocktypes='Alpha', readonly=False, resume=False):
        """
        Creates an object which stores a section of a Minecraft world as an
        NBT structure. The order of the coordinates for the block arrays in
        the file is y,z,x. This is the same order used in Minecraft 1.4's
        chunk sections.

        :type shape: tuple
        :param shape: The shape of the schematic as (x, y, z)
        :type filename: basestring
        :param filename: Path to a file to load a saved schematic from.
        :type blocktypes: basestring or BlockTypeSet
        :param blocktypes: The name of a builtin blocktypes set (one of
            "Classic", "Alpha", "Pocket") to indicate allowable blocks. The default
            is Alpha. An instance of BlockTypeSet may be passed instead.
        :rtype: SchematicFileAdapter

        """
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

        if blocktypes in blocktypes_named:
            self.blocktypes = blocktypes_named[blocktypes]
        else:
            assert(isinstance(blocktypes, BlockTypeSet))
            self.blocktypes = blocktypes

        if rootTag:
            self.rootTag = rootTag
            if "Materials" in rootTag:
                self.blocktypes = blocktypes_named[self.Materials]
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

        else:
            rootTag = nbt.TAG_Compound(name="Schematic")
            rootTag["Height"] = nbt.TAG_Short(shape[1])
            rootTag["Length"] = nbt.TAG_Short(shape[2])
            rootTag["Width"] = nbt.TAG_Short(shape[0])

            rootTag["Entities"] = nbt.TAG_List()
            rootTag["TileEntities"] = nbt.TAG_List()
            rootTag["Materials"] = nbt.TAG_String(self.blocktypes.name)

            self._Blocks = zeros((shape[1], shape[2], shape[0]), 'uint16')
            rootTag["Data"] = nbt.TAG_Byte_Array(zeros((shape[1], shape[2], shape[0]), uint8))

            rootTag["Biomes"] = nbt.TAG_Byte_Array(zeros((shape[2], shape[0]), uint8))

            self.rootTag = rootTag

        #expand blocks and data to chunk edges
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

        self.Entities = [self.EntityRef(tag, None) for tag in self.rootTag["Entities"]]
        self.TileEntities = [self.EntityRef(tag, None) for tag in self.rootTag["TileEntities"]]


    def saveChanges(self):
        return self.saveToFile(self.filename)

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

        with open(filename, 'wb') as chunkfh:
            self.rootTag.save(chunkfh)

        del self.rootTag["Blocks"]
        self.rootTag.pop("AddBlocks", None)


    def __repr__(self):
        return u"SchematicFileAdapter(shape={0}, blocktypes={2}, filename=\"{1}\")".format(self.size, self.filename or u"", self.Materials)

    # these refer to the blocks array instead of the file's height because rotation swaps the axes
    # this will have an impact later on when editing schematics instead of just importing/exporting

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

    @classmethod
    def chestWithItemID(cls, itemID, count=64, damage=0):
        """ Creates a chest with a stack of 'itemID' in each slot.
        Optionally specify the count of items in each stack. Pass a negative
        value for damage to create unnaturally sturdy tools. """
        rootTag = nbt.TAG_Compound()
        invTag = nbt.TAG_List()
        rootTag["Inventory"] = invTag
        for slot in range(9, 36):
            itemTag = nbt.TAG_Compound()
            itemTag["Slot"] = nbt.TAG_Byte(slot)
            itemTag["Count"] = nbt.TAG_Byte(count)
            itemTag["id"] = nbt.TAG_Short(itemID)
            itemTag["Damage"] = nbt.TAG_Short(damage)
            invTag.append(itemTag)

        chest = INVEditChest(rootTag, "")

        return chest

    def readChunk(self, cx, cz, dimName, create=False):
        chunk = super(SchematicFileAdapter, self).readChunk(cx, cz, dimName, create)
        if "Biomes" in self.rootTag:
            x = cx << 4
            z = cz << 4
            chunk.Biomes = numpy.zeros((16, 16), dtype=numpy.uint8)
            srcBiomes = self.Biomes[x:x + 16, z:z + 16]
            chunk.Biomes[0:srcBiomes.shape[0], 0:srcBiomes.shape[1]] = srcBiomes
        return chunk


class INVEditChest(FakeChunkedLevelAdapter):
    Width = 1
    Height = 1
    Length = 1
    Blocks = None
    Data = array([[[0]]], 'uint8')
    Entities = nbt.TAG_List()
    Materials = pc_blocktypes

    @classmethod
    def _isTagLevel(cls, rootTag):
        return "Inventory" in rootTag

    def __init__(self, filename):
        self.filename = filename
        rootTag = nbt.load(filename)
        self.Blocks = array([[[pc_blocktypes.Chest.ID]]], 'uint8')
        for item in list(rootTag["Inventory"]):
            slot = item["Slot"].value
            if slot < 9 or slot >= 36:
                rootTag["Inventory"].remove(item)
            else:
                item["Slot"].value -= 9  # adjust for different chest slot indexes

        self.rootTag = rootTag

    @property
    def TileEntities(self):
        chestTag = nbt.TAG_Compound()
        chestTag["id"] = nbt.TAG_String("Chest")
        chestTag["Items"] = nbt.TAG_List(self.rootTag["Inventory"])
        chestTag["x"] = nbt.TAG_Int(0)
        chestTag["y"] = nbt.TAG_Int(0)
        chestTag["z"] = nbt.TAG_Int(0)

        return nbt.TAG_List([chestTag], name="TileEntities")


class ZipSchematic (AnvilWorldAdapter):
    def __init__(self, filename, create=False):
        raise NotImplementedError("No adapter for zipped world/schematic files yet!!!")
        self.zipfilename = filename

        tempdir = tempfile.mktemp("schematic")
        if create is False:
            zf = zipfile.ZipFile(filename)
            zf.extractall(tempdir)
            zf.close()

        super(ZipSchematic, self).__init__(tempdir, create)
        atexit.register(shutil.rmtree, self.worldFolder.filename, True)


        try:
            schematicDat = nbt.load(self.worldFolder.getFilePath("schematic.dat"))

            self.Width = schematicDat['Width'].value
            self.Height = schematicDat['Height'].value
            self.Length = schematicDat['Length'].value

            if "Materials" in schematicDat:
                self.blocktypes = blocktypes_named[schematicDat["Materials"].value]

        except Exception as e:
            print "Exception reading schematic.dat, skipping: {0!r}".format(e)
            self.Width = 0
            self.Length = 0

    def __del__(self):
        shutil.rmtree(self.worldFolder.filename, True)

    def saveChanges(self):
        self.saveToFile(self.zipfilename)

    def saveToFile(self, filename):
        super(ZipSchematic, self).saveChanges()
        schematicDat = nbt.TAG_Compound()
        schematicDat.name = "Mega Schematic"

        schematicDat["Width"] = nbt.TAG_Int(self.size[0])
        schematicDat["Height"] = nbt.TAG_Int(self.size[1])
        schematicDat["Length"] = nbt.TAG_Int(self.size[2])
        schematicDat["Materials"] = nbt.TAG_String(self.blocktypes.name)

        schematicDat.save(self.worldFolder.getFilePath("schematic.dat"))

        basedir = self.worldFolder.filename
        assert os.path.isdir(basedir)
        with closing(zipfile.ZipFile(filename, "w", zipfile.ZIP_STORED)) as z:
            for root, dirs, files in os.walk(basedir):
                # NOTE: ignore empty directories
                for fn in files:
                    absfn = os.path.join(root, fn)
                    zfn = absfn[len(basedir) + len(os.sep):]  # XXX: relative path
                    z.write(absfn, zfn)

    def getWorldBounds(self):
        return BoundingBox((0, 0, 0), (self.Width, self.Height, self.Length))

    @classmethod
    def canOpenFile(cls, filename):
        return zipfile.is_zipfile(filename)

