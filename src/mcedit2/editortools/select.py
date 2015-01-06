"""
    select
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from OpenGL import GL
from PySide import QtGui, QtCore
import numpy
from mcedit2.command import SimpleRevisionCommand
from mcedit2.editorcommands.fill import fillCommand
from mcedit2.editorcommands.replace import replaceCommand

from mcedit2.editortools import EditorTool
from mcedit2.rendering import cubes
from mcedit2.util.load_ui import load_ui
from mcedit2.util.glutils import gl
from mcedit2.rendering.depths import DepthOffset
from mcedit2.rendering import scenegraph, rendergraph
from mcedit2.util.showprogress import showProgress
from mcedit2.widgets.layout import Column
from mcedit2.worldview.worldview import boxFaceUnderCursor
from mceditlib import faces
from mceditlib.geometry import BoundingBox, Vector
from mceditlib.operations import ComposeOperations
from mceditlib.operations.entity import RemoveEntitiesOperation

log = logging.getLogger(__name__)


class SelectionCoordinateWidget(QtGui.QWidget):
    def __init__(self, *args, **kwargs):
        super(SelectionCoordinateWidget, self).__init__(*args, **kwargs)
        load_ui("selection_coord_widget.ui", baseinstance=self)

        self.xMinInput.valueChanged.connect(self.setMinX)
        self.yMinInput.valueChanged.connect(self.setMinY)
        self.zMinInput.valueChanged.connect(self.setMinZ)
        self.xMaxInput.valueChanged.connect(self.setMaxX)
        self.yMaxInput.valueChanged.connect(self.setMaxY)
        self.zMaxInput.valueChanged.connect(self.setMaxZ)

        self.editSizeInput.stateChanged.connect(self.editSizeClicked)

    def editSizeClicked(self, state):
        if state:
            size = self.boundingBox.size
            self.widthLabel.setText("W:")
            self.heightLabel.setText("H:")
            self.lengthLabel.setText("L:")

        else:
            size = self.boundingBox.maximum
            self.widthLabel.setText("to")
            self.heightLabel.setText("to")
            self.lengthLabel.setText("to")

        self.xMaxInput.setValue(size[0])
        self.yMaxInput.setValue(size[1])
        self.zMaxInput.setValue(size[2])

        minVal = 0 if state else -2000000000
        self.xMaxInput.setMinimum(minVal)
        self.yMaxInput.setMinimum(minVal)
        self.zMaxInput.setMinimum(minVal)


    boxChanged = QtCore.Signal(BoundingBox)

    _boundingBox = BoundingBox()
    @property
    def boundingBox(self):
        return self._boundingBox

    @boundingBox.setter
    def boundingBox(self, box):
        self.setEnabled(box is not None)
        self._boundingBox = box
        if box is not None:
            self.xMinInput.setValue(box.minx)
            self.yMinInput.setValue(box.miny)
            self.zMinInput.setValue(box.minz)

            if self.editSizeInput.checkState():
                self.xMaxInput.setValue(box.width)
                self.yMaxInput.setValue(box.height)
                self.zMaxInput.setValue(box.length)
            else:
                self.xMaxInput.setValue(box.maxx)
                self.yMaxInput.setValue(box.maxy)
                self.zMaxInput.setValue(box.maxz)

        self.boxChanged.emit(box)

    def setMinX(self, value):
        origin, size = self.boundingBox
        origin = value, origin[1], origin[2]
        self.boundingBox = BoundingBox(origin, size)

    def setMinY(self, value):
        origin, size = self.boundingBox
        origin = origin[0], value, origin[2]
        self.boundingBox = BoundingBox(origin, size)

    def setMinZ(self, value):
        origin, size = self.boundingBox
        origin = origin[0], origin[1], value
        self.boundingBox = BoundingBox(origin, size)

    def setMaxX(self, value):
        origin, size = self.boundingBox
        if self.editSizeInput.checkState():
            size = value, size[1], size[2]
        else:
            size = value - origin[0], size[1], size[2]
        self.boundingBox = BoundingBox(origin, size)

    def setMaxY(self, value):
        origin, size = self.boundingBox
        if self.editSizeInput.checkState():
            size = size[0], value, size[2]
        else:
            size = size[0], value - origin[1], size[2]
        self.boundingBox = BoundingBox(origin, size)

    def setMaxZ(self, value):
        origin, size = self.boundingBox
        if self.editSizeInput.checkState():
            size = size[0], size[1], value
        else:
            size = size[0], size[1], value - origin[2]
        self.boundingBox = BoundingBox(origin, size)



class SelectCommand(QtGui.QUndoCommand):
    def __init__(self, selectionTool, box, *args, **kwargs):
        QtGui.QUndoCommand.__init__(self, *args, **kwargs)
        self.setText("Box Selection")
        self.box = box
        self.selectionTool = selectionTool
        self.previousBox = None

    def undo(self):
        self.selectionTool.currentSelection = self.previousBox

    def redo(self):
        self.previousBox = self.selectionTool.currentSelection
        self.selectionTool.currentSelection = self.box

class SelectionTool(EditorTool):
    name = "Select"
    iconName = "select_blocks"

    def __init__(self, editorSession, *args, **kwargs):
        """
        :type editorSession: EditorSession
        """
        super(SelectionTool, self).__init__(editorSession, *args, **kwargs)
        toolWidget = QtGui.QWidget()

        self.toolWidget = toolWidget

        self.coordInput = SelectionCoordinateWidget()
        self.coordInput.boxChanged.connect(self.coordInputChanged)

        self.deselectButton = QtGui.QPushButton(self.tr("Deselect"))
        self.deselectButton.clicked.connect(self.deselect)
        self.deleteSelectionButton = QtGui.QPushButton(self.tr("Delete"))
        self.deleteSelectionButton.clicked.connect(self.deleteSelection)
        self.deleteBlocksButton = QtGui.QPushButton(self.tr("Delete Blocks"))
        self.deleteBlocksButton.clicked.connect(self.deleteBlocks)
        self.deleteEntitiesButton = QtGui.QPushButton(self.tr("Delete Entities"))
        self.deleteEntitiesButton.clicked.connect(self.deleteEntities)
        self.fillButton = QtGui.QPushButton(self.tr("Fill"))
        self.fillButton.clicked.connect(self.fill)
        self.replaceButton = QtGui.QPushButton(self.tr("Replace"))
        self.replaceButton.clicked.connect(self.replace)

        self.toolWidget.setLayout(Column(self.coordInput,
                                         self.deselectButton,
                                         self.deleteSelectionButton,
                                         self.deleteBlocksButton,
                                         self.deleteEntitiesButton,
                                         self.fillButton,
                                         self.replaceButton,
                                         None))

        self.cursorNode = SelectionCursor()
        self.overlayNode = scenegraph.Node()
        self.faceHoverNode = SelectionFaceNode()
        self.selectionNode = SelectionBoxNode()
        self.overlayNode.addChild(self.selectionNode)
        self.overlayNode.addChild(self.faceHoverNode)

        self.newSelectionNode = None
        self.currentSelection = None

    @property
    def hideSelectionWalls(self):
        return not self.selectionNode.filled

    @hideSelectionWalls.setter
    def hideSelectionWalls(self, value):
        self.selectionNode.filled = not value


    @property
    def currentSelection(self):
        return self._currentSelection

    @currentSelection.setter
    def currentSelection(self, value):
        self._currentSelection = value
        self.coordInput.boundingBox = value
        self.updateNodes()

    def coordInputChanged(self, box):
        self._currentSelection = box
        self.updateNodes()

    def updateNodes(self):
        box = self.currentSelection
        if box:
            self.selectionNode.visible = True
            self.selectionNode.selectionBox = box
        else:
            self.selectionNode.visible = False
            self.faceHoverNode.visible = False

    def deleteSelection(self):
        command = SimpleRevisionCommand(self.editorSession, "Delete")
        with command.begin():
            fillTask = self.editorSession.currentDimension.fillBlocksIter(self.editorSession.currentSelection, "air")
            entitiesTask = RemoveEntitiesOperation(self.editorSession.currentDimension, self.editorSession.currentSelection)
            task = ComposeOperations(fillTask, entitiesTask)
            showProgress("Deleting...", task)
        self.editorSession.pushCommand(command)

    def deleteBlocks(self):
        pass

    def deleteEntities(self):
        pass

    def fill(self):
        fillCommand(self.editorSession)

    def replace(self):
        replaceCommand(self.editorSession)

    dragStartPoint = None
    dragStartFace = None

    def mousePress(self, event):
        if self.currentSelection:
            # Find side of existing selection to drag
            # xxxx can't do this with disjoint selections?
            point, face = boxFaceUnderCursor(self.currentSelection, event.ray)

            if face is not None:
                log.info("Beginning drag resize")
                self.dragResizeFace = face
                # Choose a dimension perpendicular to the dragged face
                self.dragResizeDimension = ((face.dimension + 1) % 2)

                self.dragResizePosition = point[self.dragResizeDimension]

                return

        self.dragStartPoint = event.blockPosition
        self.dragStartFace = faces.FaceYIncreasing  # event.blockFace

    def mouseMove(self, event):
        self.mouseDrag(event)

    def mouseDrag(self, event):
        # Update cursor
        self.cursorNode.point = event.blockPosition
        self.cursorNode.face = event.blockFace

        if self.dragStartPoint:
            # Show new box being dragged out
            newBox = self.boxFromDragSelect(event.ray)
            self.selectionNode.visible = True
            self.selectionNode.selectionBox = newBox
        else:
            if self.dragResizeFace is not None:
                # Hilite face being dragged
                newBox = self.boxFromDragResize(self.currentSelection, event.ray)
                self.faceHoverNode.selectionBox = newBox
                self.faceHoverNode.visible = True

                # Update selection box to resized size in progress
                newBox = self.boxFromDragResize(self.currentSelection, event.ray)
                self.selectionNode.selectionBox = newBox
            elif self.currentSelection is not None:
                # Hilite face cursor is over
                point, face = boxFaceUnderCursor(self.currentSelection, event.ray)
                if face is not None:
                    self.faceHoverNode.visible = True

                    self.faceHoverNode.face = face
                    self.faceHoverNode.selectionBox = self.currentSelection
                else:
                    self.faceHoverNode.visible = False

    def mouseRelease(self, event):
        editor = self.editorSession
        if self.dragStartPoint:
            newBox = self.boxFromDragSelect(event.ray)
            command = SelectCommand(self, newBox)
            editor.undoStack.push(command)
            self.dragStartPoint = None
            return

        if self.dragResizeFace is not None:
            box = self.currentSelection
            if box is not None:
                newBox = self.boxFromDragResize(box, event.ray)

                command = SelectCommand(self, newBox)
                editor.undoStack.push(command)

            self.dragResizeFace = None
            self.faceHoverNode.visible = False
            return

    def deselect(self):
        editor = self.editorSession
        command = SelectCommand(self, None)
        editor.undoStack.push(command)

    selectionColor = (0.8, 0.8, 1.0)
    alpha = 0.33

    showPreviousSelection = True
    dragResizeFace = None
    dragResizeDimension = None
    dragResizePosition = None

    def dragResizePoint(self, ray):
        # returns a point representing the intersection between the mouse ray
        # and an imaginary plane perpendicular to the dragged face

        """

        :type ray: Ray
        :rtype: Vector
        """
        nearPoint, normal = ray

        dim = self.dragResizeDimension
        distance = self.dragResizePosition - nearPoint[dim]

        scale = distance / (normal[dim] or 0.0001)
        point = normal * scale + nearPoint
        return point

    def boxFromDragResize(self, box, ray):
        point = self.dragResizePoint(ray)

        side = self.dragResizeFace & 1
        dragdim = self.dragResizeFace >> 1


        o, s = list(box.origin), list(box.size)
        if side:
            o[dragdim] += s[dragdim]
        s[dragdim] = 0

        otherSide = BoundingBox(o, s)
        o[dragdim] = int(numpy.floor(point[dragdim] + 0.5))
        thisSide = BoundingBox(o, s)

        return thisSide.union(otherSide)

    def boxFromDragSelect(self, ray):
        """
        Create a flat selection from dragging the mouse outside the selection.

        :type ray: mcedit2.util.geometry.Ray
        :rtype: BoundingBox
        """
        point = self.dragStartPoint
        face = self.dragStartFace
        size = [1, 1, 1]

        dim = face >> 1
        size[dim] = 0
        s = [0,0,0]

        if face & 1 == 0:
            s[dim] = 1
            point = point + s

        startBox = BoundingBox(point, size)
        endPoint = ray.intersectPlane(dim, point[dim])
        endBox = BoundingBox(endPoint.intfloor(), size)

        return startBox.union(endBox)

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


class SelectionCursorRenderNode(rendergraph.RenderNode):
    def drawSelf(self):
        point = self.sceneNode.point
        if point is None:
            return
        selectionColor = map(lambda a: a * a * a * a, self.sceneNode.color)
        r, g, b = selectionColor
        alpha = 0.3
        box = BoundingBox(point, (1, 1, 1))

        with gl.glPushAttrib(GL.GL_DEPTH_BUFFER_BIT | GL.GL_ENABLE_BIT):
            GL.glDepthMask(False)
            GL.glEnable(GL.GL_BLEND)
            GL.glPolygonOffset(DepthOffset.SelectionCursor, DepthOffset.SelectionCursor)

            # Wire box
            GL.glColor(1., 1., 1., alpha)
            cubes.drawBox(box, cubeType=GL.GL_LINES)

            # Highlighted face
            GL.glColor(r, g, b, alpha)
            cubes.drawFace(box, self.sceneNode.face)


class SelectionCursor(scenegraph.Node):
    RenderNodeClass = SelectionCursorRenderNode
    def __init__(self, point=Vector(0, 0, 0), face=faces.FaceXDecreasing, color=(1, .3, 1)):
        super(SelectionCursor, self).__init__()
        self._point = point
        self._face = face
        self._color = color

    @property
    def point(self):
        return self._point

    @point.setter
    def point(self, value):
        self._point = value
        self.dirty = True

    @property
    def face(self):
        return self._face

    @face.setter
    def face(self, value):
        self._face = value
        self.dirty = True

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, value):
        self._color = value
        self.dirty = True
