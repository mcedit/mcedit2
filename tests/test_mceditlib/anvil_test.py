import itertools
import os
import shutil

import numpy
import pytest

from mceditlib.anvil.adapter import AnvilWorldAdapter
from mceditlib.util import exhaust

from mceditlib.worldeditor import WorldEditor
from mceditlib import nbt
from mceditlib.selection import BoundingBox
from mceditlib.pc.regionfile import RegionFile

__author__ = 'Rio'


def testCreate(tmpdir):
    temppath = tmpdir.join("AnvilCreate")
    temppath.mkdir()
    pc_world = WorldEditor(filename=temppath.strpath, create=True, adapterClass=AnvilWorldAdapter)
    pc_world.close()


def testCreateChunks(pc_world):
    dim = pc_world.getDimension()
    for ch in list(dim.chunkPositions()):
        dim.deleteChunk(*ch)
    for ch in BoundingBox((0, 0, 0), (32, 0, 32)).chunkPositions():
        dim.createChunk(*ch)


def testRecreateChunks(pc_world):
    dim = pc_world.getDimension()
    for x, z in itertools.product(xrange(-1, 3), xrange(-1, 2)):
        dim.deleteChunk(x, z)
        assert not dim.containsChunk(x, z)
        dim.createChunk(x, z)


def testCopyRelight(pc_world, schematic_world):
    destDim = pc_world.getDimension()
    exhaust(destDim.copyBlocksIter(schematic_world.getDimension(), BoundingBox((0, 0, 0), (32, 64, 32,)),
            destDim.bounds.origin))
    pc_world.saveChanges()


def testRecompress(pc_world):
    dim = pc_world.getDimension()
    keys = 'Blocks Data SkyLight BlockLight'.split()

    cx, cz = iter(dim.chunkPositions()).next()
    chunk = dim.getChunk(cx, cz)
    chunk.dirty = True

    cy = 0
    section = chunk.getSection(cy)
    assert(section is not None)

    section.Blocks[:] = 6
    section.Data[:] = 13
    d = {}
    for key in keys:
        d[key] = numpy.array(getattr(section, key))

    for i in range(5):
        pc_world.saveChanges()
        section = dim.getChunk(cx, cz).getSection(cy)
        section.dirty = True
        assert (section.Data == 13).all()
        for key in keys:
            assert (d[key] == getattr(section, key)).all()


@pytest.mark.parametrize(['temp_file'], [('AnvilWorld/region/r.0.0.mca',)],
                         ids=['AnvilWorld'], indirect=True)
def testBigEndianIntHeightMap(tmpdir, temp_file):
    """ Test modifying, saving, and loading the new TAG_Int_Array heightmap
    added with the Anvil format.
    """
    region = RegionFile(temp_file.strpath)
    chunk_data = region.readChunkBytes(0, 0)
    chunk = nbt.load(buf=chunk_data)

    hm = chunk["Level"]["HeightMap"]
    hm.value[2] = 500
    oldhm = numpy.array(hm.value)

    filename = tmpdir.join("ChangedChunk").strpath
    chunk.save(filename)
    changedChunk = nbt.load(filename)
    os.unlink(filename)

    eq = (changedChunk["Level"]["HeightMap"].value == oldhm)
    assert eq.all()
