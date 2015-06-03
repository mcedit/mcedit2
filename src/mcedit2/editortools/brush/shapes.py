"""
    shapes
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import numpy
from mceditlib import selection

log = logging.getLogger(__name__)


class BrushShape(object):
    ID = NotImplemented
    icon = NotImplemented

    def createShapedSelection(self, box):
        """
        Return a SelectionBox that selects the blocks inside this shape.

        The default implementation returns a ShapeFuncSelection using self.shapeFunc. Subclasses
        may override this to return different types of SelectionBox.

        TODO: BitmapSelectionBox

        :param box: Bounding box of the selection
        :type box: BoundingBox
        :return: SelectionBox object that selects all blocks inside this shape
        :rtype: SelectionBox
        """
        return selection.ShapeFuncSelection(box, self.shapeFunc)

    def shapeFunc(self, blockPositions, selectionSize):
        """
        Return a 3D boolean array for the blocks selected by this shape in a requested area.

        (Note that numpy arrays have a 'shape' attribute which gives the length of the array along
        each dimension. Sorry for the confusion.)

        The coordinates of the blocks are given by `blockPositions`, which is a 4D array where
        the first axis has size 3 and represents the Y, Z, and X coordinates. The coordinates
        given are relative to the bounding box for this shape. The remaining 3 axes have the shape
        of the requested area.

        `blockPositions` may be separated into coordinate arrays by writing
        `y, z, x = blockPositions`.

        The size and shape of the array to return is given by the shapes of the arrays in
        `blockPositions`.

        The size of the shape's bounding box is given by selectionSize.

        :param blockPositions: Coordinates of requested blocks relative to Shape's bounding box.
        :type blockPositions: numpy.ndarray[ndims=4,dtype=float32]
        :param selectionSize: Size of the Shape's bounding box.
        :type selectionSize: (int, int, int)
        :return: Boolean array of the same shape as blockPositions[0] where selected blocks are True
        :rtype: numpy.ndarray[ndims=3,dtype=bool]
        """
        raise NotImplementedError

    def createOptionsWidget(self):
        """
        Return a QWidget to present additional options for this shape.

        If there are no options to present, return None. This is the default implementation.

        :return: Options widget
        :rtype: QWidget | NoneType
        """
        return None

class Round(BrushShape):
    ID = "Round"
    icon = "shapes/round.png"

    def shapeFunc(self, blockPositions, shape):
        # For spheres: x^2 + y^2 + z^2 <= r^2
        # For ovoids: x^2/rx^2 + y^2/ry^2 + z^2/rz^2 <= 1
        #
        # blockPositions are the positions of the lower left corners of each block.
        #
        # to define the sphere, we measure the distance from the center of each block
        # to the sphere's center, which will be on a block edge when the size is even
        # or at a block center when the size is odd.
        #
        # to this end, we offset blockPositions downward so the sphere's center is at 0, 0, 0
        # and blockPositions are the positions of the centers of the blocks

        radius = shape / 2.0
        offset = radius - 0.5

        blockPositions -= offset[:, None, None, None]

        blockPositions *= blockPositions
        radius2 = radius * radius

        blockPositions /= radius2[:, None, None, None]
        distances = sum(blockPositions, 0)
        return distances <= 1


class Square(BrushShape):
    ID = "Square"
    icon = "shapes/square.png"

    def createShapedSelection(self, box):
        # BoundingBox is already a SelectionBox, so just return it
        return box


class Diamond(BrushShape):
    ID = "Diamond"
    icon = "shapes/diamond.png"

    def shapeFunc(self, blockPositions, selectionSize):
        # This is an octahedron.

        # Inscribed in a cube: |x| + |y| + |z| <= cubeSize
        # Inscribed in a box: |x/w| + |y/h| + |z/l| <= 1

        selectionSize /= 2

        # Recenter coordinates
        blockPositions -= (selectionSize - 0.5)[:, None, None, None]

        # Distances should be positive
        blockPositions = numpy.abs(blockPositions)

        # Divide by w, h, l
        blockPositions /= selectionSize[:, None, None, None]

        # Add x, y, z together
        distances = numpy.sum(blockPositions, 0)
        return distances <= 1


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
