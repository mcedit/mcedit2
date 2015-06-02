"""
    shapes
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from mceditlib import selection

log = logging.getLogger(__name__)


class BrushShape(object):
    ID = NotImplemented
    icon = NotImplemented
    shapeFunc = NotImplemented

class Round(BrushShape):
    ID = "Round"
    icon = "shapes/round.png"
    shapeFunc = staticmethod(selection.SphereShape)


class Square(BrushShape):
    ID = "Square"
    icon = "shapes/square.png"
    shapeFunc = staticmethod(selection.BoxShape)


class Diamond(BrushShape):
    ID = "Diamond"
    icon = "shapes/diamond.png"
    shapeFunc = staticmethod(selection.DiamondShape)

class Cylinder(BrushShape):
    ID = "Cylinder"
    icon = None

    def shapeFunc(self, blockPositions, selectionSize):
        # axis = y
        #

        y, z, x = blockPositions
        h, l, w = selectionSize
        # radius
        w /= 2
        l /= 2
        # offset to 0,0 at center
        x -= w - 0.5
        z -= l - 0.5

        # distance formula:
        # for circles: x^2 + z^2 < r^2
        # for ovoids: x^2/rx^2 + z^2/rz^2 < 1
        x *= x
        z *= z

        rx2 = w*w
        rz2 = l*l

        x /= rx2
        z /= rz2

        distances = x + z
        return (distances < 1) & (0 <= y) & (y < h)


# load from plugins here, rename to selection shapes?
allShapes = (Square(), Round(), Diamond(), Cylinder())

def getShapes():
    return allShapes
