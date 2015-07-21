"""
    raycast
"""
from __future__ import absolute_import, division, print_function
import logging
import math
import numpy
from mcedit2.util import profiler
from mceditlib.geometry import Vector, Ray
from mceditlib.selection import SectionBox, rayIntersectsBox
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

def rayCastInBounds(ray, dimension, maxDistance=100):
    try:
        position, face = rayCast(ray, dimension, maxDistance)
    except RayBoundsError:
        ixs = rayIntersectsBox(dimension.bounds, ray)
        if ixs:
            position, face = ixs[0]
            position = position.intfloor()
        else:
            position, face = None, None
    return position, face

@profiler.function
def rayCast(ray, dimension, maxDistance=100):
    """
    Borrowed from https://gamedev.stackexchange.com/questions/47362/cast-ray-to-select-block-in-voxel-game

    Updates a factor t along each axis to compute the distance from the vector origin (in units of the vector
    magnitude) to the next integer value (i.e. block edge) along that axis.

    Return the block position and face of the block touched.

    Raises MaxDistanceError if the ray exceeded the max distance without hitting any blocks, or if the ray exits or
    doesn't enter the dimension's bounds.

    Bypasses non-air blocks until the first air block is found, and only returns when a non-air block is found after
    the first air block.

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

    point = advanceToChunk(Ray(point, vector), dimension, maxDistance * 4)

    foundAir = False

    for pos, face in _cast(point, vector, maxDistance, 1):
        ID = dimension.getBlockID(*pos)

        if ID == 0:  # xxx configurable air blocks?
            foundAir = True
        if ID and foundAir:
            return Vector(*pos), faces.Face.fromVector(face)
        if pos not in bounds:
            raise RayBoundsError("Ray exited dimension bounds")

    raise MaxDistanceError("Ray exceeded max distance.")

def intbound(o, v, step):
    if v < 0:
        v = -v
        o = -o
        if (o % step) == 0:
            return 0.0
    return (step - (o % step)) / v

def _cast_np(origin, vector, maxDistance, stepSize):
    # maxDistance is just a recommendation. More points will usually be returned.

    originPos = list(int(o - o % stepSize) for o in origin)
    # Integer single steps along each vector axis
    step = numpy.array([stepSize if v > 0 else -stepSize if v < 0 else 0 for v in vector])
    faceDirs = numpy.array([1 if v > 0 else -1 if v < 0 else 0 for v in vector])
    faceDirs = -faceDirs

    # t factor along each axis
    t = numpy.array([intbound(o, v, stepSize) if v else 2000000000 for o, v in zip(origin, vector)])
    # distance to increment t along each axis after finding a block edge
    d = numpy.array([s/v if v != 0 else 0 for s, v in zip(step, vector)])

    maxT = maxDistance / vector.length()
    stepCount = max(int(1 + (maxT - t[i]) / d[i]) for i in range(3))
    # stepCount = int(1 + (maxT) / min(d))
    print("stepCount", stepCount)
    # compute all t values for `stepCount` steps
    tarr = numpy.arange(stepCount)[None, :] * d[:, None]
    tarr += t[:, None]
    tlimits = [(tarr[i] > maxT).nonzero() for i in range(3)]
    #print("tlimit", len(tlimits), tlimits[0][0].shape)
    limits = [(i, tlimits[i][0][0]) for i in range(3) if len(tlimits[i][0])]
    print("limit", limits)
    print("stepCount?", )

    # get flattened indexes of sorted form of tarr
    targs = numpy.argsort(tarr, None)  # xxx arrays are pre-sorted, find O(n) sort method

    # the flattened indexes have a unique property: the index divided by stepCount
    # gives the axis for that t value. so now we have the axis of the smallest t value
    # at each step along the ray.

    taxis = targs // stepCount

    # make a coordinate triple for each axis that only steps along that axis

    steps = numpy.diag(step)

    # similarly, make a coordinate triple for each axis that gives the face direction
    # (the "normal") of the cube face that was hit.

    faceDirs = numpy.diag(faceDirs)

    # use taxis to pull the single-axis steps out into an array of stepCount*3 steps

    allSteps = steps[taxis]

    # similarly, use taxis to get the faces hit at each step

    allFaces = faceDirs[taxis]

    # the cumulative sum of the steps along axis 0 gives the offset at each step

    allOffsets = numpy.cumsum(allSteps, 0)

    allPositions = allOffsets + originPos

    # massage output array into a list of pairs of coordinate triples

    ret = numpy.hstack([allPositions[:, None, :], allFaces[:, None, :]])
    # print('ret', ret.shape)

    # j-j-jam the first point/face in the front

    ret = numpy.vstack([[[originPos, [0, 1, 0]]], ret[:-1]])
    return ret


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
        yield tuple(originPos), face
        smallAxis = t.index(min(t))
        t[smallAxis] += d[smallAxis]
        if t[smallAxis] > maxDistance:
            break

        # compute block coordinates and face direction
        originPos[smallAxis] += step[smallAxis]

        face = [0, 0, 0]
        face[smallAxis] = -faceDirs[smallAxis]


def advanceToChunk(ray, dimension, maxDistance):
    point, vector = ray
    inBounds = point in dimension.bounds

    for pos, face in _cast(point, vector, maxDistance, 16):

        x, y, z = pos
        x >>= 4
        y >>= 4
        z >>= 4
        if inBounds and pos not in dimension.bounds:
            raise RayBoundsError("Ray exited dimension bounds.")
        inBounds = pos in dimension.bounds

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

def main():
    vector = Vector(.333, .555, .2831).normalize()
    origin = Vector(138.2, 22.459, 12)
    maxDistance = 1000

    def cast_py():
        return numpy.array(list(_cast(origin, vector, maxDistance, 1)))
    def cast_np():
        return _cast_np(origin, vector, maxDistance, 1)

    res_py = cast_py()
    res_np = cast_np()

    print("res_py", res_py.shape)
    print("res_np", res_np.shape)
    s = min(len(res_py), len(res_np))
    passed = (res_py[:s] == res_np[:s]).all()
    print("Passed" if passed else "Failed")

    from timeit import timeit

    t_py = timeit(cast_py, number=1)
    t_np = timeit(cast_np, number=1)

    print("Time cast_py", t_py)
    print("Time cast_np", t_np)

if __name__ == '__main__':
    main()