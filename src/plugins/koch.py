# coding=utf-8
"""
    koch
"""
from __future__ import absolute_import, division, print_function
import logging
from math import pi, cos, sin
from PySide import QtGui
import math
from mcedit2.plugins import registerGeneratePlugin

from mcedit2.synth.l_system import Geometric, Line
from mcedit2.synth.l_system_plugin import LSystemPlugin
from mcedit2.widgets.blockpicker import BlockTypeButton
from mceditlib.geometry import Vector


log = logging.getLogger(__name__)

class Side(Line):
    """
    A side of a Koch snowflake. A side can be replaced by four shorter sides in a _/\_ configuration.

    Inherits from Line, so renders as a line.

    Properties:

    blocktype
    p1: Vector
    p2: Vector
    """
    def replace(self):
        p1 = self.p1
        p2 = self.p2
        d = p2 - p1

        mid1 = p1 + d * 0.3333
        mid2 = p2 - d * 0.3333
        spike = mid1 + rotatePoint(d * -0.3333)

        # First segment
        yield Side(p1=p1, p2=mid1, **self.parameters)

        # Second segment
        yield Side(p1=mid1, p2=spike, **self.parameters)

        # Third segment
        yield Side(p1=spike, p2=mid2, **self.parameters)

        # Fourth segment
        yield Side(p1=mid2, p2=p2, **self.parameters)


# One-third of a circle
THETA = 2 * pi / 3
COS_THETA = cos(THETA)
SIN_THETA = sin(THETA)


# Rotate the point around 0, 0 by one-third of a circle.
# Also works for vectors! We use it to rotate the vector
# added to get the new point when replacing a side with
# four smaller sides.

def rotatePoint((x, y, z)):
    u"""
    Rotation matrix:

    | cos θ   - sin θ  |
    | sin θ     cos θ  |

    """
    x2 = COS_THETA * x - SIN_THETA * z
    z2 = SIN_THETA * x + COS_THETA * z
    return Vector(x2, y, z2)


class Snowflake(Geometric):
    """
    Koch snowflake.

    The initial symbol is replaced by six sides.

    Each side is replaced by four shorter sides, each 1/3 the length of the original side in a _/\_ configuration.

    The side replacement is recursively defined and may be repeated any number of times.

    This could probably be optimized a bit by introducing a LineStrip symbol and inheriting SideStrip from it.

    Properties:
    blocktype

    + properties inherited from Geometric
    """
    def replace(self):
        # Find the first corner's position relative to the hexagon's center
        center = Vector(self.center.x, self.miny, self.center.z)
        firstPoint = Vector(self.maxx, self.miny, self.center.z) - center

        points = []
        point = firstPoint
        for i in range(3):
            points.append(point)
            point = rotatePoint(point)

        # Translate the corners back to the hexagon's position
        points = [p + center for p in points]

        # Compute the endpoints of the line segments
        startPoints = points
        endPoints = points[1:] + points[:1]

        for p1, p2 in zip(startPoints, endPoints):
            yield Side(p1=p1, p2=p2, blocktype=self.blocktype, glColor=(255, 64, 255, 128))


if __name__ == '__main__':
    point = 4.5, 0, 5.0
    print("THETA", THETA)
    print("COS_THETA", COS_THETA)
    print("SIN_THETA", SIN_THETA)

    for i in range(3):
        print(point)
        point = rotatePoint(point)

class KochSnowflakePlugin(LSystemPlugin):
    displayName = "Koch Snowflake"
    _optionsWidget = None
    
    def getOptionsWidget(self):
        if self._optionsWidget:
            return self._optionsWidget

        widget = self._optionsWidget = QtGui.QWidget()

        self.blockTypeButton = BlockTypeButton()
        self.blockTypeButton.editorSession = self.editorSession
        self.blockTypeButton.block = "minecraft:stone"
        self.blockTypeButton.blocksChanged.connect(self.updatePreview)

        layout = QtGui.QFormLayout()
        layout.addRow(self.tr("Iterations"), self.iterationsSlider)
        layout.addRow(self.tr("Block"), self.blockTypeButton)

        widget.setLayout(layout)
        return widget

    def createInitialSymbol(self, bounds):
        symbol = Snowflake(bounds, blocktype=self.blockTypeButton.block)

        return symbol

    def boundsChanged(self, bounds):
        if bounds is None:
            return  # no selection

        size = (bounds.width + bounds.length) / 2
        maxiter = math.log(size, 4) + 2
        self.iterationsSlider.setMaximum(maxiter)

displayName = "Koch Snowflake"

registerGeneratePlugin(KochSnowflakePlugin)
