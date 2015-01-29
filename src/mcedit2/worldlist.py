from __future__ import absolute_import, division, print_function, unicode_literals
import os

from arrow import arrow
from PySide import QtGui, QtCore
from mcedit2.rendering import blockmeshes
from mcedit2.rendering.blockmodels import BlockModels
from mcedit2.rendering.chunkloader import ChunkLoader
from mcedit2.rendering.textureatlas import TextureAtlas
from mcedit2.util import profiler, minecraftinstall
from mcedit2.util.load_ui import load_ui
from mcedit2.util.minecraftinstall import MinecraftInstallsDialog
from mcedit2.util.screen import centerWidgetInScreen
from mcedit2.util.worldloader import LoaderTimer

from mcedit2.widgets.layout import Column, Row, setWidgetError
from mcedit2.worldview.minimap import MinimapWorldView
from mceditlib.anvil.adapter import AnvilWorldAdapter
from mceditlib.geometry import Vector
from mceditlib.exceptions import LevelFormatError, PlayerNotFound
from mceditlib import worldeditor

import logging
from mceditlib.findadapter import isLevel, findAdapter
from mceditlib.util import displayName

log = logging.getLogger(__name__)

def lastPlayedTime(adapter):
    try:
        time = adapter.metadata.LastPlayed
        dt = arrow.Arrow.fromtimestamp(time / 1000.0)
        return dt
    except AttributeError as e:
        return None

def usefulFilename(adapter):
    if hasattr(adapter, 'worldFolder'):
        return os.path.basename(adapter.worldFolder.filename)
    else:
        return os.path.basename(adapter.filename)

class WorldListItemWidget(QtGui.QPushButton):
    doubleClicked = QtCore.Signal()

    def __init__(self, worldAdapter, parent=None):
        QtGui.QPushButton.__init__(self, parent)
        self.filename = worldAdapter.filename
        self.setCheckable(True)
        self.setFlat(True)

        try:
            # mapLabel = QtGui.QLabel()
            # mapLabel.setFixedSize(72, 72)
            displayNameLimit = 50
            name = displayName(worldAdapter.filename)
            if len(name) > displayNameLimit:
                name = name[:displayNameLimit] + "..."
            self.displayNameLabel = QtGui.QLabel(name)
            self.lastPlayed = lastPlayedTime(worldAdapter)
            lastPlayedText = self.lastPlayed.humanize() if self.lastPlayed else "Unknown"
            self.lastPlayedLabel = QtGui.QLabel(lastPlayedText)
            #self.sizeLabel = QtGui.QLabel(self.tr("Calculating area..."))
            # areaText = self.tr("%.02f million square meters") % (world.chunkCount * 0.25)
            # diskSize = 0
            # if hasattr(worldAdapter, 'worldFolder'):
            #     folder = worldAdapter.worldFolder
            #     for rf in folder.findRegionFiles():
            #         diskSize += os.stat(rf).st_size
            # else:
            #     diskSize = os.stat(worldAdapter.filename).st_size
            #
            # self.diskSizeLabel = QtGui.QLabel(self.tr("%0.2f MB") % (diskSize / 1000000.0))

            infoColumn = Column(
                self.displayNameLabel,
                self.lastPlayedLabel,
                #self.diskSizeLabel,
                None
            )

            #layout = Row(mapLabel, (infoColumn, 1), None)
            layout = infoColumn
            #if usefulFilename(world) == world.displayName:
            #    boxLabelText = world.displayName
            #else:
            #    boxLabelText = self.tr("%s (%s)" % (world.displayName, usefulFilename(world)))

            self.setLayout(layout)
            self.setMinimumSize(layout.sizeHint())
            self.setSizePolicy(QtGui.QSizePolicy.MinimumExpanding, QtGui.QSizePolicy.MinimumExpanding)

        except EnvironmentError as e:
            setWidgetError(self, e)

    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()

    def setErrorMessage(self, msg):
        self.sizeLabel.setText(msg)


class WorldListWidget(QtGui.QDialog):
    def __init__(self, parent=None, f=0):
        super(WorldListWidget, self).__init__(parent, f)
        self.setWindowTitle("World List")

        self.saveFileDir = None
        self.worldView = None
        self.chunkLoader = None

        self.errorWidget = QtGui.QWidget()

        load_ui('world_list.ui', baseinstance=self)

        self.setLayout(Row(self))

        self.editButton.clicked.connect(self.editClicked)
        self.cancelButton.clicked.connect(self.reject)
        self.showListAgainInput.setEnabled(False)

        self.viewButton.clicked.connect(self.viewClicked)
        self.viewButton.setEnabled(False)

        self.repairButton.clicked.connect(self.repairClicked)
        self.repairButton.setEnabled(False)
        self.backupButton.clicked.connect(self.backupClicked)
        self.backupButton.setEnabled(False)
        self.configureButton.clicked.connect(self.configureClicked)

        centerWidgetInScreen(self)

        self.loadTimer = LoaderTimer(interval=0, timeout=self.loadTimerFired)
        self.loadTimer.start()

        for install in minecraftinstall.listInstalls():
            self.minecraftInstallBox.addItem(install.name)
        self.minecraftInstallBox.setCurrentIndex(minecraftinstall.selectedInstallIndex())
        self._updateVersionsAndResourcePacks()
        self.reloadList()

    def _updateVersionsAndResourcePacks(self):
        install = minecraftinstall.getInstall(self.minecraftInstallBox.currentIndex())
        for version in sorted(install.versions, reverse=True):
            self.minecraftVersionBox.addItem(version)
        self.resourcePackBox.addItem(self.tr("(No resource pack)"))
        for resourcePack in sorted(install.resourcePacks):
            self.resourcePackBox.addItem(resourcePack)
        self.saveFileDir = install.getSaveFileDir()

    def getSelectedIVP(self):
        i = self.minecraftInstallBox.currentIndex()
        install = minecraftinstall.getInstall(i)
        v = self.minecraftVersionBox.currentText()
        if self.resourcePackBox.currentIndex() > 0:
            p = self.resourcePackBox.currentText()
        else:
            p = None
        return install, v, p

    def reloadList(self):
        self.selectedWorldIndex = -1

        self.itemWidgets = []

        try:
            if not os.path.isdir(self.saveFileDir):
                raise IOError(u"Could not find the Minecraft saves directory!\n\n({0} was not found or is not a directory)".format(self.saveFileDir))

            log.info("Scanning %s for worlds...", self.saveFileDir)
            potentialWorlds = os.listdir(self.saveFileDir)
            potentialWorlds = [os.path.join(self.saveFileDir, p) for p in potentialWorlds]
            worldFiles = [p for p in potentialWorlds if isLevel(AnvilWorldAdapter, p)]
            worldAdapters = []
            for f in worldFiles:
                try:
                    adapter = findAdapter(f, readonly=True)
                except Exception as e:
                    log.exception("Could not find adapter for %s: %r", f, e)
                    continue
                else:
                    worldAdapters.append(adapter)

            if len(worldAdapters) == 0:
                raise IOError("No worlds found! You should probably play Minecraft to create your first world.")

            column = QtGui.QVBoxLayout()
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(0)

            worldGroup = QtGui.QButtonGroup(self)
            #worldGroup.setExclusive(True)

            for adapter in worldAdapters:
                item = WorldListItemWidget(adapter)
                self.itemWidgets.append(item)

            self.itemWidgets.sort(key=lambda i: i.lastPlayed, reverse=True)

            for i, item in enumerate(self.itemWidgets):
                worldGroup.addButton(item, i)
                column.addWidget(item)
                item.doubleClicked.connect(self.worldListItemDoubleClicked)

            worldGroup.buttonClicked[int].connect(self.worldListItemClicked)

            self.scrollAreaWidgetContents.setLayout(column)

        except EnvironmentError as e:
            setWidgetError(self, e)

    def worldListItemClicked(self, i):
        if self.selectedWorldIndex == i:
            return
        self.selectedWorldIndex = i
        import gc; gc.collect()
        models = {}
        try:
            worldEditor = worldeditor.WorldEditor(self.itemWidgets[i].filename, readonly=True)
        except (EnvironmentError, LevelFormatError) as e:
            setWidgetError(self.errorWidget, e)
            while self.stackedWidget.count():
                self.stackedWidget.removeWidget(self.stackedWidget.widget(0))

            self.worldViewBox.addWidget(self.errorWidget)
        else:
            i, v, p = self.getSelectedIVP()
            blockModels = models.get(worldEditor.blocktypes)
            resLoader = i.getResourceLoader(v, p)
            if blockModels is None:
                models[worldEditor.blocktypes] = blockModels = BlockModels(worldEditor.blocktypes, resLoader)
            textureAtlas = TextureAtlas(worldEditor, resLoader, blockModels)

            dim = worldEditor.getDimension()
            self.setWorldView(MinimapWorldView(dim, textureAtlas))
            self.chunkLoader = ChunkLoader(dim)
            self.chunkLoader.addClient(self.worldView)
            self.chunkLoader.chunkCompleted.connect(self.worldView.update)

            try:
                player = worldEditor.getPlayer()
                log.info("Centering on single-player player.")
            except PlayerNotFound:
                try:
                    center = worldEditor.worldSpawnPosition()
                    log.info("Centering on spawn position.")
                except AttributeError:
                    log.info("Centering on world center")
                    center = dim.bounds.origin + (dim.bounds.size * 0.5)
            else:
                if player.dimName == dim.dimName:
                    center = Vector(*player.Position)
                    self.worldView.centerOnPoint(center)
                else:
                    center = dim.bounds.origin + (dim.bounds.size * 0.5)

            self.worldView.centerOnPoint(center)
            log.info("Switched world view")

    def setWorldView(self, worldView):
        if self.worldView:
            self.removeWorldView()
        self.worldView = worldView
        self.stackedWidget.addWidget(worldView)

    def removeWorldView(self):
        if self.worldView:
            self.worldView.textureAtlas.dispose()
            self.worldView.destroy()
            self.worldView.setParent(None)
            self.stackedWidget.removeWidget(self.worldView)
            self.worldView = None

        self.chunkLoader = None

    def closeEvent(self, event):
        self.removeWorldView()
        self.selectedWorldIndex = -1
        #import gc; gc.collect()

    def showEvent(self, event):
        if len(self.itemWidgets):
            self.itemWidgets[0].click()

    def worldListItemDoubleClicked(self):
        self.editClicked()

    @profiler.function("worldListLoadTimer")
    def loadTimerFired(self):
        if not self.isVisible():
            self.loadTimer.setInterval(1000)
            return

        if self.chunkLoader:
            try:
                self.chunkLoader.next()
                self.loadTimer.setInterval(0)
            except StopIteration:
                self.loadTimer.setInterval(1000)
        else:
            self.loadTimer.setInterval(1000)

    editWorldClicked = QtCore.Signal(unicode)
    viewWorldClicked = QtCore.Signal(unicode)
    repairWorldClicked = QtCore.Signal(unicode)
    backupWorldClicked = QtCore.Signal(unicode)

    def editClicked(self):
        self.editWorldClicked.emit(self.itemWidgets[self.selectedWorldIndex].filename)
        self.accept()

    def viewClicked(self):
        self.viewWorldClicked.emit(self.itemWidgets[self.selectedWorldIndex].filename)
        self.accept()

    def repairClicked(self):
        self.repairWorldClicked.emit(self.itemWidgets[self.selectedWorldIndex].filename)
        self.accept()

    def backupClicked(self):
        self.backupWorldClicked.emit(self.itemWidgets[self.selectedWorldIndex].filename)
        self.accept()

    def configureClicked(self):
        installsWidget = MinecraftInstallsDialog()
        installsWidget.exec_()
        self._updateVersionsAndResourcePacks()
