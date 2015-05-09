from __future__ import absolute_import, division, print_function, unicode_literals
import argparse
import collections
import os
import logging

from PySide import QtGui, QtCore, QtNetwork
from PySide.QtCore import Qt
import gc
import numpy
from mcedit2.appsettings import RecentFilesSetting, EnableLightingSetting
from mcedit2.library import LibraryWidget

from mcedit2.util import minecraftinstall
from mcedit2.util.dialogs import NotImplementedYet
from mcedit2.util.directories import getUserFilesDirectory
from mcedit2.util.load_ui import load_ui
from mcedit2.util.objgraphwidget import ObjGraphWidget
from mcedit2.util.resources import resourcePath
from mcedit2.util.worldloader import LoaderTimer
from mcedit2.widgets import prefsdialog, configureblocksdialog
from mcedit2.widgets.blocktype_list import BlockListWidget
from mcedit2.editorsession import EditorSession
from mcedit2.widgets.layout import setWidgetError
from mcedit2.widgets.log_view import LogViewFrame
from mcedit2.rendering.chunkloader import ChunkLoaderInfo
from mcedit2.util import profiler
from mcedit2.util.ipython_widget import terminal_widget
from mcedit2.widgets.objectinspector import ObjectInspector
from mcedit2.util.profilerui import ProfilerWidget
from mcedit2.util.settings import Settings
from mcedit2.worldlist import WorldListWidget
from mcedit2.worldview.worldview import WorldCursorInfo, WorldViewInfo
from mceditlib import util
from mceditlib.anvil.adapter import SessionLockLost


log = logging.getLogger(__name__)



class MCEditMainWindow(QtGui.QMainWindow):
    def __init__(self, *args, **kwargs):
        super(MCEditMainWindow, self).__init__(*args, **kwargs)
        load_ui("main_window.ui", baseinstance=self)
        from mcedit2 import __version__ as v
        self.setWindowTitle(self.tr("MCEdit %(version)s") % {"version": v})

    def loadSettings(self):
        settings = Settings()
        state = settings.value("mainwindow/state", None)
        if state:
            self.restoreState(state)
        geometry = settings.value("mainwindow/geometry", None)
        if geometry:
            self.restoreGeometry(geometry)

    def saveSettings(self):
        settings = Settings()
        settings.setValue("mainwindow/state", self.saveState())
        settings.setValue("mainwindow/geometry", self.saveGeometry())
        settings.sync()

    def closeEvent(self, event):
        self.saveSettings()

        for editor in MCEditApp.app.sessions:
            if not editor.closeTab():
                event.ignore()
                return

class MCEditApp(QtGui.QApplication):
    def __init__(self, argv, DEBUG=False):
        super(MCEditApp, self).__init__(argv)
        self.DEBUG = DEBUG
        MCEditApp.app = self

        minecraftinstall.GetInstalls().ensureValidInstall()
        self.ensureSingle()

        self.commandLineWorlds = []
        self.parseArgs(argv)

        log.warn("UserFilesDirectory: %s", getUserFilesDirectory())

        # --- Necessities ---

        translator = QtCore.QTranslator()
        translator.load(resourcePath('mcedit2/i18n/en_US.ts'))
        self.installTranslator(translator)

        log.info("Loaded translator.")

        self.setOrganizationName("MCEdit")
        self.setOrganizationDomain("mcedit.net")
        self.setApplicationName("MCEdit")
        self.setWindowIcon(QtGui.QIcon(resourcePath("mcedit2/assets/mcedit2/mcediticon.png")))
        styleSheet = file(resourcePath("mcedit2/styles/mcedit2.qcss")).read()
        self.setStyleSheet(styleSheet)

        log.info("Loaded stylesheet.")

        # --- Main Window ---

        self.mainWindow = mainWindow = MCEditMainWindow()

        self.undoGroup = QtGui.QUndoGroup()

        self.tabWidget = self.mainWindow.tabWidget
        self.tabWidget.tabCloseRequested.connect(self.tabCloseRequested)
        self.tabWidget.currentChanged.connect(self.tabChanged)

        log.info("Loaded main window.")

        # --- Sessions ---

        self._currentSession = None
        self.sessions = []
        self.sessionDockWidgets = []
        self.sessionChanged.connect(self.sessionDidChange)

        # --- Panel Widgets ---

        self.undoView = QtGui.QUndoView(self.undoGroup)
        self.undoDockWidget = QtGui.QDockWidget("History", mainWindow, objectName="HistoryWidget")
        self.undoDockWidget.setWidget(self.undoView)
        mainWindow.addDockWidget(Qt.RightDockWidgetArea, self.undoDockWidget)
        mainWindow.panelsToolBar.addAction(self.undoDockWidget.toggleViewAction())
        self.undoDockWidget.close()

        self.logViewWidget = LogViewFrame(mainWindow)
        self.logViewDockWidget = QtGui.QDockWidget("Error Log", mainWindow, objectName="ErrorsWidget")
        self.logViewDockWidget.setWidget(self.logViewWidget)
        mainWindow.addDockWidget(Qt.BottomDockWidgetArea, self.logViewDockWidget)
        mainWindow.panelsToolBar.addAction(self.logViewDockWidget.toggleViewAction())
        self.logViewDockWidget.close()

        self.libraryView = LibraryWidget()
        self.libraryDockWidget = QtGui.QDockWidget("Library", mainWindow, objectName="LibraryWidget")
        self.libraryDockWidget.setWidget(self.libraryView)
        mainWindow.addDockWidget(Qt.RightDockWidgetArea, self.libraryDockWidget)
        mainWindow.panelsToolBar.addAction(self.libraryDockWidget.toggleViewAction())
        self.libraryDockWidget.close()

        self.libraryView.doubleClicked.connect(self.libraryItemDoubleClicked)

        self.globalPanels = [self.undoDockWidget, self.logViewDockWidget, self.libraryDockWidget]

        log.info("Loaded panels.")

        # --- Debug Widgets ---

        if DEBUG:
            debugMenu = self.createDebugMenu()

            self.debugObjectInspector = ObjectInspector(mainWindow)
            self.inspectorDockWidget = QtGui.QDockWidget("Inspector", mainWindow, objectName="InspectorWidget")
            self.inspectorDockWidget.setWidget(self.debugObjectInspector)
            mainWindow.addDockWidget(Qt.RightDockWidgetArea, self.inspectorDockWidget)
            debugMenu.addAction(self.inspectorDockWidget.toggleViewAction())
            self.inspectorDockWidget.close()

            self.profileView = ProfilerWidget()
            profileDockWidget = QtGui.QDockWidget("Profiler", mainWindow, objectName="ProfilerWidget")
            profileDockWidget.setWidget(self.profileView)
            mainWindow.addDockWidget(Qt.RightDockWidgetArea, profileDockWidget)
            debugMenu.addAction(profileDockWidget.toggleViewAction())
            profileDockWidget.close()

            self.textureAtlasView = QtGui.QLabel()
            self.textureAtlasView.setScaledContents(True)
            self.textureAtlasDockWidget = QtGui.QDockWidget("Texture Atlas", mainWindow, objectName="TextureAtlasWidget")

            self.textureAtlasArea = QtGui.QScrollArea()
            self.textureAtlasArea.setWidget(self.textureAtlasView)
            self.textureAtlasDockWidget.setWidget(self.textureAtlasArea)
            mainWindow.addDockWidget(Qt.RightDockWidgetArea, self.textureAtlasDockWidget)
            debugMenu.addAction(self.textureAtlasDockWidget.toggleViewAction())
            self.textureAtlasDockWidget.close()

            infoTabs = QtGui.QTabWidget()

            self.cursorInfo = WorldCursorInfo()
            infoTabs.addTab(self.cursorInfo, "Cursor")

            self.viewInfo = WorldViewInfo()
            infoTabs.addTab(self.viewInfo, "View")

            self.loaderInfo = ChunkLoaderInfo()
            infoTabs.addTab(self.loaderInfo, "Loader")

            infoDockWidget = QtGui.QDockWidget("Debug Info", mainWindow, objectName="DebugInfo")
            infoDockWidget.setWidget(infoTabs)

            mainWindow.addDockWidget(Qt.BottomDockWidgetArea, infoDockWidget)
            mainWindow.tabifyDockWidget(infoDockWidget, self.logViewDockWidget)

            self.globalPanels.append(infoDockWidget)
            mainWindow.panelsToolBar.addAction(infoDockWidget.toggleViewAction())
            infoDockWidget.close()

            log.info("Loaded debug widgets.")

        # --- Menu Actions ---

        # -- MCEdit menu --
        mainWindow.actionNew_World.triggered.connect(self.createNewWorld)
        mainWindow.actionNew_World.setShortcut(QtGui.QKeySequence.New)

        mainWindow.actionOpen_World.triggered.connect(self.chooseOpenWorld)
        mainWindow.actionOpen_World.setShortcut(QtGui.QKeySequence.Open)

        mainWindow.actionShow_World_List.triggered.connect(self.showWorldList)
        mainWindow.actionShow_World_List.setShortcut(QtGui.QKeySequence("Ctrl+L"))

        mainWindow.actionSave_World.triggered.connect(self.saveCurrentWorld)
        mainWindow.actionSave_World.setShortcut(QtGui.QKeySequence.Save)

        mainWindow.actionSave_World_As.triggered.connect(self.saveCurrentWorldAs)
        mainWindow.actionSave_World_As.setShortcut(QtGui.QKeySequence.SaveAs)

        mainWindow.actionClose_World.triggered.connect(self.closeCurrentTab)
        mainWindow.actionClose_World.setShortcut(QtGui.QKeySequence.Close)

        mainWindow.actionExit_MCEdit.triggered.connect(self.exitEditor)
        mainWindow.actionExit_MCEdit.setShortcut(QtGui.QKeySequence.Quit)

        # -- Help menu --
        mainWindow.actionAbout_MCEdit.triggered.connect(self.showAbout)
        mainWindow.actionAbout_MCEdit.setShortcut(QtGui.QKeySequence.Quit)

        # -- Window Menu --
        mainWindow.menuWindow.addAction(self.undoDockWidget.toggleViewAction())
        mainWindow.menuWindow.addAction(self.logViewDockWidget.toggleViewAction())
        mainWindow.menuWindow.addAction(self.libraryDockWidget.toggleViewAction())

        # -- Options Menu --
        mainWindow.actionEnable_Lighting_Updates.setChecked(EnableLightingSetting.value())
        mainWindow.actionEnable_Lighting_Updates.toggled.connect(EnableLightingSetting.setValue)

        EnableLightingSetting.valueChanged.connect(self.enableLightingChanged)
        self.enableLightingChanged(EnableLightingSetting.value())

        mainWindow.actionPreferences.triggered.connect(self.showPrefsDialog)
        mainWindow.actionConfigure_Blocks_Items.triggered.connect(self.showConfigureBlocksDialog)

        log.info("Loaded menus.")

        # --- World List ---

        self.worldList = WorldListWidget(mainWindow)
        self.worldList.editWorldClicked.connect(self.editWorldFromList)
        self.worldList.viewWorldClicked.connect(self.viewWorldFromList)
        self.worldList.backupWorldClicked.connect(self.backupWorldFromList)
        self.worldList.repairWorldClicked.connect(self.repairWorldFromList)

        log.info("Loaded world list.")

        # --- Status Bar ---

        self.positionLabel = QtGui.QLabel("xx, yy, zz", minimumWidth=100)
        self.biomeLabel = QtGui.QLabel("Nowhere", minimumWidth=100)
        self.blocktypeLabel = QtGui.QLabel("(-1:-1)minecraft:rocktonium", minimumWidth=250)
        self.blockNameLabel = QtGui.QLabel("rocktonium", minimumWidth=150)
        self.cpsLabel = QtGui.QLabel("-1 cps", minimumWidth=65)
        self.fpsLabel = QtGui.QLabel("-1 fps", minimumWidth=65)

        statusBar = mainWindow.statusBar()
        statusBar.addPermanentWidget(self.positionLabel)
        statusBar.addPermanentWidget(self.biomeLabel)
        statusBar.addPermanentWidget(self.blocktypeLabel)
        statusBar.addPermanentWidget(self.blockNameLabel)
        statusBar.addPermanentWidget(self.cpsLabel)
        statusBar.addPermanentWidget(self.fpsLabel)

        log.info("Loaded status bar.")

        # --- Load settings ---

        mainWindow.loadSettings()
        self.updateRecentFilesMenu()

        log.info("Loaded settings.")

        # --- App Dialogs ---

        self.prefsDialog = prefsdialog.PrefsDialog(None)
        self.configureBlocksDialog = configureblocksdialog.ConfigureBlocksDialog(None)
        self.configureBlocksDialog.finished.connect(self.configureBlocksFinished)

        # Qt weirdness - initializing QDialog with parent puts the dialog at 0,0 instead of
        # centering it on the parent. Have to set the parent explicitly and put the Qt.Dialog flag back on
        # since changing the parent resets the window flags...
        self.prefsDialog.setParent(mainWindow)
        self.prefsDialog.setWindowFlags(Qt.Dialog)

        self.configureBlocksDialog.setParent(mainWindow)
        self.configureBlocksDialog.setWindowFlags(Qt.Dialog)

        log.info("Loaded app dialogs.")

        # --- Loader timer ---

        self.loadTimer = timer = LoaderTimer(self)
        timer.setInterval(0)
        timer.timeout.connect(self.loadTimerFired)
        timer.start()
        log.info("Loading timer started")

        mainWindow.showMaximized()

        QtCore.QTimer.singleShot(0, self.didFinishLaunching)

    # --- Startup code ---

    @profiler.function
    def didFinishLaunching(self):
        # --- Open files from command line ---
        log.info("Opening worlds from command line.")

        if len(self.commandLineWorlds):
            for filename in self.commandLineWorlds:
                self.loadFile(filename)
        else:
            self.showWorldList()

        if len(self.sessions) and self.args.eval:
            session = self.sessions[-1]
            eval_globals = {"session": session,
                            "self": self}
            exec(self.args.eval, eval_globals)

    consoleWidget = None

    def createDebugMenu(self):
        debugMenu = self.mainWindow.menuBar().addMenu("&Debug")

        def raiseError():
            raise ValueError("User requested error")

        debugMenu.addAction("Raise Error").triggered.connect(raiseError)

        def showConsole():
            if self.consoleWidget is None:
                self.consoleWidget = terminal_widget(sessions=self.sessions)
            self.consoleWidget.show()

        debugMenu.addAction("IPython Console").triggered.connect(showConsole)

        objGraph = ObjGraphWidget()

        def showObjGraph():
            objGraph.show()

        debugMenu.addAction("ObjGraph").triggered.connect(showObjGraph)

        def showHeapy():
            from guppy import hpy
            h = hpy()
            print(h.heap())

        debugMenu.addAction("Heap Trace").triggered.connect(showHeapy)

        debugMenu.addAction("Collect Garbage").triggered.connect(gc.collect)

        return debugMenu

    def ensureSingle(self):
        serverName = "MCEdit.Application"
        socket = QtNetwork.QLocalSocket()
        socket.connectToServer(serverName)
        if socket.waitForConnected(500):
            # xxx maybe write argv to the running app and have it open files?
            log.error("%s already running", serverName)
            raise SystemExit  # Already running

        def newConnection():
            newSocket = server.nextPendingConnection()
            newSocket.close()
            self.mainWindow.activateWindow()
            self.mainWindow.raise_()


        server = QtNetwork.QLocalServer(newConnection=newConnection)
        server._listener = newConnection
        server.listen(serverName)

    def parseArgs(self, argv):
        parser = argparse.ArgumentParser()
        parser.add_argument("filename", nargs="*",
                            help="A list of filenames to open")
        parser.add_argument("-resetPrefs", type=bool,
                            help="Reset MCEdit preferences")
        parser.add_argument("-eval", type=str,
                            help="Code to evaluate in context of current session")

        self.args = parser.parse_args(argv[1:])

        if self.args.resetPrefs:
            Settings().clear()

        for filename in self.args.filename:
            try:
                if os.path.exists(filename):
                    self.commandLineWorlds.append(filename)
                else:
                    log.info("File not found: %s", filename)
            except EnvironmentError as e:
                log.info("%r", e)

    # --- Status Bar ---

    def updateStatusLabel(self, pos=None, blocktype=None, biome=None, cps=None, fps=None):
        if pos is not None:
            if isinstance(pos, basestring):
                self.positionLabel.setText(pos)
            else:
                self.positionLabel.setText("%s, chunk %s" % (tuple(pos), tuple(pos.chunkPos())))
        if biome is not None:
            self.biomeLabel.setText("%s" % biome)
        if blocktype is not None:
            self.blockNameLabel.setText("%s" % blocktype.displayName)
            self.blocktypeLabel.setText("(%d:%d)%s%s" % (blocktype.ID, blocktype.meta, blocktype.internalName, blocktype.blockState))
        if cps is not None:
            self.cpsLabel.setText("%0.1f cps" % cps)
        if fps is not None:
            self.fpsLabel.setText("%0.1f fps" % fps)


    idleTime = 333

    @profiler.function
    def loadTimerFired(self):
        session = self.currentSession()
        if session is None or not hasattr(session, 'loader'):
            log.debug("Loading timer idle (session %r or session.loader %r",
                      session, getattr(session, 'loader', None))

            self.loadTimer.setInterval(self.idleTime)
            return
        try:
            session.loader.next()
            self.loadTimer.setInterval(0)
        except StopIteration:
            log.debug("Loading timer idle (no chunks)")
            self.loadTimer.setInterval(self.idleTime)

    def sessionDidChange(self, session, previousSession):
        """
        :type session: EditorSession
        """
        self.mainWindow.panelsToolBar.clear()
        self.mainWindow.toolsToolBar.clear()
        self.removeSessionDockWidgets()

        menuBar = self.mainWindow.menuBar()
        if previousSession:
            for menu in previousSession.menus:
                menuBar.removeAction(menu.menuAction())

        if session is not None:
            self.undoGroup.setActiveStack(session.undoStack)

            log.info("Adding session menus: %s", session.menus)
            for menu in session.menus:
                menuBar.insertMenu(self.mainWindow.menuWindow.menuAction(), menu)

            for panel in self.globalPanels:
                self.mainWindow.panelsToolBar.addAction(panel.toggleViewAction())
            for panel in session.panels:
                self.mainWindow.panelsToolBar.addAction(panel.toggleViewAction())

            self.mainWindow.panelsToolBar.addSeparator()
            self.mainWindow.panelsToolBar.addAction(session.changeDimensionAction)

            for action in session.toolActions:
                self.mainWindow.toolsToolBar.addAction(action)

            if self.DEBUG:
                self.loaderInfo.object = session.loader
                view = session.editorTab.currentView()
                self.cursorInfo.object = view
                session.editorTab.viewChanged.connect(self.cursorInfo.setObject)
                self.viewInfo.object = view
                session.editorTab.viewChanged.connect(self.viewInfo.setObject)

                atlas = session.textureAtlas
                try:
                    atlas.load()
                except Exception as e:
                    log.exception("Failed to finalize texture atlas.")
                else:
                    argbData = numpy.dstack((atlas.textureData[..., 3:], atlas.textureData[..., :3]))
                    argbData = argbData[::-1, :, ::-1]
                    buf = argbData.tostring()
                    textureAtlasImg = QtGui.QImage(buf,
                                                   atlas.width, atlas.height,
                                                   QtGui.QImage.Format_RGB32)

                    textureAtlasImg.textureImageData = buf  # QImage does not retain backing data

                    pixmap = QtGui.QPixmap.fromImage(textureAtlasImg)
                    pixmap = pixmap.scaled(atlas.width * 2, atlas.height * 2)
                    self.textureAtlasView.setPixmap(pixmap)
                    self.textureAtlasView.resize(atlas.width * 2, atlas.height * 2)

            for pos, dw in session.dockWidgets:
                self.mainWindow.addDockWidget(pos, dw)
                self.sessionDockWidgets.append(dw)

            session.focusWorldView()


    def removeSessionDockWidgets(self):
        for dw in self.sessionDockWidgets:
            self.mainWindow.removeDockWidget(dw)

        self.sessionDockWidgets[:] = ()

    # --- Recent files ---

    def updateRecentFilesMenu(self):
        recentFiles = RecentFilesSetting.value()
        recentWorldsMenu = self.mainWindow.menuRecent_Worlds
        for i, child in enumerate(recentWorldsMenu.children()):
            if i < 2:
                continue  # Skip "clear" and separator
            child.setParent(None)

        log.info("Updating recent files menu: (%d) %s", len(recentFiles), recentFiles)
        filenames = []
        displayNames = collections.Counter()
        for filename in recentFiles:
            text = util.displayName(filename)
            filenames.append((text, filename))
            displayNames[text] += 1

        displayFilenames = []
        for text, path in filenames:
            if displayNames[text] > 1:
                text += " (%s)" % path
            displayFilenames.append((text, path))

        for text, path in displayFilenames:
            log.info("Adding %s", text)
            action = recentWorldsMenu.addAction(text)

            def _triggered(p):
                def _f():
                    self.loadFile(p)
                return _f

            triggered = _triggered(path)
            action.triggered.connect(triggered)
            action.__triggered = triggered

    def addRecentFile(self, filename):
        recentFiles = RecentFilesSetting.value()
        if filename in recentFiles:
            recentFiles.remove(filename)
        recentFiles.insert(0, filename)
        if len(recentFiles) > self.recentFileLimit:
            recentFiles = recentFiles[:-1]

        RecentFilesSetting.setValue(recentFiles)
        self.updateRecentFilesMenu()

    # --- Tabs and sessions ---

    def tabCloseRequested(self, index):
        tab = self.tabWidget.widget(index)
        if hasattr(tab, "editorSession"):
            session = tab.editorSession
            if session.closeTab():
                log.info("Closed session %s", str(session))
                self.tabWidget.removeTab(index)

                # IMPORTANT: Even after removeTab is called, the tab widget must be unparented
                tab.setParent(None)
                self.removeSessionDockWidgets()
                self.undoGroup.removeStack(session.undoStack)
                self.sessions.remove(session)
                gc.collect()
        else:
            self.tabWidget.removeTab(index)

        if self.tabWidget.count() == 0:
            self.showWorldList()

    sessionChanged = QtCore.Signal(EditorSession, EditorSession)

    def tabChanged(self):
        session = self.currentSession()
        self.sessionChanged.emit(session, self._currentSession)
        self._currentSession = session

    def currentTab(self):
        """

        :rtype : EditorTab | QWidget
        """
        return self.tabWidget.currentWidget()

    def currentSession(self):
        """
        Return the current session. Return None if the frontmost tab is not a session tab.

        :rtype : EditorSession | None
        """
        tab = self.currentTab()
        return getattr(tab, 'editorSession', None)

    def getResourceLoaderForFilename(self, filename):
        # Is this world inside a MultiMC instance?
        filename = os.path.normpath(filename)
        installs = minecraftinstall.GetInstalls()
        for instance in installs.instances:
            savesFolder = os.path.normpath(instance.saveFileDir)
            if filename.startswith(savesFolder):
                return instance.getResourceLoader()

        # Nope. Use the version and respack chosen in the world list.
        # ... should search for installs matching this one, but vanilla installs are still multi-version...
        return self.getSelectedResourceLoader()

    def getSelectedResourceLoader(self):
        i = minecraftinstall.currentInstallOption.value()
        if i == -1:
            return minecraftinstall.GetInstalls().getDefaultResourceLoader()

        install = minecraftinstall.GetInstalls().getInstall(i)
        v = minecraftinstall.currentVersionOption.value()
        if not v:
            v = list(install.versions)[0]
        p = minecraftinstall.currentResourcePackOption.value() or None
        return install.getResourceLoader(v, p)

    def loadFile(self, filename, readonly=False):
        self.hideWorldList()
        fileLoadingDialog = QtGui.QProgressDialog(self.tr("Loading world..."),
                                                  None,
                                                  0,
                                                  1,
                                                  self.mainWindow)
        fileLoadingDialog.setAutoReset(False)
        fileLoadingDialog.setWindowModality(Qt.WindowModal)
        fileLoadingDialog.setMinimumDuration(0)
        fileLoadingDialog.setValue(0)
        fileLoadingDialog.setWindowTitle(self.tr("Loading world..."))
        self.processEvents()

        def callback(current, max, status):
            fileLoadingDialog.setValue(current)
            fileLoadingDialog.setMaximum(max)
            fileLoadingDialog.setLabelText(status)


        try:
            resourceLoader = self.getResourceLoaderForFilename(filename)
            configuredBlocks = self.configureBlocksDialog.getConfiguredBlocks()
            session = EditorSession(filename, resourceLoader, configuredBlocks, readonly=readonly, progressCallback=callback)
            self.undoGroup.addStack(session.undoStack)

            self.tabWidget.addTab(session.editorTab, session.tabCaption())
            self.tabWidget.setCurrentWidget(session.editorTab)
            self.sessions.append(session)
            self.addRecentFile(filename)

            session.loadDone()

        except EnvironmentError as e:
            log.exception("EditorSession failed to open %s: %r", filename, e)
            errorTab = QtGui.QWidget()
            setWidgetError(errorTab, e)
            self.tabWidget.addTab(errorTab, "Failed to open %s" % filename)

        fileLoadingDialog.reset()
        # XXX trigger viewportMoved to update minimap after GL initialization
        # session.editorTab.currentView().viewportMoved.emit(session.editorTab.currentView())

    # --- Library ---

    def libraryItemDoubleClicked(self, filename):
        session = self.currentSession()
        if session is None:
            return
        if os.path.isfile(filename):
            session.importSchematic(filename)

    # --- World List actions ---

    def editWorldFromList(self, filename):
        for editor in self.sessions:
            if editor.filename == filename:
                self.tabWidget.setCurrentWidget(editor.editorTab)
        else:
            self.loadFile(filename)

    def viewWorldFromList(self, filename):
        for editor in self.sessions:
            if editor.filename == filename:
                self.tabWidget.setCurrentWidget(editor.editorTab)
        else:
            self.loadFile(filename, readonly=True)

    def repairWorldFromList(self, filename):
        NotImplementedYet()

    def backupWorldFromList(self, filename):
        NotImplementedYet()

    # --- MCEdit Menu Actions ---

    def createNewWorld(self):
        NotImplementedYet()

    def chooseOpenWorld(self):
        startingDir = Settings().value("open_world_dialog/starting_dir", os.path.expanduser("~"))
        result = QtGui.QFileDialog.getOpenFileName(self.mainWindow, self.tr("Open World, Level or Schematic"),
                                                   startingDir,
                                                   "All files (*.*)")
        if result:
            filename = result[0]
            if filename:
                dirname, basename = os.path.split(filename)
                if basename in ("level.dat", "level.dat_old"):
                    dirname, basename = os.path.split(filename)

                Settings().setValue("open_world_dialog/starting_dir", dirname)
                self.loadFile(filename)

    def showWorldList(self):
        self.worldList.show()

    def saveCurrentWorld(self):
        session = self.currentSession()
        if session:
            try:
                session.save()
            except SessionLockLost as e:
                msgBox = QtGui.QMessageBox(QtGui.qApp.mainWindow)
                msgBox.setWindowTitle("Session Lock Lost")
                msgBox.setText("MCEdit has lost the session lock on this world.")
                msgBox.setInformativeText("Minecraft or another program has taken the session lock for this world. "
                                          "MCEdit cannot ensure the world will be in a consistent state after editing. "
                                          "The world must be closed.\n\n(In the future, you may be able to reopen the "
                                          "world and replay your editing history on top of the world's new state.)")
                msgBox.exec_()
                session.dirty = False  # Avoid invoking session.save() again.
                self.closeCurrentTab()

    def saveCurrentWorldAs(self):
        pass

    def closeCurrentTab(self):
        tab = self.currentTab()
        idx = self.tabWidget.indexOf(tab)
        self.tabCloseRequested(idx)

    def exitEditor(self):
        for session in self.sessions:
            if not session.closeTab():
                return

        self.mainWindow.saveSettings()
        raise SystemExit

    # --- Help Menu Actions ---

    def showAbout(self):
        from mcedit2 import __version__ as v
        QtGui.QMessageBox.about(self.mainWindow,
                                "MCEdit %s" % v,
                                "MCEdit %s\n\nCopyright 2014 "
                                "David Rio Vierra. All rights reserved." % v
                                )

    recentFileLimit = 15

    # --- App-level widgets(?) ---

    def showBlockList(self):
        session = self.currentSession()

        blockList = BlockListWidget(session.worldEditor.blocktypes, session.textureAtlas)
        self.tabWidget.insertTab(0, blockList, "Blocks for world %s" % session.filename)
        self.tabWidget.setCurrentIndex(0)

    def hideWorldList(self):
        self.worldList.close()
        self.tabWidget.removeTab(self.tabWidget.indexOf(self.worldList))

    # --- Options ---

    def enableLightingChanged(self, value):
        from mceditlib import relight
        relight.ENABLE_LIGHTING = value

    def showPrefsDialog(self):
        self.prefsDialog.exec_()

    def showConfigureBlocksDialog(self):
        self.configureBlocksDialog.showWithSession(self.currentSession())

    def configureBlocksFinished(self):
        configuredBlocks = self.configureBlocksDialog.getConfiguredBlocks()
        self.currentSession().setConfiguredBlocks(configuredBlocks)
