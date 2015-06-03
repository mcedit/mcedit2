from __future__ import absolute_import
from mceditlib.geometry import Vector


class Face(int):
    @property
    def dimension(self):
        return self >> 1

    @property
    def direction(self):
        return self & 1

    @property
    def vector(self):
        return faceDirections[self][1]

    @property
    def name(self):
        return faceNames[self]

    def __repr__(self):
        return "Face(%s)" % self.name

    @classmethod
    def fromVector(cls, v):
        v = tuple(v)
        for face, vec in faceDirections:
            if v == vec:
                return face
        raise ValueError("No face for vector %s" % (v,))

    @property
    def vector(self):
        return _directions[self]

FaceXIncreasing = FaceEast = Face(0)
FaceXDecreasing = FaceWest = Face(1)
FaceYIncreasing = FaceUp = Face(2)
FaceYDecreasing = FaceDown = Face(3)
FaceZIncreasing = FaceSouth = Face(4)
FaceZDecreasing = FaceNorth = Face(5)
MaxDirections = 6

faceDirections = (
    (FaceXIncreasing, Vector(1, 0, 0)),
    (FaceXDecreasing, Vector(-1, 0, 0)),
    (FaceYIncreasing, Vector(0, 1, 0)),
    (FaceYDecreasing, Vector(0, -1, 0)),
    (FaceZIncreasing, Vector(0, 0, 1)),
    (FaceZDecreasing, Vector(0, 0, -1))
)
_directions = {k: v for (k, v) in faceDirections}

allFaces = [f[0] for f in faceDirections]

faceNames = [
    "East",
    "West",
    "Up",
    "Down",
    "North",
    "South"
]
