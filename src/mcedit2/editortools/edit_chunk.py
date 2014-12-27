"""
    player
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from PySide.QtCore import Qt
from mcedit2.editortools import EditorTool
from mcedit2.nbt_treemodel import NBTTreeModel, NBTFilterProxyModel
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
        self.currentChunk = None

    def mousePress(self, event):
        x, y, z = event.blockPosition
        cx = x >> 4
        cz = z >> 4
        dim = self.editorSession.currentDimension
        if dim.containsChunk(cx, cz):
            chunk = dim.getChunk(cx, cz)
            self.setSelectedChunk(chunk)

    def setSelectedChunk(self, chunk):
        self.currentChunk = chunk

        model = NBTTreeModel(chunk.rootTag)

        self.toolWidget.nbtTreeView.setModel(model)

        self.toolWidget.cxSpinBox.setValue(chunk.cx)
        self.toolWidget.czSpinBox.setValue(chunk.cz)

