"""
    move
"""
from __future__ import absolute_import, division, print_function
import logging

from PySide import QtGui, QtCore
from mcedit2.editorsession import PendingImport

from mcedit2.editortools import EditorTool
from mcedit2.command import SimpleRevisionCommand
from mcedit2.editortools.select import SelectionFaceNode
from mcedit2.rendering.selection import SelectionBoxNode, SelectionFaceNode
from mcedit2.rendering import scenegraph
from mcedit2.rendering.depths import DepthOffset
from mcedit2.rendering.worldscene import WorldScene
from mcedit2.util.load_ui import load_ui
from mcedit2.util.showprogress import showProgress
from mcedit2.util.worldloader import WorldLoader
from mcedit2.widgets.layout import Column
from mcedit2.worldview.worldview import boxFaceUnderCursor
from mceditlib.geometry import Vector
from mceditlib.selection import BoundingBox

log = logging.getLogger(__name__)

class MoveSelectionCommand(SimpleRevisionCommand):
    def __init__(self, moveTool, pendingImport, text=None, *args, **kwargs):
        if text is None:
            text = moveTool.tr("Move Selected Object")
        super(MoveSelectionCommand, self).__init__(moveTool.editorSession, text, *args, **kwargs)
        self.currentImport = pendingImport
        self.moveTool = moveTool

    def undo(self):
        super(MoveSelectionCommand, self).undo()
        self.moveTool.currentImport = None
        self.editorSession.removePendingImport(self.currentImport)
        self.moveTool.editorSession.chooseTool("Select")

    def redo(self):
        self.moveTool.currentImport = self.currentImport
        self.editorSession.addPendingImport(self.currentImport)
        self.moveTool.editorSession.chooseTool("Move")
        super(MoveSelectionCommand, self).redo()


class MoveOffsetCommand(QtGui.QUndoCommand):

    def __init__(self, moveTool, oldPoint, newPoint):
        super(MoveOffsetCommand, self).__init__()
        self.setText(moveTool.tr("Move Object"))
        self.newPoint = newPoint
        self.oldPoint = oldPoint
        self.moveTool = moveTool

    def undo(self):
        self.moveTool.movePosition = self.oldPoint

    def redo(self):
        self.moveTool.movePosition = self.newPoint

class MoveFinishCommand(SimpleRevisionCommand):
    def __init__(self, moveTool, pendingImport, *args, **kwargs):
        super(MoveFinishCommand, self).__init__(moveTool.editorSession, moveTool.tr("Finish Move"), *args, **kwargs)
        self.currentImport = pendingImport
        self.moveTool = moveTool

    def undo(self):
        super(MoveFinishCommand, self).undo()
        self.moveTool.pendingImport = self.currentImport
        self.editorSession.currentSelection = self.previousSelection
        self.editorSession.chooseTool("Move")

    def redo(self):
        super(MoveFinishCommand, self).redo()
        self.previousSelection = self.editorSession.currentSelection
        self.currentImport = self.moveTool.currentImport
        self.editorSession.currentSelection = BoundingBox(self.pendingImport.pos, self.previousSelection.size)
        self.moveTool.currentImport = None
        self.editorSession.removePendingImport(self.currentImport)


class CoordinateWidget(QtGui.QWidget):
    def __init__(self, *args, **kwargs):
        super(CoordinateWidget, self).__init__(*args, **kwargs)
        load_ui("coord_widget.ui", baseinstance=self)

        self.xInput.valueChanged.connect(self.setX)
        self.yInput.valueChanged.connect(self.setY)
        self.zInput.valueChanged.connect(self.setZ)

    pointChanged = QtCore.Signal(BoundingBox)

    _point = Vector(0, 0, 0)

    @property
    def point(self):
        return self._point

    @point.setter
    def point(self, point):
        self.setEnabled(point is not None)
        self._point = point
        if point is not None:
            x, y, z = point
            self.xInput.setValue(x)
            self.yInput.setValue(y)
            self.zInput.setValue(z)

        self.pointChanged.emit(point)

    def setX(self, value):
        x, y, z = self.point
        self.point = Vector(value, y, z)

    def setY(self, value):
        x, y, z = self.point
        self.point = Vector(x, value, z)

    def setZ(self, value):
        x, y, z = self.point
        self.point = Vector(x, y, value)


class MoveTool(EditorTool):
    iconName = "move"
    name = "Move"

    def __init__(self, editorSession, *args, **kwargs):
        super(MoveTool, self).__init__(editorSession, *args, **kwargs)
        self.overlayNode = scenegraph.Node()
        self.translateNode = scenegraph.TranslateNode()
        self.overlayNode.addChild(self.translateNode)

        self.sceneHolderNode = scenegraph.Node()
        self.translateNode.addChild(self.sceneHolderNode)

        self.outlineNode = SelectionBoxNode()
        self.outlineNode.color = .9, 1., 1.
        self.translateNode.addChild(self.outlineNode)

        self.faceHoverNode = SelectionFaceNode()
        self.translateNode.addChild(self.faceHoverNode)

        self.movingWorldScene = None
        self.loader = None
        self.dragStartFace = None
        self.dragStartPoint = None

        self.toolWidget = QtGui.QWidget()
        self.pointInput = CoordinateWidget()
        self.pointInput.pointChanged.connect(self.pointInputChanged)
        confirmButton = QtGui.QPushButton("Confirm")  # xxxx should be in worldview
        confirmButton.clicked.connect(self.confirmImport)
        self.toolWidget.setLayout(Column(self.pointInput,
                                         confirmButton,
                                         None))


    @property
    def movePosition(self):
        return None if self.currentImport is None else self.currentImport.pos

    @movePosition.setter
    def movePosition(self, value):
        """

        :type value: Vector
        """
        self.pointInput.point = value
        self.pointInputChanged(value)

    def doMoveOffsetCommand(self, oldPoint, newPoint):
        if newPoint != oldPoint:
            command = MoveOffsetCommand(self, oldPoint, newPoint)
            self.editorSession.pushCommand(command)

    def pointInputChanged(self, value):
        if value is not None:
            self.currentImport.pos = value
            self.translateNode.visible = True
            self.translateNode.translateOffset = value
        else:
            self.translateNode.visible = False

    _currentImport = None

    @property
    def currentImport(self):
        return self._currentImport

    @currentImport.setter
    def currentImport(self, value):
        oldVal = self._currentImport
        self._currentImport = value
        if oldVal is not value:
            self.updateOverlay()
        self.pointInput.setEnabled(value is not None)


    def updateOverlay(self):
        if self.currentImport is None:
            log.info("updateOverlay: Nothing to display")
            if self.movingWorldScene:
                self.sceneHolderNode.removeChild(self.movingWorldScene)
                self.movingWorldScene = None
            self.outlineNode.visible = False


        log.info("Updating move schematic scene: %s", self.currentImport)
        if self.movingWorldScene:
            self.loader.timer.stop()
            self.sceneHolderNode.removeChild(self.movingWorldScene)
        if self.currentImport:
            dim = self.currentImport.schematic.getDimension()
            self.movingWorldScene = WorldScene(dim, self.editorSession.textureAtlas)
            # xxx assumes import is same blocktypes as world, find atlas for imported object
            self.outlineNode.selectionBox = dim.bounds
            self.outlineNode.filled = False
            self.outlineNode.visible = True

            self.movingWorldScene.depthOffsetNode.depthOffset = DepthOffset.PreviewRenderer
            self.sceneHolderNode.addChild(self.movingWorldScene)
            self.loader = WorldLoader(self.movingWorldScene)
            self.loader.timer.start()

    @property
    def schematicBox(self):
        box = self.currentImport.schematic.getDimension().bounds
        return BoundingBox(self.movePosition, box.size)

    # --- Mouse events ---

    def dragMovePoint(self, ray):
        """
        Return a point representing the intersection between the mouse ray
         and an imaginary plane coplanar to the dragged face

        :type ray: Ray
        :rtype: Vector
        """
        dim = self.dragStartFace.dimension
        return ray.intersectPlane(dim, self.dragStartPoint[dim])

    def mouseMove(self, event):
        # Hilite face cursor is over
        if self.currentImport is None:
            return

        point, face = boxFaceUnderCursor(self.schematicBox, event.ray)
        if face is not None:
            self.faceHoverNode.color = (0.3, 1, 1)
            self.faceHoverNode.visible = True

            self.faceHoverNode.face = face
            self.faceHoverNode.selectionBox = self.currentImport.schematic.getDimension().bounds
        else:
            self.faceHoverNode.visible = False

        # Highlight face of box to move along, or else axis pointers to grab and drag?
        pass

    def mouseDrag(self, event):
        # Move box using face or axis pointers
        if self.currentImport is None:
            return
        if self.dragStartFace is None:
            return

        delta = self.dragMovePoint(event.ray) - self.dragStartPoint
        self.movePosition = self.dragStartMovePosition + map(int, delta)

    def mousePress(self, event):
        # Record which face/axis was clicked for mouseDrag. Store current revision # in MoveCommand, begin undo
        # revision, cut selection from world, end undo revision, create overlay node for pasted selection
        # Inform EditorSession that a multi-step undo is being recorded and give it a callback to use when something
        # else tries to call beginUndo before we're done - call it an "undo block"


        # begin drag
        if self.currentImport is not None:
            point, face = boxFaceUnderCursor(self.schematicBox, event.ray)
            self.dragStartFace = face
            self.dragStartPoint = point
            self.dragStartMovePosition = self.movePosition

    def mouseRelease(self, event):
        # Don't paste cut selection in yet. Wait for tool switch or "Confirm" button press. Begin new revision
        # for paste operation, paste stored world, store revision after paste (should be previously stored revision
        # +2), commit MoveCommand to undo history.
        if self.currentImport is not None:
            self.doMoveOffsetCommand(self.dragStartMovePosition, self.movePosition)

    def toolActive(self):
        self.editorSession.selectionTool.hideSelectionWalls = True
        if self.currentImport is None:
            # Need to cut out selection
            # xxxx for huge selections, don't cut, just do everything at the end?
            if self.editorSession.currentSelection is None:
                return
            export = self.editorSession.currentDimension.exportSchematicIter(self.editorSession.currentSelection)
            schematic = showProgress("Copying...", export)
            pos = self.editorSession.currentSelection.origin
            pendingImport = PendingImport(schematic, pos)
            moveCommand = MoveSelectionCommand(self, pendingImport)

            with moveCommand.begin():
                fill = self.editorSession.currentDimension.fillBlocksIter(self.editorSession.currentSelection, "air")
                showProgress("Clearing...", fill)

            self.editorSession.pushCommand(moveCommand)

        self.outlineNode.visible = True

    def toolInactive(self):
        self.editorSession.selectionTool.hideSelectionWalls = False

        self.outlineNode.visible = False
        self.faceHoverNode.visible = False

    def confirmImport(self):
        if self.currentImport is None:
            return

        command = MoveFinishCommand(self, self.currentImport)

        with command.begin():
            task = self.editorSession.currentDimension.importSchematicIter(self.currentImport.schematic, self.currentImport.pos)
            showProgress(self.tr("Pasting..."), task)

        self.editorSession.pushCommand(command)
