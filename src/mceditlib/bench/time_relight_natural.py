import numpy
import sys
import time

from mceditlib.test import templevel
from mceditlib import relight

# run me with the source checkout as the working dir so I can find the test_files folder.

def natural_relight():
    world = templevel.TempLevel("AnvilWorld")
    dim = world.getDimension()
    positions = []
    for cx, cz in dim.chunkPositions():
        chunk = dim.getChunk(cx, cz)
        for cy in chunk.sectionPositions():
            positions.append((cx, cy, cz))

    poses = iter(positions)

    def do_relight():
        cx, cy, cz = poses.next()
        indices = numpy.indices((16, 16, 16), numpy.int32)
        indices.shape = 3, 16*16*16
        indices += ([cx], [cy], [cz])
        x, y, z = indices

        relight.updateLightsByCoord(dim, x, y, z)

    # Find out how many sections we can do in `maxtime` seconds.
    start = time.time()
    count = 0
    maxtime = 10
    end = start + maxtime
    while time.time() < end:
        try:
            do_relight()
        except StopIteration:
            break
        count += 1
    t = time.time() - start

    print "Relight natural terrain: %d chunk-sections in %.02f seconds (%f sections per second; %dms per section)" % (count, t, count / t, 1000 * t / count)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        method = sys.argv[1]
        print "Using method", method
        relight.setMethod(method)
    natural_relight()



