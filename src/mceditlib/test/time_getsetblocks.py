import numpy
from templevel import TempLevel
from mceditlib.geometry import BoundingBox

level = TempLevel("AnvilWorld")
box = BoundingBox(level.bounds.origin, (64, 32, 64))

def timeGetBlocksOld():
    for x, y, z in box.positions:
        level.getBlockID(x, y, z)
        level.getBlockData(x, y, z)



def timeGetBlocksFast():

    x, y, z = numpy.mgrid[
              box.minx:box.maxx,
              box.miny:box.maxy,
              box.minz:box.maxz,
    ]

    x, y, z = [numpy.ravel(a) for a in x, y, z]

    print "Coords", [x, y, z], "maxz", z.max()
    print "Length", level.getBlocks(x, y, z, return_Data=True).Blocks.shape

def timeGetBlocks():

    x, y, z = numpy.transpose(list(box.positions))

    print "Coords", [x, y, z], "maxz", z.max()
    print "Length", level.getBlocks(x, y, z, return_Data=True).Blocks.shape


def timeSetBlocksOld():
    for x, y, z in box.positions:
        level.setBlockID(x, y, z, 1)
        level.setBlockData(x, y, z, 1)



def timeSetBlocksFast():
    x, y, z = numpy.mgrid[
              box.minx:box.maxx,
              box.miny:box.maxy,
              box.minz:box.maxz,
    ]

    x, y, z = [numpy.ravel(a) for a in x, y, z]

    print "Coords", [x, y, z], "maxz", z.max()
    level.setBlocks(x, y, z, Blocks=1, Data=1)


def timeSetBlocks():
    x, y, z = numpy.transpose(list(box.positions))

    print "Coords", [x, y, z], "maxz", z.max()
    level.setBlocks(x, y, z, Blocks=1, Data=1)


if __name__ == "__main__":
    import timeit
    print "GetFast: %.03f" % (timeit.timeit(timeGetBlocksFast, number=1))
    print "SetFast: %.03f" % (timeit.timeit(timeSetBlocksFast, number=1))
    print "GetNew: %.03f" % (timeit.timeit(timeGetBlocks, number=1))
    print "SetNew: %.03f" % (timeit.timeit(timeSetBlocks, number=1))
    print "GetOld: %.03f" % (timeit.timeit(timeGetBlocksOld, number=1))
    print "SetOld: %.03f" % (timeit.timeit(timeSetBlocksOld, number=1))
