"""
    selection
"""
from __future__ import absolute_import, division, print_function
import logging

from OpenGL import GL

from PySide import QtCore
import numpy

from mcedit2.rendering import cubes
from mcedit2.rendering.scenegraph import scenenode, rendernode
from mcedit2.rendering.chunknode import ChunkGroupNode, ChunkNode
from mcedit2.rendering.depths import DepthOffset
from mcedit2.rendering.renderstates import _RenderstateAlphaBlendNode
from mcedit2.rendering.scenegraph.scenenode import RenderstateNode
from mcedit2.rendering.scenegraph.vertex_array import VertexNode
from mcedit2.rendering.vertexarraybuffer import QuadVertexArrayBuffer
from mcedit2.util import profiler
from mcedit2.util.glutils import gl
from mceditlib import faces
from mceditlib.exceptions import ChunkNotPresent
from mceditlib.selection import SectionBox, BoundingBox, SelectionBox, rayIntersectsBox
from mceditlib.util import exhaust

log = logging.getLogger(__name__)


class CullFaceRenderNode(rendernode.RenderstateRenderNode):
    def enter(self):
        GL.glEnable(GL.GL_CULL_FACE)

    def exit(self):
        GL.glDisable(GL.GL_CULL_FACE)

class NonAirMaskSelection(SelectionBox):

    def __init__(self, dimension, box):
        """

        :param dimension:
        :type dimension: mceditlib.worldeditor.WorldEditorDimension
        :return:
        :rtype:
        """
        super(NonAirMaskSelection, self).__init__()
        self.box = box
        self.mincx = box.mincx
        self.mincy = box.mincy
        self.mincz = box.mincz
        self.maxcx = box.maxcx
        self.maxcy = box.maxcy
        self.maxcz = box.maxcz

        self.dimension = dimension

    def box_mask(self, box):
        """

        :param box:
        :type box: BoundingBox
        :return:
        :rtype:
        """
        #if self.volume > 40:
        #    import pdb; pdb.set_trace()

        mask = numpy.zeros(shape=box.size, dtype=bool)

        for cx, cz in box.chunkPositions():
            try:
                chunk = self.dimension.getChunk(cx, cz)
            except ChunkNotPresent:
                continue
            for cy in box.sectionPositions(cx, cz):
                section = chunk.getSection(cy)
                if section is None:
                    continue
                sectionBox = box.intersect(SectionBox(cx, cy, cz))
                if sectionBox.volume == 0:
                    continue
                slices = numpy.s_[
                    sectionBox.miny & 0xf:(sectionBox.miny & 0xf) + sectionBox.height,
                    sectionBox.minz & 0xf:(sectionBox.minz & 0xf) + sectionBox.length,
                    sectionBox.minx & 0xf:(sectionBox.minx & 0xf) + sectionBox.width,
                ]
                maskSlices = numpy.s_[
                    sectionBox.miny - box.miny:sectionBox.maxy - box.miny,
                    sectionBox.minz - box.minz:sectionBox.maxz - box.minz,
                    sectionBox.minx - box.minx:sectionBox.maxx - box.minx,
                ]
                blocks = section.Blocks
                mask[maskSlices] = blocks[slices] != 0

        return mask



class SelectionScene(scenenode.Node):
    def __init__(self):
        """

        :return:
        :rtype:
        """
        super(SelectionScene, self).__init__()
        self.cullNode = RenderstateNode(CullFaceRenderNode)
        self.blendNode = RenderstateNode(_RenderstateAlphaBlendNode)
        self.groupNode = ChunkGroupNode()
        self.cullNode.addChild(self.blendNode)
        self.blendNode.addChild(self.groupNode)
        self.addChild(self.cullNode)
        self.loadTimer = QtCore.QTimer(timeout=self.loadMore)
        self.loadTimer.setInterval(0)
        self.loadTimer.start()
        self.renderSelection = None

    def __del__(self):
        self.loadTimer.stop()

    _selection = None
    @property
    def selection(self):
        return self._selection

    @selection.setter
    def selection(self, selection):
        if selection != self._selection:
            self._selection = selection
            self.updateSelection()

    _dimension = None
    @property
    def dimension(self):
        return self._dimension

    @dimension.setter
    def dimension(self, value):
        if value != self._dimension:
            self._dimension = value
            self.updateSelection()

    @property
    def filled(self):
        return self.cullNode.visible

    @filled.setter
    def filled(self, value):
        self.cullNode.visible = value

    def updateSelection(self):
        if self.dimension is None or self.selection is None:
            return

        selection = self.selection
        self.renderSelection = selection & NonAirMaskSelection(self.dimension, selection)
        self.groupNode.clear()
        self._loader = None
        if selection.chunkCount < 16:
            exhaust(self.loadSections())

            self.loadTimer.setInterval(333)

    _loader = None

    def loadMore(self):
        if self._loader is None:
            self._loader = self.loadSections()
        try:
            self._loader.next()
        except StopIteration:
            self._loader = None

    @profiler.iterator("SelectionScene")
    def loadSections(self):
        selection = self.renderSelection
        if selection is None:
            self.loadTimer.setInterval(333)
            return
        else:
            self.loadTimer.setInterval(0)

        for cx, cz in selection.chunkPositions():
            if self.groupNode.containsChunkNode((cx, cz)):
                continue

            vertexArrays = []
            for cy in selection.sectionPositions(cx, cz):
                box = SectionBox(cx, cy, cz).expand(1)
                mask = selection.box_mask(box)
                if mask is not None:
                    vertexArrays.extend(self.buildSection(mask, cy))
            if len(vertexArrays):
                chunkNode = ChunkNode((cx, cz))
                vertexNode = VertexNode(vertexArrays)
                chunkNode.addChild(vertexNode)
                self.groupNode.addChunkNode(chunkNode)
            yield
        self.loadTimer.setInterval(333)

    def discardChunk(self, cx, cz):
        self.groupNode.discardChunkNode(cx, cz)

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
            blockMask = sectionMask[1:-1, 1:-1, 1:-1] & exposedFaceMask

            vertexBuffer = QuadVertexArrayBuffer.fromBlockMask(face, blockMask, False, False)
            if not len(vertexBuffer.vertex):
                continue

            vertexBuffer.rgb[:] = faceShades[face]
            vertexBuffer.alpha[:] = 0x77
            vertexBuffer.vertex[..., 1] += cy << 4
            vertexArrays.append(vertexBuffer)

        return vertexArrays


faceShades = {
    faces.FaceNorth: (0x33, 0x33, 0x99),
    faces.FaceSouth: (0x33, 0x33, 0x99),
    faces.FaceEast:  (0x44, 0x44, 0xCC),
    faces.FaceWest:  (0x44, 0x44, 0xCC),
    faces.FaceUp:    (0x55, 0x55, 0xFF),
    faces.FaceDown:  (0x22, 0x22, 0x77),
}

class SelectionBoxRenderNode(rendernode.RenderNode):
    def drawSelf(self):
        box = self.sceneNode.selectionBox
        if box is None:
            return

        r, g, b, alpha = self.sceneNode.color
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
                r, g, b, alpha = self.sceneNode.wireColor
                GL.glColor(r, g, b, alpha)
                GL.glLineWidth(2.0)
                cubes.drawBox(box, cubeType=GL.GL_LINES)
                GL.glDisable(GL.GL_DEPTH_TEST)
                GL.glLineWidth(1.0)
                cubes.drawBox(box, cubeType=GL.GL_LINES)

class SelectionBoxNode(scenenode.Node):
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

    _color = (.3, .3, 1, .3)
    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, value):
        self._color = value
        self.dirty = True

    _wireColor = (1, 1, 1, .6)
    @property
    def wireColor(self):
        return self._wireColor

    @wireColor.setter
    def wireColor(self, value):
        self._wireColor = value
        self.dirty = True


class SelectionFaceRenderNode(rendernode.RenderNode):
    def drawSelf(self):
        box = self.sceneNode.selectionBox
        if box is None:
            return

        alpha = 0.16
        r, g, b = self.sceneNode.color
        with gl.glPushAttrib(GL.GL_DEPTH_BUFFER_BIT | GL.GL_ENABLE_BIT | GL.GL_LINE_BIT):
            GL.glDisable(GL.GL_DEPTH_TEST)
            GL.glDepthMask(False)
            GL.glEnable(GL.GL_BLEND)
            GL.glPolygonOffset(self.sceneNode.depth, self.sceneNode.depth)

            GL.glColor(1.0, 1.0, 1.0, 1.0)
            GL.glLineWidth(2.0)
            cubes.drawFace(box, self.sceneNode.face, GL.GL_LINE_STRIP)
            GL.glColor(r, g, b, alpha)
            GL.glEnable(GL.GL_DEPTH_TEST)
            cubes.drawFace(box, self.sceneNode.face)


class SelectionFaceNode(scenenode.Node):
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

    _color = (.3, .3, 1)
    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, value):
        self._color = value
        self.dirty = True


def boxFaceUnderCursor(box, mouseRay):
    """
    Find the nearest face of the given bounding box that intersects with the given mouse ray
    and return (point, face)
    """
    nearPoint, mouseVector = mouseRay

    intersections = rayIntersectsBox(box, mouseRay)
    if intersections is None:
        return None, None

    point, face = intersections[0]

    # if the point is near the edge of the face, and the edge is facing away,
    # return the away-facing face

    dim = face.dimension

    dim1 = (dim + 1) % 3
    dim2 = (dim + 2) % 3

    # determine if a click was within self.edge_factor of the edge of a selection box side. if so, click through
    # to the opposite side
    edge_factor = 0.1

    for d in dim1, dim2:
        if not isinstance(d, int):
            assert False
        edge_width = box.size[d] * edge_factor
        faceNormal = [0, 0, 0]
        cameraBehind = False

        if point[d] - box.origin[d] < edge_width:
            faceNormal[d] = -1
            cameraBehind = nearPoint[d] - box.origin[d] > 0
        if point[d] - box.maximum[d] > -edge_width:
            faceNormal[d] = 1
            cameraBehind = nearPoint[d] - box.maximum[d] < 0

        if numpy.dot(faceNormal, mouseVector) > 0 or cameraBehind:
            # the face adjacent to the clicked edge faces away from the cam
            # xxxx this is where to allow iso views in face-on angles to grab edges
            # xxxx also change face highlight node to highlight this area
            return intersections[1] if len(intersections) > 1 else intersections[0]

    return point, face
