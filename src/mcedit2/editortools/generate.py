"""
    create
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from PySide import QtCore, QtGui

from mcedit2.editortools import EditorTool
from mcedit2.widgets.layout import Column


log = logging.getLogger(__name__)

class GenerateTool(EditorTool):
    name = "Generate"
    iconName = "generate"

    def __init__(self, *args, **kwargs):
        EditorTool.__init__(self, *args, **kwargs)
        self.createToolWidget()

    def createToolWidget(self):
        toolWidget = QtGui.QWidget()

        self.toolWidget = toolWidget
        self.toolWidget.setLayout(Column(*[QtGui.QLabel("Creation Tool Options...") for i in range(12)]))

    def mousePress(self, event):
        pass

    def mouseMove(self, event):
        pass

    def mouseRelease(self, event):
        pass

