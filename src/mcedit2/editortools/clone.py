"""
    clone
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from mcedit2.command import SimpleRevisionCommand
from mcedit2.editorsession import PendingImport
from mcedit2.editortools import EditorTool
from mcedit2.imports import PendingImportNode, PendingImport
from mcedit2.rendering.scenegraph import scenenode
from PySide import QtGui
from mcedit2.rendering.selection import boxFaceUnderCursor
from mcedit2.util.showprogress import showProgress
from mcedit2.widgets.coord_widget import CoordinateWidget
from mcedit2.widgets.layout import Column, Row

log = logging.getLogger(__name__)


class CloneSelectionCommand(SimpleRevisionCommand):
    def __init__(self, cloneTool, pendingImport, text=None, *args, **kwargs):
        if text is None:
            text = cloneTool.tr("Clone Selected Object")
        super(CloneSelectionCommand, self).__init__(cloneTool.editorSession, text, *args, **kwargs)
        self.pendingImport = pendingImport
        self.cloneTool = cloneTool

    def undo(self):
        super(CloneSelectionCommand, self).undo()
        self.cloneTool.pendingClone = None
        self.cloneTool.editorSession.chooseTool("Select")

    def redo(self):
        self.cloneTool.pendingClone = self.pendingImport
        self.cloneTool.editorSession.chooseTool("Clone")
        super(CloneSelectionCommand, self).redo()


class CloneOffsetCommand(QtGui.QUndoCommand):
    def __init__(self, cloneTool, oldPoint, newPoint):
        super(CloneOffsetCommand, self).__init__()
        self.setText(cloneTool.tr("Move Cloned Object"))
        self.newPoint = newPoint
        self.oldPoint = oldPoint
        self.cloneTool = cloneTool

    def undo(self):
        self.cloneTool.clonePosition = self.oldPoint

    def redo(self):
        self.cloneTool.clonePosition = self.newPoint


class CloneFinishCommand(SimpleRevisionCommand):
    def __init__(self, cloneTool, pendingImport, *args, **kwargs):
        super(CloneFinishCommand, self).__init__(cloneTool.editorSession, cloneTool.tr("Finish Clone"), *args, **kwargs)
        self.pendingImport = pendingImport
        self.cloneTool = cloneTool

    def undo(self):
        super(CloneFinishCommand, self).undo()
        self.cloneTool.pendingClone = self.pendingImport
        self.editorSession.currentSelection = self.previousSelection
        self.editorSession.chooseTool("Clone")

    def redo(self):
        super(CloneFinishCommand, self).redo()
        self.previousSelection = self.editorSession.currentSelection
        self.editorSession.currentSelection = self.pendingImport.bounds
        self.cloneTool.pendingClone = None
        self.editorSession.chooseTool("Select")


class CloneTool(EditorTool):
    iconName = "clone"
    name = "Clone"

    def __init__(self, editorSession, *args, **kwargs):
        super(CloneTool, self).__init__(editorSession, *args, **kwargs)

        self.originPoint = None
        self.offsetPoint = None

        self.pendingCloneNodes = []
        self.mainCloneNode = None
        self.overlayNode = scenenode.Node()
        self.overlayNode.name = "Clone Overlay"

        self.toolWidget = QtGui.QWidget()
        self.pointInput = CoordinateWidget()
        self.pointInput.pointChanged.connect(self.pointInputChanged)
        confirmButton = QtGui.QPushButton(self.tr("Confirm"))  # xxxx should be in worldview
        confirmButton.clicked.connect(self.confirmClone)

        self.repeatCount = 1
        self.repeatCountInput = QtGui.QSpinBox(minimum=1, maximum=100, value=1)
        self.repeatCountInput.valueChanged.connect(self.setRepeatCount)

        self.tileX = self.tileY = self.tileZ = False

        self.tileXCheckbox = QtGui.QCheckBox(self.tr("Tile X"))
        self.tileXCheckbox.toggled.connect(self.setTileX)

        self.tileYCheckbox = QtGui.QCheckBox(self.tr("Tile Y"))
        self.tileYCheckbox.toggled.connect(self.setTileY)

        self.tileZCheckbox = QtGui.QCheckBox(self.tr("Tile Z"))
        self.tileZCheckbox.toggled.connect(self.setTileZ)

        self.toolWidget.setLayout(Column(self.pointInput,
                                         Row(QtGui.QLabel(self.tr("Repeat count: ")), self.repeatCountInput),
                                         Row(self.tileXCheckbox,
                                             self.tileYCheckbox,
                                             self.tileZCheckbox),
                                         confirmButton,
                                         None))

        self.pendingClone = None  # Do this after creating pointInput to disable inputs

    def pointInputChanged(self, value):
        if self.offsetPoint != value:
            self.offsetPoint = value
            self.pendingClone.pos = value
            self.updateTiling()

    def setTileX(self, value):
        self.tileX = value
        self.updateTiling()

    def setTileY(self, value):
        self.tileY = value
        self.updateTiling()

    def setTileZ(self, value):
        self.tileZ = value
        self.updateTiling()

    def setRepeatCount(self, value):
        self.repeatCount = value
        self.updateTiling()

    def updateTiling(self):
        if self.pendingClone is None:
            repeatCount = 0
        else:
            repeatCount = self.repeatCount

        while len(self.pendingCloneNodes) > repeatCount:
            node = self.pendingCloneNodes.pop()
            self.overlayNode.removeChild(node)
        while len(self.pendingCloneNodes) < repeatCount:
            node = PendingImportNode(self.pendingClone, self.editorSession.textureAtlas)
            self.pendingCloneNodes.append(node)
            self.overlayNode.addChild(node)

        # This is stupid.
        if self.mainCloneNode:
            self.mainCloneNode.importMoved.disconnect(self.cloneDidMove)

        if repeatCount > 0:
            self.mainCloneNode = self.pendingCloneNodes[0]
            self.mainCloneNode.importMoved.connect(self.cloneDidMove)
        else:
            self.mainCloneNode = None

        if None not in (self.offsetPoint, self.originPoint):
            for node, pos in zip(self.pendingCloneNodes, self.getTilingPositions()):
                node.pos = pos

        self.editorSession.updateView()

    def getTilingPositions(self):
        if None not in (self.offsetPoint, self.originPoint):
            pos = self.originPoint
            offset = self.offsetPoint - self.originPoint
            for i in range(self.repeatCount):
                pos = pos + offset
                yield pos

    @property
    def pendingClone(self):
        return self._pendingClone

    @pendingClone.setter
    def pendingClone(self, pendingImport):
        log.info("Begin clone: %s", pendingImport)
        self._pendingClone = pendingImport
        self.pointInput.setEnabled(pendingImport is not None)
        self.updateTiling()

    def toolActive(self):
        self.editorSession.selectionTool.hideSelectionWalls = True
        if self.pendingClone is not None:
            self.pendingClone = None

        if self.editorSession.currentSelection is None:
            return

        # This makes a reference to the latest revision in the editor.
        # If the cloned area is changed between "Clone" and "Confirm", the changed
        # blocks will be moved.
        pos = self.editorSession.currentSelection.origin
        self.originPoint = pos
        self.offsetPoint = pos
        pendingImport = PendingImport(self.editorSession.currentDimension, pos,
                                      self.editorSession.currentSelection,
                                      self.tr("<Cloned Object>"))
        moveCommand = CloneSelectionCommand(self, pendingImport)

        self.editorSession.pushCommand(moveCommand)

    def toolInactive(self):
        self.editorSession.selectionTool.hideSelectionWalls = False
        # if self.mainCloneNode:
        #     self.mainCloneNode.hoverFace(None)

        self.confirmClone()
        
    def confirmClone(self):
        if self.pendingClone is None:
            return

        command = CloneFinishCommand(self, self.pendingClone)

        with command.begin():
            # TODO don't use intermediate schematic...
            export = self.pendingClone.sourceDim.exportSchematicIter(self.pendingClone.selection)
            schematic = showProgress("Copying...", export)
            dim = schematic.getDimension()

            tasks = []
            for pos in self.getTilingPositions():
                task = self.editorSession.currentDimension.copyBlocksIter(dim, dim.bounds, pos,
                                                                          biomes=True, create=True)
                tasks.append(task)

            showProgress(self.tr("Pasting..."), *tasks)

        self.editorSession.pushCommand(command)
        self.originPoint = None

    @property
    def clonePosition(self):
        return None if self.pendingClone is None else self.pendingClone.pos

    @clonePosition.setter
    def clonePosition(self, value):
        """

        :type value: Vector
        """
        self.pointInput.point = value
        self.pointInputChanged(value)

    # --- Mouse events ---

    def mouseMove(self, event):
        if self.mainCloneNode is not None:
            self.mainCloneNode.mouseMove(event)

    def mouseDrag(self, event):
        if self.mainCloneNode is not None:
            self.mainCloneNode.mouseMove(event)

    def mousePress(self, event):
        if self.mainCloneNode is not None:
            self.mainCloneNode.mousePress(event)

    def mouseRelease(self, event):
        if self.mainCloneNode is not None:
            self.mainCloneNode.mouseRelease(event)

    # --- Box handle events ---

    def cloneDidMove(self, newPoint, oldPoint):
        log.info("clone offset command: %s %s", oldPoint, newPoint)
        if newPoint != oldPoint:
            command = CloneOffsetCommand(self, oldPoint, newPoint)
            self.editorSession.pushCommand(command)
