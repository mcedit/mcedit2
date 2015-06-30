
import numpy
import sys
import time
from mceditlib.selection import BoundingBox

from mceditlib.worldeditor import WorldEditor
from mceditlib.test import templevel
from mceditlib import relight


def manmade_relight():
    world = templevel.TempLevel("AnvilWorld")
    dim = world.getDimension()
    stationEditor = WorldEditor("test_files/station.schematic")
    station = stationEditor.getDimension()

    times = 1
    boxes = []

    for x in range(times):
        for z in range(times):
            origin = (x * station.bounds.width, 54, z * station.bounds.length)
            boxes.append(BoundingBox(origin, station.bounds.size))
            dim.copyBlocks(station, station.bounds, origin, create=True)

    box = reduce(lambda a, b: a.union(b), boxes)

    positions = []
    for cx, cz in box.chunkPositions():
        for cy in box.sectionPositions(cx, cz):
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

    print "Relight manmade building: %d chunk-sections in %.02f seconds (%f sections per second; %dms per section)" % (count, t, count / t, 1000 * t / count)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        method = sys.argv[1]
        print "Using method", method
        relight.setMethod(method)
    manmade_relight()



