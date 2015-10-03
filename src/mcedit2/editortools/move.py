"""
    move
"""
from __future__ import absolute_import, division, print_function
import logging

from PySide import QtGui, QtCore

from PySide.QtCore import Qt
from mcedit2.editorsession import PendingImport
from mcedit2.editortools import EditorTool
from mcedit2.command import SimpleRevisionCommand
from mcedit2.handles.boxhandle import BoxHandle
from mcedit2.rendering.scenegraph.matrix import TranslateNode, RotateNode
from mcedit2.rendering.scenegraph.scenenode import Node
from mcedit2.rendering.selection import SelectionBoxNode, SelectionFaceNode, boxFaceUnderCursor
from mcedit2.rendering.scenegraph import scenenode
from mcedit2.rendering.depths import DepthOffset
from mcedit2.rendering.worldscene import WorldScene
from mcedit2.util.load_ui import load_ui
from mcedit2.util.showprogress import showProgress
from mcedit2.util.worldloader import WorldLoader
from mcedit2.widgets.coord_widget import CoordinateWidget
from mcedit2.widgets.layout import Column
from mceditlib.export import extractSchematicFromIter
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
        self.editorSession.currentSelection = self.pendingImport.bounds
        self.moveTool.removePendingImport(self.pendingImport)


class Rotate3DNode(Node):
    def __init__(self):
        super(Rotate3DNode, self).__init__()
        self.anchorNode = TranslateNode()
        self.rotXNode = RotateNode(axis=(1, 0, 0))
        self.rotYNode = RotateNode(axis=(0, 1, 0))
        self.rotZNode = RotateNode(axis=(0, 0, 1))
        self.recenterNode = TranslateNode()

        super(Rotate3DNode, self).addChild(self.anchorNode)
        self.anchorNode.addChild(self.rotXNode)
        self.rotXNode.addChild(self.rotYNode)
        self.rotYNode.addChild(self.rotZNode)
        self.rotZNode.addChild(self.recenterNode)

    def addChild(self, node):
        self.recenterNode.addChild(node)

    def removeChild(self, node):
        self.recenterNode.removeChild(node)

    def setRotation(self, rots):
        rx, ry, rz = rots
        self.rotXNode.degrees = rx
        self.rotYNode.degrees = ry
        self.rotZNode.degrees = rz

    def setAnchor(self, point):
        self.anchorNode.translateOffset = point
        self.recenterNode.translateOffset = -point


class PendingImportNode(Node, QtCore.QObject):
    __node_id_counter = 0

    def __init__(self, pendingImport, textureAtlas):
        super(PendingImportNode, self).__init__()
        PendingImportNode.__node_id_counter += 1
        self.id = PendingImportNode.__node_id_counter

        self.textureAtlas = textureAtlas
        self.pendingImport = pendingImport
        dim = pendingImport.sourceDim

        self.positionTranslateNode = TranslateNode()
        self.rotateNode = Rotate3DNode()
        self.addChild(self.positionTranslateNode)
        self.positionTranslateNode.addChild(self.rotateNode)

        self.rotateNode.setAnchor(self.pendingImport.bounds.size * 0.5)

        self.worldSceneTranslateNode = TranslateNode()
        self.worldScene = WorldScene(dim, textureAtlas, bounds=pendingImport.selection)
        self.worldScene.depthOffsetNode.depthOffset = DepthOffset.PreviewRenderer

        self.transformedWorldTranslateNode = TranslateNode()
        self.transformedWorldScene = None
        self.addChild(self.transformedWorldTranslateNode)

        self.worldSceneTranslateNode.translateOffset = -self.pendingImport.selection.origin
        self.worldSceneTranslateNode.addChild(self.worldScene)
        self.rotateNode.addChild(self.worldSceneTranslateNode)

        box = BoundingBox(self.pos, pendingImport.bounds.size)

        self.handleNode = BoxHandle()
        self.handleNode.bounds = box
        self.handleNode.resizable = False
        self.handleNode.boundsChanged.connect(self.handleBoundsChanged)
        self.handleNode.boundsChangedDone.connect(self.handleBoundsChangedDone)

        self.addChild(self.handleNode)

        self.pos = pendingImport.pos

        self.loader = WorldLoader(self.worldScene,
                                  list(pendingImport.selection.chunkPositions()))
        self.loader.timer.start()

    def handleBoundsChanged(self, bounds):
        self.pos = bounds.origin

    # newPos, oldPos
    importMoved = QtCore.Signal(object, object)

    def handleBoundsChangedDone(self, bounds, oldBounds):
        self.importMoved.emit(bounds.origin, oldBounds.origin)

    def setPreviewRotation(self, rots):
        self.rotateNode.visible = True
        self.worldSceneTranslateNode.visible = True
        self.transformedWorldTranslateNode.visible = False
        self.rotateNode.setRotation(rots)

    def setRotation(self, rots):
        self.pendingImport.rotation = rots
        self.updateTransformedScene()

    def updateTransformedScene(self):
        if self.pendingImport.transformedDim is not None:
            self.rotateNode.visible = False
            self.worldSceneTranslateNode.visible = False
            self.transformedWorldTranslateNode.visible = True

            if self.transformedWorldScene:
                self.transformedWorldTranslateNode.removeChild(self.transformedWorldScene)

            self.transformedWorldScene = WorldScene(self.pendingImport.transformedDim,
                                                    self.textureAtlas)
            self.transformedWorldScene.depthOffsetNode.depthOffset = DepthOffset.PreviewRenderer
            self.transformedWorldTranslateNode.addChild(self.transformedWorldScene)
            self.transformedWorldTranslateNode.translateOffset = self.pos - self.pendingImport.rotateAnchor + self.pendingImport.bounds.size * 0.5

            cPos = list(self.pendingImport.transformedDim.chunkPositions())
            self.loader = WorldLoader(self.transformedWorldScene,
                                      cPos)
            self.loader.timer.start()

        else:
            self.rotateNode.visible = True
            self.worldSceneTranslateNode.visible = True
            self.transformedWorldTranslateNode.visible = False
            if self.transformedWorldScene:
                self.transformedWorldTranslateNode.removeChild(self.transformedWorldScene)
                self.transformedWorldScene = None

    @property
    def pos(self):
        return self.positionTranslateNode.translateOffset

    @pos.setter
    def pos(self, value):
        if value == self.positionTranslateNode.translateOffset:
            return

        self.positionTranslateNode.translateOffset = value
        bounds = BoundingBox(value, self.pendingImport.bounds.size)
        self.handleNode.bounds = bounds

class RotationWidget(QtGui.QWidget):
    def __init__(self):
        super(RotationWidget, self).__init__()
        load_ui("rotation_widget.ui", baseinstance=self)

        self.xRotSlider.valueChanged.connect(self.setXRot)
        self.yRotSlider.valueChanged.connect(self.setYRot)
        self.zRotSlider.valueChanged.connect(self.setZRot)

        self.xRotSlider.sliderReleased.connect(self.sliderReleased)
        self.yRotSlider.sliderReleased.connect(self.sliderReleased)
        self.zRotSlider.sliderReleased.connect(self.sliderReleased)

        self.xRotSpinBox.valueChanged.connect(self.setXRot)
        self.yRotSpinBox.valueChanged.connect(self.setYRot)
        self.zRotSpinBox.valueChanged.connect(self.setZRot)

        self.xRot = self.yRot = self.zRot = 0

    rotationChanged = QtCore.Signal(object, bool)

    def emitRotationChanged(self, live):
        self.rotationChanged.emit((self.xRot, self.yRot, self.zRot), live)

    def sliderReleased(self):
        self.emitRotationChanged(False)

    def setXRot(self, value):
        if self.xRot == value:
            return

        self.xRot = value
        self.xRotSlider.setValue(value)
        self.xRotSpinBox.setValue(value)

        self.emitRotationChanged(self.xRotSlider.isSliderDown())

    def setYRot(self, value):
        if self.yRot == value:
            return

        self.yRot = value
        self.yRotSlider.setValue(value)
        self.yRotSpinBox.setValue(value)

        self.emitRotationChanged(self.yRotSlider.isSliderDown())

    def setZRot(self, value):
        if self.zRot == value:
            return

        self.zRot = value
        self.zRotSlider.setValue(value)
        self.zRotSpinBox.setValue(value)

        self.emitRotationChanged(self.zRotSlider.isSliderDown())


class MoveTool(EditorTool):
    iconName = "move"
    name = "Move"

    def __init__(self, editorSession, *args, **kwargs):
        super(MoveTool, self).__init__(editorSession, *args, **kwargs)
        self.overlayNode = scenenode.Node()

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

        self.rotationInput = RotationWidget()
        self.rotationInput.rotationChanged.connect(self.rotationChanged)

        confirmButton = QtGui.QPushButton("Confirm")  # xxxx should be in worldview
        confirmButton.clicked.connect(self.confirmImport)
        self.toolWidget.setLayout(Column(self.importsListWidget,
                                         self.pointInput,
                                         self.rotationInput,
                                         confirmButton,
                                         None))


    def rotationChanged(self, rots, live):
        if self.currentImport:
            if live:
                self.currentImportNode.setPreviewRotation(rots)
            else:
                self.currentImportNode.setRotation(rots)

            self.editorSession.updateView()

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
        node.importMoved.connect(self.importDidMove)

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

    def importDidMove(self, newPoint, oldPoint):
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
        # Set current import to different color?
        # for node in self.pendingImportNodes.itervalues():
        #     node.outlineNode.wireColor = (.2, 1., .2, .5) if node.pendingImport is value else (1, 1, 1, .3)

    @property
    def currentImportNode(self):
        return self.pendingImportNodes.get(self.currentImport)

    # --- Mouse events ---

    def mouseMove(self, event):
        # Hilite face cursor is over
        if self.currentImport is not None:
            self.currentImportNode.handleNode.mouseMove(event)

        # Highlight face of box to move along, or else axis pointers to grab and drag?

    def mouseDrag(self, event):
        self.mouseMove(event)

    def mousePress(self, event):
        if self.currentImport is not None:
            self.currentImportNode.handleNode.mousePress(event)

    def mouseRelease(self, event):
        if self.currentImport is not None:
            self.currentImportNode.handleNode.mouseRelease(event)

    # --- Editor events ---

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
                                          self.editorSession.currentSelection,
                                          self.tr("<Moved Object>"),
                                          isMove=True)
            moveCommand = MoveSelectionCommand(self, pendingImport)

            self.editorSession.pushCommand(moveCommand)

    def toolInactive(self):
        self.editorSession.selectionTool.hideSelectionWalls = False
        # hide hovers for box handles?

    def confirmImport(self):
        if self.currentImport is None:
            return

        command = MoveFinishCommand(self, self.currentImport)
        destDim = self.editorSession.currentDimension
        with command.begin():
            if self.currentImport.isMove:
                sourceDim = self.currentImport.importDim
                destBox = BoundingBox(self.currentImport.importPos, sourceDim.bounds.size)

                # Use intermediate schematic only if source and destination overlap.
                if sourceDim.bounds.intersect(destBox).volume:
                    export = extractSchematicFromIter(sourceDim, self.currentImport.selection)
                    schematic = showProgress(self.tr("Copying..."), export)
                    sourceDim = schematic.getDimension()

            else:
                # Use source as-is
                sourceDim = self.currentImport.importDim

            # Copy to destination
            task = destDim.copyBlocksIter(sourceDim, sourceDim.bounds,
                                          self.currentImport.importPos,
                                          biomes=True, create=True)

            showProgress(self.tr("Pasting..."), task)

            # Clear source
            if self.currentImport.isMove:
                fill = destDim.fillBlocksIter(self.currentImport.selection, "air")
                showProgress(self.tr("Clearing..."), fill)

        self.editorSession.pushCommand(command)
