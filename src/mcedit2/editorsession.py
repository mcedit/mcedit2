from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import os

from PySide import QtGui, QtCore
from PySide.QtCore import Qt

from mcedit2 import editortools
from mcedit2.command import SimpleRevisionCommand
from mcedit2.rendering.blockmodels import BlockModels
from mcedit2.editorcommands.fill import fillCommand
from mcedit2.editorcommands.find_replace import FindReplaceDialog
from mcedit2.editortools.select import SelectCommand
from mcedit2.panels.player import PlayerPanel
from mcedit2.util.dialogs import NotImplementedYet
from mcedit2.util.lazyprop import weakrefprop
from mcedit2.util.raycast import rayCastInBounds
from mcedit2.util.resources import resourcePath
from mcedit2.util.showprogress import showProgress
from mcedit2.util.undostack import MCEUndoStack
from mcedit2.widgets.inspector import InspectorWidget
from mcedit2.worldview.viewaction import UseToolMouseAction, TrackingMouseAction
from mceditlib import util
from mcedit2.rendering import chunkloader, scenegraph
from mcedit2.rendering.geometrycache import GeometryCache
from mcedit2.rendering.textureatlas import TextureAtlas
from mcedit2.widgets.layout import Column, Row
from mcedit2.util.settings import Settings
from mcedit2.worldview.camera import CameraWorldViewFrame
from mcedit2.worldview.cutaway import CutawayWorldViewFrame
from mcedit2.worldview.minimap import MinimapWorldView
from mcedit2.worldview.overhead import OverheadWorldViewFrame
from mceditlib.geometry import Vector
from mceditlib.operations import ComposeOperations
from mceditlib.operations.entity import RemoveEntitiesOperation
from mceditlib.selection import BoundingBox
from mceditlib.exceptions import PlayerNotFound
from mceditlib.revisionhistory import UndoFolderExists
from mceditlib.worldeditor import WorldEditor


log = logging.getLogger(__name__)
"""
An EditorSession is a world currently opened for editing, the state of the editor including the current
selection box, the editor tab containing its viewports, its command history, a separate instance of each editor
tool (why?), and the ChunkLoader that coordinates loading chunks into its viewports.
"""

class PendingImport(object):
    def __init__(self, schematic, pos, text):
        self.text = text
        self.pos = pos
        self.schematic = schematic

    def __repr__(self):
        return "%s(%r, %r)" % (self.__class__.__name__, self.schematic, self.pos)

    @property
    def bounds(self):
        return BoundingBox(self.pos, self.schematic.getDimension().bounds.size)

class PasteImportCommand(QtGui.QUndoCommand):
    def __init__(self, editorSession, pendingImport, text, *args, **kwargs):
        super(PasteImportCommand, self).__init__(*args, **kwargs)
        self.setText(text)
        self.editorSession = editorSession
        self.pendingImport = pendingImport

    def undo(self):
        self.editorSession.moveTool.removePendingImport(self.pendingImport)

    def redo(self):
        self.editorSession.moveTool.addPendingImport(self.pendingImport)
        self.editorSession.chooseTool("Move")

class EditorSession(QtCore.QObject):
    def __init__(self, filename, versionInfo, readonly=False):
        QtCore.QObject.__init__(self)
        self.undoStack = MCEUndoStack()

        self.filename = filename
        self.dockWidgets = []
        self.undoBlock = None
        self.currentTool = None
        self.dirty = False

        self.copiedSchematic = None
        """:type : WorldEditor"""

        self.versionInfo = versionInfo

        # --- Open world editor ---
        try:
            self.worldEditor = WorldEditor(filename, readonly=readonly)
        except UndoFolderExists:
            msgBox = QtGui.QMessageBox()
            msgBox.setIcon(QtGui.QMessageBox.Warning)
            msgBox.setWindowTitle(self.tr("MCEdit tech demo"))
            msgBox.setText(self.tr("This world was not properly closed by MCEdit."))
            msgBox.setInformativeText(self.tr(
                "MCEdit may have crashed. An undo history was found for this world. You may try to resume editing "
                "with the saved undo history, or start over with the current state of the world."))
            resumeBtn = msgBox.addButton("Resume Editing", QtGui.QMessageBox.ApplyRole)
            msgBox.addButton("Discard History", QtGui.QMessageBox.DestructiveRole)
            # msgBox.exec_()
            # clicked = msgBox.clickedButton()
            clicked = None  # xxxxx
            resume = clicked is resumeBtn
            try:
                self.worldEditor = WorldEditor(filename, readonly=readonly, resume=resume)
            except NotImplementedError:
                NotImplementedYet()
                raise IOError("Uh-oh")

        self.worldEditor.requireRevisions()
        self.currentDimension = self.worldEditor.getDimension()
        self.loader = chunkloader.ChunkLoader(self.currentDimension)

        self.loader.chunkCompleted.connect(self.chunkDidComplete)
        self.loader.allChunksDone.connect(self.updateView)

        # --- Menus ---

        self.menus = []

        self.menuEdit = QtGui.QMenu(self.tr("Edit"))
        self.menuEdit.setObjectName("menuEdit")

        self.actionCut = QtGui.QAction(self.tr("Cut"), self, triggered=self.cut, enabled=False)
        self.actionCut.setShortcut(QtGui.QKeySequence.Cut)
        self.actionCut.setObjectName("actionCut")

        self.actionCopy = QtGui.QAction(self.tr("Copy"), self, triggered=self.copy, enabled=False)
        self.actionCopy.setShortcut(QtGui.QKeySequence.Copy)
        self.actionCopy.setObjectName("actionCopy")

        self.actionPaste = QtGui.QAction(self.tr("Paste"), self, triggered=self.paste, enabled=False)
        self.actionPaste.setShortcut(QtGui.QKeySequence.Paste)
        self.actionPaste.setObjectName("actionPaste")

        self.actionPaste_Blocks = QtGui.QAction(self.tr("Paste Blocks"), self, triggered=self.pasteBlocks, enabled=False)
        self.actionPaste_Blocks.setShortcut(QtGui.QKeySequence("Ctrl+Shift+V"))
        self.actionPaste_Blocks.setObjectName("actionPaste_Blocks")

        self.actionPaste_Entities = QtGui.QAction(self.tr("Paste Entities"), self, triggered=self.pasteEntities, enabled=False)
        self.actionPaste_Entities.setShortcut(QtGui.QKeySequence("Ctrl+Alt+V"))
        self.actionPaste_Entities.setObjectName("actionPaste_Entities")

        self.actionClear = QtGui.QAction(self.tr("Delete"), self, triggered=self.deleteSelection, enabled=False)
        self.actionClear.setShortcut(QtGui.QKeySequence.Delete)
        self.actionClear.setObjectName("actionClear")

        self.actionDeleteBlocks = QtGui.QAction(self.tr("Delete Blocks"), self, triggered=self.deleteBlocks, enabled=False)
        self.actionDeleteBlocks.setShortcut(QtGui.QKeySequence("Shift+Del"))
        self.actionDeleteBlocks.setObjectName("actionDeleteBlocks")

        self.actionDeleteEntities = QtGui.QAction(self.tr("Delete Entities"), self, triggered=self.deleteEntities, enabled=False)
        self.actionDeleteEntities.setShortcut(QtGui.QKeySequence("Shift+Alt+Del"))
        self.actionDeleteEntities.setObjectName("actionDeleteEntities")

        self.actionFill = QtGui.QAction(self.tr("Fill"), self, triggered=self.fill, enabled=False)
        self.actionFill.setShortcut(QtGui.QKeySequence("Shift+Ctrl+F"))
        self.actionFill.setObjectName("actionFill")

        self.actionFindReplace = QtGui.QAction(self.tr("Find/Replace"), self, triggered=self.findReplace, enabled=True)
        self.actionFindReplace.setShortcut(QtGui.QKeySequence.Find)
        self.actionFindReplace.setObjectName("actionFindReplace")

        undoAction = self.undoStack.createUndoAction(self.menuEdit)
        undoAction.setShortcut(QtGui.QKeySequence.Undo)
        redoAction = self.undoStack.createRedoAction(self.menuEdit)
        redoAction.setShortcut(QtGui.QKeySequence.Redo)

        self.menuEdit.addAction(undoAction)
        self.menuEdit.addAction(redoAction)
        self.menuEdit.addSeparator()
        self.menuEdit.addAction(self.actionCut)
        self.menuEdit.addAction(self.actionCopy)
        self.menuEdit.addAction(self.actionPaste)
        self.menuEdit.addAction(self.actionPaste_Blocks)
        self.menuEdit.addAction(self.actionPaste_Entities)
        self.menuEdit.addSeparator()
        self.menuEdit.addAction(self.actionClear)
        self.menuEdit.addAction(self.actionDeleteBlocks)
        self.menuEdit.addAction(self.actionDeleteEntities)
        self.menuEdit.addSeparator()
        self.menuEdit.addAction(self.actionFill)
        self.menuEdit.addSeparator()
        self.menuEdit.addAction(self.actionFindReplace)

        self.menus.append(self.menuEdit)

        self.menuSelect = QtGui.QMenu(self.tr("Select"))

        self.actionSelectAll = QtGui.QAction(self.tr("Select All"), self, triggered=self.selectAll)
        self.actionSelectAll.setShortcut(QtGui.QKeySequence.SelectAll)
        self.menuSelect.addAction(self.actionSelectAll)

        self.actionDeselect = QtGui.QAction(self.tr("Deselect"), self, triggered=self.deselect)
        self.actionDeselect.setShortcut(QtGui.QKeySequence("Ctrl+D"))
        self.menuSelect.addAction(self.actionDeselect)

        self.menus.append(self.menuSelect)

        # --- Resources ---

        i, v, p = self.versionInfo
        self.resourceLoader = i.getResourceLoader(v, p)
        self.geometryCache = GeometryCache()
        self.blockModels = BlockModels(self.worldEditor.blocktypes, self.resourceLoader)
        self.textureAtlas = TextureAtlas(self.worldEditor, self.resourceLoader, self.blockModels)

        self.editorOverlay = scenegraph.Node()

        # --- Panels ---

        self.playerPanel = PlayerPanel(self)
        self.panels = [self.playerPanel]

        # --- Tools ---

        self.toolClasses = list(editortools.ToolClasses())
        self.toolActionGroup = QtGui.QActionGroup(self)
        self.tools = [cls(self) for cls in self.toolClasses]
        self.toolActions = [tool.pickToolAction() for tool in self.tools]
        self.actionsByName = {action.toolName: action for action in self.toolActions}
        for tool in self.tools:
            tool.toolPicked.connect(self.chooseTool)
        for action in self.toolActions:
            self.toolActionGroup.addAction(action)

        self.selectionTool = self.getTool("Select")
        self.moveTool = self.getTool("Move")

        # --- Editor stuff ---
        self.editorTab = EditorTab(self)
        self.toolChanged.connect(self.toolDidChange)

        self.undoStack.indexChanged.connect(self.undoIndexChanged)

        self.findReplaceDialog = FindReplaceDialog(self)
        for resultsWidget in self.findReplaceDialog.resultsWidgets:
            self.dockWidgets.append((Qt.BottomDockWidgetArea, resultsWidget))

        self.inspectorWidget = InspectorWidget(self)
        self.inspectorDockWidget = QtGui.QDockWidget(self.tr("Inspector"), objectName="inspector")
        self.inspectorDockWidget.setWidget(self.inspectorWidget)
        self.inspectorDockWidget.hide()
        self.dockWidgets.append((Qt.RightDockWidgetArea, self.inspectorDockWidget))


        if len(self.toolActions):
            self.toolActions[0].trigger()  # Must be called after toolChanged is connected to editorTab

    def dispose(self):
        if self.textureAtlas:
            self.textureAtlas.dispose()
            self.textureAtlas = None
        if self.editorTab:
            self.editorTab.destroy()
            self.editorTab = None
        if self.worldEditor:
            self.worldEditor.close()
            self.worldEditor = None
    # Connecting these signals to the EditorTab creates a circular reference through
    # the Qt objects, preventing the EditorSession from being destroyed

    def focusWorldView(self):
        self.editorTab.currentView().setFocus()

    def updateView(self):
        self.editorTab.currentView().update()

    def toolDidChange(self, tool):
        self.editorTab.toolDidChange(tool)

    # --- Selection ---

    selectionChanged = QtCore.Signal(BoundingBox)
    _currentSelection = None

    @property
    def currentSelection(self):
        return self._currentSelection

    @currentSelection.setter
    def currentSelection(self, box):
        self._currentSelection = box
        self.enableSelectionCommands(box is not None and box.volume != 0)
        self.selectionChanged.emit(box)

    def enableSelectionCommands(self, enable):
        self.actionCut.setEnabled(enable)
        self.actionCopy.setEnabled(enable)
        self.actionPaste.setEnabled(enable)
        self.actionPaste_Blocks.setEnabled(enable)
        self.actionPaste_Entities.setEnabled(enable)
        self.actionClear.setEnabled(enable)
        self.actionDeleteBlocks.setEnabled(enable)
        self.actionDeleteEntities.setEnabled(enable)
        self.actionFill.setEnabled(enable)

    # --- Menu commands ---

    # - World -

    def save(self):
        self.undoStack.clearUndoBlock()
        self.worldEditor.saveChanges()
        self.dirty = False

    # - Edit -

    def cut(self):
        command = SimpleRevisionCommand(self, "Cut")
        with command.begin():
            task = self.currentDimension.exportSchematicIter(self.currentSelection)
            self.copiedSchematic = showProgress("Cutting...", task)
            task = self.currentDimension.fillBlocksIter(self.currentSelection, "air")
            showProgress("Cutting...", task)
        self.undoStack.push(command)

    def copy(self):
        task = self.currentDimension.exportSchematicIter(self.currentSelection)
        self.copiedSchematic = showProgress("Copying...", task)

    def paste(self):
        if self.copiedSchematic is None:
            return
        view = self.editorTab.currentView()
        imp = PendingImport(self.copiedSchematic, view.mouseBlockPos, self.tr("<Pasted Object>"))
        command = PasteImportCommand(self, imp, "Paste")
        self.undoStack.push(command)

    def pasteBlocks(self):
        NotImplementedYet()

    def pasteEntities(self):
        NotImplementedYet()

    def findReplace(self):
        self.findReplaceDialog.exec_()

    def deleteSelection(self):
        command = SimpleRevisionCommand(self, "Delete")
        with command.begin():
            fillTask = self.currentDimension.fillBlocksIter(self.currentSelection, "air")
            entitiesTask = RemoveEntitiesOperation(self.currentDimension, self.currentSelection)
            task = ComposeOperations(fillTask, entitiesTask)
            showProgress("Deleting...", task)
        self.pushCommand(command)

    def deleteBlocks(self):
        command = SimpleRevisionCommand(self, "Delete Blocks")
        with command.begin():
            fillTask = self.currentDimension.fillBlocksIter(self.currentSelection, "air")
            showProgress("Deleting...", fillTask)
        self.pushCommand(command)

    def deleteEntities(self):
        command = SimpleRevisionCommand(self, "Delete Entities")
        with command.begin():
            entitiesTask = RemoveEntitiesOperation(self.currentDimension, self.currentSelection)
            showProgress("Deleting...", entitiesTask)
        self.pushCommand(command)

    def fill(self):
        fillCommand(self)

    # - Select -

    def selectAll(self):
        command = SelectCommand(self, self.currentDimension.bounds, self.tr("Select All"))
        self.pushCommand(command)

    def deselect(self):
        command = SelectCommand(self, None)
        command.setText(self.tr("Deselect"))
        self.pushCommand(command)

    # --- Library support ---

    def importSchematic(self, filename):
        schematic = WorldEditor(filename, readonly=True)
        ray = self.editorTab.currentView().rayAtCenter()
        pos, face = rayCastInBounds(ray, self.currentDimension)
        if pos is None:
            pos = ray.point

        name = os.path.basename(filename)
        imp = PendingImport(schematic, pos, name)
        command = PasteImportCommand(self, imp, "Import %s" % name)
        self.undoStack.push(command)

    # --- Undo support ---

    revisionChanged = QtCore.Signal(int)

    def undoIndexChanged(self, index):
        self.editorTab.currentView().update()

    def pushCommand(self, command):
        self.undoStack.push(command)

    def setUndoBlock(self, callback):
        self.undoStack.setUndoBlock(callback)

    def removeUndoBlock(self, callback):
        self.undoStack.removeUndoBlock(callback)

    def beginUndo(self):
        self.undoStack.clearUndoBlock()
        self.dirty = True
        self.worldEditor.beginUndo()

    def commitUndo(self):
        self.worldEditor.commitUndo()
        self.revisionChanged.emit(self.worldEditor.currentRevision)

    def undoForward(self):
        self.worldEditor.redo()
        self.revisionChanged.emit(self.worldEditor.currentRevision)

    def undoBackward(self):
        self.worldEditor.undo()
        self.revisionChanged.emit(self.worldEditor.currentRevision)

    def gotoRevision(self, index):
        if index != self.currentRevision:
            self.worldEditor.gotoRevision(index)
            self.revisionChanged.emit(self.worldEditor.currentRevision)

    @property
    def currentRevision(self):
        return self.worldEditor.currentRevision

    # --- Misplaced startup code? ---

    def loadDone(self):
        # Called by MCEditApp after the view is on screen to make sure view.center() works correctly xxx used depth
        #  buffer read for that, now what?
        try:
            player = self.worldEditor.getPlayer()
            center = Vector(*player.Position)
            log.info("Centering on single-player player.")
            rotation = player.Rotation
            try:
                self.editorTab.currentView().yawPitch = rotation
            except AttributeError:
                pass
        except PlayerNotFound:
            try:
                center = self.worldEditor.worldSpawnPosition()
                log.info("Centering on spawn position.")
            except AttributeError:
                log.info("Centering on world center")
                center = self.currentDimension.bounds.origin + (self.currentDimension.bounds.size * 0.5)

        self.editorTab.miniMap.centerOnPoint(center)
        self.editorTab.currentView().centerOnPoint(center)

    # --- Tools ---

    def toolShortcut(self, name):
        toolShortcuts = {
            "Select": "S",
            "Create": "D",
        }
        return toolShortcuts.get(name, "")

    def getTool(self, name):
        for t in self.tools:
            if t.name == name:
                return t


    def chooseTool(self, name):
        oldTool = self.currentTool
        self.currentTool = self.getTool(name)
        if oldTool is not self.currentTool:
            if oldTool:
                oldTool.toolInactive()
            self.currentTool.toolActive()
            self.toolChanged.emit(self.currentTool)
        self.actionsByName[name].setChecked(True)

    toolChanged = QtCore.Signal(object)

    def chunkDidComplete(self):
        from mcedit2 import editorapp
        editorapp.MCEditApp.app.updateStatusLabel(None, None, self.loader.cps, self.editorTab.currentView().fps)

    def updateStatusFromEvent(self, event):
        from mcedit2 import editorapp
        if event.blockPosition:
            id = self.currentDimension.getBlockID(*event.blockPosition)
            data = self.currentDimension.getBlockData(*event.blockPosition)
            block = self.worldEditor.blocktypes[id, data]
            editorapp.MCEditApp.app.updateStatusLabel(event.blockPosition, block, self.loader.cps, event.view.fps)
        else:
            editorapp.MCEditApp.app.updateStatusLabel('(N/A)', None, self.loader.cps, event.view.fps)

    def viewMousePress(self, event):
        self.updateStatusFromEvent(event)
        if hasattr(self.currentTool, 'mousePress') and event.blockPosition is not None:
            self.currentTool.mousePress(event)
        self.editorTab.currentView().update()

    def viewMouseMove(self, event):
        self.updateStatusFromEvent(event)
        if hasattr(self.currentTool, 'mouseMove'):
            self.currentTool.mouseMove(event)
        self.editorTab.currentView().update()

    def viewMouseDrag(self, event):
        self.updateStatusFromEvent(event)
        if hasattr(self.currentTool, 'mouseDrag'):
            self.currentTool.mouseDrag(event)
        self.editorTab.currentView().update()

    def viewMouseRelease(self, event):
        self.updateStatusFromEvent(event)
        if hasattr(self.currentTool, 'mouseRelease'):
            self.currentTool.mouseRelease(event)
        self.editorTab.currentView().update()

    # --- EditorTab handling ---

    def tabCaption(self):
        return util.displayName(self.filename)

    def closeTab(self):
        if self.worldEditor is None:
            return True

        if self.dirty:
            msgBox = QtGui.QMessageBox(self.editorTab.window())
            msgBox.setText("The world has been modified.")
            msgBox.setInformativeText("Do you want to save your changes?")
            msgBox.setStandardButtons(QtGui.QMessageBox.Save | QtGui.QMessageBox.Discard | QtGui.QMessageBox.Cancel)
            msgBox.setDefaultButton(QtGui.QMessageBox.Save)
            ret = msgBox.exec_()

            if ret == QtGui.QMessageBox.Save:
                self.save()

            if ret == QtGui.QMessageBox.Cancel:
                return False

        self.editorTab.saveState()
        self.worldEditor.close()
        self.worldEditor = None
        return True

    # --- Inspector ---

    def inspectBlock(self, pos):
        self.inspectorDockWidget.show()
        self.inspectorWidget.inspectBlock(pos)

    def inspectEntity(self, entity):
        self.inspectorDockWidget.show()
        self.inspectorWidget.inspectEntity(entity)


class EditorTab(QtGui.QWidget):
    """
    EditorTab is the widget containing the editor viewports, the minimap, and
    the settings panel for the currently selected tool.
    """
    def __init__(self, editorSession):
        """

        :type editorSession: mcedit2.editorsession.EditorSession
        :rtype: EditorTab
        """
        settings = Settings()

        QtGui.QWidget.__init__(self)
        self.setContentsMargins(0, 0, 0, 0)

        self.editorSession = editorSession
        self.debugLastCenters = []

        self.viewButtonGroup = QtGui.QButtonGroup(self)
        self.viewButtonToolbar = QtGui.QToolBar()
        self.viewButtons = {}
        self.views = []

        for name, handler in (
            ("2D", self.showCutawayView),
            ("Over", self.showOverheadView),
            # ("Iso", self.showIsoView),
            ("Cam", self.showCameraView),
            # ("4-up", self.showFourUpView),
        ):
            button = QtGui.QToolButton(text=name, checkable=True)
            button.clicked.connect(handler)
            self.viewButtonGroup.addButton(button)
            self.viewButtonToolbar.addWidget(button)
            self.viewButtons[name] = button

        self.viewStack = QtGui.QStackedWidget()

        self.miniMap = MinimapWorldView(editorSession.currentDimension, editorSession.textureAtlas, editorSession.geometryCache)
        self.miniMapDockWidget = QtGui.QDockWidget("Minimap", objectName="MinimapWidget", floating=True)
        self.miniMapDockWidget.setWidget(self.miniMap)
        self.miniMapDockWidget.setFixedSize(256, 256)

        self.views.append(self.miniMap)

        self.toolOptionsArea = QtGui.QScrollArea()
        self.toolOptionsArea.setWidgetResizable(True)

        self.toolOptionsDockWidget = QtGui.QDockWidget("Tool Options", objectName="ToolOptionsWidget", floating=True)
        self.toolOptionsDockWidget.setWidget(self.toolOptionsArea)
        editorSession.dockWidgets.append((Qt.LeftDockWidgetArea, self.miniMapDockWidget))
        editorSession.dockWidgets.append((Qt.LeftDockWidgetArea, self.toolOptionsDockWidget))

        editorSession.loader.addClient(self.miniMap)

        self.overheadViewFrame = OverheadWorldViewFrame(editorSession.currentDimension, editorSession.textureAtlas, editorSession.geometryCache, self.miniMap)
        self.overheadViewFrame.worldView.viewID = "Over"
        self._addView(self.overheadViewFrame)

        self.cutawayViewFrame = CutawayWorldViewFrame(editorSession.currentDimension, editorSession.textureAtlas, editorSession.geometryCache, self.miniMap)
        self.cutawayViewFrame.worldView.viewID = "2D"
        self._addView(self.cutawayViewFrame)
        #
        # self.fourUpViewFrame = FourUpWorldViewFrame(editorSession.currentDimension, editorSession.textureAtlas, editorSession.geometryCache, self.miniMap)
        # self.fourUpViewFrame.worldView.viewID = "4-up"
        # self._addView(self.fourUpViewFrame)

        self.cameraViewFrame = CameraWorldViewFrame(editorSession.currentDimension, editorSession.textureAtlas, editorSession.geometryCache, self.miniMap)
        self.cameraViewFrame.worldView.viewID = "Cam"
        self.cameraView = self.cameraViewFrame.worldView
        self._addView(self.cameraViewFrame)

        self.viewStack.currentChanged.connect(self._viewChanged)
        self.viewChanged.connect(self.viewDidChange)

        self.setLayout(Column(self.viewButtonToolbar,
                              Row(self.viewStack, margin=0), margin=0))

        currentViewName = settings.value("mainwindow/currentview", "Cam")
        if currentViewName not in self.viewButtons:
            currentViewName = "Cam"
        self.viewButtons[currentViewName].click()

    def destroy(self):
        self.editorSession = None
        for view in self.views:
            view.destroy()

        super(EditorTab, self).destroy()
    editorSession = weakrefprop()

    def toolDidChange(self, tool):
        if tool.toolWidget:
            self.toolOptionsArea.takeWidget()  # setWidget gives ownership to the scroll area
            self.toolOptionsArea.setWidget(tool.toolWidget)
            self.toolOptionsDockWidget.setWindowTitle(self.tr(tool.name) + self.tr(" Tool Options"))
        log.info("Setting cursor %r for tool %r on view %r", tool.cursorNode, tool, self.currentView())
        self.currentView().setToolCursor(tool.cursorNode)

    def saveState(self):
        pass

    viewChanged = QtCore.Signal(object)

    def _viewChanged(self, index):
        self.viewChanged.emit(self.currentView())

    def viewDidChange(self, view):
        self.miniMap.centerOnPoint(view.viewCenter())
        Settings().setValue("mainwindow/currentview", view.viewID)
        if self.editorSession.currentTool:
            view.setToolCursor(self.editorSession.currentTool.cursorNode)

        overlayNodes = [tool.overlayNode
                        for tool in self.editorSession.tools
                        if tool.overlayNode is not None]

        overlayNodes.insert(0, self.editorSession.editorOverlay)
        view.setToolOverlays(overlayNodes)
        view.setFocus()


    def viewOffsetChanged(self, view):
        self.miniMap.centerOnPoint(view.viewCenter())
        self.miniMap.currentViewMatrixChanged(view)

    def _addView(self, frame):
        self.views.append(frame)
        frame.stackIndex = self.viewStack.addWidget(frame)
        frame.worldView.viewportMoved.connect(self.viewOffsetChanged)
        frame.worldView.viewActions.extend([
            UseToolMouseAction(self),
            TrackingMouseAction(self)
        ])

    def currentView(self):
        """

        :rtype: mcedit2.worldview.worldview.WorldView
        """
        return self.viewStack.currentWidget().worldView

    def showViewFrame(self, frame):
        center = self.currentView().viewCenter()
        self.debugLastCenters.append(center)
        log.info("Going from %s to %s: Center was %s", self.currentView(), frame.worldView, center)

        self.editorSession.loader.removeClient(self.currentView())
        self.editorSession.loader.addClient(frame.worldView, 0)
        self.viewStack.setCurrentIndex(frame.stackIndex)

        frame.worldView.centerOnPoint(center)

        log.info("Center is now %s", self.currentView().viewCenter())

    def showOverheadView(self):
        self.showViewFrame(self.overheadViewFrame)
    #
    # def showIsoView(self):
    #     self.showViewFrame(self.isoViewFrame)
    #
    # def showFourUpView(self):
    #     self.showViewFrame(self.fourUpViewFrame)

    def showCutawayView(self):
        self.showViewFrame(self.cutawayViewFrame)

    def showCameraView(self):
        self.showViewFrame(self.cameraViewFrame)
