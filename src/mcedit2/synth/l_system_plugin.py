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
    you need to implement `getInputsList` and `createInitialSymbol` - after that,
    previewing and generating the L-System is taken care of by LSystemPlugin.

    If `getInputsList` is not capable enough for your needs, you may implement `getOptionsWidget`
    from GeneratePlugin instead. If you do, you should add `self.iterationsSlider` to your widget
    to control the iteration depth.

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

    def getInputsList(self):
        """
        .... on second thought, not sure if I want to do this.

        Return a list of (name, label, inputType, defaultValue, inputOptions) tuples to configure options
        that are presented in the plugin's options widget.

        This may be implemented by subclasses to easily present common types of inputs and ensure
        the previews will be updated when the option's value is changed. Values will also be saved
        to the user's preferences, keyed on the class name of this LSystemPlugin.

        The values set by the user will be available in the LSystemPlugin's `inputValues`
        attribute as a `dict`.

        `name` is a string used as a key in the `optionValues` dict.
        `label` is a string shown to the user in the options widget. `label` should be translated
            using `self.tr("Label Text")`
        `inputType` is one of the strings listed below for the different input types.
        `defaultValue` is the initial value for the input.
        `inputOptions` is a dict providing additional options for the input widget. See the input
            types below for additional options for each input type.

        Input types:

            `SpinSlider`
                An input for entering an integer using a text field, a pair of +/- buttons,
                and a horizontal slider. The default value should be an integer.

                `inputOptions`:
                    `min`: Minimum value.
                    `max`: Maximum value.

            `BlockTypeButton`
                An input for selecting a block type from the currently edited world.

                `inputOptions`: None

            `ChoiceButton`
                An input for selecting one option from a list of possible options.

            `TextField`
                An input for entering arbitrary text. The default value should be a `str`, or
                preferably a `unicode`.

                `inputOptions`:
                    `placeholder`: Placeholder text to show in grey whenever the field is empty.

        :return:
        :rtype:
        """

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

        sceneNodes = renderSceneNodes(symbol_list)
        return sceneNodes

    def generateInSchematic(self, dimension, originalBounds):
        symbol_list = self.createSymbolList(originalBounds)
        if symbol_list is None:
            return None

        log.info("Rendering symbols to blocks")

        rendering = renderBlocks(symbol_list)

        log.info("Editing %d blocks" % len(rendering))
        for x, y, z, blockType in rendering:
            x -= originalBounds.minx
            y -= originalBounds.miny
            z -= originalBounds.minz

            dimension.setBlock(x, y, z, blockType)

