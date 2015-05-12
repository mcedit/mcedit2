"""
    create
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import traceback

from PySide import QtCore, QtGui
from PySide.QtGui import qApp
from mcedit2.command import SimpleRevisionCommand

from mcedit2.editortools import EditorTool
from mcedit2.handles.boxhandle import BoxHandle
from mcedit2.rendering import scenegraph
from mcedit2.rendering.worldscene import WorldScene
from mcedit2.util.showprogress import showProgress
from mcedit2.util.worldloader import WorldLoader
from mcedit2.widgets.layout import Column
from mcedit2.widgets.spinslider import SpinSlider
from mceditlib.schematic import createSchematic


log = logging.getLogger(__name__)

class GeneratePlugin(QtCore.QObject):
    def __init__(self, editorSession):
        super(GeneratePlugin, self).__init__()
        self.editorSession = editorSession

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

_pluginClasses = []

def registerGeneratePlugin(cls):
    _pluginClasses.append(cls)

#_pluginClasses.append(TreeGen)

class GenerateTool(EditorTool):
    name = "Generate"
    iconName = "generate"

    instantDisplayChunks = 32

    def __init__(self, *args, **kwargs):
        EditorTool.__init__(self, *args, **kwargs)
        self.liveUpdate = False

        toolWidget = QtGui.QWidget()

        self.toolWidget = toolWidget

        column = []
        self.generatorTypes = [pluginClass(self.editorSession) for pluginClass in _pluginClasses]
        self.currentType = self.generatorTypes[0]

        self.generatorTypeInput = QtGui.QComboBox()
        for gt in self.generatorTypes:
            self.generatorTypeInput.addItem(gt.displayName, gt)

        self.generatorTypeInput.currentIndexChanged.connect(self.generatorTypeChanged)

        self.liveUpdateCheckbox = QtGui.QCheckBox("Live Update")

        self.liveUpdateCheckbox.toggled.connect(self.liveUpdateToggled)

        self.optionsHolder = QtGui.QStackedWidget()
        self.optionsHolder.setSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Expanding)

        self.generateButton = QtGui.QPushButton(self.tr("Generate"))
        self.generateButton.clicked.connect(self.generateClicked)

        column.append(self.generatorTypeInput)
        column.append(self.liveUpdateCheckbox)
        column.append(self.optionsHolder)
        column.append(self.generateButton)

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
        self.currentSchematic = None

        if len(self.generatorTypes):
            self.generatorTypeChanged(0)

    def liveUpdateToggled(self, value):
        self.liveUpdate = value

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
        if not self.liveUpdate:
            return

        if bounds is not None and bounds.volume:
            node = self.currentType.getPreviewNode()
            if node is not None:
                pass
            else:
                self.generate(bounds)

        self.schematicBounds = bounds


    def generate(self, bounds):
        if self.schematicBounds is None or self.schematicBounds.size != bounds.size:
            try:
                schematic = self.currentType.generatePreview(bounds, self.editorSession.worldEditor.blocktypes)
                self.setCurrentSchematic(schematic, bounds.origin)
            except Exception as e:
                log.exception("Error while running generator %s: %s", self.currentType, e)
                QtGui.QMessageBox.warning(qApp.mainWindow, "Error while running generator",
                                          "An error occurred while running the generator: \n  %s.\n\n"
                                          "Traceback: %s" % (e, traceback.format_exc()))
                self.liveUpdate = False
        else:
            self.sceneHolderNode.translateOffset = bounds.origin


    def boundsDidChangeDone(self, bounds, newSelection):
        if bounds is not None and bounds.volume:
            self.generate(bounds)
        else:
            self.setCurrentSchematic(None, None)

        self.schematicBounds = bounds

    def setCurrentSchematic(self, schematic, offset):
        self.currentSchematic = schematic
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

    def generateClicked(self):
        if self.currentSchematic is None:
            return

        command = SimpleRevisionCommand(self.editorSession, "Generate %s")
        with command.begin():
            task = self.editorSession.currentDimension.importSchematicIter(self.currentSchematic, self.schematicBounds.origin)
            showProgress(self.tr("Importing generated object..."), task)
        self.editorSession.pushCommand(command)

