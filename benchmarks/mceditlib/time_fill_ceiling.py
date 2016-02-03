from benchmarks import bench_temp_level
from mceditlib.selection import BoundingBox
from mceditlib.util import exhaust
import logging
logging.basicConfig(level=logging.INFO)

size = 50

def timeFillCeiling():
    temp = bench_temp_level("AnvilWorld")
    editor = temp
    dim = editor.getDimension()
    bounds = dim.bounds
    x, y, z = bounds.center
    y = 254
    x -= size//2
    z -= size//2
    bounds = BoundingBox((x, y, z), (size, 1, size))
    exhaust(dim.fillBlocksIter(bounds, editor.blocktypes["planks"]))


if __name__ == "__main__":
    import timeit
    time = timeit.timeit(timeFillCeiling, number=1)
    print "Filled in %.02f (%0.3f per block" % (time, (time / (size * size)))
