"""
    __init__.py
"""
from __future__ import absolute_import, division, print_function
import itertools
import logging
import operator
import numpy
from mceditlib import faces
from mceditlib.geometry import Vector

log = logging.getLogger(__name__)


class ISelection(object):
    """
    Interface for block selections that can have any shape. Used by block_copy and block_fill.

    BoundingBox is the only provider for now.

    :ivar chunkPositions(): List or iterator of (cx, cz) coordinates for the chunks within this selection
    """
    chunkPositions = NotImplemented

    def __contains__(self, (x, y, z)):
        """
        Return True if the given set of coordinates is within this selection.

        :rtype: bool
        """

    def contains_coords(self, x, y, z):
        """
        Return an array of boolean values indicating which of the x, y, z coordinate pairs are within this
        selection. x, y, and z must be numpy arrays of the same shape, and the return value will be a numpy
        array of the same shape.

        :rtype: ndarray(shape=x.shape, dtype=bool)
        """

    def containsChunk(self, cx, cz):
        """
        Return True if the given chunk is in this selection

        :param cx: Chunk X position
        :type cx: int
        :param cz: Chunk Z position
        :type cz: int
        :rtype: boolean
        """

    def sectionPositions(self, cx, cz):
        """
        Return a list of cy values contained in the given chunk

        :param cx: Chunk X position
        :type cx: int
        :param cz: Chunk Z position
        :type cz: int
        :return: Chunk Y positions
        :rtype: iterator of ints
        """

    def box_mask(self, box):
        """
        Construct and return a contiguous 3-d array of boolean values corresponding to the part
         of this selection within the given box. The returned array's coordinates will be ordered YZX.

        :returns: Mask array, ordered YZX
        :rtype: ndarray(shape=(box.height, box.length, box.width), dtype=bool)
        """

    def section_mask(self, cx, cy, cz):
        """
        Construct and return a 16x16x16 array of boolean values indicating which of the 4096 blocks within the given
        section cube are within this selection. The returned array's coordinates will be ordered YZX. The default implementation
        calls box_mask with a box constructed for the section's bounds.

        :returns: Mask array, ordered YZX
        :rtype: ndarray(shape=(16, 16, 16), dtype=bool)
        """


class SelectionBox(object):
    def __and__(self, other):
        return IntersectionBox(self, other)

    def __or__(self, other):
        return UnionBox(self, other)

    def __add__(self, other):
        return UnionBox(self, other)

    def __sub__(self, other):
        return DifferenceBox(self, other)

    def section_mask(self, cx, cy, cz):
        return self.box_mask(SectionBox(cx, cy, cz))

    def box_mask(self, box):
        raise NotImplementedError


class CombinationBox(SelectionBox):
    oper = NotImplemented

    def __init__(self, left, right):
        self.left = left
        self.right = right

    def __contains__(self, item):
        return self.left.contains(item) or self.right.contains(item)

    def contains_coords(self, x, y, z):
        left = self.left.contains_coords(x, y, z)
        right = self.left.contains_coords(x, y, z)
        if left is None:
            return right
        if right is None:
            return left
        return self.oper(left, right)

    def box_mask(self, box):
        left = self.left.box_mask(box)
        right = self.right.box_mask(box)
        if left is None:
            return right
        if right is None:
            return left
        return self.oper(left, right)

    def sectionPositions(self, cx, cz):
        left = self.left.sectionPositions(cx, cz)
        right = self.right.sectionPositions(cx, cz)
        sections = set()
        sections.update(left)
        sections.update(right)
        return sorted(sections)


class UnionBox(CombinationBox):
    oper = operator.or_


class IntersectionBox(CombinationBox):
    oper = operator.and_


class DifferenceBox(CombinationBox):
    oper = lambda a, b: a & (~b)


def SectionBox(cx, cy, cz, section=None):
    if section is None:
        shape = 16, 16, 16
    else:
        shape = section.Blocks.shape  # XXX needed because FakeChunkedLevel returns odd sized sections - fix with storage adapter
        shape = shape[2], shape[0], shape[1]

    return BoundingBox(Vector(cx, cy, cz) * 16, shape)


def rayIntersectsBox(box, ray):
    """
    Return a list of (point, face) pairs for each side of the box intersected by ray. The list is sorted by distance
    from the ray's origin, nearest to furthest.

    :param box:
    :type box:
    :param ray:
    :type ray:
    :return:
    :rtype:
    """
    nearPoint, vector = ray

    intersections = []

    #        glPointSize(5.0)
    #        glColor(1.0, 1.0, 0.0, 1.0)
    #        glBegin(GL_POINTS)

    for dim in range(3):
        dim1 = dim + 1
        dim2 = dim + 2
        dim1 %= 3
        dim2 %= 3

        def pointInBounds(point, x):
            return box.origin[x] <= point[x] <= box.maximum[x]

        neg = vector[dim] < 0

        for side in 0, 1:
            d = (box.maximum, box.origin)[side][dim] - nearPoint[dim]

            if d >= 0 or (neg and d <= 0):
                if vector[dim]:
                    scale = d / vector[dim]
                    intersect = vector * scale + nearPoint

                    if pointInBounds(intersect, dim1) and pointInBounds(intersect, dim2):
                        intersections.append((intersect, faces.Face(dim * 2 + side)))

    if not len(intersections):
        return None
    # Get the distance from the viewing plane for each intersection point

    byDistance = [((point - nearPoint).lengthSquared(), point, face)
                  for point, face in intersections]

    byDistance.sort(key=lambda a: a[0])

    return [a[1:] for a in byDistance]


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


class BoundingBox(SelectionBox):
    type = int

    def __init__(self, origin=(0, 0, 0), size=(0, 0, 0), maximum=None):
        if isinstance(origin, BoundingBox):
            self._origin = origin._origin
            self._size = origin._size
        else:
            self._origin = Vector(*(self.type(a) for a in origin))
            if maximum is not None:
                maximum = Vector(*maximum)
                self._size = maximum - self._origin
            else:
                self._size = Vector(*(self.type(a) for a in size))

    def __repr__(self):
        return "%s(origin=%s, size=%s)" % (self.__class__.__name__, self.origin, self.size)

    def __iter__(self):
        return iter((self._origin, self._size))

    def __len__(self):
        return 2

    def __getattr__(self, item):
        if item == 0:
            return self._origin
        elif item == 1:
            return self._size
        else:
            raise IndexError

    @property
    def origin(self):
        """
        The smallest position in the box
        :rtype: Vector
        """
        return self._origin

    @property
    def size(self):
        """
        The size of the box
        :rtype: Vector
        """
        return self._size

    @property
    def width(self):
        """The dimension along the X axis"""
        return self._size.x

    @property
    def height(self):
        """The dimension along the Y axis"""
        return self._size.y

    @property
    def length(self):
        """The dimension along the Z axis"""
        return self._size.z

    @property
    def minx(self):
        return self.origin.x

    @property
    def miny(self):
        return self.origin.y

    @property
    def minz(self):
        return self.origin.z

    @property
    def maxx(self):
        return self.origin.x + self.size.x

    @property
    def maxy(self):
        return self.origin.y + self.size.y

    @property
    def maxz(self):
        return self.origin.z + self.size.z

    @property
    def maximum(self):
        "The largest point of the box; origin plus size."
        return self._origin + self._size

    @property
    def volume(self):
        "The volume of the box in blocks"
        return self.size.x * self.size.y * self.size.z

    @property
    def positions(self):
        """iterate through all of the positions within this selection box"""
        return itertools.product(
            xrange(self.minx, self.maxx),
            xrange(self.miny, self.maxy),
            xrange(self.minz, self.maxz)
        )

    def intersect(self, box):
        """
        Return a box containing the area self and box have in common. Box will have zero volume
         if there is no common area.
        """
        #if (self.minx > box.maxx or self.maxx < box.minx or
        #            self.miny > box.maxy or self.maxy < box.miny or
        #            self.minz > box.maxz or self.maxz < box.minz):
        #    #Zero size intersection.
        #    return BoundingBox()

        origin = Vector(
            max(self.minx, box.minx),
            max(self.miny, box.miny),
            max(self.minz, box.minz),
        )
        maximum = Vector(
            min(self.maxx, box.maxx),
            min(self.maxy, box.maxy),
            min(self.maxz, box.maxz),
        )
        size = maximum - origin
        if any(s<=0 for s in size):
            return ZeroBox
        #print "Intersect of {0} and {1}: {2}".format(self, box, newbox)
        return self.__class__(origin, size)

    def union(self, box):
        """
        Return a box large enough to contain both self and box.
        """
        origin = Vector(
            min(self.minx, box.minx),
            min(self.miny, box.miny),
            min(self.minz, box.minz),
        )
        maximum = Vector(
            max(self.maxx, box.maxx),
            max(self.maxy, box.maxy),
            max(self.maxz, box.maxz),
        )
        return self.__class__(origin, maximum - origin)

    def expand(self, dx, dy=None, dz=None):
        """
        Return a new box with boundaries expanded by dx, dy, dz.
        If only dx is passed, expands by dx in all dimensions.
        """
        if dz is None:
            dz = dx
        if dy is None:
            dy = dx

        origin = self.origin - (dx, dy, dz)
        size = self.size + (dx * 2, dy * 2, dz * 2)

        return self.__class__(origin, size)

    def __contains__(self, (x, y, z)):
        if x < self.minx or x >= self.maxx:
            return False
        if y < self.miny or y >= self.maxy:
            return False
        if z < self.minz or z >= self.maxz:
            return False

        return True

    def __cmp__(self, b):
        return cmp((self.origin, self.size), None if b is None else (b.origin, b.size))

    def containsChunk(self, cx, cz):
        return self.mincx <= cx < self.maxcx and self.mincz <= cz < self.maxcz
    #
    #def containsSection(self, cx, cy, cz):
    #    return self.mincx <= cx < self.maxcx and self.mincy <= cy < self.maxcy and self.mincz <= cz < self.maxcz

    def contains_coords(self, x, y, z):
        mask = x >= self.minx
        mask &= x < self.maxx
        mask &= y >= self.miny
        mask &= y < self.maxy
        mask &= z >= self.minz
        mask &= z < self.maxz

        return mask

    def box_mask(self, box):
        """

        :param box: BoundingBox
        :return: :rtype: ndarray | None
        """
        selection_box = self.intersect(box)
        if selection_box.volume == 0:
            return None

        mask = numpy.zeros((box.height, box.length, box.width), dtype=bool)

        mask[
            selection_box.miny - box.miny:selection_box.maxy - box.miny,
            selection_box.minz - box.minz:selection_box.maxz - box.minz,
            selection_box.minx - box.minx:selection_box.maxx - box.minx,
        ] = True
        return mask

    # --- Chunk/Section positions ---

    @property
    def mincx(self):
        """The smallest chunk position contained in this box"""
        return self.origin.x >> 4

    @property
    def mincy(self):
        """The smallest section position contained in this box"""
        return self.origin.y >> 4

    @property
    def mincz(self):
        """The smallest chunk position contained in this box"""
        return self.origin.z >> 4

    @property
    def maxcx(self):
        """The largest chunk position contained in this box"""
        return ((self.origin.x + self.size.x - 1) >> 4) + 1

    @property
    def maxcy(self):
        """The largest section position contained in this box"""
        return ((self.origin.y + self.size.y - 1) >> 4) + 1

    @property
    def maxcz(self):
        """The largest chunk position contained in this box"""
        return ((self.origin.z + self.size.z - 1) >> 4) + 1

    def chunkBox(self, level):
        """Returns this box extended to the chunk boundaries of the given level"""
        box = self
        return BoundingBox((box.mincx << 4, level.bounds.miny, box.mincz << 4),
                           (box.maxcx - box.mincx << 4, level.bounds.height, box.maxcz - box.mincz << 4))

    def chunkPositions(self):
        #iterate through all of the chunk positions within this selection box
        return itertools.product(xrange(self.mincx, self.maxcx), xrange(self.mincz, self.maxcz))

    def sectionPositions(self, cx=0, cz=0):
        #iterate through all of the section positions within this chunk
        return range(self.mincy, self.maxcy)

    @property
    def chunkCount(self):
        return (self.maxcx - self.mincx) * (self.maxcz - self.mincz)

    @property
    def isChunkAligned(self):
        return (self.origin.x & 0xf == 0) and (self.origin.z & 0xf == 0)

ZeroBox = BoundingBox((0, 0, 0), (0, 0, 0))

class FloatBox(BoundingBox):
    type = float


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

