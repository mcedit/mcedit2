"""
    select
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

import time
from OpenGL import GL
from PySide import QtGui, QtCore

from mcedit2.editortools import EditorTool
from mcedit2.editortools.brush.shapes import ChunkShape
from mcedit2.handles.boxhandle import BoxHandle
from mcedit2.rendering import cubes
from mcedit2.rendering.selection import SelectionScene, SelectionFaceNode
from mcedit2.ui.selection_coord_widget import Ui_selectionCoordWidget
from mcedit2.util.glutils import gl
from mcedit2.rendering.depths import DepthOffsets
from mcedit2.rendering.scenegraph import scenenode, rendernode
from mcedit2.util.settings import Settings
from mcedit2.widgets.layout import Column
from mcedit2.widgets.shapewidget import ShapeWidget
from mceditlib import faces
from mceditlib.geometry import Vector
from mceditlib.selection import BoundingBox

log = logging.getLogger(__name__)

SelectionOptions = Settings().getNamespace("select_tool")
ClassicSelectionOption = SelectionOptions.getOption("classic_selection", bool, False)
StickySelectionOption = SelectionOptions.getOption("sticky_selection", bool, False)


class SelectionCoordinateWidget(QtGui.QWidget, Ui_selectionCoordWidget):
    def __init__(self, *args, **kwargs):
        super(SelectionCoordinateWidget, self).__init__(*args, **kwargs)
        self.setupUi(self)

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

        minVal = 0 if state else -2000000000
        self.xMaxInput.setMinimum(minVal)
        self.yMaxInput.setMinimum(minVal)
        self.zMaxInput.setMinimum(minVal)

        self.xMaxInput.setValue(size[0])
        self.yMaxInput.setValue(size[1])
        self.zMaxInput.setValue(size[2])


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

    def setMinX(self, value):
        origin, size = self.boundingBox
        dx = value - origin[0]
        size = size[0] - dx, size[1], size[2]
        origin = value, origin[1], origin[2]
        box = BoundingBox(origin, size)
        self.boundingBox = box
        self.boxChanged.emit(box)

    def setMinY(self, value):
        origin, size = self.boundingBox
        dy = value - origin[1]
        size = size[0], size[1] - dy, size[2]
        origin = origin[0], value, origin[2]
        box = BoundingBox(origin, size)
        self.boundingBox = box
        self.boxChanged.emit(box)

    def setMinZ(self, value):
        origin, size = self.boundingBox
        dz = value - origin[2]
        size = size[0], size[1], size[2] - dz
        origin = origin[0], origin[1], value
        box = BoundingBox(origin, size)
        self.boundingBox = box
        self.boxChanged.emit(box)

    def setMaxX(self, value):
        origin, size = self.boundingBox
        if self.editSizeInput.checkState():
            size = value, size[1], size[2]
        else:
            size = value - origin[0], size[1], size[2]
        box = BoundingBox(origin, size)
        self.boundingBox = box
        self.boxChanged.emit(box)

    def setMaxY(self, value):
        origin, size = self.boundingBox
        if self.editSizeInput.checkState():
            size = size[0], value, size[2]
        else:
            size = size[0], value - origin[1], size[2]
        box = BoundingBox(origin, size)
        self.boundingBox = box
        self.boxChanged.emit(box)

    def setMaxZ(self, value):
        origin, size = self.boundingBox
        if self.editSizeInput.checkState():
            size = size[0], size[1], value
        else:
            size = size[0], size[1], value - origin[2]
        box = BoundingBox(origin, size)
        self.boundingBox = box
        self.boxChanged.emit(box)


class SelectCommand(QtGui.QUndoCommand):
    def __init__(self, editorSession, box, text=None, *args, **kwargs):
        QtGui.QUndoCommand.__init__(self, *args, **kwargs)
        if text is None:
            text = QtGui.qApp.tr("Box Selection")
        self.setText(text)
        self.box = box
        self.editorSession = editorSession
        self.previousBox = None

    def undo(self):
        self.editorSession.currentSelection = self.previousBox

    def redo(self):
        self.previousBox = self.editorSession.currentSelection
        self.editorSession.currentSelection = self.box


class SelectionTool(EditorTool):
    name = "Select"
    iconName = "select_blocks"

    def __init__(self, editorSession, *args, **kwargs):
        """
        :type editorSession: EditorSession
        """
        super(SelectionTool, self).__init__(editorSession, *args, **kwargs)
        toolWidget = QtGui.QWidget()

        editorSession.selectionChanged.connect(self.selectionDidChange)

        self.toolWidget = toolWidget

        self.optionsButton = QtGui.QPushButton(self.tr("Options"))

        self.optionsMenu = QtGui.QMenu()
        self.optionsButton.setMenu(self.optionsMenu)
        
        classicSelectionAction = self.optionsMenu.addAction(self.tr("Classic Selection"))
        stickySelectionAction = self.optionsMenu.addAction(self.tr("Sticky Selection"))

        self.coordInput = SelectionCoordinateWidget()
        self.coordInput.boxChanged.connect(self.coordInputChanged)
        self.shapeInput = ShapeWidget(addShapes=[ChunkShape()])
        self.shapeInput.shapeChanged.connect(self.shapeDidChange)
        self.shapeInput.shapeOptionsChanged.connect(self.shapeDidChange)

        self.toolWidget.setLayout(Column(self.optionsButton,
                                         self.coordInput,
                                         self.shapeInput,
                                         None))

        self.cursorNode = SelectionCursor()
        self.overlayNode = scenenode.Node("selectOverlay")
        self.faceHoverNode = SelectionFaceNode()
        self.selectionNode = SelectionScene()
        self.overlayNode.addChild(self.selectionNode)
        self.overlayNode.addChild(self.faceHoverNode)

        self.boxHandleNode = BoxHandle()
        self.boxHandleNode.boundsChanged.connect(self.boxHandleResized)
        self.boxHandleNode.boundsChangedDone.connect(self.boxHandleResizedDone)
        self.overlayNode.addChild(self.boxHandleNode)

        self.newSelectionNode = None

        classicSelectionAction.setCheckable(True)
        classicSelectionAction.toggled.connect(ClassicSelectionOption.setValue)
        classicSelectionAction.setChecked(ClassicSelectionOption.value())
        ClassicSelectionOption.connectAndCall(self.setClassicSelection)

        stickySelectionAction.setCheckable(True)
        stickySelectionAction.toggled.connect(StickySelectionOption.setValue)
        stickySelectionAction.setChecked(StickySelectionOption.value())
        StickySelectionOption.connectAndCall(self.setStickySelection)

        editorSession.dimensionChanged.connect(self.dimensionDidChange)
        editorSession.revisionChanged.connect(self.revisionDidChange)

    def revisionDidChange(self, changes):
        chunks = changes.chunks[self.editorSession.currentDimension.dimName]
        for cx, cz in chunks:
            self.selectionNode.discardChunk(cx, cz)

    def dimensionDidChange(self):
        self.selectionNode.dimension = self.editorSession.currentDimension

    def shapeDidChange(self):
        if self.currentSelection is not None:
            self.currentSelection = self.createShapedSelection(self.currentSelection)

    def toolActive(self):
        self.boxHandleNode.boxNode.wireColor = 1, 1, 1, .5

    def toolInactive(self):
        self.faceHoverNode.visible = False
        self.boxHandleNode.boxNode.wireColor = 1, 1, 1, .33

    @property
    def hideSelectionWalls(self):
        return not self.selectionNode.filled

    @hideSelectionWalls.setter
    def hideSelectionWalls(self, value):
        self.selectionNode.filled = not value

    @property
    def currentSelection(self):
        return self.editorSession.currentSelection

    @currentSelection.setter
    def currentSelection(self, value):
        self.editorSession.currentSelection = value

    def coordInputChanged(self, box):
        self.currentSelection = self.createShapedSelection(box)

    def selectionDidChange(self, value):
        self.coordInput.boundingBox = value
        self.updateNodes()

    def updateNodes(self):
        box = self.currentSelection
        if box:
            self.boxHandleNode.bounds = BoundingBox(box.origin, box.size)
            self.selectionNode.visible = True
            self.selectionNode.selection = box
        else:
            self.boxHandleNode.bounds = None
            self.selectionNode.visible = False
            self.faceHoverNode.visible = False
            self.selectionNode.selection = None

    lastResizeTime = time.time()

    def boxHandleResized(self, box):
        if box is not None:
            self.selectionNode.selection = self.createShapedSelection(box)
            if time.time() - self.lastResizeTime > 0.025:
                self.selectionNode.loadImmediateChunks(0.025)
            self.lastResizeTime = time.time()
        else:
            self.selectionNode.selection = None

    def boxHandleResizedDone(self, box, oldBox):
        if box is not None:
            selection = self.createShapedSelection(box)
            command = SelectCommand(self.editorSession, selection)
            if oldBox is not None:
                command.setText(self.tr("Resize Selection"))
            self.editorSession.pushCommand(command)
            self.updateNodes()
            self.selectionNode.loadImmediateChunks()
        else:
            self.selectionNode.selection = None

    def mousePress(self, event):
        self.boxHandleNode.mousePress(event)

    def mouseMove(self, event):
        self.mouseDrag(event)

    def mouseDrag(self, event):
        # Update cursor
        self.cursorNode.point = event.blockPosition
        self.cursorNode.face = event.blockFace

        self.boxHandleNode.mouseMove(event)

    def mouseRelease(self, event):
        self.boxHandleNode.mouseRelease(event)

    selectionColor = (0.8, 0.8, 1.0)
    alpha = 0.33

    showPreviousSelection = True

    def createShapedSelection(self, box):
        return self.shapeInput.currentShape.createShapedSelection(box, self.editorSession.currentDimension)

    def setClassicSelection(self, enabled):
        self.boxHandleNode.classicSelection = enabled

    def setStickySelection(self, enabled):
        self.boxHandleNode.stickySelection = enabled


class SelectionCursorRenderNode(rendernode.RenderNode):
    def drawSelf(self):
        point = self.sceneNode.point
        if point is None:
            return

        r, g, b, a = self.sceneNode.color
        box = BoundingBox(point, (1, 1, 1))

        with gl.glPushAttrib(GL.GL_DEPTH_BUFFER_BIT | GL.GL_ENABLE_BIT | GL.GL_POLYGON_BIT):
            GL.glDepthMask(False)
            GL.glEnable(GL.GL_BLEND)
            GL.glPolygonOffset(DepthOffsets.SelectionCursor, DepthOffsets.SelectionCursor)

            # Highlighted face

            GL.glPolygonMode(GL.GL_FRONT_AND_BACK, GL.GL_FILL)

            GL.glColor(r, g, b, a)
            cubes.drawFace(box, self.sceneNode.face)

            # Wire box
            GL.glPolygonMode(GL.GL_FRONT_AND_BACK, GL.GL_LINE)

            GL.glLineWidth(3.0)
            GL.glColor(1., 1., 1., a)

            cubes.drawBox(box)

            GL.glLineWidth(1.0)
            GL.glColor(0.2, 0.2, 0.2, a)

            cubes.drawBox(box)


class SelectionCursor(scenenode.Node):
    RenderNodeClass = SelectionCursorRenderNode

    def __init__(self, point=Vector(0, 0, 0), face=faces.FaceXDecreasing, color=(.3, .3, 1, .8)):
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
