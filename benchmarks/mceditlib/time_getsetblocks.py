import numpy

from benchmarks import bench_temp_level
from mceditlib.selection import BoundingBox

level = bench_temp_level("AnvilWorld")
dim = level.getDimension()
box = BoundingBox(dim.bounds.origin, (64, 32, 64))

xg, yg, zg = numpy.mgrid[
          box.minx:box.maxx,
          box.miny:box.maxy,
          box.minz:box.maxz,
]

xg, yg, zg = [numpy.ravel(a) for a in xg, yg, zg]

def timeGetBlocksGrid():

    result = dim.getBlocks(xg, yg, zg, return_Data=True)
    #print "Coords", [x, y, z], "maxz", z.max()
    #print "Length", result.Blocks.shape

def timeSetBlocksGrid():

    #print "Coords", [x, y, z], "maxz", z.max()
    dim.setBlocks(xg, yg, zg, Blocks=1, Data=1, updateLights=False)

xt, yt, zt = numpy.transpose(list(box.positions))

assert xt.shape == xg.shape

def timeGetBlocks():
    result = dim.getBlocks(xt, yt, zt, return_Data=True)
    #print "Coords", [x, y, z], "maxz", z.max()
    #print "Length", result.Blocks.shape


def timeSetBlocks():
    #x, y, z = numpy.transpose(list(box.positions))

    #print "Coords", [x, y, z], "maxz", z.max()
    dim.setBlocks(xt, yt, zt, Blocks=1, Data=1, updateLights=False)


def timeGetBlocksOld():
    for x, y, z in box.positions:
        dim.getBlockID(x, y, z)
        dim.getBlockData(x, y, z)

def timeSetBlocksOld():
    for x, y, z in box.positions:
        dim.setBlockID(x, y, z, 1)
        dim.setBlockData(x, y, z, 1)


if __name__ == "__main__":
    import timeit
    # warm up
    timeGetBlocksGrid()

    print "GetMGrid: %.03f" % (timeit.timeit(timeGetBlocksGrid, number=1))
    print "SetMGrid: %.03f" % (timeit.timeit(timeSetBlocksGrid, number=1))
    print "GetBoxPos: %.03f" % (timeit.timeit(timeGetBlocks, number=1))
    print "SetBoxPos: %.03f" % (timeit.timeit(timeSetBlocks, number=1))
    print "GetSingle: %.03f" % (timeit.timeit(timeGetBlocksOld, number=1))
    print "SetSingle: %.03f" % (timeit.timeit(timeSetBlocksOld, number=1))
