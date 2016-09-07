Brush Shape Plugins
===================

A Brush Shape plugin adds a new option to the Brush and Select tools for choosing the
shape of the tool. A shape plugin must return a Selection object that defines the range
of blocks in the shape, and may provide a Widget object to present shape-specific options
in the tool's options panel.

Shape plugins must inherit from `mcedit2.editortools.brush.shapes.BrushShape`. There are
two ways to implement the shape: as a function that returns a boolean array, or as a
function that returns a new Selection object.

The `BrushShape` instance must also have an `ID` member which is a string that uniquely
identifies this brush shape, and must have a `displayName` member which is the shape's
human-readable name. It may also have an `icon` member which is an absolute path
to an image file to display as the shape's icon.

As a boolean array
------------------

.. automethod:: mcedit2.editortools.brush.shapes.BrushShape.shapeFunc

This is the simpler way of implementing a brush shape. When the shape is used, `shapeFunc`
will be called repeatedly for each section of the selection. It will be passed the
coordinates of each block in the selection, relative to the selection's origin point, along
with the full size of the selection. Using these values, you will compute and return a
boolean array (of the same shape as the coordinate array) that indicates whether each
block in the section should be selected.

`blockPositions` is a multi-dimensional array where the first axis selects the `x`, `y`, or
`z` coordinates; e.g. to access the `x` coordinate array, write `blockPositions[0]`.

`selectionSize` is a simple tuple of three positive integers.

For example, this brush shape selects all blocks whose relative Y coordinate is more than
5 - in other words, it is a rectangular selection that excludes the bottom five layers
of its bounding box::

    class Example(BrushShape):
        ID = "example"
        displayName = "Example Brush Shape"

        def shapeFunc(self, blockPositions, size):
            y = blockPositions[1]
            mask = y > 5
            return mask

Note that `shapeFunc` does not have access to the world dimension where the selection
is made, and cannot inspect the world and react to its contents. `shapeFunc` is meant for
shapes that are purely mathematical in nature and can be made using simple computations
on the coordinates and the selection's size.

As a Selection object
---------------------

.. automethod:: mcedit2.editortools.brush.shapes.BrushShape.createShapedSelection

This is the more advanced way of implementing a brush shape. `createShapedSelection` is
given the rectangular bounding box that encloses the shape, and the world dimension where
the shape is being used. It must return a `SelectionBox` instance, which may be one of the
existing selection classes or a class of your own design. For details about `SelectionBox`
subclasses, see :doc:`selection`