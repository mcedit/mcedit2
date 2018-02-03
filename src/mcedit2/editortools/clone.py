"""
    clone
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

import numpy

from mcedit2.command import SimpleRevisionCommand
from mcedit2.editortools import EditorTool
from mcedit2.imports import PendingImportNode, PendingImport
from mcedit2.rendering.scenegraph import scenenode
from PySide import QtGui
from mcedit2.util.showprogress import showProgress
from mcedit2.widgets.coord_widget import CoordinateWidget
from mcedit2.widgets.layout import Column, Row
from mcedit2.widgets.rotation_widget import RotationWidget
from mcedit2.widgets.scale_widget import ScaleWidget
from mceditlib import transform

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
        self.cloneTool.mainPendingClone = None
        self.cloneTool.editorSession.chooseTool("Select")

    def redo(self):
        self.cloneTool.mainPendingClone = self.pendingImport
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


class CloneRotateCommand(QtGui.QUndoCommand):
    def __init__(self, oldRotation, newRotation, cloneTool):
        super(CloneRotateCommand, self).__init__()
        self.cloneTool = cloneTool
        self.setText(QtGui.qApp.tr("Rotate Cloned Objects"))
        self.newRotation = newRotation
        self.oldRotation = oldRotation

    def undo(self):
        self.cloneTool.setRotation(self.oldRotation)

    def redo(self):
        self.cloneTool.setRotation(self.newRotation)


class CloneScaleCommand(QtGui.QUndoCommand):
    def __init__(self, oldScale, newScale, cloneTool):
        super(CloneScaleCommand, self).__init__()
        self.cloneTool = cloneTool
        self.setText(QtGui.qApp.tr("Scale Cloned Objects"))
        self.newScale = newScale
        self.oldScale = oldScale

    def undo(self):
        self.cloneTool.setScale(self.oldScale)

    def redo(self):
        self.cloneTool.setScale(self.newScale)


class CloneFinishCommand(SimpleRevisionCommand):
    def __init__(self, cloneTool, pendingImport, originPoint, *args, **kwargs):
        super(CloneFinishCommand, self).__init__(cloneTool.editorSession, cloneTool.tr("Finish Clone"), *args, **kwargs)
        self.pendingImport = pendingImport
        self.cloneTool = cloneTool
        self.originPoint = originPoint
        self.previousSelection = None

    def undo(self):
        super(CloneFinishCommand, self).undo()
        self.cloneTool.mainPendingClone = self.pendingImport
        self.cloneTool.originPoint = self.originPoint
        self.editorSession.currentSelection = self.previousSelection
        self.editorSession.chooseTool("Clone")

    def redo(self):
        super(CloneFinishCommand, self).redo()
        self.previousSelection = self.editorSession.currentSelection
        self.editorSession.currentSelection = self.pendingImport.bounds
        self.cloneTool.mainPendingClone = None
        self.cloneTool.originPoint = None
        self.editorSession.chooseTool("Select")


class CloneTool(EditorTool):
    """
    Make multiple copies of the selected area. When selected, displays a preview of the
     copies and allows the position, repeat count, and transforms to be changed.


    Attributes
    ----------
    mainPendingClone : PendingImport
        The object currently being cloned.

    pendingClones : list of PendingImport
        Repeated imports of the object being cloned

    """
    iconName = "clone"
    name = "Clone"
    modifiesWorld = True

    def __init__(self, editorSession, *args, **kwargs):
        super(CloneTool, self).__init__(editorSession, *args, **kwargs)

        self.originPoint = None

        self.pendingClones = []
        self.pendingCloneNodes = []
        self.mainCloneNode = None

        self.overlayNode = scenenode.Node("cloneOverlay")

        self.toolWidget = QtGui.QWidget()
        self.pointInput = CoordinateWidget()
        self.pointInput.pointChanged.connect(self.pointInputChanged)

        self.rotationInput = RotationWidget()
        self.rotationInput.rotationChanged.connect(self.rotationChanged)

        self.scaleInput = ScaleWidget()
        self.scaleInput.scaleChanged.connect(self.scaleChanged)
        
        confirmButton = QtGui.QPushButton(self.tr("Confirm"))  # xxxx should be in worldview
        confirmButton.clicked.connect(self.confirmClone)

        self.repeatCount = 1
        self.repeatCountInput = QtGui.QSpinBox(minimum=1, maximum=10000, value=1)
        self.repeatCountInput.valueChanged.connect(self.setRepeatCount)

        self.rotateRepeatsCheckbox = QtGui.QCheckBox(self.tr("Rotate Repeats"))
        self.rotateRepeatsCheckbox.toggled.connect(self.updateTiling)

        self.rotateOffsetCheckbox = QtGui.QCheckBox(self.tr("Rotate Offset"))
        self.rotateOffsetCheckbox.toggled.connect(self.updateTiling)

        self.toolWidget.setLayout(Column(self.pointInput,
                                         self.rotationInput,
                                         Row(self.rotateRepeatsCheckbox,
                                             self.rotateOffsetCheckbox),
                                         self.scaleInput,
                                         Row(QtGui.QLabel(self.tr("Repeat count: ")), self.repeatCountInput),
                                         confirmButton,
                                         None))

        self.mainPendingClone = None  # Do this after creating pointInput to disable inputs

    def pointInputChanged(self, value):
        if self.mainPendingClone.basePosition != value:
            self.mainPendingClone.basePosition = value
            self.updateTiling()

    def rotationChanged(self, rots, live):
        scale = self.scaleInput.scale
        if live:
            for node, (nodePos, nodeRots, nodeScale) in zip(self.pendingCloneNodes, self.getTilingPositions(None, rots, scale)):
                node.setPreviewRotation(nodeRots)
                node.setPreviewScale(nodeScale)
                node.setPreviewBasePosition(nodePos + node.pendingImport.transformOffset)
            self.editorSession.updateView()
        else:
            if self.mainPendingClone and self.mainPendingClone.rotation != rots:
                command = CloneRotateCommand(self.mainPendingClone.rotation, rots, self)
                self.editorSession.pushCommand(command)
                self.updateTiling()

    def scaleChanged(self, scale, live):
        rots = self.rotationInput.rotation
        if live:
            for node, (nodePos, nodeRots, nodeScale) in zip(self.pendingCloneNodes, self.getTilingPositions(None, rots, scale)):
                node.setPreviewRotation(nodeRots)
                node.setPreviewScale(nodeScale)
                node.setPreviewBasePosition(nodePos + node.pendingImport.transformOffset)
            self.editorSession.updateView()
        else:
            if self.mainPendingClone and self.mainPendingClone.scale != scale:
                command = CloneScaleCommand(self.mainPendingClone.scale, scale, self)
                self.editorSession.pushCommand(command)
                self.updateTiling()

    def setRepeatCount(self, value):
        self.repeatCount = value
        self.updateTiling()

    def setRotation(self, rots):
        if self.mainPendingClone is None:
            return
        else:
            self.mainPendingClone.rotation = rots
            self.updateTiling()

    def setScale(self, scale):
        if self.mainPendingClone is None:
            return
        else:
            self.mainPendingClone.scale = scale
            self.updateTiling()

    def updateTiling(self):
        if self.mainPendingClone is None:
            repeatCount = 0
        else:
            repeatCount = self.repeatCount

        while len(self.pendingClones) > repeatCount:
            node = self.pendingCloneNodes.pop()
            self.overlayNode.removeChild(node)
            self.pendingClones.pop()

        while len(self.pendingClones) < repeatCount:
            clone = PendingImport(self.mainPendingClone.sourceDim,
                                  self.mainPendingClone.basePosition,
                                  self.mainPendingClone.selection,
                                  self.mainPendingClone.text + " %d" % len(self.pendingClones))
            node = PendingImportNode(clone,
                                     self.editorSession.textureAtlas,
                                     hasHandle=len(self.pendingClones) == 0)

            self.pendingClones.append(clone)
            self.pendingCloneNodes.append(node)
            self.overlayNode.addChild(node)

        # This is stupid.
        if self.mainCloneNode:
            self.mainCloneNode.importMoved.disconnect(self.cloneDidMove)
            self.mainCloneNode.importIsMoving.disconnect(self.cloneIsMoving)

        if repeatCount > 0:
            self.mainCloneNode = self.pendingCloneNodes[0]
            self.mainCloneNode.importMoved.connect(self.cloneDidMove)
            self.mainCloneNode.importIsMoving.connect(self.cloneIsMoving)
        else:
            self.mainCloneNode = None

        self.updateTilingPositions()

    def updateTilingPositions(self, offsetPoint=None):
        if self.originPoint is not None:
            for clone, (pos, rots, scale) in zip(self.pendingClones, self.getTilingPositions(offsetPoint)):
                clone.basePosition = pos
                clone.rotation = rots
                clone.scale = scale

        self.editorSession.updateView()

    def getTilingPositions(self, offsetPoint=None, rotations=None, scale=None):
        rotateRepeats = self.rotateRepeatsCheckbox.isChecked()
        rotateOffsets = self.rotateOffsetCheckbox.isChecked()
        baseRotations = rotations or self.mainPendingClone.rotation
        rotations = baseRotations
        scale = scale or self.mainPendingClone.scale

        matrix = transform.transformationMatrix((0, 0, 0), rotations, scale)
        matrix = numpy.linalg.inv(matrix)[:3, :3]
    
        # TODO: Use scales here
        if offsetPoint is None:
            offsetPoint = self.mainPendingClone.basePosition
        if None not in (offsetPoint, self.originPoint):
            pos = self.originPoint
            offset = offsetPoint - self.originPoint
            for i in range(self.repeatCount):
                pos = pos + offset
                yield pos.intfloor(), rotations, scale
                if rotateRepeats:
                    rotations = [a+b for a,b in zip(rotations, baseRotations)]
                if rotateOffsets:
                    # Convert to 4-element column and back
                    offset = (offset * matrix).T
                    offset = tuple(float(x) for x in offset)

    @property
    def mainPendingClone(self):
        return self._pendingClone

    @mainPendingClone.setter
    def mainPendingClone(self, pendingImport):
        log.info("Begin clone: %s", pendingImport)
        self._pendingClone = pendingImport
        self.pointInput.setEnabled(pendingImport is not None)
        if pendingImport:
            self.pointInput.point = pendingImport.basePosition
        self.updateTiling()

    def toolActive(self):
        self.editorSession.selectionTool.hideSelectionWalls = True
        if self.mainPendingClone is None:
            if self.editorSession.currentSelection is None:
                return

            # This makes a reference to the latest revision in the editor.
            # If the cloned area is changed between "Clone" and "Confirm", the changed
            # blocks will be cloned.
            pos = self.editorSession.currentSelection.origin
            self.pointInput.origin = self.originPoint = pos
            pendingImport = PendingImport(self.editorSession.currentDimension, pos,
                                          self.editorSession.currentSelection,
                                          self.tr("<Cloned Object>"))
            moveCommand = CloneSelectionCommand(self, pendingImport)

            self.editorSession.pushCommand(moveCommand)

        self.updateTiling()

    def toolInactive(self):
        self.editorSession.selectionTool.hideSelectionWalls = False
        # if self.mainCloneNode:
        #     self.mainCloneNode.hoverFace(None)

        self.confirmClone()
        
    def confirmClone(self):
        if self.mainPendingClone is None:
            return

        command = CloneFinishCommand(self, self.mainPendingClone, self.originPoint)

        with command.begin():
            tasks = []
            for clone in self.pendingClones:
                # TODO don't use intermediate schematic...
                destDim = self.editorSession.currentDimension
                dim, selection = clone.getSourceForDim(destDim)

                task = destDim.copyBlocksIter(dim, selection, clone.importPos,
                                              biomes=True, create=True, copyAir=False)
                tasks.append(task)

            showProgress(self.tr("Pasting..."), *tasks)

        self.editorSession.pushCommand(command)

    @property
    def clonePosition(self):
        return None if self.mainPendingClone is None else self.mainPendingClone.basePosition

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

    def cloneIsMoving(self, newPoint):
        self.updateTilingPositions(newPoint)
