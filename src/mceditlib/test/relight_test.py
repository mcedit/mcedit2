from mceditlib.worldeditor import WorldEditor
from templevel import TempLevel
import logging
import numpy

logging.basicConfig(level=logging.INFO)

def test_relight():
    templevel = TempLevel("AnvilWorld")
    anvilLevel = templevel
    anvilDim = anvilLevel.getDimension()
    bounds = anvilDim.bounds
    point = bounds.origin + (bounds.size * (0.5, 0.5, 0.5))

    box = bounds.expand(-100, 0, -100)

#    box = BoundingBox((256, 0, 256), (64, anvilLevel.Height, 64))
    chunks = [(cx, cz) for cx, cz in anvilDim.chunkPositions() if (cx << 4, 1, cz << 4) not in box]
    for c in chunks:
        anvilDim.deleteChunk(*c)

    #anvilLevel = WorldEditor(filename=temppath, create=True)
    station = WorldEditor("test_files/station.schematic")
    stationDim = station.getDimension()
    anvilDim.copyBlocks(stationDim, stationDim.bounds, point, create=True)
    for cPos in anvilDim.chunkPositions():
        anvilDim.getChunk(*cPos)

    #anvilLevel.copyBlocksFrom(station, station.bounds, point + (station.Width, 0, 0), create=True)
    anvilLevel.generateLights()

    anvilLevel.saveChanges()
    cx = int(point.x + 32) >> 4
    cz = int(point.z + 32) >> 4
    # os.system(sys.executable + " ../mcedit.py " + anvilLevel.filename)

    def check():
        sl = numpy.sum(anvilLevel.getChunk(cx, cz).SkyLight)
        bl = numpy.sum(anvilLevel.getChunk(cx, cz).BlockLight)
        assert (sl, bl) == (341328, 43213)

    check()

    anvilLevel.close()


    anvilLevel = WorldEditor(templevel.tmpname)
    check()


