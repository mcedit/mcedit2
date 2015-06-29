import numpy
from mceditlib.worldeditor import WorldEditor
from timeit import timeit

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
        print "Relighting section %s..." % ((cx, cy, cz),)
        indices = numpy.indices((16, 16, 16), numpy.int32)
        indices.shape = 3, 16*16*16
        indices += ([cx], [cy], [cz])
        x, y, z = indices
        relight.updateLightsByCoord(dim, x, y, z)

    sectionCount = 5
    t = timeit(do_relight, number=sectionCount)
    print "Relight natural terrain: %d chunk-sections in %.02f seconds (%dms per section)" % (sectionCount, t, 1000 * t / sectionCount)

if __name__ == '__main__':
    natural_relight()



