from mceditlib.worldeditor import WorldEditor
from timeit import timeit

import templevel

#import logging
#logging.basicConfig(level=logging.INFO)

def natural_relight():
    world = templevel.TempLevel("AnvilWorld")
    dim = world.getDimension()
    t = timeit(lambda: dim.generateLights(dim.chunkPositions()), number=1)
    print "Relight natural terrain: %d chunks in %.02f seconds (%.02fms per chunk)" % (dim.chunkCount, t,
                                                                                       t / world.chunkCount * 1000)


def manmade_relight():
    t = templevel.TempLevel("TimeRelight", createFunc=lambda f:WorldEditor(f, create=True))

    world = t
    station = WorldEditor("test_files/station.schematic")

    times = 2

    for x in range(times):
        for z in range(times):
            world.copyBlocksFrom(station, station.bounds, (x * station.Width, 63, z * station.Length), create=True)

    t = timeit(lambda: world.generateLights(world.chunkPositions), number=1)
    print "Relight manmade building: %d chunks in %.02f seconds (%.02fms per chunk)" % (world.chunkCount, t, t / world.chunkCount * 1000)

if __name__ == '__main__':
    natural_relight()
    manmade_relight()



