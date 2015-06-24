from timeit import timeit

import numpy
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
        print "Relighting section %s..." % ((cx, cy, cz),)
        indices = numpy.indices((16, 16, 16), numpy.uint32)
        indices.shape = 3, 16*16*16
        indices += ([cx], [cy], [cz])
        x, y, z = indices
        relight.updateLightsByCoord(dim, x, y, z)

    sectionCount = 5
    t = timeit(do_relight, number=sectionCount)
    print "Relight manmade building: %d chunk-sections in %.02f seconds (%dms per section)" % (sectionCount, t, 1000 * t / sectionCount)

if __name__ == '__main__':
    manmade_relight()



