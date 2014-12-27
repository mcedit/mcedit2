def bresenham(p1, p2):
    """
    Bresenham line algorithm
    adapted for 3d.  slooooow.
    Now in generator style.
    """
    x, y, z = p1
    x2, y2, z2 = p2

    dx = abs(x2 - x)
    if (x2 - x) > 0:
        sx = 1
    else:
        sx = -1
    dy = abs(y2 - y)
    if (y2 - y) > 0:
        sy = 1
    else:
        sy = -1
    dz = abs(z2 - z)
    if (z2 - z) > 0:
        sz = 1
    else:
        sz = -1

    dl = [dx, dy, dz]
    longestAxis = dl.index(max(dl))
    d = [2 * a - dl[longestAxis] for a in dl]

    otherAxes = [0, 1, 2]
    otherAxes.remove(longestAxis)
    p = [x, y, z]
    sp = [sx, sy, sz]
    for i in range(0, int(dl[longestAxis])):
        yield tuple(p)
        for j in otherAxes:

            while d[j] >= 0:
                p[j] += sp[j]
                d[j] -= 2 * dl[longestAxis]

        p[longestAxis] += sp[longestAxis]
        d = map(lambda a, b: a + 2 * b, d, dl)

