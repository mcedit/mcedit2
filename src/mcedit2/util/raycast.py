"""
    raycast
"""
from __future__ import absolute_import, division, print_function
import logging
import math
from mcedit2.util import profiler
from mceditlib.geometry import Vector, Ray, rayIntersectsBox, SectionBox
from mceditlib import faces

log = logging.getLogger(__name__)

class RayCastError(ValueError):
    pass

class MaxDistanceError(RayCastError):
    """
    Raised when a ray cast exceeds its max distance.
    """

class RayBoundsError(RayCastError):
    """
    Raised when a ray exits or does not enter the level boundaries.
    """

def rayCastInBounds(ray, dimension, maxDistance=100, hitAir=False):
    try:
        position, face = rayCast(ray, dimension, maxDistance, hitAir)
    except RayBoundsError:
        ixs = rayIntersectsBox(dimension.bounds, ray)
        if ixs:
            position, face = ixs[0]
            position = position.intfloor()
        else:
            position, face = None, None
    return position, face

@profiler.function
def rayCast(ray, dimension, maxDistance=100, hitAir=False):
    """
    Borrowed from https://gamedev.stackexchange.com/questions/47362/cast-ray-to-select-block-in-voxel-game

    Updates a factor t along each axis to compute the distance from the vector origin (in units of the vector
    magnitude) to the next integer value (i.e. block edge) along that axis.

    Return the block position and face of the block touched.

    Raises MaxDistanceError if the ray exceeded the max distance without hitting any blocks, or if the ray exits or
    doesn't enter the dimension's bounds.

    :param ray:
    :type ray: Ray
    :param maxDistance:
    :type maxDistance: int
    :param dimension:
    :type dimension: mceditlib.worldeditor.WorldEditorDimension
    :return: (point, face)
    :rtype:
    """
    point, vector = ray
    if all(v == 0 for v in vector):
        raise ValueError("Cannot cast with zero direction ray.")

    bounds = dimension.bounds
    if point not in bounds:
        intersects = rayIntersectsBox(bounds, ray)
        if not intersects:
            raise RayBoundsError("Ray does not enter dimension bounds.")

        point = intersects[0][0]

    point = advanceToChunk(Ray(point, vector), dimension)
    currentCX, currentCY, currentCZ = point.intfloor()
    currentChunk = None

    for pos, face in _cast(point, vector, maxDistance, 1):
        cx = pos[0] >> 4
        cz = pos[2] >> 4
        if cx != currentCX or cz != currentCZ:
            currentCX = cx
            currentCZ = cz
            if dimension.containsChunk(cx, cz):
                currentChunk = dimension.getChunk(cx, cz)  # xxxx WorldEditor.recentlyLoadedChunks
        ID = dimension.getBlockID(*pos)
        if ID or hitAir:
            return Vector(*pos), faces.Face.fromVector(face)

    raise MaxDistanceError("Ray exceeded max distance.")

def intbound(o, v, step):
    if v < 0:
        v = -v
        o = -o
        if (o % step) == 0:
            return 0.0
    return (step - (o % step)) / v

def _cast(origin, vector, maxDistance, stepSize):
    originPos = list(int(o - o % stepSize) for o in origin)
    # Integer single steps along each vector axis
    step = [stepSize if v > 0 else -stepSize if v < 0 else 0 for v in vector]
    faceDirs = [1 if v > 0 else -1 if v < 0 else 0 for v in vector]

    # t factor along each axis
    t = [intbound(o, v, stepSize) if v else 2000000000 for o, v in zip(origin, vector)]
    # distance to increment t along each axis after finding a block edge
    d = [s/v if v != 0 else 0 for s, v in zip(step, vector)]

    # to compare maxDistance against t
    maxDistance /= vector.length()
    face = [0, 1, 0]
    while True:
        # find axis of nearest block edge
        yield originPos, face
        smallAxis = t.index(min(t))
        t[smallAxis] += d[smallAxis]
        if t[smallAxis] > maxDistance:
            break

        # compute block coordinates and face direction
        originPos[smallAxis] += step[smallAxis]

        face = [0, 0, 0]
        face[smallAxis] = -faceDirs[smallAxis]


def advanceToChunk(ray, dimension):
    point, vector = ray
    distance = 2000
    for pos, face in _cast(point, vector, distance, 16):

        x, y, z = pos
        x >>= 4
        y >>= 4
        z >>= 4
        if pos not in dimension.bounds:
            raise RayBoundsError("Ray exited dimension bounds.")
        if dimension.containsChunk(x, z):
            chunk = dimension.getChunk(x, z)
            section = chunk.getSection(y)
            if section is not None:
                # if (section.Blocks == 0).all():
                #     log.warn("Empty section found!!")
                #     continue
                box = SectionBox(x, y, z)
                if point in box:
                    return point
                ixs = rayIntersectsBox(box, ray)
                if ixs:
                    hitPoint = ixs[0][0]
                    return hitPoint

    raise RayBoundsError("Ray exited dimension bounds.")
