from mceditlib.worldeditor import WorldEditor
import numpy



def test_relight(schematic_world, pc_world):
    anvilDim = pc_world.getDimension()
    bounds = anvilDim.bounds
    point = bounds.origin + (bounds.size * (0.5, 0.25, 0.5))

    stationDim = schematic_world.getDimension()
    anvilDim.copyBlocks(stationDim, stationDim.bounds, point, create=True)

    pc_world.saveChanges()
    cx = int(point.x + 32) >> 4
    cz = int(point.z + 32) >> 4

    def check():
        sl = 0
        bl = 0
        chunk = pc_world.getDimension().getChunk(cx, cz)
        for cy in chunk.sectionPositions():
            section = chunk.getSection(cy)
            sl += numpy.sum(section.SkyLight)
            bl += numpy.sum(section.BlockLight)
        assert (sl, bl) == (245085, 48261) # was 367965, why??

    check()

    pc_world.close()

    pc_world = WorldEditor(pc_world.filename)
    check()


