"""
    map
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from PySide import QtGui, QtCore
from PySide.QtCore import Qt
import numpy
from mcedit2.command import SimpleRevisionCommand
from mcedit2.ui.import_map import Ui_importMapDialog
from mcedit2.ui.panels.map import Ui_mapWidget
from mcedit2.util.resources import resourcePath
from mcedit2.util.screen import centerWidgetInScreen
from mceditlib.anvil.adapter import AnvilMapData
from mceditlib.exceptions import LevelFormatError

log = logging.getLogger(__name__)


class MapListModel(QtCore.QAbstractListModel):
    MapIDRole = Qt.UserRole

    def __init__(self, editorSession):
        super(MapListModel, self).__init__()
        self.editorSession = editorSession
        self.mapIDs = sorted(self.editorSession.worldEditor.listMaps())

    def rowCount(self, index):
        return len(self.mapIDs)

    def data(self, index, role=Qt.DisplayRole):
        row = index.row()
        if not 0 <= row < len(self.mapIDs):
            return None

        mapID = self.mapIDs[row]
        if role == Qt.DisplayRole:
            return "Map #%s" % mapID
        if role == Qt.DecorationRole:
            return self.imageForMapID(mapID)
        if role == self.MapIDRole:
            return mapID

    def getMap(self, mapID):
        return self.editorSession.worldEditor.getMap(mapID)

    def deleteMap(self, mapID):
        self.mapIDs.remove(mapID)
        self.editorSession.worldEditor.deleteMap(mapID)

    def imageForMapID(self, mapID):
        try:
            mapData = self.getMap(mapID)
        except LevelFormatError as e:
            log.exception("Invalid map for ID %s (while getting map image)", mapID)
            return None

        colorsRGBA = mapData.getColorsAsRGBA()
        colorsBGRA = rgbaToBgra(colorsRGBA)
        image = QtGui.QImage(colorsBGRA, mapData.width, mapData.height, QtGui.QImage.Format_ARGB32)
        return image

def rgbaToBgra(colors):
    return numpy.ascontiguousarray(numpy.roll(colors, 1, -1)[..., ::-1])

bgraToRgba = rgbaToBgra

class MapPanel(QtGui.QWidget, Ui_mapWidget):
    def __init__(self, editorSession):
        """

        :type editorSession: mcedit2.editorsession.EditorSession
        :rtype: MapPanel
        """
        super(MapPanel, self).__init__(QtGui.qApp.mainWindow, f=Qt.Tool)

        self.editorSession = editorSession
        self.pixmapItem = None
        self.mapListModel = None

        self.setupUi(self)

        icon = QtGui.QIcon(resourcePath("mcedit2/assets/mcedit2/icons/edit_map.png"))
        action = QtGui.QAction(icon, self.tr("Edit Maps"), self)
        action.setCheckable(True)
        action.triggered.connect(self.toggleView)
        self._toggleViewAction = action

        self.reloadModel()

        self.mapListView.clicked.connect(self.mapListClicked)

        self.splitter.splitterMoved.connect(self.updatePixmapSize)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 1)

        self.importImageButton.clicked.connect(self.importImage)

        self.deleteMapButton.clicked.connect(self.deleteMap)

        self.currentlyEditingLabel.setVisible(False)
        self.displayFirstMap()

    def displayFirstMap(self):
        if len(self.mapListModel.mapIDs):
            index = self.mapListModel.index(0, 0)
            self.mapListView.setCurrentIndex(index)
            self.displayMapID(index.data(MapListModel.MapIDRole))

    def closeEvent(self, event):
        self.toggleView()

    def toggleViewAction(self):
        return self._toggleViewAction

    def toggleView(self):
        if self.isHidden():
            centerWidgetInScreen(self, 0.8)
            self.show()
            self._toggleViewAction.setChecked(True)
        else:
            self.hide()
            self._toggleViewAction.setChecked(False)

    def mapListClicked(self, index):
        mapID = index.data(MapListModel.MapIDRole)
        self.displayMapID(mapID)

    def displayMapID(self, mapID):
        if mapID is None:
            mapData = None
        else:
            try:
                mapData = self.mapListModel.getMap(mapID)
            except LevelFormatError as e:
                log.exception("Invalid data for map ID %s (while getting map info)", mapID)
                mapData = None

        if mapData is None:
            self.widthLabel.setText("(N/A)")
            self.heightLabel.setText("(N/A)")
            self.dimensionLabel.setText("(N/A)")
            self.scaleLabel.setText("(N/A)")
            self.mapGraphicsView.setScene(None)
        else:
            self.widthLabel.setText(str(mapData.width))
            self.heightLabel.setText(str(mapData.height))
            self.dimensionLabel.setText(str(mapData.dimension))
            self.scaleLabel.setText(str(mapData.scale))
            self.updateScene(mapID)

    def updateScene(self, mapID):
        scene = QtGui.QGraphicsScene()

        image = self.mapListModel.imageForMapID(mapID)
        pixmap = QtGui.QPixmap.fromImage(image)
        self.pixmapItem = scene.addPixmap(pixmap)

        self.mapGraphicsView.setScene(scene)
        self.mapGraphicsView.fitInView(self.pixmapItem, Qt.KeepAspectRatio)

    def resizeEvent(self, event):
        self.updatePixmapSize()

    def showEvent(self, event):
        self.updatePixmapSize()

    def updatePixmapSize(self):
        if self.pixmapItem:
            self.mapGraphicsView.fitInView(self.pixmapItem, Qt.KeepAspectRatio)

    def importImage(self):
        result = QtGui.QFileDialog.getOpenFileName(self, self.tr("Choose an image file"),
                                                   ".",  # xxxxx
                                                   "Image files (*.gif;*.png;*.bmp;*.jpg)")

        if result:
            filename = result[0]
            if filename:
                colorTable = AnvilMapData.colorTable  # xxxx dispatch through WorldEditor
                dialog = ImportMapDialog(filename, colorTable)
                dialog.exec_()
                if dialog.result():
                    convertedImages = dialog.getConvertedImages()
                    command = MapImportCommand(self.editorSession, self.tr("Import Image as Map"))
                    with command.begin():
                        for x, y, image in convertedImages:
                            colors = numpy.fromstring(image.bits(), dtype=numpy.uint8)
                            colors.shape = 128, 128
                            newMap = self.editorSession.worldEditor.createMap()
                            newMap.colors[:] = colors
                            newMap.save()

                    self.reloadModel()
                    self.displayMapID(newMap.mapID)

    def deleteMap(self):
        idx = self.mapListView.currentIndex()
        if idx.isValid():
            mapID = self.mapListModel.data(idx, MapListModel.MapIDRole)
            with self.editorSession.beginSimpleCommand(self.tr("Delete Map {0}").format(mapID)):
                self.mapListModel.deleteMap(mapID)

            self.reloadModel()
            self.displayFirstMap()

    def reloadModel(self):
        self.mapListModel = MapListModel(self.editorSession)
        self.mapListView.setModel(self.mapListModel)


class MapImportCommand(SimpleRevisionCommand):
    pass


class ImportMapDialog(QtGui.QDialog, Ui_importMapDialog):
    def __init__(self, imageFilename, colorTable):
        super(ImportMapDialog, self).__init__()
        self.setupUi(self)

        self.filename = imageFilename

        # Convert to ARGB to ensure alpha channel
        image = QtGui.QImage(imageFilename)
        self.image = image.convertToFormat(QtGui.QImage.Format_ARGB32)
        self.pixmap = QtGui.QPixmap.fromImage(image)

        self.lines = []
        self.previewGroupItems = []
        self.convertedImages = []

        self.colorTable = [255] * 256
        colorTable = numpy.array(colorTable)
        colorTableBGRA = numpy.ascontiguousarray(numpy.roll(colorTable, 1, -1)[..., ::-1])
        colorTableBGRA.shape = colorTableBGRA.size
        colorTableBGRA.dtype = numpy.uint32
        self.colorTable[:len(colorTable)] = list(colorTableBGRA)

        self.importAsMosaicGroup.toggled.connect(self.updateScenes)
        self.expandImageCheckbox.toggled.connect(self.updateScenes)
        self.tilesWideSpinbox.valueChanged.connect(self.updateScenes)
        self.tilesHighSpinbox.valueChanged.connect(self.updateScenes)

        self.imageScene = QtGui.QGraphicsScene()
        self.pixmapItem = self.imageScene.addPixmap(self.pixmap)

        self.imageGraphicsView.setScene(self.imageScene)

        self.previewScene = QtGui.QGraphicsScene()
        self.previewGroup = QtGui.QGraphicsItemGroup()
        self.previewScene.addItem(self.previewGroup)
        self.previewGraphicsView.setScene(self.previewScene)

        self.updateScenes()

    def updateScenes(self):
        for lineItem in self.lines:
            self.imageScene.removeItem(lineItem)
        self.lines[:] = []

        for item in self.previewGroupItems:
            self.previewGroup.removeFromGroup(item)
        self.previewGroupItems[:] = []

        self.convertedImages[:] = []

        tilesWide = self.tilesWideSpinbox.value()
        tilesHigh = self.tilesHighSpinbox.value()

        #if self.importAsMosaicGroup.isChecked() and tilesWide > 1 or tilesHigh > 1:

        imageWidth = self.pixmap.width()
        imageHeight = self.pixmap.height()
        xSpacing = imageWidth / tilesWide
        ySpacing = imageHeight / tilesHigh
        expandImage = self.expandImageCheckbox.isChecked()
        if not expandImage:
            xSpacing = ySpacing = max(xSpacing, ySpacing)

        for x in range(1, tilesWide):
            if x * xSpacing > imageWidth:
                break
            line = QtGui.QGraphicsLineItem(x * xSpacing, 0, x * xSpacing, imageHeight)
            line.setPen(QtGui.QPen(Qt.red))
            self.imageScene.addItem(line)
            self.lines.append(line)
        for y in range(1, tilesHigh):
            if y * ySpacing > imageHeight:
                break
            line = QtGui.QGraphicsLineItem(0, y * ySpacing, imageWidth, y * ySpacing)
            line.setPen(QtGui.QPen(Qt.red))
            self.imageScene.addItem(line)
            self.lines.append(line)

        tilePositions = []
        for x in range(0, tilesWide):
            for y in range(0, tilesHigh):
                if x * xSpacing > imageWidth or y * ySpacing > imageHeight:
                    continue
                tilePositions.append((x, y))

        image = self.image

        tileSize = 128
        tileSpacing = 6
        tileOffset = tileSize + tileSpacing
        for x, y in tilePositions:
            tileImage = image.copy(x * xSpacing, y * ySpacing, xSpacing, ySpacing)
            scaledImage = tileImage.scaled(QtCore.QSize(tileSize, tileSize),
                                           Qt.KeepAspectRatio if not expandImage else Qt.IgnoreAspectRatio)
            convertedImage = scaledImage.convertToFormat(QtGui.QImage.Format_Indexed8, self.colorTable)
            convertedPixmap = QtGui.QPixmap.fromImage(convertedImage)
            self.convertedImages.append((x, y, convertedImage))

            convertedPixmapItem = QtGui.QGraphicsPixmapItem(convertedPixmap)
            convertedPixmapItem.setPos(x * tileOffset, y * tileOffset)
            self.previewGroup.addToGroup(convertedPixmapItem)
            self.previewGroupItems.append(convertedPixmapItem)

            rectItem = QtGui.QGraphicsRectItem(x*tileOffset, y*tileOffset, tileSize, tileSize)
            rectItem.setPen(QtGui.QPen(Qt.black))
            self.previewGroup.addToGroup(rectItem)
            self.previewGroupItems.append(rectItem)

        #
        # else:
        #
        #     image = self.pixmap.toImage()
        #     scaledImage = image.scaled(QtCore.QSize(128, 128), Qt.KeepAspectRatio)
        #     convertedImage = scaledImage.convertToFormat(QtGui.QImage.Format_Indexed8, self.colorTable)
        #     convertedPixmap = QtGui.QPixmap.fromImage(convertedImage)
        #     convertedPixmapItem = self.previewScene.addPixmap(convertedPixmap)
        #     self.previewGroup.addToGroup(convertedPixmapItem)
        #     self.mosaicTiles.append(convertedPixmapItem)

        self.updateImageSize()

    def updateImageSize(self):
        self.imageGraphicsView.fitInView(self.pixmapItem, Qt.KeepAspectRatio)
        self.previewGraphicsView.fitInView(self.previewGroup, Qt.KeepAspectRatio)

    def resizeEvent(self, event):
        self.updateImageSize()

    def showEvent(self, event):
        self.updateImageSize()

    def getConvertedImages(self):
        return list(self.convertedImages)
