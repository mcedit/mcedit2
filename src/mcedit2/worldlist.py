from __future__ import absolute_import, division, print_function, unicode_literals
import os
from PySide.QtCore import Qt

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

class WorldListItemWidget(QtGui.QWidget):
    doubleClicked = QtCore.Signal()

    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)

        # mapLabel = QtGui.QLabel()
        # mapLabel.setFixedSize(72, 72)
        self.displayNameLabel = QtGui.QLabel("namenamename")
        #self.lastPlayed = lastPlayedTime(worldAdapter)
        #lastPlayedText = self.lastPlayed.humanize() if self.lastPlayed else "Unknown"
        self.lastPlayedLabel = QtGui.QLabel("lastplayed")
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
        #self.setMinimumSize(layout.sizeHint())
        #self.setSizePolicy(QtGui.QSizePolicy.MinimumExpanding, QtGui.QSizePolicy.MinimumExpanding)


    def setFilename(self, filename):
        worldAdapter = findAdapter(filename, readonly=True)
        try:
            displayNameLimit = 50
            name = displayName(worldAdapter.filename)
            if len(name) > displayNameLimit:
                name = name[:displayNameLimit] + "..."

            self.displayNameLabel.setText(name)

            lastPlayed = lastPlayedTime(worldAdapter)
            lastPlayedText = lastPlayed.humanize() if lastPlayed else "Unknown"
            self.lastPlayedLabel.setText(lastPlayedText)

        except EnvironmentError as e:
            self.displayNameLabel.setText(str(e))
            self.lastPlayedLabel.setText("")


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
        style.drawPrimitive(QtGui.QStyle.PE_PanelItemViewItem, option, painter, self.parent())
        filename = index.data(Qt.DisplayRole)
        self.itemWidget.setGeometry(option.rect)
        self.itemWidget.setFilename(filename)
        self.itemWidget.render(painter,
                               painter.deviceTransform().map(option.rect.topLeft()),  # QTBUG-26694
                               renderFlags=QtGui.QWidget.DrawChildren)

    def sizeHint(self, option, index):
        return self.itemWidget.sizeHint()


class WorldListModel(QtCore.QAbstractListModel):
    def __init__(self, filenames=None):
        super(WorldListModel, self).__init__()
        if filenames is None:
            filenames = []

        self.filenames = filenames

    def rowCount(self, index):
        if index.isValid():
            return 0

        return len(self.filenames)

    def data(self, index, role=Qt.DisplayRole):
        if index.column() != 0:
            return
        row = index.row()
        if role == Qt.DisplayRole:
            return self.filenames[row]

    def flags(self, index):
        if not index.isValid():
            return 0

        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

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

        self.openWorldButton.clicked.connect(self.openWorldClicked)

        self.repairButton.clicked.connect(self.repairClicked)
        self.repairButton.setEnabled(False)
        self.backupButton.clicked.connect(self.backupClicked)
        self.backupButton.setEnabled(False)
        self.configureButton.clicked.connect(self.configureClicked)

        centerWidgetInScreen(self, 0.75)

        delegate = WorldListItemDelegate()
        self.worldListView.setItemDelegate(delegate)
        delegate.setParent(self.worldListView)  # PYSIDE-152: get the view widget to the drawPrimitive call

        self.worldListView.clicked.connect(self.worldListItemClicked)
        self.worldListView.doubleClicked.connect(self.worldListItemDoubleClicked)

        self.loadTimer = LoaderTimer(interval=0, timeout=self.loadTimerFired)
        self.loadTimer.start()

        for install in minecraftinstall.listInstalls():
            self.minecraftInstallBox.addItem(install.name)
        self.minecraftInstallBox.setCurrentIndex(minecraftinstall.selectedInstallIndex())
        self._updateVersionsAndResourcePacks()

        self.worldListModel = None
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
        try:
            if not os.path.isdir(self.saveFileDir):
                raise IOError(u"Could not find the Minecraft saves directory!\n\n({0} was not found or is not a directory)".format(self.saveFileDir))

            log.info("Scanning %s for worlds...", self.saveFileDir)
            potentialWorlds = os.listdir(self.saveFileDir)
            potentialWorlds = [os.path.join(self.saveFileDir, p) for p in potentialWorlds]
            worldFiles = [p for p in potentialWorlds if isLevel(AnvilWorldAdapter, p)]

            self.worldListModel = WorldListModel(worldFiles)
            self.worldListView.setModel(self.worldListModel)

        except EnvironmentError as e:
            setWidgetError(self, e)

    def openWorldClicked(self):
        QtGui.qApp.chooseOpenWorld()

    def worldListItemClicked(self, index):
        row = index.row()
        self.showWorld(row)

    def showWorld(self, row):
        models = {}
        try:
            worldEditor = worldeditor.WorldEditor(self.worldListModel.filenames[row], readonly=True)
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
            log.info("Removing view from WorldListWidget")
            self.worldView.textureAtlas.dispose()
            self.worldView.destroy()
            self.stackedWidget.removeWidget(self.worldView)
            self.worldView.setParent(None)
            self.worldView = None

        self.chunkLoader = None

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
        if self.worldListModel and len(self.worldListModel.filenames):
            self.showWorld(0)

    def worldListItemDoubleClicked(self, index):
        row = index.row()
        self.editWorldClicked.emit(self.worldListModel.filenames[row])
        self.accept()

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
        indexes = self.worldView.selectedIndexes()
        if len(indexes):
            return indexes[0].row()

    editWorldClicked = QtCore.Signal(unicode)
    viewWorldClicked = QtCore.Signal(unicode)
    repairWorldClicked = QtCore.Signal(unicode)
    backupWorldClicked = QtCore.Signal(unicode)

    def editClicked(self):
        index = self.selectedWorldIndex
        if index is not None:
            self.editWorldClicked.emit(self.worldListModel.filenames[index])
            self.accept()

    def viewClicked(self):
        index = self.selectedWorldIndex
        if index is not None:
            self.viewWorldClicked.emit(self.worldListModel.filenames[index])
            self.accept()

    def repairClicked(self):
        index = self.selectedWorldIndex
        if index is not None:
            self.repairWorldClicked.emit(self.worldListModel.filenames[index])
            self.accept()

    def backupClicked(self):
        index = self.selectedWorldIndex
        if index is not None:
            self.backupWorldClicked.emit(self.worldListModel.filenames[index])
            self.accept()

    def configureClicked(self):
        installsWidget = MinecraftInstallsDialog()
        installsWidget.exec_()
        self._updateVersionsAndResourcePacks()
