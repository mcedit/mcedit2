"""
    transform
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import math
import itertools

import numpy as np
from mceditlib.cachefunc import lru_cache_object
from mceditlib.geometry import Vector
from mceditlib.selection import BoundingBox

log = logging.getLogger(__name__)

def boundsCorners(bounds):
    corners = itertools.product(
        (bounds.minx, bounds.maxx),
        (bounds.miny, bounds.maxy),
        (bounds.minz, bounds.maxz),
    )
    return list(corners)

def transformBounds(bounds, matrix):
    corners = np.array(boundsCorners(bounds))
    corners = np.hstack([corners, ([1],)*8])
    corners = corners * matrix

    minx = min(corners[:, 0])
    miny = min(corners[:, 1])
    minz = min(corners[:, 2])
    maxx = max(corners[:, 0])
    maxy = max(corners[:, 1])
    maxz = max(corners[:, 2])

    newbox = BoundingBox(origin=Vector(minx, miny, minz).intfloor(),
                         maximum=Vector(maxx, maxy, maxz).intfloor())
    return newbox


def rotationMatrix(anchor, rotX, rotY, rotZ):
    translate = np.matrix(np.identity(4))
    translate[3, 0] = anchor[0]
    translate[3, 1] = anchor[1]
    translate[3, 2] = anchor[2]

    reverse_translate = np.matrix(np.identity(4))
    reverse_translate[3, 0] = -anchor[0]
    reverse_translate[3, 1] = -anchor[1]
    reverse_translate[3, 2] = -anchor[2]

    matrix = translate

    if rotX:
        matrix = npRotate('x', rotX) * matrix
    if rotY:
        matrix = npRotate('y', rotY) * matrix
    if rotZ:
        matrix = npRotate('z', rotZ) * matrix

    matrix = reverse_translate * matrix
    return matrix


def npRotate(axis, angle):
    # ( xx(1-c)+c	xy(1-c)-zs  xz(1-c)+ys	 0  )
    # | yx(1-c)+zs	yy(1-c)+c   yz(1-c)-xs	 0  |
    # | xz(1-c)-ys	yz(1-c)+xs  zz(1-c)+c	 0  |
    # (	 0	        0		    0	         1  )
    # axis:
    # "x": (1, 0, 0)
    # "y": (0, 1, 0)
    # "z": (0, 0, 1)
    x = y = z = 0
    if axis == "x":
        x = 1
    elif axis == "y":
        y = 1
    elif axis == "z":
        z = 1
    else:
        raise ValueError("Unknown axis: %r" % axis)

    s = math.sin(math.radians(angle))
    c = math.cos(math.radians(angle))
    rotate = np.matrix([[x*x*(1-c)+c,    x*y*(1-c)-z*s,  x*z*(1-c)+y*s,  0],
                           [y*x*(1-c)+z*s,  y*y*(1-c)+c,    y*z*(1-c)-x*s,  0],
                           [x*z*(1-c)-y*s,  y*z*(1-c)+x*s,  z*z*(1-c)+c,    0],
                           [0,              0,              0,              1]])
    # xxx rescale
    return rotate


class RotatedSection(object):
    def __init__(self, transform, cx, cy, cz):
        self.transform = transform
        self.cx = cx
        self.Y = cy
        self.cz = cz
        
        shape = (16, 16, 16)

        self.Blocks = np.zeros(shape, dtype='uint16')
        self.Data = np.zeros(shape, dtype='uint8')

        y, z, x = np.indices(shape)

        x += (cx << 4)
        y += (cy << 4)
        z += (cz << 4)
        w = np.ones(x.shape)

        x = x.ravel()
        y = y.ravel()
        z = z.ravel()
        w = w.ravel()

        coords = np.vstack([x, y, z, w]).T

        transformed_coords = coords * self.transform.matrix
        transformed_coords = np.floor(transformed_coords).astype('int32')
        x, y, z, w = transformed_coords.T

        result = self.transform.dimension.getBlocks(x, y, z, return_Data=True)
        self.Blocks[:] = result.Blocks.reshape(shape)
        self.Data[:] = result.Data.reshape(shape)

    @property
    def blocktypes(self):
        return self.transform.blocktypes

class RotatedChunk(object):
    def __init__(self, transform, cx, cz):
        self.transform = self.dimension = transform
        self.cx = cx
        self.cz = cz
        self.chunkPosition = cx, cz
        self.Biomes = None
        self.Entities = []
        self.TileEntities = []

    def getSection(self, cy, create=False):
        if create is True:
            return ValueError("Cannot create chunks/sections in RotationTransform")

        return self.transform.sectionCache(self.cx, cy, self.cz)

    def sectionPositions(self):
        return self.transform.bounds.sectionPositions(self.cx, self.cz)

    @property
    def blocktypes(self):
        return self.transform.blocktypes

class RotationTransform(object):
    def __init__(self, dimension, anchor, rotX, rotY, rotZ):
        self.rotX = rotX
        self.rotY = rotY
        self.rotZ = rotZ
        self.anchor = anchor
        self.dimension = dimension

        self.matrix = rotationMatrix(anchor, rotX, rotY, rotZ)

        self._transformedBounds = transformBounds(dimension.bounds, self.matrix)

        self.sectionCache = lru_cache_object(self._createSection, 1000)

    def _createSection(self, cx, cy, cz):
        return RotatedSection(self, cx, cy, cz)

    def getChunk(self, cx, cz):
        return RotatedChunk(self, cx, cz)

    def chunkCount(self):
        return self.bounds.chunkCount

    def chunkPositions(self):
        return self.bounds.chunkPositions()

    def containsChunk(self, cx, cz):
        return self.bounds.containsChunk(cx, cz)

    def getBlockID(self, x, y, z):
        # (x, y, z, 1) * self.matrix
        return self.dimension.getBlockID(x, y, z)

    @property
    def blocktypes(self):
        return self.dimension.blocktypes

    @property
    def bounds(self):
        return self._transformedBounds