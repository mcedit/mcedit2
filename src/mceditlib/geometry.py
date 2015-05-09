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
    def __repr__(self):
        return "(x=%s, y=%s, z=%s)" % self

    __slots__ = ()

    def __add__(self, other):
        return Vector(self[0] + other[0], self[1] + other[1], self[2] + other[2])

    def __sub__(self, other):
        return Vector(self[0] - other[0], self[1] - other[1], self[2] - other[2])

    def __mul__(self, other):
        if isinstance(other, (int, float)):
            return Vector(self[0] * other, self[1] * other, self[2] * other)

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
        :type pos: int
        :rtype: Vector
        """
        point, vector = self
        d = pos - point[dim]
        if d * vector[dim] < 0:
            return point  # point is backward on ray, return ray origin

        if vector[dim] == 0:
            s = [0, 0, 0]
            s[dim] = pos
            return point + s

        vector = vector / vector[dim]

        return point + vector * d

