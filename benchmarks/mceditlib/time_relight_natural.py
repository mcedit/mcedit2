import numpy
import sys
import time

from benchmarks import bench_temp_level
from mceditlib import relight

# run me with the source checkout as the working dir so I can find the test_files folder.

def natural_relight():
    world = bench_temp_level("AnvilWorld")
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
        indices += ([cx << 4], [cy << 4], [cz << 4])
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

    print "Relight natural terrain: %d/%d chunk-sections in %.02f seconds (%f sections per second; %dms per section)" % (count, len(positions), t, count / t, 1000 * t / count)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        method = sys.argv[1]
        print "Using method", method
        relight.setMethod(method)
    natural_relight()



