"""
    inspector
"""
from __future__ import absolute_import, division, print_function
import logging
import traceback

from PySide import QtGui
from mcedit2.command import SimpleRevisionCommand
from mcedit2.rendering.scenegraph import scenenode
from mcedit2.rendering.selection import SelectionBoxNode

from mcedit2.widgets.inspector.tileentities.chest import ChestEditorWidget, DispenserEditorWidget, HopperEditorWidget
from mcedit2.util.load_ui import load_ui
from mcedit2.widgets.inspector.tileentities.command import CommandBlockEditorWidget

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

class InspectorWidget(QtGui.QWidget):
    def __init__(self, editorSession):
        """

        :param editorSession:
        :type editorSession: mcedit2.editorsession.EditorSession
        :return:
        :rtype:
        """
        super(InspectorWidget, self).__init__()
        load_ui("inspector.ui", baseinstance=self)
        self.editorSession = editorSession

        self.blockNBTEditor.editorSession = self.editorSession
        self.entityNBTEditor.editorSession = self.editorSession
        self.chunkNBTEditor.editorSession = self.editorSession

        self.blockEditorWidget = None

        self.tileEntity = None
        self.entity = None

        self.currentChunk = None

        # xxxx unused! how!
        self.selectionNode = None
        self.overlayNode = scenenode.Node()

        self.chunkTabWidget.currentChanged.connect(self.chunkTabDidChange)

        self.terrainPopulatedInput.toggled.connect(self.terrainPopulatedDidChange)
        self.lightPopulatedInput.toggled.connect(self.lightPopulatedDidChange)
        self.inhabitedTimeInput.valueChanged.connect(self.inhabitedTimeDidChange)
        self.updateTimeInput.valueChanged.connect(self.updateTimeDidChange)

    def inspectBlock(self, pos):
        self.entity = None

        self.stackedWidget.setCurrentWidget(self.pageInspectBlock)
        x, y, z = pos
        self.blockXLabel.setText(str(x))
        self.blockYLabel.setText(str(y))
        self.blockZLabel.setText(str(z))

        if self.blockEditorWidget:
            self.blockTabWidget.removeTab(0)
            self.blockEditorWidget = None

        self.tileEntity = self.editorSession.currentDimension.getTileEntity(pos)

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

        self.removeTileEntityButton.setEnabled(self.tileEntity is not None)

    def inspectEntity(self, entity):
        self.tileEntity = None

        self.entity = entity
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


    # def toolInactive(self):
    #     if self.selectionNode:
    #         self.overlayNode.removeChild(self.selectionNode)
    #         self.selectionNode = None
    #         self.currentChunk = None
    #         self.updateChunkWidget()

    def inspectChunk(self, cx, cz):
        dim = self.editorSession.currentDimension
        if dim.containsChunk(cx, cz):
            chunk = dim.getChunk(cx, cz)
            self.setSelectedChunk(chunk)

    def setSelectedChunk(self, chunk):
        if self.selectionNode is None:
            self.selectionNode = SelectionBoxNode()
            self.selectionNode.filled = False
            self.selectionNode.color = (0.3, 0.3, 1, .3)
            self.overlayNode.addChild(self.selectionNode)

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
        command = InspectPropertyChangeCommand(self.editorSession,
                                               self.tr("Change chunk (%s, %s) property TerrainPopulated")
                                               % self.currentChunk.chunkPosition)
        with command.begin():
            self.currentChunk.TerrainPopulated = value
        self.editorSession.pushCommand(command)

    def lightPopulatedDidChange(self, value):
        command = InspectPropertyChangeCommand(self.editorSession,
                                               self.tr("Change chunk (%s, %s) property LightPopulated")
                                               % self.currentChunk.chunkPosition)
        with command.begin():
            self.currentChunk.rootTag["Level"]["LightPopulated"].value = value
        self.editorSession.pushCommand(command)

    def inhabitedTimeDidChange(self, value):
        command = InspectPropertyChangeCommand(self.editorSession,
                                               self.tr("Change chunk (%s, %s) property InhabitedTime")
                                               % self.currentChunk.chunkPosition)
        with command.begin():
            self.currentChunk.rootTag["Level"]["InhabitedTime"].value = value
        self.editorSession.pushCommand(command)

    def updateTimeDidChange(self, value):
        command = InspectPropertyChangeCommand(self.editorSession,
                                               self.tr("Change chunk (%s, %s) property LastUpdate")
                                               % self.currentChunk.chunkPosition)
        with command.begin():
            self.currentChunk.rootTag["Level"]["LastUpdate"].value = value
        self.editorSession.pushCommand(command)

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

class InspectPropertyChangeCommand(SimpleRevisionCommand):
    pass