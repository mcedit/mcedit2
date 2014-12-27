"""
    heightmaps.py

    Functions for computing general heightmaps and updating the special HeightMap
    attribute of modern chunks.
"""
from __future__ import absolute_import

from numpy import zeros, argmax
import numpy
#
#
# def computeChunkHeightMap(chunk, HeightMap=None):
#     """Computes the HeightMap array for a chunk, which stores the lowest
#     y-coordinate of each column where the sunlight is still at full strength.
#     The HeightMap array is indexed z,x contrary to the blocks array which is x,z,y.
#
#     If HeightMap is passed, fills it with the result and returns it. Otherwise, returns a
#     new array.
#     """
#     sectionHeights = []
#     for cy in chunk.sectionPositions():
#         section = chunk.getSection(cy)
#         if section is None:
#             continue
#
#         opaques = chunk.blocktypes.opacity[section.Blocks]
#         h = extractHeights(opaques)
#         h += (cy << 4)
#         sectionHeights.append(h)
#
#     if len(sectionHeights):
#         heights = sectionHeights.pop(0)
#         for h in sectionHeights:
#             numpy.maximum(heights, h, out=heights)
#
#         heights = heights.swapaxes(0, 1)
#     else:
#         heights = numpy.zeros((16, 16), 'uint32')
#
#     if HeightMap is None:
#         return heights.astype('uint8')
#     else:
#         HeightMap[:] = heights
#         return HeightMap

def extractHeights(array):
    """ Given an array of bytes shaped (y, z, x), return the coordinates of the highest
    non-zero value in each y-column into heightMap
    """

    # The fastest way I've found to do this is to make a boolean array with >0,
    # then turn it upside down with ::-1 and use argmax to get the _first_ nonzero
    # from each column.

    l, w = array.shape[1:]
    heightMap = numpy.empty((l, w), 'int16')

    heights = argmax((array > 0)[::-1], 0)
    heights = array.shape[0] - heights

    # if the entire column is air, argmax finds the first air block and the result is a top height column
    # top height columns won't ever have air in the top block so we can find air columns by checking for both
    heights[(array[-1] == 0) & (heights == array.shape[0])] = 0

    heightMap[:] = heights

    return heightMap
