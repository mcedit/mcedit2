from __future__ import division
import collections
import functools
from math import floor

# Original form of bresenham's plotting algorithm:
import itertools


def bresenham_0((x1, y1), (x2, y2)):
    e = 0  # error term
    y = y1  # current y
    m = (y2 - y1) / (x2 - x1)  # slope

    for x in range(x1, x2):
        yield x, y
        if e + m < 0.5:
            e += m
        else:
            y += 1
            e += m - 1


# ---
# Hoist the += m out of the if

def bresenham_1((x1, y1), (x2, y2)):
    e = 0
    y = y1
    m = (y2 - y1) / (x2 - x1)

    assert -1 <= m <= 1

    for x in range(x1, x2):
        yield x, y
        e += m
        if e >= 0.5:
            y += 1
            e -= 1


# ---
# Multiply e and m by 2 * dx. m decomposes into dx and dy
# Gains a bit of accuracy by losing the float division for m.

def bresenham_2((x1, y1), (x2, y2)):
    e = 0
    y = y1
    dy = y2 - y1
    dx = x2 - x1
    # m = (y2-y1)/(x2-x1)

    assert dx > dy

    for x in range(x1, x2):
        yield x, y
        e += 2 * dy
        if e >= dx:
            y += 1
            e -= 2 * dx


# ---
# Initialize e to -dx

def bresenham_3((x1, y1), (x2, y2)):
    y = y1
    dx = x2 - x1
    dy = y2 - y1
    e = -dx

    assert dx > dy

    for x in range(x1, x2):
        yield x, y
        e += 2 * dy
        if e >= 0:
            y += 1
            e -= 2 * dx


# ---
# Convert to 3D coordinates:
# Add z1 and z2
# Use multiple 'e' values for y and z

def bresenham3D_3((x1, y1, z1), (x2, y2, z2)):
    y = y1
    z = z1
    dx = x2 - x1
    dy = y2 - y1
    dz = z2 - z1
    ey = -dx
    ez = -dx

    assert dx > dy and dx > dz

    for x in range(x1, x2):
        yield x, y, z
        ey += 2 * dy
        if ey >= 0:
            y += 1
            ey -= 2 * dx
        ez += 2 * dz
        if ez >= 0:
            z += 1
            ez -= 2 * dx


# ---
# from bresenham_3:
# Scale up to allow float coordinates as input
# Multiply x1, x2, y1, y2 by 65536
# Multiply step by 65536
# Divide yielded output by 65536

def bresenham_4((x1, y1), (x2, y2)):
    step = 65536
    x1 = int(floor(x1 * step))
    x2 = int(floor(x2 * step))
    y1 = int(floor(y1 * step))
    y2 = int(floor(y2 * step))

    y = y1
    dx = x2 - x1
    dy = y2 - y1
    e = -dx

    assert dx > dy

    for x in range(x1, x2, step):
        yield x >> 16, y >> 16
        e += 2 * dy
        if e >= 0:
            y += step
            e -= 2 * dx


# ---
# Convert to 3D coordinates:
# Add z1 and z2
# Use multiple 'e' values for y and z

def bresenham3D_4((x1, y1, z1), (x2, y2, z2)):
    step = 65536
    x1 = int(floor(x1 * step))
    x2 = int(floor(x2 * step))
    y1 = int(floor(y1 * step))
    y2 = int(floor(y2 * step))
    z1 = int(floor(z1 * step))
    z2 = int(floor(z2 * step))

    y = y1
    z = z1

    dx = x2 - x1
    dy = y2 - y1
    dz = z2 - z1

    ey = -dx
    ez = -dx

    assert dx > dy and dx > dz

    for x in range(x1, x2, step):
        yield x >> 16, y >> 16, z >> 16

        ey += 2 * dy
        if ey >= 0:
            y += step
            ey -= 2 * dx

        ez += 2 * dz
        if ez >= 0:
            z += step
            ez -= 2 * dx

# ---
# Relax requirement that x is the major axis and dx, dy, dz are positive
# Store x, y, z in a list instead of directly as variables
# Store ex, ey, ez in a list. One of them is ignored (and pointlessly updated)
# Compute an index into this list for the major axis
# Make step negative whenever d is negative

def bresenham(p1, p2):
    """
    Bresenham line algorithm adapted for 3d and scaled for subpixel endpoints.
    """
    step = 65536
    logStep = 16
    # step = 1
    # logStep = 0

    x1, y1, z1 = p1
    x2, y2, z2 = p2

    x1 = int(floor(x1 * step))
    y1 = int(floor(y1 * step))
    z1 = int(floor(z1 * step))
    x2 = int(floor(x2 * step))
    y2 = int(floor(y2 * step))
    z2 = int(floor(z2 * step))

    dx = abs(x2 - x1)
    if (x2 - x1) > 0:
        sx = step
    else:
        sx = -step
    dy = abs(y2 - y1)
    if (y2 - y1) > 0:
        sy = step
    else:
        sy = -step
    dz = abs(z2 - z1)
    if (z2 - z1) > 0:
        sz = step
    else:
        sz = -step

    # absolute value of distance vector (dy)
    distance = [dx, dy, dz]

    # index of axis corresponding to dx
    longestAxis = distance.index(max(distance))

    # accumulated error along minor axes, multiplied by 2*dx
    # initialized to -dx so the test becomes error >= 0
    error = [-distance[longestAxis] for _ in distance]

    otherAxes = [0, 1, 2]
    otherAxes.remove(longestAxis)

    point = [x1, y1, z1]
    steps = [sx, sy, sz]
    for i in range(0, int(distance[longestAxis]), step):
        yield tuple([(a >> logStep) for a in point])

        # add dy to error terms
        error = map(lambda e, d: e + 2 * d, error, distance)

        for j in otherAxes:
            while error[j] >= 0:
                point[j] += steps[j]
                error[j] -= 2 * distance[longestAxis]

        # step along major axis
        point[longestAxis] += steps[longestAxis]


def testInt2D():
    p1 = -10, -5
    p2 = 2, 6

    r0 = list(bresenham_0(p1, p2))
    r1 = list(bresenham_1(p1, p2))
    r2 = list(bresenham_2(p1, p2))
    r3 = list(bresenham_3(p1, p2))
    r4 = list(bresenham_4(p1, p2))

    if r0 != r1:  # no change
        print "r0 != r1\n%s != \n%s" % (r0, r1)
    if r1 == r2:  # accuracy gained
        print "r1 == r2\n%s != \n%s" % (r1, r2)
    if r2 != r3:  # no change
        print "r2 != r3\n%s != \n%s" % (r2, r3)
    if r3 != r4:  # no change
        print "r3 != r4\n%s != \n%s" % (r3, r4)


def testFloat2D():
    p1 = -64, -30
    p2 = -2.66773328, -6.3785856262

    i1 = -64, -30
    i2 = -3, -7

    r3 = list(bresenham_3(i1, i2))
    r4 = list(bresenham_4(p1, p2))

    if r3 == r4:  # accuracy gained
        print "r3 == r4\n%s != \n%s" % (r3, r4)


def testFloat2D3D():
    testFloat2D3DWith(bresenham_3, bresenham3D_3, True)
    testFloat2D3DWith(bresenham_4, bresenham3D_4)


def testFloat2D3DWith(bres2d, bres3d, asInt=False):
    # 3D variant should project exactly onto 2D variant along the two non-major axes.
    # It will not project along the major axis because it will sometimes move along one minor axis and then the other,
    # which will draw a right-angle which is never normally drawn.

    print "Trying", bres2d, bres3d
    p1 = -64, -30, -15
    p2 = -2.66773328, -6.3785856262, 4.3333

    if asInt:
        p1 = map(int, p1)
        p2 = map(int, p2)

    r4_xy = list(bres2d(p1[:2], p2[:2]))
    r4_xz = list(bres2d((p1[0], p1[2]), (p2[0], p2[2])))
    r5 = list(bres3d(p1, p2))

    r5_xy = [(x, y) for x, y, z in r5]
    r5_xz = [(x, z) for x, y, z in r5]

    if r4_xy != r5_xy:  # no change for (x, y)
        print "2d_xy != 3d_xy\n%s != \n%s" % (r4_xy, r5_xy)
    if r4_xz != r5_xz:  # no change for (x, z)
        print "2d_xz != 3d_xz\n%s != \n%s" % (r4_xz, r5_xz)

def testFloat3D():
    p1 = -64, -30, -15
    p2 = -2.66773328, -6.3785856262, 4.3333

    r0 = list(bresenham3D_4(p1, p2))
    r1 = list(bresenham(p1, p2))

    if r0 != r1:  # no change
        print "r0 != r1\n%s != \n%s" % (r0, r1)

def main():
    testInt2D()
    testFloat2D()
    testFloat2D3D()
    testFloat3D()


if __name__ == '__main__':
    main()

