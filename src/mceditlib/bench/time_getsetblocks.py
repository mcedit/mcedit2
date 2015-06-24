import numpy
from templevel import TempLevel
from mceditlib.selection import BoundingBox

level = TempLevel("AnvilWorld")
dim = level.getDimension()
box = BoundingBox(dim.bounds.origin, (64, 32, 64))

def timeGetBlocksOld():
    for x, y, z in box.positions:
        dim.getBlockID(x, y, z)
        dim.getBlockData(x, y, z)

def timeSetBlocksOld():
    for x, y, z in box.positions:
        dim.setBlockID(x, y, z, 1)
        dim.setBlockData(x, y, z, 1)


def timeGetBlocksGrid():
    x, y, z = numpy.mgrid[
              box.minx:box.maxx,
              box.miny:box.maxy,
              box.minz:box.maxz,
    ]

    x, y, z = [numpy.ravel(a) for a in x, y, z]
    result = dim.getBlocks(x, y, z, return_Data=True)
    #print "Coords", [x, y, z], "maxz", z.max()
    #print "Length", result.Blocks.shape

def timeSetBlocksGrid():
    x, y, z = numpy.mgrid[
              box.minx:box.maxx,
              box.miny:box.maxy,
              box.minz:box.maxz,
    ]

    x, y, z = [numpy.ravel(a) for a in x, y, z]

    #print "Coords", [x, y, z], "maxz", z.max()
    dim.setBlocks(x, y, z, Blocks=1, Data=1)


def timeGetBlocks():
    x, y, z = numpy.transpose(list(box.positions))
    result = dim.getBlocks(x, y, z, return_Data=True)
    #print "Coords", [x, y, z], "maxz", z.max()
    #print "Length", result.Blocks.shape


def timeSetBlocks():
    x, y, z = numpy.transpose(list(box.positions))

    #print "Coords", [x, y, z], "maxz", z.max()
    dim.setBlocks(x, y, z, Blocks=1, Data=1)


if __name__ == "__main__":
    import timeit
    print "GetFast: %.03f" % (timeit.timeit(timeGetBlocksGrid, number=1))
    print "SetFast: %.03f" % (timeit.timeit(timeSetBlocksGrid, number=1))
    print "GetNew: %.03f" % (timeit.timeit(timeGetBlocks, number=1))
    print "SetNew: %.03f" % (timeit.timeit(timeSetBlocks, number=1))
    print "GetOld: %.03f" % (timeit.timeit(timeGetBlocksOld, number=1))
    print "SetOld: %.03f" % (timeit.timeit(timeSetBlocksOld, number=1))
