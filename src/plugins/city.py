"""
    city
"""
from __future__ import absolute_import, print_function
import logging
from math import pi, cos, sin
from random import Random
import time
from PySide import QtGui
from mcedit2.plugins import registerGeneratePlugin

from mcedit2.synth.l_system import Geometric, Line, Fill
from mcedit2.synth.l_system_plugin import LSystemPlugin
from mcedit2.widgets.blockpicker import BlockTypeButton
from mcedit2.widgets.layout import Column, Row
from mcedit2.widgets.spinslider import SpinSlider
from mceditlib.geometry import Vector
from mceditlib.selection import BoundingBox

log = logging.getLogger(__name__)

method = "City"  # xxx



class City(Geometric):
    """
    City from GFX by Adrian Brightmoore.

    Converted to an L-system by David Vierra.

    Parameters:

    edgeBlockType
    fillBlockType
    lightBlockType

    + parameters from Geometric
    """

    def replace(self):
        # Residential is if the maximum dimension of the selection box is less than 12 times this
        # number (i.e. 48
        # when drafting this code)
        MINSIZE = 4

        # Place random buildings radially within the selection box.
        TwoPI = 2 * pi

        centerX, centerY, centerZ = self.center
        halfSize = self.size / 2
        groundOrigin = (centerX, self.miny, centerZ)

        buildingCount = (self.width + self.length) / (MINSIZE * 6)

        for i in xrange(1, buildingCount):
            print('Constructing building %s of %s' % (i, buildingCount))
            r = self.random.randint(0, halfSize.x / 8 * 7)
            theta = self.random.random() * TwoPI
            phi = 0
            (x1, y1, z1) = polarToCartesian(theta, phi, r) + groundOrigin

            # Work out how big this building needs to be based on where it is
            # in relation to the centre of the box (with occasional variation)

            # Note that w and d are HALF the size of the resulting building

            # Scale the buildings further out downwards
            coef = float(r / (centerX / 8.0 * 7.0))
            if self.random.randint(1, 20) < 2:
                # But occasionally allow a full-height building
                h = self.height
            else:
                h = int(self.height * (1.0 - coef))

            if h < MINSIZE:
                h = MINSIZE + 1
            # Vary heights somewhat
            h = self.random.randint(MINSIZE, h)

            if h < MINSIZE:
                h = MINSIZE

            w = self.width / MINSIZE
            if w < MINSIZE:
                w = MINSIZE + 1
            w = self.random.randint(MINSIZE, w) / 2

            if w < MINSIZE:
                w = MINSIZE
            if w > MINSIZE * 2:
                if self.random.randint(1, 10) < 2:
                    w = MINSIZE * 2 + self.random.randint(MINSIZE, MINSIZE * 2)
                else:
                    w = MINSIZE * 2

            d = self.length / MINSIZE
            if d < MINSIZE:
                d = MINSIZE + 1
            d = self.random.randint(MINSIZE, d) / 2

            if d < MINSIZE:
                d = MINSIZE
            if d > MINSIZE * 2:
                if self.random.randint(1, 10) < 2:
                    d = MINSIZE * 2 + self.random.randint(MINSIZE, MINSIZE * 2)
                else:
                    d = MINSIZE * 2

            print('Building box before recentering: %s %s %s, %s %s %s' % (x1, y1, z1, w, h, d))

            # Find the new origin point where the building's previous origin
            # is now at the center of its base.
            (tx1, ty1, tz1) = (x1 - w, y1, z1 - d)
            (tx2, ty2, tz2) = (abs(w * 2), abs(h), abs(d * 2))

            print('Building box after recentering: %s %s %s, %s %s %s' % (
                tx1, ty1, tz1, tx2, ty2, tz2))

            newBox = BoundingBox((tx1, ty1, tz1), (tx2, ty2, tz2))

            if MINSIZE > 4 and self.random.randint(0, 100) < 10:
                yield BuildingAngledShim(newBox, **self.parameters)
            else:
                yield RuinedBuilding(newBox, **self.parameters)


class BuildingAngledShim(Geometric):
    def replace(self):
        return [BuildingAngled(self,
                               orientation=self.random.randint(0, 45),
                               numSides=self.random.randint(3, 11),
                               **self.parameters)]


class BuildingAngled(Geometric):
    def replace(self):
        print('%s: Started at %s' % (method, time.ctime()))
        (width, height, depth) = self.size

        edgeBlock = self.edgeBlockType
        fillBlock = self.fillBlockType
        lightBlock = self.lightBlockType
        Orientation = self.Orientation
        numSides = self.numSides

        centreWidth = width / 2
        centreDepth = depth / 2

        # Randomly swap edge and fill blocks
        if self.random.randint(1, 100) < 30:
            edgeBlock, fillBlock = fillBlock, edgeBlock

        TwoPI = 2 * pi

        SideLength = centreWidth
        RINGS = self.random.randint(1, SideLength / 4 + 1)

        if Orientation == -1:  # Randomise
            Orientation = self.random.randint(0, 45)

        offsetX = 0
        offsetZ = 0

        angle = TwoPI / 360

        if numSides < 3:
            numSides = 3 + self.random.randint(0, 15)

        banding = False
        bandingSize1 = 0
        bandingSize2 = 0
        if self.random.randint(1, 20) < 10:
            banding = True
            bandingSize1 = self.random.randint(2, 8)
            bandingSize2 = self.random.randint(1, bandingSize1)

        for y in xrange(0, height):
            print('%s: %s of %s' % (method, y, height))
            radius = int(SideLength)

            for r in xrange(1, radius):
                MATERIAL = fillBlock
                ringR = int(SideLength / RINGS)
                if ringR == 0:
                    ringR = 2
                if r == radius - 1:
                    MATERIAL = lightBlock
                    if banding:
                        t = y % (bandingSize1 + bandingSize2)
                        if t < bandingSize1:
                            MATERIAL = edgeBlock

                elif r % ringR == 0:  # Interior walls
                    MATERIAL = edgeBlock
                if (MATERIAL is fillBlock and y % 4 == 0
                    or (MATERIAL is lightBlock)
                    or (MATERIAL is edgeBlock)):
                    x = r * cos(Orientation * angle)
                    z = r * sin(Orientation * angle)

                    for sides in xrange(0, numSides + 1):
                        x1 = r * cos((Orientation + 360 / numSides * sides) * angle)
                        z1 = r * sin((Orientation + 360 / numSides * sides) * angle)
                        yield Line((self.minx + centreWidth + x + offsetX,
                                    self.miny + y,
                                    self.minz + offsetZ + centreDepth + z),
                                   (self.minx + centreWidth + x1 + offsetX,
                                    self.miny + y,
                                    self.minz + centreDepth + z1 + offsetZ))

                        x = x1
                        z = z1

            if SideLength < 1:
                break

        print('%s: Ended at %s' % (method, time.ctime()))


class RuinedBuilding(Geometric):
    def replace(self):
        print('%s: Started at %s' % (method, time.ctime()))
        width, height, depth = self.size

        edgeBlock = self.edgeBlockType
        fillBlock = self.fillBlockType
        lightBlock = self.lightBlockType

        W = Factorise(width - 1)
        H = Factorise(height - 1)
        D = Factorise(depth - 1)

        w = W.pop(self.random.randint(0, len(W) - 1))
        h = H.pop(self.random.randint(0, len(H) - 1))
        d = D.pop(self.random.randint(0, len(D) - 1))

        drawGlass = False
        if self.random.randint(1, 20) > 1:
            drawGlass = True

        banding = False
        bandType = 1
        bandingSize1 = 0
        bandingSize2 = 0
        if self.random.randint(1, 20) < 10:
            banding = True
            bandingSize1 = self.random.randint(2, 8)
            bandingSize2 = self.random.randint(1, bandingSize1)
        if self.random.randint(1, 20) < 5:
            bandType = 2

        # Floors
        print('%s: Floors' % method)
        for iterY in xrange(0, height - 1):
            if iterY == 0 or (iterY % 4 == 0 and self.random.randint(1, 10) > 1):
                floorBox = BoundingBox((self.minx + 1, self.miny + iterY, self.minz + 1),
                                       (width - 1, 1, depth - 1))
                yield Fill(floorBox, blocktype=fillBlock)

        print('%s: Rooms' % method)

        # Create room partitions along the entire height whenever x % w == 0 or x % roomSize == 0
        # Likewise for z % d == 0 or z % roomSize == 0
        roomSize = self.random.randint(6, 12)

        for x in range(width):
            if x % w == 0 or x % roomSize == 0:
                partitionBox = BoundingBox((self.minx + x, self.miny, self.minz),
                                           (1, height - 1, depth))

                yield Fill(partitionBox, edgeBlock)

        for z in range(depth):
            if z % d == 0 or z % roomSize == 0:
                partitionBox = BoundingBox((self.minx, self.miny, self.minz + z),
                                           (width, height - 1, 1))

                yield Fill(partitionBox, edgeBlock)

        # Uprights
        print('%s: Uprights' % method)
        if drawGlass:
            if not banding:
                # Walls
                wallBox = BoundingBox((self.minx, self.miny, self.minz), (width, height - 1, depth))
                yield Walls(wallBox, blocktype=lightBlock)

            else:
                # Banded walls
                y = 0
                while y < height:
                    if bandType == 1:
                        wallBox = BoundingBox((self.minx, self.miny + y, self.minz),
                                              (width, bandingSize1, depth))
                        yield Walls(wallBox, blocktype=edgeBlock)
                    else:
                        if y < height - 1:
                            if y + bandingSize1 > height - 1:
                                wallBox = BoundingBox((self.minx, self.miny + y, self.minz),
                                                      (width, height - 1 - y, depth))

                                yield Walls(wallBox, blocktype=fillBlock)
                            else:
                                wallBox = BoundingBox((self.minx, self.miny + y, self.minz),
                                                      (width, bandingSize1, depth))

                                yield Walls(wallBox, blocktype=fillBlock)

                    y += bandingSize1

                    if y < height - 1:
                        if y + bandingSize2 >= height - 1:
                            wallBox = BoundingBox((self.minx, self.miny + y, self.minz),
                                                  (width, height - 1 - y, depth))

                            yield Walls(wallBox, blocktype=lightBlock)
                        else:
                            wallBox = BoundingBox((self.minx, self.miny + y, self.minz),
                                                  (width, bandingSize2, depth))

                            yield Walls(wallBox, blocktype=lightBlock)

                    y += bandingSize2


        # Bounding
        print('%s: Bounding' % method)

        for y in (self.miny, self.maxy - 1):
            yield Line((self.minx, y, self.minz),
                       (self.maxx - 1, y, self.minz),
                       blocktype=edgeBlock)

            yield Line((self.minx, y, self.maxz - 1),
                       (self.maxx - 1, y, self.maxz - 1),
                       blocktype=edgeBlock)

            yield Line((self.minx, y, self.minz),
                       (self.minx, y, self.maxz - 1),
                       blocktype=edgeBlock)

            yield Line((self.maxx - 1, y, self.minz),
                       (self.maxx - 1, y, self.maxz - 1),
                       blocktype=edgeBlock)


class Walls(Geometric):
    def replace(self):
        wallBox = BoundingBox((self.minx, self.miny, self.minz), (1, self.height - 1, self.length))
        yield Fill(wallBox, self.blocktype)
        wallBox = BoundingBox((self.maxx - 1, self.miny, self.minz),
                              (1, self.height - 1, self.length))
        yield Fill(wallBox, self.blocktype)

        wallBox = BoundingBox((self.minx, self.miny, self.minz), (self.width, self.height - 1, 1))
        yield Fill(wallBox, self.blocktype)
        wallBox = BoundingBox((self.minx, self.miny, self.maxz - 1),
                              (self.width, self.height - 1, 1))
        yield Fill(wallBox, self.blocktype)


def Factorise(number):
    """
    Return all integer factors of `number` in no particular order.
    """
    factors = set()

    for i in xrange(1, int(number + 1)):
        r = number % i
        if r == 0:
            p = number / i
            factors.add(i)
            factors.add(p)

    return list(factors)


def polarToCartesian(angleHoriz, angleVert, distance):
    x = cos(angleHoriz) * cos(angleVert) * distance
    z = sin(angleHoriz) * cos(angleVert) * distance
    y = sin(angleVert) * distance  # Elevation

    return Vector(x, y, z)


class CityGeneratePlugin(LSystemPlugin):
    displayName = "GFX: City"

    def createInitialSymbol(self, bounds):
        symbol = City(bounds,
                      random=Random(self.seedInput.value()),
                      fillBlockType=self.fillBlockButton.block,
                      edgeBlockType=self.edgeBlockButton.block,
                      lightBlockType=self.lightBlockButton.block,
                      )
        return symbol

    def getOptionsWidget(self):
        if self.optionsWidget:
            return self.optionsWidget

        widget = QtGui.QWidget()

        self.fillBlockButton = BlockTypeButton()
        self.fillBlockButton.editorSession = self.editorSession
        self.fillBlockButton.block = "minecraft:stone"
        self.fillBlockButton.blocksChanged.connect(self.updatePreview)

        self.edgeBlockButton = BlockTypeButton()
        self.edgeBlockButton.editorSession = self.editorSession
        self.edgeBlockButton.block = "minecraft:quartz_block"
        self.edgeBlockButton.blocksChanged.connect(self.updatePreview)

        self.lightBlockButton = BlockTypeButton()
        self.lightBlockButton.editorSession = self.editorSession
        self.lightBlockButton.block = "minecraft:glass"
        self.lightBlockButton.blocksChanged.connect(self.updatePreview)

        self.seedInput = QtGui.QSpinBox()
        self.seedInput.setMinimum(-(1<<30))
        self.seedInput.setMaximum((1<<30))
        self.seedInput.setValue(0)
        self.seedInput.valueChanged.connect(self.updatePreview)

        layout = QtGui.QFormLayout()
        layout.addRow(self.tr("Iterations"), self.iterationsSlider)
        layout.addRow(self.tr("Seed"), self.seedInput)
        layout.addRow(self.tr("Fill"), self.fillBlockButton)
        layout.addRow(self.tr("Edge"), self.edgeBlockButton)
        layout.addRow(self.tr("Light"), self.lightBlockButton)

        widget.setLayout(layout)
        self.optionsWidget = widget
        return widget

registerGeneratePlugin(CityGeneratePlugin)

displayName = "GFX: City"
