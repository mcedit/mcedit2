from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import os

from PySide import QtGui, QtCore
from PySide.QtCore import Qt

from mcedit2 import editortools
from mcedit2.command import SimpleRevisionCommand
from mcedit2.rendering.blockmodels import BlockModels
from mcedit2.util.dialogs import NotImplementedYet
from mcedit2.util.resources import resourcePath
from mcedit2.util.showprogress import showProgress
from mcedit2.worldview.worldview import UseToolMouseAction, TrackingMouseAction
from mceditlib import util
from mcedit2.rendering import chunkloader, blockmeshes, scenegraph
from mcedit2.rendering.geometrycache import GeometryCache
from mcedit2.rendering.textureatlas import TextureAtlas
from mcedit2.widgets.layout import Column, Row
from mcedit2.util.settings import Settings
from mcedit2.worldview.camera import CameraWorldViewFrame
from mcedit2.worldview.cutaway import CutawayWorldViewFrame
from mcedit2.worldview.minimap import MinimapWorldView
from mcedit2.worldview.overhead import OverheadWorldViewFrame
from mceditlib.geometry import Vector
from mceditlib.exceptions import PlayerNotFound
from mceditlib.revisionhistory import UndoFolderExists
from mceditlib.worldeditor import WorldEditor


log = logging.getLogger(__name__)
"""
    An EditorSession is a world currently opened for editing, the state of the editor including the current
    selection box, the editor tab containing its viewports, its command history, a separate instance of each editor
    tool (why?), and the ChunkLoader that coordinates loading chunks into its viewports.
    """

class EditorSession(QtCore.QObject):
    def __init__(self, filename, versionInfo, readonly=False):
        QtCore.QObject.__init__(self)
        self.undoStack = QtGui.QUndoStack()

        self.filename = filename
        self.dockWidgets = []
        self.undoBlock = None
        self.currentTool = None
        self.dirty = False
        self.copiedSchematic = None
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
        self.loader.allChunksDone.connect(lambda: self.editorTab.currentView().update())

        # --- Menus ---

        self.menus = []

        self.menuEdit = QtGui.QMenu(self.tr("Edit"))
        self.menuEdit.setObjectName("menuEdit")
        self.actionUndo = QtGui.QAction(self.tr("Undo"), self, triggered=self.undo, enabled=False)
        self.actionUndo.setObjectName("actionUndo")
        self.actionRedo = QtGui.QAction(self.tr("Redo"), self, triggered=self.redo, enabled=False)
        self.actionRedo.setObjectName("actionRedo")
        self.actionCut = QtGui.QAction(self.tr("Cut"), self, triggered=self.cut, enabled=False)
        self.actionCut.setObjectName("actionCut")
        self.actionCopy = QtGui.QAction(self.tr("Copy"), self, triggered=self.copy, enabled=False)
        self.actionCopy.setObjectName("actionCopy")
        self.actionPaste = QtGui.QAction(self.tr("Paste"), self, triggered=self.paste, enabled=False)
        self.actionPaste.setObjectName("actionPaste")
        self.actionPaste_Blocks = QtGui.QAction(self.tr("Paste Blocks"), self, triggered=self.pasteBlocks, enabled=False)
        self.actionPaste_Blocks.setObjectName("actionPaste_Blocks")
        self.actionPaste_Entities = QtGui.QAction(self.tr("Paste Entities"), self, triggered=self.pasteEntities, enabled=False)
        self.actionPaste_Entities.setObjectName("actionPaste_Entities")
        self.actionClear = QtGui.QAction(self.tr("Clear"), self, triggered=self.clear, enabled=False)
        self.actionClear.setObjectName("actionClear")
        self.menuEdit.addAction(self.actionUndo)
        self.menuEdit.addAction(self.actionRedo)
        self.menuEdit.addSeparator()
        self.menuEdit.addAction(self.actionCut)
        self.menuEdit.addAction(self.actionCopy)
        self.menuEdit.addAction(self.actionPaste)
        self.menuEdit.addAction(self.actionPaste_Blocks)
        self.menuEdit.addAction(self.actionPaste_Entities)
        self.menuEdit.addAction(self.actionClear)

        self.actionUndo.setShortcut(QtGui.QKeySequence.Undo)
        self.actionRedo.setShortcut(QtGui.QKeySequence.Redo)
        self.actionCut.setShortcut(QtGui.QKeySequence.Cut)
        self.actionCopy.setShortcut(QtGui.QKeySequence.Copy)
        self.actionPaste.setShortcut(QtGui.QKeySequence.Paste)
        self.actionPaste_Blocks.setShortcut(QtGui.QKeySequence("Ctrl+Shift+V"))
        self.actionPaste_Entities.setShortcut(QtGui.QKeySequence("Ctrl+Alt+V"))
        self.actionClear.setShortcut(QtGui.QKeySequence.Quit)

        self.menus.append(self.menuEdit)

        # --- Resources ---

        i, v, p = self.versionInfo
        self.resourceLoader = i.getResourceLoader(v, p)
        self.geometryCache = GeometryCache()
        self.blockModels = BlockModels(self.worldEditor.blocktypes, self.resourceLoader)
        self.textureAtlas = TextureAtlas(self.worldEditor, self.resourceLoader, self.blockModels)

        self.editorOverlay = scenegraph.Node()

        # --- Tools ---
        def PickToolAction(tool):
            name = tool.name
            iconName = tool.iconName
            if iconName:
                iconPath = resourcePath("mcedit2/assets/mcedit2/toolicons/%s.png" % iconName)
                if not os.path.exists(iconPath):
                    log.error("Tool icon %s not found", iconPath)
                    icon = None
                else:
                    icon = QtGui.QIcon(iconPath)
            else:
                icon = None

            def _triggered():
                self.chooseTool(name)

            action = QtGui.QAction(
                self.tr(name),
                self,
                shortcut=self.toolShortcut(name),
                triggered=_triggered,
                checkable=True,
                icon=icon,
                )
            action.toolName = name
            action._triggered = _triggered  # Needed because connecting _triggered doesn't increase its refcount

            self.toolActionGroup.addAction(action)
            return action

        self.toolClasses = list(editortools.ToolClasses())
        self.toolActionGroup = QtGui.QActionGroup(self)
        self.toolActions = [PickToolAction(cls) for cls in self.toolClasses]
        self.actionsByName = {action.toolName: action for action in self.toolActions}
        self.tools = {cls.name: cls(self) for cls in self.toolClasses}

        self.selectionTool = self.tools["Select"]

        # --- Editor stuff ---
        self.editorTab = EditorTab(self)
        self.toolChanged.connect(self.editorTab.toolDidChange)

        self.undoStack.indexChanged.connect(lambda: self.editorTab.currentView().update())

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

    @property
    def selectionBox(self):
        return self.selectionTool.currentSelection

    @selectionBox.setter
    def selectionBox(self, value):
        self.selectionTool.currentSelection = value

    # --- Menu commands ---

    def save(self):
        self.worldEditor.saveChanges()
        self.dirty = False

    def undo(self):
        self.undoStack.undo()

    def redo(self):
        self.undoStack.redo()

    def cut(self):
        command = SimpleRevisionCommand(self, "Cut")
        with command.begin():
            task = self.currentDimension.exportSchematicIter(self.selectionBox)
            self.copiedSchematic = showProgress("Cutting...", task)
            task = self.currentDimension.fillBlocksIter(self.selectionBox, "air")
            showProgress("Cutting...", task)
        self.undoStack.push(command)

    def copy(self):
        task = self.currentDimension.exportSchematicIter(self.selectionBox)
        self.copiedSchematic = showProgress("Copying...", task)

    def paste(self):
        if self.copiedSchematic is None:
            return

        moveTool = self.tools["Move"]
        if moveTool is self.currentTool:
            moveTool.completeMove()
        moveTool.movingSchematic = self.copiedSchematic
        moveTool.movePosition = self.editorTab.currentView().viewCenter()
        self.chooseTool("Move")

    def pasteBlocks(self):
        NotImplementedYet()

    def pasteEntities(self):
        NotImplementedYet()

    def clear(self):
        self.selectionTool.deleteSelection()

    # --- Undo support ---

    def pushCommand(self, command):
        self.undoStack.push(command)

    def setUndoBlock(self, callback):
        """
        Set a function to be called before the next time beginUndo is called. Some tools may need to call beginUndo,
        then interact with the user for a time before calling commitUndo, or they may need to use multiple undo
        revisions for a single operation with freedom given to the user between revisions. This ensures that
        the interactive operation will be completed or aborted before the next command begins its undo revision.

        User actions that only change the editor state will not call beginUndo, and their QUndoCommand may end up
        before the interrupted command in the history.

        :param callback: Function to call
        :type callback: callable
        """
        assert not self.undoBlock, "Cannot add multiple undo blocks (yet)"
        self.undoBlock = callback

    def removeUndoBlock(self, callback):
        if self.undoBlock:
            if callback != self.undoBlock:  # can't use 'is' for func ptrs, why?
                raise ValueError("Trying to remove an undoBlock that is not set, had %r and asked to remove %r",
                                 self.undoBlock, callback)
            self.undoBlock = None

    def beginUndo(self):
        if self.undoBlock:
            callback = self.undoBlock
            self.undoBlock = None
            callback()

        self.dirty = True
        self.worldEditor.beginUndo()

    def commitUndo(self):
        self.worldEditor.commitUndo()

    def undoForward(self):
        self.worldEditor.redo()

    def undoBackward(self):
        self.worldEditor.undo()

    def gotoRevision(self, index):
        self.worldEditor.gotoRevision(index)

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

    def chooseTool(self, name):
        oldTool = self.currentTool
        self.currentTool = self.tools[name]
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


class EditorTab(QtGui.QWidget):
    """
    EditorTab is the widget containing the editor viewports, the minimap, and
    the settings panel for the currently selected tool.
    """
    def __init__(self, editorSession):
        """

        :type editorSession: mcedit2.editorsession.EditorSession
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

    def toolDidChange(self, tool):
        if tool.toolWidget:
            self.toolOptionsArea.takeWidget()  # setWidget gives ownership to the scroll area
            self.toolOptionsArea.setWidget(tool.toolWidget)
            self.toolOptionsDockWidget.setWindowTitle(self.tr(tool.name) + self.tr(" Tool Options"))
        if tool.cursorNode:
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
                        for tool in self.editorSession.tools.itervalues()
                        if tool.overlayNode is not None]

        overlayNodes.insert(0, self.editorSession.editorOverlay)
        view.setToolOverlays(overlayNodes)


    def viewOffsetChanged(self, view):
        def _offsetChanged(offset):
            self.miniMap.centerOnPoint(view.viewCenter())
            self.miniMap.currentViewMatrixChanged(view)
        return _offsetChanged

    def _addView(self, frame):
        self.views.append(frame)
        frame.stackIndex = self.viewStack.addWidget(frame)
        frame.worldView.viewportMoved.connect(self.viewOffsetChanged(frame.worldView))
        frame.worldView.mouseActions.extend([
            UseToolMouseAction(self.editorSession),
            TrackingMouseAction(self.editorSession)
        ])

    def currentView(self):
        """

        :rtype: WorldView
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
