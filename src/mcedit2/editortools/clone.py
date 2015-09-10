"""
    clone
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from mcedit2.command import SimpleRevisionCommand
from mcedit2.editorsession import PendingImport
from mcedit2.editortools import EditorTool
from mcedit2.editortools.move import PendingImportNode
from mcedit2.rendering.scenegraph import scenenode
from PySide import QtGui
from mcedit2.rendering.selection import boxFaceUnderCursor
from mcedit2.util.showprogress import showProgress
from mcedit2.widgets.coord_widget import CoordinateWidget
from mcedit2.widgets.layout import Column
from mceditlib.selection import BoundingBox

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
        self.cloneTool.currentClone = None
        self.cloneTool.editorSession.chooseTool("Select")

    def redo(self):
        self.cloneTool.currentClone = self.pendingImport
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
        self.cloneTool.currentClone = self.pendingImport
        self.editorSession.currentSelection = self.previousSelection
        self.editorSession.chooseTool("Clone")

    def redo(self):
        super(CloneFinishCommand, self).redo()
        self.previousSelection = self.editorSession.currentSelection
        self.editorSession.currentSelection = self.pendingImport.bounds
        self.cloneTool.currentClone = None
        
class CloneTool(EditorTool):
    iconName = "clone"
    name = "Clone"

    def __init__(self, editorSession, *args, **kwargs):
        super(CloneTool, self).__init__(editorSession, *args, **kwargs)

        self.dragStartFace = None
        self.dragStartPoint = None
        self.dragStartClonePosition = None

        self.pendingCloneNode = None
        self.overlayNode = scenenode.Node()
        self.overlayNode.name = "Clone Overlay"

        self.toolWidget = QtGui.QWidget()
        self.pointInput = CoordinateWidget()
        self.pointInput.pointChanged.connect(self.pointInputChanged)
        confirmButton = QtGui.QPushButton("Confirm")  # xxxx should be in worldview
        confirmButton.clicked.connect(self.confirmClone)
        self.toolWidget.setLayout(Column(self.pointInput,
                                         confirmButton,
                                         None))

        self.currentClone = None  # Do this after creating pointInput to disable inputs

    def pointInputChanged(self, value):
        if value is not None:
            self.currentClone.pos = value
            self.pendingCloneNode.pos = value

    @property
    def currentClone(self):
        return self._currentClone

    @currentClone.setter
    def currentClone(self, pendingImport):
        log.info("Begin clone: %s", pendingImport)
        self._currentClone = pendingImport
        self.pointInput.setEnabled(pendingImport is not None)
        if pendingImport is not None:
            node = self.pendingCloneNode = PendingImportNode(pendingImport, self.editorSession.textureAtlas)
            self.overlayNode.addChild(node)
        else:
            if self.pendingCloneNode:
                self.overlayNode.removeChild(self.pendingCloneNode)
                self.pendingCloneNode = None

    def toolActive(self):
        self.editorSession.selectionTool.hideSelectionWalls = True
        if self.currentClone is None:
            if self.editorSession.currentSelection is None:
                return

            # This makes a reference to the latest revision in the editor.
            # If the cloned area is changed between "Clone" and "Confirm", the changed
            # blocks will be moved.
            pos = self.editorSession.currentSelection.origin
            pendingImport = PendingImport(self.editorSession.currentDimension, pos,
                                          self.editorSession.currentSelection, 
                                          self.tr("<Cloned Object>"))
            moveCommand = CloneSelectionCommand(self, pendingImport)

            self.editorSession.pushCommand(moveCommand)

    def toolInactive(self):
        self.editorSession.selectionTool.hideSelectionWalls = False

        self.pendingCloneNode.hoverFace(None)
            
        self.confirmClone()
        
    def confirmClone(self):
        if self.currentClone is None:
            return

        command = CloneFinishCommand(self, self.currentClone)

        with command.begin():
            # TODO don't use intermediate schematic...
            export = self.currentClone.sourceDim.exportSchematicIter(self.currentClone.selection)
            schematic = showProgress("Copying...", export)
            dim = schematic.getDimension()

            task = self.editorSession.currentDimension.copyBlocksIter(dim, dim.bounds,
                                                                      self.currentClone.pos,
                                                                      biomes=True, create=True)
            showProgress(self.tr("Pasting..."), task)

        self.editorSession.pushCommand(command)
        

    @property
    def clonePosition(self):
        return None if self.currentClone is None else self.currentClone.pos

    @clonePosition.setter
    def clonePosition(self, value):
        """

        :type value: Vector
        """
        self.pointInput.point = value
        self.pointInputChanged(value)

    # --- Mouse events ---

    def dragClonePoint(self, ray):
        """
        Return a point representing the intersection between the mouse ray
         and an imaginary plane coplanar to the dragged face

        :type ray: Ray
        :rtype: Vector
        """
        dim = self.dragStartFace.dimension
        return ray.intersectPlane(dim, self.dragStartPoint[dim])

    @property
    def schematicBox(self):
        box = self.currentClone.selection
        return BoundingBox(self.clonePosition, box.size)

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
        if self.currentClone is None:
            return

        node = self.pendingCloneNode
        if node:
            point, face = boxFaceUnderCursor(self.schematicBox, event.ray)
            node.hoverFace(face)

        # Highlight face of box to move along, or else axis pointers to grab and drag?
        pass

    def mouseDrag(self, event):
        # Clone box using face or axis pointers
        if self.currentClone is None:
            return
        if self.dragStartFace is None:
            return

        delta = self.dragClonePoint(event.ray) - self.dragStartPoint
        self.clonePosition = self.dragStartClonePosition + map(int, delta)

    def mousePress(self, event):
        if self.currentClone is not None:
            point, face = boxFaceUnderCursor(self.schematicBox, event.ray)
            self.dragStartFace = face
            self.dragStartPoint = point
            self.dragStartClonePosition = self.clonePosition

    def mouseRelease(self, event):
        if self.currentClone is not None:
            self.doCloneOffsetCommand(self.dragStartClonePosition, self.clonePosition)

    def doCloneOffsetCommand(self, oldPoint, newPoint):
        if newPoint != oldPoint:
            command = CloneOffsetCommand(self, oldPoint, newPoint)
            self.editorSession.pushCommand(command)
