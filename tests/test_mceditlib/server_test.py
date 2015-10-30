import pytest
from mceditlib.minecraft_server import MCServerChunkGenerator
from mceditlib.selection import BoundingBox

__author__ = 'Rio'

@pytest.skip("Server generator not implemented")
def testCreate():
    gen = MCServerChunkGenerator()
    print "Version: ", gen.serverVersion

    def _testCreate(filename):
        gen.createLevel(filename, BoundingBox((-128, 0, -128), (128, 128, 128)))

    TempLevel("ServerCreate", createFunc=_testCreate)

@pytest.skip("Server generator not implemented")
def testServerGen(pc_world):
    gen = MCServerChunkGenerator()
    print "Version: ", gen.serverVersion

    gen.generateChunkInLevel(pc_world, 50, 50)
    gen.generateChunksInLevel(pc_world, [(120, 50), (121, 50), (122, 50), (123, 50), (244, 244), (244, 245), (244, 246)])
    c = pc_world.getChunk(50, 50)
    assert c.getSection(0).Blocks.any()
