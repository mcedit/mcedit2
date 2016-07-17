"""
    l_system_plugin
"""
from __future__ import absolute_import, division, print_function
import logging

from mcedit2.editortools.generate import GeneratePlugin
from mcedit2.synth.l_system import renderBlocks, renderSceneNodes, applyReplacementsIterated
from mcedit2.util.showprogress import showProgress
from mcedit2.widgets.spinslider import SpinSlider

log = logging.getLogger(__name__)


class LSystemPlugin(GeneratePlugin):
    """
    A GeneratePlugin subclass intended for driving an L-system.

    Most of the GeneratePlugin methods are already implemented. To use an LSystemPlugin,
    you need to implement `getOptionsWidget` and `createInitialSymbol` - after that,
    previewing and generating the L-System is taken care of by LSystemPlugin.

    In your implementation of `getOptionsWidget`, you should add `self.iterationsSlider`
     to your widget to control the iteration depth.

    A `recursive` attribute is also available. If your L-System is not recursively defined - that
    is, a finite number of iterations will result in a symbol list that has no further `replace`
    methods defined, you may set the `recursive` attribute of the LSystemPlugin to False. Setting
    `recursive` to False will cause the block and schematic renderer to run the replacement rules
    until no further replacements occur (or until MAX_ITERATIONS iterations), and the value of
    `iterationsSlider` will be ignored for the final generation. The `iterationsSlider` will
    still affect the GL rendering, which is useful for inspecting the system's state after every
    iteration.

    """

    recursive = True
    MAX_ITERATIONS = 50

    def __init__(self, editorSession):
        super(LSystemPlugin, self).__init__(editorSession)
        self.optionsWidget = None

        self.iterationsSlider = SpinSlider()
        self.iterationsSlider.setMinimum(1)
        self.iterationsSlider.setMaximum(50)
        self.iterationsSlider.setValue(3)
        self.iterationsSlider.valueChanged.connect(self.updatePreview)

    def createInitialSymbol(self, bounds):
        """
        Create and return the initial Symbol for the L-System. The symbol is typically initialized
        using values input by the user via the options widget.

        :param bounds: The bounding box selected with the Generate tool, in world coordinates.
        :type bounds: BoundingBox
        :return: The initial Symbol for this L-System
        :rtype: Symbol
        """
        raise NotImplementedError

    def createSymbolList(self, bounds, indefinite=False):
        system = self.createInitialSymbol(bounds)

        symbol_list = [system]

        if indefinite:
            max_iterations = self.MAX_ITERATIONS
        else:
            max_iterations = self.iterationsSlider.value()

        def process(_symbol_list):
            for iteration, _symbol_list in applyReplacementsIterated(_symbol_list, max_iterations):
                yield iteration, max_iterations

            yield _symbol_list

        symbol_list = showProgress("Generating...", process(symbol_list), cancel=True)
        if symbol_list is False:
            return None

        return symbol_list

    def getPreviewNode(self, bounds):
        symbol_list = self.createSymbolList(bounds)
        if symbol_list is None:
            return None

        log.info("Rendering symbols to OpenGL")

        sceneNodes = self.renderSceneNodes(symbol_list)
        return sceneNodes

    def renderSceneNodes(self, symbol_list):
        return renderSceneNodes(symbol_list)

    def generateInSchematic(self, dimension, originalBounds):
        symbol_list = self.createSymbolList(originalBounds)
        if symbol_list is None:
            return None

        log.info("Rendering symbols to blocks")

        rendering = self.renderBlocks(symbol_list)

        log.info("Editing %d blocks" % len(rendering))
        for x, y, z, blockType in rendering:
            x -= originalBounds.minx
            y -= originalBounds.miny
            z -= originalBounds.minz

            dimension.setBlock(x, y, z, blockType)

    def renderBlocks(self, symbol_list):
        return renderBlocks(symbol_list)

