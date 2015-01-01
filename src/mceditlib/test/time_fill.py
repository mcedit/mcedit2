from mceditlib.util import exhaust
from templevel import TempLevel
import logging
logging.basicConfig(level=logging.INFO)

def timeFill():
    temp = TempLevel("AnvilWorld")
    editor = temp
    dim = editor.getDimension()
    editor.loadedChunkLimit = 1
    exhaust(dim.fillBlocksIter(dim.bounds, editor.blocktypes.OakWoodPlanks))


if __name__ == "__main__":
    import timeit
    print "Filled in %.02f" % (timeit.timeit(timeFill, number=1))
