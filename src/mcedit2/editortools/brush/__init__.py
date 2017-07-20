"""
    brush
"""
from __future__ import absolute_import, division, print_function, unicode_literals

import logging

from PySide import QtGui

from mcedit2.command import SimplePerformCommand
from mcedit2.editortools import EditorTool
from mcedit2.editortools.brush.masklevel import FakeBrushSection
from mcedit2.editortools.brush.modes import BrushModeClasses
from mcedit2.editortools.tool_settings import BrushModeSetting, BrushSizeSetting
from mcedit2.rendering import worldscene
from mcedit2.rendering.depths import DepthOffsets
from mcedit2.rendering.scenegraph.matrix import Translate
from mcedit2.rendering.scenegraph.scenenode import Node
from mcedit2.rendering.selection import SelectionBoxNode
from mcedit2.ui.editortools.brush import Ui_brushWidget
from mcedit2.util import bresenham
from mcedit2.util.showprogress import showProgress
from mcedit2.util.worldloader import WorldLoader
from mceditlib.geometry import Vector
from mceditlib.selection import UnionBox
from mceditlib.selection.hollow import HollowSelection
from mceditlib.util import exhaust

log = logging.getLogger(__name__)


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
        try:
            selections = [self.brushShape.createShapedSelection(self.brushMode.brushBoxForPoint(point, self.options),
                                                                self.editorSession.currentDimension)
                          for point in self.points]

            if len(selections) > 1:
                selection = UnionBox(*selections)
            elif len(selections) == 0:
                yield 0
                return
            else:
                selection = selections[0]

            if self.hollow:
                selection = HollowSelection(selection)

            for i in self.brushMode.applyToSelection(self, selection):
                yield i
        except NotImplementedError:
            for i, point in enumerate(self.points):
                f = self.brushMode.applyToPoint(self, point)
                if hasattr(f, "__iter__"):
                    for progress in f:
                        yield progress
                else:
                    yield i, len(self.points), "Applying {0} brush...".format(self.brushMode.name)

        self.performed = True


class BrushToolWidget(QtGui.QWidget, Ui_brushWidget):
    def __init__(self, *args, **kwargs):
        super(BrushToolWidget, self).__init__(*args, **kwargs)
        self.setupUi(self)


class BrushTool(EditorTool):
    name = "Brush"
    iconName = "brush"
    maxBrushSize = 512

    modifiesWorld = True

    def __init__(self, editorSession, *args, **kwargs):
        super(BrushTool, self).__init__(editorSession, *args, **kwargs)
        self.toolWidget = BrushToolWidget()
        self.brushMode = None
        self.brushLoader = None

        self.brushModesByName = {cls.name:cls(self) for cls in BrushModeClasses}
        brushModes = self.brushModesByName.values()
        self.toolWidget.brushModeInput.setModes(brushModes)
        BrushModeSetting.connectAndCall(self.modeSettingChanged)

        self.cursorWorldScene = None
        self.cursorBoxNode = None
        self.cursorNode = Node("brushCursor")
        self.cursorTranslate = Translate()
        self.cursorNode.addState(self.cursorTranslate)

        self.toolWidget.xSpinSlider.setMinimum(1)
        self.toolWidget.ySpinSlider.setMinimum(1)
        self.toolWidget.zSpinSlider.setMinimum(1)

        self.toolWidget.xSpinSlider.valueChanged.connect(self.setX)
        self.toolWidget.ySpinSlider.valueChanged.connect(self.setY)
        self.toolWidget.zSpinSlider.valueChanged.connect(self.setZ)

        self.toolWidget.brushShapeInput.shapeChanged.connect(self.updateCursor)
        self.toolWidget.brushShapeInput.shapeOptionsChanged.connect(self.updateCursor)

        self.brushSize = BrushSizeSetting.value(QtGui.QVector3D(5, 5, 5)).toTuple()  # calls updateCursor

        self.toolWidget.xSpinSlider.setValue(self.brushSize[0])
        self.toolWidget.ySpinSlider.setValue(self.brushSize[1])
        self.toolWidget.zSpinSlider.setValue(self.brushSize[2])
        self.toolWidget.hoverSpinSlider.setValue(1)

        self.dragPoints = []

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

    def hoverPosition(self, event):
        if event.blockPosition:
            vector = (event.blockFace.vector * self.hoverDistance)
            pos = event.blockPosition + vector
            return pos

    def mousePress(self, event):
        self.dragPoints[:] = []
        pos = self.hoverPosition(event)
        if pos:
            self.dragPoints.append(pos)
            
    def mouseMove(self, event):
        pos = self.hoverPosition(event)
        if pos:
            self.cursorTranslate.translateOffset = pos

    def mouseDrag(self, event):
        p2 = self.hoverPosition(event)
        if p2:
            if len(self.dragPoints):
                p1 = self.dragPoints.pop(-1)
                points = list(bresenham.bresenham(p1, p2))
                self.dragPoints.extend(points)
            else:
                self.dragPoints.append(p2)

    def mouseRelease(self, event):
        if not len(self.dragPoints):
            pos = self.hoverPosition(event)
            if pos:
                self.dragPoints.append(pos)
        if len(self.dragPoints):
            dragPoints = sorted(set(self.dragPoints))
            self.dragPoints[:] = []
            command = BrushCommand(self.editorSession, dragPoints, self.options)
            self.editorSession.pushCommand(command)

    @property
    def options(self):
        options = {'brushSize': self.brushSize,
                   'brushShape': self.brushShape,
                   'brushMode': self.brushMode,
                   'brushHollow': self.brushHollow}
        options.update(self.brushMode.getOptions())
        return options

    def modeSettingChanged(self, value):
        self.brushMode = self.brushModesByName[value]
        stack = self.toolWidget.modeOptionsStack
        while stack.count():
            stack.removeWidget(stack.widget(0))
        if self.brushMode.optionsWidget:
            stack.addWidget(self.brushMode.optionsWidget)

    @property
    def brushShape(self):
        return self.toolWidget.brushShapeInput.currentShape

    @property
    def brushHollow(self):
        return self.toolWidget.hollowCheckBox.isChecked()

    def updateCursor(self):
        log.info("Updating brush cursor")
        if self.cursorWorldScene:
            self.brushLoader.timer.stop()
            self.cursorNode.removeChild(self.cursorWorldScene)
            self.cursorWorldScene = None

        if self.cursorBoxNode:
            self.cursorNode.removeChild(self.cursorBoxNode)
            self.cursorBoxNode = None

        cursorLevel = self.brushMode.createCursorLevel(self)
        if cursorLevel is not None:
            self.cursorWorldScene = worldscene.WorldScene(cursorLevel, self.editorSession.textureAtlas)
            self.cursorWorldScene.depthOffset.depthOffset = DepthOffsets.PreviewRenderer
            self.cursorNode.addChild(self.cursorWorldScene)

            self.brushLoader = WorldLoader(self.cursorWorldScene)
            self.brushLoader.startLoader()

        cursorBox = self.brushMode.brushBoxForPoint((0, 0, 0), self.options)
        if cursorBox is not None:
            self.cursorBoxNode = SelectionBoxNode()
            self.cursorBoxNode.selectionBox = cursorBox
            self.cursorBoxNode.filled = False

            self.cursorNode.addChild(self.cursorBoxNode)


