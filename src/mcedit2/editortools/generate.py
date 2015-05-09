"""
    create
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from PySide import QtCore, QtGui

from mcedit2.editortools import EditorTool
from mcedit2.handles.boxhandle import BoxHandle
from mcedit2.rendering import scenegraph
from mcedit2.rendering.worldscene import WorldScene
from mcedit2.util.worldloader import WorldLoader
from mcedit2.widgets.layout import Column
from mcedit2.widgets.spinslider import SpinSlider
from mceditlib.schematic import createSchematic


log = logging.getLogger(__name__)

class GeneratePlugin(QtCore.QObject):
    def generatePreview(self, bounds, blocktypes):
        return self.generate(bounds, blocktypes)

    def getPreviewNode(self):
        return None

class TreeGen(GeneratePlugin):

    def __init__(self, *args, **kwargs):
        super(TreeGen, self).__init__(*args, **kwargs)
        self.optionsWidget = None
        self.displayName = self.tr("Tree")

    def getOptionsWidget(self):
        if self.optionsWidget:
            return self.optionsWidget

        widget = QtGui.QWidget()
        self.trunkSlider = SpinSlider()
        self.trunkSlider.setValue(1)
        widget.setLayout(Column(self.trunkSlider, None))
        self.optionsWidget = widget
        return widget

    def generate(self, bounds, blocktypes):
        schematic = createSchematic(bounds.size, blocktypes)
        dim = schematic.getDimension()

        trunkX = int(bounds.width / 2)
        trunkZ = int(bounds.length / 2)

        crownBottom = int(bounds.height * 2 / 3)

        wood = blocktypes["log[axis=y,variant=birch]"]
        leaves = blocktypes["leaves[check_decay=false,decayable=true,variant=birch]"]

        dim.setBlocks(range(0, bounds.width), [range(crownBottom, bounds.height)], [[range(0, bounds.length)]], leaves)
        dim.setBlocks(trunkX, range(0, bounds.height), trunkZ, wood)

        return schematic

class GenerateTool(EditorTool):
    name = "Generate"
    iconName = "generate"

    instantDisplayChunks = 32

    def __init__(self, *args, **kwargs):
        EditorTool.__init__(self, *args, **kwargs)
        self.createToolWidget()

    def createToolWidget(self):
        toolWidget = QtGui.QWidget()

        self.toolWidget = toolWidget

        column = []
        self.generatorTypes = [TreeGen()]
        self.currentType = self.generatorTypes[0]

        self.generatorTypeInput = QtGui.QComboBox()
        for gt in self.generatorTypes:
            self.generatorTypeInput.addItem(gt.displayName, gt)

        self.generatorTypeInput.currentIndexChanged.connect(self.generatorTypeChanged)
        self.optionsHolder = QtGui.QStackedWidget()
        self.optionsHolder.setSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Expanding)

        column.append(self.generatorTypeInput)
        column.append(self.optionsHolder)

        self.toolWidget.setLayout(Column(*column))

        self.overlayNode = scenegraph.Node()

        self.sceneHolderNode = scenegraph.TranslateNode()
        self.overlayNode.addChild(self.sceneHolderNode)


        self.boxHandleNode = BoxHandle()
        self.boxHandleNode.boundsChanged.connect(self.boundsDidChange)
        self.boxHandleNode.boundsChangedDone.connect(self.boundsDidChangeDone)
        self.overlayNode.addChild(self.boxHandleNode)

        self.worldScene = None

        self.schematicBounds = None


    def generatorTypeChanged(self, index):
        self.currentType = self.generatorTypes[index]
        self.optionsHolder.removeWidget(self.optionsHolder.widget(0))
        self.optionsHolder.addWidget(self.currentType.getOptionsWidget())

    def mousePress(self, event):
        self.boxHandleNode.mousePress(event)

    def mouseMove(self, event):
        self.boxHandleNode.mouseMove(event)

    def mouseRelease(self, event):
        self.boxHandleNode.mouseRelease(event)

    def boundsDidChange(self, bounds):
        if bounds is not None and bounds.volume:
            node = self.currentType.getPreviewNode()
            if node is not None:
                pass
            else:

                if self.schematicBounds is None or self.schematicBounds.size != bounds.size:
                    schematic = self.currentType.generatePreview(bounds, self.editorSession.worldEditor.blocktypes)
                    self.displaySchematic(schematic, bounds.origin)
                else:
                    self.sceneHolderNode.translateOffset = bounds.origin

        self.schematicBounds = bounds

    def boundsDidChangeDone(self, bounds, newSelection):
        if bounds is not None and bounds.volume:
            if self.schematicBounds is None or self.schematicBounds.size != bounds.size:
                schematic = self.currentType.generate(bounds, self.editorSession.worldEditor.blocktypes)
                offset = bounds.origin
                self.displaySchematic(schematic, offset)
            else:
                self.sceneHolderNode.translateOffset = bounds.origin
        else:
            self.displaySchematic(None, None)

        self.schematicBounds = bounds

    def displaySchematic(self, schematic, offset):
        if schematic is not None:
            dim = schematic.getDimension()

            if self.worldScene:
                self.sceneHolderNode.removeChild(self.worldScene)
                self.loader.timer.stop()
                self.loader = None

            atlas = self.editorSession.textureAtlas
            self.worldScene = WorldScene(dim, atlas)
            self.sceneHolderNode.translateOffset = offset
            self.sceneHolderNode.addChild(self.worldScene)

            self.loader = WorldLoader(self.worldScene)
            if dim.chunkCount() <= self.instantDisplayChunks:
                for _ in self.loader.work():
                    pass
            else:
                self.loader.timer.start()
        else:
            if self.worldScene:
                self.sceneHolderNode.removeChild(self.worldScene)
                self.worldScene = None
                self.loader.timer.stop()
                self.loader = None

