"""
    brush
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import os

from PySide import QtGui, QtCore
import numpy

from mcedit2.editortools import EditorTool
from mcedit2.command import SimplePerformCommand
from mcedit2.rendering import worldscene, scenegraph
from mcedit2.rendering.depths import DepthOffset
from mcedit2.util.load_ui import load_ui, registerCustomWidget
from mcedit2.util.resources import resourcePath
from mcedit2.util.settings import Settings
from mcedit2.util.showprogress import showProgress
from mcedit2.util.worldloader import WorldLoader
from mcedit2.widgets import flowlayout
from mceditlib.geometry import BoundingBox, Vector
from mceditlib.util import exhaust


log = logging.getLogger(__name__)

BrushModeSetting = Settings().getOption("editortools/brush/mode")
BrushShapeSetting = Settings().getOption("editortools/brush/shape")
BrushSizeSetting = Settings().getOption("editortools/brush/size")

class BrushCommand(SimplePerformCommand):
    def __init__(self, editorSession, points, options):
        """

        :type editorSession: mcedit2.editorsession.EditorSession
        :type points: list
        :type options: dict
        :return:
        :rtype:
        """
        super(BrushCommand, self).__init__(editorSession)
        # if options is None: options = {}

        self.options = options

        self.points = points

        self.brushSize = options['brushSize']
        self.blockInfo = options['blockInfo']
        self.brushStyle = options['brushStyle']
        self.brushMode = options['brushMode']
        self.setText("%s %s Brush" % (self.brushMode.name, self.brushStyle.ID))

        if max(self.brushSize) > BrushTool.maxBrushSize:
            self.brushSize = (BrushTool.maxBrushSize,) * 3
        if max(self.brushSize) < 1:
            self.brushSize = (1, 1, 1)

    @property
    def noise(self):
        return self.options.get('brushNoise', 100)

    @property
    def hollow(self):
        return self.options.get('brushHollow', False)

    def brushBoxForPoint(self, point):
        return self.brushMode.brushBoundingBox(point, self.options)

    def perform(self):
        if len(self.points) > 10:
            showProgress("Performing brush...", self._perform(), cancel=True)
        else:
            exhaust(self._perform())

    def _perform(self):
        yield 0, len(self.points), "Applying {0} brush...".format(self.brushMode.name)
        try:
            #xxx combine selections
            selections = [BrushSelection(self.brushBoxForPoint(point), self.brushStyle) for point in self.points]
            self.brushMode.applyToSelections(self, selections)
        except NotImplementedError:
            for i, point in enumerate(self.points):
                f = self.brushMode.applyToPoint(self, point)
                if hasattr(f, "__iter__"):
                    for progress in f:
                        yield progress
                else:
                    yield i, len(self.points), "Applying {0} brush...".format(self.brushMode.name)

        self.performed = True


class BrushMode(object):
    options = []

    def brushBoundingBox(self, center, options={}):
        # Return a box of size options['brushSize'] centered around point.
        # also used to position the preview cursor
        size = options['brushSize']
        x, y, z = size
        origin = Vector(*center) - (Vector(x, y, z) / 2) + Vector((x % 2) * 0.5, (y % 2) * 0.5, (z % 2) * 0.5)
        return BoundingBox(origin, size)

    def applyToPoint(self, command, point):
        """
        Called by BrushCommand for brush modes that can't be implemented using applyToChunk
        :type point: Vector
        :type command: BrushCommand
        """
        raise NotImplementedError


    def applyToSelections(self, command, selections):
        """
        Called by BrushCommand to apply this brush mode to the given selection. Selection is generated
        by calling
        """
        raise NotImplementedError


    def applyToChunkSlices(self, op, chunk, slices, brushBox, brushBoxThisChunk):
        raise NotImplementedError

    def createOptionsPanel(self, tool):
        pass


class Fill(BrushMode):
    name = "Fill"
    #
    #def createOptions(self, panel, tool):
    #    col = [
    #        panel.modeStyleGrid,
    #        panel.hollowRow,
    #        panel.noiseInput,
    #        panel.brushSizeRows,
    #        panel.blockButton,
    #    ]
    #    return col

    def applyToSelections(self, command, selections):
        """

        :type command: BrushCommand
        """
        fill = command.editorSession.currentDimension.fillBlocksIter(selections[0], command.blockInfo)
        showProgress("Applying brush...", fill)

class BrushModes(object):
    allModes = (Fill(),)


class BrushSelection(BoundingBox):
    def __init__(self, box, style, chance=100, hollow=False):
        """


        :type style: Style
        :type box: BoundingBox
        """
        super(BrushSelection, self).__init__(box.origin, box.size)
        self.style = style
        self.chance = chance
        self.hollow = hollow

    def box_mask(self, box):
        return createBrushMask(self, self.style, box, self.chance, self.hollow)


def createBrushMask(brushBox, style, requestedBox, chance=100, hollow=False):
    """
    Return a boolean array for a brush with the given shape and style.
    If 'offset' and 'box' are given, then the brush is offset into the world
    and only the part of the world contained in box is returned as an array
    """

    origin, shape = brushBox.origin, brushBox.size

    if chance < 100 or hollow:
        requestedBox = requestedBox.expand(1)

    # we are returning indices for a Blocks array, so swap axes to YZX
    outputShape = requestedBox.size
    outputShape = (outputShape[1], outputShape[2], outputShape[0])

    shape = shape[1], shape[2], shape[0]
    origin = numpy.array(origin) - numpy.array(requestedBox.origin)
    origin = origin[[1, 2, 0]]

    inds = numpy.indices(outputShape, dtype=numpy.float32)
    halfshape = numpy.array([(i >> 1) - ((i & 1 == 0) and 0.5 or 0) for i in shape])

    blockCenters = inds - halfshape[:, None, None, None]
    blockCenters -= origin[:, None, None, None]

    # odd diameter means measure from the center of the block at 0,0,0 to each block center
    # even diameter means measure from the 0,0,0 grid point to each block center

    # if diameter & 1 == 0: blockCenters += 0.5
    shape = numpy.array(shape, dtype='float32')

    mask = style.maskFromCoords(blockCenters, shape)

    if (chance < 100 or hollow) and max(shape) > 1:
        threshold = chance / 100.0
        exposedBlockMask = numpy.ones(shape=outputShape, dtype='bool')
        exposedBlockMask[:] = mask
        submask = mask[1:-1, 1:-1, 1:-1]
        exposedBlockSubMask = exposedBlockMask[1:-1, 1:-1, 1:-1]
        exposedBlockSubMask[:] = False

        for dim in (0, 1, 2):
            slices = [slice(1, -1), slice(1, -1), slice(1, -1)]
            slices[dim] = slice(None, -2)
            exposedBlockSubMask |= (submask & (mask[slices] != submask))
            slices[dim] = slice(2, None)
            exposedBlockSubMask |= (submask & (mask[slices] != submask))

        if hollow:
            mask[~exposedBlockMask] = False
        if chance < 100:
            rmask = numpy.random.random(mask.shape) < threshold

            mask[exposedBlockMask] = rmask[exposedBlockMask]

    if chance < 100 or hollow:
        return mask[1:-1, 1:-1, 1:-1]
    else:
        return mask


class Style(object):
    pass


class Round(Style):
    ID = "Round"
    icon = "brush_round.png"

    def maskFromCoords(self, blockCenters, shape):
        blockCenters *= blockCenters
        shape /= 2
        shape *= shape

        blockCenters /= shape[:, None, None, None]
        distances = sum(blockCenters, 0)
        return distances < 1


class Square(Style):
    ID = "Square"
    icon = "brush_square.png"

    def maskFromCoords(self, blockCenters, shape):
        blockCenters /= shape[:, None, None, None]  # XXXXXX USING DIVIDE FOR A RECTANGLE

        distances = numpy.absolute(blockCenters).max(0)
        return distances < .5


class Diamond(Style):
    ID = "Diamond"
    icon = "brush_diamond.png"

    def maskFromCoords(self, blockCenters, shape):
        blockCenters = numpy.abs(blockCenters)
        shape /= 2
        blockCenters /= shape[:, None, None, None]
        distances = numpy.sum(blockCenters, 0)
        return distances < 1


class BrushStyles(object):
    allStyles = (Round(), Square(), Diamond())


NULL_ID = 255  # xxx


class MaskLevel(object):
    def __init__(self, selection, fillBlock, blocktypes):
        """
        Level emulator to be used for rendering brushes and selections.

        :type selection: BrushSelection
        :param selection:
        :param fillBlock:
        :param blocktypes:
        """
        self.bounds = self.selection = selection

        self.blocktypes = blocktypes
        self.sectionCache = {}
        self.fillBlock = fillBlock
        self.filename = "Temporary Level (%s %s %s)" % (selection, fillBlock, blocktypes)

    def chunkPositions(self):
        return self.bounds.chunkPositions()

    def getChunk(self, cx, cz, create=False):
        return FakeBrushChunk(self, cx, cz)

    def containsChunk(self, cx, cz):
        return self.bounds.containsChunk(cx, cz)

class FakeBrushSection(object):
    BlockLight = numpy.empty((16, 16, 16), dtype=numpy.uint8)
    BlockLight[:] = 15
    SkyLight = numpy.empty((16, 16, 16), dtype=numpy.uint8)
    SkyLight[:] = 15
    pass

class FakeBrushChunk(object):
    Entities = ()
    TileEntities = ()

    def __init__(self, world, cx, cz):
        """

        :type world: MaskLevel
        """
        self.dimension = world
        self.cx = cx
        self.cz = cz

    @property
    def blocktypes(self):
        return self.dimension.blocktypes

    @property
    def chunkPosition(self):
        return self.cx, self.cz

    def sectionPositions(self):
        return self.dimension.selection.sectionPositions(self.cx, self.cz)

    @property
    def bounds(self):
        return BoundingBox((self.cx << 4, self.dimension.bounds.miny, self.cz << 4),
                           (16, self.dimension.bounds.height, 16))


    _sentinel = object()

    def getSection(self, y, create=False):
        selection = self.dimension.selection
        sectionCache = self.dimension.sectionCache
        fillBlock = self.dimension.fillBlock
        cx, cz = self.chunkPosition

        section = sectionCache.get((cx, y, cz), self._sentinel)
        if section is self._sentinel:
            mask = selection.section_mask(cx, y, cz)
            if mask is None:
                sectionCache[cx, y, cz] = None
                return None

            section = FakeBrushSection()
            section.Y = y
            if fillBlock.ID:
                section.Blocks = numpy.array([0, fillBlock.ID])[mask.astype(numpy.uint8)]
                section.Data = numpy.array([0, fillBlock.meta])[mask.astype(numpy.uint8)]
            else:
                section.Blocks = numpy.array([0, NULL_ID])[mask.astype(numpy.uint8)]

            sectionCache[cx, y, cz] = section

        return section


class BrushTool(EditorTool):
    name = "Brush"
    iconName = "brush"
    maxBrushSize = 512

    def __init__(self, editorSession, *args, **kwargs):
        super(BrushTool, self).__init__(editorSession, *args, **kwargs)
        self.toolWidget = load_ui("editortools/brush.ui")

        self.cursorWorldScene = None
        self.cursorNode = scenegraph.TranslateNode()

        self.toolWidget.xSpinBox.valueChanged.connect(self.setX)
        self.toolWidget.ySpinBox.valueChanged.connect(self.setY)
        self.toolWidget.zSpinBox.valueChanged.connect(self.setZ)

        self.toolWidget.xSlider.valueChanged.connect(self.setX)
        self.toolWidget.ySlider.valueChanged.connect(self.setY)
        self.toolWidget.zSlider.valueChanged.connect(self.setZ)

        self.toolWidget.blockTypeInput.editorSession = editorSession
        self.toolWidget.blockTypeInput.block = editorSession.worldEditor.blocktypes["minecraft:stone"]
        self.toolWidget.blockTypeInput.blocksChanged.connect(self.setBlocktypes)

        self.toolWidget.brushShapeInput.shapeChanged.connect(self.updateCursor)

        self.fillBlock = editorSession.worldEditor.blocktypes["stone"]

        self.brushSize = BrushSizeSetting.value(QtGui.QVector3D(5, 5, 5)).toTuple()  # calls updateCursor

        self.toolWidget.xSpinBox.setValue(self.brushSize[0])
        self.toolWidget.ySpinBox.setValue(self.brushSize[1])
        self.toolWidget.zSpinBox.setValue(self.brushSize[2])

    _brushSize = (0, 0, 0)
    @property
    def brushSize(self):
        return self._brushSize

    @brushSize.setter
    def brushSize(self, value):
        self._brushSize = value
        BrushSizeSetting.setValue(QtGui.QVector3D(*self.brushSize))
        self.updateCursor()

    def setX(self, val):
        x, y, z = self.brushSize
        x = float(val)
        self.brushSize = x, y, z
        self.toolWidget.xSlider.setValue(val)
        self.toolWidget.xSpinBox.setValue(val)

    def setY(self, val):
        x, y, z = self.brushSize
        y = float(val)
        self.brushSize = x, y, z
        self.toolWidget.ySlider.setValue(val)
        self.toolWidget.ySpinBox.setValue(val)

    def setZ(self, val):
        x, y, z = self.brushSize
        z = float(val)
        self.brushSize = x, y, z
        self.toolWidget.zSlider.setValue(val)
        self.toolWidget.zSpinBox.setValue(val)

    def setBlocktypes(self, types):
        if len(types) == 0:
            return

        self.fillBlock = types[0]
        self.updateCursor()

    def mousePress(self, event):
        pos = event.blockPosition
        pos += event.blockFace.vector
        command = BrushCommand(self.editorSession, [pos], self.options)
        self.editorSession.pushCommand(command)

    def mouseMove(self, event):
        #box = self.brushBoxForPoint(event.blockPosition)
        if event.blockPosition:
            self.cursorNode.translateOffset = event.blockPosition + event.blockFace.vector


    @property
    def options(self):
        return {'brushSize': self.brushSize,
                'blockInfo': self.fillBlock,
                'brushStyle': self.brushStyle,
                'brushMode': self.brushMode}

    @property
    def brushMode(self):
        return self.toolWidget.brushModeInput.currentMode()

    @property
    def brushStyle(self):
        return self.toolWidget.brushShapeInput.currentShape

    def brushBoxForPoint(self, point):
        return self.brushMode.brushBoundingBox(point, self.options)

    def brushSelectionForCursor(self):
        return BrushSelection(self.brushBoxForPoint((0, 0, 0)), self.brushStyle)

    def updateCursor(self):
        log.info("Updating brush cursor: %s %s", self.brushStyle, self.brushSelectionForCursor())
        if self.cursorWorldScene:
            self.brushLoader.timer.stop()
            self.cursorNode.removeChild(self.cursorWorldScene)

        cursorLevel = MaskLevel(self.brushSelectionForCursor(),
                                self.fillBlock,
                                self.editorSession.worldEditor.blocktypes)

        self.cursorWorldScene = worldscene.WorldScene(cursorLevel, self.editorSession.textureAtlas)
        self.cursorWorldScene.depthOffsetNode.depthOffset = DepthOffset.PreviewRenderer
        self.cursorNode.addChild(self.cursorWorldScene)

        self.brushLoader = WorldLoader(self.cursorWorldScene)
        self.brushLoader.timer.start()


@registerCustomWidget
class BrushShapeWidget(QtGui.QWidget):
    def __init__(self, *args, **kwargs):
        super(BrushShapeWidget, self).__init__(*args, **kwargs)
        buttons = self.buttons = []
        layout = flowlayout.FlowLayout()
        buttonGroup = QtGui.QButtonGroup()

        iconBase = resourcePath("mcedit2/ui/editortools/images")
        for shape in BrushStyles.allStyles:
            filename = os.path.join(iconBase, shape.icon)
            assert os.path.exists(filename), "%r does not exist" % filename
            icon = QtGui.QIcon(filename)
            if icon is None:
                raise ValueError("Failed to read shape icon file %s" % filename)
            def _handler(shape):
                def handler():
                    self.currentShape = shape
                    BrushShapeSetting.setValue(shape.ID)
                    self.shapeChanged.emit()
                return handler
            action = QtGui.QAction(icon, shape.ID, self, triggered=_handler(shape))
            button = QtGui.QToolButton()
            button.setCheckable(True)
            button.setDefaultAction(action)
            button.setIconSize(QtCore.QSize(32, 32))
            buttons.append(button)
            layout.addWidget(button)
            buttonGroup.addButton(button)

        self.setLayout(layout)
        currentID = BrushShapeSetting.value(BrushStyles.allStyles[0].ID)
        shapesByID = {shape.ID:shape for shape in BrushStyles.allStyles}

        self.currentShape = shapesByID.get(currentID, BrushStyles.allStyles[0])

    shapeChanged = QtCore.Signal()

@registerCustomWidget
class BrushModeWidget(QtGui.QComboBox):
    def __init__(self, *args, **kwargs):
        super(BrushModeWidget, self).__init__(*args, **kwargs)

        for mode in BrushModes.allModes:
            self.addItem(mode.name, mode)

        currentID = BrushModeSetting.value(BrushModes.allModes[0].name)
        indexesByID = {s.name: i for (i, s) in enumerate(BrushModes.allModes)}
        idx = indexesByID.get(currentID, 0)
        self.setCurrentIndex(idx)
        self.currentIndexChanged.connect(self.indexDidChange)

    def currentMode(self):
        return self.itemData(self.currentIndex())

    def indexDidChange(self):
        BrushModeSetting.setValue(self.currentMode().name)
