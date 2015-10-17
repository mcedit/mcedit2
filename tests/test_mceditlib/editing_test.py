import numpy
import pytest

from mceditlib.blocktypes import blocktypeConverter
from mceditlib.export import extractSchematicFrom
from mceditlib.selection import BoundingBox
from mceditlib.worldeditor import WorldEditor

__author__ = 'Rio'


def testGetEntities(any_world):
    dim = any_world.getDimension()
    print len(list(dim.getEntities(dim.bounds)))


def testImportAndConvert(any_world, schematic_world):
    destDim = any_world.getDimension()
    sourceDim = schematic_world.getDimension()
    destPoint = sourceDim.bounds.origin

    oldEntityCount = len(list(destDim.getEntities(BoundingBox(destPoint, sourceDim.bounds.size))))
    destDim.copyBlocks(sourceDim, sourceDim.bounds, destPoint, create=True)

    convertBlocks = blocktypeConverter(any_world.blocktypes, schematic_world.blocktypes)

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

            convertedSourceBlocks, convertedSourceData = convertBlocks(sourceSection.Blocks, sourceSection.Data)

            same = (destSection.Blocks == convertedSourceBlocks)

            # assert same.all()
            if not same.all():
                found = destSection.Blocks[~same]
                expected = convertedSourceBlocks[~same]
                assert (found != expected).any()

    assert (oldEntityCount + len(list(sourceDim.getEntities(sourceDim.bounds)))
            == len(list(destDim.getEntities(sourceDim.bounds))))


def testFill(any_world):
    dim = any_world.getDimension()
    bounds = dim.bounds

    box = BoundingBox(bounds.origin + (bounds.size / 2), (64, bounds.height / 2, 64))
    x, y, z = numpy.array(list(box.positions)).transpose()

    dim.fillBlocks(box, any_world.blocktypes["planks"])

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

    checkEqual(dim.getBlocks(x, y, z).Blocks, any_world.blocktypes["planks"].ID)

    dim.fillBlocks(box, any_world.blocktypes["stone"], [any_world.blocktypes["planks"]])
    any_world.saveChanges()
    any_world.close()

    filename = any_world.filename
    any_world = WorldEditor(filename)
    checkEqual(any_world.getDimension().getBlocks(x, y, z).Blocks, any_world.blocktypes["stone"].ID)


def testOldReplace(any_world):
    dim = any_world.getDimension()
    dim.fillBlocks(BoundingBox((-11, 0, -7), (38, dim.bounds.height, 25)), any_world.blocktypes["planks"],
                   [any_world.blocktypes["dirt"], any_world.blocktypes["grass"]])


def testMultiReplace(any_world):
    dim = any_world.getDimension()
    dim.fillBlocks(BoundingBox((-11, 0, -7), (38, dim.bounds.height, 25)),
                   [(any_world.blocktypes["planks"], any_world.blocktypes["dirt"]),
                    (any_world.blocktypes["grass"], any_world.blocktypes["iron_ore"])])


def testImport(any_world, schematic_world):
    dim = any_world.getDimension()
    dim.copyBlocks(schematic_world.getDimension(), BoundingBox((0, 0, 0), (32, 64, 32,)), dim.bounds.origin)
    any_world.saveChanges()


def testExportImport(any_world):
    dim = any_world.getDimension()

    schem = extractSchematicFrom(dim, dim.bounds)
    schemDim = schem.getDimension()
    dim.copyBlocks(schemDim, schemDim.bounds, (0, 0, 0))


if __name__ == "__main__":
    pytest.main()
