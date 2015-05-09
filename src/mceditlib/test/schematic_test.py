import itertools
import os
import unittest
from mceditlib.worldeditor import WorldEditor
from templevel import TempLevel, mktemp
from mceditlib.schematic import SchematicFileAdapter, createSchematic
from mceditlib.selection import BoundingBox

__author__ = 'Rio'

class TestSchematics(unittest.TestCase):
    def setUp(self):
        # self.alphaLevel = TempLevel("Dojo_64_64_128.dat")
        self.schematicLevel = TempLevel("Floating.schematic")
        self.anvilLevel = TempLevel("AnvilWorld")

    def testCreate(self):
        # log.info("Schematic from indev")

        size = (64, 64, 64)
        temp = mktemp("testcreate.schematic")
        editor = createSchematic(shape=size, blocktypes='Classic')
        editor.filename = temp
        dim = editor.getDimension()
        level = self.schematicLevel

        dim.importSchematic(level, (0, 0, 0))
        assert((schematic.Blocks[0:64, 0:64, 0:64] == level.adapter.Blocks[0:64, 0:64, 0:64]).all())

        dim.importSchematic(level, (-32, -32, -32))
        assert((schematic.Blocks[0:32, 0:32, 0:32] == level.adapter.Blocks[32:64, 32:64, 32:64]).all())

        schematic.saveChanges()

        schem = WorldEditor("test_files/Station.schematic")
        tempEditor = createSchematic(shape=(1, 1, 3))
        tempDim = tempEditor.getDimension()
        tempDim.copyBlocks(schem, BoundingBox((0, 0, 0), (1, 1, 3)), (0, 0, 0))

        level = self.anvilLevel
        for cx, cz in itertools.product(xrange(0, 4), xrange(0, 4)):
            try:
                level.createChunk(cx, cz)
            except ValueError:
                pass
        dim.copyBlocks(level.getDimension(), BoundingBox((0, 0, 0), (64, 64, 64,)), (0, 0, 0))
        os.remove(temp)

    def testRotate(self):
        editor = self.anvilLevel
        dim = editor.getDimension()
        schematic = dim.exportSchematic(BoundingBox((0, 0, 0), (21, 11, 8)))

        schematic.rotateLeft()
        dim.importSchematic(schematic, dim.bounds.origin)

        schematic.flipEastWest()
        dim.importSchematic(schematic, dim.bounds.origin)

        schematic.flipVertical()
        dim.importSchematic(schematic, dim.bounds.origin)

    def testZipSchematic(self):
        level = self.anvilLevel

        x, y, z = level.bounds.origin
        x += level.bounds.size[0]/2 & ~15
        z += level.bounds.size[2]/2 & ~15

        box = BoundingBox((x, y, z), (64, 64, 64,))
        zs = level.extractZipSchematic(box)
        assert(box.chunkCount == zs.chunkCount)
        zs.close()
        os.remove(zs.filename)

    def testINVEditChests(self):
        invFile = WorldEditor("schematics/Chests/TinkerersBox.inv")
        assert invFile.Blocks.any()
        assert not invFile.Data.any()
        assert len(invFile.Entities) == 0
        assert len(invFile.TileEntities) == 1
        # raise SystemExit

    def testCopyOffsets(self):
        editor = TempLevel("AnvilWorld")
        dimension = editor.getDimension()
        schematic = createSchematic((13, 8, 5))
        schematicDim = schematic.getDimension()

        x, y, z = dimension.bounds.origin + [p/2 for p in dimension.bounds.size]
        for dx in range(16):
            for dz in range(16):
                dimension.copyBlocks(schematicDim, schematicDim.bounds, (x+dx, y, z+dz), biomes=True)
