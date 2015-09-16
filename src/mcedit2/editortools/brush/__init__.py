"""
    brush
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from PySide import QtGui

from mcedit2.editortools import EditorTool
from mcedit2.command import SimplePerformCommand
from mcedit2.editortools.brush.masklevel import FakeBrushSection
from mcedit2.editortools.brush.modes import BrushModeClasses
from mcedit2.rendering import worldscene
from mcedit2.rendering.depths import DepthOffset
from mcedit2.rendering.scenegraph.matrix import TranslateNode
from mcedit2.rendering.selection import SelectionBoxNode
from mcedit2.util.load_ui import load_ui, registerCustomWidget
from mcedit2.util.settings import Settings
from mcedit2.util.showprogress import showProgress
from mcedit2.util.worldloader import WorldLoader
from mceditlib.geometry import Vector
from mceditlib.util import exhaust


log = logging.getLogger(__name__)

BrushModeSetting = Settings().getOption("editortools/brush/mode", default="fill")
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
        self.brushShape = options['brushShape']
        self.brushMode = options['brushMode']
        self.setText("%s %s Brush" % (self.brushMode.name, self.brushShape.ID))

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

    def perform(self):
        if len(self.points) > 10:
            showProgress("Performing brush...", self._perform(), cancel=True)
        else:
            exhaust(self._perform())

    def _perform(self):
        yield 0, len(self.points), "Applying {0} brush...".format(self.brushMode.name)
        try:
            #xxx combine selections
            selections = [self.brushShape.createShapedSelection(self.brushMode.brushBoxForPoint(point, self.options),
                                                                self.editorSession.currentDimension)
                          for point in self.points]
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



class BrushTool(EditorTool):
    name = "Brush"
    iconName = "brush"
    maxBrushSize = 512

    def __init__(self, editorSession, *args, **kwargs):
        super(BrushTool, self).__init__(editorSession, *args, **kwargs)
        self.toolWidget = load_ui("editortools/brush.ui")
        self.brushMode = None
        self.brushLoader = None

        self.brushModesByName = {cls.name:cls() for cls in BrushModeClasses}
        modes = self.brushModesByName.values()
        modes.sort(key=lambda m: m.name)
        self.toolWidget.brushModeInput.setModes(modes)
        BrushModeSetting.connectAndCall(self.modeSettingChanged)

        self.cursorWorldScene = None
        self.cursorNode = TranslateNode()

        self.toolWidget.xSpinSlider.setMinimum(1)
        self.toolWidget.ySpinSlider.setMinimum(1)
        self.toolWidget.zSpinSlider.setMinimum(1)

        self.toolWidget.xSpinSlider.valueChanged.connect(self.setX)
        self.toolWidget.ySpinSlider.valueChanged.connect(self.setY)
        self.toolWidget.zSpinSlider.valueChanged.connect(self.setZ)

        self.toolWidget.brushShapeInput.shapeChanged.connect(self.updateCursor)
        self.toolWidget.brushShapeInput.shapeOptionsChanged.connect(self.updateCursor)

        self.fillBlock = editorSession.worldEditor.blocktypes["stone"]

        self.brushSize = BrushSizeSetting.value(QtGui.QVector3D(5, 5, 5)).toTuple()  # calls updateCursor

        self.toolWidget.xSpinSlider.setValue(self.brushSize[0])
        self.toolWidget.ySpinSlider.setValue(self.brushSize[1])
        self.toolWidget.zSpinSlider.setValue(self.brushSize[2])

    @property
    def hoverDistance(self):
        return self.toolWidget.hoverSpinSlider.value()

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

    def setY(self, val):
        x, y, z = self.brushSize
        y = float(val)
        self.brushSize = x, y, z

    def setZ(self, val):
        x, y, z = self.brushSize
        z = float(val)
        self.brushSize = x, y, z

    def setBlocktypes(self, types):
        if len(types) == 0:
            return

        self.fillBlock = types[0]
        self.updateCursor()

    def mousePress(self, event):
        pos = event.blockPosition
        vector = (event.blockFace.vector * self.hoverDistance)
        command = BrushCommand(self.editorSession, [pos + vector], self.options)
        self.editorSession.pushCommand(command)

    def mouseMove(self, event):
        if event.blockPosition:
            vector = (event.blockFace.vector * self.hoverDistance)
            assert isinstance(vector, Vector), "vector isa %s" % type(vector)
            self.cursorNode.translateOffset = event.blockPosition + vector

    @property
    def options(self):
        options = {'brushSize': self.brushSize,
                   'brushShape': self.brushShape,
                   'brushMode': self.brushMode}
        options.update(self.brushMode.getOptions())
        return options

    def modeSettingChanged(self, value):
        self.brushMode = self.brushModesByName[value]
        stack = self.toolWidget.modeOptionsStack
        while stack.count():
            stack.removeWidget(stack.widget(0))
        widget = self.brushMode.createOptionsWidget(self)
        if widget:
            stack.addWidget(widget)

    @property
    def brushShape(self):
        return self.toolWidget.brushShapeInput.currentShape

    def updateCursor(self):
        log.info("Updating brush cursor")
        if self.cursorWorldScene:
            self.brushLoader.timer.stop()
            self.cursorNode.removeChild(self.cursorWorldScene)
            self.cursorNode.removeChild(self.cursorBoxNode)

        cursorLevel = self.brushMode.createCursorLevel(self)
        cursorBox = self.brushMode.brushBoxForPoint((0, 0, 0), self.options)

        self.cursorBoxNode = SelectionBoxNode()
        self.cursorBoxNode.selectionBox = cursorBox
        self.cursorBoxNode.filled = False

        self.cursorWorldScene = worldscene.WorldScene(cursorLevel, self.editorSession.textureAtlas)
        self.cursorWorldScene.depthOffsetNode.depthOffset = DepthOffset.PreviewRenderer
        self.cursorNode.addChild(self.cursorWorldScene)
        self.cursorNode.addChild(self.cursorBoxNode)

        self.brushLoader = WorldLoader(self.cursorWorldScene)
        self.brushLoader.timer.start()


# xxx button palette?
@registerCustomWidget
class BrushModeWidget(QtGui.QComboBox):
    def __init__(self, *args, **kwargs):
        super(BrushModeWidget, self).__init__(*args, **kwargs)
        self.currentIndexChanged.connect(self.indexDidChange)
        self.adding = False
    def setModes(self, modes):
        self.adding = True
        try:
            for mode in modes:
                self.addItem(mode.displayName, mode.name)

            currentID = BrushModeSetting.value()
            currentIndex = self.findData(currentID)
            if currentIndex == -1:
                log.info("Search failed!")
                currentIndex = 0
            log.info("Loading BrushModeWidget setting: found %s at %s", currentID, currentIndex)
            self.setCurrentIndex(currentIndex)
        finally:
            self.adding = False

    def indexDidChange(self):
        if self.adding:
            return
        BrushModeSetting.setValue(self.itemData(self.currentIndex()))
