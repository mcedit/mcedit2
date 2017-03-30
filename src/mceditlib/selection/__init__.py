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
    Interface for block selections that can have any shape. Used by copy and fill
    operations, among others.

    BoundingBox is the only provider for now.

    :ivar chunkPositions(): List or iterator of (cx, cz) coordinates for the chunks within this selection
    """
    chunkPositions = NotImplemented

    def __contains__(self, xyz):
        """
        Return True if the given set of coordinates is within this selection.

        :rtype: bool
        """
        (x, y, z) = xyz

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
    origin = NotImplemented
    """:type : mceditlib.geometry.Vector"""
    size = NotImplemented
    """:type : mceditlib.geometry.Vector"""

    def __and__(self, other):
        return IntersectionBox(self, other)

    def __or__(self, other):
        return UnionBox(self, other)

    def __add__(self, other):
        return UnionBox(self, other)

    def __sub__(self, other):
        return DifferenceBox(self, other)

    def __invert__(self):
        return InvertedBox(self)

    def section_mask(self, cx, cy, cz):
        """
        Return a mask delimiting the block positions in the given selection. The mask
        is a 3D boolean array with indices ordered YZX. If no blocks in the given section
        are selected, returns None.

        Parameters
        ----------
        cx : int
        cy : int
        cz : int

        Returns
        -------
        mask : numpy.ndarray | None

        """
        return self.box_mask(SectionBox(cx, cy, cz))

    def box_mask(self, box):
        """
        Return a boolean mask array for the given bounding box.

        Array indices are ordered YZX.

        Parameters
        ----------
        box : BoundingBox

        Returns
        -------
        mask : ndarray | None
        """
        raise NotImplementedError

    @property
    def positions(self):
        """
        Return an iterator over the block positions in this section. Yields tuples of
        ints (x, y, z).

        Slow. Consider using section_mask with the chunk's sections to operate on blocks
        in parallel.

        Returns
        -------

        positions: Iterator[(int, int, int)]
        """
        for cx, cz in self.chunkPositions():
            for cy in self.sectionPositions(cx, cz):
                mask = self.section_mask(cx, cy, cz)
                y, z, x = mask.nonzero()
                x = x + (cx << 4)
                y = y + (cy << 4)
                z = z + (cz << 4)
                for i in range(len(x)):
                    yield x[i], y[i], z[i]

    mincx = NotImplemented
    mincy = NotImplemented
    mincz = NotImplemented
    maxcx = NotImplemented
    maxcy = NotImplemented
    maxcz = NotImplemented

    def chunkBox(self, level):
        """
        Returns this box extended to the chunk boundaries of the given level
        """
        box = self
        return BoundingBox((box.mincx << 4, level.bounds.miny, box.mincz << 4),
                           (box.maxcx - box.mincx << 4, level.bounds.height, box.maxcz - box.mincz << 4))

    def containsChunk(self, cx, cz):
        return self.mincx <= cx < self.maxcx and self.mincz <= cz < self.maxcz

    def chunkPositions(self):
        """ Iterate through all of the chunk positions within this selection box """
        return itertools.product(xrange(self.mincx, self.maxcx), xrange(self.mincz, self.maxcz))

    def sectionPositions(self, cx, cz):
        """ Iterate through all of the section positions within this chunk"""
        return range(self.mincy, self.maxcy)

    @property
    def chunkCount(self):
        return (self.maxcx - self.mincx) * (self.maxcz - self.mincz)

    @property
    def center(self):
        return self.origin + self.size * 0.5

    @property
    def width(self):
        """The dimension along the X axis"""
        return self.size.x

    @property
    def height(self):
        """The dimension along the Y axis"""
        return self.size.y

    @property
    def length(self):
        """The dimension along the Z axis"""
        return self.size.z

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
        return self.origin + self.size

    @property
    def volume(self):
        "The volume of the box in blocks"
        return self.size.x * self.size.y * self.size.z


class InvertedBox(SelectionBox):
    def __init__(self, base):
        super(InvertedBox, self).__init__()
        self.base = base
        self.mincx = base.mincx
        self.mincy = base.mincy
        self.mincz = base.mincz
        self.maxcx = base.maxcx
        self.maxcy = base.maxcy
        self.maxcz = base.maxcz

    def contains_coords(self, x, y, z):
        return not self.base.contains_coords(x, y, z)

    def box_mask(self, box):
        return ~self.base.box_mask(box)


class CombinationBox(SelectionBox):
    oper = setoper = NotImplemented
    boundsminoper = NotImplemented
    boundsmaxoper = NotImplemented
    box_mask = NotImplemented

    def __init__(self, *selections):
        self.selections = selections
        self.mincx = self.boundsminoper(s.mincx for s in selections)
        self.mincy = self.boundsminoper(s.mincy for s in selections)
        self.mincz = self.boundsminoper(s.mincz for s in selections)
        self.maxcx = self.boundsmaxoper(s.maxcx for s in selections)
        self.maxcy = self.boundsmaxoper(s.maxcy for s in selections)
        self.maxcz = self.boundsmaxoper(s.maxcz for s in selections)

    def __contains__(self, item):
        return self.oper(item in s for s in self.selections)

    def sectionPositions(self, cx, cz):
        positionLists = [set(s.sectionPositions(cx, cz)) for s in self.selections]
        if len(positionLists) == 0:
            return []
        if len(positionLists) == 1:
            return positionLists[0]

        return reduce(self.setoper, positionLists)


class UnionBox(CombinationBox):
    oper = setoper = operator.or_
    boundsminoper = min
    boundsmaxoper = max

    def contains_coords(self, x, y, z):
        contains = [s.contains_coords(x, y, z) for s in self.selections]
        return reduce(self.oper, contains)

    def box_mask(self, box):
        masks = [s.box_mask(box) for s in self.selections]
        masks = [m for m in masks if m is not None]
        if not len(masks):
            return None

        m = masks.pop()

        while len(masks):
            numpy.logical_or(m, masks.pop(), m)

        return m


class IntersectionBox(CombinationBox):
    oper = setoper = operator.and_
    boundsminoper = max
    boundsmaxoper = min

    def contains_coords(self, x, y, z):
        contains = [s.contains_coords(x, y, z) for s in self.selections]
        return reduce(self.oper, contains)

    def box_mask(self, box):
        masks = [s.box_mask(box) for s in self.selections]
        if any(m is None for m in masks):
            return None

        m = masks.pop()

        while len(masks):
            numpy.logical_and(m, masks.pop(), m)

        return m


class DifferenceBox(CombinationBox):
    def oper(self, a, b):
        return a & (~b)

    def setoper(self, a, b):
        return a - b

    def boundsminoper(self, a):
        return iter(a).next()

    def boundsmaxoper(self, a):
        return iter(a).next()

    def contains_coords(self, x, y, z):
        source = self.selections[0].contains_coords(x, y, z)
        if not source:
            return False
        rest = [s.contains_coords(x, y, z) for s in self.selections[1:]]
        rest.insert(0, source)
        return reduce(self.oper, rest)

    def box_mask(self, box):
        source = self.selections[0].box_mask(box)
        if source is None:
            return None
        for s in self.selections[1:]:
            mask = s.box_mask(box)
            if mask is None:
                continue
            source &= (~mask)
        return source


def SectionBox(cx, cy, cz):
    shape = 16, 16, 16

    return BoundingBox(Vector(cx, cy, cz) * 16, shape)


def rayIntersectsBox(box, ray):
    """
    Return a list of (point, face) pairs for each side of the box intersected by ray. The list is
    sorted by distance from the ray's origin, nearest to furthest.

    :param box:
    :type box:
    :param ray:
    :type ray:
    :return:
    :rtype:
    """
    nearPoint, vector = ray

    intersections = []

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

    # Get the distance from the near point for each intersection point
    byDistance = [((point - nearPoint).lengthSquared(), point, face)
                  for point, face in intersections]

    byDistance.sort(key=lambda a: a[0])

    return [d[1:] for d in byDistance]


class BoundingBox(SelectionBox):
    type = int

    def __init__(self, origin=(0, 0, 0), size=(0, 0, 0), maximum=None):
        if isinstance(origin, BoundingBox):
            self._origin = origin._origin
            self._size = origin._size
        else:
            self._origin = Vector(*[self.type(a) for a in origin])
            if maximum is not None:
                maximum = Vector(*maximum)
                self._size = maximum - self._origin
            else:
                self._size = Vector(*[self.type(a) for a in size])

    def __repr__(self):
        return "%s(origin=%s, size=%s)" % (self.__class__.__name__, self.origin, self.size)

    def __iter__(self):
        return iter((self._origin, self._size))

    def __len__(self):
        return 2

    def __getitem__(self, item):
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
        # print "Intersect of {0} and {1}: {2}".format(self, box, newbox)
        # return self.__class__(origin, size)
        return BoundingBox(origin, size)

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
        # return self.__class__(origin, maximum - origin)
        return BoundingBox(origin, maximum - origin)

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

        # return self.__class__(origin, size)
        return BoundingBox(origin, size)

    def __contains__(self, xyz):
        (x, y, z) = xyz
        if x < self.minx or x >= self.maxx:
            return False
        if y < self.miny or y >= self.maxy:
            return False
        if z < self.minz or z >= self.maxz:
            return False

        return True

    def __cmp__(self, b):
        if self.__class__ != b.__class__:
            return cmp(self.__class__, b.__class__)
        return cmp((self.origin, self.size), None if b is None else (b.origin, b.size))

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

    @property
    def isChunkAligned(self):
        return (self.origin.x & 0xf == 0) and (self.origin.z & 0xf == 0)

ZeroBox = BoundingBox((0, 0, 0), (0, 0, 0))

class FloatBox(BoundingBox):
    type = float


class ShapeFuncSelection(BoundingBox):
    def __init__(self, box, shapeFunc):
        """
        Generic class for implementing shaped selections via a shapeFunc callable.

        shapeFunc is called with two arguments:

            blockPositions: Three parallel arrays of coordinates (y, z, x). All arrays have the same
                shape, which may reflect the size of the box requested in calls to box_mask. These
                coordinates are relative to the ShapedSelection's bounding box.

                xxx pass coordinates in world space for things like noise functions??

            selectionShape: The size of this ShapedSelection (y, z, x)

                xxx pass the ShapedSelection itself?

        shapeFunc should return a boolean array with shape equal to the shape of the arrays in
        blockPositions.

        # xxx this init is not compatible with BoundingBox.__init__ and can't intersect

        :type shapeFunc: Callable(blockPositions, selectionShape)
        :type box: BoundingBox
        """
        super(ShapeFuncSelection, self).__init__(box.origin, box.size)
        self.shapeFunc = shapeFunc

    def box_mask(self, box):
        """

        :param box: Area to return a mask array for, in world coordinates
        :type box: BoundingBox
        :return: numpy.ndarray[ndim=3,dtype=bool]
        """
        origin, shape = self.origin, self.size

        # we are returning indices for a Blocks array, so swap axes to YZX
        sx, sy, sz = box.size

        shape = shape[1], shape[2], shape[0]

        # find requested box's coordinates relative to selection
        ox, oy, oz = box.origin
        dx, dy, dz = origin
        ox -= dx
        oy -= dy
        oz -= dz

        # create coordinate array, offset by requested box's origin
        blockPositions = numpy.mgrid[float(oy):oy+sy, oz:oz+sz, ox:ox+sx]

        shape = numpy.array(shape, dtype='float32')

        mask = self.shapeFunc(blockPositions, shape)
        return mask

    def __cmp__(self, b):
        if not isinstance(b, ShapeFuncSelection):
            return -1
        return cmp((self.origin, self.size, self.shapeFunc), (b.origin, b.size, b.shapeFunc))

    @property
    def positions(self):
        for cx, cz in self.chunkPositions():
            for cy in self.sectionPositions(cx, cz):
                mask = self.section_mask(cx, cy, cz)
                y, z, x = mask.nonzero()
                x = x + (cx << 4)
                y = y + (cy << 4)
                z = z + (cz << 4)
                for i in range(len(x)):
                    yield x[i], y[i], z[i]


