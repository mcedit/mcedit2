"""
    l_system
"""
from __future__ import absolute_import, division, print_function
import logging

from OpenGL import GL

from mcedit2.rendering.scenegraph.vertex_array import VertexNode
from mcedit2.rendering.selection import SelectionBoxNode
from mcedit2.rendering.vertexarraybuffer import VertexArrayBuffer
from mcedit2.util import bresenham
from mceditlib.selection import BoundingBox

log = logging.getLogger(__name__)

"""
An L-system is a way of generating graphics and geometric structures through code. It is also
a way of thinking about algorithmic generation.

This is a very simple L-system that only renders a triangle with fixed coordinates:

    class Triangle(Symbol):
        def replace():
            p1 = (0, 0, 20)
            p2 = (10, 0, -10)
            p3 = (-10, 0, -10)
            return [Line(p1, p2, blocktype="stone"),
                    Line(p2, p3, blocktype="stone"),
                    Line(p3, p1, blocktype="stone")]

    initial_system = [Triangle()]
    # use initial_system in an LSystemPlugin, etc...

At the core, an L-system is made of one type of object, a Symbol, and two functions: a `replace`
function and a `render` function. The `replace` function's job is to add increasing amounts of
detail to the system by replacing a symbol with its components, and the `render` function is for
transforming the final result from a list of Symbols into a form suitable for rendering. In our
case, we have two kinds of `render` functions - one for producing OpenGL graphics to show on
screen, and one for producing Minecraft blocks to either show on screen or write to the world file.

An L-system as a whole is a simple list of Symbols. The initial state of the system is a list
containing a single Symbol (called the "axiom" in the literature). The system is evolved to the
next state by calling `replace` on each symbol in the list, and replacing it with the result of
the replace function. Thus, the system is evolved by calling `replace` repeatedly, over a given
number of iterations, or until no further symbols can be replaced.

A Symbol is an object that contains any number of parameters, and implements either the `replace`
function, the `render` function, or both.

The `replace` function returns a list of new Symbols to replace this symbol in the system's list.
Because Symbols are allowed to have parameters, the replace function can return different lists of
new Symbols depending on the current Symbol's parameters. If the Symbol does not implement replace,
it will remain in the system as-is during further iterations. *

The `renderBlocks` function returns a list of `setBlock` tuples: `(x, y, z, blockType)`.
(in the future, `renderBlocks` may be changed to take the currently edited world as an argument
so it can directly edit the world.) *

The `renderSceneNodes` function returns a list of `scenegraph.Node` objects to be rendered in an
OpenGL viewport. *

If a Symbol implements both `replace` and `render` functions, it is said to be recursive. This
means a system containing this symbol can be evolved for any number of iterations and will not
ever "halt" with a list of non-replaceable symbols.

To implement your own L-system, start by creating a Symbol subclass for your initial symbol.
Implement `replace` on this symbol to return a list of symbols that will replace this symbol
in the first iteration. You may create additional Symbol subclasses for the symbols that will
replace the initial symbol. Optionally, implement `renderBlocks` and possibly `renderSceneNodes` on
any symbols that can be rendered as the final output of the system.

For generating Minecraft objects, it is useful for each Symbol to represent a region of 3D space,
and for each `replace` function to subdivide this symbol into smaller regions represented by
other Symbols. A `Geometric` symbol class is provided for this purpose that acts as an
axis-aligned bounding box. `Geometric` also implements `renderSceneNodes` to help visualize the
evolution of a system.

A small collection of predefined symbols that implement both `render` functions are provided:
Line, Fill, (TODO: more symbols), and others. You can return these from your Symbol's `replace` to
render the final output of a system. These symbols usually have points or boxes as parameters, plus
a `blocktype` parameter. They can save you the trouble of implementing any `render` functions.

* `replace` and `render` may be implemented as generators using the `yield` statement instead of
directly returning a `list`.
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

    def __init__(self, p1, p2, **kw):
        kw.setdefault("glColor", (255, 64, 64, 128))
        super(Line, self).__init__(**kw)
        self.p1 = p1
        self.p2 = p2

    def renderBlocks(self):
        for x, y, z in bresenham.bresenham(self.p1, self.p2):
            yield x, y, z, self.blocktype

    def renderSceneNodes(self):
        vertexArray = VertexArrayBuffer(2, GL.GL_LINES, False, False)
        vertexArray.vertex[:] = [self.p1, self.p2]
        vertexArray.vertex[:] += 0.5  # draw using box centers
        vertexArray.rgba[:] = self.glColor

        node = VertexNode([vertexArray])  # xxx LineNode

        return [node]

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
