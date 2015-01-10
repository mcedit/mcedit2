import itertools
import os
import shutil

import numpy
import py.test
from mceditlib.anvil.adapter import AnvilWorldAdapter
from mceditlib.util import exhaust

from mceditlib.worldeditor import WorldEditor
from mceditlib import nbt
from mceditlib.selection import BoundingBox
from mceditlib.pc.regionfile import RegionFile
from templevel import mktemp, TempLevel, TempFile


__author__ = 'Rio'

def testCreate():
    temppath = mktemp("AnvilCreate")
    anvilLevel = WorldEditor(filename=temppath, create=True, adapterClass=AnvilWorldAdapter)
    anvilLevel.close()
    shutil.rmtree(temppath)


@py.test.fixture
def sourceLevel():
    return TempLevel("Station.schematic")

@py.test.fixture
def anvilLevel():
    return TempLevel("AnvilWorld")

def testCreateChunks(anvilLevel):
    dim = anvilLevel.getDimension()
    for ch in list(dim.chunkPositions()):
        dim.deleteChunk(*ch)
    for ch in BoundingBox((0, 0, 0), (32, 0, 32)).chunkPositions():
        dim.createChunk(*ch)

def testRecreateChunks(anvilLevel):
    dim = anvilLevel.getDimension()
    for x, z in itertools.product(xrange(-1, 3), xrange(-1, 2)):
        dim.deleteChunk(x, z)
        assert not dim.containsChunk(x, z)
        dim.createChunk(x, z)

def testCopyRelight(anvilLevel, sourceLevel):
    destDim = anvilLevel.getDimension()
    exhaust(destDim.copyBlocksIter(sourceLevel.getDimension(), BoundingBox((0, 0, 0), (32, 64, 32,)),
            destDim.bounds.origin))
    anvilLevel.saveChanges()

def testRecompress(anvilLevel):
    dim = anvilLevel.getDimension()
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
        anvilLevel.saveChanges()
        section = dim.getChunk(cx, cz).getSection(cy)
        section.dirty = True
        assert (section.Data == 13).all()
        for key in keys:
            assert (d[key] == getattr(section, key)).all()

def testBigEndianIntHeightMap():
    """ Test modifying, saving, and loading the new TAG_Int_Array heightmap
    added with the Anvil format.
    """
    region = RegionFile(TempFile("test_files/AnvilWorld/region/r.0.0.mca"))
    chunk_data = region.readChunkBytes(0, 0)
    chunk = nbt.load(buf=chunk_data)

    hm = chunk["Level"]["HeightMap"]
    hm.value[2] = 500
    oldhm = numpy.array(hm.value)

    filename = mktemp("ChangedChunk")
    chunk.save(filename)
    changedChunk = nbt.load(filename)
    os.unlink(filename)

    eq = (changedChunk["Level"]["HeightMap"].value == oldhm)
    assert eq.all()
