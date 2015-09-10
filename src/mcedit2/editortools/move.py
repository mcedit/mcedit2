"""
    move
"""
from __future__ import absolute_import, division, print_function
import logging

from PySide import QtGui

from PySide.QtCore import Qt
from mcedit2.editorsession import PendingImport
from mcedit2.editortools import EditorTool
from mcedit2.command import SimpleRevisionCommand
from mcedit2.rendering.scenegraph.matrix import TranslateNode
from mcedit2.rendering.selection import SelectionBoxNode, SelectionFaceNode, boxFaceUnderCursor
from mcedit2.rendering.scenegraph import scenenode
from mcedit2.rendering.depths import DepthOffset
from mcedit2.rendering.worldscene import WorldScene
from mcedit2.util.showprogress import showProgress
from mcedit2.util.worldloader import WorldLoader
from mcedit2.widgets.coord_widget import CoordinateWidget
from mcedit2.widgets.layout import Column
from mceditlib.geometry import Vector
from mceditlib.selection import BoundingBox

log = logging.getLogger(__name__)

class MoveSelectionCommand(SimpleRevisionCommand):
    def __init__(self, moveTool, pendingImport, text=None, *args, **kwargs):
        if text is None:
            text = moveTool.tr("Move Selected Object")
        super(MoveSelectionCommand, self).__init__(moveTool.editorSession, text, *args, **kwargs)
        self.pendingImport = pendingImport
        self.moveTool = moveTool

    def undo(self):
        super(MoveSelectionCommand, self).undo()
        self.moveTool.currentImport = None
        self.moveTool.removePendingImport(self.pendingImport)
        self.moveTool.editorSession.chooseTool("Select")

    def redo(self):
        self.moveTool.currentImport = self.pendingImport
        self.moveTool.addPendingImport(self.pendingImport)
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
        self.pendingImport = pendingImport
        self.moveTool = moveTool

    def undo(self):
        super(MoveFinishCommand, self).undo()
        self.moveTool.addPendingImport(self.pendingImport)
        self.editorSession.currentSelection = self.previousSelection
        self.editorSession.chooseTool("Move")

    def redo(self):
        super(MoveFinishCommand, self).redo()
        self.previousSelection = self.editorSession.currentSelection
        self.editorSession.currentSelection = BoundingBox(self.pendingImport.pos, self.pendingImport.bounds.size)
        self.moveTool.removePendingImport(self.pendingImport)


class PendingImportNode(TranslateNode):
    def __init__(self, pendingImport, textureAtlas):
        super(PendingImportNode, self).__init__()
        self.pendingImport = pendingImport
        self.pos = pendingImport.pos

        dim = pendingImport.sourceDim

        self.worldSceneTranslateNode = TranslateNode()
        self.worldScene = WorldScene(dim, textureAtlas, bounds=pendingImport.selection)
        self.worldScene.depthOffsetNode.depthOffset = DepthOffset.PreviewRenderer

        self.worldSceneTranslateNode.translateOffset = -self.pendingImport.selection.origin
        self.worldSceneTranslateNode.addChild(self.worldScene)
        self.addChild(self.worldSceneTranslateNode)

        box = BoundingBox((0, 0, 0), pendingImport.bounds.size)
        self.outlineNode = SelectionBoxNode()
        self.outlineNode.filled = False
        self.outlineNode.selectionBox = box
        self.addChild(self.outlineNode)

        self.faceHoverNode = SelectionFaceNode()
        self.faceHoverNode.selectionBox = box
        self.addChild(self.faceHoverNode)

        self.loader = WorldLoader(self.worldScene,
                                  list(pendingImport.selection.chunkPositions()))
        self.loader.timer.start()

    @property
    def pos(self):
        return self.translateOffset

    @pos.setter
    def pos(self, value):
        self.translateOffset = value

    def hoverFace(self, face):
        if face is not None:
            self.faceHoverNode.color = 0.3, 1, 1
            self.faceHoverNode.visible = True

            self.faceHoverNode.face = face
        else:
            self.faceHoverNode.visible = False

class MoveTool(EditorTool):
    iconName = "move"
    name = "Move"

    def __init__(self, editorSession, *args, **kwargs):
        super(MoveTool, self).__init__(editorSession, *args, **kwargs)
        self.overlayNode = scenenode.Node()

        self.loader = None
        self.dragStartFace = None
        self.dragStartPoint = None

        self.pendingImports = []

        self.pendingImportNodes = {}

        self.toolWidget = QtGui.QWidget()

        self.importsListWidget = QtGui.QListView()
        self.importsListModel = QtGui.QStandardItemModel()
        self.importsListWidget.setModel(self.importsListModel)
        self.importsListWidget.clicked.connect(self.listClicked)
        self.importsListWidget.doubleClicked.connect(self.listDoubleClicked)

        self.pointInput = CoordinateWidget()
        self.pointInput.pointChanged.connect(self.pointInputChanged)
        confirmButton = QtGui.QPushButton("Confirm")  # xxxx should be in worldview
        confirmButton.clicked.connect(self.confirmImport)
        self.toolWidget.setLayout(Column(self.importsListWidget,
                                         self.pointInput,
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

    def pointInputChanged(self, value):
        if value is not None:
            self.currentImport.pos = value
            self.currentImportNode.pos = value

    # --- Pending imports ---

    def addPendingImport(self, pendingImport):
        log.info("Added import: %s", pendingImport)
        self.pendingImports.append(pendingImport)
        item = QtGui.QStandardItem()
        item.setEditable(False)
        item.setText(pendingImport.text)
        item.setData(pendingImport, Qt.UserRole)
        self.importsListModel.appendRow(item)
        self.importsListWidget.setCurrentIndex(self.importsListModel.index(self.importsListModel.rowCount()-1, 0))
        node = self.pendingImportNodes[pendingImport] = PendingImportNode(pendingImport, self.editorSession.textureAtlas)
        self.overlayNode.addChild(node)
        self.currentImport = pendingImport

    def removePendingImport(self, pendingImport):
        index = self.pendingImports.index(pendingImport)
        self.pendingImports.remove(pendingImport)
        self.importsListModel.removeRows(index, 1)
        self.currentImport = self.pendingImports[-1] if len(self.pendingImports) else None
        node = self.pendingImportNodes.pop(pendingImport)
        if node:
            self.overlayNode.removeChild(node)

    def doMoveOffsetCommand(self, oldPoint, newPoint):
        if newPoint != oldPoint:
            command = MoveOffsetCommand(self, oldPoint, newPoint)
            self.editorSession.pushCommand(command)

    def listClicked(self, index):
        item = self.importsListModel.itemFromIndex(index)
        pendingImport = item.data(Qt.UserRole)
        self.currentImport = pendingImport

    def listDoubleClicked(self, index):
        item = self.importsListModel.itemFromIndex(index)
        pendingImport = item.data(Qt.UserRole)
        self.editorSession.editorTab.currentView().centerOnPoint(pendingImport.bounds.center)

    _currentImport = None

    @property
    def currentImport(self):
        return self._currentImport

    @currentImport.setter
    def currentImport(self, value):
        self._currentImport = value
        self.pointInput.setEnabled(value is not None)
        for node in self.pendingImportNodes.itervalues():
            node.outlineNode.wireColor = (.2, 1., .2, .5) if node.pendingImport is value else (1, 1, 1, .3)

    @property
    def currentImportNode(self):
        return self.pendingImportNodes.get(self.currentImport)

    @property
    def schematicBox(self):
        box = self.currentImport.selection
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

        node = self.currentImportNode
        if node:
            point, face = boxFaceUnderCursor(self.schematicBox, event.ray)
            node.hoverFace(face)

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
            if self.editorSession.currentSelection is None:
                return

            # This makes a reference to the latest revision in the editor.
            # If the moved area is changed between "Move" and "Confirm", the changed
            # blocks will be moved.
            pos = self.editorSession.currentSelection.origin
            pendingImport = PendingImport(self.editorSession.currentDimension, pos,
                                          self.editorSession.currentSelection, self.tr("<Moved Object>"),
                                          isMove=True)
            moveCommand = MoveSelectionCommand(self, pendingImport)

            self.editorSession.pushCommand(moveCommand)

    def toolInactive(self):
        self.editorSession.selectionTool.hideSelectionWalls = False

        for node in self.pendingImportNodes.itervalues():
            node.hoverFace(None)

    def confirmImport(self):
        if self.currentImport is None:
            return

        command = MoveFinishCommand(self, self.currentImport)

        with command.begin():
            # TODO don't use intermediate schematic...
            if self.currentImport.isMove:
                export = self.currentImport.sourceDim.exportSchematicIter(self.currentImport.selection)
                schematic = showProgress("Copying...", export)
                dim = schematic.getDimension()
                fill = self.editorSession.currentDimension.fillBlocksIter(self.currentImport.selection, "air")
                showProgress("Clearing...", fill)
            else:
                dim = self.currentImport.sourceDim

            task = self.editorSession.currentDimension.copyBlocksIter(dim, dim.bounds,
                                                                      self.currentImport.pos,
                                                                      biomes=True, create=True)
            showProgress(self.tr("Pasting..."), task)

        self.editorSession.pushCommand(command)
