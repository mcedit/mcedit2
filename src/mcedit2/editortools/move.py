"""
    move
"""
from __future__ import absolute_import, division, print_function
import logging

from PySide import QtGui, QtCore

from mcedit2.editortools import EditorTool
from mcedit2.command import SimpleRevisionCommand
from mcedit2.editortools.select import SelectionBoxNode, SelectionFaceNode
from mcedit2.rendering import scenegraph
from mcedit2.rendering.depths import DepthOffset
from mcedit2.rendering.worldscene import WorldScene
from mcedit2.util.load_ui import load_ui
from mcedit2.util.showprogress import showProgress
from mcedit2.util.worldloader import WorldLoader
from mcedit2.widgets.layout import Column
from mcedit2.worldview.worldview import boxFaceUnderCursor
from mceditlib.geometry import BoundingBox, Vector

log = logging.getLogger(__name__)

class MoveSelectionCommand(SimpleRevisionCommand):
    def __init__(self, moveTool, movingSchematic, movePosition=None, text=None, *args, **kwargs):
        if text is None:
            text = moveTool.tr("Move Selected Things")
        if movePosition is None:
            movePosition = moveTool.editorSession.currentSelection.origin
        super(MoveSelectionCommand, self).__init__(moveTool.editorSession, text, *args, **kwargs)
        self.moveTool = moveTool
        self.movingSchematic = movingSchematic
        self.movePosition = movePosition

    def undo(self):
        super(MoveSelectionCommand, self).undo()
        self.moveTool.movingSchematic = None
        self.moveTool.movePosition = None
        self.moveTool.editorSession.chooseTool("Select")

    def redo(self):
        self.moveTool.movingSchematic = self.movingSchematic
        self.moveTool.movePosition = self.movePosition
        self.moveTool.editorSession.chooseTool("Move")
        super(MoveSelectionCommand, self).redo()


class MoveOffsetCommand(QtGui.QUndoCommand):

    def __init__(self, moveTool, oldPoint, newPoint):
        super(MoveOffsetCommand, self).__init__()
        self.setText(moveTool.tr("Move Things"))
        self.newPoint = newPoint
        self.oldPoint = oldPoint
        self.moveTool = moveTool

    def undo(self):
        self.moveTool.movePosition = self.oldPoint

    def redo(self):
        self.moveTool.movePosition = self.newPoint

class MoveFinishCommand(SimpleRevisionCommand):
    def __init__(self, moveTool, movingSchematic, *args, **kwargs):
        super(MoveFinishCommand, self).__init__(moveTool.editorSession, moveTool.tr("Finish Moving Things"), *args, **kwargs)
        self.movingSchematic = movingSchematic
        self.moveTool = moveTool

    def undo(self):
        super(MoveFinishCommand, self).undo()
        self.moveTool.movingSchematic = self.movingSchematic
        self.moveTool.movePosition = self.movePosition
        self.editorSession.currentSelection = self.previousSelection
        self.editorSession.chooseTool("Move")

    def redo(self):
        super(MoveFinishCommand, self).redo()
        self.previousSelection = self.editorSession.currentSelection
        self.movePosition = self.moveTool.movePosition
        self.editorSession.currentSelection = BoundingBox(self.movePosition, self.previousSelection.size)
        self.moveTool.movingSchematic = None


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
        confirmButton.clicked.connect(self.completeMove)
        self.toolWidget.setLayout(Column(self.pointInput,
                                         confirmButton,
                                         None))

        self.movePosition = None

    _movePosition = None

    @property
    def movePosition(self):
        return self._movePosition

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
            self.editorSession.removeUndoBlock(self.moveUndoBlock)
            self.editorSession.pushCommand(command)
            self.editorSession.setUndoBlock(self.moveUndoBlock)

    def pointInputChanged(self, value):
        self._movePosition = value
        if value is not None:
            self.translateNode.visible = True
            self.translateNode.translateOffset = value
        else:
            self.translateNode.visible = False

    _movingSchematic = None

    @property
    def movingSchematic(self):
        return self._movingSchematic

    @movingSchematic.setter
    def movingSchematic(self, value):
        oldVal = self._movingSchematic
        self._movingSchematic = value
        if oldVal is not value:
            self.updateOverlay()
        self.pointInput.setEnabled(value is not None)


    def updateOverlay(self):
        if self.movingSchematic is None:
            log.info("updateOverlay: Nothing to display")
            if self.movingWorldScene:
                self.sceneHolderNode.removeChild(self.movingWorldScene)
                self.movingWorldScene = None
            self.outlineNode.visible = False


        log.info("Updating move schematic scene: %s", self.movingSchematic)
        if self.movingWorldScene:
            self.loader.timer.stop()
            self.sceneHolderNode.removeChild(self.movingWorldScene)
        if self.movingSchematic:
            dim = self.movingSchematic.getDimension()
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
        box = self.movingSchematic.getDimension().bounds
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
        if self.movingSchematic is None or self.movePosition is None:
            return

        point, face = boxFaceUnderCursor(self.schematicBox, event.ray)
        if face is not None:
            self.faceHoverNode.color = (0.3, 1, 1)
            self.faceHoverNode.visible = True

            self.faceHoverNode.face = face
            self.faceHoverNode.selectionBox = self.movingSchematic.getDimension().bounds
        else:
            self.faceHoverNode.visible = False

        # Highlight face of box to move along, or else axis pointers to grab and drag?
        pass

    def mouseDrag(self, event):
        # Move box using face or axis pointers
        if self.movingSchematic is None:
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
        if self.movingSchematic is not None:
            point, face = boxFaceUnderCursor(self.schematicBox, event.ray)
            self.dragStartFace = face
            self.dragStartPoint = point
            self.dragStartMovePosition = self.movePosition

    def mouseRelease(self, event):
        # Don't paste cut selection in yet. Wait for tool switch or "Confirm" button press. Begin new revision
        # for paste operation, paste stored world, store revision after paste (should be previously stored revision
        # +2), commit MoveCommand to undo history.
        if self.movingSchematic is not None:
            self.doMoveOffsetCommand(self.dragStartMovePosition, self.movePosition)

    def toolActive(self):
        self.editorSession.selectionTool.hideSelectionWalls = True
        if self.movingSchematic is None:
            # Need to cut out selection
            # xxxx for huge selections, don't cut, just do everything at the end?
            if self.editorSession.currentSelection is None:
                return
            export = self.editorSession.currentDimension.exportSchematicIter(self.editorSession.currentSelection)
            self.movingSchematic = showProgress("Lifting...", export)

            moveCommand = MoveSelectionCommand(self, self.movingSchematic)

            with moveCommand.begin():
                fill = self.editorSession.currentDimension.fillBlocksIter(self.editorSession.currentSelection, "air")
                showProgress("Lifting...", fill)

            self.editorSession.pushCommand(moveCommand)
            self.editorSession.setUndoBlock(self.moveUndoBlock)

    def moveUndoBlock(self):
        self.completeMove()
        self.movingSchematic = None

    def toolInactive(self):
        self.editorSession.selectionTool.hideSelectionWalls = False
        if self.movingSchematic is not None:
            self.completeMove()
            self.movingSchematic = None

        self.outlineNode.visible = False
        self.faceHoverNode.visible = False

    def completeMove(self):
        if self.movingSchematic is None:
            return

        self.editorSession.removeUndoBlock(self.moveUndoBlock)
        command = MoveFinishCommand(self, self.movingSchematic)

        with command.begin():
            task = self.editorSession.currentDimension.importSchematicIter(self.movingSchematic, self.movePosition)
            showProgress(self.tr("Pasting..."), task)

        self.editorSession.pushCommand(command)

    def pasteSchematic(self, copiedSchematic, position):
        command = MoveSelectionCommand(self, copiedSchematic, position, self.tr("Paste"))
        self.editorSession.pushCommand(command)
        self.editorSession.setUndoBlock(self.moveUndoBlock)
