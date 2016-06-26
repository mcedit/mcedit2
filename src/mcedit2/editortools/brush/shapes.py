"""
    shapes
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from PySide import QtGui, QtCore
import numpy
from mcedit2.widgets.layout import Column
from mceditlib import selection
from mceditlib.selection import BoundingBox

log = logging.getLogger(__name__)


class BrushShape(QtCore.QObject):
    """
    BrushShape is an object that produces a shaped selection box, usable with the Brush and
    Select tools. BrushShape is responsible for providing a widget to present shape-specific options
    to the widget, and for signaling its client that the user has changed these options. It also
    provides an internal string ID and an icon to display in the shape chooser widget.

    Attributes
    ----------

    ID : unicode
        Textual identifier for this shape. Used for preference saving, etc.

    icon : unicode
        Path to icon file, relative to `mcedit2/assets/mcedit2/icons`

    optionsChanged : Signal
        This signal should be emitted whenever the options in the BrushShape's
        options widget are changed, to notify the shape's client that it should redraw the shape.
    """

    ID = NotImplemented
    icon = NotImplemented
    optionsChanged = QtCore.Signal()
    
    def createShapedSelection(self, box, dimension):
        """
        Return a SelectionBox that selects the blocks inside this shape.

        The default implementation returns a ShapeFuncSelection using self.shapeFunc. Subclasses
        may override this to return different types of SelectionBox.

        TODO: BitmapSelectionBox

        Parameters
        ----------

        box : BoundingBox
            Bounding box of the selection
        dimension : WorldEditorDimension
            Dimension to create the shaped selection for.

        Returns
        -------
        box: SelectionBox
            SelectionBox object that selects all blocks inside this shape
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

        Parameters
        ----------

        blockPositions : numpy.ndarray[ndims=4,dtype=float32]
            Coordinates of requested blocks relative to Shape's bounding box.
        selectionSize : (int, int, int)
            Size of the Shape's bounding box.

        Returns
        -------
        mask : numpy.ndarray[ndims=3,dtype=bool]
            Boolean array of the same shape as blockPositions[0] where selected blocks are True
        """
        raise NotImplementedError

    def getOptionsWidget(self):
        """
        Return a QWidget to present additional options for this shape.

        If there are no options to present, return None. This is the default implementation.

        Returns
        -------

        widget : QWidget | NoneType
        """
        return None


class Round(BrushShape):
    ID = "Round"
    icon = "shapes/round.png"

    def __init__(self):
        super(Round, self).__init__()
        self.displayName = self.tr("Round")

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

        if 0 in radius:
            log.warn("Zero volume shape: %s", shape)
            return None

        blockPositions -= offset[:, None, None, None]

        blockPositions *= blockPositions
        radius2 = radius * radius

        blockPositions /= radius2[:, None, None, None]
        distances = sum(blockPositions, 0)
        return distances <= 1


class Square(BrushShape):
    ID = "Square"
    icon = "shapes/square.png"

    def __init__(self):
        super(Square, self).__init__()
        self.displayName = self.tr("Square")

    def createShapedSelection(self, box, dimension):
        return BoundingBox(box.origin, box.size)


class Diamond(BrushShape):
    ID = "Diamond"
    icon = "shapes/diamond.png"

    def __init__(self):
        super(Diamond, self).__init__()
        self.displayName = self.tr("Diamond")

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
    icon = "shapes/cylinder.png"

    def __init__(self):
        super(Cylinder, self).__init__()
        self.displayName = self.tr("Cylinder")

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


class ChunkShape(BrushShape):
    ID = "Chunk"
    icon = "shapes/chunk.png"

    def __init__(self):
        super(ChunkShape, self).__init__()
        self.displayName = self.tr("Chunk")

    def createShapedSelection(self, box, dimension):
        return box.chunkBox(dimension)


class ParabolicDome(BrushShape):
    ID = "ParabolicDome"
    icon = "shapes/parabolic_dome.png"

    def __init__(self):
        super(ParabolicDome, self).__init__()
        self.displayName = self.tr("Parabolic Dome")

    def shapeFunc(self, blockPositions, selectionSize):

        # In 2D:
        # Parabola:
        #   y = x^2
        # Need to get y=h when x=0, so add h and invert:
        #   y = h - x^2
        # Need to get y=0 when x=w/2, which means getting x^2=h when x=w/2
        # Scale x down by w/2 and then up by sqrt(h)
        #   y = h - x'^2
        #   x' = 2x/w sqrt(h)

        # Assert h is positive.
        #   x'^2 = 4hx^2/w^2
        #   y = h - 4hx^2/w^2
        #
        # Fill in the parabola:
        #   y <= h - 4hx^2/w^2
        #
        # Extend to 3D.
        # x' = 4hx^2/w^2
        # z' = 4hz^2/l^2

        # y <= h - sqrt(x'^2 + z'^2)

        y, z, x = blockPositions
        h, l, w = selectionSize
        # First, offset x and z such that 0, 0 is at the bottom center of the selection box.
        x -= w / 2.0 - 0.5
        z -= l / 2.0 - 0.5

        # Now drop h by one to treat it as the maximum value and
        # not the "one-past" we use for array indexing.
        h -= 1

        xPrime = 4 * h * x * x / (w * w)
        zPrime = 4 * h * z * z / (l * l)

        yPrime = h - numpy.sqrt(xPrime * xPrime + zPrime * zPrime)
        # yPrime = h - xPrime
        return (y <= yPrime) & (y > 0) & (x < w/2.0) & (x > -w/2.0) & (z < l/2.0) & (z > -l/2.0)

# load from plugins here, rename to selection shapes?

# xxx what is responsible for "owning" the instances of BrushShape??
# Currently the ShapeWidget seems to own them.

def getShapes():
    return Square(), Round(), Diamond(), Cylinder(), ParabolicDome()
