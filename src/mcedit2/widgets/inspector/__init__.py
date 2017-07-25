"""
    inspector
"""
from __future__ import absolute_import, division, print_function
import logging
import traceback

from PySide import QtGui
from mcedit2.command import SimpleRevisionCommand
from mcedit2.rendering import depths
from mcedit2.rendering.command_visuals import CommandVisuals
from mcedit2.rendering.scenegraph import scenenode
from mcedit2.rendering.selection import SelectionBoxNode
from mcedit2.ui.inspector import Ui_inspectorWidget
from mcedit2.util.commandblock import ParseCommand
from mcedit2.widgets.inspector.tileentities.chest import ChestEditorWidget, DispenserEditorWidget, HopperEditorWidget
from mcedit2.widgets.inspector.tileentities.command import CommandBlockEditorWidget
from mcedit2.widgets.inspector.tileentities.sign import SignEditorWidget
from mceditlib.geometry import Vector
from mceditlib.selection import BoundingBox

log = logging.getLogger(__name__)

tileEntityEditorClasses = {
}

def registerBlockInspectorWidget(widgetClass):
    ID = widgetClass.tileEntityID
    tileEntityEditorClasses[ID] = widgetClass

def unregisterBlockInspectorWidget(widgetClass):
    dead = [k for k, v in tileEntityEditorClasses.iteritems() if v == widgetClass]
    for k in dead:
        tileEntityEditorClasses.pop(k, None)

registerBlockInspectorWidget(ChestEditorWidget)
registerBlockInspectorWidget(DispenserEditorWidget)
registerBlockInspectorWidget(HopperEditorWidget)
registerBlockInspectorWidget(CommandBlockEditorWidget)
registerBlockInspectorWidget(SignEditorWidget)


class InspectorWidget(QtGui.QWidget, Ui_inspectorWidget):
    def __init__(self, editorSession):
        """

        :param editorSession:
        :type editorSession: mcedit2.editorsession.EditorSession
        :return:
        :rtype:
        """
        super(InspectorWidget, self).__init__()
        self.setupUi(self)

        self.editorSession = editorSession

        self.blockNBTEditor.editorSession = self.editorSession
        self.entityNBTEditor.editorSession = self.editorSession
        self.chunkNBTEditor.editorSession = self.editorSession

        self.blockEditorWidget = None

        self.blockPos = None
        self.tileEntity = None

        self.entityPtr = None
        self.entity = None

        self.chunkPos = None
        self.currentChunk = None

        self.overlayNode = scenenode.Node("inspectorOverlay")
        self.selectionNode = SelectionBoxNode()
        self.selectionNode.depth = depths.DepthOffsets.SelectionCursor
        self.selectionNode.filled = False
        self.selectionNode.wireColor = (0.2, 0.9, .2, .8)

        self.overlayNode.addChild(self.selectionNode)

        self.commandBlockVisualsNode = None

        self.chunkTabWidget.currentChanged.connect(self.chunkTabDidChange)

        self.terrainPopulatedInput.toggled.connect(self.terrainPopulatedDidChange)
        self.lightPopulatedInput.toggled.connect(self.lightPopulatedDidChange)
        self.inhabitedTimeInput.valueChanged.connect(self.inhabitedTimeDidChange)
        self.updateTimeInput.valueChanged.connect(self.updateTimeDidChange)

        self.blockXSpinBox.valueChanged.connect(self.blockXChanged)
        self.blockYSpinBox.valueChanged.connect(self.blockYChanged)
        self.blockZSpinBox.valueChanged.connect(self.blockZChanged)

        self.removeEntityButton.clicked.connect(self.removeEntity)

        self.addTileEntityButton.clicked.connect(self.addTileEntity)
        self.removeTileEntityButton.clicked.connect(self.removeTileEntity)

        enabled = not self.editorSession.readonly

        self.removeEntityButton.setEnabled(enabled)

        self.addTileEntityButton.setEnabled(enabled)
        self.removeTileEntityButton.setEnabled(enabled)
        self.terrainPopulatedInput.setEnabled(enabled)
        self.lightPopulatedInput.setEnabled(enabled)
        self.inhabitedTimeInput.setEnabled(enabled)
        self.updateTimeInput.setEnabled(enabled)
        self.tileTicksSpinBox.setEnabled(enabled)

        self.editorSession.revisionChanged.connect(self.revisionDidChange)

    def revisionDidChange(self):
        if self.blockPos is not None:
            self.inspectBlock(self.blockPos)

        elif self.entityPtr is not None and self.entityPtr.get() is not None:
            self.inspectEntity(self.entityPtr)

        elif self.chunkPos is not None:
            self.inspectChunk(*self.chunkPos)
            self.chunkNBTEditor.refresh()

        else:
            self.inspectNothing()

    def _changed(self, value, idx):
        if self.blockPos is None:
            return

        if self.blockPos[idx] == value:
            return

        pos = list(self.blockPos)
        pos[idx] = value
        self.inspectBlock(Vector(*pos))

    def blockXChanged(self, value):
        self._changed(value, 0)

    def blockYChanged(self, value):
        self._changed(value, 1)

    def blockZChanged(self, value):
        self._changed(value, 2)

    def hide(self, *args, **kwargs):
        super(InspectorWidget, self).hide(*args, **kwargs)
        self.overlayNode.visible = False
    
    def show(self, *args, **kwargs):
        super(InspectorWidget, self).show(*args, **kwargs)
        self.overlayNode.visible = True

    def clearVisuals(self):
        if self.commandBlockVisualsNode:
            self.overlayNode.removeChild(self.commandBlockVisualsNode)
            self.commandBlockVisualsNode = None

    def inspectBlock(self, pos):
        self.clearVisuals()
        self.blockPos = pos
        self.entity = None
        self.entityPtr = None
        self.currentChunk = None
        self.chunkPos = None

        self.stackedWidget.setCurrentWidget(self.pageInspectBlock)
        x, y, z = pos
        self.blockXSpinBox.setValue(x)
        self.blockYSpinBox.setValue(y)
        self.blockZSpinBox.setValue(z)

        blockID = self.editorSession.currentDimension.getBlockID(x, y, z)
        blockData = self.editorSession.currentDimension.getBlockData(x, y, z)
        blockLight = self.editorSession.currentDimension.getBlockLight(x, y, z)
        skyLight = self.editorSession.currentDimension.getSkyLight(x, y, z)

        self.blockIDLabel.setText(str(blockID))
        self.blockDataLabel.setText(str(blockData))
        self.blockLightLabel.setText(str(blockLight))
        self.skyLightLabel.setText(str(skyLight))

        block = self.editorSession.currentDimension.getBlock(x, y, z)

        self.blockNameLabel.setText(block.displayName)
        self.blockInternalNameLabel.setText(block.internalName)
        self.blockStateLabel.setText(str(block.blockState))

        blockBox = BoundingBox((x, y, z), (1, 1, 1))

        self.selectionNode.selectionBox = blockBox

        self.updateTileEntity()

    def updateTileEntity(self):
        if self.blockEditorWidget:
            self.blockTabWidget.removeTab(0)
            self.blockEditorWidget = None

        pos = self.blockPos

        if pos is None:
            self.blockNBTEditor.setRootTagRef(None)
            return

        self.tileEntity = self.editorSession.currentDimension.getTileEntity(pos)
        log.info("Inspecting TileEntity %s at %s", self.tileEntity, pos)

        if self.tileEntity is not None:
            editorClass = tileEntityEditorClasses.get(self.tileEntity.id)
            if editorClass is not None:
                try:
                    self.blockEditorWidget = editorClass(self.editorSession, self.tileEntity)
                except Exception as e:
                    self.blockEditorWidget = QtGui.QLabel("Failed to load TileEntity editor:\n%s\n%s" % (
                        e,
                        traceback.format_exc(),
                                                                                                        ))
                    self.blockEditorWidget.displayName = "Error"

                displayName = getattr(self.blockEditorWidget, 'displayName', self.tileEntity.id)

                self.blockTabWidget.insertTab(0, self.blockEditorWidget, displayName)
                self.blockTabWidget.setCurrentIndex(0)

            self.blockNBTEditor.setRootTagRef(self.tileEntity)
        else:
            self.blockNBTEditor.setRootTagRef(None)

        self.removeTileEntityButton.setEnabled(self.tileEntity is not None and not self.editorSession.readonly)

        if self.tileEntity is not None:
            if self.tileEntity.id == "Control":
                try:
                    commandObj = ParseCommand(self.tileEntity.Command)
                    visuals = CommandVisuals(pos, commandObj)
                    self.commandBlockVisualsNode = visuals
                    self.overlayNode.addChild(visuals)
                    self.editorSession.updateView()
                except Exception as e:
                    log.warn("Failed to parse command.", exc_info=1)

    _tileEntityIDs = {
        "minecraft:command_block": "Control",
        "minecraft:standing_sign": "Sign",
        "minecraft:wall_sign": "Sign",
        "minecraft:chest": "Chest",
        "minecraft:hopper": "Hopper",
        "minecraft:dispenser": "Trap",
    }

    def addTileEntity(self):
        if self.tileEntity is not None:
            return
        block = self.editorSession.currentDimension.getBlock(*self.blockPos)

        tileEntityID = self._tileEntityIDs[block.internalName]

        ref = self.editorSession.worldEditor.TileEntityRef.create(tileEntityID)
        ref.Position = self.blockPos

        with self.editorSession.beginSimpleCommand("Create TileEntity"):
            self.editorSession.currentDimension.addTileEntity(ref)

        self.updateTileEntity()

    def removeTileEntity(self):
        if self.tileEntity is not None:
            with self.editorSession.beginSimpleCommand("Remove TileEntity"):
                self.editorSession.currentDimension.removeTileEntity(self.tileEntity)
                self.tileEntity = None

    def inspectEntity(self, entityPtr):
        self.tileEntity = None
        self.chunkPos = None
        self.blockPos = None

        self.clearVisuals()

        self.entityPtr = entityPtr
        if self.entityPtr is not None:
            self.entity = entity = entityPtr.get()
        else:
            self.entity = None

        if self.entity is not None:
            self.stackedWidget.setCurrentWidget(self.pageInspectEntity)
            self.entityIDLabel.setText(entity.id)
            try:
                self.entityUUIDLabel.setText(str(entity.UUID))
            except KeyError:
                self.entityUUIDLabel.setText(self.tr("(Not set)"))

            x, y, z = entity.Position
            self.entityXLabel.setText("%0.2f" % x)
            self.entityYLabel.setText("%0.2f" % y)
            self.entityZLabel.setText("%0.2f" % z)

            self.entityNBTEditor.setRootTagRef(entity)

            # xxx entity bounds per type

            entityBox = BoundingBox((x-.5, y, z-.5), (1, 2, 1))

            self.selectionNode.selectionBox = entityBox
        else:
            self.selectionNode.selectionBox = None
            self.entityNBTEditor.setRootTagRef(None)

    def removeEntity(self):
        if self.entity is None:
            return

        with self.editorSession.beginSimpleCommand(self.tr("Remove Entity")):
            self.entity.chunk.Entities.remove(self.entity)
            self.entity = None

    def inspectChunk(self, cx, cz):
        self.clearVisuals()
        self.chunkPos = (cx, cz)
        self.entityPtr = None
        self.tileEntity = None
        self.blockPos = None

        dim = self.editorSession.currentDimension
        if dim.containsChunk(cx, cz):
            chunk = dim.getChunk(cx, cz)
            self.setSelectedChunk(chunk)
            self.stackedWidget.setCurrentWidget(self.pageInspectChunk)

    def inspectNothing(self):
        self.clearVisuals()
        self.chunkPos = None
        self.currentChunk = None
        self.entityPtr = None
        self.tileEntity = None
        self.blockPos = None
        self.stackedWidget.setCurrentWidget(self.pageInspectNothing)

        self.updateChunkNBTView()

    def setSelectedChunk(self, chunk):
        self.selectionNode.selectionBox = chunk.bounds
        self.currentChunk = chunk
        self.updateChunkWidget()
        self.updateChunkNBTView()

    def updateChunkWidget(self):
        if self.currentChunk:
            chunk = self.currentChunk
            cx, cz = chunk.chunkPosition

            self.chunkCXLabel.setText(str(cx))
            self.chunkCZLabel.setText(str(cz))
            self.terrainPopulatedInput.setEnabled(True)
            self.terrainPopulatedInput.setChecked(chunk.TerrainPopulated)

            levelTag = chunk.rootTag["Level"]
            if "LightPopulated" in levelTag:
                self.lightPopulatedInput.setEnabled(True)
                self.lightPopulatedInput.setChecked(levelTag["LightPopulated"].value)
            else:
                self.lightPopulatedInput.setEnabled(False)

            if "InhabitedTime" in levelTag:
                self.inhabitedTimeInput.setEnabled(True)
                self.inhabitedTimeInput.setValue(levelTag["InhabitedTime"].value)
            else:
                self.inhabitedTimeInput.setEnabled(False)

            if "LastUpdate" in levelTag:
                self.updateTimeInput.setEnabled(True)
                self.updateTimeInput.setValue(levelTag["LastUpdate"].value)
            else:
                self.updateTimeInput.setEnabled(False)
        else:
            self.terrainPopulatedInput.setEnabled(False)
            self.lightPopulatedInput.setEnabled(False)
            self.inhabitedTimeInput.setEnabled(False)
            self.updateTimeInput.setEnabled(False)

    def terrainPopulatedDidChange(self, value):
        if self.currentChunk.TerrainPopulated == value:
            return

        with self.editorSession.beginSimpleCommand(self.tr("Change chunk (%s, %s) property TerrainPopulated")
                                                   % self.currentChunk.chunkPosition):
            self.currentChunk.TerrainPopulated = value

    def lightPopulatedDidChange(self, value):
        if self.currentChunk.rootTag["Level"]["LightPopulated"].value == value:
            return

        with self.editorSession.beginSimpleCommand(self.tr("Change chunk (%s, %s) property LightPopulated")
                                                   % self.currentChunk.chunkPosition):
            self.currentChunk.rootTag["Level"]["LightPopulated"].value = value


    def inhabitedTimeDidChange(self, value):
        if self.currentChunk.rootTag["Level"]["InhabitedTime"].value == value:
            return

        with self.editorSession.beginSimpleCommand(self.tr("Change chunk (%s, %s) property InhabitedTime")
                                                   % self.currentChunk.chunkPosition):
            self.currentChunk.rootTag["Level"]["InhabitedTime"].value = value


    def updateTimeDidChange(self, value):
        if self.currentChunk.rootTag["Level"]["LastUpdate"].value == value:
            return

        with self.editorSession.beginSimpleCommand(self.tr("Change chunk (%s, %s) property LastUpdate")
                                                   % self.currentChunk.chunkPosition):
            self.currentChunk.rootTag["Level"]["LastUpdate"].value = value


    def chunkTabDidChange(self, index):
        if self.chunkTabWidget.widget(index) is self.chunkPropertiesTab:
            self.updateChunkWidget()
        else:  # NBT tab
            pass

    def updateChunkNBTView(self):
        chunk = self.currentChunk
        if chunk is None:
            self.chunkNBTEditor.setRootTagRef(None)
            return

        self.chunkNBTEditor.setRootTagRef(chunk)
    #
    # def chunkPositionDidChange(self):
    #     cx = self.cxSpinBox.value()
    #     cz = self.czSpinBox.value()
    #     self.selectChunk(cx, cz)
