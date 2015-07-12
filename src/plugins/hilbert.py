# coding=utf-8
"""
    hilbert
"""
from __future__ import absolute_import, division, print_function
import logging
import math

from OpenGL import GL
from PySide import QtGui

from mcedit2.plugins import registerGeneratePlugin
from mcedit2.rendering.scenegraph.vertex_array import VertexNode
from mcedit2.rendering.vertexarraybuffer import VertexArrayBuffer
from mcedit2.synth.l_system import Geometric, Symbol
from mcedit2.synth.l_system_plugin import LSystemPlugin
from mcedit2.util import bresenham
from mcedit2.widgets.blockpicker import BlockTypeButton

log = logging.getLogger(__name__)
"""


    In 2D:

    Each cell has an initial subcell index, and a 'forward/backward' marker.

    A "forward" cell replaces itself with "backward, forward, forward, backward" cells.
    A "backward" cell with "forward, backward, backward, forward" cells.

    A cell with initial subcell index N returns cells with subcell indices `(N, N, N, N+2)`
    (modulo ncells)

    That is to say, a `0, forward` cell returns subcells `0, 1, 2, 3` each with subcell
    indexes `0, 0, 0, 2`

    A `0, backward` cell returns subcells `0, 3, 2, 1` with indices `0, 0, 0, 2`
    A `2, backward` cell returns subcells `2, 1, 0, 3` with indices `2, 2, 2, 0`

    Wikipedia gives this production rule for turtle graphics:

    A → − B F + A F A + F B −
    B → + A F − B F B − F A +

    The 'counter' and 'clock' types correspond to the 'A' and 'B' types of the turtle
    graphics system. The cardinal direction is stored in the orientation of the turtle.
    Without a turtle, we need to store the direction in the cell itself.

    When counter-clockwise, return these subcells. When clockwise, return them
    in reverse order.

    down: (0, 0), (0, 1), (1, 1), (1, 0)
    right: (0, 1), (1, 1), (1, 0), (0, 0)
    up: (1, 1), (1, 0), (0, 0), (0, 1)
    left: (1, 0), (0, 0), (0, 1), (1, 1)

"""
#
# offsets = [
#     (0, 0, 0),
#     (0, 0, 1),
#     (0, 1, 1),
#     (0, 1, 0),
#     (1, 1, 0),
#     (1, 1, 1),
#     (1, 0, 1),
#     (1, 0, 0),
# ]
offsets = [
    (0, 0), (0, 1), (1, 1), (1, 0),
]

ncells = len(offsets)
def nextSubcells(N):
    return N, N, N, (N+2) % ncells

def getOffsets(initialIndex):
    return offsets[initialIndex:] + offsets[:initialIndex]

class Cell(Symbol):
    """
    A cell of a Hilbert curve. A cell can be replaced by eight smaller cells, each
    half the size of this cell. Cell sides must be a power of two.

    Properties:

    blocktype
    p1: Vector
    p2: Vector
    """
    def replace(self):
        x, y, z = self.origin
        cellSize = self.cellSize
        initialIndex = self.initialIndex
        forward = self.forward

        if cellSize == 2:
            yield self
            return

        cellSize >>= 1

        subcellIndices = nextSubcells(initialIndex)

        if forward:
            nextForwards = False, True, True, False
            d=1
        else:
            nextForwards = True, False, False, True
            d=-1

        offsets = getOffsets(initialIndex)


        for i, (subcellIndex, forward) in enumerate(zip(subcellIndices, nextForwards)):
            dx, dz = offsets[d*i]
            origin = (x + dx * cellSize, y, z + dz * cellSize)
            yield Cell(origin=origin, cellSize=cellSize,
                       forward=forward, initialIndex=subcellIndex)




Clock = True
Counter = False

class HilbertCurveShell(Geometric):
    """
    The outer shell of a Hilbert curve. This shell simply replaces itself with a
    HilbertCurve the size of the largest power-of-two cube that fits inside itself.

    Properties:
    blocktype

    + properties inherited from Geometric
    """
    def replace(self):
        size = min(self.size[0], self.size[2]) # xxx 3d
        cellSize = 1
        while cellSize <= size:
            cellSize <<= 1

        cellSize >>= 1

        yield Cell(origin=self.origin, cellSize=cellSize,
                   initialIndex=0,
                   forward=True,
                   blocktype=self.blocktype)


class HilbertCurvePlugin(LSystemPlugin):
    displayName = "Hilbert Curve"
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
        symbol = HilbertCurveShell(bounds, blocktype=self.blockTypeButton.block)

        return symbol

    def renderSceneNodes(self, symbol_list):
        points = []
        for cell in symbol_list:
            if not isinstance(cell, Cell):
                continue
            points.append(cell.origin)

        vertexArray = VertexArrayBuffer(len(points), GL.GL_LINE_STRIP, False, False)
        vertexArray.vertex[:] = points
        vertexArray.vertex[:] += 0.5  # draw using box centers
        vertexArray.rgba[:] = [(255, 0, 255, 255)]

        node = VertexNode([vertexArray])  # xxx LineNode
        return [node]

    def _renderBlocks(self, symbol_list):
        for cell1, cell2 in zip(symbol_list[:-1], symbol_list[1:]):
            if not isinstance(cell1, Cell):
                continue
            for p in bresenham.bresenham(cell1.origin, cell2.origin):
                yield p + (self.blockTypeButton.block, )  #xxx line

    def renderBlocks(self, symbol_list):
        return list(self._renderBlocks(symbol_list))

    def boundsChanged(self, bounds):
        size = (bounds.width + bounds.length) / 2
        maxiter = math.log(size, 2) + 2
        self.iterationsSlider.setMaximum(maxiter)

displayName = "Hilbert Curve"

registerGeneratePlugin(HilbertCurvePlugin)
