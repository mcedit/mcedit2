import itertools
import os
import pytest
from mceditlib.worldeditor import WorldEditor
from mceditlib.schematic import createSchematic
from mceditlib.selection import BoundingBox

__author__ = 'Rio'


@pytest.skip("Classic not implemented")
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

    level = self.pc_world
    for cx, cz in itertools.product(xrange(0, 4), xrange(0, 4)):
        try:
            level.createChunk(cx, cz)
        except ValueError:
            pass
    dim.copyBlocks(level.getDimension(), BoundingBox((0, 0, 0), (64, 64, 64,)), (0, 0, 0))
    os.remove(temp)


@pytest.skip("Rotate not implemented")
def testRotate(pc_world):
    dim = pc_world.getDimension()
    schematic = dim.exportSchematic(BoundingBox((0, 0, 0), (21, 11, 8)))

    schematic.rotateLeft()
    dim.importSchematic(schematic, dim.bounds.origin)

    schematic.flipEastWest()
    dim.importSchematic(schematic, dim.bounds.origin)

    schematic.flipVertical()
    dim.importSchematic(schematic, dim.bounds.origin)


def testZipSchematic(pc_world):
    level = pc_world.getDimension()

    x, y, z = level.bounds.origin
    x += level.bounds.size[0]/2 & ~15
    z += level.bounds.size[2]/2 & ~15

    box = BoundingBox((x, y, z), (64, 64, 64,))
    zs = level.extractZipSchematic(box)
    assert(box.chunkCount == zs.chunkCount)
    zs.close()
    os.remove(zs.filename)
#
# def testINVEditChests(self):
#     invFile = WorldEditor("schematics/Chests/TinkerersBox.inv")
#     assert invFile.Blocks.any()
#     assert not invFile.Data.any()
#     assert len(invFile.Entities) == 0
#     assert len(invFile.TileEntities) == 1
#     # raise SystemExit

def testCopyOffsets(pc_world):
    dimension = pc_world.getDimension()
    schematic = createSchematic((13, 8, 5))
    schematicDim = schematic.getDimension()

    x, y, z = dimension.bounds.origin + [p/2 for p in dimension.bounds.size]
    for dx in range(16):
        for dz in range(16):
            dimension.copyBlocks(schematicDim, schematicDim.bounds, (x+dx, y, z+dz), biomes=True)
