"""
    selection
"""
from __future__ import absolute_import, division, print_function
from OpenGL import GL
from PySide import QtCore
import logging
import numpy
from mcedit2.rendering import scenegraph, rendergraph, cubes
from mcedit2.rendering.chunknode import ChunkGroupNode, ChunkNode
from mcedit2.rendering.depths import DepthOffset
from mcedit2.rendering.renderstates import _RenderstateAlphaBlendNode
from mcedit2.rendering.scenegraph import VertexNode, RenderstateNode
from mcedit2.rendering.vertexarraybuffer import VertexArrayBuffer
from mcedit2.util.glutils import gl
from mceditlib import faces
from mceditlib.geometry import SectionBox

log = logging.getLogger(__name__)


class CullFaceRenderNode(rendergraph.RenderstateRenderNode):
    def enter(self):
        GL.glEnable(GL.GL_CULL_FACE)

    def exit(self):
        GL.glDisable(GL.GL_CULL_FACE)

class SelectionScene(scenegraph.Node):
    def __init__(self):
        """

        :return:
        :rtype:
        """
        super(SelectionScene, self).__init__()
        self.cullNode = RenderstateNode(CullFaceRenderNode)
        self.blendNode = RenderstateNode(_RenderstateAlphaBlendNode)
        self.groupNode = ChunkGroupNode()
        self.boxNode = SelectionBoxNode()
        self.boxNode.filled = False
        self.cullNode.addChild(self.blendNode)
        self.blendNode.addChild(self.groupNode)
        self.addChild(self.cullNode)
        self.addChild(self.boxNode)
        self.loadTimer = QtCore.QTimer(timeout=self.loadMore)
        self.loadTimer.setInterval(0)
        self.loadTimer.start()

    def __del__(self):
        self.loadTimer.stop()

    _selection = None
    @property
    def selection(self):
        return self._selection

    @selection.setter
    def selection(self, value):
        if value != self._selection:
            self._selection = value
            self.boxNode.selectionBox = value
            self.groupNode.clear()
            self._loader = None

    _loader = None
    def loadMore(self):
        if self._loader is None:
            self._loader = self.loadSections()
        try:
            self._loader.next()
        except StopIteration:
            self._loader = None

    def loadSections(self):
        if self.selection is None:
            self.loadTimer.setInterval(333)
            return
        else:
            self.loadTimer.setInterval(0)

        for cx, cz in self.selection.chunkPositions():
            if self.groupNode.containsChunkNode((cx, cz)):
                continue

            vertexArrays = []
            for cy in self.selection.sectionPositions(cx, cz):
                box = SectionBox(cx, cy, cz).expand(1)
                mask = self.selection.box_mask(box)
                if mask is not None:
                    vertexArrays.extend(self.buildSection(mask, cy))
            if len(vertexArrays):
                chunkNode = ChunkNode((cx, cz))
                vertexNode = VertexNode(vertexArrays)
                chunkNode.addChild(vertexNode)
                self.groupNode.addChunkNode(chunkNode)
            yield

    def exposedBlockMasks(self, mask):
        """
        Compare adjacent cells in the 3d mask along all three axes and return one mask for each cardinal direction.
        The returned masks contain the faces of each cell which are exposed in that direction and should be rendered.

        :param mask:
        :type mask: ndarray
        :return:
        :rtype: list[ndarray]
        """
        sy = sz = sx = 16
        exposedY = numpy.zeros((sy+1, sz, sx), dtype=bool)
        exposedZ = numpy.zeros((sy, sz+1, sx), dtype=bool)
        exposedX = numpy.zeros((sy, sz, sx+1), dtype=bool)

        exposedY[:] = mask[1:,   1:-1, 1:-1] != mask[ :-1, 1:-1, 1:-1]
        exposedZ[:] = mask[1:-1, 1:,   1:-1] != mask[1:-1,  :-1, 1:-1]
        exposedX[:] = mask[1:-1, 1:-1, 1:  ] != mask[1:-1, 1:-1,  :-1]

        exposedByFace = [
            exposedX[:, :, 1:],
            exposedX[:, :, :-1],
            exposedY[1:],
            exposedY[:-1],
            exposedZ[:, 1:],
            exposedZ[:, :-1],
        ]

        return exposedByFace

    def buildSection(self, sectionMask, cy):
        vertexArrays = []

        for (face, exposedFaceMask) in enumerate(self.exposedBlockMasks(sectionMask)):
            blockIndices = sectionMask[1:-1, 1:-1, 1:-1] & exposedFaceMask

            vertexBuffer = VertexArrayBuffer.fromIndices(face, blockIndices, False, False)
            if not len(vertexBuffer.vertex):
                continue

            vertexBuffer.rgb[:] = faceShades[face]
            vertexBuffer.alpha[:] = 0xff
            vertexBuffer.vertex[..., 1] += cy << 4
            vertexArrays.append(vertexBuffer)

        return vertexArrays


faceShades = {
    faces.FaceNorth: 0x99,
    faces.FaceSouth: 0x99,
    faces.FaceEast: 0xCC,
    faces.FaceWest: 0xCC,
    faces.FaceUp: 0xFF,
    faces.FaceDown: 0x77,
}

class SelectionBoxRenderNode(rendergraph.RenderNode):
    def drawSelf(self):
        box = self.sceneNode.selectionBox
        if box is None:
            return

        alpha = 0.3
        r, g, b = self.sceneNode.color
        with gl.glPushAttrib(GL.GL_DEPTH_BUFFER_BIT | GL.GL_ENABLE_BIT | GL.GL_POLYGON_BIT):
            GL.glDepthMask(False)
            GL.glEnable(GL.GL_BLEND)
            GL.glPolygonOffset(self.sceneNode.depth, self.sceneNode.depth)

            if self.sceneNode.filled:
                # Filled box
                GL.glColor(r, g, b, alpha)
                cubes.drawBox(box)

            if self.sceneNode.wire:
                # Wire box, thinner behind terrain
                GL.glColor(1., 1., 1., alpha)
                GL.glLineWidth(2.0)
                cubes.drawBox(box, cubeType=GL.GL_LINES)
                GL.glDisable(GL.GL_DEPTH_TEST)
                GL.glLineWidth(1.0)
                cubes.drawBox(box, cubeType=GL.GL_LINES)

class SelectionBoxNode(scenegraph.Node):
    RenderNodeClass = SelectionBoxRenderNode
    _selectionBox = None
    depth = DepthOffset.Selection
    wire = True

    _filled = True
    @property
    def filled(self):
        return self._filled

    @filled.setter
    def filled(self, value):
        self._filled = value
        self.dirty = True

    @property
    def selectionBox(self):
        return self._selectionBox

    @selectionBox.setter
    def selectionBox(self, value):
        self._selectionBox = value
        self.dirty = True

    _color = (1, .3, 1)
    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, value):
        self._color = value
        self.dirty = True


class SelectionFaceRenderNode(rendergraph.RenderNode):
    def drawSelf(self):
        box = self.sceneNode.selectionBox
        if box is None:
            return

        alpha = 0.3
        r, g, b = self.sceneNode.color
        with gl.glPushAttrib(GL.GL_DEPTH_BUFFER_BIT | GL.GL_ENABLE_BIT):
            GL.glDisable(GL.GL_DEPTH_TEST)
            GL.glDepthMask(False)
            GL.glEnable(GL.GL_BLEND)
            GL.glPolygonOffset(self.sceneNode.depth, self.sceneNode.depth)

            GL.glColor(r, g, b, alpha)
            cubes.drawFace(box, self.sceneNode.face)


class SelectionFaceNode(scenegraph.Node):
    RenderNodeClass = SelectionFaceRenderNode
    _selectionBox = None
    _face = faces.FaceYIncreasing
    depth = DepthOffset.Selection

    @property
    def selectionBox(self):
        return self._selectionBox

    @selectionBox.setter
    def selectionBox(self, value):
        self._selectionBox = value
        self.dirty = True


    @property
    def face(self):
        return self._face

    @face.setter
    def face(self, value):
        self._face = value
        self.dirty = True

    _color = (1, .3, 1)
    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, value):
        self._color = value
        self.dirty = True
