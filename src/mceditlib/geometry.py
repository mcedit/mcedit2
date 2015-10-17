"""
   box.py

   Defines two geometric primitives: A ``Vector`` that can represent
   either a point or vector, and an axis-aligned ``BoundingBox`` which is
   made from two Vectors.
"""
from __future__ import absolute_import

from collections import namedtuple
import math
import logging

import numpy

log = logging.getLogger(__name__)

class Vector(namedtuple("_Vector", ("x", "y", "z"))):
    """
    A vector is an x, y, z coordinate triple that provides vector addition,
    multiplication, scaling, and cross products. Vectors are immutable.

    Examples:

        >>> p1 = Vector(10, 0, 3)
        >>> p2 = Vector(4, 5, 6)

    Element access:
        >>> p1.x
        10
        >>> p1.y
        0
        >>> p1.z
        3

    Element access via tuple indexing:
        >>> p1[0]
        10
        >>> p1[1]
        0
        >>> p1[2]
        3

    Vector addition:

        >>> p1 + p2
        Vector(14, 5, 8)
        >>> p2 + (3, 5, 3)
        Vector(7, 10, 9)

    Vector multiplication:
        >>> p1 * p2
        Vector(40, 0, 18)
        >>> p2 * (3, 1, 5)
        Vector(12, 5, 30)

    Vector scaling:
        >>> p1 * 5
        Vector(50, 0, 15)

    Vector cross-product (returns a vector perpendicular to the plane defined by the two vectors):
        >>> p1.cross(p2)
        Vector(-15, -48, 50)

    Vector length:
        >>> p2.length()
        8.774964387392123

    Vector normalized to unit length:
        >>> p2.normalize()
        Vector(0.455842305839, 0.569802882298, 0.683763458758)

    Translate a vector along a distance in a direction given by another vector:
        >>> direction = p2.normalize()
        >>> distance = -20
        >>> p3 = p1 + direction * distance
        >>> p3
        Vector(0.883153883229, -11.396057646, -10.6752691752)

    Vector with coordinates rounded down to nearest integer:
        >>> p3.intfloor()
        Vector(0, -12, -11)

    Absolute value of vector:
        >>> p3.abs()
        Vector(0.883153883229, 11.396057646, 10.6752691752)

    """
    def __repr__(self):
        return "Vector(%s, %s, %s)" % self

    __slots__ = ()

    def __add__(self, other):
        return Vector(self[0] + other[0], self[1] + other[1], self[2] + other[2])

    def __sub__(self, other):
        return Vector(self[0] - other[0], self[1] - other[1], self[2] - other[2])

    def __mul__(self, other):
        if isinstance(other, (int, float)):
            return Vector(self[0] * other, self[1] * other, self[2] * other)
        elif isinstance(other, numpy.ndarray):
            return other.__rmul__(self)

        return Vector(self[0] * other[0], self[1] * other[1], self[2] * other[2])

    def __truediv__(self, other):
        if isinstance(other, (int, float)):
            return Vector(self[0] / other, self[1] / other, self[2] / other)
        return Vector(self[0] / other[0], self[1] / other[1], self[2] / other[2])

    __div__ = __truediv__

    def __neg__(self):
        return Vector(-self[0], -self[1], -self[2])

    def lengthSquared(self):
        return self[0] * self[0] + self[1] * self[1] + self[2] * self[2]

    def length(self):
        return math.sqrt(self.lengthSquared())

    def normalize(self):
        l = self.length()
        if l == 0:
            return self
        return self / l

    def intfloor(self):
        return Vector(*[int(math.floor(p)) for p in self])

    def cross(self, other):
        return Vector(*numpy.cross(self, other))

    def abs(self):
        return Vector(*(abs(p) for p in self))

    def chunkPos(self):
        return Vector(*[p >> 4 for p in self.intfloor()])


class Ray(object):
    """
    A ray in 3D space, starting at an origin point and extending in a direction given
    by a vector

    Parameters
    ----------
    point: Vector
        The ray's origin point
    vector: Vector
        The ray's direction vector

    Attributes
    ----------

    point: Vector
    vector: Vector

    Methods
    ----------

    atHeight(h: int) : Vector
        Return the intersection of this vector with the plane at y=h.  If the ray
        does not intersect the plane, returns the ray's origin.
    """

    def __init__(self, point, vector):
        self.point = Vector(*point)
        self.vector = Vector(*vector)

    def __iter__(self):
        return iter((self.point, self.vector))

    def __repr__(self):
        return "Ray(%r, %r)" % (self.point, self.vector)


    @classmethod
    def fromPoints(cls, p1, p2):
        p1 = Vector(*p1)
        p2 = Vector(*p2)
        vec = (p2 - p1).normalize()
        return cls(p1, vec)

    def atHeight(self, h):
        return self.intersectPlane(1, h)

    def intersectPlane(self, dim, pos):
        """
        :type dim: int
        :type pos: float
        :rtype: Vector
        """
        point, vector = self
        d = pos - point[dim]
        if d * vector[dim] < 0:
            return point  # point is backward on ray, return ray origin

        if vector[dim] == 0:
            # ray is parallel to plane. return some point on plane, but should raise an error?
            s = [0, 0, 0]
            s[dim] = pos
            return point + s

        vector = vector / vector[dim]

        return point + vector * d

