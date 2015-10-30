
import numpy
import sys
import time

from benchmarks import bench_temp_level
from mceditlib.selection import BoundingBox

from mceditlib.worldeditor import WorldEditor
from mceditlib import relight


def do_copy(dim, station, relight):
    times = 1
    boxes = []
    for x in range(times):
        for z in range(times):
            origin = (x * station.bounds.width, 54, z * station.bounds.length)
            boxes.append(BoundingBox(origin, station.bounds.size))
            dim.copyBlocks(station, station.bounds, origin, create=True, updateLights=relight)
    return reduce(lambda a, b: a.union(b), boxes)

def manmade_relight(test):
    world = bench_temp_level("AnvilWorld")
    dim = world.getDimension()
    stationEditor = WorldEditor("test_files/station.schematic")
    station = stationEditor.getDimension()

    startCopy = time.time()
    box = do_copy(dim, station, False)
    copyTime = time.time() - startCopy
    print("Copy took %f seconds. Reducing relight-in-copyBlocks times by this much." % copyTime)

    positions = []
    for cx, cz in box.chunkPositions():
        for cy in box.sectionPositions(cx, cz):
            positions.append((cx, cy, cz))
    assert len(positions) > box.chunkCount

    if test == "post" or test == "all":
        def postCopy():  # profiling
            start = time.time()
            count = 0
            print("Relighting outside of copyBlocks. Updating %d cells" % (len(positions) * 16 * 16 * 16))
            for cx, cy, cz in positions:
                indices = numpy.indices((16, 16, 16), numpy.int32)
                indices.shape = 3, 16*16*16
                indices += ([cx << 4], [cy << 4], [cz << 4])
                x, y, z = indices
                relight.updateLightsByCoord(dim, x, y, z)
                count += 1
            t = time.time() - start

            print "Relight manmade building (outside copyBlocks): " \
                  "%d (out of %d) chunk-sections in %.02f seconds (%f sections per second; %dms per section)" \
                  % (count, len(positions), t, count / t, 1000 * t / count)
        postCopy()

    if test == "smart" or test == "all":
        def allSections():
            world = bench_temp_level("AnvilWorld")
            dim = world.getDimension()

            start = time.time()
            do_copy(dim, station, "all")
            t = time.time() - start - copyTime

            print "Relight manmade building (in copyBlocks, all sections): " \
                  "%d chunk-sections in %.02f seconds (%f sections per second; %dms per section)" \
                  % (len(positions), t, len(positions) / t, 1000 * t / len(positions))
        allSections()

    if test == "section" or test == "all":
        def perSection():
            world = bench_temp_level("AnvilWorld")
            dim = world.getDimension()

            start = time.time()
            do_copy(dim, station, "section")
            t = time.time() - start - copyTime

            print "Relight manmade building (in copyBlocks, for each section): " \
                  "%d chunk-sections in %.02f seconds (%f sections per second; %dms per section)" \
                  % (len(positions), t, len(positions) / t, 1000 * t / len(positions))
        perSection()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        method = sys.argv[1]
        print "Using method", method
        relight.setMethod(method)
    if len(sys.argv) > 2:
        test = sys.argv[2]
    else:
        test = "all"
    manmade_relight(test)


"""
Conclusion:

Much time is spent in the "post" method which updates all cells in the selection box, calling
updateLights on cells whose opacity values did not change. This is evidenced by the time spent in
"drawLights", which must be called because updateLights doesn't know the previous block type in
that cell.

copyBlocksFrom has been modified to find the cells whose lighting or opacity value did change,
and passing only those cells to updateLights. This is more than twice as fast, and updating
all changed cells at once is even faster, presumably because changes to following chunks will
invalidate lighting data computed by previous chunks.

Because updateLights does not know what the previous cell's opacity values were (it does know the
cell's current light value, so it can skip spreadLight if the new brightness didn't exceed that),
clients of updateLights should take care to find only cells whose opacity values changed.

copyBlocksFrom stores all changed cell positions, which could lead to MemoryErrors for very large
copies. Instead of storing all positions, it should periodically call updateLights whenever the
position list exceeds a threshold. This "batch-update" method should be an acceptable compromise
between updating for each section (suffering invalidation costs), and updating all sections
at once after the copy (risking MemoryErrors and possibly paying additional chunk loading costs)

Updating lights for chunks whose neighbors have not been copied yet will cause wasted effort.
It helps to describe this graphically. This is the current visitation order:

(area is 24x12, and 34 chunks have been copied so far)

************************
**********..............
........................
........................
........................
........................
........................
........................
........................
........................
........................
........................

'.' represents chunks that are yet to be copied.
'*' represents chunks that have been copied.

If a batched lighting update is called at this point, these are the chunks that, when they are
copied over later, will invalidate parts of the previous update:

************************
**********--------------
----------+.............
........................
........................
........................
........................
........................
........................
........................
........................
........................

'-' represents chunks that when edited will invalidate the previous lighting update applied
to the '*' chunks. There are 24 such chunks.

'+' represents chunks that when edited will invalidate at most half of a previous chunk's
update.

So let's say 24.5 chunks are invalidated later. Out of 34 chunks, that is not very good at all.

That number is roughly proportional to the width of the selection box.

The current visitation order is thus:


1234567890abcdefghijklmn
opqrstuvwx--------------
----------+.............
........................
........................
........................
........................
........................
........................
........................
........................
........................


A possibly improved visitation order:

12efghuvwx-.............
43dcjits--+.............
589bknor-...............
670almpq-...............
--------+...............
........................
........................
........................
........................
........................
........................
........................

13 full chunks and two half-chunks are invalidated, for a total of 15 chunks out of 34.

At least it's less than half.

This number is roughly proportional to the square root of the number of chunks copied so far.

The order of chunks visited by copyBlocksFrom is linear. When it calls updateLights for a chunk,
the chunks adjacent to that chunk (and ahead of that chunk in the order) will have to redo part
of this chunk's lighting for the current chunk when they are copied. To minimize wasted effort,
a chunk order that resembles a space-filling curve such as a Hilbert curve may be
applicable. The goal is to reduce the number of chunks who have neighbors yet to be copied at the
time the batched update is performed.

Maybe we can do better. What if, instead of batch-updating ALL of the chunks copied so far,
we only batch-update the ones we know won't be invalidated later?

The cells that need update are currently just tossed in a list. Instead, associate them with
their chunk position. Keep track of which chunks we have copied, and how many of their
eight neighbors have already been copied too. Only issue a batch update for chunks where all eight
neighbors are copied. If we use the original visitation order, then for very large copies, we may
reach the threshold before any neighbors have been copied. The new visitation order would avoid
this as, for most chunks, it will visit all of a chunk's neighbors very soon after that chunk.

In fact, it may not be necessary to batch-update at all if we can update a chunk as soon as all its
neighbors are ready.

Output:
Using method cython
INFO:mceditlib.block_copy:Copying 3103771 blocks from BoundingBox(origin=Vector(0, 0, 0), size=Vector(113, 121, 227)) to (0, 54, 0)
INFO:mceditlib.block_copy:Copying: Chunk 20/120...
INFO:mceditlib.block_copy:Copying: Chunk 40/120...
INFO:mceditlib.block_copy:Copying: Chunk 60/120...
INFO:mceditlib.block_copy:Copying: Chunk 80/120...
INFO:mceditlib.block_copy:Copying: Chunk 100/120...
INFO:mceditlib.block_copy:Copying: Chunk 120/120...
INFO:mceditlib.block_copy:Duration: 1.292s, 120/120 chunks, 10.77ms per chunk (92.88 chunks per second)
INFO:mceditlib.block_copy:Copied 0/0 entities and 293/293 tile entities
Copy took 1.292000 seconds. Reducing relight-in-copyBlocks times by this much.
Relighting outside of copyBlocks. Updating 3932160 cells
Relight manmade building (outside copyBlocks): 960 (out of 960) chunk-sections in 71.49 seconds (13.428639 sections per second; 74ms per section)
INFO:mceditlib.block_copy:Copying 3103771 blocks from BoundingBox(origin=Vector(0, 0, 0), size=Vector(113, 121, 227)) to (0, 54, 0)
INFO:mceditlib.block_copy:Copying: Chunk 20/120...
INFO:mceditlib.block_copy:Copying: Chunk 40/120...
INFO:mceditlib.block_copy:Copying: Chunk 60/120...
INFO:mceditlib.block_copy:Copying: Chunk 80/120...
INFO:mceditlib.block_copy:Copying: Chunk 100/120...
INFO:mceditlib.block_copy:Copying: Chunk 120/120...
INFO:mceditlib.block_copy:Duration: 1.318s, 120/120 chunks, 10.98ms per chunk (91.05 chunks per second)
INFO:mceditlib.block_copy:Copied 0/0 entities and 293/293 tile entities
INFO:mceditlib.block_copy:Updating all at once for 969 sections (646338 cells)
INFO:mceditlib.block_copy:Lighting complete.
INFO:mceditlib.block_copy:Duration: 16.979s, 968 sections, 17.54ms per section (57.01 sections per second)
Relight manmade building (in copyBlocks, all sections): 960 chunk-sections in 17.01 seconds (56.444027 sections per second; 17ms per section)
INFO:mceditlib.block_copy:Copying 3103771 blocks from BoundingBox(origin=Vector(0, 0, 0), size=Vector(113, 121, 227)) to (0, 54, 0)
INFO:mceditlib.block_copy:Copying: Chunk 20/120...
INFO:mceditlib.block_copy:Copying: Chunk 40/120...
INFO:mceditlib.block_copy:Copying: Chunk 60/120...
INFO:mceditlib.block_copy:Copying: Chunk 80/120...
INFO:mceditlib.block_copy:Copying: Chunk 100/120...
INFO:mceditlib.block_copy:Copying: Chunk 120/120...
Relight manmade building (in copyBlocks, for each section): 960 chunk-sections in 26.12 seconds (36.757667 sections per second; 27ms per section)
INFO:mceditlib.block_copy:Duration: 27.408s, 120/120 chunks, 228.40ms per chunk (4.38 chunks per second)
INFO:mceditlib.block_copy:Copied 0/0 entities and 293/293 tile entities
"""
