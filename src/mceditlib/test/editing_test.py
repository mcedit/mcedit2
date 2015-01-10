import zipfile
import numpy
import pytest
import logging

from mceditlib.export import extractSchematicFrom
from mceditlib.selection import BoundingBox
from mceditlib import block_copy
from mceditlib.worldeditor import WorldEditor
from templevel import TempLevel

logging.basicConfig(level=logging.INFO)

__author__ = 'Rio'


@pytest.fixture(params=["AnvilWorld", "Floating.schematic"])
# , "MCRWorld", "city_256_256_128.dat", "PocketWorldAdapter.zip"
def world(request):
    if request.param == "PocketWorldAdapter.zip":
        def unpackPocket(tmpname):
            zf = zipfile.ZipFile("test_files/PocketWorldAdapter.zip")
            zf.extractall(tmpname)
            return WorldEditor(tmpname + "/PocketWorldAdapter")

        return TempLevel("XXX", createFunc=unpackPocket)

    return TempLevel(request.param)


@pytest.fixture(params=["Station.schematic"])
def sourceLevel(request):
    return TempLevel(request.param)


def testGetEntities(world):
    dim = world.getDimension()
    print len(list(dim.getEntities(dim.bounds)))


def testImportAndConvert(world, sourceLevel):
    destDim = world.getDimension()
    sourceDim = sourceLevel.getDimension()
    destPoint = sourceDim.bounds.origin

    oldEntityCount = len(list(destDim.getEntities(BoundingBox(destPoint, sourceDim.bounds.size))))
    destDim.copyBlocks(sourceDim, sourceDim.bounds, destPoint, create=True)

    for sourceChunk in sourceDim.getChunks():
        cx = sourceChunk.cx
        cz = sourceChunk.cz
        destChunk = destDim.getChunk(cx, cz)

        x = cx << 4
        z = cz << 4
        for cy in sourceChunk.bounds.sectionPositions(cx, cz):
            destSection = destChunk.getSection(cy)
            if destSection is None:
                continue
            sourceSection = sourceChunk.getSection(cy)

            convertedSourceBlocks, convertedSourceData = block_copy.convertBlocks(world, sourceLevel,
                                                                                  sourceSection.Blocks,
                                                                                  sourceSection.Data)

            same = (destSection.Blocks == convertedSourceBlocks)

            # assert same.all()
            if not same.all():
                found = destSection.Blocks[~same]
                expected = convertedSourceBlocks[~same]
                assert (found != expected).any()

    assert (oldEntityCount + len(list(sourceDim.getEntities(sourceDim.bounds)))
            == len(list(destDim.getEntities(sourceDim.bounds))))


def testFill(world):
    dim = world.getDimension()
    bounds = dim.bounds

    box = BoundingBox(bounds.origin + (bounds.size / 2), (64, bounds.height / 2, 64))
    x, y, z = numpy.array(list(box.positions)).transpose()

    dim.fillBlocks(box, world.blocktypes.OakWoodPlanks)

    def checkEqual(a, b):
        """

        :type a: ndarray
        :type b: ndarray
        """
        equal = a == b
        if not equal.all():
            assert False, "Coordinates not equal to %s: \nX: %s\nY: %s\nZ: %s" % (b, x[~equal], y[~equal], z[~equal])

        for cp in box.chunkPositions():
            chunk = dim.getChunk(*cp)
            for cy in chunk.bounds.sectionPositions(*cp):
                assert chunk.getSection(cy) is not None, "Section %s not found" % cy

    checkEqual(dim.getBlocks(x, y, z).Blocks, world.blocktypes.OakWoodPlanks.ID)

    dim.fillBlocks(box, world.blocktypes.Stone, [world.blocktypes.OakWoodPlanks])
    world.saveChanges()
    world.close()

    filename = world.filename
    world = WorldEditor(filename)
    checkEqual(world.getDimension().getBlocks(x, y, z).Blocks, world.blocktypes.Stone.ID)


def testOldReplace(world):
    dim = world.getDimension()
    dim.fillBlocks(BoundingBox((-11, 0, -7), (38, dim.bounds.height, 25)), world.blocktypes.OakWoodPlanks,
                   [world.blocktypes.Dirt, world.blocktypes.Grass])


def testMultiReplace(world):
    dim = world.getDimension()
    dim.fillBlocks(BoundingBox((-11, 0, -7), (38, dim.bounds.height, 25)),
                   [(world.blocktypes.OakWoodPlanks, world.blocktypes.Dirt),
                    (world.blocktypes.Grass, world.blocktypes.IronOre)])


def testImport(world, sourceLevel):
    dim = world.getDimension()
    dim.copyBlocks(sourceLevel.getDimension(), BoundingBox((0, 0, 0), (32, 64, 32,)), dim.bounds.origin)
    world.saveChanges()


def testExportImport(world):
    dim = world.getDimension()

    schem = extractSchematicFrom(dim, dim.bounds)
    schemDim = schem.getDimension()
    dim.copyBlocks(schemDim, schemDim.bounds, (0, 0, 0))


if __name__ == "__main__":
    pytest.main()
