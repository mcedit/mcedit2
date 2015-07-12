"""
    player
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from mcedit2.editortools import EditorTool
from mcedit2.rendering.selection import SelectionBoxNode
from mcedit2.rendering.scenegraph import scenenode
from mcedit2.util.load_ui import load_ui


log = logging.getLogger(__name__)

class ChunkTool(EditorTool):
    name = "Edit Chunk"
    iconName = "edit_chunk"

    def __init__(self, editorSession, *args, **kwargs):
        """

        :type editorSession: EditorSession
        """
        super(ChunkTool, self).__init__(editorSession, *args, **kwargs)

        self.toolWidget = load_ui("editortools/edit_chunk.ui")
        self.toolWidget.tabWidget.currentChanged.connect(self.tabDidChange)

        self.toolWidget.terrainPopulatedInput.toggled.connect(self.terrainPopulatedDidChange)
        self.toolWidget.lightPopulatedInput.toggled.connect(self.lightPopulatedDidChange)
        self.toolWidget.inhabitedTimeInput.valueChanged.connect(self.inhabitedTimeDidChange)
        self.toolWidget.updateTimeInput.valueChanged.connect(self.updateTimeDidChange)

        self.toolWidget.cxSpinBox.valueChanged.connect(self.chunkPositionDidChange)
        self.toolWidget.czSpinBox.valueChanged.connect(self.chunkPositionDidChange)

        self.toolWidget.nbtEditor.editorSession = self.editorSession

        self.currentChunk = None
        self.selectionNode = None
        self.overlayNode = scenenode.Node()
        self.updateChunkWidget()
        self.updateNBTView()

    def toolInactive(self):
        if self.selectionNode:
            self.overlayNode.removeChild(self.selectionNode)
            self.selectionNode = None
            self.currentChunk = None
            self.updateChunkWidget()


    def updateChunkWidget(self):
        if self.currentChunk:
            chunk = self.currentChunk

            self.toolWidget.terrainPopulatedInput.setEnabled(True)
            self.toolWidget.terrainPopulatedInput.setChecked(chunk.TerrainPopulated)

            levelTag = chunk.rootTag["Level"]
            if "LightPopulated" in levelTag:
                self.toolWidget.lightPopulatedInput.setEnabled(True)
                self.toolWidget.lightPopulatedInput.setChecked(levelTag["LightPopulated"].value)
            else:
                self.toolWidget.lightPopulatedInput.setEnabled(False)

            if "InhabitedTime" in levelTag:
                self.toolWidget.inhabitedTimeInput.setEnabled(True)
                self.toolWidget.inhabitedTimeInput.setValue(levelTag["InhabitedTime"].value)
            else:
                self.toolWidget.inhabitedTimeInput.setEnabled(False)

            if "LastUpdate" in levelTag:
                self.toolWidget.updateTimeInput.setEnabled(True)
                self.toolWidget.updateTimeInput.setValue(levelTag["LastUpdate"].value)
            else:
                self.toolWidget.updateTimeInput.setEnabled(False)
        else:
            self.toolWidget.terrainPopulatedInput.setEnabled(False)
            self.toolWidget.lightPopulatedInput.setEnabled(False)
            self.toolWidget.inhabitedTimeInput.setEnabled(False)
            self.toolWidget.updateTimeInput.setEnabled(False)


    def terrainPopulatedDidChange(self, value):
        self.currentChunk.TerrainPopulated = value

    def lightPopulatedDidChange(self, value):
        self.currentChunk.rootTag["Level"]["LightPopulated"].value = value

    def inhabitedTimeDidChange(self, value):
        self.currentChunk.rootTag["Level"]["InhabitedTime"].value = value

    def updateTimeDidChange(self, value):
        self.currentChunk.rootTag["Level"]["LastUpdate"].value = value

    def tabDidChange(self, index):
        if index == 0:  # Chunk tab
            self.updateChunkWidget()
        else:  # NBT tab
            pass

    def mousePress(self, event):
        x, y, z = event.blockPosition
        cx = x >> 4
        cz = z >> 4
        self.selectChunk(cx, cz)

    def selectChunk(self, cx, cz):
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
        self.updateNBTView()

    def updateNBTView(self):
        chunk = self.currentChunk
        if chunk is None:
            self.toolWidget.nbtEditor.setRootTagRef(None)
            return

        self.toolWidget.nbtEditor.setRootTagRef(chunk)

        self.toolWidget.cxSpinBox.setValue(chunk.cx)
        self.toolWidget.czSpinBox.setValue(chunk.cz)

    def chunkPositionDidChange(self):
        cx = self.toolWidget.cxSpinBox.value()
        cz = self.toolWidget.czSpinBox.value()
        self.selectChunk(cx, cz)
