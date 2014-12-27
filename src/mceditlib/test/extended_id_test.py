from mceditlib.export import extractSchematicFrom
from mceditlib.schematic import SchematicFile
from mceditlib.geometry import BoundingBox
from mceditlib.worldeditor import WorldEditor
from templevel import TempLevel

__author__ = 'Rio'

def test_schematic_extended_ids():
    s = SchematicFile(shape=(1, 1, 5))
    s.Blocks[0,0,0] = 2048
    temp = TempLevel("schematic", createFunc=s.saveToFile)
    s = temp
    assert s.Blocks[0,0,0] == 2048

def alpha_test_level():
    level = TempLevel("alpha", createFunc=lambda f: WorldEditor(f, create=True))
    level.createChunk(0, 0)

    for x in range(0, 10):
        level.setBlockID(x, 2, 5, 2048)

    level.saveChanges()
    level.close()

    level = WorldEditor(filename=level.filename)
    return level

def testExport():
    level = alpha_test_level()

    for size in [(15, 15, 15),
                 (16, 16, 16),
                 (15, 16, 16),
                 (15, 16, 15),
                 ]:
        schem = extractSchematicFrom(level, BoundingBox((0, 0, 0), size))
        schem = TempLevel("schem", createFunc=lambda f: schem.saveToFile(f))
        assert (schem.Blocks > 255).any()

def testAlphaIDs():
    level = alpha_test_level()
    assert level.getBlock(0,2,5) == 2048

