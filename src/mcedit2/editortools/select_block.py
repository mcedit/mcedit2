"""
    select block
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from PySide import QtGui

from mcedit2.editortools import EditorTool
from mcedit2.util.load_ui import load_ui


log = logging.getLogger(__name__)

class SelectBlockTool(EditorTool):
    name = "Select Block"
    iconName = "edit_block"
    selectionRay = None
    currentEntity = None

    def __init__(self, editorSession, *args, **kwargs):
        """
        :type editorSession: EditorSession
        """
        super(SelectBlockTool, self).__init__(editorSession, *args, **kwargs)
        self.mousePos = None
        self.toolWidget = load_ui("editortools/select_block.ui")

    def mousePress(self, event):
        self.setMousePos(event.blockPosition)

    def setMousePos(self, pos):
        self.mousePos = pos
        self.editorSession.inspectBlock(pos)









