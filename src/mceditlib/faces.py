from __future__ import absolute_import


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
        return self.name

    @classmethod
    def fromVector(cls, v):
        v = tuple(v)
        for face, vec in faceDirections:
            if v == vec:
                return face
        raise ValueError("No face for vector %s" % (v,))

FaceXIncreasing = Face(0)
FaceXDecreasing = Face(1)
FaceYIncreasing = Face(2)
FaceYDecreasing = Face(3)
FaceZIncreasing = Face(4)
FaceZDecreasing = Face(5)
MaxDirections = 6

faceDirections = (
    (FaceXIncreasing, (1, 0, 0)),
    (FaceXDecreasing, (-1, 0, 0)),
    (FaceYIncreasing, (0, 1, 0)),
    (FaceYDecreasing, (0, -1, 0)),
    (FaceZIncreasing, (0, 0, 1)),
    (FaceZDecreasing, (0, 0, -1))
)

faceNames = [
    "East",
    "West",
    "Up",
    "Down",
    "North",
    "South"
]
