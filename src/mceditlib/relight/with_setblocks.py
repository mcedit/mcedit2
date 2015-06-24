
import logging
import pprint
import itertools
import numpy
from mceditlib.heightmaps import extractHeights

log = logging.getLogger(__name__)

def unique_chunks(x, z):
    from mceditlib import multi_block

    cPos = multi_block.chunkPosArray(x, z)
    elements, inverse = numpy.unique(cPos, return_inverse=True)
    return multi_block.decodeChunkPos(elements)


def updateHeightmap(dimension, x, y, z):
    """

    :param dimension:
    :type dimension: mceditlib.worldeditor.WorldEditorDimension
    :type x: numpy.ndarray
    :type y: numpy.ndarray
    :type z: numpy.ndarray
    :return:
    :rtype:
    """
    blocktypes = dimension.blocktypes
    blocktypeOpacity = numpy.array(blocktypes.opacity)
    numpy.clip(blocktypeOpacity, 1, 15, blocktypeOpacity)
    blocktypeOpacity.dtype = 'int8'

    chunkPos = unique_chunks(x, z)
    for i, (cx, cz) in enumerate(chunkPos):
        chunk = dimension.getChunk(cx, cz)
        HeightMap = chunk.HeightMap
        if HeightMap is None:
            return  # Level does not have heightmaps.

        newHeightMap = numpy.zeros_like(HeightMap)
        for cy in reversed(chunk.sectionPositions()):
            section = chunk.getSection(cy)
            opacity = blocktypes.opacity[section.Blocks]
            heights = extractHeights(opacity)
            heights[heights > 0] += cy << 4

            numpy.maximum(newHeightMap, heights, newHeightMap)
        #
        changedHM = newHeightMap != HeightMap
        chunk.HeightMap[:] = newHeightMap

        #
        # for ix, iz in changedHM:
        #     new = newHeightMap[iz, ix]
        #     old = HeightMap[iz, ix]
        #     if new < old:
        #         for iy in range(old):
        #
        updatePos = []
        z, x = changedHM.nonzero()
        for cy in reversed(chunk.sectionPositions()):
            newHeight = newHeightMap[z, x]
            belowSection = newHeight < cy << 4
            section = chunk.getSection(cy)
            section.SkyLight[:, z[belowSection], x[belowSection]] = 15
            aboveSection = newHeight >= (cy+1) << 4
            section.SkyLight[:, z[aboveSection], x[aboveSection]] = 0
            inSection = ~belowSection & ~aboveSection
            y = newHeight[inSection]
            if not y.size:
                continue

            sectionTop = y - (cy << 4)
            # repeat each pair of coordinates in z,x a number of times equal to sectionTop[z, x]
            # construct a y coordinate array equal to concatenated ranges of 0..sectionTop[z,x]
            # such that its length is equal to the first two arrays'
            iz = z[inSection]
            ix = x[inSection]
            section.SkyLight[:, iz, ix] = 15
            rz = numpy.repeat(iz, sectionTop)
            rx = numpy.repeat(ix, sectionTop)
            ry = numpy.concatenate([numpy.arange(s) for s in sectionTop])
            section.SkyLight[ry, rz, rx] = 0

            updatePos.append((y, iz, ix))
        #
        #
        # for x, z in itertools.product(xrange(16), xrange(16)):
        #     if changedHM[z, x] == False:
        #         continue
        #     for cy in reversed(chunk.sectionPositions()):
        #         section = chunk.getSection(cy)
        #         newHeight = newHeightMap[z, x]
        #         if newHeight < cy << 4:
        #             section.SkyLight[:, z, x] = 15
        #             continue
        #         if newHeight >= (cy+1) << 4:
        #             section.SkyLight[:, z, x] = 0
        #             continue
        #
        #         section.SkyLight[newHeight & 0xf:16, z, x] = 15
        #         updatePos.append((newHeight-1, z + cz << 4, x + cx << 4))
        #
        if not len(updatePos):
            return
        if not ENABLE_LIGHTING:
            return

        ys, zs, xs = zip(*updatePos)
        uy = numpy.concatenate(ys)
        uz = numpy.concatenate(zs)
        uz += cz << 4
        ux = numpy.concatenate(xs)
        ux += cx << 4

        result = dimension.getBlocks(ux, uy, uz)
        opacity = blocktypeOpacity[result.Blocks]
        newLight = -opacity + 15
        newLight.dtype = 'int8'
        numpy.clip(newLight, 0, 15, newLight)

        while True:
            dimension.setBlocks(ux, uy, uz, SkyLight=newLight)
            stillBright = newLight > 0
            if not len(stillBright):
                break
            ux = ux[stillBright]
            uy = uy[stillBright]
            uz = uz[stillBright]
            newLight = newLight[stillBright]
            uy -= 1

            result = dimension.getBlocks(ux, uy, uz)
            opacity = blocktypeOpacity[result.Blocks]
            newLight = newLight - opacity
            newLight.dtype = 'int8'
            numpy.clip(newLight, 0, 15, newLight)


ENABLE_LIGHTING = True

def updateLightsInSelection(dimension, selection):
    # xxx slow
    x, y, z = numpy.array(selection.positions).T
    return updateLightsByCoord(dimension, x, y, z)

def updateLightsByCoord(dimension, x, y, z):
    """

    :param dimension:
    :type dimension: mceditlib.worldeditor.WorldEditorDimension
    :type x: numpy.ndarray
    :type y: numpy.ndarray
    :type z: numpy.ndarray
    :return:
    :rtype:
    """
    updateHeightmap(dimension, x, y, z)
    if not ENABLE_LIGHTING:
        return
    brightness = numpy.array(dimension.blocktypes.brightness)
    brightness.dtype = 'int8'

    opacity = numpy.array(dimension.blocktypes.opacity)
    numpy.clip(opacity, 1, 15, opacity)
    opacity.dtype = 'int8'
    assert opacity[0] == 1
    result = dimension.getBlocks(x, y, z, return_BlockLight=True)
    brightness = numpy.maximum(brightness[result.Blocks], result.BlockLight)

    dimension.setBlocks(x, y, z, BlockLight=brightness, updateLights=False)
    # x+

    def go(dx, dy, dz, x, y, z, brightness):
        nx = x + dx if dx else x
        ny = y + dy if dy else y
        nz = z + dz if dz else z
        # log.info("xyz %s", (nx, ny, nz))

        nextResult = dimension.getBlocks(nx, ny, nz, return_BlockLight=True)
        nextOpacity = opacity[nextResult.Blocks]
        # log.info("nextOpacity %s", nextOpacity)
        nextBrightness = brightness - nextOpacity
        numpy.clip(nextBrightness, 0, 15, nextBrightness)
        # log.info("nextBrightness %s > %s", nextBrightness, nextResult.BlockLight)
        nextChanged = nextBrightness > nextResult.BlockLight
        #nextChanged &= (nextBrightness != 0)
        # log.info("nextChanged %s", nextChanged)
        nextBrightness = nextBrightness[nextChanged]
        if 0 == nextBrightness.size:
            return
        # log.info("nextBrightness[nextChanged] %s", nextBrightness)
        cx = nx[nextChanged]
        cy = ny[nextChanged]
        cz = nz[nextChanged]
        # log.info("xyz[nextChanged] %s", (cx, cy, cz))

        dimension.setBlocks(cx, cy, cz,
                            BlockLight=nextBrightness,
                            updateLights=False)
        # r = dimension.getBlocks(cx, cy, cz,
        #                     return_BlockLight=True,
        #                     )
        # assert r.BlockLight == nextBrightness, "Expected %s to be %s" % (r.BlockLight, nextBrightness)

        #recurse(cx, cy, cz, nextBrightness)
        return cx, cy, cz

    def goNeighbors(x, y, z, brightness):
        result = []
        result.append(go(1, 0, 0, x, y, z, brightness))
        result.append(go(-1, 0, 0, x, y, z, brightness))
        result.append(go(0, 1, 0, x, y, z, brightness))
        result.append(go(0, -1, 0, x, y, z, brightness))
        result.append(go(0, 0, 1, x, y, z, brightness))
        result.append(go(0, 0, -1, x, y, z, brightness))
        result = [r for r in result if r is not None]
        if not len(result):
            return [], [], [], []
        x, y, z = zip(*result)
        #log.info("SHAPE %s", [a.shape for a in x])
        x = numpy.concatenate(x)
        y = numpy.concatenate(y)
        z = numpy.concatenate(z)

        result = dimension.getBlocks(x, y, z, return_BlockLight=True)
        return x, y, z, result.BlockLight

    while len(x):
 #       coords = zip(x, y, z, brightness)
 #       log.info("Lighting step:\n%s", pprint.pformat(coords))
        x, y, z, brightness = goNeighbors(x, y, z, brightness)
