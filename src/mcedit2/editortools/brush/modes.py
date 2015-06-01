"""
    modes
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from PySide import QtGui, QtCore
from mcedit2.editortools.brush.masklevel import MaskLevel
from mcedit2.util.showprogress import showProgress
from mcedit2.widgets.blockpicker import BlockTypeButton
from mcedit2.widgets.layout import Column, Row
from mceditlib.anvil.biome_types import BiomeTypes
from mceditlib.geometry import Vector
from mceditlib.selection import ShapedSelection, BoundingBox

log = logging.getLogger(__name__)



class BrushMode(QtCore.QObject):
    optionsWidget = None

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

    def createOptionsWidget(self, brushTool):
        return None

    def createCursorLevel(self, brushTool):
        return None


class Fill(BrushMode):
    name = "fill"

    def __init__(self):
        super(Fill, self).__init__()
        self.displayName = self.tr("Fill")

    def createOptionsWidget(self, brushTool):
        if self.optionsWidget:
            return self.optionsWidget

        self.optionsWidget = QtGui.QWidget()
        label = QtGui.QLabel(self.tr("Fill Block:"))
        self.blockTypeButton = BlockTypeButton()
        self.blockTypeButton.editorSession = brushTool.editorSession
        self.blockTypeButton.block = brushTool.editorSession.worldEditor.blocktypes['minecraft:stone']
        self.blockTypeButton.blocksChanged.connect(brushTool.updateCursor)

        self.optionsWidget.setLayout(Column(
            Row(label, self.blockTypeButton, margin=0),
            None, margin=0))
        return self.optionsWidget

    def getOptions(self):
        return {'blockInfo': self.blockTypeButton.block}

    def applyToSelections(self, command, selections):
        """

        :type command: BrushCommand
        """
        fill = command.editorSession.currentDimension.fillBlocksIter(selections[0], command.options['blockInfo'])
        showProgress("Applying brush...", fill)

    def brushBoxForPoint(self, point, options):
        return self.brushBoundingBox(point, options)

    def createCursorLevel(self, brushTool):
        selection = ShapedSelection(self.brushBoxForPoint((0, 0, 0), brushTool.options), brushTool.brushShape.shapeFunc)
        cursorLevel = MaskLevel(selection,
                                self.blockTypeButton.block,
                                brushTool.editorSession.worldEditor.blocktypes)
        return cursorLevel


class Biome(BrushMode):
    name = "biome"

    def __init__(self, *args, **kwargs):
        super(Biome, self).__init__(*args, **kwargs)
        self.displayName = self.tr("Biome")

    def getOptions(self):
        return {'biomeID': self.biomeTypeBox.itemData(self.biomeTypeBox.currentIndex())}

    def createOptionsWidget(self, brushTool):
        if self.optionsWidget:
            return self.optionsWidget

        self.optionsWidget = QtGui.QWidget()
        label = QtGui.QLabel(self.tr("Fill Biome:"))
        self.biomeTypeBox = QtGui.QComboBox()
        self.biomeTypes = BiomeTypes()
        for biome in self.biomeTypes.types.values():
            self.biomeTypeBox.addItem(biome.name, biome.ID)

        self.biomeTypeBox.activated.connect(brushTool.updateCursor)
        self.optionsWidget.setLayout(Column(Row(label, self.biomeTypeBox, margin=0), None, margin=0))
        return self.optionsWidget

    def applyToSelections(self, command, selections):
        """

        :type command: BrushCommand
        """
        #task = command.editorSession.currentDimension.fillBlocksIter(selections[0], command.blockInfo)
        #showProgress("Applying brush...", task)
        selection = selections[0]
        biomeID = command.options['biomeID']
        for x, _, z in selection.positions:
            command.editorSession.currentDimension.setBiomeID(x, z, biomeID)

    def brushBoxForPoint(self, point, options):
        x, y, z = options['brushSize']
        options['brushSize'] = x, 1, z

        return self.brushBoundingBox(point, options)

    def createCursorLevel(self, brushTool):
        box = self.brushBoxForPoint((0, 0, 0), brushTool.options)

        selection = ShapedSelection(box, brushTool.brushShape.shapeFunc)
        cursorLevel = MaskLevel(selection,
                                brushTool.editorSession.worldEditor.blocktypes["minecraft:grass"],
                                brushTool.editorSession.worldEditor.blocktypes,
                                biomeID=self.getOptions()['biomeID'])
        return cursorLevel


class BrushModes(object):
    # load from plugins here
    fill = Fill()
    biome = Biome()
    allModes = [fill, biome]
    modesByName = {mode.name: mode for mode in allModes}
