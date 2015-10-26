"""
    workplane
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from OpenGL import GL

from mcedit2.rendering.scenegraph import scenenode
from mcedit2.rendering.scenegraph.matrix import Translate
from mcedit2.rendering.scenegraph.vertex_array import VertexNode
from mcedit2.rendering.vertexarraybuffer import VertexArrayBuffer

log = logging.getLogger(__name__)



class WorkplaneNode(scenenode.Node):

    def __init__(self):
        super(WorkplaneNode, self).__init__()
        self.translateState = Translate()
        self.addState(self.translateState)
        self.axis = 1

    vertexNode = None

    _axis = 1

    @property
    def axis(self):
        return self._axis

    @axis.setter
    def axis(self, axis):
        self._axis = axis
        self.dirty = True

        gridSize = 64
        left = -gridSize//2
        right = gridSize//2

        gridArrayBuffer = VertexArrayBuffer((gridSize * 4,),
                                            GL.GL_LINES, textures=False, lights=False)

        gridArrayBuffer.rgba[:] = 255, 255, 255, 100

        # y=0, move by translating
        gridArrayBuffer.vertex[:, axis] = 0

        axis1 = (axis-1) % 3
        axis2 = (axis+1) % 3

        # left edge
        gridArrayBuffer.vertex[0:gridSize*2:2, axis2] = left
        gridArrayBuffer.vertex[0:gridSize*2:2, axis1] = range(left, right)

        # right edge
        gridArrayBuffer.vertex[1:gridSize*2:2, axis2] = right-1
        gridArrayBuffer.vertex[1:gridSize*2:2, axis1] = range(left, right)

        # bottom edge
        gridArrayBuffer.vertex[gridSize*2::2, axis1] = left
        gridArrayBuffer.vertex[gridSize*2::2, axis2] = range(left, right)

        # top edge
        gridArrayBuffer.vertex[gridSize*2+1::2, axis1] = right-1
        gridArrayBuffer.vertex[gridSize*2+1::2, axis2] = range(left, right)

        if self.vertexNode:
            self.removeChild(self.vertexNode)
        self.vertexNode = VertexNode([gridArrayBuffer])
        self.addChild(self.vertexNode)

    @property
    def position(self):
        return self.translateState.translateOffset

    @position.setter
    def position(self, value):
        self.translateState.translateOffset = value
