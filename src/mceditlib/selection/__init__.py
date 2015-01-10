"""
    __init__.py
"""
from __future__ import absolute_import, division, print_function
import logging
import numpy
from mceditlib.geometry import BoundingBox

log = logging.getLogger(__name__)


def createSelectionMask(brushBox, shapeFunc, requestedBox, chance=100, hollow=False):
    """
    Return a boolean array for a selection with the given shape and style.
    If 'offset' and 'box' are given, then the selection is offset into the world
    and only the part of the world contained in box is returned as an array
    """

    origin, shape = brushBox.origin, brushBox.size

    if chance < 100 or hollow:
        requestedBox = requestedBox.expand(1)

    # we are returning indices for a Blocks array, so swap axes to YZX
    outputShape = requestedBox.size
    outputShape = (outputShape[1], outputShape[2], outputShape[0])

    shape = shape[1], shape[2], shape[0]
    origin = numpy.array(origin) - numpy.array(requestedBox.origin)
    origin = origin[[1, 2, 0]]

    inds = numpy.indices(outputShape, dtype=numpy.float32)
    halfshape = numpy.array([(i >> 1) - ((i & 1 == 0) and 0.5 or 0) for i in shape])

    blockCenters = inds - halfshape[:, None, None, None]
    blockCenters -= origin[:, None, None, None]

    # odd diameter means measure from the center of the block at 0,0,0 to each block center
    # even diameter means measure from the 0,0,0 grid point to each block center

    # if diameter & 1 == 0: blockCenters += 0.5
    shape = numpy.array(shape, dtype='float32')

    mask = shapeFunc(blockCenters, shape)

    if (chance < 100 or hollow) and max(shape) > 1:
        threshold = chance / 100.0
        exposedBlockMask = numpy.ones(shape=outputShape, dtype='bool')
        exposedBlockMask[:] = mask
        submask = mask[1:-1, 1:-1, 1:-1]
        exposedBlockSubMask = exposedBlockMask[1:-1, 1:-1, 1:-1]
        exposedBlockSubMask[:] = False

        for dim in (0, 1, 2):
            slices = [slice(1, -1), slice(1, -1), slice(1, -1)]
            slices[dim] = slice(None, -2)
            exposedBlockSubMask |= (submask & (mask[slices] != submask))
            slices[dim] = slice(2, None)
            exposedBlockSubMask |= (submask & (mask[slices] != submask))

        if hollow:
            mask[~exposedBlockMask] = False
        if chance < 100:
            rmask = numpy.random.random(mask.shape) < threshold

            mask[exposedBlockMask] = rmask[exposedBlockMask]

    if chance < 100 or hollow:
        return mask[1:-1, 1:-1, 1:-1]
    else:
        return mask


class ShapedSelection(BoundingBox):
    def __init__(self, box, shapeFunc, chance=100, hollow=False):
        """

        :type shapeFunc: Style
        :type box: BoundingBox
        """
        super(ShapedSelection, self).__init__(box.origin, box.size)
        self.shapeFunc = shapeFunc
        self.chance = chance
        self.hollow = hollow

    def box_mask(self, box):
        return createSelectionMask(self, self.shapeFunc, box, self.chance, self.hollow)

    def __cmp__(self, b):
        return cmp((self.origin, self.size, self.shapeFunc), None if b is None else (b.origin, b.size, b.shapeFunc))


# --- Shape functions ---


def SphereShape(blockCenters, shape):
    blockCenters *= blockCenters
    shape /= 2
    shape *= shape

    blockCenters /= shape[:, None, None, None]
    distances = sum(blockCenters, 0)
    return distances < 1


def BoxShape(blockCenters, shape):
    blockCenters /= shape[:, None, None, None]  # XXXXXX USING DIVIDE FOR A RECTANGLE

    distances = numpy.absolute(blockCenters).max(0)
    return distances < .5


def DiamondShape(blockCenters, shape):
    blockCenters = numpy.abs(blockCenters)
    shape /= 2
    blockCenters /= shape[:, None, None, None]
    distances = numpy.sum(blockCenters, 0)
    return distances < 1
