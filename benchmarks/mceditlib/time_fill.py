from benchmarks import bench_temp_level
from mceditlib.util import exhaust
import logging
logging.basicConfig(level=logging.INFO)

def timeFill():
    temp = bench_temp_level("AnvilWorld")
    editor = temp
    dim = editor.getDimension()
    editor.loadedChunkLimit = 1
    exhaust(dim.fillBlocksIter(dim.bounds, editor.blocktypes.OakWoodPlanks))


if __name__ == "__main__":
    import timeit
    print "Filled in %.02f" % (timeit.timeit(timeFill, number=1))
