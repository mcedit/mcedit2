"""
    workplane
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from OpenGL import GL
from mcedit2.rendering import scenegraph, rendergraph
from mcedit2.rendering.vertexarraybuffer import VertexArrayBuffer

log = logging.getLogger(__name__)



class WorkplaneNode(scenegraph.Node):

    def __init__(self):
        super(WorkplaneNode, self).__init__()
        self.translateNode = scenegraph.TranslateNode()
        self.addChild(self.translateNode)
        gridSize = 64
        left = -gridSize//2
        right = gridSize//2

        gridArrayBuffer = VertexArrayBuffer((gridSize * 4,),
                                            GL.GL_LINES, textures=False, lights=False)

        gridArrayBuffer.rgba[:] = 255, 255, 255, 100

        # y=0, move by translating
        gridArrayBuffer.vertex[:, 1] = 0

        # left edge
        gridArrayBuffer.vertex[0:gridSize*2:2, 2] = left
        gridArrayBuffer.vertex[0:gridSize*2:2, 0] = range(left, right)

        # right edge
        gridArrayBuffer.vertex[1:gridSize*2:2, 2] = right-1
        gridArrayBuffer.vertex[1:gridSize*2:2, 0] = range(left, right)

        # bottom edge
        gridArrayBuffer.vertex[gridSize*2::2, 0] = left
        gridArrayBuffer.vertex[gridSize*2::2, 2] = range(left, right)

        # top edge
        gridArrayBuffer.vertex[gridSize*2+1::2, 0] = right-1
        gridArrayBuffer.vertex[gridSize*2+1::2, 2] = range(left, right)

        self.vertexNode = scenegraph.VertexNode([gridArrayBuffer])
        self.translateNode.addChild(self.vertexNode)

    @property
    def position(self):
        return self.translateNode.translateOffset

    @position.setter
    def position(self, value):
        self.translateNode.translateOffset = value
