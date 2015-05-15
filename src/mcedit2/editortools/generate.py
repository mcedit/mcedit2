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
    def __init__(self, generateTool):
        super(GeneratePlugin, self).__init__()
        self.generateTool = generateTool

    def getPreviewNode(self, bounds):
        """
        Get a preview of the generated object as a SceneNode. Intended as a light-weight alternative to generating
        the entire object up front when the user selects a bounding box.

        :param bounds: Bounding box chosen by the user
        :type bounds: BoundingBox
        :return: A preview of the generated object
        :rtype: SceneNode
        """
        return None

    def generate(self, bounds, blocktypes):
        """
        The main entry point of the GeneratePlugin. Given the bounding box chosen by the user and the BlockTypeSet
        for the currently edited world, return a world (usually a Schematic file) suitable for importing into the
        edited world.

        :param bounds: Bounding box chosen by the user
        :type bounds: BoundingBox
        :param blocktypes: BlockTypeSet of currently edited world
        :type blocktypes: BlockTypeSet
        :return: Generated Schematic
        :rtype: WorldEditor
        """
        schematic = createSchematic(bounds.size, blocktypes)
        dim = schematic.getDimension()

        self.generateInSchematic(dim, bounds)
        return schematic

    def generateInSchematic(self, dimension, originalBounds):
        """
        A convenience entry point that provides an already-created schematic file as a WorldEditorDimension.

        :param dimension: The main dimension of the schematic
        :type dimension: WorldEditorDimension
        :param originalBounds: The bounding box in world coordinates
        :type dimension: BoundingBox
        :return: Nothing. Edit the provided dimension to provide a "return value"
        :rtype: None
        """
        raise NotImplementedError

    def generateInDimension(self, bounds, dimension):
        """
        An alternate entry point for generating directly into a world without an intermediate schematic.

        In order to use generateInDimension, you must also override generate and return None.

        This function will not be called for the purpose of displaying block previews. If you need to use
        generateInDimension, you should implement getPreviewNode to provide an OpenGL preview using scene nodes.

        :param bounds:
        :type bounds:
        :param dimension:
        :type dimension:
        :return:
        :rtype:
        """
        raise NotImplementedError

    def getOptionsWidget(self):
        """
        Return (and possibly create) a QWidget that will be displayed in the Generate Tool Options panel while
        this GeneratePlugin is chosen.

        :return:
        :rtype: QtGui.QWidget
        """
        raise NotImplementedError

    def updatePreview(self):
        """
        Trigger the GenerateTool to call generate() on this GeneratePlugin again. This function should be
        called by the plugin whenever one of the options provided by the options widget is changed.

        :return:
        :rtype:
        """
        self.generateTool.updatePreview()

    @property
    def editorSession(self):
        return self.generateTool.editorSession

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

    def generateInSchematic(self, dim):
        bounds = dim.bounds
        blocktypes = dim.blocktypes

        trunkX = int(bounds.width / 2)
        trunkZ = int(bounds.length / 2)

        crownBottom = int(bounds.height * 2 / 3)

        wood = blocktypes["log[axis=y,variant=birch]"]
        leaves = blocktypes["leaves[check_decay=false,decayable=true,variant=birch]"]

        dim.setBlocks(range(0, bounds.width), [range(crownBottom, bounds.height)], [[range(0, bounds.length)]], leaves)
        dim.setBlocks(trunkX, range(0, bounds.height), trunkZ, wood)


_pluginClasses = []

def registerGeneratePlugin(cls):
    _pluginClasses.append(cls)
    return cls

def unregisterGeneratePlugin(cls):
    _pluginClasses[:] = [c for c in _pluginClasses if c != cls]

_pluginClasses.append(TreeGen)

class GenerateTool(EditorTool):
    name = "Generate"
    iconName = "generate"

    instantDisplayChunks = 32

    def __init__(self, *args, **kwargs):
        EditorTool.__init__(self, *args, **kwargs)
        self.livePreview = False
        self.blockPreview = False
        self.glPreview = True

        toolWidget = QtGui.QWidget()

        self.toolWidget = toolWidget

        column = []
        self.generatorTypes = [pluginClass(self) for pluginClass in _pluginClasses]
        self.currentGenerator = None
        if len(self.generatorTypes):
            self.currentGenerator = self.generatorTypes[0]

        self.generatorTypeInput = QtGui.QComboBox()
        for gt in self.generatorTypes:
            self.generatorTypeInput.addItem(gt.displayName, gt)

        self.generatorTypeInput.currentIndexChanged.connect(self.generatorTypeChanged)

        self.livePreviewCheckbox = QtGui.QCheckBox("Live Preview")
        self.livePreviewCheckbox.setChecked(self.livePreview)
        self.livePreviewCheckbox.toggled.connect(self.livePreviewToggled)

        self.blockPreviewCheckbox = QtGui.QCheckBox("Block Preview")
        self.blockPreviewCheckbox.setChecked(self.blockPreview)
        self.blockPreviewCheckbox.toggled.connect(self.blockPreviewToggled)

        self.glPreviewCheckbox = QtGui.QCheckBox("GL Preview")
        self.glPreviewCheckbox.setChecked(self.glPreview)
        self.glPreviewCheckbox.toggled.connect(self.glPreviewToggled)

        self.optionsHolder = QtGui.QStackedWidget()
        self.optionsHolder.setSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Expanding)

        self.generateButton = QtGui.QPushButton(self.tr("Generate"))
        self.generateButton.clicked.connect(self.generateClicked)

        column.append(self.generatorTypeInput)
        column.append(self.livePreviewCheckbox)
        column.append(self.blockPreviewCheckbox)
        column.append(self.glPreviewCheckbox)
        column.append(self.optionsHolder)
        column.append(self.generateButton)

        self.toolWidget.setLayout(Column(*column))

        self.overlayNode = scenegraph.Node()

        self.sceneHolderNode = scenegraph.TranslateNode()
        self.overlayNode.addChild(self.sceneHolderNode)

        self.previewNode = None

        self.boxHandleNode = BoxHandle()
        self.boxHandleNode.boundsChanged.connect(self.boundsDidChange)
        self.boxHandleNode.boundsChangedDone.connect(self.boundsDidChangeDone)
        self.overlayNode.addChild(self.boxHandleNode)

        self.worldScene = None

        self.previewBounds = None
        self.schematicBounds = None
        self.currentSchematic = None

        if len(self.generatorTypes):
            self.generatorTypeChanged(0)

    def livePreviewToggled(self, value):
        self.livePreview = value

    def blockPreviewToggled(self, value):
        self.blockPreview = value
        if value:
            if self.currentSchematic:
                self.displaySchematic(self.currentSchematic, self.schematicBounds.origin)
            else:
                self.updateBlockPreview()
        else:
            self.clearSchematic()

    def glPreviewToggled(self, value):
        self.glPreview = value
        if value:
            self.updateNodePreview()  # xxx cache previewNode?
        else:
            self.clearNode()

    def generatorTypeChanged(self, index):
        self.currentGenerator = self.generatorTypes[index]
        self.optionsHolder.removeWidget(self.optionsHolder.widget(0))
        self.optionsHolder.addWidget(self.currentGenerator.getOptionsWidget())
        self.updatePreview()

    def mousePress(self, event):
        self.boxHandleNode.mousePress(event)

    def mouseMove(self, event):
        self.boxHandleNode.mouseMove(event)

    def mouseRelease(self, event):
        self.boxHandleNode.mouseRelease(event)

    def boundsDidChange(self, bounds):
        # box still being resized
        if not self.livePreview:
            return

        self.previewBounds = bounds
        self.updatePreview()

    def boundsDidChangeDone(self, bounds, newSelection):
        # box finished resize

        self.previewBounds = bounds
        self.schematicBounds = bounds
        self.updatePreview()

    def clearNode(self):
        if self.previewNode:
            self.overlayNode.removeChild(self.previewNode)
            self.previewNode = None

    def updatePreview(self):
        if self.blockPreview:
            self.updateBlockPreview()
        else:
            self.clearSchematic()

        if self.glPreview:
            self.updateNodePreview()
        else:
            self.clearNode()

    def updateBlockPreview(self):
        bounds = self.previewBounds

        if bounds is not None and bounds.volume > 0:
            self.generateNextSchematic(bounds)
        else:
            self.clearSchematic()

    def updateNodePreview(self):
        bounds = self.previewBounds
        if self.currentGenerator is None:
            return

        if bounds is not None and bounds.volume > 0:
            node = self.currentGenerator.getPreviewNode(bounds)
            if node is not None:
                self.clearNode()

                if isinstance(node, list):
                    nodes = node
                    node = scenegraph.Node()
                    for c in nodes:
                        node.addChild(c)

                self.overlayNode.addChild(node)
                self.previewNode = node

    def generateNextSchematic(self, bounds):
        if bounds is None:
            self.clearSchematic()
            return
        if self.currentGenerator is None:
            return

        try:
            schematic = self.currentGenerator.generate(bounds, self.editorSession.worldEditor.blocktypes)
            self.currentSchematic = schematic
            self.displaySchematic(schematic, bounds.origin)
        except Exception as e:
            log.exception("Error while running generator %s: %s", self.currentGenerator, e)
            QtGui.QMessageBox.warning(qApp.mainWindow, "Error while running generator",
                                      "An error occurred while running the generator: \n  %s.\n\n"
                                      "Traceback: %s" % (e, traceback.format_exc()))
            self.livePreview = False

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
            self.clearSchematic()

    def clearSchematic(self):
        if self.worldScene:
            self.sceneHolderNode.removeChild(self.worldScene)
            self.worldScene = None
            self.loader.timer.stop()
            self.loader = None

    def generateClicked(self):
        if self.currentGenerator is None:
            return

        if self.schematicBounds is None:
            log.info("schematicBounds is None, not generating")
            return

        if self.currentSchematic is None:
            log.info("Generating new schematic for import")
            currentSchematic = self.currentGenerator.generate(self.schematicBounds, self.editorSession.worldEditor.blocktypes)
        else:
            log.info("Importing previously generated schematic.")
            currentSchematic = self.currentSchematic

        command = GenerateCommand(self, self.schematicBounds)
        try:
            with command.begin():
                if currentSchematic is not None:
                    task = self.editorSession.currentDimension.importSchematicIter(currentSchematic, self.schematicBounds.origin)
                    showProgress(self.tr("Importing generated object..."), task)
                else:
                    task = self.currentGenerator.generateInWorld(self.schematicBounds, self.editorSession.currentDimension)
                    showProgress(self.tr("Generating object in world..."), task)
        except Exception as e:
            log.exception("Error while importing or generating in world: %r" % e)
            command.undo()
        else:
            self.editorSession.pushCommand(command)

class GenerateCommand(SimpleRevisionCommand):
    def __init__(self, generatorTool, schematicBounds):
        super(GenerateCommand, self).__init__(generatorTool.editorSession, "Generate %s")
        self.schematicBounds = schematicBounds
        self.generatorTool = generatorTool

    def undo(self):
        super(GenerateCommand, self).undo()
        self.generatorTool.boxHandleNode.bounds = self.schematicBounds
        self.generatorTool.schematicBounds = self.schematicBounds
        self.generatorTool.updatePreview()

    def redo(self):
        super(GenerateCommand, self).redo()
        self.generatorTool.clearSchematic()
        self.generatorTool.clearNode()
        self.generatorTool.boxHandleNode.bounds = None
