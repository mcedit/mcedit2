from mceditlib.export import extractSchematicFrom
from mceditlib.schematic import createSchematic
from mceditlib.selection import BoundingBox
from mceditlib.worldeditor import WorldEditor

import pytest

__author__ = 'Rio'


@pytest.fixture
def extid_pc_world(tmpdir):
    filename = tmpdir.join("pc_extended_ids").strpath
    level = WorldEditor(filename, create=True)
    dim = level.getDimension()

    dim.createChunk(0, 0)

    for x in range(0, 10):
        dim.setBlockID(x, 2, 5, 2048)

    return level


def test_schematic_extended_ids(tmpdir):
    s = createSchematic(shape=(1, 1, 5))

    s.adapter.Blocks[0,0,0] = 2048
    s.filename = tmpdir.join("schematic_extended_ids.schematic").strpath
    s.saveChanges()
    assert s.adapter.Blocks[0,0,0] == 2048


def test_extid_extract(tmpdir, extid_pc_world):

    for size in [(15, 15, 15),
                 (16, 16, 16),
                 (15, 16, 16),
                 (15, 16, 15),
                 ]:
        schem = extractSchematicFrom(extid_pc_world, BoundingBox((0, 0, 0), size))
        filename = tmpdir.join("extid_extract_%s" % "_".join(size)).strpath
        schem.filename = filename
        schem.saveChanges()
        del schem
        schem = WorldEditor(filename)
        assert (schem.adapter.Blocks > 255).any()


def test_extid_pc_world(extid_pc_world):
    extid_pc_world.saveChanges()
    extid_pc_world.close()
    filename = extid_pc_world.filename
    del extid_pc_world
    level = WorldEditor(filename=filename)

    assert level.getDimension().getBlockID(0,2,5) == 2048

