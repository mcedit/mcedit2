"""
    select block
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from PySide import QtGui

from mcedit2.editortools import EditorTool
from mcedit2.util.load_ui import load_ui


log = logging.getLogger(__name__)


class SelectBlockCommand(QtGui.QUndoCommand):
    def __init__(self, tool, mousePos, *args, **kwargs):
        QtGui.QUndoCommand.__init__(self, *args, **kwargs)
        self.setText("Select Block")
        self.mousePos = mousePos
        self.tool = tool

    def undo(self):
        self.tool.setMousePos(self.ray)

    def redo(self):
        self.previousPos = self.tool.mousePos
        self.tool.setMousePos(self.mousePos)


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
        self.createToolWidget()
        self.mousePos = None

    def createToolWidget(self):
        self.toolWidget = load_ui("editortools/select_block.ui")

    def mousePress(self, event):
        command = SelectBlockCommand(self, event.blockPosition)
        self.editorSession.pushCommand(command)

    def setMousePos(self, pos):
        self.mousePos = pos
        self.editorSession.inspectBlock(pos)









