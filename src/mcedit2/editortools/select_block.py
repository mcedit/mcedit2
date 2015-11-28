"""
    select block
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from PySide import QtGui

from mcedit2.editortools import EditorTool
from mcedit2.ui.editortools.select_block import Ui_selectBlockWidget


log = logging.getLogger(__name__)


class SelectBlockToolWidget(QtGui.QWidget, Ui_selectBlockWidget):
    def __init__(self, *args, **kwargs):
        super(SelectBlockToolWidget, self).__init__(*args, **kwargs)
        self.setupUi(self)


class SelectBlockTool(EditorTool):
    name = "Inspect Block"
    iconName = "edit_block"
    selectionRay = None
    currentEntity = None

    def __init__(self, editorSession, *args, **kwargs):
        """
        :type editorSession: EditorSession
        """
        super(SelectBlockTool, self).__init__(editorSession, *args, **kwargs)
        self.mousePos = None
        self.toolWidget = SelectBlockToolWidget()

    def mousePress(self, event):
        self.setMousePos(event.blockPosition)

    def setMousePos(self, pos):
        self.mousePos = pos
        self.editorSession.inspectBlock(pos)









