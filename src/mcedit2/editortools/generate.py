"""
    create
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import traceback

from PySide import QtCore, QtGui

from mcedit2.command import SimpleRevisionCommand
from mcedit2.editortools import EditorTool
from mcedit2.handles.boxhandle import BoxHandle
from mcedit2.plugins.registry import PluginClassRegistry
from mcedit2.rendering.scenegraph import scenenode
from mcedit2.rendering.scenegraph.matrix import Translate
from mcedit2.rendering.scenegraph.scenenode import Node
from mcedit2.rendering.worldscene import WorldScene
from mcedit2.util.showprogress import showProgress
from mcedit2.util.worldloader import WorldLoader
from mcedit2.widgets.layout import Column
from mceditlib.schematic import createSchematic
from mceditlib.util import exhaust

log = logging.getLogger(__name__)

class GeneratePlugin(QtCore.QObject):
    """
    A plugin for the Generate tool.

    The `displayName` attribute contains the name to display when choosing this plugin. If not
    present, the class name will be used.

    """
    def __init__(self, generateTool):
        super(GeneratePlugin, self).__init__()
        self.generateTool = generateTool

    def getPreviewNode(self, bounds):
        """
        Get a preview of the generated object as a SceneNode. Intended as a light-weight
        alternative to generating the entire object up front when the user selects a bounding box.

        :param bounds: Bounding box chosen by the user
        :type bounds: BoundingBox
        :return: A preview of the generated object
        :rtype: SceneNode
        """
        return None

    def generate(self, bounds, blocktypes):
        """
        The main entry point of the GeneratePlugin. Given the bounding box chosen by the user and
        the BlockTypeSet for the currently edited world, return a world (usually a Schematic
        file) suitable for importing into the edited world.

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
        A convenience entry point that provides an already-created schematic file as a
        WorldEditorDimension.

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
        An alternate entry point for generating directly into a world without an intermediate
        schematic.

        In order to use generateInDimension, you must also override generate and return None.

        This function will not be called for the purpose of displaying block previews. If you
        need to use generateInDimension, you should implement getPreviewNode to provide an OpenGL
        preview using scene nodes.

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
        Return (and possibly create) a QWidget that will be displayed in the Generate Tool
        Options panel while this GeneratePlugin is chosen.

        :return:
        :rtype: QtGui.QWidget
        """
        raise NotImplementedError

    def boundsChanged(self, bounds):
        """
        Called by GenerateTool whenever the user moves or resizes the bounding box.
        The plugin may use this to change parts of the options widget, for example.

        :type bounds: BoundingBox
        :rtype: None
        """
        pass

    def updatePreview(self):
        """
        Trigger the GenerateTool to call generate() on this GeneratePlugin again. This function
        should be called by the plugin whenever one of the options provided by the options widget
        is changed.

        :return:
        :rtype:
        """
        self.generateTool.updatePreview()

    @property
    def editorSession(self):
        return self.generateTool.editorSession


class _GeneratePlugins(PluginClassRegistry):
    pluginClass = GeneratePlugin

GeneratePlugins = _GeneratePlugins()


class GenerateTool(EditorTool):
    name = "Generate"
    iconName = "generate"

    instantDisplayChunks = 32
    modifiesWorld = True

    def __init__(self, *args, **kwargs):
        EditorTool.__init__(self, *args, **kwargs)
        self.livePreview = False
        self.blockPreview = False
        self.glPreview = True

        toolWidget = QtGui.QWidget()

        self.toolWidget = toolWidget

        column = []
        self.generatorTypes = [pluginClass(self) for pluginClass in GeneratePlugins.registeredPlugins]
        self.currentGenerator = None
        if len(self.generatorTypes):
            self.currentGenerator = self.generatorTypes[0]

        self.generatorTypeInput = QtGui.QComboBox()
        self.generatorTypesChanged()

        self.generatorTypeInput.currentIndexChanged.connect(self.currentTypeChanged)

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

        self.overlayNode = scenenode.Node("generateOverlay")

        self.sceneHolderNode = Node("sceneHolder")
        self.sceneTranslate = Translate()
        self.sceneHolderNode.addState(self.sceneTranslate)

        self.overlayNode.addChild(self.sceneHolderNode)

        self.previewNode = None

        self.boxHandleNode = BoxHandle()
        self.boxHandleNode.boundsChanged.connect(self.boundsDidChange)
        self.boxHandleNode.boundsChangedDone.connect(self.boundsDidChangeDone)
        self.overlayNode.addChild(self.boxHandleNode)

        self.worldScene = None
        self.loader = None

        self.previewBounds = None
        self.schematicBounds = None
        self.currentSchematic = None

        self.currentTypeChanged(0)

        # Name of last selected generator plugin is saved after unloading
        # so it can be reselected if it is immediately reloaded
        self._lastTypeName = None

        GeneratePlugins.pluginAdded.connect(self.addPlugin)
        GeneratePlugins.pluginRemoved.connect(self.removePlugin)

    def removePlugin(self, cls):
        log.info("Removing plugin %s", cls.__name__)
        self.generatorTypes[:] = [gt for gt in self.generatorTypes if not isinstance(gt, cls)]
        self.generatorTypesChanged()
        if self.currentGenerator not in self.generatorTypes:
            lastTypeName = self.currentGenerator.__class__.__name__
            self.currentTypeChanged(0)  # resets self._lastTypeName
            self._lastTypeName = lastTypeName

    def addPlugin(self, cls):
        log.info("Adding plugin %s", cls.__name__)
        self.generatorTypes.append(cls(self))
        self.generatorTypesChanged()
        if self._lastTypeName is not None:
            if cls.__name__ == self._lastTypeName:
                self.currentTypeChanged(len(self.generatorTypes)-1)

    def generatorTypesChanged(self):
        self.generatorTypeInput.clear()
        for gt in self.generatorTypes:
            if hasattr(gt, 'displayName'):
                displayName = gt.displayName
            else:
                displayName = gt.__class__.__name__
            self.generatorTypeInput.addItem(displayName, gt)


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

    def currentTypeChanged(self, index):
        # user selected generator type after old type was unloaded, so forget the old type
        self._lastTypeName = None

        self.optionsHolder.removeWidget(self.optionsHolder.widget(0))
        if index < len(self.generatorTypes):
            self.currentGenerator = self.generatorTypes[index]
            self.optionsHolder.addWidget(self.currentGenerator.getOptionsWidget())
            self.updatePreview()
        else:
            self.currentGenerator = None
            self.clearSchematic()
            self.clearNode()

        log.info("Chose generator %s", repr(self.currentGenerator))

    def mousePress(self, event):
        self.boxHandleNode.mousePress(event)

    def mouseMove(self, event):
        self.boxHandleNode.mouseMove(event)

    def mouseRelease(self, event):
        self.boxHandleNode.mouseRelease(event)

    def boundsDidChange(self, bounds):
        # box still being resized
        if not self.currentGenerator:
            return

        if not self.livePreview:
            return

        self.previewBounds = bounds
        self.currentGenerator.boundsChanged(bounds)
        self.updatePreview()

    def boundsDidChangeDone(self, bounds, oldBounds):
        # box finished resize
        if not self.currentGenerator:
            return

        self.previewBounds = bounds
        self.schematicBounds = bounds
        self.currentGenerator.boundsChanged(bounds)
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
            try:
                node = self.currentGenerator.getPreviewNode(bounds)
            except Exception:
                log.exception("Error while getting scene nodes from generator:")
            else:
                if node is not None:
                    self.clearNode()

                    if isinstance(node, list):
                        nodes = node
                        node = scenenode.Node("generatePreviewHolder")
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
            QtGui.QMessageBox.warning(QtGui.qApp.mainWindow, "Error while running generator",
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
            self.sceneTranslate.translateOffset = offset
            self.sceneHolderNode.addChild(self.worldScene)

            self.loader = WorldLoader(self.worldScene)
            if dim.chunkCount() <= self.instantDisplayChunks:
                exhaust(self.loader.work())
            else:
                self.loader.startLoader()
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
