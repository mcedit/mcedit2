from mceditlib.worldeditor import WorldEditor
from templevel import TempLevel
import logging
import numpy

logging.basicConfig(level=logging.INFO)

def test_relight():
    pc_world = TempLevel("AnvilWorld")
    anvilDim = pc_world.getDimension()
    bounds = anvilDim.bounds
    point = bounds.origin + (bounds.size * (0.5, 0.5, 0.5))

    box = bounds.expand(-100, 0, -100)

#    box = BoundingBox((256, 0, 256), (64, pc_world.Height, 64))
    chunks = [(cx, cz) for cx, cz in anvilDim.chunkPositions() if (cx << 4, 1, cz << 4) not in box]
    for c in chunks:
        anvilDim.deleteChunk(*c)

    #pc_world = WorldEditor(filename=temppath, create=True)
    station = TempLevel("station.schematic")
    stationDim = station.getDimension()
    anvilDim.copyBlocks(stationDim, stationDim.bounds, point, create=True)
    for cPos in anvilDim.chunkPositions():
        anvilDim.getChunk(*cPos)

    #pc_world.copyBlocksFrom(station, station.bounds, point + (station.Width, 0, 0), create=True)
    pc_world.generateLights()

    pc_world.saveChanges()
    cx = int(point.x + 32) >> 4
    cz = int(point.z + 32) >> 4
    # os.system(sys.executable + " ../mcedit.py " + pc_world.filename)

    def check():
        sl = numpy.sum(pc_world.getChunk(cx, cz).SkyLight)
        bl = numpy.sum(pc_world.getChunk(cx, cz).BlockLight)
        assert (sl, bl) == (341328, 43213)

    check()

    pc_world.close()


    pc_world = WorldEditor(templevel.tmpname)
    check()


