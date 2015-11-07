"""
    command_visuals
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from OpenGL import GL

from mcedit2.rendering.scenegraph.depth_test import DepthFunc
from mcedit2.rendering.scenegraph.misc import LineWidth
from mcedit2.rendering.scenegraph.scenenode import Node
from mcedit2.rendering.scenegraph.vertex_array import VertexNode
from mcedit2.rendering.selection import SelectionBoxNode
from mcedit2.rendering.vertexarraybuffer import VertexArrayBuffer
from mcedit2.util.commandblock import UnknownCommand
from mceditlib.geometry import Vector
from mceditlib.selection import BoundingBox

log = logging.getLogger(__name__)

_visualClasses = {}


def register_visual(cls):
    _visualClasses[cls.commandName] = cls
    return cls


def LineStripNode(points, rgba):
    vertexArray = VertexArrayBuffer(len(points), GL.GL_LINE_STRIP, False, False)
    vertexArray.vertex[:] = points
    vertexArray.rgba[:] = rgba
    node = VertexNode([vertexArray])
    return node


def LineArcNode(p1, p2, color):
    arcSegments = 20

    rgba = [c * 255 for c in color]
    points = [p1]
    x, y, z = p1
    dx = p2[0] - p1[0]
    dz = p2[2] - p1[2]
    dx /= arcSegments
    dz /= arcSegments
    heightDiff = p2[1] - p1[1]
    # maxRise = 8

    # initial y-velocity
    dy = 0.3 if heightDiff >= 0 else -0.3
    dy += 2 * heightDiff / arcSegments

    # the height of p2 without gravity

    overshot = y + dy * arcSegments - p2[1]

    # needed gravity so the last point is p2
    ddy = -overshot / (arcSegments * (arcSegments-1) / 2)

    for i in range(arcSegments):
        y += dy
        dy += ddy
        x += dx
        z += dz
        points.append((x, y, z))

    arcNode = Node("lineArc")

    lineNode = LineStripNode(points, rgba)
    arcNode.addChild(lineNode)

    arcNode.addState(LineWidth(3.0))

    backLineNode = Node("lineArcBack")
    backLineNode.addChild(lineNode)
    arcNode.addChild(backLineNode)

    backLineNode.addState(DepthFunc(GL.GL_GREATER))
    backLineNode.addState(LineWidth(1.0))

    return arcNode


def CommandVisuals(pos, commandObj):
    visualCls = _visualClasses.get(commandObj.name)
    if visualCls is None:
        log.warn("No command found for %s", commandObj.name)
        return Node("nullCommandVisuals")
    else:
        return visualCls(pos, commandObj)


class PositionalVisuals(Node):
    color = (0.2, 0.9, 0.7, 0.6)

    def __init__(self, pos, commandObj):
        super(PositionalVisuals, self).__init__()

        x, y, z = commandObj.resolvePosition(pos)

        boxNode = SelectionBoxNode()
        boxNode.filled = False
        boxNode.wireColor = self.color
        boxNode.selectionBox = BoundingBox((x, y, z), (1, 1, 1))

        lineNode = LineArcNode(Vector(*pos) + (0.5, 0.5, 0.5), (x+.5, y+.5, z+.5), self.color)

        self.addChild(boxNode)
        self.addChild(lineNode)


class TargetedVisuals(Node):
    def __init__(self, pos, commandObj):
        super(TargetedVisuals, self).__init__()

        selector = commandObj.targetSelector
        if selector.playerName is not None:
            return

        selectorPos = [selector.getArg(a) for a in 'xyz']
        if None in selectorPos:
            return

        color = (0.2, 0.9, 0.7, 0.6)

        boxNode = SelectionBoxNode()
        boxNode.filled = False
        boxNode.wireColor = color
        boxNode.selectionBox = BoundingBox(selectorPos, (1, 1, 1))

        lineNode = LineArcNode(Vector(*pos) + (0.5, 0.5, 0.5),
                               Vector(*selectorPos) + (.5, .5, .5), color)

        self.addChild(boxNode)
        self.addChild(lineNode)


@register_visual
class GiveVisuals(TargetedVisuals):
    commandName = "give"


@register_visual
class PlaySoundVisuals(TargetedVisuals):
    commandName = "playsound"


@register_visual
class SetBlockVisuals(PositionalVisuals):
    color = (0.2, 0.9, 0.7, 0.6)
    commandName = "setblock"

@register_visual
class SummonVisuals(PositionalVisuals):
    color = (0.9, 0.2, 0.4, 0.6)
    commandName = "summon"


@register_visual
class TestForBlockVisuals(PositionalVisuals):
    color = (0.5, 0.2, 0.7, 0.6)
    commandName = "testforblock"


@register_visual
class BlockdataVisuals(PositionalVisuals):
    color = (0.2, 0.6, 0.9, 0.6)
    commandName = "blockdata"


class BoundingBoxVisuals(Node):
    boxColor = (0.4, 0.2, 0.7, 0.6)

    def __init__(self, pos, commandObj):
        super(BoundingBoxVisuals, self).__init__()
        box = commandObj.resolveBoundingBox(pos)
        boxNode = SelectionBoxNode()
        boxNode.filled = False
        boxNode.wireColor = self.boxColor
        boxNode.selectionBox = box
        lineToBoxNode = LineArcNode(Vector(*pos) + (0.5, 0.5, 0.5),
                                    box.center, self.boxColor)

        self.addChild(boxNode)
        self.addChild(lineToBoxNode)


@register_visual
class FillVisuals(BoundingBoxVisuals):
    boxColor = (0.9, 0.6, 0.3, 0.6)
    commandName = "fill"


@register_visual
class CloneVisuals(Node):
    commandName = "clone"

    def __init__(self, pos, commandObj):
        super(CloneVisuals, self).__init__()

        sourceBox = commandObj.resolveBoundingBox(pos)

        dest = commandObj.resolveDestination(pos)
        destBox = BoundingBox(dest, sourceBox.size)

        sourceColor = (0.3, 0.5, 0.9, 0.6)
        destColor = (0.0, 0.0, 0.9, 0.6)

        sourceBoxNode = SelectionBoxNode()
        sourceBoxNode.filled = False
        sourceBoxNode.wireColor = sourceColor
        sourceBoxNode.selectionBox = sourceBox

        destBoxNode = SelectionBoxNode()
        destBoxNode.filled = False
        destBoxNode.wireColor = destColor
        destBoxNode.selectionBox = destBox

        lineToSourceNode = LineArcNode(Vector(*pos) + (0.5, 0.5, 0.5), sourceBox.center, sourceColor)
        lineToDestNode = LineArcNode(sourceBox.center, destBox.center, destColor)

        self.addChild(sourceBoxNode)
        self.addChild(destBoxNode)

        self.addChild(lineToSourceNode)
        self.addChild(lineToDestNode)


@register_visual
class ExecuteVisuals(Node):
    commandName = "execute"

    def __init__(self, pos, commandObj):
        """

        Parameters
        ----------
        commandObj : ExecuteCommand

        Returns
        -------

        """
        super(ExecuteVisuals, self).__init__()

        selector = commandObj.targetSelector
        if selector.playerName is not None:
            return

        selectorPos = [selector.getArg(a) for a in 'xyz']

        if None in (selectorPos):
            log.warn("No selector coordinates for command %s", commandObj)
            targetPos = commandObj.resolvePosition((0, 0, 0))
        else:
            targetPos = commandObj.resolvePosition(selectorPos)

        # Draw box at selector pos and draw line from command block to selector pos
        # xxxx selector pos is a sphere of radius `selector.getArg('r')`

        boxNode = SelectionBoxNode()
        boxNode.filled = False
        boxNode.wireColor = (0.9, 0.2, 0.2, 0.6)
        boxNode.selectionBox = BoundingBox(selectorPos, (1, 1, 1))

        lineNode = LineArcNode(Vector(*pos) + (0.5, 0.5, 0.5),
                               Vector(*selectorPos) + (.5, .5, .5),
                               (0.9, 0.2, 0.2, 0.6))
        self.addChild(boxNode)
        self.addChild(lineNode)

        if selectorPos != targetPos:
            # Command block's own coordinates are different from the selected pos,
            # either relative or absolute.
            # Draw a box at the target coordinates and a line from
            # the selected pos to the target

            boxNode = SelectionBoxNode()
            boxNode.filled = False
            boxNode.wireColor = (0.9, 0.2, 0.2, 0.6)
            boxNode.selectionBox = BoundingBox(targetPos, (1, 1, 1))

            lineNode = LineArcNode(Vector(*selectorPos) + (0.5, 0.5, 0.5),
                                   Vector(*targetPos) + (.5, .5, .5),
                                   (0.9, 0.2, 0.2, 0.6))

            self.addChild(boxNode)
            self.addChild(lineNode)

        if not isinstance(commandObj.subcommand, UnknownCommand):
            subvisuals = CommandVisuals(targetPos, commandObj.subcommand)
            self.addChild(subvisuals)

