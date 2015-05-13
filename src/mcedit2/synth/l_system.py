"""
    l_system
"""
from __future__ import absolute_import, division, print_function
import logging
import pprint
from math import floor
from OpenGL import GL
from mcedit2.rendering.scenegraph import Node, VertexNode
from mcedit2.rendering.selection import SelectionBoxNode
from mcedit2.rendering.vertexarraybuffer import VertexArrayBuffer
from mcedit2.util.bresenham import bresenham
from mceditlib.selection import BoundingBox

log = logging.getLogger(__name__)

"""

From Wikipedia:
[An L-system or Lindenmayer system is a parallel rewriting system and
a type of formal grammar. An L-system consists of an alphabet of symbols
that can be used to make strings, a collection of production rules that
expand each symbol into some larger string of symbols, an initial
"axiom" string from which to begin construction, and a mechanism for
translating the generated strings into geometric structures.]

Briefly, an L-system allows you to start with a root symbol (the
"axiom"), and then define rules for replacing that symbol with a number
of sub-symbols. The rules may be applied repeatedly to add more
symbols and more depth to the symbol list. The final element list is then
translated into a form that can be displayed on-screen.

The Wiki page describes translating the symbols into Turtle Graphics commands
from LOGO. Other forms such as OpenGL rendering commands or 2D painting
commands from DirectDraw/QuickDraw/Cocoa2D are also possible, but typically
the replacement rules must be designed with the output in mind, such as
by using a parametric grammar as described further down the page.

The original use of L-systems was to model organic growth, by using a
set of replacement rules that results in symbols that can be replaced
further. The rules are typically applied for a fixed number of
iterations. For our purpose of modeling deliberate constructions it is
more useful to have non-recursive replacement rules that can be run
indefinitely because they will terminate when all of the elements have
no replacements available.

The resulting tree of elements is then rendered into geometric points.

This file defines a variant of the L-system meant for creating geometric
structures in 3D space. The alphabet of symbols is extended to include
"parametrized" symbols, where a single symbol can take many forms according
to parameters such as length, width, radius, etcetera. The production rules
are also extended to consider the parameters of a symbol when formulating its
replacements.

The final step of translating the symbols into geometric structures will
result in a list of coordinates and blocktypes, suitable for passing to
the `setBlock` function of a Minecraft world or world editor.

Alternately, the symbols can be rendered as OpenGL scene nodes instead of
Minecraft blocks. This is usually much faster and is suitable for returning
preview nodes from a Generate Tool plugin.

Several default symbols are available for primitives such as lines and blocks.
These provide both Minecraft block renderers and OpenGL scene node renderers.
The block renderers will use only a single block type. For primitives filled with
e.g. patterns of blocks, subclass them and override render()

It may be possible to add different rendering outputs such as SVG or HTML.
This is as simple as adding another render function to each symbol type, and
calling that function on each symbol in the list. (See the renderBlocks and
renderSceneNodes functions - they are really nothing more than `flatmap(f, symbol_list)`)
"""


def applyReplacements(symbol_list):
    """
    Apply the rules associated with each symbol to the symbols in
     `symbol_list`. Symbols with no defined rule are returned as-is.

    The elements of `symbol_list` must be subclasses of Symbol.

    Returns a tuple of (`replaced`, `new_symbol_list`) where `replaced` is
    True if any symbols had triggered a replacement rule, and
    `new_symbol_list` is the new list after applying all replacement rules.
    If `replaced` is False, `new_symbol_list` should be identical to
    `symbol_list`

    :param symbol_list:
    :type symbol_list: list[Symbol]
    :return:
    :rtype: (bool, list[Symbol])
    """
    replaced = False
    new_list = []
    for symbol in symbol_list:
        if hasattr(symbol, 'replace'):
            replaced = True
            new_symbols = symbol.replace()
            new_list.extend(new_symbols)
        else:
            new_list.append(symbol)

    return replaced, new_list


def applyReplacementsIterated(symbol_list, repeats):
    """
    Repeatedly apply replacement rules to `symbol_list` up to `repeats` times or until no replacements are applied.

    This is a generator function. For each iteration, yields the iteration count and the intermediate list as a tuple.

    :param symbol_list:
    :type symbol_list: list[Symbol]
    :param repeats:
    :type repeats: int
    :return:
    :rtype: list[Symbol]
    """
    for i in range(repeats):
        replaced, symbol_list = applyReplacements(symbol_list)
        if not replaced:
            break

        yield i, symbol_list

def renderBlocks(symbol_list):
    rendering = []
    for symbol in symbol_list:
        rendering.extend(symbol.renderBlocks())

    return rendering

def renderSceneNodes(symbol_list):
    rendering = []
    for symbol in symbol_list:
        rendering.extend(symbol.renderSceneNodes())

    return rendering


class Symbol(object):
    def __init__(self, **kw):
        self.parameters = kw

    def __getattr__(self, key):
        return self.parameters[key]

    def renderBlocks(self):
        """
        Implement this function to render this symbol as a list of Minecraft block
        placement commands, in the form of (x, y, z, blockType) tuples. Return an empty
        list if there is nothing to render.

        In the future this will probably be extended to allow rendering Entities and TileEntities,
        although this may require passing in the level to render into in order to create item stacks
        with the correct id format.
        """

        return []

    def renderSceneNodes(self):
        """
        Implement this function to render this symbol as an OpenGL scene node. Typically only
        one Node is required. Return an empty list if there is nothing to render.
        """
        return []

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, self.parameters)


# --- Predefined symbols ---

class Geometric(Symbol, BoundingBox):
    """
    A symbol that can represent a region of 3D space as an axis-aligned
    bounding box.

    Inherits from mceditlib's BoundingBox and provides all derived
    properties such as center, volume, maximum, positions, the chunk
    coordinates [min,max][cx,cy,cz] and so on.

    Parameters:
    minx
    miny
    minz
    width
    height
    length
    """

    def __init__(self, box=None, **kw):
        Symbol.__init__(self, **kw)
        if box is None:
            origin = kw['minx'], kw['miny'], kw['minz']
            size = kw['width'], kw['height'], kw['length']
        else:
            origin = box.origin
            size = box.size

        BoundingBox.__init__(self, origin, size)

    def renderSceneNodes(self):
        node = SelectionBoxNode()  # xxx BoundingBoxNode
        node.selectionBox = self
        node.filled = False
        node.color = 1.0, 1.0, 1.0, 0.7

        return [node]

class Fill(Geometric):
    """
    Fills a 3D box with a chosen blocktype.

    Parameters:

    blocktype

    + parameters inherited from Geometric
    """

    def __init__(self, box=None, blocktype=None, **kw):
        super(Fill, self).__init__(box, **kw)
        if blocktype:
            self.parameters["blocktype"] = blocktype

    def renderBlocks(self):
        return [(x, y, z, self.blocktype) for x, y, z in self.positions]


class Line(Symbol):
    """
    Draws a line between the chosen points with a chosen blocktype.

    Parameters:

    blocktype: BlockType | str | int | (int, int)
    p1: Vector
    p2: Vector

    """

    def renderBlocks(self):
        for x, y, z in bresenham(self.p1, self.p2):
            yield x, y, z, self.blocktype


    def renderSceneNodes(self):
        vertexArray = VertexArrayBuffer(2, GL.GL_LINES, False, False)
        vertexArray.vertex[:] = [self.p1, self.p2]
        vertexArray.rgba[:] = 255, 64, 64, 128

        node = VertexNode([vertexArray])  # xxx LineNode

        return [node]
