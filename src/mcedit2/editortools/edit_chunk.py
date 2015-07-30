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
    name = "Inspect Chunk"
    iconName = "edit_chunk"

    def __init__(self, editorSession, *args, **kwargs):
        """
        :type editorSession: EditorSession
        """
        super(ChunkTool, self).__init__(editorSession, *args, **kwargs)
        self.mousePos = None
        self.toolWidget = load_ui("editortools/select_chunk.ui")

    def mousePress(self, event):
        self.setMousePos(event.blockPosition)

    def setMousePos(self, pos):
        x, y, z = self.mousePos = pos
        cx = x >> 4
        cz = z >> 4
        self.editorSession.inspectChunk(cx, cz)

