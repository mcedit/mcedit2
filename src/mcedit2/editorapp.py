from __future__ import absolute_import, division, print_function, unicode_literals

import collections
import gc
import logging
import os
import sys

import argparse
import numpy
from PySide import QtGui, QtCore, QtNetwork
from PySide.QtCore import Qt

from mcedit2 import plugins
from mcedit2.appsettings import RecentFilesSetting, EnableLightingSetting, DevModeSetting
from mcedit2.dialogs import configure_blocks
from mcedit2.dialogs.error_dialog import showErrorDialog
from mcedit2.dialogs.plugins_dialog import PluginsDialog, showPluginLoadError, showPluginUnloadError
from mcedit2.editorsession import EditorSession
from mcedit2.library import LibraryWidget
from mcedit2.rendering.chunkloader import ChunkLoaderInfo
from mcedit2.ui.main_window import Ui_mainWindow
from mcedit2.util import minecraftinstall
from mcedit2.util import profiler
from mcedit2.util.dialogs import NotImplementedYet
from mcedit2.util.directories import getUserFilesDirectory, getUserPluginsDirectory
from mcedit2.util.ipython_widget import terminal_widget
from mcedit2.util.objgraphwidget import ObjGraphWidget
from mcedit2.util.profilerui import ProfilerWidget
from mcedit2.util.qglcontext import setDefaultFormat
from mcedit2.util.resources import resourcePath
from mcedit2.util.settings import Settings
from mcedit2.util.showprogress import MCEProgressDialog
from mcedit2.util.worldloader import LoaderTimer
from mcedit2.widgets import prefsdialog
from mcedit2.widgets.blocktype_list import BlockListWidget
from mcedit2.widgets.layout import setWidgetError, Column, Row
from mcedit2.widgets.mcedockwidget import MCEDockWidget
from mcedit2.widgets.objectinspector import ObjectInspector
from mcedit2.worldlist import WorldListWidget
from mcedit2.worldview.worldview import WorldCursorInfo, WorldViewInfo
from mceditlib import util
from mceditlib.anvil.adapter import SessionLockLost

log = logging.getLogger(__name__)


class UserRequestedError(ValueError):
    """ Raised from the "Raise Error" item in the "Debug" menu. Used to test error reporting. """

class MCEditMainWindow(QtGui.QMainWindow, Ui_mainWindow):
    def __init__(self, *args, **kwargs):
        super(MCEditMainWindow, self).__init__(*args, **kwargs)
        self.setupUi(self)
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

        MCEditApp.app.quit()

LangSetting = Settings().getOption("app_language", str)

class MCEditApp(QtGui.QApplication):
    def __init__(self, argv):
        super(MCEditApp, self).__init__(argv)
        MCEditApp.app = self
        
        self.ensureSingle()

        self.commandLineWorlds = []
        self.parseArgs(argv)

        log.warn("UserFilesDirectory: %s", getUserFilesDirectory())

        # --- Translations ---

        self.transDir = resourcePath('mcedit2/i18n')
        self.transLangs = [f[:-3] for f in os.listdir(self.transDir) if f.endswith(".qm")]

        lang = LangSetting.value()

        langFile = self.findLangFile(lang)

        if langFile is None:
            systemLocale = QtCore.QLocale.system()
            lang = systemLocale.name()  # "en_US"
            langFile = self.findLangFile(lang)

            if langFile is None:
                lang = "en"
                langFile = os.path.join(self.transDir, "en.qm")

        chosenLang = lang
        self.translator = QtCore.QTranslator()
        self.translator.load(langFile)
        self.installTranslator(self.translator)

        log.info("Loaded translator. Selected language: %s", lang)

        self.translationsMenu = QtGui.QMenu()
        self.translationsMenu.setTitle(self.tr("Language"))

        self.langActions = []

        for lang in self.transLangs:
            locale = QtCore.QLocale(lang)
            language = locale.nativeLanguageName().title() or lang
            if lang == "pr":
                language = "Pirate"
            langAction = self.translationsMenu.addAction(language)
            langAction.setData(lang)
            langAction.setCheckable(True)
            if lang == chosenLang:
                langAction.setChecked(True)
            self.langActions.append(langAction)

        self.translationsMenu.triggered.connect(self.changeLanguage)

        # --- Necessities ---

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

        tttIcon = QtGui.QIcon(resourcePath("mcedit2/assets/mcedit2/icons/toolbar_text.png"))

        self.toggleToolbarTextAction = QtGui.QAction(tttIcon, "Toolbar Text", self)

        self.toggleToolbarTextAction.setCheckable(True)
        self.toggleToolbarTextAction.setChecked(True)

        self.toggleToolbarTextAction.toggled.connect(self.toggleToolbarText)

        # --- OpenGL ---

        setDefaultFormat()

        # --- Sessions ---

        self._currentSession = None
        self.sessions = []
        self.sessionDockWidgets = []
        self.sessionChanged.connect(self.sessionDidChange)

        # --- Panel Widgets ---
        historyIcon = QtGui.QIcon(resourcePath("mcedit2/assets/mcedit2/icons/history.png"))

        self.undoView = QtGui.QUndoView(self.undoGroup)
        self.undoDockWidget = MCEDockWidget("History", mainWindow, objectName="HistoryWidget")
        self.undoDockWidget.setWidget(self.undoView)
        self.undoDockWidget.setWindowIcon(historyIcon)
        self.undoDockWidget.setUnfocusedOpacity(0.8)

        mainWindow.addDockWidget(Qt.RightDockWidgetArea, self.undoDockWidget)
        undoToggleAction = self.undoDockWidget.toggleViewAction()
        undoToggleAction.setIcon(historyIcon)
        mainWindow.panelsToolBar.addAction(undoToggleAction)
        self.undoDockWidget.close()

        libraryIcon = QtGui.QIcon(resourcePath("mcedit2/assets/mcedit2/icons/library.png"))
        self.libraryWidget = LibraryWidget()
        self.libraryDockWidget = MCEDockWidget("Library", mainWindow, objectName="LibraryWidget")
        self.libraryDockWidget.setWidget(self.libraryWidget)
        self.libraryDockWidget.setWindowIcon(libraryIcon)
        self.libraryDockWidget.setUnfocusedOpacity(0.8)

        mainWindow.addDockWidget(Qt.RightDockWidgetArea, self.libraryDockWidget)

        libraryToggleAction = self.libraryDockWidget.toggleViewAction()
        libraryToggleAction.setIcon(libraryIcon)
        mainWindow.panelsToolBar.addAction(libraryToggleAction)
        self.libraryDockWidget.close()
        self.sessionChanged.connect(self.libraryWidget.sessionDidChange)

        self.libraryWidget.doubleClicked.connect(self.libraryItemDoubleClicked)

        self.globalPanels = [self.undoDockWidget, self.libraryDockWidget]

        log.info("Loaded panels.")

        # --- Debug Widgets ---

        self.debugMenu = self.createDebugMenu()

        self.debugObjectInspector = ObjectInspector(mainWindow)
        self.inspectorDockWidget = MCEDockWidget("Object Inspector", mainWindow, objectName="InspectorWidget")
        self.inspectorDockWidget.setWidget(self.debugObjectInspector)
        self.debugMenu.addAction(self.inspectorDockWidget.toggleViewAction())
        self.inspectorDockWidget.close()

        self.profileView = ProfilerWidget()
        self.profileDockWidget = MCEDockWidget("Profiler", mainWindow, objectName="ProfilerWidget")
        self.profileDockWidget.setWidget(self.profileView)
        self.debugMenu.addAction(self.profileDockWidget.toggleViewAction())
        self.profileDockWidget.close()

        self.textureAtlasView = QtGui.QLabel()
        self.textureAtlasView.setScaledContents(True)
        self.textureAtlasDockWidget = MCEDockWidget("Texture Atlas", mainWindow, objectName="TextureAtlasWidget")

        self.textureAtlasArea = QtGui.QScrollArea()
        self.textureAtlasArea.setWidget(self.textureAtlasView)
        self.textureAtlasDockWidget.setWidget(self.textureAtlasArea)
        self.debugMenu.addAction(self.textureAtlasDockWidget.toggleViewAction())
        self.textureAtlasDockWidget.close()

        infoTabs = QtGui.QTabWidget()

        self.cursorInfo = WorldCursorInfo()
        infoTabs.addTab(self.cursorInfo, "Cursor")

        self.viewInfo = WorldViewInfo()
        infoTabs.addTab(self.viewInfo, "View")

        self.loaderInfo = ChunkLoaderInfo()
        infoTabs.addTab(self.loaderInfo, "Loader")

        self.infoDockWidget = MCEDockWidget("Debug Info", mainWindow, objectName="DebugInfo")
        self.infoDockWidget.setWidget(infoTabs)
        self.infoDockWidget.close()

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
        mainWindow.menuWindow.addAction(self.libraryDockWidget.toggleViewAction())

        # -- Options Menu --
        mainWindow.actionEnable_Lighting_Updates.setChecked(EnableLightingSetting.value())
        mainWindow.actionEnable_Lighting_Updates.toggled.connect(EnableLightingSetting.setValue)

        EnableLightingSetting.valueChanged.connect(self.enableLightingChanged)
        self.enableLightingChanged(EnableLightingSetting.value())

        mainWindow.actionPreferences.triggered.connect(self.showPrefsDialog)
        mainWindow.actionConfigure_Blocks_Items.triggered.connect(self.showConfigureBlocksDialog)
        mainWindow.actionConfigure_Blocks_Items.setEnabled(False)
        mainWindow.actionPlugins.triggered.connect(self.showPluginsDialog)

        mainWindow.actionEnable_Developer_Mode.setChecked(DevModeSetting.value())
        mainWindow.actionEnable_Developer_Mode.toggled.connect(DevModeSetting.setValue)
        DevModeSetting.valueChanged.connect(self.toggleDeveloperMode)
        self.toggleDeveloperMode(DevModeSetting.value())

        mainWindow.menuOptions.addMenu(self.translationsMenu)

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

        # Qt weirdness - initializing QDialog with parent puts the dialog at 0,
        # 0 instead of centering it on the parent. Have to set the parent explicitly
        # and put the Qt.Dialog flag back on since changing the parent resets the
        # window flags...

        self.prefsDialog = prefsdialog.PrefsDialog(None)
        self.prefsDialog.setParent(mainWindow)
        self.prefsDialog.setWindowFlags(Qt.Dialog)

        self.configureBlocksDialog = configure_blocks.ConfigureBlocksDialog(None)
        self.configureBlocksDialog.finished.connect(self.configureBlocksFinished)
        self.configureBlocksDialog.setParent(mainWindow)
        self.configureBlocksDialog.setWindowFlags(Qt.Dialog)

        self.pluginsDialog = PluginsDialog()
        self.pluginsDialog.setParent(mainWindow)
        self.pluginsDialog.setWindowFlags(Qt.Dialog)

        log.info("Loaded app dialogs.")

        # --- Loader timer ---

        self.loadTimer = timer = LoaderTimer(self)
        timer.setInterval(0)
        timer.timeout.connect(self.loadTimerFired)
        timer.start()
        log.info("Loading timer started")

        mainWindow.showMaximized()

    # --- Startup code ---
    
    def startup(self):
        
        minecraftinstall.GetInstalls().ensureValidInstall()

        log.info("Finding plugins")

        if getattr(sys, 'frozen', False):
            # frozen - load from app dir
            pluginsDir = getUserPluginsDirectory()
            plugins.findNewPluginsInDir(pluginsDir)
        else:
            # not frozen - load from src/plugins
            # from editorapp.py, ../../plugins
            devPluginsDir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugins")
            plugins.findNewPluginsInDir(devPluginsDir)

        for pluginRef in plugins.getAllPlugins():
            if pluginRef.enabled:
                if not pluginRef.load():
                    showPluginLoadError(pluginRef)

        log.info("Opening worlds from command line.")

        if len(self.commandLineWorlds):
            for filename in self.commandLineWorlds:
                self.loadFile(filename, self.args.view)
        else:
            self.showWorldList()

        if len(self.sessions) and self.args.eval:
            session = self.sessions[-1]
            eval_globals = {"session": session,
                            "self": self}
            exec(self.args.eval, eval_globals)

    pluginsChanged = QtCore.Signal()

    consoleWidget = None

    def createDebugMenu(self):
        debugMenu = QtGui.QMenu(self.tr("&Debug"))

        def raiseError():
            ret = QtGui.QMessageBox.warning(self.mainWindow,
                                            self.tr("Raise Error"),
                                            self.tr("Raise an error? This may crash MCEdit."),
                                            buttons=QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
            if ret == QtGui.QMessageBox.Yes:
                raise UserRequestedError("User requested error")

        debugMenu.addAction(self.tr("Raise Error")).triggered.connect(raiseError)

        def showConsole():
            if self.consoleWidget is None:
                self.consoleWidget = terminal_widget(sessions=self.sessions)
            self.consoleWidget.show()

        debugMenu.addAction(self.tr("IPython Console")).triggered.connect(showConsole)

        objGraph = ObjGraphWidget()

        def showObjGraph():
            objGraph.show()

        debugMenu.addAction(self.tr("ObjGraph")).triggered.connect(showObjGraph)

        def showHeapy():
            from guppy import hpy
            h = hpy()
            print(h.heap())

        debugMenu.addAction(self.tr("Heap Trace (slow)")).triggered.connect(showHeapy)

        debugMenu.addAction(self.tr("Collect Garbage")).triggered.connect(gc.collect)

        return debugMenu

    def ensureSingle(self):
        serverName = "MCEdit.Application"
        socket = QtNetwork.QLocalSocket()
        socket.connectToServer(serverName)
        if socket.waitForConnected(500):
            # TODO: get filenames from argv and pass to running app
            log.error("%s already running", serverName)
            raise SystemExit  # Already running

        def newConnection():
            newSocket = server.nextPendingConnection()
            # TODO: read filenames from socket
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
        parser.add_argument("-resetPrefs", action='store_true',
                            help="Reset MCEdit preferences")
        parser.add_argument("-eval", type=str,
                            help="Code to evaluate in context of current session")
        parser.add_argument("-view", action='store_true',
                            help="Open the given filenames read-only")

        self.args = parser.parse_args(argv[1:])

        if self.args.resetPrefs:
            Settings().clear()

        for filename in self.args.filename:
            try:
                # we use `unicode` filenames, but argv is `str`
                # should only get `str` on linux/osx - need to get wargv on windows
                if isinstance(filename, str):
                    filename = filename.decode(sys.getfilesystemencoding())
                if os.path.exists(filename):
                    self.commandLineWorlds.append(filename)
                else:
                    log.info("File not found: %s", filename)
            except EnvironmentError as e:
                log.info("%r", e)
            except UnicodeDecodeError as e:
                log.info("%r", e)

    # --- Language Menu ---

    def findLangFile(self, lang):
        if lang in self.transLangs:
            return os.path.join(self.transDir, lang + ".qm")
        lang = lang.split("_")[0]
        if lang in self.transLangs:
            return os.path.join(self.transDir, lang + ".qm")
        return None

    def changeLanguage(self, action):
        lang = action.data()
        langFile = self.findLangFile(lang)
        self.removeTranslator(self.translator)
        self.translator = QtCore.QTranslator()
        self.translator.load(langFile)
        self.installTranslator(self.translator)

        for a in self.langActions:
            a.setChecked(False)
        action.setChecked(True)

        LangSetting.setValue(lang)
        log.info("Changed language to %s", lang)


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

    # --- Global chunk loading timer ---

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

    # --- Update UI after tab change ---

    def sessionDidChange(self, session, previousSession):
        """
        :type session: EditorSession
        """
        self.mainWindow.panelsToolBar.clear()
        self.mainWindow.panelsToolBar.addAction(self.toggleToolbarTextAction)

        self.mainWindow.toolsToolBar.clear()
        self.removeSessionDockWidgets()

        menuBar = self.mainWindow.menuBar()
        if previousSession:
            for menu in previousSession.menus:
                menuBar.removeAction(menu.menuAction())

        if session is None:
            self.undoGroup.setActiveStack(None)
        else:
            self.undoGroup.setActiveStack(session.undoStack)

            log.info("Adding session menus: %s", session.menus)
            for menu in session.menus:
                menuBar.insertAction(self.mainWindow.menuWindow.menuAction(), menu.menuAction())

            for action in session.topToolbarActions:
                if action is None:
                    self.mainWindow.panelsToolBar.addSeparator()
                else:
                    self.mainWindow.panelsToolBar.addAction(action)

            for panel in session.panels:
                self.mainWindow.panelsToolBar.addAction(panel.toggleViewAction())

            self.mainWindow.panelsToolBar.addSeparator()

            for panel in self.globalPanels:
                self.mainWindow.panelsToolBar.addAction(panel.toggleViewAction())

            for action in session.toolActions:
                if action is None:
                    self.mainWindow.toolsToolBar.addSeparator()
                else:
                    self.mainWindow.toolsToolBar.addAction(action)

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
                if dw.wasVisible is not None:
                    dw.setVisible(dw.wasVisible)

            session.focusWorldView()

    def removeSessionDockWidgets(self):
        for dw in self.sessionDockWidgets:
            dw.wasVisible = dw.isVisible()
            self.mainWindow.removeDockWidget(dw)
            dw.setParent(None)

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
                self.undoGroup.removeStack(session.undoStack)
                self.sessions.remove(session)
                session.dealloc()
                del tab
                del session
                gc.collect()
        else:
            self.tabWidget.removeTab(index)

        if self.tabWidget.count() == 0:
            self.showWorldList()

    sessionChanged = QtCore.Signal(EditorSession, EditorSession)

    def tabChanged(self):
        session = self.currentSession()
        self.mainWindow.actionConfigure_Blocks_Items.setEnabled(session is not None)
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

    def loadFile(self, filename, readonly=False):
        filename = os.path.normpath(filename)

        for s in self.sessions:
            if s.filename == filename:
                self.tabWidget.setCurrentWidget(s.editorTab)
                return

        self.hideWorldList()
        fileLoadingDialog = MCEProgressDialog(self.tr("Loading world..."),
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
            configuredBlocks = self.configureBlocksDialog.getConfiguredBlocks()
            session = EditorSession(filename, configuredBlocks, readonly=readonly, progressCallback=callback)
            self.undoGroup.addStack(session.undoStack)

            self.tabWidget.addTab(session.editorTab, session.tabCaption())
            self.tabWidget.setCurrentWidget(session.editorTab)
            self.sessions.append(session)
            self.addRecentFile(filename)

            session.loadDone()

        except Exception as e:
            log.exception("EditorSession failed to open %s: %r", filename, e)
            errorTab = QtGui.QWidget()
            setWidgetError(errorTab, e, "An error occurred while opening %s" % filename)
            self.tabWidget.addTab(errorTab, "Failed to open %s" % filename)

        fileLoadingDialog.reset()
        # XXX trigger viewportMoved to update minimap after GL initialization
        # session.editorTab.currentView().viewportMoved.emit(session.editorTab.currentView())

    # --- Toolbar ---

    toolbarTextToggled = QtCore.Signal(bool)

    def toggleToolbarText(self, enable):
        if enable:
            style = Qt.ToolButtonTextUnderIcon
        else:
            style = Qt.ToolButtonIconOnly
        self.mainWindow.toolsToolBar.setToolButtonStyle(style)
        self.mainWindow.panelsToolBar.setToolButtonStyle(style)
        self.toolbarTextToggled.emit(enable)

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
        startingDir = Settings().value("open_world_dialog/starting_dir", os.path.expanduser(b"~"))
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
        self.quit()

    # --- Help Menu Actions ---

    def showAbout(self):
        from mcedit2 import __version__ as v
        credits = """<b>Supporters:</b>
<br>
<br>Saurik Works
<br>Gamer2313
<br>Andrew Devillez
<br>Alek Poyato
<br>Josh Mann
<br>NodeCraft Hosting
<br>Drew L
<br>Capt_World
<br>Adrian Brightmoore
<br>Marcel C
<br>Tim G
<br>Owen C
<br>Julian C
<br>Ausstan L
<br>Leonard P
<br>Gregory M
<br>Joseph P
<br>Lance R
<br>John B
<br>Aaron J
<br>A.M.P.
<br>Daniel B
<br>Zachary B
<br>Geoffrey C
<br>Diane W
<br>Kyle H
<br>Nathan M
<br>Ross C
<br>Thomas H
<br>Jordan S
<br>Micael L
<br>Todd A
<br>John C
<br>Elisabeth F
<br>Chris L
<br>S Spurlock
<br>Paul H
<br>Jack T
<br>
<br><b>Technologies used:</b>
<br>
<br>Python
<br>Qt
<br>PySide
<br>PyOpenGL
<br>numpy
<br>cython
<br>PyCharm
<br>
"""

        aboutBox = QtGui.QDialog(self.mainWindow)
        icon = self.windowIcon()
        iconLabel = QtGui.QLabel()
        iconLabel.setPixmap(icon.pixmap(32, 32))

        versionText = "MCEdit %s" % v
        aboutBox.setWindowTitle(versionText)
        versionLabel = QtGui.QLabel(versionText)
        copyrightLabel = QtGui.QLabel("Copyright 2014-2015 David Rio Vierra. All rights reserved.")

        okButton = QtGui.QPushButton(self.tr("OK"))
        okButton.clicked.connect(aboutBox.accept)

        creditsField = QtGui.QTextEdit()
        creditsField.setReadOnly(True)
        creditsField.setHtml(credits)

        creditsBox = QtGui.QGroupBox()
        creditsBox.setTitle("Credits")

        creditsBox.setLayout(Column(creditsField))
        aboutBox.setLayout(Column(Row(iconLabel, Column(versionLabel, copyrightLabel, None)),
                                  creditsBox,
                                  Row(None, okButton)))

        aboutBox.exec_()

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

    def showPluginsDialog(self):
        self.pluginsDialog.exec_()

    def toggleDeveloperMode(self, enable):
        if enable:
            self.mainWindow.menuBar().addAction(self.debugMenu.menuAction())
            self.mainWindow.addDockWidget(Qt.RightDockWidgetArea, self.inspectorDockWidget)
            self.mainWindow.addDockWidget(Qt.RightDockWidgetArea, self.profileDockWidget)
            self.mainWindow.addDockWidget(Qt.RightDockWidgetArea, self.textureAtlasDockWidget)
            self.mainWindow.addDockWidget(Qt.BottomDockWidgetArea, self.infoDockWidget)

        else:
            self.mainWindow.menuBar().removeAction(self.debugMenu.menuAction())
            self.mainWindow.removeDockWidget(self.inspectorDockWidget)
            self.mainWindow.removeDockWidget(self.profileDockWidget)
            self.mainWindow.removeDockWidget(self.textureAtlasDockWidget)
            self.mainWindow.removeDockWidget(self.infoDockWidget)

    # --- App foreground ---

    def event(self, event):
        """

        :type event: QtCore.QEvent
        :rtype: bool
        """
        if event.type() == QtCore.QEvent.ApplicationActivated:
            self.tryReloadPlugins()
            event.accept()
            return True

        else:
            return super(MCEditApp, self).event(event)

    def tryReloadPlugins(self):
        if not DevModeSetting.value():
            return
        
        for pluginRef in plugins.getAllPlugins():
            if pluginRef.checkTimestamps():
                log.info("Plugin %s changed. Reloading plugin module...", pluginRef.displayName)
                if not pluginRef.unload():
                    showPluginUnloadError(pluginRef)
                elif not pluginRef.load():
                    showPluginLoadError(pluginRef)
                else:
                    log.info("Plugin %s reloaded.", pluginRef.displayName)