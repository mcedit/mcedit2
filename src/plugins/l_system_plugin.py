"""
    l_system_plugin
"""
from __future__ import absolute_import, division, print_function
import logging

from PySide import QtGui

from mcedit2.editortools.generate import GeneratePlugin
from mcedit2.plugins import registerGeneratePlugin
import koch
from mcedit2.synth.l_system import renderBlocks, renderSceneNodes, applyReplacementsIterated
from mcedit2.util.showprogress import showProgress
from mcedit2.widgets.blockpicker import BlockTypeButton
from mcedit2.widgets.layout import Column
from mcedit2.widgets.spinslider import SpinSlider
from mceditlib.schematic import createSchematic


log = logging.getLogger(__name__)

class LSystemPlugin(GeneratePlugin):

    def __init__(self, editorSession):
        log.warn("type(LSystemPlugin): %s, type(self): %s (IS? %s)",
                 LSystemPlugin, type(self),
                 LSystemPlugin is type(self))
        super(LSystemPlugin, self).__init__(editorSession)
        self.optionsWidget = None
        self.displayName = self.tr("L-System Test")

    def getOptionsWidget(self):
        if self.optionsWidget:
            return self.optionsWidget

        widget = QtGui.QWidget()

        self.systemsBox = QtGui.QComboBox()
        self.systemsBox.addItem("Koch Snowflake")

        self.blocktypeButton = BlockTypeButton()
        self.blocktypeButton.editorSession = self.editorSession
        self.blocktypeButton.block = "minecraft:stone"
        self.blocktypeButton.blocksChanged.connect(self.updatePreview)

        self.iterationsSlider = SpinSlider()
        self.iterationsSlider.setMinimum(1)
        self.iterationsSlider.setMaximum(100)
        self.iterationsSlider.setValue(3)
        self.iterationsSlider.valueChanged.connect(self.updatePreview)

        widget.setLayout(Column(self.systemsBox,
                                self.iterationsSlider,
                                self.blocktypeButton, # xxx from systemsBox
                                None))

        self.optionsWidget = widget
        return widget

    def getPreviewNode(self, bounds):
        system = koch.Snowflake(bounds, blocktype=self.blocktypeButton.block)
        symbol_list = [system]

        max_iterations = self.iterationsSlider.value()

        def process(_symbol_list):
            for iteration, _symbol_list in applyReplacementsIterated(_symbol_list, max_iterations):
                yield iteration, max_iterations

            yield _symbol_list

        symbol_list = showProgress("Generating...", process(symbol_list), cancel=True)
        if symbol_list is False:
            return

        sceneNodes = renderSceneNodes(symbol_list)
        return sceneNodes

    def generate(self, bounds, blocktypes):
        # self.systemsBox.value()
        schematic = createSchematic(bounds.size, blocktypes)
        dim = schematic.getDimension()
        system = koch.Snowflake(dim.bounds, blocktype=self.blocktypeButton.block)
        symbol_list = [system]

        max_iterations = self.iterationsSlider.value()
        def process(_symbol_list):
            for iteration, _symbol_list in applyReplacementsIterated(_symbol_list, max_iterations):
                yield iteration, max_iterations

            yield _symbol_list

        symbol_list = showProgress("Generating...", process(symbol_list), cancel=True)
        if symbol_list is False:
            return

        import pprint
        pprint.pprint(symbol_list)
        rendering = renderBlocks(symbol_list)

        print("Rendering %d blocks" % len(rendering))
        for x, y, z, blockType in rendering:
            dim.setBlock(x, y, z, blockType)

        return schematic

registerGeneratePlugin(LSystemPlugin)
