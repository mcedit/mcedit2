from __future__ import absolute_import, division, print_function, unicode_literals
import os
import zipfile
from PySide.QtCore import Qt

from arrow import arrow
from PySide import QtGui, QtCore
from mcedit2.appsettings import RecentFilesSetting
from mcedit2.rendering.chunkloader import ChunkLoader
from mcedit2.ui.world_list import Ui_worldList
from mcedit2.util import profiler, minecraftinstall
from mcedit2.util.minecraftinstall import MinecraftInstallsDialog
from mcedit2.util.screen import centerWidgetInScreen
from mcedit2.util.settings import Settings
from mcedit2.util.worldloader import LoaderTimer

from mcedit2.widgets.layout import Column, Row, setWidgetError
from mcedit2.worldview.minimap import MinimapWorldView
from mceditlib.anvil.adapter import AnvilWorldAdapter
from mceditlib.geometry import Vector
from mceditlib.exceptions import LevelFormatError, PlayerNotFound
from mceditlib import worldeditor

import logging
from mceditlib.findadapter import isLevel
from mceditlib.nbt import NBTFormatError
from mceditlib.worldeditor import WorldEditor

log = logging.getLogger(__name__)

WorldListSettings = Settings().getNamespace('world_list')
WorldListSettings.allSavesFolders = WorldListSettings.getOption('saves_folders', 'json', [])
WorldListSettings.currentSavesFolder = WorldListSettings.getOption('current_saves_folder', unicode, '')
WorldListSettings.lastChosenSavesFolder = WorldListSettings.getOption('last_chosen_saves_folder', unicode, '')

class WorldListItemWidget(QtGui.QWidget):
    doubleClicked = QtCore.Signal()

    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)

        self.displayNameLabel = QtGui.QLabel("namenamename")
        self.lastPlayedLabel = QtGui.QLabel("lastplayed")
        self.versionInfoLabel = QtGui.QLabel("version")

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
            self.versionInfoLabel,
            #self.diskSizeLabel,
            None
        )

        layout = Row(20, infoColumn)

        self.setLayout(layout)

    def setWorldInfo(self, (name, lastPlayed, versionInfo)):
        self.displayNameLabel.setText(name)
        if lastPlayed:
            try:
                lastPlayedText = arrow.Arrow.fromtimestamp(lastPlayed / 1000.0).humanize()
            except ValueError:
                # Nonsense value for LastPlayed?
                lastPlayedText = "Unknown (Timestamp %s)" % (lastPlayed / 1000.0,)
                
            self.lastPlayedLabel.setText(lastPlayedText)
        else:
            self.lastPlayedLabel.setText("")

        if versionInfo:
            self.versionInfoLabel.setText(versionInfo)
        else:
            self.versionInfoLabel.setText("")

    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()

    def setErrorMessage(self, msg):
        self.sizeLabel.setText(msg)


class WorldListItemDelegate(QtGui.QStyledItemDelegate):
    def __init__(self):
        super(WorldListItemDelegate, self).__init__()
        self.itemWidget = WorldListItemWidget()
        self.itemWidget.adjustSize()
        log.info("Size hint: %s", str(self.itemWidget.sizeHint()))
        log.info("Size : %s", str(self.itemWidget.size()))

    def paint(self, painter, option, index):
        """

        :param painter:
        :type painter: QtGui.QPainter
        :param option:
        :type option: QtGui.QStyleOptionViewItemV4
        :param index:
        :type index:
        :return:
        :rtype:
        """
        option = QtGui.QStyleOptionViewItemV4(option)
        self.initStyleOption(option, index)
        style = QtGui.qApp.style()
        worldInfo = index.model().data(index, Qt.UserRole)
        style.drawPrimitive(QtGui.QStyle.PE_PanelItemViewItem, option, painter, self.parent())
        self.itemWidget.setGeometry(option.rect)
        self.itemWidget.setWorldInfo(worldInfo)
        self.itemWidget.render(painter,
                               painter.deviceTransform().map(option.rect.topLeft()),  # QTBUG-26694
                               renderFlags=QtGui.QWidget.DrawChildren)

    def sizeHint(self, option, index):
        return self.itemWidget.sizeHint()


class WorldListModel(QtCore.QAbstractListModel):
    WorldInfoRole = Qt.UserRole

    def __init__(self, worlds=None):
        super(WorldListModel, self).__init__()
        if worlds is None:
            worlds = []

        self.worlds = []
        for f in worlds:
            try:
                info = WorldEditor.getWorldInfo(f)
            except Exception as e:
                log.warn("Error while getting world info, skipping...", exc_info=1)
                continue
            else:
                self.worlds.append((f, info))

    def rowCount(self, index):
        if index.isValid():
            return 0

        return len(self.worlds)

    def data(self, index, role=Qt.DisplayRole):
        if index.column() != 0:
            return
        row = index.row()

        if role == Qt.DisplayRole:
            return self.worlds[row][0]
        if role == self.WorldInfoRole:
            return self.worlds[row][1]

    def flags(self, index):
        if not index.isValid():
            return 0
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable


class WorldListWidget(QtGui.QDialog, Ui_worldList):
    def __init__(self, parent=None):
        super(WorldListWidget, self).__init__(parent, f=Qt.Tool)
        self.setWindowTitle("World List")
        self.setWindowModality(Qt.NonModal)
        self.setupUi(self)

        self.worldView = None
        self.chunkLoader = None

        self.errorWidget = None
        self.blankWidget = QtGui.QWidget()
        self.stackedWidget.addWidget(self.blankWidget)

        self.editButton.clicked.connect(self.editClicked)
        self.cancelButton.clicked.connect(self.reject)
        self.showListAgainInput.setEnabled(False)

        self.viewButton.clicked.connect(self.viewClicked)

        self.openWorldButton.clicked.connect(self.openWorldClicked)

        self.repairButton.clicked.connect(self.repairClicked)
        self.repairButton.setEnabled(False)
        self.backupButton.clicked.connect(self.backupClicked)
        self.backupButton.setEnabled(False)
        self.configureButton.clicked.connect(self.configureClicked)

        self.chooseSavesFolderButton.clicked.connect(self.chooseSavesFolder)

        centerWidgetInScreen(self, 0.75)

        delegate = WorldListItemDelegate()
        self.worldListView.setItemDelegate(delegate)
        delegate.setParent(self.worldListView)  # PYSIDE-152: get the view widget to the drawPrimitive call

        self.worldListView.clicked.connect(self.worldListItemClicked)
        self.worldListView.doubleClicked.connect(self.worldListItemDoubleClicked)

        self.loadTimer = LoaderTimer(interval=0, timeout=self.loadTimerFired)
        self.loadTimer.start()

        self._updateInstalls()

        try:
            savesFolders = WorldListSettings.allSavesFolders.value()
            for filename in savesFolders:
                if not os.path.isdir(filename):
                    continue
                dirname, basename = os.path.split(filename)
                displayName = os.sep.join(dirname.split(os.sep)[-2:] + [basename])
                self.savesFolderComboBox.addItem(displayName, filename)
        except (ValueError, KeyError) as e:
            log.warn("Failed to load saves folder list.")

        currentFolder = WorldListSettings.currentSavesFolder.value()
        if os.path.isdir(currentFolder):
            index = self.savesFolderComboBox.findData(currentFolder)
            if index != -1:
                self.savesFolderComboBox.setCurrentIndex(index)

        self.savesFolderComboBox.currentIndexChanged.connect(self.savesFolderChanged)
        self.minecraftInstallBox.currentIndexChanged.connect(self.currentInstallChanged)
        self.minecraftVersionBox.currentIndexChanged[str].connect(minecraftinstall.currentVersionOption.setValue)
        self.resourcePackBox.currentIndexChanged.connect(self.resourcePackChanged)
        self.worldListModel = None
        self.reloadList()
        self.reloadRecentWorlds()

    def currentInstallChanged(self, index):
        path = self.minecraftInstallBox.itemData(index)
        minecraftinstall.currentInstallOption.setValue(path)

    def resourcePackChanged(self, index):
        if index == 0:
            minecraftinstall.currentResourcePackOption.setValue("")
        else:
            minecraftinstall.currentResourcePackOption.setValue(self.resourcePackBox.currentText())

    def _updateInstalls(self):
        self.minecraftInstallBox.clear()

        for install in minecraftinstall.GetInstalls().installs:
            self.minecraftInstallBox.addItem(install.name, install.path)
            for saveDir in install.getSaveDirs():
                self.savesFolderComboBox.addItem(install.name + os.sep + os.path.basename(saveDir), saveDir)

        for instance in minecraftinstall.GetInstalls().instances:
            saveDir = instance.saveFileDir
            self.savesFolderComboBox.addItem(instance.name + os.sep + os.path.basename(saveDir), saveDir)

        path = minecraftinstall.GetInstalls().selectedInstallPath()
        index = self.minecraftInstallBox.findData(path)
        self.minecraftInstallBox.setCurrentIndex(index)

        self._updateVersionsAndResourcePacks()

    def _updateVersionsAndResourcePacks(self):
        self.minecraftVersionBox.clear()
        self.resourcePackBox.clear()
        self.resourcePackBox.addItem(self.tr("(No resource pack)"))

        path = minecraftinstall.currentInstallOption.value()
        install = minecraftinstall.GetInstalls().getInstall(path)

        if install:
            for version in sorted(install.versions, reverse=True):
                self.minecraftVersionBox.addItem(version)

            for resourcePack in sorted(install.resourcePacks):
                self.resourcePackBox.addItem(resourcePack)

    def chooseSavesFolder(self):
        startingDir = WorldListSettings.lastChosenSavesFolder.value()
        if startingDir == '' or not os.path.isdir(startingDir):
            startingDir = os.path.expanduser(b"~")

        filename = QtGui.QFileDialog.getExistingDirectory(
            self, self.tr("Choose Saves Folder"), startingDir
        )

        if filename:
            log.info("Adding saves folder %s", filename)

            savesFolders = WorldListSettings.allSavesFolders.value()
            savesFolders.append(filename)
            WorldListSettings.allSavesFolders.setValue(savesFolders)

            dirname, basename = os.path.split(filename)
            displayName = os.sep.join(dirname.split(os.sep)[-2:] + [basename])
            WorldListSettings.lastChosenSavesFolder.setValue(filename)
            self.savesFolderComboBox.addItem(displayName, filename)
            self.savesFolderComboBox.setCurrentIndex(self.savesFolderComboBox.count()-1)

    def reloadRecentWorlds(self):
        recentWorlds = RecentFilesSetting.value()
        self.recentWorldsMenu = QtGui.QMenu()

        def _triggered(f):
            def triggered():
                self.accept()
                self.editWorldClicked.emit(f)
            return triggered
        dead = []
        for filename in recentWorlds:
            if not os.path.exists(filename):
                dead.append(filename)
                continue
            try:
                displayName, lastPlayed, versionInfo = WorldEditor.getWorldInfo(filename)
                action = self.recentWorldsMenu.addAction(displayName)
                action._editWorld = _triggered(filename)
                action.triggered.connect(action._editWorld)
            except EnvironmentError as e:
                log.exception("Failed to load world info")

        if len(dead):
            for f in dead:
                recentWorlds.remove(f)
            RecentFilesSetting.setValue(recentWorlds)

        self.recentWorldsButton.setMenu(self.recentWorldsMenu)

    def savesFolderChanged(self):
        currentFolder = self.savesFolderComboBox.itemData(self.savesFolderComboBox.currentIndex())
        WorldListSettings.currentSavesFolder.setValue(currentFolder)
        
        self.reloadList()
        if len(self.worldListModel.worlds):
            self.worldListView.setFocus()
            self.worldListView.setCurrentIndex(self.worldListModel.createIndex(0, 0))
            self.showWorld(self.worldListModel.worlds[0][0])
        else:
            self.removeWorldView()

    def reloadList(self):
        try:
            saveFileDir = self.savesFolderComboBox.itemData(self.savesFolderComboBox.currentIndex())
            if saveFileDir is None:
                log.error("No item selected in savesFolderComboBox!!(?)")
                return
            if not os.path.isdir(saveFileDir):
                raise IOError(u"Could not find the Minecraft saves directory!\n\n({0} was not found or is not a directory)".format(saveFileDir))

            log.info("Scanning %s for worlds...", saveFileDir)
            potentialWorlds = os.listdir(saveFileDir)
            potentialWorlds = [os.path.join(saveFileDir, p) for p in potentialWorlds]
            worldFiles = [p for p in potentialWorlds if isLevel(AnvilWorldAdapter, p)]

            self.worldListModel = WorldListModel(worldFiles)
            self.worldListView.setModel(self.worldListModel)

        except Exception as e:
            setWidgetError(self, e, "An error occurred while scanning the saves folder.")

    def openWorldClicked(self):
        QtGui.qApp.chooseOpenWorld()

    _currentFilename = None

    def worldListItemClicked(self, index):
        filename = index.data()
        self.showWorld(filename)

    def worldListItemDoubleClicked(self, index):
        row = index.row()
        self.accept()
        self.editWorldClicked.emit(self.worldListModel.worlds[row][0])

    def showWorld(self, filename):
        if filename == self._currentFilename:
            return
        self._currentFilename = filename

        self.removeWorldView()

        try:
            worldEditor = worldeditor.WorldEditor(filename, readonly=True)

        except Exception as e:
            self.errorWidget = QtGui.QWidget()
            setWidgetError(self.errorWidget, e, "An error occurred while reading the file %s. This file might not be a Minecraft world. If it is, please file a bug report." % filename)
            self.stackedWidget.addWidget(self.errorWidget)
            self.stackedWidget.setCurrentWidget(self.errorWidget)

        else:

            dim = worldEditor.getDimension()
            self.setWorldView(MinimapWorldView(dim))
            self.chunkLoader = ChunkLoader(dim)
            self.chunkLoader.addClient(self.worldView)
            self.chunkLoader.chunkCompleted.connect(self.worldView.update)

            try:
                try:
                    player = worldEditor.getPlayer()
                    log.info("Centering on single-player player.")
                except (PlayerNotFound, NBTFormatError):
                    try:
                        center = worldEditor.getWorldMetadata().Spawn
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
            except Exception as e:
                log.exception("Error while centering view in world list: %s", e)

            log.info("Switched world view")

    def setWorldView(self, worldView):
        if self.worldView:
            self.removeWorldView()
        self.worldView = worldView
        self.stackedWidget.addWidget(worldView)
        self.stackedWidget.setCurrentWidget(worldView)

    def removeWorldView(self):
        self.stackedWidget.setCurrentWidget(self.blankWidget)
        QtGui.qApp.processEvents()  # force repaint of stackedWidget to hide old error widget
        if self.worldView:
            log.info("Removing view from WorldListWidget")
            self.worldView.dealloc()
            self.stackedWidget.removeWidget(self.worldView)
            self.worldView.setParent(None)
            self.worldView = None
        if self.errorWidget:
            self.stackedWidget.removeWidget(self.errorWidget)
            self.errorWidget = None

        self.chunkLoader = None

        # ensure WorldView gets freed now and not later
        # if it is freed later, it will call makeCurrent and ruin another view's render
        import gc; gc.collect()

    def hide(self):
        self.removeWorldView()
        super(WorldListWidget, self).hide()

    def close(self):
        self.removeWorldView()
        super(WorldListWidget, self).close()

    def reject(self):
        self.removeWorldView()
        super(WorldListWidget, self).reject()

    def showEvent(self, event):
        if self.worldListModel and len(self.worldListModel.worlds):
            self.worldListView.setFocus()
            self.worldListView.setCurrentIndex(self.worldListModel.createIndex(0, 0))
            self.showWorld(self.worldListModel.worlds[0][0])

        self.reloadRecentWorlds()

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

    @property
    def selectedWorldIndex(self):
        indexes = self.worldListView.selectedIndexes()
        if len(indexes):
            return indexes[0]

    editWorldClicked = QtCore.Signal(unicode)
    viewWorldClicked = QtCore.Signal(unicode)
    repairWorldClicked = QtCore.Signal(unicode)
    backupWorldClicked = QtCore.Signal(unicode)

    def editClicked(self):
        index = self.selectedWorldIndex
        if index is not None:
            self.editWorldClicked.emit(index.data(Qt.DisplayRole))
            self.accept()

    def viewClicked(self):
        index = self.selectedWorldIndex
        if index is not None:
            self.viewWorldClicked.emit(index.data(Qt.DisplayRole))
            self.accept()

    def repairClicked(self):
        index = self.selectedWorldIndex
        if index is not None:
            self.repairWorldClicked.emit(index.data(Qt.DisplayRole))
            self.accept()

    def backupClicked(self):
        index = self.selectedWorldIndex
        if index is not None:
            self.backupWorldClicked.emit(index.data(Qt.DisplayRole))
            self.accept()

    def configureClicked(self):
        installsWidget = MinecraftInstallsDialog()
        installsWidget.exec_()
        self._updateInstalls()
