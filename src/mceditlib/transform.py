"""
    transform
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import math
import itertools

import numpy as np

from mceditlib.blocktypes.rotation import BlockRotations, blankRotationTable
from mceditlib.cachefunc import lru_cache_object
from mceditlib.geometry import Vector
from mceditlib.multi_block import getBlocks
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
    # matrix goes from dest to source; we need source to dest here, so get inverse
    matrix = np.linalg.inv(matrix)
    corners = np.array(boundsCorners(bounds))
    corners = np.hstack([corners, ([1],)*8])
    corners = corners * matrix
    
    minx = math.floor(min(corners[:, 0]))
    miny = math.floor(min(corners[:, 1]))
    minz = math.floor(min(corners[:, 2]))
    maxx = math.ceil(max(corners[:, 0]))
    maxy = math.ceil(max(corners[:, 1]))
    maxz = math.ceil(max(corners[:, 2]))
    
    # Why? Weird hacks for rotation?
    
    # if maxx % 1:
    #     maxx += 1
    # if maxy % 1:
    #     maxy += 1
    # if maxz % 1:
    #     maxz += 1

    newbox = BoundingBox(origin=Vector(minx, miny, minz).intfloor(),
                         maximum=Vector(maxx, maxy, maxz).intfloor())
    return newbox


def transformationMatrix(anchor, rotation, scale):
    rotX, rotY, rotZ = rotation
    
    scaleInv = tuple([1.0/c if c != 0 else 1.0 for c in scale])
    
    translate = np.matrix(np.identity(4))
    translate[3, 0] = anchor[0]
    translate[3, 1] = anchor[1]
    translate[3, 2] = anchor[2]
    
    scaleMatrix = np.matrix(np.identity(4))
    scaleMatrix[0, 0] = scaleInv[0]
    scaleMatrix[1, 1] = scaleInv[1]
    scaleMatrix[2, 2] = scaleInv[2]

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

    matrix = scaleMatrix * matrix

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

    angle %= 360

    exact_sin = {
        0: 0,
        90: 1,
        180: 0,
        270: -1,
    }
    exact_cos = {
        0: 1,
        90: 0,
        180: -1,
        270: 0,
    }

    if angle % 90 != 0:
        s = math.sin(math.radians(angle))
        c = math.cos(math.radians(angle))
    else:
        s = exact_sin[angle]
        c = exact_cos[angle]

    rotate = np.matrix([[x*x*(1-c)+c,    x*y*(1-c)-z*s,  x*z*(1-c)+y*s,  0],
                           [y*x*(1-c)+z*s,  y*y*(1-c)+c,    y*z*(1-c)-x*s,  0],
                           [x*z*(1-c)-y*s,  y*z*(1-c)+x*s,  z*z*(1-c)+c,    0],
                           [0,              0,              0,              1]])
    # xxx rescale
    return rotate


class TransformedSection(object):
    def __init__(self, transform, cx, cy, cz):
        self.transform = transform
        self.cx = cx
        self.Y = cy
        self.cz = cz

        self.transform.initSection(self)

    @property
    def blocktypes(self):
        return self.transform.blocktypes

class TransformedChunk(object):
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


class DimensionTransformBase(object):
    def __init__(self, dimension):
        self.dimension = dimension
        self.sectionCache = lru_cache_object(self._createSection, 1000)

    _transformedBounds = NotImplemented

    def _createSection(self, cx, cy, cz):
        return TransformedSection(self, cx, cy, cz)

    def getChunk(self, cx, cz):
        return TransformedChunk(self, cx, cz)

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

    def getBlocks(self, x, y, z,
                  return_Blocks=True,
                  return_Data=False,
                  return_BlockLight=False,
                  return_SkyLight=False,
                  return_Biomes=False):
        return getBlocks(self, x, y, z,
                         return_Blocks,
                         return_Data,
                         return_BlockLight,
                         return_SkyLight,
                         return_Biomes)

class SelectionTransform(DimensionTransformBase):
    def __init__(self, dimension, selection):
        """
        SelectionTransform is a simple wrapper around a dimension that restricts
        the blocks and chunks in the dimension to those selected by the given
        selection. It can be used anywhere a WorldEditorDimension is usable.

        Parameters
        ----------

        dimension: WorldEditorDimension
            The dimension to restrict

        selection: ISelection
            The selection to apply

        Returns
        -------

        transformedDimension: SelectionTransform
            A wrapper around the dimension, displaying only the selected blocks.
        """
        super(SelectionTransform, self).__init__(dimension)
        self._transformedBounds = selection

    def initSection(self, section):
        shape = (16, 16, 16)
        cx, cy, cz = section.cx, section.Y, section.cz

        section.Blocks = np.zeros(shape, dtype='uint16')
        section.Data = np.zeros(shape, dtype='uint8')

        if self.dimension.containsChunk(cx, cz):
            chunk = self.dimension.getChunk(cx, cz)
            baseSection = chunk.getSection(cy)
            if baseSection is not None:
                sectionMask = self._transformedBounds.section_mask(cx, cy, cz)
                section.Blocks[sectionMask] = baseSection.Blocks[sectionMask]
                section.Data[sectionMask] = baseSection.Data[sectionMask]


class DimensionTransform(DimensionTransformBase):
    def __init__(self, dimension, anchor, rotation=(0, 0, 0), scale=(1, 1, 1)):
        """
        A wrapper around a WorldEditorDimension that applies a three-dimensional rotation
        around a given anchor point. The wrapped dimension's bounds will be different from the
        original dimension.

        Parameters
        ----------

        dimension: mceditlib.worldeditor.WorldEditorDimension
            The dimension to wrap and apply rotations to

        anchor: mceditlib.geometry.Vector
            The point to rotate and scale the dimension around

        rotation: float[3]
            The angles to rotate the dimension around, along each axis respectively.
            The angles are given in degrees.
            
        scale: float[3]
            The scales to resize the dimension along each axis respectively. 1.0 is
            normal size.

        Returns
        -------

        transformedDimension: DimensionTransform
            A dimension that acts as a rotated version of the given dimension.
        """
        super(DimensionTransform, self).__init__(dimension)
        rotX, rotY, rotZ = rotation
        self.rotX = rotX
        self.rotY = rotY
        self.rotZ = rotZ
        self.anchor = anchor
        self.scale = scale

        self.matrix = transformationMatrix(anchor, rotation, scale)

        blockRotation = BlockRotations(dimension.blocktypes)
        rotationTable = blankRotationTable()

        while rotX >= 135.0:
            rotX -= 180
            rotationTable = blockRotation.rotateX180[rotationTable[..., 0], rotationTable[..., 1]]
        while rotX >= 45.0:
            rotX -= 90
            rotationTable = blockRotation.rotateX90[rotationTable[..., 0], rotationTable[..., 1]]
        while rotY >= 45.0:
            rotY -= 90
            rotationTable = blockRotation.rotateY90[rotationTable[..., 0], rotationTable[..., 1]]
        while rotZ >= 135.0:
            rotZ -= 180
            rotationTable = blockRotation.rotateZ180[rotationTable[..., 0], rotationTable[..., 1]]
        while rotZ >= 45.0:
            rotZ -= 90
            rotationTable = blockRotation.rotateZ90[rotationTable[..., 0], rotationTable[..., 1]]

        self.rotationTable = rotationTable

        self._transformedBounds = transformBounds(dimension.bounds, self.matrix)

    def initSection(self, section):
        shape = (16, 16, 16)

        section.Blocks = np.zeros(shape, dtype='uint16')
        section.Data = np.zeros(shape, dtype='uint8')

        y, z, x = np.indices(shape)

        x += (section.cx << 4)
        y += (section.Y << 4)
        z += (section.cz << 4)
        w = np.ones(x.shape)

        x = x.ravel()
        y = y.ravel()
        z = z.ravel()
        w = w.ravel()

        coords = np.vstack([x, y, z, w]).T

        transformed_coords = coords * self.matrix
        transformed_coords = np.floor(transformed_coords).astype('int32')
        x, y, z, w = transformed_coords.T

        result = self.dimension.getBlocks(x, y, z, return_Data=True)
        blocks = result.Blocks.reshape(shape)
        data = result.Data.reshape(shape)
        rotated = self.rotationTable[blocks, data]

        section.Blocks[:] = rotated[..., 0]
        section.Data[:] = rotated[..., 1]
