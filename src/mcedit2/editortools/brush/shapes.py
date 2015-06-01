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



# load from plugins here, rename to selection shapes?
allShapes = (Square(), Round(), Diamond())

def getShapes():
    return allShapes
